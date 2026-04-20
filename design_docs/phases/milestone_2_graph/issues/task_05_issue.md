# Task 05 — HumanGate Adapter — Audit Issues

**Source task:** [../task_05_human_gate.md](../task_05_human_gate.md)
**Audited on:** 2026-04-19
**Audit scope:** `ai_workflows/graph/human_gate.py`, `tests/graph/test_human_gate.py`, `CHANGELOG.md` unreleased entry, cross-checked against [architecture.md §3 / §4.2 / §8.3](../../../architecture.md) and KDR-001 / KDR-009. Sibling tasks T03 (config-injection pattern) and T04 (validator_node) reviewed for contract alignment. M1 Task 05 (`StorageBackend.record_gate` / `record_gate_response`) and `migrations/002_reconciliation.sql` re-verified as the persistence substrate.
**Status:** ✅ PASS on T05's explicit ACs (AC-1..AC-4 all met, no OPEN issues).

## Design-drift check

| Axis | Verdict | Evidence |
| --- | --- | --- |
| New dependency | None | No new entries in [pyproject.toml](../../../../pyproject.toml). Module imports only `langchain_core.runnables.RunnableConfig` (installed transitively by LangGraph, already declared in M1) and `langgraph.types.interrupt` (already declared). |
| Four-layer contract | KEPT | `import-linter` reports 3 / 3 contracts kept, 0 broken (16 files / 7 deps analyzed). New module lives in `ai_workflows.graph`; imports are LangGraph runtime types only — no `workflows` / `cli` / `mcp` reach-up. |
| LLM call present? | No | Zero `litellm` / subprocess / `CostTracker` / `TokenUsage` imports. `grep` clean on `anthropic` and `ANTHROPIC_API_KEY`. This is a human-gate node, never an LLM node (KDR-004 doesn't apply — nothing to validate after). |
| KDR-001 compliance | Met | Gate pause + resume delegates entirely to `langgraph.types.interrupt` + `Command(resume=...)`. No hand-rolled `await_event` / futures / asyncio.Event plumbing. |
| KDR-009 compliance | Met | Node writes nothing to the checkpoint; that remains LangGraph's `SqliteSaver`'s job. `Storage` writes are only to the M1 Task 05 gate-log surface. Tests use `MemorySaver` (real saver smoke is T08's scope per AC-3). |
| Checkpoint / resume logic | None | No `SqliteSaver` / `MemorySaver` used inside the production module — tests wire one explicitly. |
| Retry logic | None | No try/except around `interrupt`. Three-bucket taxonomy untouched. |
| Observability | None | No `StructuredLogger` wired in (architecture §8.3 does not require gate logging here; the gate row itself is the audit trail via `Storage`). No Langfuse / OTel / LangSmith creep. |
| Secrets | None read | Module reads nothing from env. |
| `nice_to_have.md` adoption | None | No items pulled in. |

No drift. Task passes the design-drift gate.

## AC grading

| AC | Verdict | Evidence |
| --- | --- | --- |
| AC-1 — Gate prompt and response round-trip through `Storage` | ✅ | [ai_workflows/graph/human_gate.py:104](../../../../ai_workflows/graph/human_gate.py#L104) calls `record_gate(run_id, gate_id, prompt, strict_review)` before `interrupt`; [L117](../../../../ai_workflows/graph/human_gate.py#L117) calls `record_gate_response(run_id, gate_id, response)` after resume. Asserted by stub-storage [test_gate_round_trips_prompt_and_response_through_storage](../../../../tests/graph/test_human_gate.py#L71-L88) **and** real-schema [test_full_sqlite_storage_round_trip](../../../../tests/graph/test_human_gate.py#L204-L227) — the latter confirms the `gate_responses` row holds both prompt and response at the end. |
| AC-2 — `strict_review=True` disables timeout enforcement | ✅ | [ai_workflows/graph/human_gate.py:110-113](../../../../ai_workflows/graph/human_gate.py#L110-L113) forces `timeout_s` + `default_response_on_timeout` to `None` in the interrupt payload when `strict_review=True`. Architecture §4.2 / §8.3 delegate the enforcement to the surface layer; this node refuses to encode any enforceable value. Asserted by [test_strict_review_zeros_out_timeout_in_interrupt_payload](../../../../tests/graph/test_human_gate.py#L107-L133) (passes `timeout_s=1` — would be near-immediate if honored — and pins both fields as `None`). Complementary [test_non_strict_review_forwards_timeout_fields](../../../../tests/graph/test_human_gate.py#L136-L161) pins the inverse so the zeroing is proven conditional. |
| AC-3 — Node integrates with a LangGraph `StateGraph` checkpointed by `SqliteSaver` (T08 covers the smoke test) | ✅ | Node is a vanilla async `(state, config) -> dict` — registered via `g.add_node("gate", node)` in every test ([tests/graph/test_human_gate.py:62-68](../../../../tests/graph/test_human_gate.py#L62-L68)). Pause + resume through `MemorySaver` round-trips correctly. AC defers the `SqliteSaver` smoke to M2 Task 08, so `MemorySaver` is the right substrate here. |
| AC-4 — `uv run pytest tests/graph/test_human_gate.py` green | ✅ | 7 / 7 passed in 0.17s. Full suite: 184 passed in 2.61s. |

## 🔴 HIGH

None.

## 🟡 MEDIUM

None.

## 🟢 LOW

None.

## Additions beyond spec — audited and justified

1. **Two tests beyond the spec's four** (spec lists: `interrupt` once, `record_gate` preserves flag, resumption writes response, strict-review ignores timeout).
   - **`test_non_strict_review_forwards_timeout_fields`** pins the inverse of the strict-review payload test. Without it, a regression that always zeros the timeout fields would pass AC-2 while silently breaking the non-strict path.
   - **`test_full_sqlite_storage_round_trip`** replaces the stub with a real `SQLiteStorage` so AC-1 is pinned against the live M1 Task 05 schema — catches divergence between the stub's positional signature and the real SQL column order / upsert.
   Both tests exercise existing production behaviour. No new code paths were introduced to satisfy them.
2. **Interrupt payload includes `gate_id`, `timeout_s`, `default_response_on_timeout` in addition to `prompt`.** Spec says "Invokes `langgraph.interrupt()` with the prompt payload." A bare `prompt` string would leave the surface with no way to enforce the timeout policy that architecture §8.3 assigns to it. Including the factory's configurable knobs in the payload is the mechanism by which the surface learns whether / how long to wait. No behavioural change vs. a prompt-only payload — just more information on the same wire.
3. **`run_id` + `storage` resolution sites (spec gap, not a deviation).** Spec signature omits both; the node must get them from somewhere.
   - `run_id ← state["run_id"]` — state is the natural carrier of run identity; M3 workflow schemas will include it.
   - `storage ← config["configurable"]["storage"]` — mirrors the "injected via LangGraph config (no module-level globals)" pattern called out in [../task_03_tiered_node.md](../task_03_tiered_node.md). Keeps the node stateless and backend-swap-friendly.
   Surfaced in the CHANGELOG entry so M3 workflow authors see the contract. No drift.

## Gate summary

| Gate | Result |
| --- | --- |
| `uv run pytest` | ✅ 184 passed, 2 warnings (pre-existing `yoyo` datetime deprecation inside `SQLiteStorage.open`, unrelated to T05) in 2.61s |
| `uv run lint-imports` | ✅ 3 contracts kept, 0 broken (16 files, 7 deps analyzed) |
| `uv run ruff check` | ✅ All checks passed! |

## Issue log — cross-task follow-up

None. No deferrals; no cross-task findings.

## Deferred to nice_to_have

None.

## Propagation status

Not applicable. Task closed clean with no forward-deferred items.
