# Task 01 — Eval Dataset Schema + Storage Layout — Audit Issues

**Source task:** [../task_01_dataset_schema.md](../task_01_dataset_schema.md)
**Audited on:** 2026-04-21
**Audit scope:** `ai_workflows/evals/`, `tests/evals/`, `pyproject.toml` importlinter block, `CHANGELOG.md`, `evals/.gitkeep`, cross-check against [architecture.md](../../../architecture.md) §3 / §4 / §5 / §7 / §10, KDR-004, KDR-010 / [ADR-0002](../../../adr/0002_bare_typed_response_format_schemas.md).
**Status:** ✅ PASS — no OPEN issues.

---

## Design-drift check

| Axis | Finding |
| --- | --- |
| New dependency | None. Only `pydantic` (already in deps) + stdlib (`pathlib`, `datetime`, `os`, `typing`). |
| New module / layer | `ai_workflows.evals` package added. Paired with a new (4th) import-linter contract. Layer semantically fits architecture.md §10 roadmap item 7 ("Eval harness") and §5 "Prompting is a contract". §3 layer diagram does not yet mention `evals`; documentation-level follow-up logged as LOW (ISS-01). |
| LLM call added | None. No provider calls, no TieredNode usage. |
| Checkpoint / resume | None. |
| Retry logic | None. |
| Observability | None beyond existing primitives. |
| KDR-010 bare-typed | Confirmed — `EvalCase`, `EvalSuite`, `EvalTolerance` use only typed fields + `Field(default_factory=...)`; no `min_length` / `max_length` / `ge` / `le` anywhere. |
| KDR-004 validator-after-LLM | N/A — this task ships no LLM nodes. |
| KDR-003 no Anthropic API | N/A — no provider code. |
| KDR-009 SqliteSaver | N/A — no checkpoint logic. |
| KDR-006 retry taxonomy | N/A. |
| Four-layer contract | Extended to five contracts of enforcement (4 via importlinter + 1 via AST test). evals → workflows/cli/mcp blocked; graph/workflows → evals blocked. |

**Verdict:** no HIGH drift. One LOW (doc) logged below.

---

## AC grading

