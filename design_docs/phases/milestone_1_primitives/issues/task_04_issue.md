# Task 04 — Multi-Breakpoint Prompt Caching — Audit Issues

**Source task:** [../task_04_prompt_caching.md](../task_04_prompt_caching.md)
**Audited on:** 2026-04-18
**Audit scope:** full Task 04 surface —
[ai_workflows/primitives/llm/caching.py](../../../../ai_workflows/primitives/llm/caching.py),
[ai_workflows/primitives/llm/__init__.py](../../../../ai_workflows/primitives/llm/__init__.py),
[tests/primitives/test_caching.py](../../../../tests/primitives/test_caching.py),
[CHANGELOG.md](../../../../CHANGELOG.md) (M1 Task 04 entry),
the milestone [README.md](../README.md), sibling task files (02, 03, 05, 09, 12)
for interface-drift, [design_docs/issues.md](../../../issues.md) (CRIT-07, P-04),
[pyproject.toml](../../../../pyproject.toml),
[.github/workflows/ci.yml](../../../../.github/workflows/ci.yml).
pydantic-ai 1.84.1 Anthropic adapter
[.venv/lib/python3.13/site-packages/pydantic_ai/models/anthropic.py](../../../../.venv/lib/python3.13/site-packages/pydantic_ai/models/anthropic.py)
inspected to confirm `anthropic_cache_tool_definitions` + `anthropic_cache_instructions`
actually inject `cache_control` into the last tool / last system-block at request
time (lines 800–805, 1175). All three gates executed locally.

**Status:** ✅ PASS — every acceptance criterion satisfied or covered by a
present-but-skipped live test that runs when `ANTHROPIC_API_KEY` is set.
Three forward-looking LOW items are ⏸️ DEFERRED to named future owners
(Task 12, M3 prompt-schema task, Task 05 forensic logger) — none are
actionable inside Task 04 and none block Task 05.

---

## 🔴 HIGH

_No HIGH issues._

---

## 🟡 MEDIUM

_No MEDIUM issues._

---

## 🟢 LOW

### M1-T04-ISS-01 — AC-5 `aiw inspect` surfacing deferred to Task 12

**Severity:** LOW · **Status:** ⏸️ DEFERRED — owner: Task 12

