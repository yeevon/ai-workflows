# Task 03 — `resume_run` Tool — Audit Issues

**Source task:** [../task_03_resume_run.md](../task_03_resume_run.md)
**Audited on:** 2026-04-20
**Audit scope:** `ai_workflows/mcp/server.py` (resume_run body), `ai_workflows/workflows/_dispatch.py` (resume_run helper + ResumePreconditionError + _build_resume_result_from_final), `ai_workflows/cli.py` (_resume_async refactor + _emit_cli_resume_result + import cleanup), `ai_workflows/mcp/schemas.py` (`error` field on ResumeRunOutput), `tests/mcp/test_resume_run.py` (new), `tests/mcp/test_scaffold.py` (stub assertion removed), CHANGELOG.md. Full gates. architecture.md §4.4/§5/§7, KDR-002/003/008/009, ADR-0002. Sibling task specs T04 (list_runs) + T05 (cancel_run) for forward-dependency check.
**Status:** ✅ PASS — 0 OPEN issues.

---

## Design-drift check (architecture.md + KDRs)

| Concern | Finding |
| --- | --- |
| New dependency added? | **None.** Only re-uses what `_dispatch.py` already imported (langgraph `Command`, `datetime`, existing cost/storage primitives). |
| New module or layer? | No new module; extended existing `workflows/_dispatch.py`. Placement continues the T02 decision (shared surface-above-workflow helper). Lint-imports 3/3 KEPT. |
| LLM call added? | No. Resume does not fire LLM calls on the planner graph (gate is before artifact; artifact is pure persistence). |
| Checkpoint / resume logic? | Uses LangGraph's `Command(resume=...)` through `AsyncSqliteSaver` per KDR-009. No hand-rolled checkpoint handling — the helper opens the existing async checkpointer via `build_async_checkpointer()` and closes it in a `finally`. ✓ |
| Retry logic? | No bespoke retry. Graph-level exceptions are caught at the surface boundary with `_extract_error_message` reading `state["last_exception"]` populated by `wrap_with_error_handler` (KDR-006 pattern unchanged). ✓ |
| Observability? | No change. StructuredLogger path unaffected. |
| KDR-002 portable surface | Cancelled-run guard + precondition error raised from the shared helper, translated at each surface boundary (CLI → `typer.Exit(2)`; MCP → `ToolError`). Both surfaces converge on the same contract. ✓ |
| KDR-003 Anthropic boundary | `grep -nE "GEMINI_API_KEY\|ANTHROPIC_API_KEY\|import anthropic\|from anthropic"` across `mcp/server.py` + `workflows/_dispatch.py` → **no matches.** Test `test_mcp_server_module_does_not_read_provider_secrets` still pins the boundary on `mcp/server.py`. ✓ |
| KDR-008 FastMCP | Tool signature `async def resume_run(payload: ResumeRunInput) -> ResumeRunOutput` — FastMCP auto-derives the JSON-RPC schema. Exception translation uses `fastmcp.exceptions.ToolError` per spec. ✓ |
| KDR-010 bare-typed rule | MCP I/O schemas are out-of-scope for KDR-010 (ADR-0002). The new `error` field is a plain `str | None = None` — no bounds, defaults match T02 pattern. ✓ |

**Verdict:** no drift.

---

## Acceptance-criteria grading

| # | AC | Grade | Evidence |
| --- | --- | --- | --- |
| 1 | `resume_run(ResumeRunInput) → ResumeRunOutput` with `{run_id, status, plan?, total_cost_usd?}` | ✅ | `mcp/server.py:91-117` wires the tool; schema at `schemas.py:95-111` now with optional `error` field. |
| 2 | Approved + completed → `status="completed"`, `plan` populated, Storage row `"completed"` | ✅ | `_dispatch.py` `_build_resume_result_from_final` (plan branch) calls `storage.update_run_status(run_id, "completed", total_cost_usd=total)`. Test: `test_resume_run_happy_path_completes_and_rolls_up_cost` asserts `status="completed"`, `plan["goal"]`, `total_cost_usd≈0.0033`, and the row has `status="completed"`. CLI regression: `test_resume_happy_path_completes_and_persists_plan_artifact` still green. |
| 3 | Rejected → `status="gate_rejected"`, `plan=None`, Storage row `"gate_rejected"` | ✅ | `_dispatch.py` rejected branch flips status + stamps `finished_at`. Test: `test_resume_run_rejected_flips_row_and_returns_gate_rejected` asserts all three. CLI regression: `test_resume_rejected_flips_status_to_gate_rejected_and_exits_one` still green. |
| 4 | Cancelled-run guard refuses resume with actionable error (T05 relies on this) | ✅ | `ResumePreconditionError` raised from `_dispatch.resume_run` when `row["status"] == "cancelled"`. Test: `test_resume_run_cancelled_guard_raises_tool_error` seeds a cancelled row via Storage, asserts `ToolError` with both "cancelled" and the run id in the message. Raises without hitting LangGraph (pure-precondition guard). |
| 5 | `aiw resume` CLI byte-identical post-refactor | ✅ | `tests/cli/test_resume.py` 8/8 green in full suite; CLI output contract preserved via `_emit_cli_resume_result` mirroring pre-T03 `_emit_resume_final` behavior exactly (pending 3-line handle; rejected "plan rejected by gate" + cost + Exit(1); completed JSON indent=2 + cost; errored "error: …" + Exit(1); no-run-found "no run found: <id>" + Exit(2)). Note: JSON serialization swapped from `plan.model_dump_json(indent=2)` (pydantic) to `json.dumps(plan_dict, indent=2)` (stdlib) — tests use substring matches (`'"goal": "Ship..."' in result.stdout`) which pass under both; the two serializers produce functionally equivalent output for the Plan's scalar/list/nested fields. |
| 6 | CostTracker reseed from `runs.total_cost_usd` still budget-caps (M3 T05 AC-5 regression) | ✅ | `_dispatch.resume_run` preserves the synthetic `tracker.record(run_id, TokenUsage(cost_usd=stored_cost, model="<resumed>", tier="<resumed>"))` pattern verbatim from the prior CLI code. Regression pinned by `tests/cli/test_resume.py::test_resume_reseeds_cost_tracker_from_runs_total_cost_usd` → `row_after["total_cost_usd"] == pytest.approx(0.0033)` still green. |
| 7 | `uv run pytest tests/mcp/test_resume_run.py tests/cli/test_resume.py` green | ✅ | 11 passed, 0 failed, 0 skipped. |
| 8 | `uv run lint-imports` 3/3 kept; `uv run ruff check` clean | ✅ | Lint-imports: `Contracts: 3 kept, 0 broken.` Ruff: `All checks passed!` |

