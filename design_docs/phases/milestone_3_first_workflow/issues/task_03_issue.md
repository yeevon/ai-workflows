# Task 03 — `planner` StateGraph — Audit Issues

**Source task:** [../task_03_planner_graph.md](../task_03_planner_graph.md)
**Audited on:** 2026-04-20
**Audit scope:** `ai_workflows/workflows/planner.py`, `ai_workflows/primitives/storage.py`, `migrations/003_artifacts.sql` + `.rollback.sql`, `tests/workflows/test_planner_graph.py`, `tests/primitives/test_storage.py`, `CHANGELOG.md`; cross-checked against `design_docs/architecture.md` (§3 layer contract, §4.1–§4.3, §5 runtime flow, §6 dependencies, §7 contracts, §8.2 error handling, §8.3 gates) and KDR-001/003/004/006/007/009.
**Status:** ✅ PASS — all ACs met; no OPEN issues.

## Design-drift check

| Vector | Result | Note |
| --- | --- | --- |
| New dependency | ✅ None | `langgraph` / `langchain_core` / `pydantic` all already in `architecture.md §6`. No `nice_to_have.md` item adopted. |
| New module/layer | ✅ Fits | All additions sit in existing layers: `workflows/planner.py` (workflows), `primitives/storage.py` (primitives), new migration under `migrations/`. No cross-layer hops introduced. `lint-imports`: 3 / 3 KEPT. |
| LLM call added | ✅ Pairs | Two `TieredNode`s, each followed by a `ValidatorNode` — KDR-004 honoured in the stricter two-validator form (task spec picks this over the README's single-validator sketch). Both nodes route through `LiteLLMAdapter` via `tiered_node`; no direct provider call. |
| Checkpoint/resume | ✅ LangGraph | Graph compiles against `build_async_checkpointer(...)` → `AsyncSqliteSaver`; no hand-rolled checkpoint writes. KDR-009 preserved. The new `artifacts` table is post-gate workflow output (architecture §5 step 8: "Terminal nodes emit artifacts to Storage") — *not* a reintroduction of the pre-pivot checkpoint-adjacent artifacts surface dropped by 002. |
| Retry logic | ✅ Taxonomy | Four `retrying_edge`s wired (one after each LLM node + one after each validator), each reading `last_exception` / `_retry_counts` / `_non_retryable_failures`. Every `TieredNode` is wrapped by `wrap_with_error_handler` so the raise→state-update contract from M2 T08 applies. No bespoke `try/except` retry loops — KDR-006 honoured. |
| Observability | ✅ Structured | All logging routes through `tiered_node` → `log_node_event` (section §8.1 shape). `workflow="planner"` stamped via `config["configurable"]["workflow"]`. No Langfuse / OTel / LangSmith pulled in. |
| Four-layer contract | ✅ Holds | `primitives → graph → workflows → surfaces`: `planner.py` imports `graph` + `primitives` only; `storage.py` imports stdlib only. `lint-imports` analyzed 22 files / 24 deps, 3 kept / 0 broken. |
| KDR-003 (no Anthropic API) | ✅ | Source-level guard `test_planner_module_has_no_anthropic_surface` greps for `import anthropic`, `from anthropic`, `ANTHROPIC_API_KEY` — none present. |
| `nice_to_have.md` items | ✅ None adopted | |

**Cross-layer extension flagged (task-spec sanctioned, not drift):** `SQLiteStorage.write_artifact` / `read_artifact` + the `StorageBackend` protocol additions land inside T03 per task spec lines 219–221 ("This is a cross-layer change (primitives), so flag it clearly in the task's deviations if it must land inside this task or file a sibling T03a"). No T03a was filed; the change lands here with:

- A narrow ``(run_id, kind, payload_json, created_at)`` schema — no `file_path`, no `artifact_type`, no AUTOINCREMENT id. Not a rehydration of the pre-pivot table dropped by 002.
- New forward migration `003_artifacts.sql` + paired rollback.
- Docstring in `storage.py` cites the task and the architecture §5 step-8 anchor.
- Protocol-surface test (`test_storage_protocol_only_exposes_the_trimmed_surface`) updated to the nine-method set with a comment explaining the delta from M1.05.

Architecture.md §4.1 describes Storage as "run registry and gate-response log"; §5 step 8 says "Terminal nodes emit artifacts to Storage." The two are reconciled by the new table being a post-gate, schema-less (JSON payload) surface — not a checkpoint-adjacent one. KDR-009 (LangGraph owns checkpoint persistence) remains intact.

No design drift.

## AC grading

| # | Acceptance criterion | Grade | Evidence |
| --- | --- | --- | --- |
| 1 | `build_planner()` returns a builder that compiles against `AsyncSqliteSaver` | ✅ | `test_build_planner_compiles_against_async_sqlite_saver` — opens `AsyncSqliteSaver`, calls `.compile(checkpointer=...)`, asserts non-null app. |
| 2 | Importing `ai_workflows.workflows.planner` registers the builder under `"planner"` | ✅ | Module-level `register("planner", build_planner)` call; `test_importing_planner_registers_builder` verifies after a `_reset_for_tests`. Autouse fixture ensures registration independent of sibling-module resets. |
| 3 | Graph includes two validators (one after explorer, one after planner) per KDR-004 | ✅ | `explorer_validator` (parses `ExplorerReport`) + `planner_validator` (parses `PlannerPlan`); both wrapped with `wrap_with_error_handler`. `test_build_planner_returns_stategraph_with_expected_nodes` pins the exact six-node set including both validators. |
| 4 | All `TieredNode`s wrapped with `wrap_with_error_handler`; all retry decisions go through `retrying_edge` | ✅ | Source in `planner.py:145-186`: `wrap_with_error_handler` around both `tiered_node` calls and both `validator_node` calls. Four `retrying_edge`s bound to conditional edges. |
| 5 | Happy-path test pauses at `HumanGate` and resumes to produce a valid `PlannerPlan` artifact in `Storage` | ✅ | `test_happy_path_pauses_at_gate_then_persists_artifact` — asserts `"__interrupt__" in paused`, `isinstance(paused["plan"], PlannerPlan)`, then resumes with `Command(resume="approved")`, reads the artifact back via `storage.read_artifact("run-happy", "plan")`, and round-trips the JSON through `PlannerPlan.model_validate_json`. |
| 6 | Retry-path test proves the T08 retry loop applies at workflow scope | ✅ | `test_retry_path_bumps_explorer_retry_counter` — script `[RateLimitError, valid_explorer, valid_plan]`; asserts `_retry_counts == {"explorer": 1}`, `_non_retryable_failures == 0`, `last_exception is None` after the successful second pass, and `call_count == 3`. |
| 7 | No `ANTHROPIC_API_KEY` / `anthropic` reference in the module (KDR-003) | ✅ | `test_planner_module_has_no_anthropic_surface` — source-level grep for `import anthropic`, `from anthropic`, `ANTHROPIC_API_KEY`; none present. Docstring mentions KDR-003 by name as a *prohibition* — test matches on surface forms, not substring. |
| 8 | `uv run pytest tests/workflows/test_planner_graph.py` green; `uv run lint-imports` 3 / 3 kept | ✅ | 8 passed in 1.31s; import-linter 3 contracts KEPT, 0 broken. |

## Additions beyond spec — audited and justified

- **`write_artifact` / `read_artifact` also added to the `StorageBackend` protocol** (not just the concrete `SQLiteStorage`). The task spec only specifies "Extend `SQLiteStorage` with…" but a protocol method is what lets `_artifact_node` type-check against `StorageBackend` when the CLI / MCP surface later swaps backends. Zero cost; keeps the protocol honest. Covered by the extended `test_storage_protocol_only_exposes_the_trimmed_surface` assertion.
- **Primitives-level round-trip tests for `write_artifact`** (`test_write_artifact_round_trip`, `test_read_artifact_returns_none_when_absent`, `test_write_artifact_upserts_on_repeat`) — same AC umbrella as AC-5 (artifact persistence), exercised at the storage boundary rather than only through the full graph. No new surface area.
- **Migration-count + table-presence test updates** (`test_first_open_applies_all_migrations`, `test_initialize_is_idempotent`, `test_reconciliation_drops_legacy_tables`) — required by the new 003 migration; the updated assertions keep the intent (legacy surfaces stay dropped; `artifacts` is re-added deliberately).
- **`_RecordingStorage` test helper** in `test_planner_graph.py` — wraps `SQLiteStorage` to count `write_artifact` calls for the rejected-gate contract (AC of the task spec's *Tests* section). Lives entirely in the test module; no production surface change.
- **`workflow: "planner"` in `config["configurable"]`** — optional field that `tiered_node` forwards to the `StructuredLogger` record. Architecture §8.1 lists `workflow` as a required log field; setting it here is conformance, not scope creep.
- **`ExplorerReport` + `PlannerState` added to `__all__`** — standard Python hygiene; matches the public surface T04–T06 CLI tasks will import.
- **Rejected-gate enforcement inside `_artifact_node`** — the task spec says "Picking the exact rejected-response handling is up to the builder." Option taken: keep `gate → artifact → END` as a single linear edge; the artifact node no-ops when the response is not `"approved"`. Documented in the node's docstring.

None extend scope beyond the task file.

## 🔴 HIGH

None.

## 🟡 MEDIUM

None.

## 🟢 LOW

None.

## Deferred to nice_to_have

None.

## Gate summary

| Gate | Result |
| --- | --- |
| `uv run pytest` | ✅ 274 passed, 2 warnings (pre-existing `yoyo` datetime deprecation) in 3.64s |
| `uv run pytest tests/workflows/test_planner_graph.py` | ✅ 8 passed in 1.31s |
| `uv run lint-imports` | ✅ 3 contracts kept, 0 broken (22 files, 24 deps) |
| `uv run ruff check` | ✅ All checks passed |

## Issue log — cross-task follow-up

None. The registered `"planner"` builder + extended Storage surface are stable handles for the M3 CLI tasks:

- [T04 `aiw run`](../task_04_cli_run.md) resolves the builder via `workflows.get("planner")` and invokes under `AsyncSqliteSaver`.
- [T05 `aiw resume`](../task_05_cli_resume.md) rehydrates from the same checkpoint and delivers the gate response via `Command(resume=...)`.
- [T06 `aiw list-runs` / `cost-report`](../task_06_cli_list_cost.md) reads the run registry + cost tracker; the new `artifacts` table is where the plan payload is fetched for the CLI's future `aiw show <run_id>` affordance.

No MEDIUM / LOW findings to propagate.

## Propagation status

No deferrals from this audit — no carry-over entries written to downstream tasks.

---

## Post-M3 amendment (2026-04-20)

The T07 e2e smoke test's live run on 2026-04-20 surfaced a requirement gap in T03's `tiered_node` wiring: neither the explorer nor the planner tier forwarded `output_schema=` to LiteLLM, so Gemini returned free-form / markdown-fenced JSON and `validator_node`'s strict `model_validate_json` parse rejected probabilistically. T03's hermetic tests stubbed the adapter with pre-canned clean JSON, masking the live-path divergence.

Gap closed by [T07a](../task_07a_planner_structured_output.md) — a dedicated, scope-bounded follow-up (two `output_schema=` kwarg additions, test-assertion bumps, `max_transient_attempts` bump 3→5). **Not** a re-open of this audit. T03's audit status line and gate summary above remain the ground truth for what T03 shipped on its own scope; the amendment is documentation of the live-path discovery and its resolution path, for reviewers reading the M3 trail end-to-end. Re-auditing T03 would be incorrect: the live-path convergence gap was a spec-level omission, not a T03 implementation defect.
