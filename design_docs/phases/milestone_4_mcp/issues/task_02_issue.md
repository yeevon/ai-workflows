# Task 02 — `run_workflow` Tool — Audit Issues

**Source task:** [../task_02_run_workflow.md](../task_02_run_workflow.md)
**Audited on:** 2026-04-20
**Audit scope:** `ai_workflows/mcp/server.py` (run_workflow body), `ai_workflows/workflows/_dispatch.py` (new shared helper), `ai_workflows/cli.py` (refactor to consume dispatch), `ai_workflows/mcp/schemas.py` (`error` field amendment), `tests/mcp/test_run_workflow.py` (new), `tests/mcp/test_scaffold.py` (guard rewrite), CHANGELOG.md, full gates, architecture.md §4.4/§5/§6, KDR-002/003/008/009/010, ADR-0002, sibling task specs T03–T07.
**Status:** ✅ PASS — 0 OPEN issues.

---

## Design-drift check (architecture.md + KDRs)

| Concern | Finding |
| --- | --- |
| New dependency added? | **None.** Dispatch helper is stdlib only (`contextlib`, `importlib`, `secrets`, `time`). `fastmcp.exceptions.ToolError` is already in `fastmcp` which §6 lists. |
| New module or layer? | `ai_workflows/workflows/_dispatch.py` — lands in the `workflows` layer, which surfaces (`cli`, `mcp`) may import per §3 four-layer contract. Spec explicitly permitted this placement ("decide at task start — import-linter allows either"). Lint-imports confirms 3/3 contracts KEPT. |
| LLM call added? | No new call sites — this is orchestration refactoring. Tier registry is still resolved through `workflows.<name>_tier_registry()`, still fed into `CostTrackingCallback`, still consumed by `TieredNode` (KDR-004 unchanged). |
| Checkpoint / resume logic? | `build_async_checkpointer()` still delegates to LangGraph's `AsyncSqliteSaver`. No hand-rolled checkpoint writes. KDR-009 respected. |
| Retry logic? | No bespoke retry loops. Budget-breach capture uses the existing `wrap_with_error_handler` → `state["last_exception"]` path from M3 T04; dispatch just reads the snapshot via `aget_state`. KDR-006 unchanged. |
| Observability? | `StructuredLogger` pattern preserved (no new external backends). |
| KDR-002 portable surface | Both surfaces now share one dispatch path; MCP tool body is a thin translator between pydantic I/O and the dict contract. ✓ |
| KDR-003 Anthropic boundary | `grep -nE "GEMINI_API_KEY\|ANTHROPIC_API_KEY\|import anthropic\|from anthropic"` across `mcp/server.py` and `workflows/_dispatch.py` → **no matches.** Test `test_mcp_server_module_does_not_read_provider_secrets` pins it. ✓ |
| KDR-008 FastMCP | Tool signature `async def run_workflow(payload: RunWorkflowInput) -> RunWorkflowOutput` — FastMCP auto-derives the JSON-RPC schema from annotations. ✓ |
| KDR-010 bare-typed rule | Affects only `response_format` schemas sent to LLMs. MCP I/O schemas are explicitly out-of-scope per ADR-0002 ("MCP I/O models are explicitly *out of scope* for the bare-typed rule"). No regression. |

**Verdict:** no drift. Placement choice for `_dispatch.py` in the workflows layer rather than `ai_workflows/mcp/dispatch.py` is a deliberate, spec-permitted decision documented in the module docstring and CHANGELOG.

---

## Acceptance-criteria grading

