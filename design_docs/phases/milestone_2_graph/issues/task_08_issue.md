# Task 08 — SqliteSaver Binding + Smoke Graph — Audit Issues

**Source task:** [../task_08_checkpointer.md](../task_08_checkpointer.md)
**Audited on:** 2026-04-19
**Audit scope:** `ai_workflows/graph/checkpointer.py` (155 LoC), `ai_workflows/graph/error_handler.py` (158 LoC, carry-over M2-T07-ISS-01), `tests/graph/test_checkpointer.py` (8 tests), `tests/graph/test_error_handler.py` (10 tests), `tests/graph/test_smoke_graph.py` (5 tests), `CHANGELOG.md` `[Unreleased]` entry, `design_docs/phases/milestone_2_graph/task_08_checkpointer.md` (including the M2-T07-ISS-01 carry-over). Cross-checked against [architecture.md §3 / §4.1 / §4.2 / §6 / §8.2 / §8.3](../../../architecture.md), KDR-003, KDR-004, KDR-006, KDR-009. Sibling modules re-read: `graph/tiered_node.py` (T03), `graph/validator_node.py` (T04), `graph/human_gate.py` (T05), `graph/cost_callback.py` (T06), `graph/retrying_edge.py` (T07), `primitives/storage.py`, `primitives/retry.py`. Sibling issue files re-verified: [task_03_issue.md](task_03_issue.md) (option (b) confirmation + remainder allocation), [task_07_issue.md](task_07_issue.md) (M2-T07-ISS-01 origin). `pyproject.toml` and `.github/workflows/ci.yml` consulted for dependency + CI-gate alignment.
**Status:** ✅ PASS on T08's explicit ACs (AC-1..AC-5 all met) and on the M2-T07-ISS-01 carry-over (end-to-end retry loop pinned). No OPEN issues. Two additions beyond spec (`build_async_checkpointer` sibling factory + `wrap_with_error_handler` module) audited and justified below.

## Design-drift check

