# Task 03 — TieredNode Adapter — Audit Issues

**Source task:** [../task_03_tiered_node.md](../task_03_tiered_node.md)
**Audited on:** 2026-04-19
**Audit scope:** `ai_workflows/graph/tiered_node.py` (392 LoC), `tests/graph/test_tiered_node.py` (555 LoC, 15 tests), `CHANGELOG.md` `[Unreleased]` entry. Cross-checked against [architecture.md §3 / §4.1 / §4.2 / §8.1 / §8.2 / §8.5 / §8.6](../../../architecture.md); KDR-003, KDR-004, KDR-006, KDR-007. Sibling modules re-read: `graph/cost_callback.py` (T06), `graph/retrying_edge.py` (T07), `graph/validator_node.py` (T04), `primitives/llm/litellm_adapter.py` (T01), `primitives/llm/claude_code.py` (T02), `primitives/retry.py`, `primitives/tiers.py`, `primitives/logging.py`. Task 01/Task 02 issue files consulted for upstream contract alignment. T07 issue file (which deferred M2-T07-ISS-01 here as primary owner) re-read in full.
**Status:** ✅ PASS on T03's explicit ACs (AC-1..AC-6 all met, no OPEN issues). T07 carry-over M2-T07-ISS-01 resolved at T03's boundary via option (b); integration-test responsibility remains forward-deferred to T08 per the original issue's own partitioning.

## Design-drift check

| Axis | Verdict | Evidence |
| --- | --- | --- |
| New dependency | None | No new entries in [pyproject.toml](../../../../pyproject.toml). `tiered_node.py` imports only `asyncio` + `time` (stdlib), `structlog`, `pydantic`, and sibling modules (`graph.cost_callback`, `primitives.*`). No new external dep; no `design_docs/nice_to_have.md` item pulled in. |
| Four-layer contract | KEPT | `import-linter` reports 3 / 3 contracts kept, 0 broken (19 files / 16 deps analyzed). New module lives in `ai_workflows.graph` and imports only from `ai_workflows.primitives.*` and `ai_workflows.graph.cost_callback`. No upward imports. |
| LLM call added? | Yes — this IS the LLM-call node | Routes through `LiteLLMAdapter` (KDR-007) for `LiteLLMRoute` and `ClaudeCodeSubprocess` for `ClaudeCodeRoute`. The KDR-004 pairing (validator-after-every-LLM-node) is a graph-construction concern; T04 (`validator_node`) is the paired module and is already implemented. |
| KDR-003 compliance | Met | `grep -i "anthropic\|ANTHROPIC_API_KEY"` on the module → 0 matches. Claude Code path uses `ClaudeCodeSubprocess` which itself is already audit-clean for KDR-003 (Task 02 issue file). |
| KDR-004 compliance | Met (this module is upstream of the pairing) | T03 produces the raw text under `state[f"{node_name}_output"]`; T04's `validator_node(input_key="<node_name>_output", ...)` is the paired parser. The pairing is a graph-assembly choice enforced at workflow build time; T03 cannot enforce it at the adapter layer. |
| KDR-006 compliance | Met | On provider exception the node calls `primitives.retry.classify(exc)` and re-raises the bucket class (`RetryableTransient` or `NonRetryable`). `RetryableSemantic` passes through. No bespoke `for … range(n)` retry loop, no `asyncio.sleep` backoff, no swallow-and-retry inside the node. Retry routing remains T07's job. |
| KDR-007 compliance | Met | LiteLLM is used only via the `LiteLLMAdapter` (which `grep` confirmed already uses `max_retries=0` and classification-free). This module does not import `litellm` directly. |
| KDR-009 compliance | Met | Zero `SqliteSaver` / `MemorySaver` / `checkpoint` references in the module. State updates flow through the node's return dict; persistence is LangGraph's concern. |
| Checkpoint / resume logic | None | No custom checkpoint writes. |
| Retry logic | Classification only | Re-raises bucket-tagged exceptions; no backoff, no attempt counter mutation. |
| Observability | `StructuredLogger` only | `structlog.get_logger(__name__)` at module level; `log_node_event` from `primitives.logging` emits the §8.1 shape. `grep -i "langfuse\|opentelemetry\|langsmith"` → 0 matches. |
| Secrets | None read | Module reads no env vars directly. Provider adapters handle their own secrets at their layer (LiteLLM reads `GEMINI_API_KEY`; Claude Code uses OAuth via CLI). |
| `nice_to_have.md` adoption | None | No items pulled in. |

