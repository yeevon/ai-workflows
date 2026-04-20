# Task 02 — Claude Code Subprocess Driver — Audit Issues

**Source task:** [../task_02_claude_code_driver.md](../task_02_claude_code_driver.md)
**Audited on:** 2026-04-19
**Audit scope:** `ai_workflows/primitives/llm/claude_code.py`,
`ai_workflows/primitives/llm/__init__.py`,
`tests/primitives/llm/test_claude_code.py`,
`CHANGELOG.md` (Unreleased §M2 Task 02), `pyproject.toml`,
`.github/workflows/ci.yml`, `pricing.yaml`, `tiers.yaml`,
[architecture.md](../../../architecture.md) (§3 layers, §4.1
primitives layer, §4.2 graph layer, §6 dependencies, §8.2 error
handling, §8.5 cost control, §8.6 concurrency), KDR-003 / KDR-004 /
KDR-006 / KDR-007, sibling tasks
[task_01](../task_01_litellm_adapter.md) (audit file ✅ PASS) and
[task_03](../task_03_tiered_node.md) (dispatches by `route.kind`
onto the `complete(...)` surface this driver now provides). Ran
`uv run pytest`, `uv run lint-imports`, `uv run ruff check`, and the
KDR-003 grep (`grep -r "ANTHROPIC_API_KEY\|from anthropic\|import
anthropic" ai_workflows/`) locally.
**Status:** ✅ **PASS** — all 5 ACs met; no OPEN issues; gates green
(pytest 171 passed / lint-imports 3 kept / ruff clean). Three LOW
observations logged for traceability; none blocks cycle completion.

## Design-drift check — clean

Cross-referenced every change against `architecture.md` before
grading ACs:

| Drift vector | Finding |
| --- | --- |
| **New dependency?** | None. Driver uses only `asyncio`, `json`, and `subprocess` from the stdlib plus `pydantic.BaseModel` (already in [pyproject.toml](../../../../pyproject.toml) `[project] dependencies`). KDR-007's "Claude Code stays bespoke (subprocess OAuth)" explicitly rules out a SDK wrap; the implementation matches. |
| **New module or layer?** | `primitives/llm/claude_code.py` slots into the existing `primitives/llm/` subpackage installed by M2 T01. No upward imports. Four-layer contract (`primitives → graph → workflows → surfaces`) kept. Confirmed by `uv run lint-imports` (3/3 contracts kept). |
| **LLM call added?** | The driver *is* the Claude-Code provider driver the primitives layer has always been responsible for (architecture.md §4.1: "both return `(text, TokenUsage)`"). It does not itself wire a call path into workflows/surfaces — `TieredNode` (M2 T03) + paired `ValidatorNode` per KDR-004 will handle that. No KDR-004 violation at this layer. |
| **KDR-003 (no Anthropic API)?** | `grep -rn "ANTHROPIC_API_KEY\|from anthropic\|import anthropic" ai_workflows/` → 0 matches (including in the new module). The driver only imports `asyncio`, `json`, `subprocess`, `typing.Any`, `pydantic.BaseModel`, and its own sibling primitives. Auth is OAuth/keychain held by the CLI — no env-var lookup anywhere. |
| **Checkpoint/resume logic?** | None. KDR-009 is out of scope for this task. |
| **Retry logic?** | The driver carries **no** try/except around a retry loop. It only wraps `asyncio.wait_for(proc.communicate(...), timeout=...)` to convert `TimeoutError` into `subprocess.TimeoutExpired` (the exact shape the M1 T07 `classify()` expects for a transient bucket). The three-bucket taxonomy (KDR-006) runs above the driver in `RetryingEdge` (M2 T07). Confirmed by the audit's `classify()` probes: both `TimeoutExpired` → `RetryableTransient` and `CalledProcessError` → `NonRetryable` are asserted in the test suite. |
| **Observability?** | No new logging backend. `StructuredLogger` use arrives in M2 T03 (`TieredNode`), not here. No Langfuse / OTel / LangSmith imports. |

**Verdict:** no drift. No HIGH recorded.

## AC grading