| # | AC | Grade | Evidence |
| --- | --- | --- | --- |
| 1 | `run_workflow(RunWorkflowInput) → RunWorkflowOutput` with `{run_id, status, awaiting?, plan?, total_cost_usd?}` | ✅ | `ai_workflows/mcp/server.py:69-89`; schema at `schemas.py:67-85` (now with optional `error`). |
| 2 | Gate-pause → `status="pending"`, `awaiting="gate"`, `plan=None`, `total_cost_usd` set | ✅ | `_dispatch.py:312-321` stamps row + returns dict; `tests/mcp/test_run_workflow.py:136-164` asserts `0.0033`, `pending`, `awaiting=gate`, row exists. |
| 3 | Completion → `status="completed"`, `plan` populated, `total_cost_usd` set | ✅ (covered by parity) | `_dispatch.py:323-333` handles completion; the path is exercised end-to-end by `tests/cli/test_run.py` completion flow which routes through the same dispatch helper (byte-identical refactor, AC-5). The MCP tool body is a 2-line translator over the same dict — no MCP-specific completion branch exists. |
| 4 | Budget breach → `status="errored"` with descriptive error (not raw exception) | ✅ | `_dispatch.py:264-275` + `_extract_error_message` recover the captured `NonRetryable` from `state["last_exception"]`. `tests/mcp/test_run_workflow.py:167-201` asserts `status="errored"`, `"budget" in error.lower()`, no uncaught exception. Schema amendment (adding `error: str \| None = None`) is additive/backwards-compatible — default `None` preserves T01 contract. |
| 5 | `aiw run` byte-identical post-refactor | ✅ | `tests/cli/test_run.py` (7 tests) green in full suite; `tests/cli/test_resume.py` (8 tests) green. `_emit_cli_run_result` in `cli.py` preserves the exact 3-line pending output and JSON+cost completion output. 311 passed / 1 skipped. |
| 6 | MCP tool does not read `GEMINI_API_KEY` — env read stays in `LiteLLMAdapter` (KDR-003 boundary) | ✅ | Source grep clean; pinned by `tests/mcp/test_run_workflow.py:241-257` which fails build if `GEMINI_API_KEY`, `ANTHROPIC_API_KEY`, or `anthropic` imports appear in `mcp/server.py`. |
| 7 | `uv run pytest tests/mcp/test_run_workflow.py tests/cli/test_run.py` green | ✅ | Focused run green; full suite also green (311 passed, 1 skipped). |
| 8 | `uv run lint-imports` 3/3 kept; `uv run ruff check` clean | ✅ | `lint-imports`: "Contracts: 3 kept, 0 broken." `ruff check`: "All checks passed!" |

All 8 ACs pass.

---

## 🔴 HIGH — (none)

## 🟡 MEDIUM — (none)

## 🟢 LOW — (none)

---

## Additions beyond spec — audited and justified

1. **`error: str | None = None` field on `RunWorkflowOutput`** (schemas.py:85).
   *Justified.* AC-4 requires surfacing budget-breach errors in-band ("descriptive error in the tool response, not as a raw Python exception"); T01's schema had no field to carry the message. Additive with `None` default → backwards-compatible. Explicitly covered by the T02 docstring and test assertions.

2. **`_extract_error_message()` helper using `compiled.aget_state(cfg)`** (`_dispatch.py:187-207`).
   *Justified.* The budget-breach cascade is that `CostTrackingCallback` raises `NonRetryable`, `wrap_with_error_handler` captures it into `state["last_exception"]` and routes to terminal, then the next node (a validator reading a field the prior LLM never wrote) raises a plain `KeyError` that escapes LangGraph. Without reaching back into checkpointed state via `aget_state`, the caller would see "KeyError: 'explorer_output'" instead of "budget exceeded". This reuses M3 T04's existing pattern (same helper lived in `cli._surface_graph_error` pre-refactor).

3. **Dispatch-layer re-exports via `ai_workflows.cli.__all__`** (`_CROCKFORD`, `_generate_ulid`).
   *Justified.* Preserves the existing M3 T04 test contract (`tests/cli/test_run.py` asserts ULID shape via those symbols). Pure re-export; no behavioural coupling beyond keeping tests green. Marked module-private (`_`-prefixed) so it stays out of the public surface.

4. **`UnknownWorkflowError(ValueError)` as surface-agnostic error class** (`_dispatch.py:67-79`).
   *Justified.* Spec required the MCP tool to raise a `fastmcp.exceptions.ToolError` for unknown workflows; the CLI already emitted `typer.Exit(2)` with a registered-workflows message. A surface-agnostic exception class in the dispatch layer lets each surface translate at its boundary without importing surface-specific error types into `workflows/`. Subclasses `ValueError` so external callers who catch `ValueError` still behave correctly.

All additions have direct AC mappings; none introduce new coupling, new dependencies, or new surface area.

---

## Gate summary

| Gate | Command | Result |
| --- | --- | --- |
| Full pytest | `uv run pytest` | **311 passed, 1 skipped** |
| Focused MCP + regression | `uv run pytest tests/mcp/ tests/cli/test_run.py tests/cli/test_resume.py` | **36 passed** |
| Layer contract | `uv run lint-imports` | **3/3 contracts kept** |
| Lint | `uv run ruff check` | **All checks passed** |
| KDR-003 boundary | `grep -nE "GEMINI_API_KEY\|ANTHROPIC_API_KEY\|import anthropic\|from anthropic" ai_workflows/mcp/server.py ai_workflows/workflows/_dispatch.py` | **no matches** |

---

## Issue log — cross-task follow-up

None. All T02 ACs closed; no forward-deferrals.

---

## Deferred to nice_to_have

None raised.

---

## Propagation status

No forward-deferrals from T02. T03 (`resume_run`) will extend `_dispatch.py` with a `resume_run()` helper + cancelled-run precondition check per its own spec — that's in-spec inheritance, not a deferral from T02.