No drift. Task passes the design-drift gate.

## AC grading

| AC | Verdict | Evidence |
| --- | --- | --- |
| AC-1 — Node is a standard LangGraph node (plain `async def`, takes state, returns dict) | ✅ | Inner function signature is `async def _node(state: GraphState, config: Any = None) -> dict[str, Any]` — the LangGraph convention that lets the runtime inject `RunnableConfig`. Pinned by [test_node_returns_a_dict_with_output_key_keyed_by_node_name](../../../../tests/graph/test_tiered_node.py#L484-L500) (asserts dict return, keyed by `f"{node_name}_output"`). |
| AC-2 — Both provider paths covered by tests | ✅ | LiteLLM path: [test_dispatches_to_litellm_adapter_for_litellm_route](../../../../tests/graph/test_tiered_node.py#L215-L238) asserts `_FakeLiteLLMAdapter.last_instance.route.model == "gemini/gemini-2.5-flash"` and log `provider="litellm"`. Claude Code path: [test_dispatches_to_claude_code_driver_for_claude_code_route](../../../../tests/graph/test_tiered_node.py#L246-L268) asserts `_FakeClaudeCodeAdapter.last_instance.route.cli_model_flag == "sonnet"` and log `provider="claude_code"`. |
| AC-3 — Semaphore respected | ✅ | [test_semaphore_enforces_max_concurrency_one](../../../../tests/graph/test_tiered_node.py#L276-L305) holds the fake adapter inside `complete()` via an `asyncio.Event`, spawns two concurrent node invocations, yields the event loop five times, then asserts `max_concurrent == 1`. Release + `asyncio.gather` confirms both invocations eventually complete. [test_no_semaphore_entry_allows_unbounded_concurrency](../../../../tests/graph/test_tiered_node.py#L308-L326) pins the inverse — absence of a semaphore entry permits concurrent entry — so a future change that silently constructs a unity semaphore would fail loudly. |
| AC-4 — Emits exactly one structured log record per invocation | ✅ | Three tests pin the invariant across three failure modes plus success. Success: [test_emits_exactly_one_structured_log_on_success](../../../../tests/graph/test_tiered_node.py#L334-L357) asserts `len(logs) == 1` with all §8.1 fields populated. Provider failure: [test_emits_exactly_one_structured_log_on_failure](../../../../tests/graph/test_tiered_node.py#L360-L377) — `event="node_failed"`, `log_level="error"`, `bucket="RetryableTransient"`. Budget-cap failure: [test_budget_breach_emits_exactly_one_failure_log_and_raises_non_retryable](../../../../tests/graph/test_tiered_node.py#L416-L447) — same single-log invariant on the `CostTrackingCallback` raise path (§8.5), closed by structuring the `try/except` to enclose both dispatch and cost-record ([tiered_node.py:217-245](../../../../ai_workflows/graph/tiered_node.py#L217-L245)). |
| AC-5 — Emits exactly one `CostTracker.record` call per invocation | ✅ (with documented interpretation) | [test_emits_exactly_one_cost_record_per_successful_invocation](../../../../tests/graph/test_tiered_node.py#L385-L402) asserts `len(tracker._entries["run-1"]) == 1` and that `tier` is stamped on the entry so `CostTracker.by_tier` groups correctly. [test_no_cost_record_on_failed_invocation](../../../../tests/graph/test_tiered_node.py#L405-L413) pins the corollary: a failed provider call records *zero* entries. Interpretation: "per invocation" = "per successful invocation" — a failed call has no `TokenUsage` to record and writing a zero-cost entry would pollute `by_model` / `by_tier` rollups. See additions-beyond-spec §1 for justification. |
| AC-6 — `uv run pytest tests/graph/test_tiered_node.py` green | ✅ | 15 / 15 passed in 0.90s. Full suite: 213 passed in 2.64s. |
| **Carry-over M2-T07-ISS-01** — option (a) OR (b), plus clear `last_exception` on success | ✅ (option (b)) | Node raises the classified bucket verbatim (preserving the task spec's "adapter raises `litellm.RateLimitError` → node raises `RetryableTransient`" test wording): [tiered_node.py:283-291](../../../../ai_workflows/graph/tiered_node.py#L283-L291) dispatches `classify()` → `raise RetryableTransient(str(exc)) from exc` or `raise NonRetryable(str(exc)) from exc`; classification pinned by [test_litellm_rate_limit_error_raises_retryable_transient](../../../../tests/graph/test_tiered_node.py#L454-L467) and [test_litellm_bad_request_error_raises_non_retryable](../../../../tests/graph/test_tiered_node.py#L470-L482). Success path clears stale state: [tiered_node.py:307-310](../../../../ai_workflows/graph/tiered_node.py#L307-L310) returns `{f"{node_name}_output": text, "last_exception": None}`; pinned by [test_success_path_clears_stale_last_exception](../../../../tests/graph/test_tiered_node.py#L490-L504). The state-update wrapper that `RetryingEdge` reads is explicitly owned by M2 Task 08 per the T07 issue's own partitioning ("If T03's builder picked option (b) (wrapper error handler) the wrapper belongs here" in T08). |

## 🔴 HIGH

None.

## 🟡 MEDIUM

None.

## 🟢 LOW

None.

## Additions beyond spec — audited and justified

1. **"Per invocation" interpreted as "per successful invocation" for AC-5.** The spec phrasing "Emits exactly one `CostTracker.record` call per invocation" admits two readings. I picked the "successful invocation" reading because (a) a failed adapter call produces no `TokenUsage` — any record written on the failure path would carry zero input/output/cost and an empty `model`, which pollutes `CostTracker.by_model` and `CostTracker.by_tier`; (b) the spec's own test list ("Dispatch to LiteLLM path … asserts correct provider selected", "Exception classification: adapter raises `RateLimitError` → node raises `RetryableTransient`") never names a "record on failure" expectation; (c) the architecture §8.5 flow ("`CostTracker` checks budget after each node") implies the record fires post-success. The interpretation is pinned by *two* tests — one positive (`test_emits_exactly_one_cost_record_per_successful_invocation`) and one negative (`test_no_cost_record_on_failed_invocation`) — so a future reviewer cannot accidentally flip the contract without failing CI.
2. **Cost callback inside the dispatch `try/except`.** Moved from after the block to inside so a budget-breach `NonRetryable` raised by `CostTracker.check_budget` (§8.5) funnels through the same single-log failure path as a provider exception, preserving AC-4 on the budget-cap path. Pinned by `test_budget_breach_emits_exactly_one_failure_log_and_raises_non_retryable` — without this structural choice the invocation would raise `NonRetryable` with *zero* log records emitted, silently breaking observability on the exact code path §8.5 says should be visible.
3. **Output key convention: `f"{node_name}_output"`.** The spec's numbered pseudo-code lists the provider call / cost record / log emission / classification but does not name the state key the raw text lands under. The paired `validator_node` (T04) spec takes an explicit `input_key`, so some key has to be named by the upstream producer. `f"{node_name}_output"` is derivable from the required `node_name` parameter (so no new parameter), unambiguous per-node, and matches the "keyed by destination node name" idiom T07's retry edge already uses for `_retry_counts`. Alternative (explicit `output_key` param) would add surface area the spec doesn't request.
4. **`TokenUsage.tier` stamped by this node.** Provider adapters (`LiteLLMAdapter`, `ClaudeCodeSubprocess`) do not know the logical tier — they receive a resolved `Route` only. `CostTracker.by_tier` is unusable unless something in the call chain writes the tier label. This node has the tier in scope (the `tier` parameter) and is the last hop before the ledger, so it is the natural owner. Same convention M1 Task 08 established (`TokenUsage.tier` is the field; deviation documented in the T08 CHANGELOG entry) and the T06 callback takes on trust.
5. **Two missing-configurable paths raise `NonRetryable` with a clear message.** `config=None` or a missing required key (`tier_registry` / `cost_callback` / `run_id`) raises `NonRetryable` instead of a raw `KeyError` — configuration errors should fail loud and non-retryable rather than silently loop. Same for an unknown tier name. Pinned by `test_missing_configurable_raises_non_retryable` and `test_unknown_tier_raises_non_retryable`.
6. **Node signature is `async def _node(state, config=None)` rather than `Callable[[GraphState], Awaitable[dict]]`.** The spec's return-type annotation omits `config` from the inner function signature, but the spec body (next paragraph) mandates "Tier registry is injected via LangGraph config (no module-level globals)" — config injection and the state-only signature are mutually exclusive. LangGraph's own runtime introspects node signatures and supplies `config` when the node accepts it; nodes with `(state, config)` are first-class. The only alternative would be module-level globals (forbidden). The spec's type annotation is a minor shorthand, not a load-bearing constraint.

## Gate summary

| Gate | Result |
| --- | --- |
| `uv run pytest` | ✅ 213 passed, 2 warnings (pre-existing `yoyo` datetime deprecation inside `SQLiteStorage.open`, unrelated to T03) in 2.64s |
| `uv run lint-imports` | ✅ 3 contracts kept, 0 broken (19 files, 16 deps analyzed) |
| `uv run ruff check` | ✅ All checks passed! |
| KDR-003 grep (`anthropic` / `ANTHROPIC_API_KEY` on the new module) | ✅ 0 matches |
| Observability-backend grep (`langfuse` / `opentelemetry` / `langsmith` on the new module) | ✅ 0 matches |
| `SqliteSaver` / `MemorySaver` / `checkpoint` grep on the new module | ✅ 0 matches |

## Issue log — cross-task follow-up

**M2-T07-ISS-01 — PARTIALLY RESOLVED at T03 (remainder owned by M2 Task 08)**
*Severity:* observational / non-blocking for T03.

T07's audit flagged that the retry edge's pure `(state) -> str` router cannot observe a raised exception that was never stored; M2-T07-ISS-01 required either (a) T03 catch-and-store, or (b) a wrapper error handler (owned by T08). This audit confirms T03 took **option (b)**:

- T03 raises the classified bucket (`RetryableTransient` / `NonRetryable`) verbatim from provider exceptions, preserving the task spec test wording ("node raises `RetryableTransient`").
- T03 clears `state['last_exception']` on the success path so the edge does not re-fire on stale data.

**Remainder owned by T08:** the "catch-the-raised-bucket and write it into `state['last_exception']` + increment `_retry_counts[node_name]` + bump `_non_retryable_failures` if NonRetryable" wrapper. This is explicitly what the T07 issue assigned to T08: *"If T03's builder picked option (b) (wrapper error handler) the wrapper belongs here"* (quoted from T08's own carry-over section). The T08 spec already carries the M2-T07-ISS-01 carry-over entry with this instruction verbatim.

**Also still relevant:** T04 (`validator_node`, already closed) similarly raises `RetryableSemantic` rather than storing it. The same T08 wrapper must cover that raising site too — T07's issue flagged this as "T04 backfit, minor" and assigned it to T08 as part of the integration smoke-graph wiring. Same propagation mechanism (T08's carry-over already covers this).

*Action / Recommendation:*
- **T03 (this task):** nothing more. Option (b) is complete at this boundary; the raising contract matches the task spec.
- **T08:** implement the error-handler wrapper (one implementation shared by T03 and T04 raising sites). The existing T08 carry-over already specifies the shape: `{"last_exception": exc, "_retry_counts": {**prev, node_name: prev.get(node_name, 0) + 1}, "_non_retryable_failures": prev + 1 if isinstance(exc, NonRetryable) else prev}`. The T08 smoke graph then exercises the full retry loop end-to-end.
- **T07 origin issue:** once T08 lands, the originating T07 issue's DEFERRED entry can flip to RESOLVED.

No new carry-over appended to any task file — the T08 carry-over from T07's audit already covers this work.

## Deferred to nice_to_have

None.

## Propagation status

- [../task_07_retrying_edge.md](../task_07_retrying_edge.md) — no new carry-over (T07 does not own remaining work). Originating issue file ([task_07_issue.md](task_07_issue.md)) will flip M2-T07-ISS-01 to RESOLVED after T08 lands the wrapper.
- [../task_08_checkpointer.md](../task_08_checkpointer.md) — no new carry-over appended (T07's audit already propagated M2-T07-ISS-01 here; that entry covers T03's option-(b) choice exactly).
