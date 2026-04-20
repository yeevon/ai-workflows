# Task 07a — Planner `tiered_node` Native Structured Output

**Status:** 📝 Planned.
**Prerequisite of:** [Task 08](task_08_milestone_closeout.md) (cannot close M3 until T07a lands).
**Raised by:** [M3 T07 e2e smoke test](task_07_e2e_smoke.md) live run on 2026-04-20 — see [issues/task_08_issue.md](issues/task_08_issue.md) M3-T08-ISS-02.

## What to Build

Pass `output_schema=ExplorerReport` / `output_schema=PlannerPlan` to the two `tiered_node` calls in [ai_workflows/workflows/planner.py](../../../ai_workflows/workflows/planner.py) so LiteLLM flips Gemini into native structured-output / JSON mode and the `validator_node`'s strict `model_validate_json` parse gets deterministic input. Today those calls omit the kwarg, so Gemini returns free-form text (usually markdown-fenced JSON), the validator rejects, the graph burns a hint-driven retry turn against a ~1300-output-token re-roll, and convergence is probabilistic.

Scope is tight: two kwarg additions in `planner.py`, two test-updates in `tests/workflows/test_planner_graph.py`, one CHANGELOG entry. No signature changes to `tiered_node` / `validator_node` / `LiteLLMAdapter` — the plumbing already exists at each hop ([tiered_node.py:113](../../../ai_workflows/graph/tiered_node.py#L113) accepts `output_schema`, [tiered_node.py:343](../../../ai_workflows/graph/tiered_node.py#L343) forwards as `response_format`, [litellm_adapter.py:92-93](../../../ai_workflows/primitives/llm/litellm_adapter.py#L92-L93) forwards to LiteLLM's `response_format`). T03 left the parameter unused; T07 exposed the consequence.

## Why (requirement-drift root cause)

The M3 T07 live e2e run on 2026-04-20 failed with `RetryableSemantic('explorer_validator: output failed ExplorerReport validation')`. Replay showed two explorer calls whose Gemini output failed strict JSON parsing, each consuming a full ~1300 output tokens (~$0.0033 each) before the validator rejected. The third, fourth, and fifth explorer attempts hit transient Gemini 503s and exhausted the retry budget. Without the 503 collision, the semantic-retry loop would have had exactly **one** more attempt before exhaustion — so even on a healthy Gemini day, convergence is not guaranteed.

This is a **requirement gap in T03**, not a T03 implementation defect. The T03 spec ([task_03_planner_graph.md:128-130](task_03_planner_graph.md#L128-L130)) wrote the `tiered_node(...)` calls without `output_schema`, relying on the retry-with-revision-hint loop ([task_03_planner_graph.md:231](task_03_planner_graph.md#L231)) to catch format drift. T03's hermetic tests stub the LiteLLM adapter with pre-canned valid JSON, so the probabilistic-convergence assumption was never exercised against live Gemini. T07 — the first task to exercise the live path — surfaced the gap.

Cost-waste analysis:

- **503 ServiceUnavailable retries:** free. No tokens consumed; `input_tokens=null`, `cost_usd=null` on the `TokenUsage` record. Retrying only costs ~2s of latency per attempt.
- **Semantic-failure retries:** expensive. Each failed explorer/planner re-roll emits a full ~1000–1500-token response before the validator rejects. Two semantic retries in the 2026-04-20 run cost `$0.0067` on what should have been a single-shot $0.003 call.

Native structured output moves JSON shape from a "convince the LLM via prompt" concern to a "the API guarantees it" concern, closing this class of failure near-completely.

## Deliverables

### `ai_workflows/workflows/planner.py`

Two edits, minimal blast radius:

```python
explorer = wrap_with_error_handler(
    tiered_node(
        tier="planner-explorer",
        prompt_fn=_explorer_prompt,
        output_schema=ExplorerReport,   # <-- add
        node_name="explorer",
    ),
    node_name="explorer",
)
# ... planner tier:
planner = wrap_with_error_handler(
    tiered_node(
        tier="planner-synth",
        prompt_fn=_planner_prompt,
        output_schema=PlannerPlan,      # <-- add
        node_name="planner",
    ),
    node_name="planner",
)
```

Prompts in `_explorer_prompt` / `_planner_prompt` can be simplified to drop the "Respond as JSON matching the ... schema: `{...}`" JSON-shape dictation — redundant once the provider enforces it natively. Optional; leave them if the prompt still reads fine.

### `RetryPolicy` — optional bump for 503-resilience

The current policy is `RetryPolicy(max_transient_attempts=3, max_semantic_attempts=3)`. 503 bursts on Gemini's free tier can exceed 3 consecutive attempts during regional incidents; bumping `max_transient_attempts` to 5 is free (no token cost per 503) and buys resilience at the expense of up to ~10s extra latency on bad infra days. **Decision point:** apply the bump as part of T07a, or leave at 3?

The recommendation inside the task spec body is "bump to 5" since:

1. `max_transient_attempts` costs nothing in dollars.
2. It's orthogonal to the structured-output fix — separate concerns, cheap to bundle.
3. CI's `workflow_dispatch` `e2e` job is manual-triggered, so a flaky first run is especially annoying there (no auto-retry on the GHA side).

If the M3 lead wants to keep the bump out of T07a and in a follow-up, split it cleanly — no functional coupling.

### `tests/workflows/test_planner_graph.py`

Two new assertions, attached to the existing happy-path test (not a new test module):

1. After the explorer tier's stubbed `LiteLLMAdapter.generate(...)` call, assert the captured `response_format` kwarg is the `ExplorerReport` class (or a `response_format`-equivalent value consistent with how `tiered_node` forwards it; see [tiered_node.py:343](../../../ai_workflows/graph/tiered_node.py#L343)).
2. Same assertion after the planner tier with `PlannerPlan`.

If the existing stub doesn't capture `response_format`, extend it minimally. Do not add a new test file — keep the assertion colocated with the happy-path scenario.

If the `RetryPolicy` bump is included: add a one-line assertion that `max_transient_attempts == 5` on the `policy` object built inside `build_planner` — either expose `policy` for test inspection or, simpler, re-instantiate the constant inside the test and pin the value.

### `CHANGELOG.md`

Under `## [Unreleased]`, add `### Added — M3 Task 07a: Planner Structured Output (YYYY-MM-DD)`. List:

- The `output_schema=` wiring as the primary fix.
- Token-waste analysis (503s free, semantic retries burn full response tokens).
- Impact on the e2e smoke test's convergence probability.
- If applied: the `RetryPolicy` bump to 5 transient attempts and the reasoning.

### Updates to sibling docs

- [task_08_milestone_closeout.md](task_08_milestone_closeout.md) — add T07a to the `## Dependencies` list. No carry-over section needed; the dependency is explicit.
- [README.md](README.md) task-order table — insert a `07a` row between T07 and T08 with `T04–T07` as the critical-path dep.
- [issues/task_03_issue.md](issues/task_03_issue.md) — append a "**Post-M3 amendment (2026-04-20)**" note at the bottom linking to T07a, documenting that the live-path convergence gap was surfaced by T07 and closed by T07a. Do not re-open the audit or flip its status line.
- [issues/task_08_issue.md](issues/task_08_issue.md) — flip M3-T08-ISS-02 from `OPEN` to `RESOLVED (T07a)` in the cycle-N re-audit after T07a lands and a live e2e `green-once` is recorded in the T08 CHANGELOG entry.

## Acceptance Criteria

- [ ] Both `tiered_node` calls in `planner.py` pass `output_schema=ExplorerReport` / `output_schema=PlannerPlan`.
- [ ] The existing happy-path test in `tests/workflows/test_planner_graph.py` asserts `response_format` was forwarded to the stubbed adapter on both tiers. Pre-T07a this assertion would fail; post-T07a it passes.
- [ ] `uv run pytest` green on a dev box with `AIW_E2E` unset — 295 + (unchanged or +1 for the new assertion count).
- [ ] `AIW_E2E=1 uv run pytest -m e2e -v` green end-to-end with a live `GEMINI_API_KEY`, recorded verbatim in the T08 CHANGELOG entry's `**AC-3 live-run evidence**` sub-block (duration, pass/fail, recorded `runs.total_cost_usd`).
- [ ] `uv run lint-imports` 3 / 3 kept; `uv run ruff check` clean.
- [ ] No change to the `tiered_node` / `validator_node` / `LiteLLMAdapter` signatures or to any other workflow. Scope is strictly T03's two call sites.
- [ ] (If the `RetryPolicy` bump is applied) `max_transient_attempts = 5` is pinned by an explicit test assertion.

## Dependencies

- [M3 Task 03](task_03_planner_graph.md) — the module being edited.
- [M2 Task 03](../milestone_2_graph/task_03_tiered_node.md) — `tiered_node`'s `output_schema` kwarg (already implemented; not modified).
- [M2 Task 01](../milestone_2_graph/task_01_litellm_adapter.md) — `LiteLLMAdapter.generate`'s `response_format` forwarding (already implemented; not modified).

## Non-goals

- Revisiting the three-bucket retry taxonomy (KDR-006).
- Changing the validator-after-every-LLM-node pattern (KDR-004) — that shape is preserved; structured output is complementary, not a replacement.
- Extending `tiered_node` or `validator_node` signatures.
- Rewriting prompts beyond trimming the now-redundant "Respond as JSON matching schema: `{...}`" dictation sentences (optional).