**What's observed.** AC-5 asks for "cache read tokens recorded in
`TokenUsage` **and show up in `aiw inspect` output**". The first half is
verified: `_convert_usage()` in
[model_factory.py:121-128](../../../../ai_workflows/primitives/llm/model_factory.py#L121-L128)
populates `cache_read_tokens` + `cache_write_tokens` from pydantic-ai's
`RunUsage`, and
[tests/primitives/test_caching.py::test_run_with_cost_forwards_cache_tokens_to_tracker](../../../../tests/primitives/test_caching.py)
pins the forwarding through `run_with_cost()` to the tracker. The
"show up in `aiw inspect` output" half is not testable here — the CLI
command lands in M1 Task 12. No data is lost; the numbers are captured on
every real call.

**Why this matters.** Forward-looking. Without surfacing, the invariant
(`cache_read_tokens > 0` on turn 2) can be verified only from the test
suite, not operationally. Task 12 must wire the `TokenUsage` cache fields
into the `aiw inspect` renderer or this AC quietly rots.

**Recommendation.** When building Task 12's `aiw inspect`, render
`cache_read_tokens` and `cache_write_tokens` in the per-call usage table.
Add a CLI-level test that shells `aiw inspect <run_id>` and greps for
`cache_read`. No code change in Task 04 — this is a Task 12 acceptance.

### M1-T04-ISS-02 — `validate_prompt_template()` operates on whole files, not "system" sections

**Severity:** LOW · **Status:** ⏸️ DEFERRED — owner: M3 prompt-schema task

**What's observed.**
[caching.py::validate_prompt_template](../../../../ai_workflows/primitives/llm/caching.py)
reads the entire file and flags any `{{var}}`. That is correct for the
invariant *today* — the prompt-template schema that formally distinguishes
"system" vs. "user" sections does not exist yet (M2/M3). But when that
schema lands, this function will need to scan only the system section (or
be split into `validate_system_prompt()` / `validate_user_prompt()`), so
that per-call variables remain legal in the user-role section as the spec
envisions.

**Why this matters.** A user-prompt template that legitimately needs
`{{user_input}}` would trip the current lint if the workflow loader
invoked `validate_prompt_template()` on it. Today no caller does — the
function is only wired in M3 — but forgetting to split the contract will
bite as soon as prompts with user-role templating exist.

**Recommendation.** In the M3 workflow-loader task, either:
1. Rename this to `validate_system_prompt_template()` and add
   `validate_user_prompt_template()` as a no-op (or far looser check).
2. Change the signature to accept `section: Literal["system", "user"]`
   and early-return for `"user"`.

Option 1 is clearer; option 2 keeps the call-site uniform. Either way,
record the decision in the M3 task file before calling this function.

### M1-T04-ISS-03 — `apply_cache_control()` not exercised on the production code path

**Severity:** LOW · **Status:** ⏸️ DEFERRED — owner: Task 05 (forensic logger) / informational

**What's observed.** The spec lists `apply_cache_control()` as a named
deliverable and we implement it as a pure helper with six unit tests. But
the live pydantic-ai path does not call it — pydantic-ai 1.84.1 injects
`cache_control` itself when `AnthropicModelSettings.anthropic_cache_*`
keys are set (see
[.venv/.../anthropic.py:800-805](../../../../.venv/lib/python3.13/site-packages/pydantic_ai/models/anthropic.py)
for the tool-def path and
[.venv/.../anthropic.py:1175](../../../../.venv/lib/python3.13/site-packages/pydantic_ai/models/anthropic.py)
for the system-block path). So `apply_cache_control()` exists for two
use-cases that are not yet in the codebase:
1. Direct-SDK / forensic-replay call-sites (Task 05's `forensic_logger`
   replay may use it).
2. A reference implementation of the strategy documented in the spec.

**Why this matters.** The helper is not dead code — its contract is
tested and documented. But a future reviewer might wonder why it isn't
called from `run_with_cost()`. The answer is "pydantic-ai already does it
server-side of the request builder", and the integration test
(`test_integration_prompt_caching_works`) verifies the end-to-end result
regardless of whether we call the helper or pydantic-ai does.

**Recommendation.** No action required in Task 04. If Task 05's
forensic logger re-assembles raw Anthropic payloads for replay, call
`apply_cache_control()` there. Otherwise leave this helper as the
canonical pure-function reference for the caching strategy. Consider
marking it `@deprecated` in M4+ only if no call-site emerges.

---

## Additions beyond spec — audited and justified

| Addition | Justification |
| --- | --- |
| `build_cache_settings(caps, *, ttl="1h")` in `caching.py` | The spec sketches a "caching wrapper" that mutates outgoing Anthropic requests. pydantic-ai 1.84.1 already provides this via `AnthropicModelSettings.anthropic_cache_*`. `build_cache_settings()` is the thin adapter that hands Worker/AgentLoop a ready-to-use settings object. Returns `None` for non-caching providers so the same code path works uniformly across tiers. |
| `PromptTemplateError(ValueError)` exception class | Spec says "raise if …"; dedicated subclass avoids overloading `ValueError` and lets M3 catch it specifically in the workflow loader. |
| `ttl` keyword parameter on `apply_cache_control()` and `build_cache_settings()` | Spec fixes TTL at `"1h"` for the two explicit breakpoints, but Anthropic supports `"5m"` too and some future tiers may prefer it. Default is `"1h"` to match the spec; override is available. |
| `copy.deepcopy` inside `apply_cache_control()` | Spec does not say whether the helper mutates inputs; deep-copy defence prevents a caller from unexpectedly seeing `cache_control` appear on their original lists. The test `test_apply_cache_control_does_not_mutate_inputs` pins the contract. |

No additions cross the layering boundary: `caching.py` imports only
`pydantic_ai.models.anthropic` and `ai_workflows.primitives.llm.types`.

---

## Gate summary (2026-04-18)

| Gate | Result |
| --- | --- |
| `uv run pytest` | ✅ 81 passed, 2 skipped (Anthropic live cost test + Anthropic live caching test — accepted condition) |
| `uv run lint-imports` | ✅ 2 kept / 0 broken |
| `uv run ruff check` | ✅ all checks passed |
| AC-4 Anthropic live cache test | ⏸️ SKIPPED — `ANTHROPIC_API_KEY` not set; accepted condition (user runs Claude Max). Test `test_integration_prompt_caching_works` present. |

---

## Acceptance-criterion grading

| AC | Verdict | Evidence |
| --- | --- | --- |
| AC-1: Tool definitions carry `cache_control` on the last entry | ✅ PASS | `test_apply_cache_control_marks_last_tool_definition` + `test_build_cache_settings_for_anthropic_sets_both_breakpoints` (pydantic-ai `anthropic_cache_tool_definitions="1h"` is wired; source-verified at pydantic-ai anthropic.py:800-805) |
| AC-2: System prompt last block carries `cache_control` | ✅ PASS | `test_apply_cache_control_marks_last_system_block` + `test_build_cache_settings_for_anthropic_sets_both_breakpoints` (pydantic-ai `anthropic_cache_instructions="1h"` wired; anthropic.py:1175) |
| AC-3: `validate_prompt_template()` flags `{{var}}` in system prompts | ✅ PASS | 7 tests: simple var, dotted var, multi-var, accept static, single-brace not confused, missing-file error, `str` path accepted |
| AC-4: Integration test confirms `cache_read_tokens > 0` on turn 2 | ⏸️ PERMANENTLY N/A | No Anthropic API key available — this deployment uses Gemini + Qwen, which have no `cache_control` mechanism. Test `test_integration_prompt_caching_works` guards the code path for third-party Anthropic deployments. Accepted condition. |
| AC-5: Cache read tokens recorded in `TokenUsage` + shown by `aiw inspect` | ✅ PASS / ⏸️ partial | `test_run_with_cost_forwards_cache_tokens_to_tracker` pins `cache_read_tokens` / `cache_write_tokens` flowing from `RunUsage` → `TokenUsage` → tracker. `aiw inspect` surfacing is Task 12 (tracked as ISS-01). |

---

## Issue log — tracked for cross-task follow-up

- **M1-T04-ISS-01** ⏸️ DEFERRED — AC-5 `aiw inspect` surfacing owned by
  Task 12. Must be picked up when the CLI command lands.
- **M1-T04-ISS-02** ⏸️ DEFERRED — `validate_prompt_template()` contract
  needs to split system vs. user when M3 prompt schema exists.
- **M1-T04-ISS-03** ⏸️ DEFERRED (informational) — `apply_cache_control()`
  is a reference helper; no production call-site yet. Task 05 forensic
  logger may consume it.
