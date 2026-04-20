# Task 07 — RetryingEdge — Audit Issues

**Source task:** [../task_07_retrying_edge.md](../task_07_retrying_edge.md)
**Audited on:** 2026-04-19
**Audit scope:** `ai_workflows/graph/retrying_edge.py`, `tests/graph/test_retrying_edge.py`, `CHANGELOG.md` unreleased entry, cross-checked against [architecture.md §3 / §4.2 / §8.2](../../../architecture.md) and KDR-006 / KDR-009. Sibling tasks T03 (`TieredNode` — raising site for the transient bucket, still unimplemented) and T04 (`validator_node` — raising site for the semantic bucket, already implemented) reviewed for upstream contract alignment. M1 Task 07 (`RetryableTransient` / `RetryableSemantic` / `NonRetryable` / `RetryPolicy`) re-verified as the primitives substrate.
**Status:** ✅ PASS on T07's explicit ACs (AC-1..AC-4 all met, no OPEN issues). One observational cross-task concern logged as DEFERRED to M2 T03 — does not block T07.

## Design-drift check

| Axis | Verdict | Evidence |
| --- | --- | --- |
| New dependency | None | No new entries in [pyproject.toml](../../../../pyproject.toml). Module imports only `ai_workflows.primitives.retry.{RetryableSemantic, RetryableTransient, RetryPolicy}`. No LangGraph imports — the edge is a plain `(state) -> str` function usable with `StateGraph.add_conditional_edges` without coupling to a specific LangGraph version surface. |
| Four-layer contract | KEPT | `import-linter` reports 3 / 3 contracts kept, 0 broken (18 files / 9 deps analyzed). New module lives in `ai_workflows.graph` and imports only from `ai_workflows.primitives`. |
| LLM call present? | No | Zero `litellm` / subprocess / anthropic imports. `grep` clean on `ANTHROPIC_API_KEY`, `langfuse`, `opentelemetry`, `langsmith`. This module never invokes a model. |
| KDR-003 compliance | Met | No Anthropic SDK import, no key lookup. |
| KDR-004 compliance | N/A (upstream of boundary) | This edge is the routing surface *between* an LLM node and its validator; not itself an LLM surface. KDR-004 applies to T03+T04 pairing, which this edge simply routes. |
| KDR-006 compliance | Met | Routes by the three-bucket taxonomy exactly (`RetryableTransient` → `on_transient`; `RetryableSemantic` → `on_semantic`; `NonRetryable` / unknown / missing → `on_terminal`). Consumes `RetryPolicy.max_transient_attempts` and `RetryPolicy.max_semantic_attempts` to cap loops. Classification is delegated upstream per spec — this module never calls `classify()` itself. |
| KDR-009 compliance | Met | Pure routing function, no state mutation, no custom checkpoint writes. Counters (`_retry_counts`, `_non_retryable_failures`) live in LangGraph state and ride the `SqliteSaver` the same as any other state key. `test_attempt_counters_are_read_from_state_so_they_survive_resume` pins this by building a fresh closure + fresh state dict to simulate resume. |
| Checkpoint / resume logic | None | No `SqliteSaver` / `MemorySaver` / custom checkpoint writes inside the module. |
| Retry logic | Bucket routing only | No `try`/`except`, no `asyncio.sleep`, no backoff math — spec explicitly scopes backoff to the self-loop target node. No bespoke retry loops in violation of KDR-006. |
| Observability | None | No `StructuredLogger` wired in — spec does not require logging at the edge, and logging belongs on `TieredNode` per T03. No Langfuse / OTel / LangSmith creep. |
| Secrets | None read | Module reads nothing from env. |
| `nice_to_have.md` adoption | None | No items pulled in. |

No drift. Task passes the design-drift gate.

## AC grading

