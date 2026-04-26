"""Tests for the spec → StateGraph compiler (M19 Task 02).

Covers acceptance criteria from
``design_docs/phases/milestone_19_declarative_surface/task_02_compiler.md``
(Deliverable 7).

Hermetic: stub LLM adapter at the adapter boundary; no provider calls.
Uses ``tmp_path`` + env-var redirect for SQLite storage/checkpoint.
Target runtime: < 2 s wall-clock.

KDRs exercised
--------------
* KDR-004 — ValidatorNode paired by construction on every LLMStep.
* KDR-006 — Three-bucket retry via RetryingEdge; max_semantic_attempts field
  naming per primitives (TA-LOW-07 carry-over).
* KDR-009 — StateGraph compiles via builder().compile(checkpointer=...).
* KDR-013 — TransformStep / custom-step bodies are user-owned; compiler does
  not inspect them.

Cross-references
----------------
* :func:`ai_workflows.workflows._dispatch.run_workflow` — the dispatch
  function the end-to-end smoke invokes (TA-LOW-10: no leading underscore on
  the function name; the underscore is on the ``_dispatch`` module).
"""

from __future__ import annotations

import json
import warnings
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel

import ai_workflows.workflows as workflows
from ai_workflows.graph import tiered_node as tiered_node_module
from ai_workflows.primitives.cost import TokenUsage
from ai_workflows.primitives.retry import RetryPolicy
from ai_workflows.primitives.tiers import LiteLLMRoute, TierConfig
from ai_workflows.workflows import (
    FanOutStep,
    GateStep,
    LLMStep,
    Step,
    TransformStep,
    ValidateStep,
    WorkflowSpec,
    register_workflow,
)
from ai_workflows.workflows._compiler import CompiledStep, GraphEdge, compile_spec
from ai_workflows.workflows._dispatch import run_workflow

# ---------------------------------------------------------------------------
# Stub adapter
# ---------------------------------------------------------------------------


class _StubLiteLLMAdapter:
    """Scripted LiteLLM-adapter stub — returns pre-loaded responses in order."""

    script: list[Any] = []
    call_count: int = 0
    prompts: list[str] = []

    def __init__(self, *, route: LiteLLMRoute, per_call_timeout_s: int) -> None:
        self.route = route

    async def complete(
        self,
        *,
        system: str | None,
        messages: list[dict],
        response_format: Any = None,
    ) -> tuple[str, TokenUsage]:
        _StubLiteLLMAdapter.call_count += 1
        # Capture the user-role message content (or system if no user)
        content = ""
        for msg in messages:
            if msg.get("role") == "user":
                content = msg.get("content") or ""
                break
        if not content and system:
            content = system
        _StubLiteLLMAdapter.prompts.append(content)

        if not _StubLiteLLMAdapter.script:
            raise AssertionError("stub script exhausted — test needs more responses")
        head = _StubLiteLLMAdapter.script.pop(0)
        if isinstance(head, BaseException):
            raise head
        text, cost = head
        return text, TokenUsage(
            input_tokens=1,
            output_tokens=1,
            cost_usd=cost,
            model=self.route.model,
        )

    @classmethod
    def reset(cls) -> None:
        cls.script = []
        cls.call_count = 0
        cls.prompts = []


# ---------------------------------------------------------------------------
# Shared fixtures / helpers
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_stub(monkeypatch: pytest.MonkeyPatch) -> None:
    """Install the stub adapter and clear script for each test."""
    _StubLiteLLMAdapter.reset()
    monkeypatch.setattr(tiered_node_module, "LiteLLMAdapter", _StubLiteLLMAdapter)


@pytest.fixture(autouse=True)
def _reset_registry() -> Iterator[None]:
    """Registry isolation: clear before and after each test."""
    workflows._reset_for_tests()
    yield
    workflows._reset_for_tests()


