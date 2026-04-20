# Task 05 — `cancel_run` Tool (Storage-Level) — Audit Issues

**Source task:** [../task_05_cancel_run.md](../task_05_cancel_run.md)
**Audited on:** 2026-04-20
**Audit scope:** `ai_workflows/primitives/storage.py` (new `cancel_run` on `StorageBackend` protocol + `SQLiteStorage` implementation), `ai_workflows/mcp/server.py` (cancel_run body wired), `ai_workflows/workflows/_dispatch.py` (cancelled-run precondition guard — T03-shipped, T05-relied-on), `tests/mcp/test_cancel_run.py` (new), `tests/primitives/test_storage.py` (new unit tests + protocol-surface pin), `tests/mcp/test_scaffold.py` (stub assertion removed), `CHANGELOG.md`. Full gates (`uv run pytest`, `uv run lint-imports`, `uv run ruff check`). Cross-referenced against `architecture.md §3` (layer contract), `§4.4` (MCP tools), `§8.7` (cancellation M4/M6 split), KDR-002, KDR-008, KDR-009, M4 README, T03 issue file, `tests/mcp/test_resume_run.py` (cancelled-run guard parity).
**Status:** ✅ PASS — 0 OPEN issues.

---

## Design-drift check (architecture.md + KDRs)

| Concern | Finding |
| --- | --- |
| New dependency added? | **None.** Uses stdlib `sqlite3`, `asyncio`, `typing.Literal` (already imported in the module). |
| New module or layer? | No. New method on an existing primitives-layer class. Surfaces-layer `mcp.server` imports `primitives.storage` — allowed by the four-layer contract (§3). Lint-imports 3/3 KEPT. |
| LLM call added? | **No.** `cancel_run` is a pure storage flip — never compiles a graph, never instantiates a `TieredNode`, never calls an adapter. KDR-004 inapplicable. |
| Checkpoint / resume logic? | **No.** Tool touches only the `runs` registry table. The checkpointer DB (`checkpoints.sqlite`) is never opened. KDR-009 unaffected — no hand-rolled checkpoint writes. |
| Retry logic? | No. |
| Observability? | No change. |
| KDR-002 portable surface | `cancel_run` exposes the same cancel semantics at both CLI and MCP surfaces at the contract level; M4 MCP is the only live surface today (no `aiw cancel` CLI shipped — none required by M3 / M4 scope). The storage primitive is surface-agnostic. ✓ |
| KDR-003 Anthropic boundary | No provider imports added. `grep -E "ANTHROPIC_API_KEY\|GEMINI_API_KEY\|import anthropic\|from anthropic" ai_workflows/mcp/server.py` → **0 matches**. Pinned by the existing `tests/mcp/test_run_workflow.py::test_mcp_server_module_does_not_read_provider_secrets` module-scan test. ✓ |
| KDR-008 FastMCP | Tool signature `async def cancel_run(payload: CancelRunInput) -> CancelRunOutput` — FastMCP auto-derives the JSON-RPC schema from the pydantic annotations. Unknown-id failure surfaces as `ToolError` (JSON-RPC error response), not an uncaught exception. ✓ |
| KDR-009 LangGraph SqliteSaver | **Not invoked.** `cancel_run` is a registry-table write only; it never opens `build_async_checkpointer`, never touches the `checkpoints` DB, never writes to LangGraph's state. ✓ |
| KDR-010 bare-typed rule | MCP I/O models are out-of-scope (ADR-0002). `CancelRunOutput.status: Literal["cancelled", "already_terminal"]` is the boundary-contract Literal, not a `response_format`. ✓ |
| **architecture.md §8.7 — M4 / M6 split** | ✓ **Critical check — honoured.** `grep` for `durability="sync"`, `task.cancel(`, `asyncio.Task` across `ai_workflows/` → **no matches in code** (only doc strings citing the M6 deferral). The M6-owned in-flight path is explicitly documented in three places (tool docstring, storage docstring, CHANGELOG) without being implemented. No subgraph / ToolNode guards added. |
| M4 README scope | Tool #4 of 4 landed; completes the four-tool surface listed in the README scope block (line 8) and the tasks table (line 42). ✓ |

**Verdict:** no drift. The M4 / M6 cancellation split is the single most audit-sensitive concern for this task, and it is cleanly respected.

---

## Acceptance-criteria grading