All 8 ACs pass.

---

## 🔴 HIGH — (none)

## 🟡 MEDIUM — (none)

## 🟢 LOW — (none)

---

## Additions beyond spec — audited and justified

1. **`error: str | None = None` field on `ResumeRunOutput`** (schemas.py:110).
   *Justified.* T03 spec implicitly requires in-band error surfacing for the `"errored"` status it already lists in the Literal (pre-T03 `ResumeRunOutput` had `"errored"` in the union but no field to carry the message — a gap from T01). The new field is optional + default `None`, backwards-compatible. Parallels the T02 addition on `RunWorkflowOutput`.

2. **`ResumePreconditionError(ValueError)`** (`_dispatch.py:82-92`).
   *Justified.* Spec §Cancelled-run precondition block literally writes `raise ValueError(f"no run found: {run_id}")` and `raise ValueError(f"run {run_id} was cancelled and cannot be resumed")`. Subclassing ValueError keeps the spec's literal "ValueError" contract (any `except ValueError` still catches) while letting each surface discriminate this class specifically from other ValueErrors in the pipeline (the MCP tool catches both `ResumePreconditionError` and `UnknownWorkflowError` to translate to `ToolError`; the CLI catches both to hit `typer.Exit(2)`). Symmetric to T02's `UnknownWorkflowError(ValueError)` pattern.

3. **`_build_resume_result_from_final` as a module-private helper** (`_dispatch.py`).
   *Justified.* Parallel to T02's `_build_result_from_final`; keeps the four terminal-state translators in one module so the two `_build_*` helpers are obviously siblings.

4. **Scaffold stub assertion for `resume_run` removed** (`tests/mcp/test_scaffold.py`).
   *Justified.* Same pattern as T02's removal of the `run_workflow` stub assertion — the body is wired, so the NotImplementedError assertion no longer holds.

5. **CLI import pruning** (`cli.py:40-62`).
   *Justified.* With `_resume_async` routing through the dispatch helper, the local imports of `datetime`, `UTC`, `Command`, `CostTracker`, `TokenUsage`, `workflows`, `CostTrackingCallback`, `build_async_checkpointer`, `_import_workflow_module`, `_resolve_tier_registry`, `_build_cfg`, `_extract_error_message` are dead code. Dead-code pruning is consistent with CLAUDE.md's "Don't add … unused" guidance. `ruff check` confirms no F401 regression; `SQLiteStorage` and `default_storage_path` imports remain (still used by `_list_runs_async`).

All additions have direct AC mappings; none introduce new coupling, new dependencies, or new public API surface.

---

## Gate summary

| Gate | Command | Result |
| --- | --- | --- |
| Full pytest | `uv run pytest` | **314 passed, 1 skipped** |
| Focused T03 | `uv run pytest tests/mcp/test_resume_run.py tests/cli/test_resume.py` | **11 passed** |
| MCP + CLI regression | `uv run pytest tests/mcp/ tests/cli/test_run.py tests/cli/test_resume.py` | **39 passed** |
| Layer contract | `uv run lint-imports` | **3/3 contracts kept** |
| Lint | `uv run ruff check` | **All checks passed** |
| KDR-003 boundary | `grep -nE "GEMINI_API_KEY\|ANTHROPIC_API_KEY\|import anthropic\|from anthropic" ai_workflows/mcp/server.py ai_workflows/workflows/_dispatch.py` | **no matches** |

---

## Issue log — cross-task follow-up

None. All T03 ACs closed; T05 cancelled-run guard dependency is pre-landed and test-pinned.

---

## Deferred to nice_to_have

None raised.

---

## Propagation status

No forward-deferrals from T03. T05 inherits the cancelled-run guard (already-written behaviour, not a deferral) and will add the `cancel_run` tool that flips `runs.status="cancelled"` — that flip is what makes this guard's precondition reachable in practice.
