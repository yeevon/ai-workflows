# Task 03 — Ollama Fallback `HumanGate` Wiring — Audit Issues

**Source task:** [../task_03_fallback_gate.md](../task_03_fallback_gate.md)
**Audited on:** 2026-04-21
**Audit scope:** task file, milestone README, [ai_workflows/graph/ollama_fallback_gate.py](../../../../ai_workflows/graph/ollama_fallback_gate.py), [ai_workflows/graph/__init__.py](../../../../ai_workflows/graph/__init__.py), [ai_workflows/graph/human_gate.py](../../../../ai_workflows/graph/human_gate.py) (sibling), [ai_workflows/primitives/storage.py](../../../../ai_workflows/primitives/storage.py) (protocol reuse), [tests/graph/test_ollama_fallback_gate.py](../../../../tests/graph/test_ollama_fallback_gate.py), [CHANGELOG.md](../../../../CHANGELOG.md), sibling task specs (T01–T02, T04–T06), [design_docs/architecture.md](../../../architecture.md) (§3, §4.2, §6, §8.3, §8.4, §9 KDR-001 / KDR-009), [task_01_issue.md](task_01_issue.md), [task_02_issue.md](task_02_issue.md).
**Status:** ✅ PASS — Cycle 1/10. All 8 ACs satisfied; no design drift; gates green (565 passed, 4 skipped; 4 contracts kept; ruff clean).

## Design-drift check

Cross-referenced against [architecture.md](../../../architecture.md):

- **Layering (§3, §4.2).** Module lives in `ai_workflows/graph/`. Imports: `logging`, `collections.abc`, `enum`, `typing`, `structlog`, `langchain_core.runnables.RunnableConfig`, `langgraph.types.interrupt`. No edges into `workflows/` or surfaces; `primitives` contract untouched (only the `StorageBackend` protocol shape is read out of `config["configurable"]`, keeping primitives → graph layering intact). `lint-imports` reports 4 contracts kept.
- **KDR-001 (LangGraph substrate).** Gate uses `langgraph.types.interrupt` — same substrate `human_gate` uses. No bespoke resume machinery.
- **KDR-004 (validator-after-LLM).** N/A. No LLM call.
- **KDR-009 (SqliteSaver-only checkpointing).** Gate leans on LangGraph's interrupt + checkpointer — no hand-rolled checkpoint writes. `record_gate` / `record_gate_response` is the gate-audit ledger, a separate concern from the checkpoint (same split `human_gate` maintains).
- **Storage protocol reuse (AC-5).** `record_gate(run_id, gate_id, prompt, strict_review=True)` + `record_gate_response(run_id, gate_id, decision.value)` — existing M1-T05 surface. No new primitive, no migration.
- **Strict review (§8.3).** Gate always passes `strict_review=True`; payload hardcodes `timeout_s=None` and `default_response_on_timeout=None`. Test `test_gate_is_strict_review` pins the payload shape.
- **State-key contract.** `_ollama_fallback_reason`, `_ollama_fallback_count`, and the canonical `ollama_fallback_decision` key are exported as module-level constants (`FALLBACK_DECISION_STATE_KEY`) so T04 writers + T05 tests share the vocabulary without stringly-typed re-invention.
- **Dependencies (§6).** No new runtime dependency.
- **Observability.** Logs via `structlog.get_logger("ai_workflows.graph.ollama_fallback_gate")`; WARN on unknown response. Also emits a stdlib `logging` WARN so `caplog` captures it in standard pytest fashion (see *Additions beyond spec*). Nothing external.

**Verdict:** no drift.

## AC grading table

