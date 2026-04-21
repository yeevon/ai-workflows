# Task 03 — Replay Runner (Deterministic + Live Modes)

**Status:** 📝 Planned.
**Grounding:** [milestone README §Exit criteria 3](README.md) · [architecture.md §7](../../architecture.md) · [KDR-004](../../architecture.md) · [KDR-010 / ADR-0002](../../adr/0002_bare_typed_response_format_schemas.md).

## What to Build

`EvalRunner.run(suite) → EvalReport` — the engine that replays a loaded `EvalSuite` against the current graph and reports pass/fail per case. Supports two modes, selected at runner construction:

- **Deterministic** — default, always runs. Builds a workflow with a **stub tier registry** whose adapter returns each case's `expected_output` verbatim when the matching node fires. Verifies the graph's current prompt template + `ValidatorNode` schema + downstream wiring still accept the captured I/O.
- **Live** — gated by `AIW_EVAL_LIVE=1` at runner construction time (mirror the `AIW_E2E` pattern). Re-fires the captured inputs against the real provider and compares the fresh output against the pinned expected output using `EvalTolerance`.

A case that passes deterministic but fails live means **model-side drift** (provider output changed). A case that fails deterministic means **code-side drift** (prompt / schema / wiring changed). The split is the harness's diagnostic value.

## Deliverables

### [ai_workflows/evals/runner.py](../../../ai_workflows/evals/runner.py)

```python
@dataclass(frozen=True)
class EvalResult:
    case_id: str
    node_name: str
    mode: Literal["deterministic", "live"]
    passed: bool
    diff: str | None  # empty when passed
    duration_s: float
    error: str | None  # set when the run raised before comparison


@dataclass(frozen=True)
class EvalReport:
    suite_workflow_id: str
    mode: Literal["deterministic", "live"]
    results: tuple[EvalResult, ...]

    @property
    def pass_count(self) -> int: ...

    @property
    def fail_count(self) -> int: ...

    def summary_lines(self) -> list[str]: ...  # for CLI / CI output


class EvalRunner:
    def __init__(
        self,
        *,
        mode: Literal["deterministic", "live"],
        tolerance_override: EvalTolerance | None = None,
    ) -> None: ...

    async def run(self, suite: EvalSuite) -> EvalReport: ...
```

### Deterministic-mode adapter

[ai_workflows/evals/_stub_adapter.py](../../../ai_workflows/evals/_stub_adapter.py) — a minimal `LLMAdapter` (shape-matching the existing `LiteLLMAdapter` interface) that takes the loaded `EvalSuite` at construction and, on each `invoke`, looks up the expected output by `(node_name, case_id)` and returns it. If the runner fires a node for which no case exists in the suite, the stub raises loudly — the suite is incomplete and that's the eval's first catch.

### Per-case graph construction

Each case runs through a **single-node replay graph**, not the full workflow. The runner:

1. Resolves the case's `node_name` + `workflow_id` against the workflow registry.
2. Imports the workflow module (`ai_workflows.workflows.<workflow_id>`) and extracts the node's `TieredNode` builder (e.g., `_build_explorer_node`, `_build_planner_node`, `_build_slice_worker_subgraph`).
3. Wraps the node in a minimal `StateGraph` with `START → <node> → <node_validator> → END`.
4. Invokes with `case.inputs` as the initial state.
5. Parses the terminal state's node-output key against `case.output_schema_fqn` (import-string lookup).
6. Compares with `case.expected_output` via `_compare(...)` honouring `EvalTolerance`.

This sidesteps fan-out / human-gate / retry complexity: M7's unit of regression is the *LLM-node contract*, not the end-to-end workflow.

### Comparison semantics

[ai_workflows/evals/_compare.py](../../../ai_workflows/evals/_compare.py):

```python
def compare(
    expected: Any,
    actual: Any,
    tolerance: EvalTolerance,
    output_schema_fqn: str | None,
) -> tuple[bool, str]:
    """Return (passed, diff_string). Empty diff when passed."""
```

Rules:

- `tolerance.mode == "strict_json"` — parse both through the resolved `output_schema` (if present) and compare as pydantic-models' dicts (`model.model_dump()`). Diff via `difflib.unified_diff` on pretty-printed JSON.
- `tolerance.mode == "substring"` — for each string-typed field, assert `expected.lower() in actual.lower()`.
- `tolerance.mode == "regex"` — for each string-typed field, assert `re.search(expected, actual)`.
- `tolerance.field_overrides` — per-field mode override (e.g., `{"summary": "substring"}` keeps the rest strict-JSON).

### Tests

[tests/evals/test_runner_deterministic.py](../../../tests/evals/test_runner_deterministic.py):

- `test_deterministic_replay_passes_on_captured_output` — seed a `planner` `explorer` case, replay, expect `EvalResult.passed=True`.
- `test_deterministic_replay_fails_on_prompt_template_drift` — mutate the prompt template in-test (monkeypatch `_build_explorer_node`'s template string) so it raises on rendering; replay fails with non-empty `error`.
- `test_deterministic_replay_fails_on_schema_drift` — add a required field to `ExplorerReport` in-test (via a local subclass + registry swap); replay fails with a validation diff.
- `test_missing_case_for_fired_node_raises_loudly` — stub adapter asked for a `(node, case)` pair not in the suite → `EvalRunner.run` returns an `EvalResult` with `error="case not found in suite"`.

[tests/evals/test_runner_live.py](../../../tests/evals/test_runner_live.py):

- `@pytest.mark.e2e` gated — reuses the `AIW_E2E` mark pattern. Plus a runner-level `AIW_EVAL_LIVE=1` second-gate: the runner refuses to construct in `mode="live"` unless both env vars are set.
- `test_live_replay_passes_on_unchanged_provider_output` — hits `planner-explorer` tier against live Qwen, compares to pinned expected with `substring` tolerance on the summary field. Skips if `ollama` daemon unreachable.
- `test_live_runner_refuses_without_eval_live_env` — `EvalRunner(mode="live")` raises unless `AIW_EVAL_LIVE=1`.

[tests/evals/test_compare.py](../../../tests/evals/test_compare.py):

- One test per tolerance mode + one mixed-tolerance test exercising `field_overrides`.
- `test_strict_json_diff_shows_unified_diff_on_mismatch` — diff string is the kind a human can read on a CI log.

## Acceptance Criteria

- [ ] `EvalRunner(mode="deterministic").run(suite)` against a passing fixture returns `EvalReport(pass_count=N, fail_count=0)`.
- [ ] `EvalRunner(mode="deterministic").run(suite)` against a broken current-tree (prompt template mutated, schema field added) returns `fail_count >= 1` with a human-readable `diff` or `error`.
- [ ] `EvalRunner(mode="live")` construction is refused unless `AIW_EVAL_LIVE=1` is set; additionally refuses unless `AIW_E2E=1` because live mode fires real provider calls and shares that gating.
- [ ] `compare(...)` honours every `EvalTolerance.mode` and `field_overrides` axis.
- [ ] The stub adapter raises loudly when a case is missing — incomplete suites do not silently pass.
- [ ] KDR-004 discipline: replay runner invokes the node's paired `ValidatorNode` in the same graph position as production; no replay-only bypass.
- [ ] Import-linter 4/4 kept.
- [ ] `uv run pytest && uv run lint-imports && uv run ruff check` green.

## Dependencies

- [Task 01](task_01_dataset_schema.md) — `EvalCase`, `EvalSuite`, `EvalTolerance`, `load_suite`.
- [Task 02](task_02_capture_callback.md) — **not a hard dependency for T03 code**, but T03's tests need a few hand-crafted fixtures; T05 lands the capture-flow-generated ones.

## Out of scope (explicit)

- CLI surface (T04).
- CI wiring (T05).
- LLM-as-judge tolerance mode — see milestone README §Non-goals.
- Full-workflow trajectory replay (single-node is the M7 unit). Revisit post-M7 if the need is real.