| AC | Verdict | Evidence |
| --- | --- | --- |
| AC-1 — All three buckets routed correctly | ✅ | Transient: [ai_workflows/graph/retrying_edge.py:112-115](../../../../ai_workflows/graph/retrying_edge.py#L112-L115) routes to `on_transient` while `retry_counts[on_transient] < max_transient_attempts`, else `on_terminal`. Pinned by [test_transient_routes_to_on_transient_until_max_then_terminal](../../../../tests/graph/test_retrying_edge.py#L48-L64) (iterates counts 0..2 → transient; count=3 → terminal). Semantic: [ai_workflows/graph/retrying_edge.py:117-120](../../../../ai_workflows/graph/retrying_edge.py#L117-L120) mirrors the structure; pinned by [test_semantic_routes_to_on_semantic_and_preserves_revision_hint](../../../../tests/graph/test_retrying_edge.py#L67-L77) (hint preserved on the exception instance) and [test_semantic_exhaustion_routes_to_terminal](../../../../tests/graph/test_retrying_edge.py#L80-L89). Non-retryable: [ai_workflows/graph/retrying_edge.py:122](../../../../ai_workflows/graph/retrying_edge.py#L122) falls through to `on_terminal`; pinned by [test_non_retryable_routes_to_terminal](../../../../tests/graph/test_retrying_edge.py#L92-L96). |
| AC-2 — Attempt counters live in state (durable across checkpoint resume) | ✅ | Edge is a pure `(state) -> str` function; the closure stores only factory args, not counters. All counter reads flow through `_retry_counts(state)` ([ai_workflows/graph/retrying_edge.py:127-132](../../../../ai_workflows/graph/retrying_edge.py#L127-L132)) and `_non_retryable_failures(state)` ([L135-137](../../../../ai_workflows/graph/retrying_edge.py#L135-L137)). [test_attempt_counters_are_read_from_state_so_they_survive_resume](../../../../tests/graph/test_retrying_edge.py#L115-L139) simulates a resume by building a **fresh** edge closure against a fresh state dict carrying the pre-pause counter values and asserts the decision depends solely on those values — if any counter were hiding in the closure, this test would diverge. |
| AC-3 — Double-failure hard-stop covered by a test | ✅ | [ai_workflows/graph/retrying_edge.py:103-104](../../../../ai_workflows/graph/retrying_edge.py#L103-L104) checks `_non_retryable_failures(state) >= 2` **before** bucket dispatch; pinned by [test_double_non_retryable_failure_forces_terminal_even_for_transient](../../../../tests/graph/test_retrying_edge.py#L99-L112) which stages a `RetryableTransient` exception (would normally self-loop) alongside `_non_retryable_failures=2` and asserts the edge returns `on_terminal`. The "regardless of sibling state" requirement from §8.2 is honoured by the unconditional precedence of this check over every bucket dispatch. |
| AC-4 — `uv run pytest tests/graph/test_retrying_edge.py` green | ✅ | 9 / 9 passed in 0.80s. Full suite: 198 passed in 2.72s. |

## 🔴 HIGH

None.

## 🟡 MEDIUM

None.

## 🟢 LOW

None.

## Additions beyond spec — audited and justified

1. **Five tests beyond the spec's four** (spec lists: transient exhaustion, semantic exhaustion + hint preservation, non-retryable, double-failure).
   - **`test_semantic_routes_to_on_semantic_and_preserves_revision_hint`** explicitly checks `state['last_exception'] is exc` and `.revision_hint == hint` — forces the "pure routing, no mutation" invariant into the test suite so a future change that inadvertently copies / normalises the exception will fail loudly.
   - **`test_attempt_counters_are_read_from_state_so_they_survive_resume`** simulates a resume by building a fresh closure against a fresh state dict. Without it, AC-2 would only be observed indirectly through the transient/semantic tests; this pins the contract head-on.
   - **`test_missing_last_exception_defensively_routes_to_terminal`** covers the spec gap "what does the edge do if `state['last_exception']` is absent?" Routing to `on_terminal` is the safe default — a silent self-loop would be a worse failure mode, and LangGraph conditional edges must always return a destination.
   - **`test_unknown_exception_type_is_treated_as_terminal`** pins the "anything not listed → NonRetryable" philosophy from `primitives.retry.classify` into the edge as well; protects against a future bucket being added and accidentally routing through the "fall-through" path.
   - **`test_distinct_on_transient_and_on_semantic_destinations_are_respected`** pins the contract that `_retry_counts` is keyed by **destination node name** (not by bucket), so callers who route each bucket to a different node get independent counters. Also demonstrates that the common `on_transient == on_semantic` case (self-loop same LLM node) intentionally shares the counter — a single retry budget for the node, not per-bucket budgets.
   All additional tests exercise existing production behaviour — no new code paths were introduced to satisfy them.
2. **Defensive routing for `last_exception is None` and unknown exception types.** Spec's docstring focuses on the happy path (bucket classification). Production needs an answer for the "not-an-exception" case — my choice of `on_terminal` over raising mirrors `primitives.retry.classify`'s "anything not listed → NonRetryable" default and never silently self-loops.
3. **`_retry_counts` / `_non_retryable_failures` helpers.** Two one-line private functions that normalise missing / `None` state values to empty-dict / zero. Kept as helpers rather than inline so the `_edge` body reads top-to-bottom as pure routing logic. No behavioural change vs. inline `or {}` / `or 0`.

## Gate summary

| Gate | Result |
| --- | --- |
| `uv run pytest` | ✅ 198 passed, 2 warnings (pre-existing `yoyo` datetime deprecation inside `SQLiteStorage.open`, unrelated to T07) in 2.72s |
| `uv run lint-imports` | ✅ 3 contracts kept, 0 broken (18 files, 9 deps analyzed) |
| `uv run ruff check` | ✅ All checks passed! |

## Issue log — cross-task follow-up

**M2-T07-ISS-01 — RESOLVED (2026-04-19 via M2 Task 03 option (b) + M2 Task 08 wrapper + smoke graph)**
*Severity:* observational / non-blocking for T07. Closed in two halves: T03 chose option (b) (raise verbatim; clear `last_exception` on success — see [task_03_issue.md](task_03_issue.md)); T08 delivered `ai_workflows/graph/error_handler.py::wrap_with_error_handler` and wired it into the smoke graph end-to-end (see [task_08_issue.md](task_08_issue.md)). Both halves are pinned by tests.
T07 reads three keys from graph state: `last_exception` (instance), `_retry_counts` (dict[str, int] keyed by destination node name), and `_non_retryable_failures` (int). None of these are currently written anywhere in the codebase — T04 (`validator_node`, already implemented) **raises** `RetryableSemantic` directly rather than writing it into state, and T03 (`tiered_node`, still planned) has spec text saying "the typed exception propagates so `RetryingEdge` can route" — which is architecturally incomplete: a pure `(state) -> str` edge cannot observe a raised exception that was never stored. The integration contract needs explicit resolution at the raising sites so the edge actually has data to route on.

*Action / Recommendation:*
- **T03 (builder):** on exception, either (a) catch-and-store pattern — catch the typed bucket, write `{"last_exception": exc, "_retry_counts": {...+1}, "_non_retryable_failures": ...+1 if NonRetryable else same}` into state via the node's return dict, or (b) wrap the node with a small LangGraph-native error handler that converts the raised bucket into the same state update. The T03 spec's "does not swallow exceptions" posture needs to be reconciled with T07's state-read contract before T08's smoke graph can exercise the retry loop end-to-end.
- **T04 (backfit, minor):** same pattern needs to be applied to `validator_node` before the first concrete workflow uses it — either in a follow-up task or as part of T08's wiring. No code change needed in T07.
- **T08 (smoke graph):** must wire T03 + T04 + T07 together in a trivial graph that exercises the full retry loop; surface the counter-increment pattern here so M3 workflow authors have a concrete template.

*Propagation:* carry-over appended to [../task_03_tiered_node.md](../task_03_tiered_node.md) and [../task_08_checkpointer.md](../task_08_checkpointer.md). T04 is already closed; if the backfit is non-trivial, raise a follow-up task rather than re-opening T04.

## Deferred to nice_to_have

None.

## Propagation status

- [../task_03_tiered_node.md](../task_03_tiered_node.md) — carry-over appended (M2-T07-ISS-01 primary owner).
- [../task_08_checkpointer.md](../task_08_checkpointer.md) — carry-over appended (integration responsibility).