| # | Criterion | Status | Evidence |
| --- | --- | --- | --- |
| 1 | `from ai_workflows.evals import EvalCase, EvalSuite, save_case, load_suite` works | ✅ PASS | Every test module imports the public surface; 21 tests green. |
| 2 | Models are pydantic v2 w/ `extra="forbid"` and `frozen=True`, bare-typed per KDR-010 | ✅ PASS | [schemas.py:47-50](../../../../ai_workflows/evals/schemas.py#L47-L50), [schemas.py:69](../../../../ai_workflows/evals/schemas.py#L69), [schemas.py:91](../../../../ai_workflows/evals/schemas.py#L91); `test_eval_case_rejects_extra_fields`, `test_eval_case_is_frozen`. |
| 3 | `save_case` / `load_suite` round-trip lossless | ✅ PASS | `test_round_trip_preserves_tolerance_overrides`, `test_eval_case_serialization_round_trip`, `test_load_suite_aggregates_nested_cases`. |
| 4 | Import-linter: **4 kept, 0 broken** | ✅ PASS | `uv run lint-imports` output: 4 kept, 0 broken. |
| 5 | Every listed test passes under `uv run pytest tests/evals/` | ✅ PASS | 21 passed; all eight tests named in the task spec are present and green. |
| 6 | `uv run ruff check` clean | ✅ PASS | "All checks passed!" |
| 7 | No `ai_workflows.evals` import inside `graph/` or `workflows/` | ✅ PASS | `tests/evals/test_layer_contract.py::test_subpackage_does_not_import_evals[graph/workflows]` both green; AST grep confirms. |

---

## 🔴 HIGH

None.

## 🟡 MEDIUM

### M7-T01-ISS-03 — `evals → workflows` forbidden in import-linter contract was over-restrictive (retrofit amendment, 2026-04-21)

**Observation (added during T03 implementation).** T01's fourth import-linter contract originally forbade `ai_workflows.evals` from importing `ai_workflows.workflows` (alongside the surfaces). T03's replay runner (`ai_workflows/evals/runner.py`) genuinely needs that edge: the runner imports the workflow module to pull out a node's `StateNodeSpec.runnable` and wire a single-node replay `StateGraph`. That is the only way to replay exactly one node without reinventing the planner's private builder functions.

The corrected architectural rule: **`evals` is peer to the two surfaces** (library of replay/capture helpers sitting above `graph`, not below `workflows`). The contract has been narrowed to forbid only `evals → {cli, mcp}`. The name is updated from `"evals depends on graph + primitives only"` → `"evals cannot import surfaces"` to reflect the narrower intent. `pyproject.toml` [tool.importlinter] block carries an inline comment recording this amendment; `tests/test_scaffolding.py` assertion substring was updated accordingly.

**Action / Recommendation.** Retrofit amendment — no code changes at T01 scope beyond the contract rename. The T01 pyproject contract + scaffolding test have already been updated by T03. This entry exists so the T01 audit record reflects the discovered correction rather than leaving the original contract frozen as "correct".

**Owner.** Closed in T03's working tree. T01 bookkeeping only.

**Severity.** MEDIUM — documented drift between T01's originally-graded AC-4 scope and the final resolved layer rule. Same category as M7-T01-ISS-02.

### M7-T01-ISS-02 — Layer-contract test was over-restrictive (retrofit amendment, 2026-04-21)

**Observation (added during T02 implementation).** T01's `tests/evals/test_layer_contract.py` was parametrized over `["graph", "workflows"]`, forbidding either subpackage from importing `ai_workflows.evals`. T02 required `ai_workflows/workflows/_dispatch.py` to import `CaptureCallback` at dispatch time so the `AIW_CAPTURE_EVALS` opt-in path could construct it — exactly the situation the test was blocking.

The correct architectural rule is narrower: **`graph → evals` is forbidden** (lower layer must not reach into a higher one), but `workflows → evals` is allowed — workflows already sits above both `graph` and `evals`, and the dispatch module wiring the callback is the natural seam for the opt-in. T02 relaxed the test to guard only the `graph → evals` direction and documented the correction in [tests/evals/test_layer_contract.py](../../../../tests/evals/test_layer_contract.py) + [ai_workflows/evals/__init__.py](../../../../ai_workflows/evals/__init__.py) docstrings.

**Action / Recommendation.** Retrofit amendment — no code changes at T01 scope; the T01 test file has already been updated by T02. This entry exists so the T01 audit record reflects the discovered correction rather than leaving the original parametrisation frozen as "correct".

**Owner.** Closed in T02's working tree. T01 bookkeeping only.

**Severity.** MEDIUM — documented drift between T01's originally-graded AC-7 scope and the final resolved layer rule.

## 🟢 LOW

### M7-T01-ISS-01 — architecture.md §3 / §4 does not yet document the `evals` layer

`architecture.md` §3 still diagrams four layers (`primitives → graph → workflows → surfaces`); §4 lists four subsections (4.1 Primitives, 4.2 Graph, 4.3 Workflows, 4.4 Surfaces). The new `ai_workflows.evals` package sits alongside `graph` in the layer order (imports primitives + graph, forbidden from workflows/cli/mcp on the import side, and not-importable-by graph/workflows on the export side). This placement is correct per the task spec and §10 roadmap item 7, but the architecture document has not yet been updated to reflect it.

**Action / Recommendation:** Defer to M7 Task 06 milestone close-out. The close-out Builder should extend `architecture.md` §3 diagram to show `evals` as a peer of `graph` (both consume `primitives`, both are consumed by surfaces; workflows does not consume evals), and add a `§4.5 Evals layer` subsection summarising the package's role. Until T06 lands, the import-linter contract + companion AST test carry the enforceable meaning of the layer rule.

**Owner:** M7 Task 06 (close-out).

---

## Additions beyond spec — audited and justified

- **`default_evals_root()` helper + `EVALS_ROOT` module-level constant** ([storage.py:38-46](../../../../ai_workflows/evals/storage.py#L38-L46)). Task spec shows `root: Path = EVALS_ROOT` as a default argument; Builder switched to `root: Path | None = None` and resolves through `default_evals_root()` inside the function body. Rationale: env-var override (`AIW_EVALS_ROOT`) must be read at call time, not at import time — the default-argument pattern would freeze the env state when the module loads. Export list declares both to keep the helper testable. Acceptable — preserves task semantics, fixes a latent env-resolution bug.
- **`tests/evals/test_layer_contract.py`**. Task AC-7 (no evals import from graph/workflows) was said to be "verified by the new import-linter contract". The task's contract code block covers only the `evals → {workflows, cli, mcp}` direction. Builder added an AST-grep test to close the other direction. Rationale preserved in-doc (code comment in `pyproject.toml` + docstring in the test module). Acceptable — satisfies the AC without adding a 5th import-linter contract that would contradict the task's "existing 3 + new 1 = 4 total" arithmetic.
- **`tests/test_scaffolding.py` contract-count update** from `== 3` to `== 4`. Required follow-on; test would have failed otherwise.

---

## Gate summary

| Gate | Result |
| --- | --- |
| `uv run pytest` | 496 passed, 3 skipped |
| `uv run pytest tests/evals/` | 21 passed |
| `uv run lint-imports` | 4 kept, 0 broken |
| `uv run ruff check` | All checks passed |

---

## Issue log

| ID | Severity | Summary | Owner / next touch point |
| --- | --- | --- | --- |
| M7-T01-ISS-01 | 🟢 LOW | architecture.md §3 / §4 does not yet document the evals layer | DEFERRED → M7 Task 06 (close-out) |
| M7-T01-ISS-02 | 🟡 MEDIUM | Layer-contract test forbade `workflows → evals` over-restrictively | RESOLVED in T02 working tree (retrofit bookkeeping) |
| M7-T01-ISS-03 | 🟡 MEDIUM | Import-linter contract forbade `evals → workflows` over-restrictively | RESOLVED in T03 working tree (retrofit bookkeeping) |

---

## Deferred to nice_to_have

None.

---

## Propagation status

- M7-T01-ISS-01 propagated as a carry-over on [../task_06_milestone_closeout.md](../task_06_milestone_closeout.md).