| Axis | Verdict | Evidence |
| --- | --- | --- |
| New dependency | None (direct) | No new entries in [pyproject.toml](../../../../pyproject.toml). `checkpointer.py` imports `aiosqlite` and `langgraph.checkpoint.sqlite.{SqliteSaver, aio.AsyncSqliteSaver}`; both ship inside `langgraph-checkpoint-sqlite>=1.0` which is already an explicit dep (listed as "Required-by: langgraph-checkpoint-sqlite" for `aiosqlite` via `uv pip show`). `error_handler.py` imports `langchain_core.runnables.RunnableConfig` — same import already landed in [graph/human_gate.py](../../../../ai_workflows/graph/human_gate.py#L41) (T05) without audit concern, and `langchain_core` is a first-order transitive of `langgraph`. No items from [design_docs/nice_to_have.md](../../../../design_docs/nice_to_have.md) adopted. |
| Four-layer contract | KEPT | `import-linter` reports 3 / 3 contracts kept, 0 broken (21 files / 17 deps analyzed). `checkpointer.py` imports only stdlib (`os`, `sqlite3`, `pathlib`) + `aiosqlite` + `langgraph.checkpoint.sqlite`. `error_handler.py` imports stdlib + `langchain_core` + `ai_workflows.primitives.retry`. No upward imports. |
| LLM call added? | No (in T08 modules) | Smoke test stubs `LiteLLMAdapter` at the module-level monkeypatch site — no real API traffic. `checkpointer.py` / `error_handler.py` are zero-LLM modules. |
| KDR-003 compliance | Met | `grep -i "anthropic\|ANTHROPIC_API_KEY"` on T08 modules → 0 matches. |
| KDR-004 compliance | Met (demonstrated end-to-end) | Smoke graph wires `llm (TieredNode) → validator (ValidatorNode) → gate (HumanGate) → END`, exactly the KDR-004 pairing. [tests/graph/test_smoke_graph.py:180-223](../../../../tests/graph/test_smoke_graph.py#L180-L223). |
| KDR-006 compliance | Met | `wrap_with_error_handler` catches exactly the three buckets (`RetryableTransient` / `RetryableSemantic` / `NonRetryable`) and writes them into state for `RetryingEdge` to observe — this is the "wrapper error handler" option (b) that T07's audit explicitly authorised ("If T03's builder picked option (b) (wrapper error handler) the wrapper belongs here"). No bespoke retry loop, no `asyncio.sleep`, no `for … range(n)`. Other exception types propagate ([test_wrapper_does_not_trap_unclassified_exceptions](../../../../tests/graph/test_error_handler.py#L150-L157)). |
| KDR-009 compliance | Met | `checkpointer.py` is a thin factory around LangGraph-owned savers. Zero hand-rolled checkpoint writes, zero custom serialiser, zero `yoyo` migration. `SqliteSaver.setup()` / `AsyncSqliteSaver.setup()` own the schema. [test_checkpointer_db_is_separate_from_storage_db](../../../../tests/graph/test_checkpointer.py#L113-L140) pins the "separate from Storage" invariant (KDR-009 §4.1): distinct paths, distinct connections, `sqlite_master` probe confirms the checkpointer owns the `checkpoints` table on its own file. |
| Checkpoint / resume logic | All LangGraph-native | Resume flow exercised by [test_smoke_graph_resumes_after_interrupt_and_completes](../../../../tests/graph/test_smoke_graph.py#L292-L316) — `ainvoke` on `Command(resume="approved")` rehydrates from the checkpoint and finishes. No custom checkpoint writes anywhere. |
| Retry logic | Bucket catch → state update; routing by edge | `wrap_with_error_handler` is the "raise → state" bridge the T07 edge needs; it delegates the routing decision to `retrying_edge` unchanged. No bespoke budget accounting at the wrapper layer (per-node counter bump + `NonRetryable` failure bump are the shape T07 names; nothing more). |
| Observability | `StructuredLogger` only (via T03, unchanged) | T08 modules emit no log records themselves — structured logging rides the wrapped `tiered_node`. `grep -i "langfuse\|opentelemetry\|langsmith"` on T08 modules → 0 matches. |
| Secrets | None read | `checkpointer.py` reads `AIW_CHECKPOINT_DB` env var only — a path override, not a secret. `error_handler.py` reads no env vars. |
| `nice_to_have.md` adoption | None | No items pulled in. |

No drift. Task passes the design-drift gate.

## AC grading

| AC | Verdict | Evidence |
| --- | --- | --- |
| AC-1 — Checkpointer DB file created at the expected path | ✅ | Explicit arg path: [test_custom_path_honoured](../../../../tests/graph/test_checkpointer.py#L36-L46) asserts the DB exists at `tmp_path / "custom" / "checkpoints.sqlite"` and that the factory returns an actual `SqliteSaver`. Env override: [test_env_var_override_honoured](../../../../tests/graph/test_checkpointer.py#L49-L62). Explicit beats env: [test_explicit_path_beats_env_var](../../../../tests/graph/test_checkpointer.py#L65-L79). Default under `~/.ai-workflows/`: [test_default_path_resolves_under_user_home](../../../../tests/graph/test_checkpointer.py#L82-L92). `~` expansion: [test_tilde_expansion_in_custom_path](../../../../tests/graph/test_checkpointer.py#L160-L166). Precedence order (explicit > env > default) matches the module docstring at [checkpointer.py:93-98](../../../../ai_workflows/graph/checkpointer.py#L93-L98). |
| AC-2 — Checkpointer DB separate from Storage DB on disk (KDR-009) | ✅ | [test_checkpointer_db_is_separate_from_storage_db](../../../../tests/graph/test_checkpointer.py#L113-L140) creates a pre-existing Storage file, builds a checkpointer at a distinct path, asserts `storage_path.resolve() != checkpoint_path.resolve()`, and probes `sqlite_master` on the checkpointer connection to confirm it owns the `checkpoints` table — so a silent regression that unified the two files (aliasing KDR-009 away) would either create the wrong tables on Storage or fail to find the probe row. Matches architecture.md §4.1 ("`Storage` keeps the run registry and gate log; LangGraph owns checkpoint persistence"). |
| AC-3 — Smoke graph runs to interrupt, checkpoints, resumes cleanly | ✅ | [test_smoke_graph_runs_to_interrupt_and_checkpoints](../../../../tests/graph/test_smoke_graph.py#L253-L289) asserts (a) `"__interrupt__"` present in the paused state (LangGraph surface for an active `interrupt()`), (b) the on-disk checkpoint file exists at the requested path, (c) a row exists in the `checkpoints` table matching the run's `thread_id` — probed via a bare `sqlite3.connect` so we verify LangGraph actually persisted to disk rather than inferring from the saver's in-memory state, (d) the validator ran before the gate so the parsed `Answer` is on the paused state (KDR-004 structural sanity). [test_smoke_graph_resumes_after_interrupt_and_completes](../../../../tests/graph/test_smoke_graph.py#L292-L316) pins the resume half: `Command(resume="approved")` rehydrates from the checkpoint, the gate persists `{review: approved}` to Storage, and the final state carries both `gate_review_response="approved"` and the validated answer. |
| AC-4 — `CostTracker` totals reflect the smoke run | ✅ | [test_smoke_graph_cost_tracker_totals_non_zero](../../../../tests/graph/test_smoke_graph.py#L319-L336) asserts `tracker.total("run-cost") > 0` **and** equals `pytest.approx(0.0017)` — the exact value returned by the stub. Equality (not just `> 0`) catches silent drift where the callback fires multiple times, fires on the wrong run, or loses precision. |
| AC-5 — Scoped pytest command green | ✅ | `uv run pytest tests/graph/test_smoke_graph.py tests/graph/test_checkpointer.py` — 13 / 13 passed (5 smoke + 8 checkpointer). Full suite: 236 / 236 in 3.22s. |
| **Carry-over M2-T07-ISS-01 (task-file tick-box)** | ✅ | Landed via `ai_workflows/graph/error_handler.py`. Wrapper contract pinned unit-level by all 10 tests in [test_error_handler.py](../../../../tests/graph/test_error_handler.py) (exact dict shape for each bucket, non-mutation of incoming state, config forwarding, unclassified exceptions propagate). End-to-end proof in [test_transient_retry_routes_correctly_and_clears_on_success](../../../../tests/graph/test_smoke_graph.py#L344-L392): a `litellm.RateLimitError` on the first LLM call raises → wrapper writes `last_exception` + bumps `_retry_counts['llm']` → `retrying_edge` routes back to `llm` → the successful second call returns `last_exception=None` via T03's "clear on success" path → `retrying_edge` forwards to `validator` → `gate` → END. Budget exhaustion pinned by [test_exhausted_transient_budget_routes_to_on_terminal](../../../../tests/graph/test_smoke_graph.py#L395-L429) — LLM calls capped at `max_transient_attempts = 3`. |

## 🔴 HIGH

None.

## 🟡 MEDIUM

None.

## 🟢 LOW

None.

## Additions beyond spec — audited and justified

1. **`build_async_checkpointer(db_path) -> AsyncSqliteSaver` sibling factory** ([checkpointer.py:117-132](../../../../ai_workflows/graph/checkpointer.py#L117-L132)). The task spec names only one factory (`build_checkpointer(db_path) -> SqliteSaver`), and my sync factory preserves that signature *exactly*. The async variant is a genuine necessity, not scope creep: every M2 node adapter (`tiered_node`, `validator_node`, `human_gate`) is `async def`, so the smoke graph must invoke via `.ainvoke`. LangGraph's sync `SqliteSaver` raises `NotImplementedError: The SqliteSaver does not support async methods` when handed to an `ainvoke` path (verified empirically while building AC-3 tests; see CHANGELOG "Deviations from spec"). Both factories are concrete siblings from the same `langgraph-checkpoint-sqlite` package already listed in architecture.md §6 — not a new backend, not a schema fork. They share `resolve_checkpoint_path` + `_prepare_path` so the "default under `~/.ai-workflows/`, `AIW_CHECKPOINT_DB` overrides, parent dir created lazily" rules land exactly once ([checkpointer.py:135-154](../../../../ai_workflows/graph/checkpointer.py#L135-L154)). The sync factory is still wired into the spec-named AC tests; the async factory is what the smoke graph uses. Pinned by [test_applied_to_plain_stategraph_compiles_without_error](../../../../tests/graph/test_checkpointer.py#L95-L110) (sync variant in a sync graph) + all 5 smoke tests (async variant in an async graph).

2. **`resolve_checkpoint_path(db_path) -> Path` exposed at module level.** Separated from the factories so tests (and future callers inspecting "where will this write?") can check path resolution without opening a connection — matters because opening `AsyncSqliteSaver` mid-test without `await`ing its close is awkward. The function encodes the precedence rule in one place, cited from both factories + `_prepare_path` ([checkpointer.py:150-154](../../../../ai_workflows/graph/checkpointer.py#L150-L154)), and pinned by [test_default_path_resolves_under_user_home](../../../../tests/graph/test_checkpointer.py#L82-L92) + [test_tilde_expansion_in_custom_path](../../../../tests/graph/test_checkpointer.py#L160-L166). No new surface area vs. hiding it inside the factories — it just makes the rule observable.

3. **`wrap_with_error_handler(node, *, node_name)` module + 10 unit tests.** Explicitly assigned to T08 by M2-T07-ISS-01 (quoted in the T07 issue: *"M2 Task 08 per the deferred issue … wraps the node with a small LangGraph-native error handler that converts the raised bucket into the same state update"*). The exact state-update shape `{last_exception, _retry_counts, _non_retryable_failures}` ([error_handler.py:135-157](../../../../ai_workflows/graph/error_handler.py#L135-L157)) is the shape the T07 audit named. Centralising it in one module (vs. inlining in each workflow) lands the "concrete template the T07 audit asked T08 to surface for M3 workflow authors to copy" requirement from the same carry-over. Signature introspection ([error_handler.py:114-132](../../../../ai_workflows/graph/error_handler.py#L114-L132)) lets the wrapper cover both `tiered_node`'s `(state, config)` shape and `validator_node`'s `(state)` shape without mutation at either site — pinned by [test_wrapper_forwards_config_when_node_accepts_it](../../../../tests/graph/test_error_handler.py#L114-L120) + [test_wrapper_skips_config_when_node_rejects_it](../../../../tests/graph/test_error_handler.py#L123-L129). State non-mutation pinned by [test_wrapper_does_not_mutate_incoming_state](../../../../tests/graph/test_error_handler.py#L132-L147) — matters because LangGraph checkpoint snapshots may be shared references.

4. **`error_handler.py` omits `from __future__ import annotations`** (every other `graph/` module includes it). This is deliberate and documented in the CHANGELOG "Deviations from spec". LangGraph auto-detects whether a node takes `config: RunnableConfig | None` by *evaluating* the type annotation, not by string-matching its repr; `from __future__ import annotations` stringifies annotations at import time and defeats the detection (empirically: LangGraph warns `UserWarning: The 'config' parameter should be typed as 'RunnableConfig' or 'RunnableConfig | None', not 'RunnableConfig | None'` — identical strings, failed type comparison — and silently refuses to pass the config dict; AC-3 fails because `tier_registry` shows up as `None` inside `tiered_node`). Dropping the future import on this one module keeps the wrapper's runtime type real, which is what LangGraph needs. Body still uses `RunnableConfig | None` syntax (Python 3.10+ evaluates it at runtime when not deferred). No ruff complaint once `UP007` / `UP045` fixups landed.

5. **Test file `test_smoke_graph.py` runs under `asyncio_mode = "auto"` (pyproject `tool.pytest.ini_options`).** Smoke tests are `async def` because `AsyncSqliteSaver.conn.close()` is awaitable and `ainvoke` is the only path that routes through the async nodes. This re-uses the config already established by M1 T01; no new pytest plugin needed.

6. **Stub adapter pattern in `_StubLiteLLMAdapter`.** Class-level `script` list of `Exception | (text, cost)` entries popped in order, installed via `monkeypatch.setattr(tiered_node_module, "LiteLLMAdapter", _StubLiteLLMAdapter)`. Keeps the smoke graph hermetic (no real API hits, no network, no rate-limit timing) while still exercising the real `tiered_node` classification + cost-callback + structured-log paths. Autouse fixture `_reset_stub` clears the script on every test so one test's leftover budget cannot pollute another. Matches the T03 test style already audited clean in [task_03_issue.md](task_03_issue.md).

## Gate summary

| Gate | Result |
| --- | --- |
| `uv run pytest` | ✅ 236 passed, 2 warnings (pre-existing `yoyo` datetime deprecation inside `SQLiteStorage.open`, unrelated to T08) in 3.22s |
| `uv run pytest tests/graph/test_smoke_graph.py tests/graph/test_checkpointer.py` (AC-5 scoped command) | ✅ 13 / 13 passed |
| `uv run pytest tests/graph/test_error_handler.py` (carry-over) | ✅ 10 / 10 passed |
| `uv run lint-imports` | ✅ 3 contracts kept, 0 broken (21 files, 17 deps analyzed) |
| `uv run ruff check` | ✅ All checks passed! |
| KDR-003 grep (`anthropic` / `ANTHROPIC_API_KEY` on T08 modules) | ✅ 0 matches |
| KDR-009 grep (`yoyo` / hand-rolled `CREATE TABLE checkpoints` on T08 modules) | ✅ 0 matches — schema owned by LangGraph saver's `.setup()` |
| Observability-backend grep (`langfuse` / `opentelemetry` / `langsmith` on T08 modules) | ✅ 0 matches |
| `nice_to_have.md` item grep on T08 modules | ✅ 0 matches |

## Issue log — cross-task follow-up

**M2-T07-ISS-01 — RESOLVED (T08 audit, 2026-04-19)**
Originally deferred from T07's audit to T03 (option (b)) + T08 (wrapper + smoke graph). T03 closed its half in its own audit (option (b) — raise verbatim + clear `last_exception` on success). T08 has now delivered the remaining half:

- `ai_workflows/graph/error_handler.py::wrap_with_error_handler` — catches each of the three buckets and writes the exact state-update shape the T07 issue named: `{"last_exception": exc, "_retry_counts": {**prev, node_name: prev.get(node_name, 0) + 1}, "_non_retryable_failures": prev + 1 if isinstance(exc, NonRetryable) else prev}`.
- Unit-level contract pinned by 10 tests in `tests/graph/test_error_handler.py` (one per bucket + non-mutation + config forwarding + counter preservation + unclassified exceptions propagate).
- End-to-end retry loop pinned by `tests/graph/test_smoke_graph.py::test_transient_retry_routes_correctly_and_clears_on_success` and `test_exhausted_transient_budget_routes_to_on_terminal` — these are the "M3 workflow authors copy this template" tests the T07 audit asked for.

*Propagation:* see the footer.

## Deferred to nice_to_have

None.

## Propagation status

- [task_07_issue.md](task_07_issue.md) — M2-T07-ISS-01 flips DEFERRED → RESOLVED. T08 has closed the last owed piece; T03's audit already closed its half.
- [../task_08_checkpointer.md](../task_08_checkpointer.md) — carry-over `- [x]` ticked inline with a 2026-04-19 landed-at reference.
- No new carry-over forwarded to any future task. T09 (milestone close-out) will inherit the full M2 scope on its own schedule.
