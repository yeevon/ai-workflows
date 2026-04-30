"""Tests for the scaffold_workflow graph, validator, and write-safety (M17 Task 01).

Covers all ACs from
``design_docs/phases/milestone_17_scaffold_workflow/task_01_scaffold_workflow.md``.

All LLM calls are stubbed — no live provider fires.
"""

from __future__ import annotations

import json
import stat
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from langgraph.types import Command
from pydantic import ValidationError

from ai_workflows import workflows
from ai_workflows.graph import tiered_node as tiered_node_module
from ai_workflows.graph.checkpointer import build_async_checkpointer
from ai_workflows.graph.cost_callback import CostTrackingCallback
from ai_workflows.primitives.cost import CostTracker, TokenUsage
from ai_workflows.primitives.storage import SQLiteStorage
from ai_workflows.primitives.tiers import LiteLLMRoute, TierConfig
from ai_workflows.workflows._scaffold_validator import (
    ScaffoldOutputValidationError,
    validate_scaffold_output,
)
from ai_workflows.workflows._scaffold_write_safety import (
    TargetDirectoryNotWritableError,
    TargetExistsError,
    TargetInsideInstalledPackageError,
    TargetRelativePathError,
    atomic_write,
    validate_target_path,
)
from ai_workflows.workflows.scaffold_workflow import (
    ScaffoldedWorkflow,
    ScaffoldWorkflowInput,
    build_scaffold_workflow,
    scaffold_workflow_tier_registry,
)
from ai_workflows.workflows.scaffold_workflow_prompt import render_scaffold_prompt

# ---------------------------------------------------------------------------
# Stub LiteLLM adapter (same pattern as test_planner_graph.py)
# ---------------------------------------------------------------------------


class _StubLiteLLMAdapter:
    """Scripted stub adapter for the scaffold's scaffold-synth tier."""

    script: list[Any] = []
    call_count: int = 0

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
        if not _StubLiteLLMAdapter.script:
            raise AssertionError("stub script exhausted")
        head = _StubLiteLLMAdapter.script.pop(0)
        if isinstance(head, BaseException):
            raise head
        text, cost = head
        return text, TokenUsage(
            input_tokens=10,
            output_tokens=20,
            cost_usd=cost,
            model=self.route.model,
        )

    @classmethod
    def reset(cls) -> None:
        cls.script = []
        cls.call_count = 0