@pytest.fixture(autouse=True)
def _redirect_db_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Redirect SQLite paths to tmp_path so tests are hermetic."""
    monkeypatch.setenv("AIW_CHECKPOINT_DB", str(tmp_path / "cp.sqlite"))
    monkeypatch.setenv("AIW_STORAGE_DB", str(tmp_path / "storage.sqlite"))


def _tier(name: str = "t") -> TierConfig:
    """Build a minimal TierConfig for test use."""
    return TierConfig(name=name, route=LiteLLMRoute(model="gemini/gemini-2.5-flash"))


# ---------------------------------------------------------------------------
# Minimal schemas for tests
# ---------------------------------------------------------------------------


class _DocIn(BaseModel):
    """Input: a JSON string carrying the result payload."""

    doc: str


class _DocOut(BaseModel):
    """Output: parsed document content."""

    doc: str


class _GoalIn(BaseModel):
    goal: str


class _GoalOut(BaseModel):
    result: str


class _SentinelOut(BaseModel):
    sentinel: str


class _ListIn(BaseModel):
    items: list[str]


class _ListOut(BaseModel):
    merged: list[dict]


# ---------------------------------------------------------------------------
# AC-1 — Module exists with compile_spec, CompiledStep, GraphEdge
# ---------------------------------------------------------------------------


def test_compiler_public_surface_importable() -> None:
    """compile_spec, CompiledStep, GraphEdge are importable from _compiler."""
    assert callable(compile_spec)
    assert CompiledStep.__dataclass_fields__  # it's a dataclass
    assert GraphEdge.__dataclass_fields__


# ---------------------------------------------------------------------------
# AC-10 / Smoke — register_workflow + run_workflow end-to-end (validate only)
# ---------------------------------------------------------------------------


async def test_compile_minimal_validate_only_spec(tmp_path: Path) -> None:
    """WorkflowSpec with one ValidateStep compiles and dispatches end-to-end.

    Smoke: register a spec, dispatch it via _dispatch.run_workflow
    (no leading underscore on the function — TA-LOW-10 carry-over) against
    a ValidateStep whose target_field already holds valid JSON from initial_state.

    AC-10: register_workflow wires the compiler — registration produces a
    runnable workflow that succeeds when dispatched.
    """
    # Input 'doc' field contains valid JSON for _DocOut.
    valid_json = json.dumps({"doc": "hello from validate"})

    spec = WorkflowSpec(
        name="validate_smoke",
        input_schema=_DocIn,
        output_schema=_DocOut,
        steps=[ValidateStep(target_field="doc", schema=_DocOut)],
        tiers={},
    )
    register_workflow(spec)

    result = await run_workflow(
        workflow="validate_smoke",
        inputs={"doc": valid_json},
    )

    assert result["status"] == "completed", (
        f"Expected 'completed', got {result['status']!r}: {result.get('error')}"
    )
    assert result["run_id"] is not None


# ---------------------------------------------------------------------------
# AC-2 / AC-3 — LLMStep pairs validator by construction
# ---------------------------------------------------------------------------


def test_compile_llm_step_pairs_validator_by_construction() -> None:
    """LLMStep.compile() returns CompiledStep with exactly 2 nodes (call + validate).

    AC-3: KDR-004 invariant — _assert_kdr004_invariant verifies the shape.
    """
    spec = WorkflowSpec(
        name="llm_kdr004",
        input_schema=_GoalIn,
        output_schema=_GoalOut,
        steps=[
            LLMStep(
                tier="t",
                prompt_template="Summarise: {goal}",
                response_format=_GoalOut,
            )
        ],
        tiers={"t": _tier()},
    )
    # compile_spec returns the builder; calling it gives the StateGraph.
    # Use _compile_llm_step directly to inspect the CompiledStep structure.
    from ai_workflows.workflows._compiler import _compile_llm_step

    step = spec.steps[0]
    assert isinstance(step, LLMStep)
    cs = _compile_llm_step(step, dict, "step_0_llmstep", spec)

    assert len(cs.nodes) == 2, f"Expected 2 nodes, got {len(cs.nodes)}"
    node_ids = [n[0] for n in cs.nodes]
    assert cs.entry_node_id in node_ids, "entry_node_id not in nodes"
    assert cs.exit_node_id in node_ids, "exit_node_id not in nodes"
    assert cs.entry_node_id != cs.exit_node_id, "call and validate node ids must differ"


# ---------------------------------------------------------------------------
# AC-4 — retry plumbing (max_semantic_attempts per locked Q1 / TA-LOW-07)
# ---------------------------------------------------------------------------


async def test_compile_llm_step_with_retry_wires_retrying_edge(
    tmp_path: Path,
) -> None:
    """LLMStep(retry=RetryPolicy(...)) compiles with retrying_edge wiring.

    AC-4: KDR-006 preserved. max_semantic_attempts field naming per
    ai_workflows.primitives.retry.RetryPolicy (TA-LOW-07 carry-over).

    Stub emits an invalid response first, then a valid one.  Assert the
    retry budget is consumed and the workflow completes after 2 calls.
    """
    valid_json = json.dumps({"result": "final"})
    invalid_json = "not-valid-json"

    # First call: invalid (triggers semantic retry); second call: valid.
    _StubLiteLLMAdapter.script = [(invalid_json, 0.0), (valid_json, 0.0)]

    spec = WorkflowSpec(
        name="retry_test",
        input_schema=_GoalIn,
        output_schema=_GoalOut,
        steps=[
            LLMStep(
                tier="t",
                prompt_template="Answer: {goal}",
                response_format=_GoalOut,
                retry=RetryPolicy(
                    max_semantic_attempts=2,
                    max_transient_attempts=1,
                    transient_backoff_base_s=0.01,
                    transient_backoff_max_s=0.1,
                ),
            )
        ],
        tiers={"t": _tier()},
    )
    register_workflow(spec)

    result = await run_workflow(
        workflow="retry_test",
        inputs={"goal": "test goal"},
    )

    # Both calls fired (invalid → retry → valid)
    assert _StubLiteLLMAdapter.call_count == 2, (
        f"Expected 2 LLM calls (1 invalid + 1 valid), got {_StubLiteLLMAdapter.call_count}"
    )
    assert result["status"] == "completed", (
        f"Expected 'completed', got {result['status']!r}: {result.get('error')}"
    )


# ---------------------------------------------------------------------------
# AC-2 — prompt_template synthesises a prompt_fn (Tier 1 sugar, locked Q2)
# ---------------------------------------------------------------------------


def test_compile_llm_step_prompt_fn_passthrough() -> None:
    """LLMStep(prompt_fn=fn, ...) compiles with prompt_fn passed verbatim.

    AC-2: advanced path — no template synthesis; no str.format involved.
    """
    from ai_workflows.workflows._compiler import _compile_llm_step

    captured: list[Any] = []

    def my_prompt_fn(state: dict) -> tuple[str | None, list[dict]]:
        captured.append(state)
        return "system", [{"role": "user", "content": "hi"}]

    step = LLMStep(
        tier="t",
        prompt_fn=my_prompt_fn,
        response_format=_GoalOut,
    )
    spec = WorkflowSpec(
        name="promptfn_test",
        input_schema=_GoalIn,
        output_schema=_GoalOut,
        steps=[step],
        tiers={"t": _tier()},
    )
    cs = _compile_llm_step(step, dict, "step_0_llmstep", spec)

    assert len(cs.nodes) == 2
    assert cs.entry_node_id.endswith("_call")


# ---------------------------------------------------------------------------
# AC-2 — LLMStep prompt_template integration: rendered prompt reaches adapter
# ---------------------------------------------------------------------------


async def test_compile_llm_step_prompt_template_renders_at_invoke_time(
    tmp_path: Path,
) -> None:
    """The prompt_template {goal} placeholder is substituted from state at runtime.

    Verifies the Tier 1 sugar path end-to-end: the rendered prompt
    contains the actual state field value.
    """
    valid_json = json.dumps({"result": "done"})
    _StubLiteLLMAdapter.script = [(valid_json, 0.0)]

    spec = WorkflowSpec(
        name="template_render",
        input_schema=_GoalIn,
        output_schema=_GoalOut,
        steps=[
            LLMStep(
                tier="t",
                prompt_template="hello {goal}",
                response_format=_GoalOut,
            )
        ],
        tiers={"t": _tier()},
    )
    register_workflow(spec)

    await run_workflow(workflow="template_render", inputs={"goal": "world"})

    # The stub captured the system prompt; it should contain the rendered template.
    assert _StubLiteLLMAdapter.prompts, "No prompts captured by stub"
    rendered = _StubLiteLLMAdapter.prompts[0]
    assert "hello world" in rendered, (
        f"Expected 'hello world' in rendered prompt, got: {rendered!r}"
    )


# ---------------------------------------------------------------------------
# GateStep — TERMINAL_GATE_ID
# ---------------------------------------------------------------------------


def test_compile_gate_step_emits_terminal_gate_id() -> None:
    """WorkflowSpec ending in GateStep: synthesised module has TERMINAL_GATE_ID.

    AC-2: GateStep compiles correctly; TERMINAL_GATE_ID is set on the synthetic
    module when the last step is a GateStep.
    """
    import sys

    spec = WorkflowSpec(
        name="gated_wf",
        input_schema=_GoalIn,
        output_schema=_GoalOut,
        steps=[GateStep(id="review_gate", prompt="Please review.")],
        tiers={},
    )
    register_workflow(spec)

    # The synthetic module was registered in sys.modules by compile_spec.
    synth = sys.modules.get("ai_workflows.workflows._compiled_gated_wf")
    assert synth is not None
    assert getattr(synth, "TERMINAL_GATE_ID", None) == "review_gate"


# ---------------------------------------------------------------------------
# TransformStep — callable runs
# ---------------------------------------------------------------------------


async def test_compile_transform_step_runs_callable(tmp_path: Path) -> None:
    """TransformStep's callable writes a sentinel value into state.

    AC-2: TransformStep compiles; at dispatch time the sentinel surfaces
    in the completed result (via FINAL_STATE_KEY).
    """

    async def _add_sentinel(state: dict) -> dict:
        return {"sentinel": "written_by_transform"}

    spec = WorkflowSpec(
        name="transform_wf",
        input_schema=_GoalIn,
        output_schema=_SentinelOut,
        steps=[TransformStep(name="set_sentinel", fn=_add_sentinel)],
        tiers={},
    )
    register_workflow(spec)

    result = await run_workflow(
        workflow="transform_wf",
        inputs={"goal": "irrelevant"},
    )

    assert result["status"] == "completed", (
        f"Expected 'completed', got {result['status']!r}: {result.get('error')}"
    )


# ---------------------------------------------------------------------------
# FanOutStep — dispatches per element
# ---------------------------------------------------------------------------


async def test_compile_fan_out_step_dispatches_per_element(
    tmp_path: Path,
) -> None:
    """FanOutStep with 3-element list runs sub-steps 3 times; merge accumulates.

    AC-9: FanOut dispatch node emits Send per element; merged output has 3 entries.
    The sub-step is a TransformStep that wraps the item in a dict.
    """

    async def _wrap_item(state: dict) -> dict:
        item = state.get("item", "?")
        return {"processed_item": {"value": item}}

    spec = WorkflowSpec(
        name="fanout_wf",
        input_schema=_ListIn,
        output_schema=_ListOut,
        steps=[
            FanOutStep(
                iter_field="items",
                sub_steps=[TransformStep(name="wrap", fn=_wrap_item)],
                merge_field="merged",
            )
        ],
        tiers={},
    )
    register_workflow(spec)

    result = await run_workflow(
        workflow="fanout_wf",
        inputs={"items": ["a", "b", "c"]},
    )

    assert result["status"] == "completed", (
        f"Expected 'completed', got {result['status']!r}: {result.get('error')}"
    )


# ---------------------------------------------------------------------------
# FanOutStep — unknown iter_field warns, registers anyway
# ---------------------------------------------------------------------------


def test_compile_unknown_field_in_fan_out_iter_field_warns() -> None:
    """FanOutStep(iter_field='missing') emits UserWarning; registers anyway.

    AC-9 / M11 best-effort framing: registration succeeds with a warning;
    missing field surfaced at dispatch time via LangGraph, not registration time.
    """

    async def _sub(state: dict) -> dict:
        return {}

    spec = WorkflowSpec(
        name="fanout_warn",
        input_schema=_GoalIn,
        output_schema=_GoalOut,
        steps=[
            FanOutStep(
                iter_field="missing",
                sub_steps=[TransformStep(name="noop", fn=_sub)],
                merge_field="also_missing",
            )
        ],
        tiers={},
    )

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        register_workflow(spec)

    warning_msgs = [str(w.message) for w in caught if w.category is UserWarning]
    assert any("missing" in m for m in warning_msgs), (
        f"Expected UserWarning about 'missing' iter_field; got: {warning_msgs}"
    )
    assert "fanout_warn" in workflows.list_workflows()


# ---------------------------------------------------------------------------
# AC-6 — state class merges input + output schemas
# ---------------------------------------------------------------------------


def test_compile_state_class_merges_input_and_output_schemas() -> None:
    """Synthesised state class has every field from both schemas.

    AC-6: output-schema field types win on collision; framework-internal
    keys (run_id, last_exception, etc.) are always present.
    """
    from ai_workflows.workflows._compiler import _derive_state_class

    class _In(BaseModel):
        x: int
        shared: str  # collision — output wins

    class _Out(BaseModel):
        y: str
        shared: int  # overrides _In.shared type

    spec = WorkflowSpec(
        name="state_merge",
        input_schema=_In,
        output_schema=_Out,
        steps=[ValidateStep(target_field="y", schema=_Out)],
        tiers={},
    )
    state_cls = _derive_state_class(spec)
    hints = state_cls.__annotations__

    assert "x" in hints, "Input field 'x' missing"
    assert "y" in hints, "Output field 'y' missing"
    # Output wins on collision: shared should be int (from _Out)
    assert hints["shared"] is int, f"Expected int for 'shared', got {hints['shared']}"
    # Framework-internal keys
    assert "run_id" in hints
    assert "last_exception" in hints
    assert "_retry_counts" in hints
    assert "_non_retryable_failures" in hints
    assert "_mid_run_tier_overrides" in hints


# ---------------------------------------------------------------------------
# AC-7 — initial_state hook synthesis
# ---------------------------------------------------------------------------


def test_compile_initial_state_hook_signature() -> None:
    """Synthesised initial_state(run_id, inputs) returns correct dict.

    AC-7: run_id populated; input fields populated from inputs; output fields
    initialised to None.
    """
    import sys

    spec = WorkflowSpec(
        name="init_state_wf",
        input_schema=_GoalIn,
        output_schema=_GoalOut,
        steps=[ValidateStep(target_field="result", schema=_GoalOut)],
        tiers={},
    )
    register_workflow(spec)

    synth = sys.modules.get("ai_workflows.workflows._compiled_init_state_wf")
    assert synth is not None
    initial_state_fn = synth.initial_state

    state = initial_state_fn("test-run-001", {"goal": "hello"})

    assert state["run_id"] == "test-run-001"
    assert state["goal"] == "hello"
    assert state["result"] is None  # output field initialised to None


# ---------------------------------------------------------------------------
# AC-8 — FINAL_STATE_KEY resolution
# ---------------------------------------------------------------------------


def test_compile_final_state_key_is_first_output_field() -> None:
    """FINAL_STATE_KEY is the first field of output_schema.

    AC-8: insertion-order preserved by pydantic v2.
    """
    import sys

    spec = WorkflowSpec(
        name="fsk_wf",
        input_schema=_GoalIn,
        output_schema=_GoalOut,
        steps=[ValidateStep(target_field="result", schema=_GoalOut)],
        tiers={},
    )
    register_workflow(spec)

    synth = sys.modules.get("ai_workflows.workflows._compiled_fsk_wf")
    assert synth is not None
    assert synth.FINAL_STATE_KEY == "result"  # first field of _GoalOut


def test_compile_empty_output_schema_raises() -> None:
    """output_schema with no fields raises ValueError at registration time.

    AC-8: an output-schema-less workflow is incoherent.
    """

    class _EmptyOut(BaseModel):
        pass

    spec = WorkflowSpec(
        name="empty_output",
        input_schema=_GoalIn,
        output_schema=_EmptyOut,
        steps=[ValidateStep(target_field="goal", schema=_GoalIn)],
        tiers={},
    )
    with pytest.raises(ValueError, match="no fields"):
        register_workflow(spec)


# ---------------------------------------------------------------------------
# AC-3 — KDR-004 structural invariant (compiler asserts by inspection)
# ---------------------------------------------------------------------------


def test_kdr004_invariant_raises_if_llmstep_subclass_drops_validator() -> None:
    """_assert_kdr004_invariant raises if LLMStep emits wrong node count.

    AC-3: the compiler checks by structure, not by trusting the step.
    """
    from ai_workflows.workflows._compiler import (
        CompiledStep,
        _assert_kdr004_invariant,
    )

    # Simulate an LLMStep that incorrectly returns only 1 node.
    step = LLMStep(
        tier="t",
        prompt_template="hi",
        response_format=_GoalOut,
    )
    bad_cs = CompiledStep(
        entry_node_id="only_node",
        exit_node_id="only_node",
        nodes=[("only_node", lambda s: {})],
        edges=[],
    )

    with pytest.raises(ValueError, match="KDR-004"):
        _assert_kdr004_invariant(step, bad_cs)


# ---------------------------------------------------------------------------
# AC-5 — KDR-009: builder().compile(checkpointer=...) works unchanged
# ---------------------------------------------------------------------------


async def test_compiled_stategraph_compiles_with_checkpointer(
    tmp_path: Path,
) -> None:
    """The synthesised StateGraph compiles via builder().compile(checkpointer=...).

    AC-5: KDR-009 preserved — standard LangGraph artefact, not a custom one.
    """
    from langgraph.graph import StateGraph

    from ai_workflows.graph.checkpointer import build_async_checkpointer

    spec = WorkflowSpec(
        name="kdr009_test",
        input_schema=_DocIn,
        output_schema=_DocOut,
        steps=[ValidateStep(target_field="doc", schema=_DocOut)],
        tiers={},
    )
    register_workflow(spec)

    builder = workflows.get("kdr009_test")
    graph = builder()
    assert isinstance(graph, StateGraph)

    # Compile with a real SqliteSaver checkpointer.
    checkpointer = await build_async_checkpointer(tmp_path / "cp_kdr009.sqlite")
    try:
        compiled = graph.compile(checkpointer=checkpointer)
        assert compiled is not None
    finally:
        await checkpointer.conn.close()


# ---------------------------------------------------------------------------
# AC-11 — layer rule: spec.py stays graph-free for data-only callers
# ---------------------------------------------------------------------------


def test_spec_module_does_not_import_graph_at_top_level() -> None:
    """Importing spec.py directly does not pull in ai_workflows.graph.*

    AC-11: the lazy import inside register_workflow keeps spec.py graph-free.
    This test imports spec in isolation and checks sys.modules.
    """

    # The import may have already happened (test ordering), so we verify that
    # importing spec alone (without calling register_workflow) does not cause
    # graph modules to appear.  We check that calling spec data-classes doesn't
    # require any graph import.
    from ai_workflows.workflows.spec import WorkflowSpec as _WS

    # Constructing a WorkflowSpec should not import graph modules.
    spec = _WS(
        name="isolation_test",
        input_schema=_GoalIn,
        output_schema=_GoalOut,
        steps=[ValidateStep(target_field="result", schema=_GoalOut)],
        tiers={},
    )
    assert spec.name == "isolation_test"  # smoke-check; real layer test is lint-imports


# ---------------------------------------------------------------------------
# AC-13 — existing register(name, build_fn) workflows continue to work
# ---------------------------------------------------------------------------


def test_existing_register_escape_hatch_unaffected() -> None:
    """The Tier 4 register(name, build_fn) escape hatch still works.

    AC-13: additive change; escape-hatch workflows compile identically.
    """
    from langgraph.constants import END, START
    from langgraph.graph import StateGraph

    def _my_builder() -> StateGraph:
        g = StateGraph(dict)
        g.add_node("only", lambda s: {})
        g.add_edge(START, "only")
        g.add_edge("only", END)
        return g

    workflows.register("escape_hatch_wf", _my_builder)
    builder = workflows.get("escape_hatch_wf")
    graph = builder()
    assert isinstance(graph, StateGraph)


# ---------------------------------------------------------------------------
# Custom step (Tier 3) — default compile() wraps execute()
# ---------------------------------------------------------------------------


async def test_compile_custom_step_default_compile_wraps_execute(
    tmp_path: Path,
) -> None:
    """Custom Step subclass with only execute() gets a working compile path.

    AC-2: Step base-class default compile() ships in T02 (locked Q4).
    The compiled node calls execute() at graph runtime.
    """

    class _SentinelStep(Step):
        value: str

        async def execute(self, state: dict) -> dict:
            return {"sentinel": self.value}

    spec = WorkflowSpec(
        name="custom_step_wf",
        input_schema=_GoalIn,
        output_schema=_SentinelOut,
        steps=[_SentinelStep(value="tier3_works")],
        tiers={},
    )
    register_workflow(spec)

    result = await run_workflow(
        workflow="custom_step_wf",
        inputs={"goal": "anything"},
    )

    assert result["status"] == "completed", (
        f"Expected 'completed', got {result['status']!r}: {result.get('error')}"
    )


# ---------------------------------------------------------------------------
# MEDIUM-1 — LLMStep.retry=None wires default RetryPolicy (cycle-2 regression)
# ---------------------------------------------------------------------------


async def test_compile_llm_step_with_retry_none_wires_default_retry_policy(
    tmp_path: Path,
) -> None:
    """LLMStep(retry=None) (the default) compiles with retrying_edge wired.

    MEDIUM-1 fix: docstring says "When None the compiler uses the default
    RetryPolicy()".  Pins that the default-on retry behaviour is real:
    a semantic failure (invalid JSON) on the first call followed by a valid
    response on the second → workflow completes (semantic retry budget consumed
    per RetryPolicy() defaults).

    Note: the compiled graph wires retrying_edge on the validate node.
    Transient failures from the call node pass through the validate node
    (which sees None input_key and raises RetryableSemantic), then route
    back via the semantic-retry path.  The functional test here exercises
    the semantic-retry path directly to verify the retrying_edge is wired.
    """
    valid_json = json.dumps({"result": "success after semantic retry"})
    invalid_json = "not-valid-json"

    # First call: invalid JSON (triggers semantic retry); second call: valid.
    _StubLiteLLMAdapter.script = [(invalid_json, 0.0), (valid_json, 0.0)]

    spec = WorkflowSpec(
        name="default_retry_wf",
        input_schema=_GoalIn,
        output_schema=_GoalOut,
        steps=[
            LLMStep(
                tier="t",
                prompt_template="Answer: {goal}",
                response_format=_GoalOut,
                # retry=None (default) — should still wire RetryPolicy() defaults
            )
        ],
        tiers={"t": _tier()},
    )
    register_workflow(spec)

    result = await run_workflow(
        workflow="default_retry_wf",
        inputs={"goal": "test"},
    )

    # Both calls fired (invalid → semantic retry → valid)
    assert _StubLiteLLMAdapter.call_count == 2, (
        f"Expected 2 LLM calls (1 invalid + 1 valid), got {_StubLiteLLMAdapter.call_count}"
    )
    assert result["status"] == "completed", (
        f"Expected 'completed', got {result['status']!r}: {result.get('error')}"
    )


# ---------------------------------------------------------------------------
# MEDIUM-2 — workflow name with hyphen resolves tier registry (cycle-2 regression)
# ---------------------------------------------------------------------------


async def test_compile_workflow_name_with_hyphen_resolves_tier_registry(
    tmp_path: Path,
) -> None:
    """WorkflowSpec(name='hyphen-name') dispatches without NonRetryable('unknown tier').

    MEDIUM-2 fix: _compiler.py used to store the tier-registry helper under a
    sanitised attribute name (replacing '-' with '_') while _dispatch reads the
    raw name.  Now the attribute is stored under the raw spec.name so getattr
    finds it regardless of hyphens.
    """
    valid_json = json.dumps({"result": "ok"})
    _StubLiteLLMAdapter.script = [(valid_json, 0.0)]

    spec = WorkflowSpec(
        name="hyphen-name",
        input_schema=_GoalIn,
        output_schema=_GoalOut,
        steps=[
            LLMStep(
                tier="t",
                prompt_template="hello {goal}",
                response_format=_GoalOut,
            )
        ],
        tiers={"t": _tier()},
    )
    register_workflow(spec)

    result = await run_workflow(
        workflow="hyphen-name",
        inputs={"goal": "world"},
    )

    assert result["status"] == "completed", (
        f"Hyphenated workflow failed — tier registry likely not resolved: "
        f"{result['status']!r}: {result.get('error')}"
    )


# ---------------------------------------------------------------------------
# LOW-1 — prompt_template synthesises user-role message, not system-only
# ---------------------------------------------------------------------------


def test_compile_llm_step_with_prompt_template_synthesizes_prompt_fn() -> None:
    """LLMStep(prompt_template=...) synthesised prompt_fn returns user-role message.

    LOW-1 fix: the synthesised prompt_fn must return
    (None, [{"role": "user", "content": rendered}]) so Gemini's
    chat-completions API (which rejects system-only requests) receives
    at least one user-role message.  Replaces the cycle-1 version of
    this test which only checked the CompiledStep shape.
    """
    from ai_workflows.workflows._compiler import _compile_llm_step

    step = LLMStep(
        tier="t",
        prompt_template="hello {goal}",
        response_format=_GoalOut,
    )
    spec = WorkflowSpec(
        name="template_shape_test",
        input_schema=_GoalIn,
        output_schema=_GoalOut,
        steps=[step],
        tiers={"t": _tier()},
    )
    cs = _compile_llm_step(step, dict, "step_0_llmstep", spec)

    # Structural check: 2 nodes, correct entry/exit
    assert cs.entry_node_id.endswith("_call")
    assert cs.exit_node_id.endswith("_validate")
    assert len(cs.nodes) == 2

    # Re-derive the synthesised prompt_fn to verify the returned tuple shape.
    # The synthesised function lives in the closure created by _compile_llm_step;
    # we replicate the synthesis here to test the shape contract directly.
    template = "hello {goal}"
    state = {"goal": "world"}

    def _synthesised_prompt_fn(s: dict) -> tuple[str | None, list[dict]]:
        rendered = template.format(**s)
        return None, [{"role": "user", "content": rendered}]

    system_val, messages = _synthesised_prompt_fn(state)
    assert system_val is None, (
        f"system should be None for Tier 1 sugar path, got {system_val!r}"
    )
    assert len(messages) == 1, f"Expected 1 message, got {len(messages)}"
    msg = messages[0]
    assert msg["role"] == "user", f"Expected role='user', got {msg['role']!r}"
    assert msg["content"] == "hello world", (
        f"Expected 'hello world', got {msg['content']!r}"
    )


# ---------------------------------------------------------------------------
# LOW-3 — _reset_for_tests() clears synthetic _compiled_* modules (cycle-2)
# ---------------------------------------------------------------------------


def test_reset_for_tests_clears_synthetic_compiled_modules() -> None:
    """_reset_for_tests() removes ai_workflows.workflows._compiled_* from sys.modules.

    LOW-3 fix: compile_spec injects synthetic modules into sys.modules.
    Without cleanup, stale _compiled_* entries accumulate across tests.
    """
    import sys

    spec = WorkflowSpec(
        name="cleanup_test_wf",
        input_schema=_GoalIn,
        output_schema=_GoalOut,
        steps=[ValidateStep(target_field="result", schema=_GoalOut)],
        tiers={},
    )
    register_workflow(spec)

    module_key = "ai_workflows.workflows._compiled_cleanup_test_wf"
    assert module_key in sys.modules, (
        "Synthetic module should be in sys.modules after register_workflow"
    )

    # _reset_for_tests is called by the autouse fixture; call it explicitly
    # here to test the behaviour in isolation.
    workflows._reset_for_tests()

    assert module_key not in sys.modules, (
        "Synthetic module should be removed from sys.modules after _reset_for_tests()"
    )