| AC | Status | Evidence |
| --- | --- | --- |
| AC-1 — Driver returns `(str, TokenUsage)` with `sub_models` populated when `modelUsage` is present | ✅ Pass | [claude_code.py](../../../../ai_workflows/primitives/llm/claude_code.py) — `complete()` returns the tuple; `_build_usage` iterates `modelUsage` and assigns the primary entry while pushing the rest onto `sub_models`. [test_claude_code.py::test_complete_returns_text_and_token_usage_with_sub_models](../../../../tests/primitives/llm/test_claude_code.py) asserts the primary (`claude-opus-4-7`) is the `opus` cli_flag match and the single sub-model is the haiku auto-classifier. |
| AC-2 — Cost computed from `pricing.yaml` for top-level and every sub-model row | ✅ Pass | `_compute_cost` multiplies every token bucket by its per-million-token rate across `input_per_mtok`, `output_per_mtok`, `cache_read_per_mtok`, `cache_write_per_mtok`. The test fixture uses non-zero rates (the shipped `pricing.yaml` has $0 Claude-Max rows, which would hide arithmetic bugs) and asserts explicit expected values for both the opus primary (`(6/1M)*15 + (6/1M)*75 + (13737/1M)*18.75`) and the haiku sub-model (`(353/1M)*1 + (13/1M)*5`). |
| AC-3 — Timeouts and non-zero exits bucket correctly via `classify()` | ✅ Pass | `test_timeout_raises_timeoutexpired_bucketed_transient` verifies `subprocess.TimeoutExpired` → `RetryableTransient`. `test_non_zero_exit_raises_calledprocesserror_bucketed_nonretryable` verifies `subprocess.CalledProcessError` → `NonRetryable`. Both tests call `classify()` on the raised exception to exercise the taxonomy mapping directly. |
| AC-4 — No `ANTHROPIC_API_KEY` lookup anywhere (KDR-003) | ✅ Pass | `test_no_anthropic_api_key_reference_in_driver_source` reads the driver source and asserts absence of `ANTHROPIC_API_KEY`, `from anthropic`, and `import anthropic`. Audit re-ran the same grep over all of `ai_workflows/` — 0 matches. |
| AC-5 — `uv run pytest tests/primitives/llm/test_claude_code.py` green | ✅ Pass | 11 passed in 0.79s locally; full suite 171 passed (was 160 pre-task, +11 from the new file). |

## Gate summary

| Gate | Result |
| --- | --- |
| `uv run pytest` | ✅ 171 passed, 2 warnings (pre-existing yoyo DeprecationWarning from storage tests) |
| `uv run lint-imports` | ✅ 3 contracts kept, 0 broken |
| `uv run ruff check` | ✅ All checks passed |
| `grep -rn "ANTHROPIC_API_KEY\|from anthropic\|import anthropic" ai_workflows/` | ✅ 0 matches (KDR-003) |

## 🔴 HIGH — none

## 🟡 MEDIUM — none

## 🟢 LOW

### M2-T02-ISS-01 (LOW) — Task spec names `pricing: PricingTable`; no such type exists

- **Finding.** The task spec's deliverable block types the constructor
  as `__init__(self, route: ClaudeCodeRoute, per_call_timeout_s: int,
  pricing: PricingTable)`. No `PricingTable` class exists in
  `ai_workflows.primitives.tiers` (or anywhere else). The implementation
  uses `dict[str, ModelPricing]` — the concrete return type of
  `load_pricing()` introduced in M1 T06 — which is the only available
  pricing surface at this layer.
- **Severity.** LOW — the spec names a type that was never created;
  the implementation uses the *existing* contract from M1 T06 and
  documents the deviation in the CHANGELOG. No semantic drift.
- **Action / Recommendation.** None at the driver layer. When M2 T03
  (`TieredNode`) instantiates this driver, it will pass the
  `load_pricing()` dict directly. If a future refactor introduces a
  named `PricingTable` wrapper, the driver can be updated in place
  with no behavioural change. Captured here so the T03 author does
  not re-litigate the type choice.

### M2-T02-ISS-02 (LOW) — Task spec says "via stdin"; spike invoked prompt as positional

- **Finding.** The task spec prescribes "Feed the prompt via stdin."
  The M1 Task 13 spike validated the CLI with the prompt passed as a
  positional argv element. Both shapes work — the spec's stdin choice
  sidesteps argv-length limits and shell-quoting ambiguity, which is
  the better default for a production driver, so the implementation
  honours the spec. The deviation from the spike's argv shape is
  noted for clarity.