@pytest.fixture(autouse=True)
def _reset_stub(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    _StubLiteLLMAdapter.reset()
    monkeypatch.setattr(tiered_node_module, "LiteLLMAdapter", _StubLiteLLMAdapter)
    yield
    _StubLiteLLMAdapter.reset()


@pytest.fixture(autouse=True)
def _reensure_scaffold_registered() -> Iterator[None]:
    workflows._reset_for_tests()
    workflows.register("scaffold_workflow", build_scaffold_workflow)
    yield


@pytest.fixture(autouse=True)
def _redirect_default_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AIW_CHECKPOINT_DB", str(tmp_path / "cp.sqlite"))
    monkeypatch.setenv("AIW_STORAGE_DB", str(tmp_path / "storage.sqlite"))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _hermetic_tier_registry() -> dict[str, TierConfig]:
    return {
        "scaffold-synth": TierConfig(
            name="scaffold-synth",
            route=LiteLLMRoute(model="gemini/gemini-2.5-flash"),
            max_concurrency=1,
            per_call_timeout_s=90,
        ),
    }


async def _build_config(
    tmp_path: Path,
    run_id: str,
) -> tuple[dict[str, Any], CostTracker, SQLiteStorage]:
    storage = await SQLiteStorage.open(tmp_path / "storage.sqlite")
    await storage.create_run(run_id, "scaffold_workflow", None)
    tracker = CostTracker()
    callback = CostTrackingCallback(cost_tracker=tracker, budget_cap_usd=None)
    cfg = {
        "configurable": {
            "thread_id": run_id,
            "run_id": run_id,
            "tier_registry": _hermetic_tier_registry(),
            "cost_callback": callback,
            "storage": storage,
            "workflow": "scaffold_workflow",
        }
    }
    return cfg, tracker, storage


def _valid_scaffold_json(target_path: str) -> str:
    source = (
        "from ai_workflows.workflows import WorkflowSpec, LLMStep, register_workflow\n"
        "from pydantic import BaseModel\n\n"
        "class QuestionGenInput(BaseModel):\n"
        "    text: str\n\n"
        "class QuestionGenOutput(BaseModel):\n"
        "    questions: list[str]\n\n"
        "_SPEC = WorkflowSpec(\n"
        "    name='question_gen',\n"
        "    input_schema=QuestionGenInput,\n"
        "    output_schema=QuestionGenOutput,\n"
        "    tiers={},\n"
        "    steps=[],\n"
        ")\n"
        "register_workflow(_SPEC)\n"
    )
    return json.dumps(
        {
            "name": "question_gen",
            "spec_python": source,
            "description": "Generates exam questions from text.",
            "reasoning": "Simple LLM step wrapped in a WorkflowSpec.",
        }
    )


# ---------------------------------------------------------------------------
# Validator tests (AC-3)
# ---------------------------------------------------------------------------


def test_validator_accepts_well_formed_output() -> None:
    """AC-3: well-formed ScaffoldedWorkflow with register_workflow(_SPEC) passes."""
    source = (
        "from ai_workflows.workflows import register_workflow, WorkflowSpec\n"
        "from pydantic import BaseModel\n\n"
        "class MyInput(BaseModel):\n"
        "    text: str\n\n"
        "class MyOutput(BaseModel):\n"
        "    result: str\n\n"
        "_SPEC = WorkflowSpec(name='my_wf', input_schema=MyInput, "
        "output_schema=MyOutput, tiers={}, steps=[])\n"
        "register_workflow(_SPEC)\n"
    )
    output = ScaffoldedWorkflow(
        name="my_wf",
        spec_python=source,
        description="Test workflow",
        reasoning="For testing",
    )
    validate_scaffold_output(output)  # Must not raise


def test_validator_accepts_register_workflow_with_name_reference() -> None:
    """AC-3: register_workflow(MY_SPEC) where MY_SPEC is a Name reference passes."""
    source = (
        "from ai_workflows.workflows import register_workflow, WorkflowSpec\n"
        "from pydantic import BaseModel\n\n"
        "class MyInput(BaseModel):\n"
        "    text: str\n\n"
        "class MyOutput(BaseModel):\n"
        "    result: str\n\n"
        "MY_SPEC = WorkflowSpec(name='my_wf', input_schema=MyInput, "
        "output_schema=MyOutput, tiers={}, steps=[])\n"
        "register_workflow(MY_SPEC)\n"
    )
    output = ScaffoldedWorkflow(
        name="my_wf",
        spec_python=source,
        description="Test workflow",
        reasoning="For testing",
    )
    validate_scaffold_output(output)  # Must not raise


def test_validator_rejects_syntactically_invalid_python() -> None:
    """AC-3: spec_python with a syntax error raises ScaffoldOutputValidationError."""
    bad_source = (
        "x " * 40 + "def = broken\n"
    )
    output = ScaffoldedWorkflow(
        name="bad",
        spec_python=bad_source,
        description="Bad workflow",
        reasoning="This is broken",
    )
    with pytest.raises(ScaffoldOutputValidationError, match="not valid Python"):
        validate_scaffold_output(output)


def test_validator_rejects_missing_register_workflow_call() -> None:
    """AC-3: valid Python without register_workflow() call raises."""
    source = (
        "# No register_workflow call here\n"
        "from pydantic import BaseModel\n\n"
        "class MyInput(BaseModel):\n"
        "    text: str\n\n"
        "class MyOutput(BaseModel):\n"
        "    result: str\n\n"
        "x = 1  # placeholder, not register_workflow\n"
    )
    output = ScaffoldedWorkflow(
        name="missing",
        spec_python=source,
        description="Missing call",
        reasoning="No registration",
    )
    with pytest.raises(ScaffoldOutputValidationError, match="register_workflow"):
        validate_scaffold_output(output)


def test_validator_rejects_trivially_short_source() -> None:
    """AC-3: source shorter than 80 chars raises even if syntactically valid."""
    short = "register_workflow(x)\n"
    assert len(short) < 80
    output = ScaffoldedWorkflow(
        name="tiny",
        spec_python=short,
        description="Tiny",
        reasoning="Tiny",
    )
    with pytest.raises(ScaffoldOutputValidationError, match="too short"):
        validate_scaffold_output(output)


# ---------------------------------------------------------------------------
# Write-safety tests (AC-4)
# ---------------------------------------------------------------------------


def test_atomic_write_creates_file_and_returns_sha256(tmp_path: Path) -> None:
    """AC-4: atomic_write creates the file and returns the SHA256."""
    import hashlib

    target = tmp_path / "output.py"
    content = "register_workflow(SPEC)\n"
    sha = atomic_write(target, content)
    assert target.exists()
    assert target.read_text() == content
    expected = hashlib.sha256(content.encode("utf-8")).hexdigest()
    assert sha == expected


def test_atomic_write_overwrites_only_on_replace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC-4: when os.replace raises, atomic_write cleans up the temp file and
    leaves the original file intact.
    """
    import ai_workflows.workflows._scaffold_write_safety as _ws_mod

    target = tmp_path / "output.py"
    original = "original content\n"
    target.write_text(original)

    # Monkeypatch os.replace inside the write-safety module to simulate failure.
    def _fail_replace(src: str, dst: str) -> None:
        raise OSError("simulated os.replace failure")

    monkeypatch.setattr(_ws_mod.os, "replace", _fail_replace)

    new_content = "new content\n"
    with pytest.raises(OSError, match="simulated"):
        atomic_write(target, new_content)

    # Original file must still be intact.
    assert target.read_text() == original
    # No stray .tmp files should remain in the parent directory.
    leftover_tmps = list(tmp_path.glob("*.tmp"))
    assert leftover_tmps == [], f"leaked temp files: {leftover_tmps}"


def test_validate_target_rejects_inside_installed_package(tmp_path: Path) -> None:
    """AC-4: target inside the ai_workflows package raises TargetInsideInstalledPackageError."""
    import ai_workflows as _aiw_pkg

    pkg_dir = Path(_aiw_pkg.__file__).parent.resolve()
    target = pkg_dir / "workflows" / "injected.py"
    with pytest.raises(TargetInsideInstalledPackageError):
        validate_target_path(target, force=True)


def test_validate_target_rejects_nonexistent_parent_directory() -> None:
    """AC-4: target with nonexistent parent raises TargetDirectoryNotWritableError."""
    target = Path("/tmp/nonexistent-xyz-12345/file.py")
    with pytest.raises(TargetDirectoryNotWritableError, match="does not exist"):
        validate_target_path(target, force=True)


def test_validate_target_rejects_readonly_parent(tmp_path: Path) -> None:
    """AC-4: target in a readonly directory raises TargetDirectoryNotWritableError."""
    readonly_dir = tmp_path / "readonly"
    readonly_dir.mkdir()
    readonly_dir.chmod(stat.S_IRUSR | stat.S_IXUSR)  # r-x
    target = readonly_dir / "file.py"
    try:
        with pytest.raises(TargetDirectoryNotWritableError, match="not writable"):
            validate_target_path(target, force=True)
    finally:
        readonly_dir.chmod(stat.S_IRWXU)  # restore so tmp_path cleanup works


def test_validate_target_rejects_existing_file_when_not_forced(tmp_path: Path) -> None:
    """AC-4: existing file without force=True raises TargetExistsError."""
    target = tmp_path / "exists.py"
    target.write_text("existing content\n")
    with pytest.raises(TargetExistsError):
        validate_target_path(target, force=False)


def test_validate_target_accepts_existing_file_when_forced(tmp_path: Path) -> None:
    """AC-4: existing file with force=True returns the resolved path."""
    target = tmp_path / "exists.py"
    target.write_text("existing content\n")
    result = validate_target_path(target, force=True)
    assert result == target.resolve()


def test_validate_target_rejects_relative_path() -> None:
    """AC-4: relative path raises TargetRelativePathError."""
    with pytest.raises(TargetRelativePathError):
        validate_target_path(Path("./scaffolded.py"), force=False)


# ---------------------------------------------------------------------------
# Integration tests (stub adapter, full graph) (AC-5, AC-6, AC-10, AC-11)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scaffold_end_to_end_with_stub_adapter(tmp_path: Path) -> None:
    """AC-5, AC-6: happy path — stub LLM → validator passes → gate → write.

    The written file's spec_python round-trips through ast.parse() cleanly.
    SHA256 of written bytes matches the expected value.
    """
    import ast
    import hashlib

    target = tmp_path / "question_gen.py"
    run_id = "scaffold-e2e-01"

    _StubLiteLLMAdapter.script = [(_valid_scaffold_json(str(target)), 0.002)]

    checkpointer = await build_async_checkpointer(tmp_path / "cp.sqlite")
    app = build_scaffold_workflow().compile(checkpointer=checkpointer)

    cfg, tracker, storage = await _build_config(tmp_path, run_id)

    initial = {
        "run_id": run_id,
        "input": ScaffoldWorkflowInput(
            goal="Generate exam questions from a textbook chapter.",
            target_path=target,
        ),
    }

    # First invoke — runs until HumanGate interrupt.
    await app.ainvoke(initial, config=cfg, durability="sync")
    # Should be waiting at gate
    assert not target.exists(), "file must not be written before gate approval"

    # Resume with approval.
    await app.ainvoke(
        Command(resume="approved"), config=cfg, durability="sync"
    )

    assert target.exists(), "file should be written after gate approval"
    content = target.read_text(encoding="utf-8")

    # Must parse as valid Python.
    ast.parse(content)

    # SHA256 must match.
    expected_sha = hashlib.sha256(content.encode("utf-8")).hexdigest()
    state = await app.aget_state(cfg)
    write_outcome = state.values.get("write_outcome")
    assert write_outcome is not None
    assert write_outcome.sha256 == expected_sha


@pytest.mark.asyncio
async def test_scaffold_validator_retry_on_bad_output(tmp_path: Path) -> None:
    """AC-10: stub emits invalid spec_python on first attempt; valid on second.

    RetryingEdge drives the second attempt; file writes successfully.
    """
    target = tmp_path / "retry_wf.py"
    run_id = "scaffold-retry-01"

    # First output: missing register_workflow call — validator rejects.
    bad_source = "x " * 50 + "\ny = 1\n"  # > 80 chars, no register_workflow
    bad_json = json.dumps(
        {
            "name": "retry_wf",
            "spec_python": bad_source,
            "description": "Bad first attempt",
            "reasoning": "Missing call",
        }
    )
    # Second output: valid.
    good_json = _valid_scaffold_json(str(target))

    _StubLiteLLMAdapter.script = [
        (bad_json, 0.001),
        (good_json, 0.002),
    ]

    checkpointer = await build_async_checkpointer(tmp_path / "cp.sqlite")
    app = build_scaffold_workflow().compile(checkpointer=checkpointer)

    cfg, _, storage = await _build_config(tmp_path, run_id)

    initial = {
        "run_id": run_id,
        "input": ScaffoldWorkflowInput(
            goal="Generate exam questions.",
            target_path=target,
        ),
    }

    # Should reach gate after retry.
    await app.ainvoke(initial, config=cfg, durability="sync")
    assert _StubLiteLLMAdapter.call_count >= 2, "should have called LLM at least twice"

    # Resume with approval.
    await app.ainvoke(Command(resume="approved"), config=cfg, durability="sync")
    assert target.exists()


@pytest.mark.asyncio
async def test_scaffold_gate_rejection_aborts_without_write(tmp_path: Path) -> None:
    """AC-10: gate rejection terminates the run without writing the file."""
    target = tmp_path / "reject_wf.py"
    run_id = "scaffold-reject-01"

    _StubLiteLLMAdapter.script = [(_valid_scaffold_json(str(target)), 0.001)]

    checkpointer = await build_async_checkpointer(tmp_path / "cp.sqlite")
    app = build_scaffold_workflow().compile(checkpointer=checkpointer)

    cfg, _, storage = await _build_config(tmp_path, run_id)

    initial = {
        "run_id": run_id,
        "input": ScaffoldWorkflowInput(
            goal="Generate exam questions.",
            target_path=target,
        ),
    }

    await app.ainvoke(initial, config=cfg, durability="sync")
    assert not target.exists()

    # Resume with rejection.
    await app.ainvoke(Command(resume="rejected"), config=cfg, durability="sync")
    assert not target.exists(), "file must NOT be written on gate rejection"


@pytest.mark.asyncio
async def test_scaffold_write_failure_after_approve_surfaces_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC-10: atomic_write failure after gate approval surfaces an error.

    Uses a valid target path so the graph runs through the full build→gate path,
    then monkeypatches atomic_write to raise OSError at write time after approval.
    Verifies the error is surfaced (NonRetryable propagates out of _write_to_disk).
    """
    import ai_workflows.workflows.scaffold_workflow as _swmod

    target = tmp_path / "fail_write_wf.py"
    run_id = "scaffold-writefail-02"

    _StubLiteLLMAdapter.script = [(_valid_scaffold_json(str(target)), 0.001)]

    checkpointer = await build_async_checkpointer(tmp_path / "cp.sqlite")
    app = build_scaffold_workflow().compile(checkpointer=checkpointer)

    cfg, _, _storage = await _build_config(tmp_path, run_id)

    initial = {
        "run_id": run_id,
        "input": ScaffoldWorkflowInput(
            goal="Generate a workflow.",
            target_path=target,
        ),
    }

    # First invoke — runs to gate pause.
    await app.ainvoke(initial, config=cfg, durability="sync")
    assert not target.exists(), "file must not be written before gate approval"

    # Patch atomic_write inside scaffold_workflow module to raise on the resume.
    def _raise_oserror(t: Path, content: str) -> str:
        raise OSError("disk full simulation")

    monkeypatch.setattr(_swmod, "atomic_write", _raise_oserror)

    # Resume with approval — write node should surface the OSError as an error.
    with pytest.raises(BaseException):  # noqa: B017 — LangGraph wraps NonRetryable
        await app.ainvoke(
            Command(resume="approved"), config=cfg, durability="sync"
        )

    # File must NOT have been written.
    assert not target.exists(), "file must not exist after a write failure"


# ---------------------------------------------------------------------------
# Registration tests (AC-1)
# ---------------------------------------------------------------------------


def test_scaffold_workflow_registered() -> None:
    """AC-1: module-top register() fires; scaffold_workflow is in list_workflows()."""
    assert "scaffold_workflow" in workflows.list_workflows()
    assert workflows.get("scaffold_workflow") is build_scaffold_workflow


# ---------------------------------------------------------------------------
# Pydantic model tests (AC-2)
# ---------------------------------------------------------------------------


def test_scaffold_workflow_input_model_strict() -> None:
    """AC-2: extra fields are forbidden."""
    with pytest.raises(ValidationError):
        ScaffoldWorkflowInput(
            goal="test",
            target_path="/tmp/test.py",
            unknown_field="oops",  # type: ignore[call-arg]
        )


def test_scaffold_workflow_input_requires_absolute_path() -> None:
    """AC-2: relative target_path is rejected by the model validator."""
    with pytest.raises(ValidationError):
        ScaffoldWorkflowInput(goal="test", target_path=Path("./relative.py"))


def test_scaffolded_workflow_model_fields() -> None:
    """AC-2: ScaffoldedWorkflow has the four required fields."""
    sw = ScaffoldedWorkflow(
        name="test_wf",
        spec_python="register_workflow(SPEC)  # padding " + "x" * 60,
        description="A test workflow",
        reasoning="Testing field presence",
    )
    assert sw.name == "test_wf"
    assert "register_workflow" in sw.spec_python
    assert sw.description
    assert sw.reasoning


def test_scaffolded_workflow_no_tier_preferences_field() -> None:
    """AC-2: tier_preferences field was dropped; extra fields forbidden."""
    with pytest.raises(ValidationError):
        ScaffoldedWorkflow(
            name="x",
            spec_python="x" * 100,
            description="d",
            reasoning="r",
            tier_preferences=["something"],  # type: ignore[call-arg]
        )


# ---------------------------------------------------------------------------
# Tier registry tests (AC-9)
# ---------------------------------------------------------------------------


def test_scaffold_workflow_tier_registry_has_scaffold_synth() -> None:
    """AC-9: scaffold_workflow_tier_registry() exposes scaffold-synth tier."""
    registry = scaffold_workflow_tier_registry()
    assert "scaffold-synth" in registry
    tier = registry["scaffold-synth"]
    from ai_workflows.primitives.tiers import ClaudeCodeRoute

    assert isinstance(tier.route, ClaudeCodeRoute)
    assert tier.route.cli_model_flag == "opus"
    assert tier.max_concurrency == 1
    assert tier.per_call_timeout_s == 300


# ---------------------------------------------------------------------------
# KDR-003 compliance (AC-14)
# ---------------------------------------------------------------------------


def test_scaffold_workflow_no_anthropic_surface() -> None:
    """AC-14: no anthropic SDK import or ANTHROPIC_API_KEY in scaffold_workflow.py."""
    source = (
        Path(__file__).resolve().parent.parent.parent
        / "ai_workflows"
        / "workflows"
        / "scaffold_workflow.py"
    ).read_text(encoding="utf-8")
    for forbidden in ("import anthropic", "from anthropic", "ANTHROPIC_API_KEY"):
        assert forbidden not in source, (
            f"KDR-003 violated: {forbidden!r} found in scaffold_workflow.py"
        )


# ---------------------------------------------------------------------------
# KDR-004 compliance (AC-13)
# ---------------------------------------------------------------------------


def test_scaffold_graph_has_synthesize_and_validator_paired() -> None:
    """AC-13: LLM node (synthesize_source) is paired with scaffold_validator downstream."""
    g = build_scaffold_workflow()
    assert "synthesize_source" in g.nodes
    assert "scaffold_validator" in g.nodes
    assert "preview_gate" in g.nodes
    assert "write_to_disk" in g.nodes


# ---------------------------------------------------------------------------
# Prompt rendering tests (M17 T02 AC-4 / LOW-3 / M17-T01-ISS-03)
# ---------------------------------------------------------------------------


def test_render_scaffold_prompt_brace_escaping() -> None:
    """AC-4 / LOW-3: brace-containing inputs in goal, target_path, and
    existing_workflow_context pass through render_scaffold_prompt() literally.

    str.format() does not scan substituted values for format fields — values
    are opaque.  Pre-escaping user-supplied braces is wrong: it would produce
    {{x}} in the rendered output (LLM sees double braces instead of single).
    """
    result = render_scaffold_prompt(
        goal="generate {x}",
        target_path="/tmp/{name}.py",
        existing_workflow_context="def f(): return {'a': 1}",
    )
    assert "{x}" in result
    assert "{{x}}" not in result
    assert "{'a': 1}" in result
    assert "{{'a': 1}}" not in result
