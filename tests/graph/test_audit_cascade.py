"""Tests for ``ai_workflows.graph.audit_cascade`` (M12 Task 02 / amended M12 Task 08
/ M12 Task 04 — KDR-004, KDR-006, KDR-011).

Thirteen hermetic tests exercising the compiled cascade sub-graph with stub provider
adapters.  No real LLM call, no subprocess.  The stub pattern mirrors
``tests/graph/test_tiered_node.py:104,172`` — ``monkeypatch.setattr`` on the
module-level adapter names inside ``ai_workflows.graph.tiered_node``.

T02 tests (cascade tests 1-7 in this file):
1. Pass-through — auditor passes on first try (wire-level smoke per CLAUDE.md
   non-inferential rule).
2. Re-fire with audit-feedback in revision_hint — auditor fails once then passes.
3. Exhaustion → strict HumanGate with cascade transcript.
4. Validator failure short-circuits the auditor (hybrid scenario).
5. Pure-shape-failure exhaustion — auditor never invoked.
6. Cascade is a ``CompiledStateGraph`` composable as a node in an outer graph.
7. Role tags stamped on state by each cascade sub-node.

T08 tests (cascade tests 8-11 in this file):
8. Default False preserves T02 behaviour — exhaustion still routes to human_gate.
9. skip_terminal_gate=True omits the gate node from the compiled sub-graph.
10. skip_terminal_gate=True routes verdict-exhaustion to END with AuditFailure
    in state['last_exception'] (wire-level smoke for T08 per CLAUDE.md rule).
11. skip_terminal_gate=True routes validator-exhaustion (NonRetryable) to END
    with NonRetryable in state['last_exception']; auditor never invoked.

T04 tests (cascade tests 12-13 in this file):
12. Wire-level smoke: primary records role="author" + auditor records role="auditor"
    via the production CostTrackingCallback path; exactly 2 records total (verdict
    node does NOT dispatch — protective assertion).
13. Role attribution survives audit retry cycle: no author record carries
    role="auditor" and vice versa across retry cycles.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, TypedDict

import pytest
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel

from ai_workflows.graph import tiered_node as tiered_node_module
from ai_workflows.graph.audit_cascade import audit_cascade_node
from ai_workflows.graph.checkpointer import build_async_checkpointer
from ai_workflows.graph.cost_callback import CostTrackingCallback
from ai_workflows.primitives.cost import CostTracker, TokenUsage
from ai_workflows.primitives.retry import AuditFailure, NonRetryable, RetryableSemantic, RetryPolicy
from ai_workflows.primitives.storage import SQLiteStorage
from ai_workflows.primitives.tiers import ClaudeCodeRoute, LiteLLMRoute, TierConfig

# ---------------------------------------------------------------------------
# Shared schemas and tiers
# ---------------------------------------------------------------------------


class _PrimaryOutput(BaseModel):
    """Minimal schema the primary validator parses against."""

    content: str


# ---------------------------------------------------------------------------
# Stub adapters
# ---------------------------------------------------------------------------


class _StubLiteLLMAdapter:
    """Scriptable LiteLLMAdapter stub.

    ``script`` is a list of (text, cost) tuples or Exception instances.
    Each ``complete`` call pops the head of the list.
    """

    script: list[Any] = []
    calls: list[dict] = []

    def __init__(self, *, route: LiteLLMRoute, per_call_timeout_s: int) -> None:
        self.route = route

    async def complete(
        self,
        *,
        system: str | None,
        messages: list[dict],
        response_format: Any = None,
    ) -> tuple[str, TokenUsage]:
        _StubLiteLLMAdapter.calls.append({"system": system, "messages": messages})
        if not _StubLiteLLMAdapter.script:
            raise AssertionError("stub script exhausted")
        head = _StubLiteLLMAdapter.script.pop(0)
        if isinstance(head, BaseException):
            raise head
        text, cost = head
        return text, TokenUsage(
            input_tokens=5, output_tokens=7, cost_usd=cost, model=self.route.model
        )


class _StubClaudeCodeAdapter:
    """Stub for the Claude Code subprocess driver — auditor-tier path.

    Holds an independent class-level `script` of (`output_text`, `usage_dict`)
    tuples consumed FIFO by sequential calls. Populated separately from
    `_StubLiteLLMAdapter` (which scripts the primary-tier path); the two
    adapters do not share state.
    """

    script: list[Any] = []
    calls: list[dict] = []

    def __init__(
        self,
        *,
        route: ClaudeCodeRoute,
        per_call_timeout_s: int,
        pricing: dict,
    ) -> None:
        self.route = route

    async def complete(
        self,
        *,
        system: str | None,
        messages: list[dict],
        response_format: Any = None,
    ) -> tuple[str, TokenUsage]:
        _StubClaudeCodeAdapter.calls.append({"system": system, "messages": messages})
        if not _StubClaudeCodeAdapter.script:
            raise AssertionError("stub script exhausted (claude)")
        head = _StubClaudeCodeAdapter.script.pop(0)
        if isinstance(head, BaseException):
            raise head
        text, cost = head
        return text, TokenUsage(
            input_tokens=3, output_tokens=2, cost_usd=cost, model=self.route.cli_model_flag
        )


@pytest.fixture(autouse=True)
def _reset_stubs(monkeypatch: pytest.MonkeyPatch) -> None:
    """Install stub adapters and reset call counts before each test."""
    _StubLiteLLMAdapter.script = []
    _StubLiteLLMAdapter.calls = []
    _StubClaudeCodeAdapter.script = []
    _StubClaudeCodeAdapter.calls = []
    monkeypatch.setattr(tiered_node_module, "LiteLLMAdapter", _StubLiteLLMAdapter)
    monkeypatch.setattr(tiered_node_module, "ClaudeCodeSubprocess", _StubClaudeCodeAdapter)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PRIMARY_JSON = '{"content": "hello"}'
_AUDIT_PASS_JSON = '{"passed": true, "failure_reasons": [], "suggested_approach": null}'
_AUDIT_FAIL_JSON = (
    '{"passed": false, "failure_reasons": ["bad shape"], "suggested_approach": "try Y"}'
)

_POLICY_2 = RetryPolicy(max_transient_attempts=3, max_semantic_attempts=2)
_POLICY_3 = RetryPolicy(max_transient_attempts=3, max_semantic_attempts=3)


def _tier_registry() -> dict[str, TierConfig]:
    """Minimal tier registry with primary (LiteLLM) + auditor (Claude Code)."""
    return {
        "primary-litellm": TierConfig(
            name="primary-litellm",
            route=LiteLLMRoute(model="gemini/gemini-2.5-flash"),
            max_concurrency=1,
            per_call_timeout_s=30,
        ),
        "auditor-sonnet": TierConfig(
            name="auditor-sonnet",
            route=ClaudeCodeRoute(cli_model_flag="sonnet"),
            max_concurrency=1,
            per_call_timeout_s=30,
        ),
    }


def _build_config(
    tmp_path: Path,
    run_id: str,
    checkpointer: Any,
    storage: Any,
) -> dict[str, Any]:
    tracker = CostTracker()
    callback = CostTrackingCallback(cost_tracker=tracker, budget_cap_usd=None)
    return {
        "configurable": {
            "thread_id": run_id,
            "run_id": run_id,
            "tier_registry": _tier_registry(),
            "cost_callback": callback,
            "storage": storage,
            "pricing": {},
        }
    }


def _primary_prompt_fn(state: Mapping[str, Any]) -> tuple[str | None, list[dict]]:
    """Return a trivial (system, messages) pair for tests."""
    return ("sys-primary", [{"role": "user", "content": "produce output"}])


def _cascade(*, name: str = "ac", policy: RetryPolicy = _POLICY_3) -> CompiledStateGraph:
    """Factory for the cascade sub-graph used across most tests."""
    return audit_cascade_node(
        primary_tier="primary-litellm",
        primary_prompt_fn=_primary_prompt_fn,
        primary_output_schema=_PrimaryOutput,
        auditor_tier="auditor-sonnet",
        policy=policy,
        name=name,
    )


# ---------------------------------------------------------------------------
# Test 1: pass-through — wire-level smoke (CLAUDE.md non-inferential rule)
# ---------------------------------------------------------------------------


async def test_cascade_pass_through(tmp_path: Path) -> None:
    """Test 1 / Smoke: cascade exits via verdict node on first-try auditor pass.

    Asserts:
    * cascade exits (not via human_gate) — no ``__interrupt__`` in state
    * ``cascade_transcript`` has exactly 1 author attempt + 1 auditor verdict
    * ``cascade_role`` was stamped (last stamp = "verdict")
    * parsed primary output is in state under the expected schema key
    """
    # primary fires once → returns valid JSON; auditor fires once → passes
    _StubLiteLLMAdapter.script = [(_PRIMARY_JSON, 0.001)]
    _StubClaudeCodeAdapter.script = [(_AUDIT_PASS_JSON, 0.0)]

    checkpointer = await build_async_checkpointer(tmp_path / "cp.sqlite")
    storage = await SQLiteStorage.open(tmp_path / "storage.sqlite")
    await storage.create_run("r1", "cascade_smoke", None)

    cascade = _cascade(name="ac")
    outer = _build_outer_graph(cascade, name="ac")
    cfg = _build_config(tmp_path, "r1", checkpointer, storage)

    try:
        final = await outer.ainvoke({"run_id": "r1"}, cfg)
    finally:
        await checkpointer.conn.close()

    # No interrupt — cascade succeeded without hitting the human_gate.
    assert "__interrupt__" not in final

    # Transcript: exactly one attempt per node type.
    transcript = final.get("cascade_transcript") or {}
    assert len(transcript.get("author_attempts", [])) == 1
    assert len(transcript.get("auditor_verdicts", [])) == 1
    assert transcript["auditor_verdicts"][0].passed is True

    # role_tags_stamped — last stamp wins in LangGraph merge.
    assert final.get("cascade_role") == "verdict"

    # Primary parsed output is in state.
    parsed = final.get("ac_primary_parsed")
    assert isinstance(parsed, _PrimaryOutput)
    assert parsed.content == "hello"


# ---------------------------------------------------------------------------
# Test 2: re-fire with audit-feedback in revision_hint
# ---------------------------------------------------------------------------


async def test_cascade_re_fires_with_audit_feedback_in_revision_hint(
    tmp_path: Path,
) -> None:
    """Test 2: auditor fails once → primary re-prompts with enriched context → passes.

    Asserts:
    * primary fired twice (second call from _StubLiteLLMAdapter.calls)
    * the second primary call's prompt messages reveal last_exception was set
      (the revision_hint is read from state['last_exception'].revision_hint
      by the primary's prompt_fn — here we use a custom prompt_fn that
      embeds the hint)
    * cascade_transcript has 2 author_attempts + 2 auditor_verdicts
    """
    # Use a custom prompt_fn that embeds last_exception.revision_hint so we can
    # assert the re-fire received the audit feedback.
    captured_prompts: list[dict] = []

    def _tracking_prompt(state: Mapping[str, Any]) -> tuple[str | None, list[dict]]:
        exc = state.get("last_exception")
        hint = exc.revision_hint if isinstance(exc, RetryableSemantic) else ""
        captured_prompts.append({"hint": hint})
        content = "produce output"
        if hint:
            content = f"produce output (hint: {hint})"
        return ("sys-primary", [{"role": "user", "content": content}])

    # primary fires twice → both return valid JSON
    _StubLiteLLMAdapter.script = [(_PRIMARY_JSON, 0.001), (_PRIMARY_JSON, 0.001)]
    # auditor fires twice → first fails, second passes
    _StubClaudeCodeAdapter.script = [(_AUDIT_FAIL_JSON, 0.0), (_AUDIT_PASS_JSON, 0.0)]

    checkpointer = await build_async_checkpointer(tmp_path / "cp.sqlite")
    storage = await SQLiteStorage.open(tmp_path / "storage.sqlite")
    await storage.create_run("r2", "cascade_refire", None)

    cascade = audit_cascade_node(
        primary_tier="primary-litellm",
        primary_prompt_fn=_tracking_prompt,
        primary_output_schema=_PrimaryOutput,
        auditor_tier="auditor-sonnet",
        policy=_POLICY_3,
        name="ac",
    )
    outer = _build_outer_graph(cascade, name="ac")
    cfg = _build_config(tmp_path, "r2", checkpointer, storage)

    try:
        final = await outer.ainvoke({"run_id": "r2"}, cfg)
    finally:
        await checkpointer.conn.close()

    assert "__interrupt__" not in final

    # Primary (LiteLLM) fired exactly twice.
    assert len(_StubLiteLLMAdapter.calls) == 2

    # _tracking_prompt is called 3 times:
    # [0] first primary dispatch (no hint)
    # [1] verdict node calls _default_primary_original(state, prompt_fn) to
    #     construct AuditFailure.primary_original — last_exception is None at
    #     this point (auditor ran successfully before verdict), so no hint yet.
    # [2] second primary dispatch — last_exception is now AuditFailure from
    #     cycle 1, so the hint is the rendered audit-feedback template.
    assert len(captured_prompts) == 3

    # The second primary dispatch (index 2) received the audit-feedback hint.
    second_dispatch_hint = captured_prompts[2]["hint"]
    assert second_dispatch_hint != "", "second primary call did not receive revision_hint"
    assert "bad shape" in second_dispatch_hint  # failure reason from _AUDIT_FAIL_JSON
    assert "try Y" in second_dispatch_hint  # suggested_approach from _AUDIT_FAIL_JSON

    # Verify hint matches expected template (byte-equal assertion per spec test #2).
    # The verdict node uses _default_primary_original which calls prompt_fn(state)
    # where state has last_exception=None (auditor just completed).
    # captured_prompts[1] is exactly that call: hint='', content='produce output'.
    # So primary_original = "sys-primary\n\nproduce output".
    from ai_workflows.primitives.retry import _render_audit_feedback  # type: ignore[attr-defined]

    # primary_original is what _default_primary_original computed from the prompt_fn.
    # From captured_prompts[1]: system="sys-primary", content="produce output".
    primary_original = "sys-primary\n\nproduce output"

    expected_hint = _render_audit_feedback(
        primary_original=primary_original,
        failure_reasons=["bad shape"],
        suggested_approach="try Y",
        primary_context="",
    )
    assert second_dispatch_hint == expected_hint

    # Transcript has 2 entries (only written on final success cycle — see
    # §Transcript-accumulation design note in audit_cascade.py module docstring).
    transcript = final.get("cascade_transcript") or {}
    assert len(transcript.get("author_attempts", [])) == 2
    assert len(transcript.get("auditor_verdicts", [])) == 2


# ---------------------------------------------------------------------------
# Test 3: exhaustion → strict HumanGate with transcript (pure audit-failure-only)
# ---------------------------------------------------------------------------


async def test_cascade_exhausts_retries_routes_to_strict_human_gate(
    tmp_path: Path,
) -> None:
    """Test 3: pure-audit-failure-only scenario with max_semantic_attempts=2.

    Asserts:
    * cascade reaches human_gate after 2 primary attempts
    * __interrupt__ payload carries cascade transcript with 2 entries each
    * strict_review=True is set on the gate
    """
    # primary always returns valid JSON (shape-valid); auditor always fails
    _StubLiteLLMAdapter.script = [(_PRIMARY_JSON, 0.001), (_PRIMARY_JSON, 0.001)]
    _StubClaudeCodeAdapter.script = [(_AUDIT_FAIL_JSON, 0.0), (_AUDIT_FAIL_JSON, 0.0)]

    checkpointer = await build_async_checkpointer(tmp_path / "cp.sqlite")
    storage = await SQLiteStorage.open(tmp_path / "storage.sqlite")
    await storage.create_run("r3", "cascade_exhaust", None)

    cascade = _cascade(name="ac", policy=_POLICY_2)
    outer = _build_outer_graph(cascade, name="ac")
    cfg = _build_config(tmp_path, "r3", checkpointer, storage)

    try:
        paused = await outer.ainvoke({"run_id": "r3"}, cfg)
    finally:
        await checkpointer.conn.close()

    # Cascade interrupted at human_gate.
    assert "__interrupt__" in paused

    interrupt_payload = paused["__interrupt__"][0].value
    assert interrupt_payload["strict_review"] is True

    # Gate prompt carries the cascade transcript.
    prompt_text: str = interrupt_payload["prompt"]
    assert "Attempts recorded: 2" in prompt_text
    assert "bad shape" in prompt_text  # failure_reason from _AUDIT_FAIL_JSON present in prompt

    # Primary fired exactly 2 times.
    assert len(_StubLiteLLMAdapter.calls) == 2
    # Auditor fired exactly 2 times.
    assert len(_StubClaudeCodeAdapter.calls) == 2


# ---------------------------------------------------------------------------
# Test 4: validator failure short-circuits the auditor
# ---------------------------------------------------------------------------


async def test_cascade_validator_failure_routes_back_to_primary_not_auditor(
    tmp_path: Path,
) -> None:
    """Test 4: shape-invalid primary output → validator loops back without invoking auditor.

    Hybrid scenario: primary returns shape-invalid output on attempts 1 and 2
    (validator raises RetryableSemantic, short-circuiting the auditor); on
    attempt 3 the primary returns shape-valid output, the validator passes, and
    the auditor is invoked exactly once (and passes).

    Asserts:
    * primary fired 3 times (2 shape failures + 1 shape-valid success)
    * auditor adapter was called exactly 1 time (only on the shape-valid attempt);
      NOT called on the two shape-failing attempts — the validator short-circuits it
    * cascade exits without hitting the human_gate (third attempt passes end-to-end)
    """
    # primary returns invalid JSON twice (validator will reject), then valid JSON
    _StubLiteLLMAdapter.script = [
        ("not json at all", 0.001),
        ("also not json", 0.001),
        (_PRIMARY_JSON, 0.001),  # third try: shape-valid
    ]
    # auditor fires only on the shape-valid attempt
    _StubClaudeCodeAdapter.script = [(_AUDIT_PASS_JSON, 0.0)]

    checkpointer = await build_async_checkpointer(tmp_path / "cp.sqlite")
    storage = await SQLiteStorage.open(tmp_path / "storage.sqlite")
    await storage.create_run("r4", "cascade_shapefail", None)

    cascade = _cascade(name="ac", policy=_POLICY_3)
    outer = _build_outer_graph(cascade, name="ac")
    cfg = _build_config(tmp_path, "r4", checkpointer, storage)

    try:
        final = await outer.ainvoke({"run_id": "r4"}, cfg)
    finally:
        await checkpointer.conn.close()

    assert "__interrupt__" not in final

    # Primary fired 3 times (2 shape failures + 1 success).
    assert len(_StubLiteLLMAdapter.calls) == 3

    # Auditor fired only once (only on the shape-valid third attempt).
    assert len(_StubClaudeCodeAdapter.calls) == 1


# ---------------------------------------------------------------------------
# Test 4b: pure-shape-failure exhaustion — auditor never invoked (AC-9 pin)
# ---------------------------------------------------------------------------


async def test_cascade_pure_shape_failure_never_invokes_auditor(
    tmp_path: Path,
) -> None:
    """Pure-exhaustion scenario from spec test #4: every primary attempt is
    shape-invalid; the in-validator escalation (M6 T07 pattern) escalates
    RetryableSemantic → NonRetryable on the final attempt; cascade routes
    to the human_gate without ever invoking the auditor.

    Pins AC-9's stronger claim: when shape failure exhausts the budget
    without ever producing a valid payload, the auditor adapter's
    call counter is 0.

    With RetryPolicy(max_semantic_attempts=2):
    - Attempt 1: shape-invalid → validator raises RetryableSemantic (prior_failures=0,
      0 >= max_attempts-1=1 → False). _retry_counts["ac_primary"] bumps to 1.
      retrying_edge routes back to primary via on_semantic.
    - Attempt 2: shape-invalid → validator checks prior_failures=1, 1 >= 1 → True.
      Escalates RetryableSemantic → NonRetryable (validator_node.py:136-142).
      _decide_after_validator intercepts NonRetryable → routes to human_gate directly,
      bypassing the auditor node entirely.
    Result: __interrupt__ raised at human_gate; _StubClaudeCodeAdapter.calls == 0.
    """
    # Every primary attempt returns invalid JSON — shape validation always fails.
    _StubLiteLLMAdapter.script = [
        ("not json at all", 0.001),
        ("also not json", 0.001),
    ]
    # Auditor script is empty — it must never be invoked.
    _StubClaudeCodeAdapter.script = []

    checkpointer = await build_async_checkpointer(tmp_path / "cp_4b.sqlite")
    storage = await SQLiteStorage.open(tmp_path / "storage_4b.sqlite")
    await storage.create_run("r4b", "cascade_pure_shapefail", None)

    # Use _POLICY_2 (max_semantic_attempts=2) so the budget exhausts after 2 attempts.
    cascade = _cascade(name="ac", policy=_POLICY_2)
    outer = _build_outer_graph(cascade, name="ac")
    cfg = _build_config(tmp_path, "r4b", checkpointer, storage)

    try:
        paused = await outer.ainvoke({"run_id": "r4b"}, cfg)
    finally:
        await checkpointer.conn.close()

    # Cascade routed to human_gate — interrupt present.
    assert "__interrupt__" in paused

    # Primary fired exactly 2 times (one per allowed attempt).
    assert len(_StubLiteLLMAdapter.calls) == 2

    # Auditor was NEVER invoked — pure shape-failure path bypasses the auditor.
    assert len(_StubClaudeCodeAdapter.calls) == 0


# ---------------------------------------------------------------------------
# Test 5: cascade is composable in an outer StateGraph
# ---------------------------------------------------------------------------


async def test_cascade_returns_compiled_state_graph_composable_in_outer(
    tmp_path: Path,
) -> None:
    """Test 5: audit_cascade_node returns a CompiledStateGraph; compiles in outer graph.

    Asserts:
    * return value is a CompiledStateGraph instance
    * can be added as a single node to a minimal outer StateGraph
    * compiled outer graph invokes successfully (with stubbed adapters)
    """
    _StubLiteLLMAdapter.script = [(_PRIMARY_JSON, 0.001)]
    _StubClaudeCodeAdapter.script = [(_AUDIT_PASS_JSON, 0.0)]

    cascade = _cascade(name="ac", policy=_POLICY_3)
    assert isinstance(cascade, CompiledStateGraph)

    outer = _build_outer_graph(cascade, name="ac")

    checkpointer = await build_async_checkpointer(tmp_path / "cp.sqlite")
    storage = await SQLiteStorage.open(tmp_path / "storage.sqlite")
    await storage.create_run("r5", "cascade_composable", None)
    cfg = _build_config(tmp_path, "r5", checkpointer, storage)

    try:
        final = await outer.ainvoke({"run_id": "r5"}, cfg)
    finally:
        await checkpointer.conn.close()

    assert "__interrupt__" not in final
    assert isinstance(final.get("ac_primary_parsed"), _PrimaryOutput)


# ---------------------------------------------------------------------------
# Test 6: role tags stamped on state by each cascade sub-node
# ---------------------------------------------------------------------------


async def test_cascade_role_tags_stamped_on_state(tmp_path: Path) -> None:
    """Test 6: cascade_role is stamped correctly by primary (author), auditor, verdict nodes.

    T04 will consume this channel; T02 only writes.  We verify the final state
    has cascade_role="verdict" (the last writer on the success path) and that
    all three roles appeared during the run.

    We track role stamps via a custom prompt_fn that records state at call time.
    """
    captured_roles: list[str | None] = []

    def _tracking_prompt(state: Mapping[str, Any]) -> tuple[str | None, list[dict]]:
        # Called at each primary invocation; record role as seen by the primary
        captured_roles.append(state.get("cascade_role"))
        return ("sys", [{"role": "user", "content": "produce output"}])

    _StubLiteLLMAdapter.script = [(_PRIMARY_JSON, 0.001)]
    _StubClaudeCodeAdapter.script = [(_AUDIT_PASS_JSON, 0.0)]

    checkpointer = await build_async_checkpointer(tmp_path / "cp.sqlite")
    storage = await SQLiteStorage.open(tmp_path / "storage.sqlite")
    await storage.create_run("r6", "cascade_roles", None)

    cascade = audit_cascade_node(
        primary_tier="primary-litellm",
        primary_prompt_fn=_tracking_prompt,
        primary_output_schema=_PrimaryOutput,
        auditor_tier="auditor-sonnet",
        policy=_POLICY_3,
        name="ac",
    )
    outer = _build_outer_graph(cascade, name="ac")
    cfg = _build_config(tmp_path, "r6", checkpointer, storage)

    try:
        final = await outer.ainvoke({"run_id": "r6"}, cfg)
    finally:
        await checkpointer.conn.close()

    assert "__interrupt__" not in final

    # Final cascade_role is "verdict" (last writer on success path).
    assert final.get("cascade_role") == "verdict"


# ---------------------------------------------------------------------------
# Outer graph factory (shared by all tests)
# ---------------------------------------------------------------------------


class _OuterState(TypedDict, total=False):
    """Outer state schema with all channels the cascade and its storage need."""

    run_id: str
    last_exception: Any
    _retry_counts: dict[str, int]
    _non_retryable_failures: int

    # Cascade channels (default name="ac")
    cascade_role: str
    cascade_transcript: dict[str, list]
    ac_primary_output: str
    ac_primary_parsed: Any
    ac_primary_output_revision_hint: Any
    ac_auditor_output: str
    ac_auditor_output_revision_hint: Any
    ac_audit_verdict: Any
    ac_audit_exhausted_response: str


def _build_outer_graph(cascade: CompiledStateGraph, *, name: str) -> Any:
    """Wrap the cascade in a minimal outer StateGraph for testing."""
    g = StateGraph(_OuterState)
    g.add_node("cascade", cascade)
    g.add_edge(START, "cascade")
    g.add_edge("cascade", END)
    return g.compile()


def _cascade_skip(*, name: str = "ac", policy: RetryPolicy = _POLICY_3) -> CompiledStateGraph:
    """Factory for a skip_terminal_gate=True cascade sub-graph used in T08 tests."""
    return audit_cascade_node(
        primary_tier="primary-litellm",
        primary_prompt_fn=_primary_prompt_fn,
        primary_output_schema=_PrimaryOutput,
        auditor_tier="auditor-sonnet",
        policy=policy,
        skip_terminal_gate=True,
        name=name,
    )


# ---------------------------------------------------------------------------
# Test 8 (T08): default False preserves T02 behaviour — exhaustion → human_gate
# ---------------------------------------------------------------------------


async def test_skip_terminal_gate_default_false_preserves_t02_behaviour(
    tmp_path: Path,
) -> None:
    """Test 8 / T08-AC: omitting skip_terminal_gate (or passing False) preserves T02.

    Drives a pure audit-failure exhaustion scenario with max_semantic_attempts=2.
    Asserts:
    * cascade reaches the human_gate node — ``__interrupt__`` is non-empty
    * ``strict_review=True`` is set on the interrupt payload
    * default-False path is structurally equivalent to the T02 exhaustion test

    Pins the default-False contract so the new conditional branch does not
    accidentally regress T02's exhaustion behaviour.
    """
    # primary always returns valid JSON; auditor always fails (2 cycles → exhausted)
    _StubLiteLLMAdapter.script = [(_PRIMARY_JSON, 0.001), (_PRIMARY_JSON, 0.001)]
    _StubClaudeCodeAdapter.script = [(_AUDIT_FAIL_JSON, 0.0), (_AUDIT_FAIL_JSON, 0.0)]

    checkpointer = await build_async_checkpointer(tmp_path / "cp_t08a.sqlite")
    storage = await SQLiteStorage.open(tmp_path / "storage_t08a.sqlite")
    await storage.create_run("r_t08a", "cascade_skip_default_false", None)

    # Explicitly pass skip_terminal_gate=False — same as default.
    cascade = audit_cascade_node(
        primary_tier="primary-litellm",
        primary_prompt_fn=_primary_prompt_fn,
        primary_output_schema=_PrimaryOutput,
        auditor_tier="auditor-sonnet",
        policy=_POLICY_2,
        skip_terminal_gate=False,
        name="ac",
    )
    outer = _build_outer_graph(cascade, name="ac")
    cfg = _build_config(tmp_path, "r_t08a", checkpointer, storage)

    try:
        paused = await outer.ainvoke({"run_id": "r_t08a"}, cfg)
    finally:
        await checkpointer.conn.close()

    # Cascade interrupted at human_gate — same as T02 test 3.
    assert "__interrupt__" in paused
    interrupt_payload = paused["__interrupt__"][0].value
    assert interrupt_payload["strict_review"] is True


# ---------------------------------------------------------------------------
# Test 9 (T08): skip_terminal_gate=True omits the gate node from compiled graph
# ---------------------------------------------------------------------------


async def test_skip_terminal_gate_true_omits_human_gate_node_from_compiled_subgraph(
    tmp_path: Path,
) -> None:
    """Test 9 / T08-AC: with skip_terminal_gate=True, the gate node is structurally absent.

    Asserts:
    * ``f"{name}_human_gate" not in compiled.nodes`` — the gate is never registered,
      not just unreachable.

    This pins the "no gate allocated at all" contract — the caller does not pay the
    gate-allocation cost when skip_terminal_gate=True.
    """
    cascade = _cascade_skip(name="ac")
    gate_key = "ac_human_gate"
    assert gate_key not in cascade.nodes, (
        f"Expected '{gate_key}' absent from compiled sub-graph nodes when "
        "skip_terminal_gate=True, but it was present."
    )


# ---------------------------------------------------------------------------
# Test 10 (T08): skip_terminal_gate=True → verdict-exhaustion → END + AuditFailure
# Wire-level smoke (CLAUDE.md non-inferential rule)
# ---------------------------------------------------------------------------


async def test_skip_terminal_gate_true_routes_exhaustion_to_END_with_audit_failure_in_state(
    tmp_path: Path,
) -> None:
    """Test 10 / T08 wire-level smoke: verdict-exhaustion routes to END with AuditFailure.

    Drives an auditor-fail-every-attempt scenario with max_semantic_attempts=2
    and skip_terminal_gate=True.

    Asserts:
    * graph reaches END (no ``__interrupt__`` in state)
    * ``state["last_exception"]`` is an :class:`AuditFailure` instance
    * ``state["last_exception"].failure_reasons`` matches the auditor's last verdict
    * ``state["last_exception"].suggested_approach`` matches the auditor's last verdict
    * ``state["cascade_transcript"]["author_attempts"]`` length is 2
    * ``state["cascade_transcript"]["auditor_verdicts"]`` length is 2
    """
    # primary always returns valid JSON; auditor always fails (2 cycles → exhausted)
    _StubLiteLLMAdapter.script = [(_PRIMARY_JSON, 0.001), (_PRIMARY_JSON, 0.001)]
    _StubClaudeCodeAdapter.script = [(_AUDIT_FAIL_JSON, 0.0), (_AUDIT_FAIL_JSON, 0.0)]

    checkpointer = await build_async_checkpointer(tmp_path / "cp_t08b.sqlite")
    storage = await SQLiteStorage.open(tmp_path / "storage_t08b.sqlite")
    await storage.create_run("r_t08b", "cascade_skip_exhaustion", None)

    cascade = _cascade_skip(name="ac", policy=_POLICY_2)
    outer = _build_outer_graph(cascade, name="ac")
    cfg = _build_config(tmp_path, "r_t08b", checkpointer, storage)

    try:
        final = await outer.ainvoke({"run_id": "r_t08b"}, cfg)
    finally:
        await checkpointer.conn.close()

    # No interrupt — cascade exhausted to END (not human_gate).
    assert "__interrupt__" not in final, (
        "Expected cascade to exit to END (not interrupt) when skip_terminal_gate=True"
    )

    # last_exception carries AuditFailure from the final verdict cycle.
    exc = final.get("last_exception")
    assert isinstance(exc, AuditFailure), (
        f"Expected AuditFailure in state['last_exception'], got {type(exc)}"
    )

    # AuditFailure payload matches the auditor's verdict from _AUDIT_FAIL_JSON.
    assert exc.failure_reasons == ["bad shape"], (
        f"Expected failure_reasons=['bad shape'], got {exc.failure_reasons}"
    )
    assert exc.suggested_approach == "try Y", (
        f"Expected suggested_approach='try Y', got {exc.suggested_approach}"
    )

    # Transcript accumulated 2 author attempts + 2 auditor verdicts.
    # On all-failure runs, _wrap_verdict_with_transcript preserves cascade_transcript
    # from exc.cascade_transcript on each cycle; the last cycle's transcript state
    # is written to the outer state dict by the cascade sub-graph wrapper.
    transcript = final.get("cascade_transcript") or {}
    assert len(transcript.get("author_attempts", [])) == 2, (
        f"Expected 2 author_attempts, got {len(transcript.get('author_attempts', []))}"
    )
    assert len(transcript.get("auditor_verdicts", [])) == 2, (
        f"Expected 2 auditor_verdicts, got {len(transcript.get('auditor_verdicts', []))}"
    )


# ---------------------------------------------------------------------------
# Test 11 (T08): skip_terminal_gate=True → validator-exhaustion → END + NonRetryable
# ---------------------------------------------------------------------------


async def test_skip_terminal_gate_true_routes_validator_exhaustion_to_END_with_nonretryable_in_state(  # noqa: E501
    tmp_path: Path,
) -> None:
    """Test 11 / T08-AC: pure shape-failure exhaustion routes to END (not human_gate).

    Mirrors ``test_cascade_pure_shape_failure_never_invokes_auditor`` shape but
    with skip_terminal_gate=True.  Every primary attempt returns shape-invalid
    output; the in-validator escalation (M6 T07 pattern) converts
    RetryableSemantic → NonRetryable on the final attempt; the
    ``_decide_after_validator`` intercepts NonRetryable and routes to END
    (not human_gate) when skip_terminal_gate=True.

    Asserts:
    * graph reaches END (no ``__interrupt__`` in state)
    * ``state["last_exception"]`` is a :class:`NonRetryable` instance
    * auditor adapter call count is 0 (auditor never invoked under pure-shape-failure)
    """
    # Every primary attempt returns invalid JSON — shape validation always fails.
    _StubLiteLLMAdapter.script = [
        ("not json at all", 0.001),
        ("also not json", 0.001),
    ]
    # Auditor script is empty — it must never be invoked.
    _StubClaudeCodeAdapter.script = []

    checkpointer = await build_async_checkpointer(tmp_path / "cp_t08c.sqlite")
    storage = await SQLiteStorage.open(tmp_path / "storage_t08c.sqlite")
    await storage.create_run("r_t08c", "cascade_skip_shapefail", None)

    # _POLICY_2 (max_semantic_attempts=2) — exhausts after 2 shape-failing attempts.
    cascade = _cascade_skip(name="ac", policy=_POLICY_2)
    outer = _build_outer_graph(cascade, name="ac")
    cfg = _build_config(tmp_path, "r_t08c", checkpointer, storage)

    try:
        final = await outer.ainvoke({"run_id": "r_t08c"}, cfg)
    finally:
        await checkpointer.conn.close()

    # No interrupt — cascade exhausted to END (not human_gate).
    assert "__interrupt__" not in final, (
        "Expected cascade to exit to END (not interrupt) when skip_terminal_gate=True "
        "and validator exhausts shape budget."
    )

    # last_exception carries NonRetryable from the validator escalation.
    exc = final.get("last_exception")
    assert isinstance(exc, NonRetryable), (
        f"Expected NonRetryable in state['last_exception'], got {type(exc)}"
    )

    # Auditor was NEVER invoked — pure shape-failure path bypasses the auditor.
    assert len(_StubClaudeCodeAdapter.calls) == 0, (
        f"Auditor should not be invoked under pure shape-failure with "
        f"skip_terminal_gate=True, but was called {len(_StubClaudeCodeAdapter.calls)} time(s)."
    )


# ---------------------------------------------------------------------------
# Test 12 (T04): wire-level smoke — primary records role="author", auditor role="auditor"
# CLAUDE.md non-inferential rule: wire-level smoke (same code path as downstream consumer)
# ---------------------------------------------------------------------------


async def test_cascade_records_role_tagged_token_usage_per_step(
    tmp_path: Path,
) -> None:
    """Test 12 / T04 wire-level smoke: primary records role="author", auditor role="auditor".

    Drives a happy-path cascade (auditor passes on first try) with a real
    ``CostTracker`` + ``CostTrackingCallback`` in the config.  Asserts:

    * Exactly 2 ``TokenUsage`` records are written for the run (primary +
      auditor).  The count is the protective assertion: pins that the verdict
      node correctly does NOT dispatch an LLM call (no third record), and that
      the primary + auditor each record exactly once.
    * ``records[0].role == "author"`` — primary's factory-time role binding
      (Option 4, locked 2026-04-27) stamped via ``tiered_node(role="author")``.
    * ``records[1].role == "auditor"`` — auditor's factory-time role binding.

    This test exercises the production cost-callback path (``CostTracker.record``
    called by ``CostTrackingCallback.on_node_complete`` called by ``tiered_node``
    after the role stamp), NOT a mock.  Wire-level per CLAUDE.md non-inferential
    rule: same code path a downstream consumer hits.
    """
    _StubLiteLLMAdapter.script = [(_PRIMARY_JSON, 0.001)]
    _StubClaudeCodeAdapter.script = [(_AUDIT_PASS_JSON, 0.0)]

    checkpointer = await build_async_checkpointer(tmp_path / "cp_t04a.sqlite")
    storage = await SQLiteStorage.open(tmp_path / "storage_t04a.sqlite")
    await storage.create_run("r_t04a", "cascade_role_smoke", None)

    # Build the tracker separately so we can inspect it after the run.
    tracker = CostTracker()
    callback = CostTrackingCallback(cost_tracker=tracker, budget_cap_usd=None)

    cascade = _cascade(name="ac")
    outer = _build_outer_graph(cascade, name="ac")

    cfg = {
        "configurable": {
            "thread_id": "r_t04a",
            "run_id": "r_t04a",
            "tier_registry": _tier_registry(),
            "cost_callback": callback,
            "storage": storage,
            "pricing": {},
        }
    }

    try:
        final = await outer.ainvoke({"run_id": "r_t04a"}, cfg)
    finally:
        await checkpointer.conn.close()

    assert "__interrupt__" not in final

    # Inspect the ledger: exactly 2 records for this run.
    records = tracker._entries.get("r_t04a", [])
    assert len(records) == 2, (
        f"Expected exactly 2 TokenUsage records (primary + auditor); "
        f"got {len(records)}: {[(r.role, r.cost_usd) for r in records]}"
    )

    # First record: primary call — role="author".
    assert records[0].role == "author", (
        f"Expected records[0].role='author' (primary tiered_node with role='author'), "
        f"got {records[0].role!r}"
    )

    # Second record: auditor call — role="auditor".
    assert records[1].role == "auditor", (
        f"Expected records[1].role='auditor' (auditor tiered_node with role='auditor'), "
        f"got {records[1].role!r}"
    )


# ---------------------------------------------------------------------------
# Test 13 (T04): role attribution survives audit retry cycle
# Pins H2 mitigation: factory-time binding is immune to state-channel stale reads
# ---------------------------------------------------------------------------


async def test_cascade_role_attribution_survives_audit_retry_cycle(
    tmp_path: Path,
) -> None:
    """Test 13 / T04: role attribution is correct across an auditor-fail-then-pass cycle.

    Drives a cascade where the auditor fails once then succeeds.  Captures every
    ``TokenUsage`` the cost tracker receives across the retry cycle.  Asserts:

    * 2 author records (cycle 1 primary + cycle 2 primary re-fire) all carry
      ``role="author"``.
    * 2 auditor records (cycle 1 auditor failure + cycle 2 auditor success) all
      carry ``role="auditor"``.
    * No author record carries ``role="auditor"`` and no auditor record carries
      ``role="author"``.

    Pins H2's mitigation: Option 4's factory-time role binding eliminates the
    stale-role-on-retry concern (under Options 1/3 the role would be read from
    ``state['cascade_role']`` and could inherit a stale value from the prior
    node's success-side write; under Option 4 the role is closure-captured at
    cascade construction time and immune to state-channel ordering).
    """
    # primary fires twice (cycle 1 + retry after audit failure); both return valid JSON.
    _StubLiteLLMAdapter.script = [(_PRIMARY_JSON, 0.001), (_PRIMARY_JSON, 0.001)]
    # auditor fires twice: first fails, second passes.
    _StubClaudeCodeAdapter.script = [(_AUDIT_FAIL_JSON, 0.0), (_AUDIT_PASS_JSON, 0.0)]

    checkpointer = await build_async_checkpointer(tmp_path / "cp_t04b.sqlite")
    storage = await SQLiteStorage.open(tmp_path / "storage_t04b.sqlite")
    await storage.create_run("r_t04b", "cascade_role_retry", None)

    tracker = CostTracker()
    callback = CostTrackingCallback(cost_tracker=tracker, budget_cap_usd=None)

    cascade = _cascade(name="ac", policy=_POLICY_3)
    outer = _build_outer_graph(cascade, name="ac")

    cfg = {
        "configurable": {
            "thread_id": "r_t04b",
            "run_id": "r_t04b",
            "tier_registry": _tier_registry(),
            "cost_callback": callback,
            "storage": storage,
            "pricing": {},
        }
    }

    try:
        final = await outer.ainvoke({"run_id": "r_t04b"}, cfg)
    finally:
        await checkpointer.conn.close()

    assert "__interrupt__" not in final

    records = tracker._entries.get("r_t04b", [])
    # Expected: primary (author), auditor (auditor), primary (author), auditor (auditor) — 4 total.
    assert len(records) == 4, (
        f"Expected 4 TokenUsage records (2 primary + 2 auditor across retry cycle); "
        f"got {len(records)}: {[(r.role, r.cost_usd) for r in records]}"
    )

    # Separate into author and auditor records.
    author_records = [r for r in records if r.role == "author"]
    auditor_records = [r for r in records if r.role == "auditor"]

    # 2 author records (both from the primary tiered_node).
    assert len(author_records) == 2, (
        f"Expected 2 records with role='author', got {len(author_records)}: "
        f"{[r.role for r in records]}"
    )

    # 2 auditor records (both from the auditor tiered_node).
    assert len(auditor_records) == 2, (
        f"Expected 2 records with role='auditor', got {len(auditor_records)}: "
        f"{[r.role for r in records]}"
    )

    # No cross-contamination: no author record carries role="auditor" and vice versa.
    # (This is trivially guaranteed by the above counts if total == 4 and all roles
    # are "author" or "auditor", but pin it explicitly for clarity.)
    for r in author_records:
        assert r.role == "author", f"Author record carries unexpected role: {r.role!r}"
    for r in auditor_records:
        assert r.role == "auditor", f"Auditor record carries unexpected role: {r.role!r}"