- **Severity.** LOW — spec wins over spike per CLAUDE.md ("task file
  wins"); the implementation complies with the spec. No behavioural
  risk — stdin prompts flow through the `--print` / `-p` path the
  spike already validated end-to-end.
- **Action / Recommendation.** None. If the CLI ever stops accepting
  stdin prompts under `-p --output-format json`, flip to the
  positional form; the test fixture already captures the stdin payload
  (`FakeProc.received_stdin`) so a regression would surface loudly.

### M2-T02-ISS-03 (LOW) — `--setting-sources ""` hermetic-flag carry-over not applied

- **Finding.** The archived M1 Task 13 issue file (`M1-T13-ISS-01`,
  LOW) suggested the launcher pass `--setting-sources ""` (or
  `--setting-sources user`) in addition to `--tools ""` /
  `--no-session-persistence` for full hermeticity. That issue was
  carried over to an M4 Task 00 that was subsequently archived when
  the LangGraph pivot rewrote the milestone map (the original M4
  Task 00 is under `design_docs/archive/pre_langgraph_pivot_2026_04_19/`).
  The current M2 Task 02 spec does not restate the `--setting-sources`
  flag, so it was not applied.
- **Severity.** LOW — spike-era follow-up; the current hermetic flag
  set (`--tools ""` + `--no-session-persistence`) is what the spec
  calls out and what the spike validated. Adding an un-specced flag
  without a trigger would be drive-by scope.
- **Action / Recommendation.** None in this task. If the driver later
  exhibits flaky behaviour because of user/project settings bleeding
  into the subprocess, revisit at that point — probably as a M2 T03
  (`TieredNode`) invocation-shape refinement rather than a driver
  change. Not propagated forward; flagged here for traceability only.

## Additions beyond spec — audited and justified

| Addition | Justification |
| --- | --- |
| `is_error: true` → synthetic `subprocess.CalledProcessError` | M1 Task 13 spike explicitly named `is_error` as the truth-bearing field even on exit 0. The spec's "Non-zero exit: stderr captured; mapped via `classify()`" covers the exit-1 case but not the exit-0-with-`is_error`-true case. Raising `CalledProcessError` gives `classify()` the same `NonRetryable` bucket either way, matching the spike's AC-5 mapping. Covered by `test_is_error_true_raises_calledprocesserror_bucketed_nonretryable`. |
| `--system-prompt` forwarding from `system` arg | Task spec's deliverable signature has `system: str \| None` — forwarding is the only sensible interpretation and the spike validated that `--system-prompt` actually reaches the model. |
| `messages` flattening into a single stdin blob | The CLI runs single-shot; the spec takes a multi-turn `messages: list[dict]` for API parity with the LiteLLM adapter. Flattening `content` fields with `\n\n` separators is the least-lossy translation and preserves ordering; empty contents are dropped so role-tags do not leak bare separators. Covered by `test_complete_flattens_multiple_messages_into_stdin`. |
| `response_format` kwarg accepted but ignored | Same API-parity reason; the CLI has no structured-output mode and `ValidatorNode` handles schema enforcement per KDR-004. Documented in the method docstring and covered by `test_response_format_is_accepted_and_ignored`. |
| Top-level-`usage` fallback when `modelUsage` is absent | The spike called this out as a defensive branch for older CLI versions; the implementation honours the contract and the test fixture (`test_complete_falls_back_to_top_level_usage_when_modelusage_absent`) exercises it. |

None of these introduce new coupling, none imports any new dependency, and all are justified by contracts that already exist upstream or the spike's explicit findings. Cleared.

## Issue log — cross-task follow-up

None. All three LOW observations are self-contained in this task; nothing propagates forward.

## Deferred to nice_to_have

None — no findings map to any `nice_to_have.md` trigger.

## Propagation status

No forward-deferred items. No sibling task spec modified.

---

**Final verdict:** ✅ **PASS on cycle 1.** All five ACs graded
individually, no design drift, no HIGH / MEDIUM findings, three LOW
observations logged for traceability only.