| # | AC | Grade | Evidence |
| --- | --- | --- | --- |
| 1 | `cancel_run(CancelRunInput)` returns `CancelRunOutput` with `status ∈ {"cancelled", "already_terminal"}` | ✅ | [schemas.py:154-165](../../../../ai_workflows/mcp/schemas.py#L154-L165) pins the `Literal["cancelled", "already_terminal"]`; [server.py:141-162](../../../../ai_workflows/mcp/server.py#L141-L162) constructs the output from `storage.cancel_run`. Tests `test_cancel_run_flips_pending_row_to_cancelled` + `test_cancel_run_on_terminal_row_is_noop` + `test_cancel_run_second_call_is_already_terminal` exercise both variants. |
| 2 | Storage row flip: `status='cancelled'` + `finished_at` set; no other fields mutated | ✅ | [storage.py:420-435](../../../../ai_workflows/primitives/storage.py#L420-L435): UPDATE touches `status` + `finished_at` only. `test_cancel_run_on_terminal_row_is_noop` pins the **no side effect** half: on a terminal row, `finished_at == pre_finished_at` (the UPDATE's `AND status='pending'` clause makes rowcount 0 — nothing is mutated). `test_cancel_run_flips_pending_row_to_cancelled` asserts the positive half: `status="cancelled"` + `finished_at is not None` after a flip. |
| 3 | Idempotent: two calls return `"cancelled"` then `"already_terminal"` | ✅ | `test_cancel_run_second_call_is_already_terminal` (MCP-level) + `test_cancel_run_idempotent_second_call_is_already_terminal` (Storage unit) both pin the sequence. |
| 4 | `resume_run` refuses a cancelled run (T03 guard exercised end-to-end) | ✅ | T03 guard at [_dispatch.py:405-408](../../../../ai_workflows/workflows/_dispatch.py#L405-L408) (pre-existing, T03-shipped). End-to-end exercise: `test_cancel_then_resume_is_refused` drives `run_workflow → cancel_run → resume_run` and asserts the ToolError message contains both "cancelled" and the run id. This is the M4-kickoff promise made to T03 (see T03 issue ISS-NONE — guard shipped with T03 specifically so T05 could close this loop). |
| 5 | No LangGraph task cancellation, no `durability="sync"` change, no subgraph / ToolNode handling — that path is M6's | ✅ | Verified by two paths: (a) full-repo grep for `durability.*sync`, `task.cancel(`, `asyncio.Task` — **0 code matches**, only docstrings and CHANGELOG lines citing the M6 deferral; (b) source inspection of `cancel_run` — opens storage, issues one pre-check SELECT + one conditional UPDATE, returns. No checkpointer touch, no task registry, no graph compile. |
| 6 | `uv run pytest tests/mcp/test_cancel_run.py tests/primitives/test_storage.py` green | ✅ | **38 passed** (5 new MCP + 4 new Storage-unit + 29 existing Storage). |
| 7 | `uv run lint-imports` 3 / 3 kept; `uv run ruff check` clean | ✅ | Lint-imports: `Contracts: 3 kept, 0 broken.` Ruff: `All checks passed!` |

All 7 ACs pass.

---

## 🔴 HIGH — (none)

## 🟡 MEDIUM — (none)

## 🟢 LOW — (none)

---

## Additions beyond spec — audited and justified

1. **Pre-check SELECT guards unknown run ids** ([storage.py:423-428](../../../../ai_workflows/primitives/storage.py#L423-L428)). *Justified.* Spec §Deliverables is explicit: "Raises if `run_id` does not exist". A plain conditional UPDATE can't distinguish "unknown id" from "id exists but not pending" (both rowcount 0); the pre-check is the minimum viable way to surface the unknown-id error as a `ValueError` → `ToolError`. Pinned by `test_cancel_run_raises_on_unknown_run_id` + `test_cancel_run_unknown_run_id_raises_tool_error`.

2. **Inlined `asyncio.Lock` + `asyncio.to_thread`** in `cancel_run` rather than routing through the base `_run_write` helper. *Justified.* Looked at the existing `_run_write` (lines 313-329): it returns `None`. `cancel_run` needs to surface the `Literal["cancelled", "already_terminal"]` result to the caller. Two minimal-impact options: (a) overload `_run_write` to preserve return types (wider refactor, crosses other call sites); (b) inline the two-line `async with self._write_lock: return await asyncio.to_thread(...)` pattern. Option (b) was chosen — contained to this method, same lock semantics, no regression risk for sibling writers. Docstring at [storage.py:413-415](../../../../ai_workflows/primitives/storage.py#L413-L415) calls out the choice so future refactors have context.

3. **`cancel_run` added to `test_storage_protocol_only_exposes_the_trimmed_surface` expected set**. *Justified.* Keeps the protocol-surface pin accurate — omitting the new method would silently loosen what the test guards. Same pattern the test uses for every other method on `StorageBackend`.

4. **Scaffold stub assertion removed** (`tests/mcp/test_scaffold.py`). *Justified.* Identical pattern to T02 / T03 / T04 — body is wired, so the NotImplementedError assertion no longer holds.

5. **`CancelRunOutput.run_id`** — returned in the response (spec snippet shows only `status`, but the pre-M4 schema definition at [schemas.py:163-165](../../../../ai_workflows/mcp/schemas.py#L163-L165) has both). *Justified.* Schema-first contract set at T01; the T05 body uses the field exactly as defined. Not an addition beyond spec — a carry-forward from the T01 scaffold schema.

No other additions. No new dependencies, no new modules, no new public API beyond what the spec's deliverable snippet names.

---

## Gate summary

| Gate | Command | Result |
| --- | --- | --- |
| Full pytest | `uv run pytest` | **328 passed, 1 skipped** |
| Focused T05 | `uv run pytest tests/mcp/test_cancel_run.py tests/primitives/test_storage.py` | **38 passed** |
| Layer contract | `uv run lint-imports` | **3 / 3 contracts kept** |
| Lint | `uv run ruff check` | **All checks passed** |
| KDR-003 boundary | `grep -nE "ANTHROPIC_API_KEY\|GEMINI_API_KEY\|import anthropic\|from anthropic" ai_workflows/mcp/server.py` | **no matches** |
| §8.7 M4 / M6 split | `grep -nE "durability.*sync\|task\.cancel\(\|asyncio\.Task" ai_workflows/` | **no code matches** (only docstrings referencing the M6 deferral) |

---

## Issue log — cross-task follow-up

None. T05 ACs are all closed and the M6 deferral is pre-existing (tracked in [architecture.md §8.7](../../../../design_docs/architecture.md) and the M6 README, not raised by this audit).

---

## Deferred to nice_to_have

None raised.

---

## Propagation status

No forward-deferrals from T05. The dependent M6-T02 in-flight-cancellation work is already scoped in `architecture.md §8.7` + the M6 milestone README — no new carry-over entry needed (the split was planned, not discovered by this audit).