| # | AC | Status | Evidence |
| --- | --- | --- | --- |
| 1 | `from ai_workflows.graph import build_ollama_fallback_gate, FallbackChoice` works | ✅ PASS | [`graph/__init__.py:19-24`](../../../../ai_workflows/graph/__init__.py#L19-L24) re-exports both; test imports at [L20](../../../../tests/graph/test_ollama_fallback_gate.py#L20). |
| 2 | Gate built with `strict_review=True`, no timeout fires under any code path | ✅ PASS | [`ollama_fallback_gate.py:168-175`](../../../../ai_workflows/graph/ollama_fallback_gate.py#L168-L175) hardcodes `strict_review=True`, `timeout_s=None`, `default_response_on_timeout=None`. `test_gate_is_strict_review` asserts all three on the captured interrupt payload. |
| 3 | `FallbackChoice` has exactly three members: RETRY, FALLBACK, ABORT | ✅ PASS | `StrEnum` at [`ollama_fallback_gate.py:75-80`](../../../../ai_workflows/graph/ollama_fallback_gate.py#L75-L80); verified by `test_response_parses_canonical_values` parametrisation covering all three. |
| 4 | Unknown responses parse to RETRY with WARN, never raise / abort | ✅ PASS | `parse_fallback_choice` returns `FallbackChoice.RETRY` on no-match branch, emits structlog + stdlib WARN. `test_unknown_response_defaults_to_retry` + `test_unknown_resume_produces_retry_decision` cover both parse-path and full graph-run paths. |
| 5 | Gate persistence goes through `StorageBackend.record_gate` / `record_gate_response` — no new primitive/migration | ✅ PASS | Direct calls to those two protocol methods only. `test_gate_persists_via_storage_protocol` asserts one call to each with exact tuple shape (`FALLBACK_GATE_ID`, enum `.value`). No storage schema changes. |
| 6 | Every listed test passes | ✅ PASS | 12 tests green in 0.11s. 5 spec tests + 2 parametrisation expansions + 1 bonus `test_unknown_resume_produces_retry_decision`. |
| 7 | `uv run lint-imports` — 4 contracts kept | ✅ PASS | `Contracts: 4 kept, 0 broken.` |
| 8 | `uv run ruff check` clean | ✅ PASS | `All checks passed!` |

## 🔴 HIGH

None.

## 🟡 MEDIUM

None.

## 🟢 LOW

None.

## Additions beyond spec — audited and justified

- **`parse_fallback_choice`, `render_ollama_fallback_prompt` exposed at module scope.** Spec sketches them as inner-helpers inside `build_ollama_fallback_gate`. Exposing them as module-level functions lets the test suite hit them directly (spec AC-test `test_gate_prompt_renders_tier_reason_and_fallback` needs a callable prompt_fn to assert on) without reaching into closure internals. Zero coupling cost; private names remain pinned to this module via `__all__`.
- **`FALLBACK_GATE_ID` + `FALLBACK_DECISION_STATE_KEY` module constants.** Spec text calls out these contract strings. Lifting them to module constants prevents the T04 planner/slice_refactor wiring and T05 tests from re-hardcoding the magic string. Additive, documented in the docstring.
- **Dual logging (structlog + stdlib) for the WARN on unknown response.** Structlog captures the event into the JSON node-record stream; stdlib `logging.getLogger(__name__).warning(...)` makes the record visible to pytest's `caplog` fixture (which only sees stdlib loggers). This is a pragmatic bridge — the canonical sink is still structlog, the stdlib warning is a test-observability accommodation. Alternative would have been a custom structlog-to-caplog processor, which is higher risk than the one-line stdlib echo. Justified.
- **`test_unknown_resume_produces_retry_decision`** — bonus end-to-end test covering the unknown-resume path through the full gate (not just the parser). Complements the spec's parser-level `test_unknown_response_defaults_to_retry`. Ensures the persisted `record_gate_response` row carries the *enum* value, not the user's raw typo.

## Gate summary

| Gate | Result |
| --- | --- |
| `uv run pytest tests/graph/test_ollama_fallback_gate.py` | ✅ 12 passed in 0.11s |
| `uv run pytest` (full suite) | ✅ 565 passed, 4 skipped in 15.59s |
| `uv run lint-imports` | ✅ 4 contracts kept, 0 broken |
| `uv run ruff check` | ✅ All checks passed |
| CHANGELOG updated | ✅ `[Unreleased]` entry above T02 |
| Docstring discipline | ✅ Module docstring cites M8 T03 + every public class/function documented |

## Issue log

None.

## Deferred to nice_to_have

None.

## Propagation status

No forward deferrals from this audit. T04–T06 carry-over sections remain empty.
