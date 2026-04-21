# Task 03 — Replay Runner (Deterministic + Live Modes) — Audit Issues

**Source task:** [../task_03_replay_runner.md](../task_03_replay_runner.md)
**Audited on:** 2026-04-21
**Audit scope:** `ai_workflows/evals/runner.py`, `ai_workflows/evals/_stub_adapter.py`, `ai_workflows/evals/_compare.py`, `ai_workflows/evals/__init__.py`, `pyproject.toml` importlinter block, `tests/evals/test_runner_deterministic.py`, `tests/evals/test_runner_live.py`, `tests/evals/test_compare.py`, `tests/evals/test_layer_contract.py`, `tests/test_scaffolding.py`, `CHANGELOG.md`, cross-check against [architecture.md](../../../architecture.md) §3 / §4 / §6 / §7 / §8.2, KDR-003, KDR-004, KDR-006, KDR-009, KDR-010, and the [T01 issue file](task_01_issue.md) M7-T01-ISS-03 retrofit.
**Status:** ✅ PASS — no OPEN issues. (2026-04-21 addendum: M7-T03-ISS-02 sub-graph resolution retrofit landed in T05's working tree; status unchanged.)

---

## Design-drift check

| Axis | Finding |
| --- | --- |
| New dependency | None. Only stdlib (`asyncio`, `difflib`, `importlib`, `json`, `os`, `re`, `time`, `typing.get_type_hints`, `unittest.mock.patch`) + existing in-tree modules. No `pydantic-ai`, no `instructor`, no external observability backend. |
| New module / layer | Three new modules inside the existing `ai_workflows.evals` package: `runner.py`, `_stub_adapter.py`, `_compare.py`. All sit in the `evals` layer created at T01. Import-linter still enforces the 4 layer contracts (4 kept, 0 broken). **Contract name + `forbidden_modules` amended** — see M7-T01-ISS-03 retrofit in [task_01_issue.md](task_01_issue.md) for the justification. The amendment is load-bearing for T03: the runner genuinely requires the `evals → workflows` edge (imports the workflow module to extract `StateNodeSpec.runnable` for single-node replay). |
| LLM call added | The runner replays existing workflow LLM nodes through their own `TieredNode` + `ValidatorNode` pairs; no new call site. Deterministic mode monkey-patches `LiteLLMAdapter` → `StubLLMAdapter`, so no provider call fires. Live mode dispatches through the real registry. **KDR-004 honoured**: the replay graph is `START → <node> → <node>_validator → END`, preserving the validator pairing in the same graph position as production. |
| KDR-003 no Anthropic API | Confirmed — no `anthropic` SDK import, no `ANTHROPIC_API_KEY` lookup. `_stub_tier_registry` rewrites every tier (including `ClaudeCodeRoute` tiers) to `LiteLLMRoute("stub/{name}")` so the stub is the only adapter the deterministic path reaches; no subprocess fires. |
| Checkpoint / resume | None. Replay graphs are single-shot `StateGraph.compile().ainvoke(...)` invocations with no checkpointer. KDR-009 N/A — replay does not persist state across resumes. |
| Retry logic | None bespoke. The runner inherits the workflow's `retrying_edge` + `wrap_with_error_handler` chain via `target_spec.runnable`; errors surface through `state["last_exception"]` which the runner inspects and translates to `EvalResult.error`. No new try/except retry loop outside that inheritance. KDR-006 honoured. |
| Observability | `StructuredLogger` inherited through `TieredNode`. `CostTrackingCallback` instantiated with `budget_cap_usd=None` per case (side-effect free — tracker never persisted). No Langfuse / OTel / LangSmith imports. nice_to_have.md §1/§3/§8 triggers untouched. |
| KDR-010 bare-typed | N/A — no new `response_format` schemas introduced. The stub adapter accepts and ignores `response_format` on `complete(...)`. |
| Four-layer contract | `evals → workflows` now permitted; `evals → cli` / `evals → mcp` still forbidden. `graph → evals` still forbidden (import-linter contract 2 of 4 + companion AST grep in `tests/evals/test_layer_contract.py`). `workflows → evals` still permitted (T02 dispatch wiring). All 4 contracts pass `lint-imports`. |

**Verdict:** no HIGH drift. The single architectural change (import-linter contract relaxation) is documented both inline in `pyproject.toml` and as a retrofit M7-T01-ISS-03 entry in the T01 issue file; CHANGELOG entry spells out the rationale.

---

## AC grading

| # | Criterion | Status | Evidence |
| --- | --- | --- | --- |
| 1 | `EvalRunner(mode="deterministic").run(suite)` returns `pass_count=N, fail_count=0` on passing fixtures | ✅ PASS | [test_runner_deterministic.py:62-76](../../../../tests/evals/test_runner_deterministic.py#L62-L76) green. |
| 2 | Broken current-tree (prompt-template drift / schema drift) returns `fail_count >= 1` with human-readable error | ✅ PASS | [test_runner_deterministic.py:79-110](../../../../tests/evals/test_runner_deterministic.py#L79-L110) (template drift) + [test_runner_deterministic.py:112-159](../../../../tests/evals/test_runner_deterministic.py#L112-L159) (schema drift) both green. |
| 3 | `EvalRunner(mode="live")` refused unless both `AIW_EVAL_LIVE=1` and `AIW_E2E=1` are set | ✅ PASS | [test_runner_live.py:26-51](../../../../tests/evals/test_runner_live.py#L26-L51) green (three construction tests covering each env permutation). |
| 4 | `compare(...)` honours every `EvalTolerance.mode` + `field_overrides` | ✅ PASS | [test_compare.py](../../../../tests/evals/test_compare.py) — eight tests: pass+fail per mode, mixed field_overrides, strict_json unified diff, schema-parse fallback. |
| 5 | Stub adapter raises loudly when a case is missing — incomplete suites do not silently pass | ✅ PASS | `StubAdapterMissingCaseError` raised when `_pending_output is None` ([_stub_adapter.py:108-113](../../../../ai_workflows/evals/_stub_adapter.py#L108-L113)); runner also hard-fails on unknown `node_name` via `_EvalCaseError` before `ainvoke` ([runner.py:295-305](../../../../ai_workflows/evals/runner.py#L295-L305)). Test [test_runner_deterministic.py:162-184](../../../../tests/evals/test_runner_deterministic.py#L162-L184) green. |
| 6 | KDR-004 discipline: replay runner invokes paired `ValidatorNode` in the same graph position; no replay-only bypass | ✅ PASS | [runner.py:311-316](../../../../ai_workflows/evals/runner.py#L311-L316) adds both `target_spec.runnable` and `validator_spec.runnable` to the replay graph with edges `START → node → validator → END`. Runner hard-fails if the paired `{node}_validator` is absent ([runner.py:300-305](../../../../ai_workflows/evals/runner.py#L300-L305)) so a validator-less replay cannot silently succeed. |
| 7 | Import-linter 4/4 kept | ✅ PASS | `uv run lint-imports` → 4 kept, 0 broken. Contract 4 was renamed (`"evals depends on graph + primitives only"` → `"evals cannot import surfaces"`) and narrowed from `[workflows, cli, mcp]` → `[cli, mcp]`; amendment traced in the M7-T01-ISS-03 retrofit. |
| 8 | `uv run pytest && uv run lint-imports && uv run ruff check` green | ✅ PASS | 522 passed, 4 skipped; 4 kept 0 broken; `All checks passed!`. |

---

## 🔴 HIGH

None.

## 🟡 MEDIUM

### M7-T03-ISS-02 — Replay runner did flat-node lookup, missed sub-graph-wrapped LLM nodes (RESOLVED in T05)

**Surfaced:** 2026-04-21 during T05 seed-fixture capture for `slice_refactor`.
**Resolved:** 2026-04-21 in the T05 working tree.

The T03 `_invoke_replay` resolved `case.node_name` via a flat dict lookup against `build_workflow().nodes`. That works for `planner` (every LLM node sits at the top-level `StateGraph`) but misses `slice_refactor`'s `slice_worker` + `slice_worker_validator`, which are wrapped inside the compiled `slice_branch` sub-graph dispatched per-slice via LangGraph's `Send`. Running `aiw eval run slice_refactor` against a correctly-captured `slice_worker` fixture produced `_EvalCaseError: case references node 'slice_worker' which is not registered in workflow 'slice_refactor'` — a false negative that would block T05's AC-2 outright.

**Resolution landed in T05's working tree** (`ai_workflows/evals/runner.py`):

- New `_resolve_node_scope(graph, node_name, validator_name)` helper: returns `(state_schema, target_spec, validator_spec)` resolved top-level first, then walking each top-level runnable's `.builder` attribute (present on `CompiledStateGraph`) to find the enclosing `StateGraph` that contains both nodes. Requires the target + validator to land in the *same* scope — cross-scope pairing is a wiring error.
- New `_node_exists_anywhere(graph, node_name)` helper: distinguishes "node missing" from "validator missing" so the caller emits the right `_EvalCaseError` text.
- `_invoke_replay` updated to use the helper and to pass the resolved sub-graph's `state_schema` to `_hydrate_state` (so replay of `slice_worker` hydrates `SliceBranchState`, not the parent `SliceRefactorState`).
- Runner module docstring amended with a "sub-graph walk" paragraph naming this retrofit.

**Tests:**

- `tests/evals/test_runner_deterministic.py::test_resolve_node_scope_walks_into_compiled_subgraphs` — asserts `slice_worker` + `slice_worker_validator` resolve via the sub-graph walk and return `SliceBranchState` as the replay schema.
- `tests/evals/test_runner_deterministic.py::test_resolve_node_scope_returns_none_on_missing_validator` — asserts the helper returns `None` (not a silent half-resolution) when the paired validator is absent.
- `tests/evals/test_seed_fixtures_deterministic.py::test_slice_refactor_seed_fixtures_replay_green_deterministic` — end-to-end cover: committed slice_refactor fixture replays green, exercising the same code path.

**Severity:** 🟡 MEDIUM — no silent false positives (the runner raised loudly rather than passing), but blocking the slice_refactor replay outright would have left the M7 harness with no coverage of the M6 workflow.

**Propagation:** CHANGELOG entry under M7 Task 05 names this retrofit trigger; the M7-T03 audit verdict (`✅ PASS`) is reaffirmed for the portion of the runner it originally audited — this addendum covers behaviour the T03 audit did not exercise (no sub-graph workflow existed in the suite at T03 time).

## 🟢 LOW

### M7-T03-ISS-01 — `StubLLMAdapter.calls()` classmethod has no in-tree consumer yet

[`_stub_adapter.py:134-138`](../../../../ai_workflows/evals/_stub_adapter.py#L134-L138) adds a `calls()` classmethod returning a copy of the per-arm call log. None of the current test suite or runner code reads it — it exists for future debuggability (e.g. a T04 `aiw eval run --verbose` mode that dumps which messages the stub saw). Kept because its cost is trivial (~5 lines, class-level list already maintained for internal state) and its removal would be unrelated drive-by cleanup. Flag-only, no action required.

**Action / Recommendation:** No action at T03. Revisit if T04 / T05 does not wire a consumer within this milestone.

**Severity:** 🟢 LOW — unused helper, zero risk.

---

## Additions beyond spec — audited and justified

- **`_stub_tier_registry` rewrites every tier to `LiteLLMRoute("stub/{name}")`** ([runner.py:417-441](../../../../ai_workflows/evals/runner.py#L417-L441)). Task spec says "a stub tier registry whose adapter returns each case's expected_output verbatim" but does not prescribe how `ClaudeCodeRoute` tiers are handled. The Builder's choice keeps the monkey-patch surface a single attribute (`tiered_node_module.LiteLLMAdapter`) rather than requiring a second adapter swap for subprocess tiers — simpler to audit and preserves the AC-5 invariant (any fired call goes through the armed stub). **Accepted** — preserves task semantics, reduces test-harness complexity, and keeps the Claude Code CLI subprocess path from firing under deterministic replay.
- **`_hydrate_state` rebuilds pydantic-model state values from their JSON dumps** ([runner.py:384-414](../../../../ai_workflows/evals/runner.py#L384-L414)). T02's `CaptureCallback` normalises pydantic leaves via `model_dump(mode="json")` before writing a fixture; replay must reverse that normalisation so the workflow's `prompt_fn` can call `state["input"].goal`. Uses `typing.get_type_hints(state_schema)` — a principled reflection, not a workflow-specific map. **Accepted** — closes the capture/replay round-trip that would otherwise be a silent type error on the first `prompt_fn` access.
- **`_patched_adapters` async context manager** ([runner.py:448-477](../../../../ai_workflows/evals/runner.py#L448-L477)). Wraps `patch.object(...)` in `__aenter__` / `__aexit__` so the patch is scoped to the `async with` block, and pairs it with `StubLLMAdapter.arm/disarm` so class-level state is bounded per case. Deterministic-mode only; live-mode is a no-op context. **Accepted** — idiomatic test-isolation shape for class-level stub state; matches the module-docstring's "single-case-per-invoke invariant".
- **`_EvalCaseError` internal sentinel** ([runner.py:444-445](../../../../ai_workflows/evals/runner.py#L444-L445)). Used to surface three distinct validation shortfalls before `ainvoke` fires (unknown workflow, unknown node, missing paired validator). Caught by the generic `except Exception` in `_run_case` and stamped into `EvalResult.error`. **Accepted** — keeps the pre-replay validation path centralised and observable.
- **`CHANGELOG.md` entry names M7-T01-ISS-03 as the retrofit trigger** (see `## [Unreleased]` → `### Added — M7 Task 03: Replay Runner`). Matches the M7-T01-ISS-02 pattern T02 set for its own retrofit. **Accepted** — audit-trail hygiene.

None of these additions pulls in external dependencies, adds new surfaces, or introduces coupling the spec did not already imply.

---

## Gate summary

| Gate | Result |
| --- | --- |
| `uv run pytest` | 522 passed, 4 skipped, 2 warnings |
| `uv run pytest tests/evals/` | 44 passed, 1 skipped |
| `uv run lint-imports` | 4 kept, 0 broken |
| `uv run ruff check` | All checks passed |

---

## Issue log

| ID | Severity | Summary | Owner / next touch point |
| --- | --- | --- | --- |
| M7-T03-ISS-01 | 🟢 LOW | `StubLLMAdapter.calls()` has no in-tree consumer yet | Flag-only; revisit if T04/T05 does not wire it |
| M7-T01-ISS-03 | 🟡 MEDIUM | Import-linter contract forbade `evals → workflows` over-restrictively | **Propagated** to [../issues/task_01_issue.md](task_01_issue.md) as retrofit; resolved in this task's working tree |
| M7-T03-ISS-02 | 🟡 MEDIUM | Replay runner flat-node lookup missed sub-graph-wrapped LLM nodes (`slice_worker`) | **RESOLVED** in T05 working tree — `_resolve_node_scope` + `_node_exists_anywhere` helpers walk `CompiledStateGraph.builder` |

---

## Deferred to nice_to_have

None.

---

## Propagation status

- **M7-T01-ISS-03** propagated to [../issues/task_01_issue.md](task_01_issue.md) as a MEDIUM retrofit entry + issue-log row. The T01 issue file documents the import-linter contract narrowing + renaming and links back to this audit.
- No new carry-over for T04/T05/T06 beyond what those task files already reference.
