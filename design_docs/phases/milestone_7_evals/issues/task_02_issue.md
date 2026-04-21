# Task 02 — Capture Callback — Audit Issues

**Source task:** [../task_02_capture_callback.md](../task_02_capture_callback.md)
**Audited on:** 2026-04-21
**Audit scope:** `ai_workflows/evals/capture_callback.py`, `ai_workflows/evals/__init__.py`, `ai_workflows/graph/tiered_node.py` (eval-capture wiring block), `ai_workflows/workflows/_dispatch.py` (`_build_eval_capture_callback`, `_build_cfg`, `run_workflow`, `resume_run` signatures), `tests/evals/test_capture_callback.py`, `tests/evals/test_layer_contract.py` (relaxation), `CHANGELOG.md`, cross-check against [architecture.md](../../../architecture.md) §3 / §4.2 / §4.1 / §7, KDR-004 / KDR-009 / KDR-010, milestone README exit criterion 1, T01 issue file ([task_01_issue.md](task_01_issue.md)).
**Status:** ✅ PASS — all OPEN issues resolved in Cycle 2 re-implement (2026-04-21).

**Cycle log:**

- **Cycle 1 (2026-04-21)** — Implement phase landed the callback + dispatch wiring + 7 callback-level unit tests. Audit found 1 HIGH (missing dispatch integration tests) + 1 MEDIUM (task-doc placement drift vs. milestone README). Status: 🟥 FAIL.
- **Cycle 2 (2026-04-21)** — Re-implement phase added `tests/workflows/test_dispatch_capture_opt_in.py` (3 integration tests, all green) and amended the task doc in-place to match the milestone README exit criterion 1. Both OPEN issues RESOLVED. Status: ✅ PASS.

---

## Design-drift check

| Axis | Finding |
| --- | --- |
| New dependency | None. Only stdlib (`uuid`, `datetime`, `pathlib`, `os`, `logging`, `typing`) + already-listed `pydantic`. |
| New module / layer | `ai_workflows/evals/capture_callback.py` added. **Task spec placed the callback at `ai_workflows/graph/eval_capture_callback.py`.** Builder moved it to `evals/` because the callback imports `EvalCase` + `save_case` from `ai_workflows.evals`; a `graph/` module doing the same import would violate the architecture.md §3 layer order (`graph` cannot import `evals`; `evals` sits above `graph`). The new placement matches **milestone README exit criterion 1** which explicitly says "`ai_workflows.evals` package exports `EvalCase`, `EvalSuite`, `EvalRunner`, `CaptureCallback`". Task spec is the out-of-date document here. Flagged as MEDIUM below (the task-doc ACs must be amended to reflect the correct placement). |
| LLM call added | None. Callback is pure instrumentation, no provider calls. |
| Checkpoint / resume | None. |
| Retry logic | None. Callback swallows its own exceptions and logs at WARNING — matches the "capture must never break a live run" contract in the task doc. |
| Observability | `_LOG = logging.getLogger(__name__)` — std `logging` with `exc_info=True`. Does not use `StructuredLogger` directly; the warning goes through whatever handlers pytest / the CLI install. Acceptable at this scope but noted in the "Additions beyond spec" section because the task sketch said "logged at `WARNING` via `StructuredLogger`". |
| KDR-004 (validator after every LLM node) | Unaffected — no graph topology change; TieredNode still pairs with its ValidatorNode unchanged. Cost callback ordering preserved. |
| KDR-003 (no Anthropic API) | Unaffected — no provider code. |
| KDR-009 (SqliteSaver) | Unaffected — no checkpointer change. |
| KDR-010 (bare-typed schemas) | Unaffected — callback does not define new `response_format` pydantic models. Reuses T01's `EvalCase` (already bare-typed and audited). |
| Four-layer contract | Extended: `workflows → evals` is now an allowed direction (required by `_dispatch.py` opt-in wiring). `graph → evals` remains blocked by the import-linter contract T01 added. T01's companion AST test was relaxed to match. See M7-T01-ISS-02 amendment below. |
| Duck-typing the graph → evals boundary | `TieredNode` reads `configurable.get("eval_capture_callback")` and calls `on_node_complete(...)` without importing `CaptureCallback`. Keeps the graph layer evals-unaware and preserves the one-direction rule. |

**Verdict:** no HIGH drift. One MEDIUM (task-doc AC drift between task spec and milestone README).

---

## AC grading

| # | Criterion | Status | Evidence |
| --- | --- | --- | --- |
| 1 | `CaptureCallback` exported from `ai_workflows.evals` (amended 2026-04-21 per milestone README exit criterion 1) | ✅ PASS | [ai_workflows/evals/__init__.py:41,52](../../../../ai_workflows/evals/__init__.py#L41). Task-doc amended in Cycle 2 to reflect this (M7-T02-ISS-01 RESOLVED). |
| 2 | `AIW_CAPTURE_EVALS=<name>` set → one fixture per LLM-node call at `evals/<name>/<workflow>/<node>/<case_id>.json`, verified via dispatch-driven test | ✅ PASS | [tests/workflows/test_dispatch_capture_opt_in.py::test_dispatch_attaches_capture_callback_when_env_set](../../../../tests/workflows/test_dispatch_capture_opt_in.py) exercises the full env-var → `_build_eval_capture_callback` → `_build_cfg` → `TieredNode` → fixture-on-disk chain against a stubbed planner run. Fixture round-trips as `EvalCase` and carries `captured_from_run_id`. (Cycle 2; M7-T02-ISS-02 RESOLVED.) |
| 3 | `AIW_CAPTURE_EVALS` unset → byte-identical default path: no fixture directory, no callback attached | ✅ PASS | [test_dispatch_skips_capture_when_env_unset](../../../../tests/workflows/test_dispatch_capture_opt_in.py) asserts (a) no `evals/` directory exists post-run, and (b) `_build_eval_capture_callback(...)` returns `None`, and (c) `_build_cfg(..., eval_capture_callback=None)` produces a `configurable` dict without the `"eval_capture_callback"` key. (Cycle 2; M7-T02-ISS-02 RESOLVED.) |
| 4 | `save_case` errors logged, not raised — run with broken capture environment still completes normally | ✅ PASS | Callback-scope: [test_capture_failure_logs_warning_but_does_not_raise](../../../../tests/evals/test_capture_callback.py#L123-L146). End-to-end confirmation: [test_capture_does_not_affect_run_result](../../../../tests/workflows/test_dispatch_capture_opt_in.py) runs the approve path twice (capture off then on) and asserts identical `{run_id-shape, status, awaiting, plan, total_cost_usd, error}` surface. (Cycle 2.) |
| 5 | KDR-004 unaffected: no `ValidatorNode` wiring changed, no prompt change | ✅ PASS | `ai_workflows/graph/tiered_node.py` diff touches only the post-cost-callback block; no validator changes; no prompt text changes. Grep confirms zero new `response_format=` sites and zero new prompt strings. |
| 6 | Import-linter 4/4 kept | ✅ PASS | `uv run lint-imports` → 4 kept, 0 broken. |
| 7 | `uv run pytest && uv run lint-imports && uv run ruff check` green | ✅ PASS (subject to AC-2 / AC-3 gap) | `uv run pytest` 502 passed / 3 skipped; `lint-imports` 4/0; `ruff check` clean. |

---

## 🔴 HIGH

### M7-T02-ISS-02 — Dispatch-level integration tests are missing (AC-2 / AC-3 unverified) — ✅ RESOLVED (Cycle 2, 2026-04-21)

**Resolution.** Added `tests/workflows/test_dispatch_capture_opt_in.py` with the three tests named in the task spec. All three green. Uses a directory-local hermetic `planner_tier_registry` override (mirroring [tests/mcp/conftest.py](../../../../tests/mcp/conftest.py)) so both the explorer and synth (`planner` node) calls route through the `_StubLiteLLMAdapter` — the synth tier ships as `ClaudeCodeRoute` in production and would otherwise spawn a real subprocess. Fixture verification uses explicit `explorer_dir.glob("*.json")` checks on disk plus an `EvalCase.model_validate_json` round-trip. Post-resolution gate: `uv run pytest` → 505 passed (+3 from the cycle-1 502 baseline).

---

### M7-T02-ISS-02 — (original finding, preserved for audit history)

**Observation.** The task spec lists, under "Tests", a second file with three specific integration tests:

> [tests/workflows/test_dispatch_capture_opt_in.py](../../../../tests/workflows/test_dispatch_capture_opt_in.py):
>
> - `test_dispatch_attaches_capture_callback_when_env_set` — `AIW_CAPTURE_EVALS=testsuite` set, `run_workflow` run against a stub adapter, fixture JSON appears under `<tmp_path>/testsuite/...`.
> - `test_dispatch_skips_capture_when_env_unset` — default: zero fixtures written, no `CaptureCallback` in `callbacks`.
> - `test_capture_does_not_affect_run_result` — approve-path run with capture enabled returns the same `{run_id, status, plan, total_cost_usd}` shape as without capture.

`tests/workflows/test_dispatch_capture_opt_in.py` does not exist. AC-2 and AC-3 therefore have **no test verifying the wiring chain end-to-end**:

```
AIW_CAPTURE_EVALS env var
  → _build_eval_capture_callback (dispatch)
  → _build_cfg inserts "eval_capture_callback" into configurable
  → TieredNode reads configurable.get("eval_capture_callback") (graph)
  → callback.on_node_complete(...)
  → fixture JSON written under <root>/<workflow>/<node>/<case>.json
```

A regression that broke any single link — for example, `_build_cfg` forgetting to copy the callback into `configurable`, or `TieredNode.get("eval_capture_callback")` being renamed, or a future refactor that swallowed the env var in a different branch — would pass the entire current suite and ship silently. The existing unit tests in [tests/evals/test_capture_callback.py](../../../../tests/evals/test_capture_callback.py) call `on_node_complete` directly and cannot catch wiring regressions.

**Impact.** AC-2, AC-3, and the full-run half of AC-4 are all transitively uncovered. The callback works; the wiring around it is claimed but not tested.

**Action / Recommendation.** Add `tests/workflows/test_dispatch_capture_opt_in.py` implementing the three tests named in the task spec. Use the existing stub-adapter pattern from [tests/workflows/test_planner_graph.py](../../../../tests/workflows/test_planner_graph.py) (stubbed tier registry, no live providers) so the suite stays deterministic. Assertion shapes:

1. `test_dispatch_attaches_capture_callback_when_env_set` — set `AIW_CAPTURE_EVALS="testsuite"` via `monkeypatch.setenv`, set `AIW_EVALS_ROOT=tmp_path`, run `run_workflow(workflow="planner", inputs={...})` with a stubbed explorer + synth tier. Assert that `(tmp_path / "testsuite" / "planner" / "explorer").glob("*.json")` has at least one fixture and the JSON loads as an `EvalCase`.
2. `test_dispatch_skips_capture_when_env_unset` — env var explicitly unset; same dispatch call. Assert `(tmp_path / "testsuite").exists() is False` **and** that the `configurable` dict built by `_build_cfg` under this branch does not contain the `"eval_capture_callback"` key. (Verify the key-absence via direct unit call to `_build_eval_capture_callback(workflow=..., run_id=..., dataset_override=None)` returning `None`, then `_build_cfg(..., eval_capture_callback=None)` producing a configurable without the key.)
3. `test_capture_does_not_affect_run_result` — run the approve-path planner twice, once with `AIW_CAPTURE_EVALS` set and once without. Assert the returned `{run_id, status, plan, total_cost_usd}` dicts are shape-equivalent (ignoring `run_id` values, plan content variation if the stub is non-deterministic — pin the stub to return the same output both times).

**Owner.** Re-implement phase of this audit cycle (same task, next iteration).

**Severity.** HIGH — explicit task deliverable missing, two ACs uncovered. Blocks T02 PASS.

---

## 🟡 MEDIUM

### M7-T02-ISS-01 — Task-doc AC-1 prescribes a placement that contradicts milestone README exit criterion 1 — ✅ RESOLVED (Cycle 2, 2026-04-21)

**Resolution.** Amended [../task_02_capture_callback.md](../task_02_capture_callback.md) in place: (a) amendment note at the top of the file citing this issue; (b) deliverable heading flipped from `ai_workflows/graph/eval_capture_callback.py` → `ai_workflows/evals/capture_callback.py` + `ai_workflows/graph/__init__.py` → `ai_workflows/evals/__init__.py`; (c) class sketch rewritten to show the plain-class + `on_node_complete(...)` shape the codebase actually uses; (d) AC-1 flipped from `ai_workflows.graph` → `ai_workflows.evals`; (e) test-file location moved to `tests/evals/test_capture_callback.py` and test names updated to match what Cycle 1 shipped. Dependencies section updated: the spec's `BaseCallbackHandler` / `langchain-core` reference is now correctly scoped to std `logging.getLogger`.

---

### M7-T02-ISS-01 — (original finding, preserved for audit history)

**Observation.** [task_02_capture_callback.md](../task_02_capture_callback.md) AC-1 reads:

> `CaptureCallback` exported from `ai_workflows.graph`.

This contradicts the milestone README's exit criterion 1:

> `ai_workflows.evals` package exports `EvalCase`, `EvalSuite`, `EvalRunner`, `CaptureCallback`.

Builder took the README's prescription because (a) it matches the M7-wide layer direction T01 set up (evals imports graph+primitives; graph cannot import evals) and (b) a `graph/eval_capture_callback.py` module would have to import `EvalCase` + `save_case` from `ai_workflows.evals` to do its job, which is a `graph → evals` edge forbidden by the import-linter contract T01 landed.

**Impact.** Nominal — the actual behaviour matches the milestone exit criterion and the architecture.md §3 layer contract. But the task doc still reads wrong for any future reader, and the literal AC-1 line grades "unmet" mechanically.

**Action / Recommendation.** Amend [task_02_capture_callback.md](../task_02_capture_callback.md):

1. AC-1 line: change `ai_workflows.graph` → `ai_workflows.evals`.
2. Deliverable heading `### [ai_workflows/graph/eval_capture_callback.py]` → `### [ai_workflows/evals/capture_callback.py]`; strip the `BaseCallbackHandler` subclass line and the `on_llm_start` / `on_llm_end` pair from the sketch body; rewrite the class docstring sketch to reflect the actual `on_node_complete(*, run_id, node_name, inputs, raw_output, output_schema)` contract the codebase uses (matching `CostTrackingCallback`).
3. Deliverable heading `### [ai_workflows/graph/__init__.py]` → `### [ai_workflows/evals/__init__.py]`.
4. "Tests" heading: move `tests/graph/test_eval_capture_callback.py` → `tests/evals/test_capture_callback.py`.

These are doc-only changes; no code moves. The Builder follow-up for this issue is a single commit amending the task file with a terse "Amendment 2026-04-21 — task-doc placement corrected to match milestone README exit criterion 1; see task_02_issue.md M7-T02-ISS-01" note at the top.

**Owner.** Re-implement phase of this audit cycle (same task, next iteration).

**Severity.** MEDIUM — documentation drift between task and milestone spec, not a behaviour bug.

---

## 🟢 LOW

None.

---

## Additions beyond spec — audited and justified

- **Test file naming and placement: `tests/evals/test_capture_callback.py` (not `tests/graph/test_eval_capture_callback.py`).** Follows the file-placement correction under M7-T02-ISS-01. Tests live next to the module they test. Rationale preserved in-file via the module docstring. Acceptable.
- **Callback method shape: `on_node_complete(*, run_id, node_name, inputs, raw_output, output_schema)` instead of the task-spec sketch's `BaseCallbackHandler` subclass with `on_llm_start` / `on_llm_end`.** Rationale: (i) the codebase already standardised on the plain-class + `on_node_complete` pattern at `CostTrackingCallback` ([cost_callback.py](../../../../ai_workflows/graph/cost_callback.py)); (ii) LangChain's `on_llm_end` signature does not receive the `output_schema` the T03 replay runner needs; (iii) `TieredNode` already owns the post-node hook point where the cost callback fires, so threading the eval callback into the same call site is a one-line addition. Recorded in [CHANGELOG.md](../../../../CHANGELOG.md) under "Deviations from spec". Acceptable.
- **`output_schema_fqn()` as a module-level helper exported from `ai_workflows.evals`.** Used both by the callback itself and anticipated by the T03 replay runner which needs to resolve `output_schema_fqn` back to a `type[BaseModel]`. Exposing it at package scope lets T03 import one function rather than duplicating the `f"{schema.__module__}.{schema.__qualname__}"` convention. Acceptable.
- **`_resolve_unique_path` suffixing `-002`, `-003`, …** matches the task-spec line "append a monotonic suffix (`<case_id>-002.json`) rather than overwriting" verbatim. Acceptable.
- **`_normalize` / `_normalize_value` / `_normalize_output` helpers** that walk the `TieredNode` state dict and convert pydantic models to JSON-ready dicts via `model_dump(mode="json")`. The task spec does not list this explicitly, but the assertion "serialize into an `EvalCase`" requires the `inputs: dict[str, Any]` field to be JSON-serialisable — and `TieredNode` state frequently carries pydantic `*Input` models at the top-level keys. Without normalisation, `model_dump_json(indent=2)` would raise on any non-serialisable leaf. Covered by `test_normalizes_pydantic_inputs`. Acceptable.
- **Std `logging.getLogger(__name__)` rather than `StructuredLogger`.** The task spec says "logged at `WARNING` via `StructuredLogger`". The rest of the graph/evals layer uses plain `logging.getLogger` for warnings (compare `ai_workflows/graph/cost_callback.py` imports); `StructuredLogger` is the forward path for *emit-per-node-completion* records, not ad-hoc warnings. Acceptable — the warning carries `extra={"dataset", "workflow", "node", "run_id"}` so JSON handlers attached at the surface still see the context.
- **`tests/evals/test_layer_contract.py` relaxation — workflows → evals now allowed.** T01's AC-7 forbade both `graph → evals` and `workflows → evals`. The second half is incompatible with T02's opt-in wiring requirement (`_dispatch.py` must construct `CaptureCallback` at dispatch time, which requires importing it from `ai_workflows.evals`). Test relaxed to guard only `graph → evals` — the architecturally load-bearing direction. Recorded on the T01 audit file as M7-T01-ISS-02; see amendment below.

---

## Gate summary

### Cycle 1 (2026-04-21)

| Gate | Result |
| --- | --- |
| `uv run pytest` | 502 passed, 3 skipped |
| `uv run pytest tests/evals/` | 27 passed |
| `uv run pytest tests/evals/test_capture_callback.py` | 7 passed |
| `uv run lint-imports` | 4 kept, 0 broken |
| `uv run ruff check` | All checks passed |

### Cycle 2 (2026-04-21) — post resolution

| Gate | Result |
| --- | --- |
| `uv run pytest` | **505 passed**, 3 skipped (+3 new dispatch integration tests) |
| `uv run pytest tests/workflows/test_dispatch_capture_opt_in.py` | 3 passed |
| `uv run lint-imports` | 4 kept, 0 broken |
| `uv run ruff check` | All checks passed |

---

## Issue log

| ID | Severity | Summary | Status |
| --- | --- | --- | --- |
| M7-T02-ISS-01 | 🟡 MEDIUM | Task-doc AC-1 prescribed `ai_workflows.graph` export; milestone README says `ai_workflows.evals` (correct) | ✅ RESOLVED — task doc amended 2026-04-21 (Cycle 2) |
| M7-T02-ISS-02 | 🔴 HIGH | `tests/workflows/test_dispatch_capture_opt_in.py` missing; AC-2 / AC-3 uncovered at dispatch boundary | ✅ RESOLVED — 3 dispatch tests added, all green 2026-04-21 (Cycle 2) |
| M7-T01-ISS-02 | 🟡 MEDIUM | T01 layer-contract test was over-restrictive (forbade `workflows → evals`); relaxed in T02 so `_dispatch.py` can import `CaptureCallback` | ✅ AMENDED — retrofit entry on [task_01_issue.md](task_01_issue.md) 2026-04-21 |

---

## Deferred to nice_to_have

None.

---

## Propagation status

- **M7-T02-ISS-01 / M7-T02-ISS-02** — no forward-deferral. Both resolve in the next implement pass of this same task (no cross-milestone dependency).
- **M7-T01-ISS-02** — retrofitted as an amendment onto [task_01_issue.md](task_01_issue.md) so the T01 audit record reflects the layer-rule correction that was discovered during T02 implementation. No spec-file carry-over needed (T01 is already closed; the amendment is purely bookkeeping on the audit file).
