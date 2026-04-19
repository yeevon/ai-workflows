# Task 03 — Model Factory — Audit Issues

**Source task:** [../task_03_model_factory.md](../task_03_model_factory.md)
**Audited on:** 2026-04-18
**Re-audited on:** 2026-04-18 (issue-resolution pass)
**Re-audited on:** 2026-04-18 (post-resolution confirmation audit)
**Re-audited on:** 2026-04-18 (final confirmation after ISS-09/10/11 fixes + ISS-12 defer)
**Audit scope:** full Task 03 surface —
[ai_workflows/primitives/llm/model_factory.py](../../../../ai_workflows/primitives/llm/model_factory.py),
[ai_workflows/primitives/tiers.py](../../../../ai_workflows/primitives/tiers.py),
[ai_workflows/primitives/cost.py](../../../../ai_workflows/primitives/cost.py),
[ai_workflows/primitives/llm/types.py](../../../../ai_workflows/primitives/llm/types.py),
[tests/primitives/test_model_factory.py](../../../../tests/primitives/test_model_factory.py),
[tests/conftest.py](../../../../tests/conftest.py),
[CHANGELOG.md](../../../../CHANGELOG.md) (M1 Task 03 entries),
the milestone [README.md](../README.md), sibling task files (02, 04, 07, 09) for
interface-drift, [design_docs/issues.md](../../../issues.md)
(CRIT-05, CRIT-06, P-06, P-09, P-10),
[.github/workflows/ci.yml](../../../../.github/workflows/ci.yml),
and [pyproject.toml](../../../../pyproject.toml). All three gates executed locally.
`RunUsage` attributes probed via REPL to confirm `cache_read_tokens` /
`cache_write_tokens` are real fields on pydantic-ai 1.x. `Agent.run` return
type probed via `inspect.signature` — confirmed `AgentRunResult[Any]`.

**Status:** ✅ PASS — all twelve issues resolved or deferred (ISS-12 deferred
to Task 07 by user decision). All four provider branches have full model-type +
capability-flag + max_retries unit-test coverage. Task 04 may begin.

---

## 🔴 HIGH

_No HIGH issues open. ISS-08 (AC-4 integration) resolved via Gemini + Ollama
live tests in the first resolution pass and confirmed passing in this
re-audit._

---

## 🟡 MEDIUM

### M1-T03-ISS-09 — `openai_compat` capability flags never unit-tested (RESOLVED)

**Severity:** MEDIUM · **Status:** ✅ RESOLVED (2026-04-18)
**Resolution:** Added `test_build_openai_compat_returns_correct_type` (asserts `OpenAIChatModel`, `provider == "openai_compat"`, `model`, `max_context == 128_000`) and `test_openai_compat_capabilities_flags` (asserts all five capability booleans). All four provider branches now have full model-type + caps-flags test coverage.

**Original description (preserved for context)**

**What's wrong.** The `_build_openai_compat()` helper wires a full
`ClientCapabilities` block (provider, max_context 128_000, parallel tool
calls, structured output, vision off, caching off) but **no unit test ever
reads those fields**. The only unit test exercising this branch is
[test_model_factory.py:151](../../../../tests/primitives/test_model_factory.py#L151) —
`test_openai_compat_client_max_retries_is_zero` — which asserts retries only.

Compare with the sibling coverage:

| Provider | model type test | caps flags test | max_retries test |
| --- | --- | --- | --- |
| anthropic | ✅ | ✅ | ✅ |
| ollama | ✅ | ✅ | ✅ |
| google | ✅ | ✅ | ✅ (retry-default) |
| **openai_compat** | ❌ | ❌ | ✅ |

The live Gemini integration test (`test_integration_gemini_cost_recorded_after_real_agent_run`)
calls through `_build_openai_compat()` end-to-end, but it only asserts
`usage.input_tokens > 0` — it never reads `caps.provider`,
`caps.max_context`, or the capability booleans. A silent regression that
flips `supports_structured_output=False` or sets the wrong `max_context`
on the openai_compat branch would ship undetected.

**Why this matters.** `ClientCapabilities` is the CRIT-05 contract.
Components will gate behavior on these flags (structured output path vs.
freeform parse, tool-parallelism) without isinstance() checks. The
openai_compat tier drives DeepSeek, OpenRouter, and Gemini — the three most
likely "real" tiers beside Anthropic. Leaving capability flags unverified
defeats the purpose of having the descriptor.

**Recommendation.** Add two tests mirroring the Google / Ollama pattern:

```python
def test_build_openai_compat_returns_correct_type(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    from pydantic_ai.models.openai import OpenAIChatModel

    model, caps = build_model("gemini", _tiers(), _null_tracker())
    assert isinstance(model, OpenAIChatModel)
    assert caps.provider == "openai_compat"
    assert caps.model == "gemini-2.5-flash"
    assert caps.max_context == 128_000

def test_openai_compat_capabilities_flags(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    _, caps = build_model("gemini", _tiers(), _null_tracker())
    assert caps.supports_prompt_caching is False
    assert caps.supports_parallel_tool_calls is True
    assert caps.supports_structured_output is True
    assert caps.supports_thinking is False
    assert caps.supports_vision is False
```

Two tests, ~15 lines. Zero runtime cost (no network). Closes the last
per-provider coverage hole.

---

## 🟢 LOW

### M1-T03-ISS-10 — `run_with_cost` missing return type annotation (RESOLVED)

**Severity:** LOW · **Status:** ✅ RESOLVED (2026-04-18)
**Resolution:** Added `-> "AgentRunResult[Any]"` annotation and `Any` to `typing` imports; `AgentRunResult` imported under `TYPE_CHECKING`.

**What's wrong.** The task spec declares
`async def run_with_cost(...) -> AgentRunResult` but
[model_factory.py:81-86](../../../../ai_workflows/primitives/llm/model_factory.py#L81-L86)
omits the return annotation entirely. `uv run python -c "..."` confirms
pydantic-ai's `Agent.run()` returns `AgentRunResult[Any]`.

**Why this matters.** Cosmetic + spec compliance. Downstream callers
(Task 04 caching wrappers, Task 09 cost verification) will benefit from
type-checker help. Extra benefit: flips a `type: ignore` dependency if
callers ever try to narrow the result.

**Recommendation.** Import `AgentRunResult` under `TYPE_CHECKING` and
annotate:

```python
if TYPE_CHECKING:
    from pydantic_ai import Agent
    from pydantic_ai.agent import AgentRunResult  # verify exact path

async def run_with_cost(
    agent: "Agent",
    prompt: str,
    deps: WorkflowDeps,
    cost_tracker: CostTracker,
) -> "AgentRunResult[Any]":
    ...
```

Or, more pragmatically, return `Any` to stay decoupled — but take an
explicit stance.

### M1-T03-ISS-11 — `build_model` has an unreachable `Unsupported provider` branch (RESOLVED)

**Severity:** LOW · **Status:** ✅ RESOLVED (2026-04-18) — conservative approach
**Resolution:** Branch kept as-is. Added `test_unsupported_provider_raises_configuration_error` that uses `TierConfig.model_construct(provider="unsupported", ...)` to bypass Literal validation and exercise the fallthrough `raise`. Any future provider added to TierConfig without a matching `_build_*()` branch will trip this test before it ships.

**What's wrong.**
[model_factory.py:78](../../../../ai_workflows/primitives/llm/model_factory.py#L78)
ends with `raise ConfigurationError(f"Unsupported provider: {config.provider!r}")`,
but `TierConfig.provider` is
`Literal["anthropic", "ollama", "openai_compat", "google"]` — Pydantic
rejects anything else at validation, and all four are handled. The final
`raise` is dead code.

**Why this matters.** Low impact (defensive code is fine), but it's
untested and will never fire unless the Literal is expanded without
updating `build_model`. If a future provider is added to `TierConfig`
without a matching `_build_*()` branch, a silent crash would be preferable
to `ConfigurationError` hiding the forgotten branch — or, inversely, we
should formalize the pattern with a `match` statement and a
`typing.assert_never` sentinel so the type checker flags the drift.

**Recommendation.** Two reasonable fixes — **stop and ask the user which
they prefer** before editing:

1. Convert the if/elif chain to a `match` statement with
   `case _ as unreachable: typing.assert_never(unreachable)`. mypy / pyright
   will flag the drift at review time.
2. Leave the explicit `raise` but add a unit test that monkey-patches
   `TierConfig.model_fields` or constructs a `TierConfig.model_construct(...)`
   bypassing validation to exercise the branch.

Option 1 is cleaner; option 2 is lower-risk if we want zero behavior change.

### M1-T03-ISS-12 — `TierConfig.max_retries` field added but never consumed (DEFERRED)

**Severity:** LOW · **Status:** ⏸️ DEFERRED — owner: Task 07 (tiers loader)

**What's wrong.**
[tiers.py:27](../../../../ai_workflows/primitives/tiers.py#L27) defines
`max_retries: int = 3` with a comment noting it's for Task 10. Nothing in
Task 03 reads this field — the underlying SDK clients hard-code
`max_retries=0` regardless. If a user sets `max_retries=5` in
`tiers.yaml` today, the setting is silently ignored.

**Why this matters.** Forward-looking only. But today it reads as a
feature the user can configure when they cannot. A misleading config
surface is worse than a missing one.

**Recommendation.** Either:
1. Remove the field from `TierConfig` now; Task 10 re-adds it when
   `retry_on_rate_limit()` actually reads it.
2. Keep the field but add a deprecation/"not yet active" warning path, or
   rename to `_reserved_max_retries` until Task 10 wires it.

Trade-off: removing means a small cross-task churn when Task 10 lands;
keeping means we ship a dead knob. **Stop and ask** — Task 07 (tiers
loader) is the correct owner of this decision since it formalizes the
tiers.yaml schema.

---

## Additions beyond spec — audited and justified (unchanged from prior audit)

| Addition | Justification |
| --- | --- |
| [ai_workflows/primitives/tiers.py](../../../../ai_workflows/primitives/tiers.py) (`TierConfig`) | Task 03's `build_model()` signature requires `TierConfig` as a parameter type; Task 07 expands this module with `load_tiers()` / `load_pricing()`. Field names and defaults match the Task 07 spec exactly, so Task 07 will expand — not redefine — the model. |
| [ai_workflows/primitives/cost.py](../../../../ai_workflows/primitives/cost.py) (`CostTracker` Protocol) | Required for the `cost_tracker` parameter of `build_model()` and `run_with_cost()`. Using a `Protocol` keeps Task 03 decoupled from the storage layer. Signature matches Task 09's spec exactly. |
| `ConfigurationError` | Referenced by AC-5 but not explicitly defined in the spec. Dedicated exception avoids overloading `ValueError`. |
| Unit test for `run_with_cost()` | Not explicitly listed in the AC, but the spec includes `run_with_cost()` as a named deliverable. Pins the wiring contract. |
| [tests/conftest.py](../../../../tests/conftest.py) | Root conftest calling `load_dotenv()` so integration tests read `.env` without manual `export`. |
| `python-dotenv` dev dependency | Required by `tests/conftest.py`. Lightweight. |
| Gemini + Ollama integration tests | ISS-08 resolution. User runs Claude Max; no separate pay-as-you-go Anthropic API account. |

No additions import from `components` or `workflows`. No adapter-specific
types leaked into shared modules.

---

## Gate summary (final re-audit, 2026-04-18)

| Gate | Result |
| --- | --- |
| `uv run pytest` | ✅ 63 passed, 1 skipped (Anthropic live test — accepted condition) |
| `uv run lint-imports` | ✅ 2 kept / 0 broken |
| `uv run ruff check` | ✅ all checks passed |
| AC-4 Gemini live test | ✅ PASS — `test_integration_gemini_cost_recorded_after_real_agent_run` runs green when `GEMINI_API_KEY` is set |
| AC-4 Ollama live test | ✅ PASS — `test_integration_ollama_cost_recorded_after_real_agent_run` runs green when `AIWORKFLOWS_OLLAMA_BASE_URL` is set to `/v1` |
| AC-4 Anthropic live test | ⏸️ SKIPPED — `ANTHROPIC_API_KEY` not set; accepted condition |

---

## Acceptance-criterion grading (re-audit)

| AC | Verdict | Evidence |
| --- | --- | --- |
| AC-1: `build_model("sonnet", ...)` → `(AnthropicModel, caps)` with `supports_prompt_caching=True` | ✅ PASS | `test_build_anthropic_model_returns_correct_type` + `test_anthropic_capabilities_flags` |
| AC-2: `build_model("local_coder", ...)` → `(OpenAIChatModel, caps)` with Ollama base_url | ✅ PASS | `test_build_ollama_model_returns_correct_type` + `test_build_ollama_base_url_from_config` + `test_ollama_capabilities_flags` |
| AC-3: Underlying SDK clients have `max_retries=0` | ✅ PASS | Anthropic / OpenAI-compat / Ollama: explicit. Google: documented default + regression test. |
| AC-4: Integration test with real provider key confirms cost recording fires after `agent.run()` | ✅ PASS | Gemini `openai_compat` + Ollama live tests green in this re-audit |
| AC-5: Missing env var raises `ConfigurationError` naming the variable | ✅ PASS | Anthropic + Google + custom-env + unknown-tier + openai_compat-missing-base_url tests |

---

## Issue log — tracked for cross-task follow-up

- **M1-T03-ISS-01** ✅ RESOLVED — Google retry documented + regression test added.
- **M1-T03-ISS-02** ✅ RESOLVED — Google provider branch fully tested.
- **M1-T03-ISS-03** ✅ RESOLVED — in-body `cost_tracker` comment added.
- **M1-T03-ISS-04** ✅ RESOLVED — Ollama base-url assertion covers full prefix.
- **M1-T03-ISS-05** ✅ RESOLVED — `openai_compat` raises `ConfigurationError` when `base_url` is absent.
- **M1-T03-ISS-06** ✅ RESOLVED — task file, README, CHANGELOG all marked complete.
- **M1-T03-ISS-07** ✅ RESOLVED — CRIT-05 `[x]`, CRIT-06 `[~]` in `design_docs/issues.md`.
- **M1-T03-ISS-08** ✅ RESOLVED — AC-4 satisfied via Gemini + Ollama integration tests.
- **M1-T03-ISS-09** ✅ RESOLVED — `openai_compat` caps fully tested: `test_build_openai_compat_returns_correct_type` + `test_openai_compat_capabilities_flags`.
- **M1-T03-ISS-10** ✅ RESOLVED — `run_with_cost` annotated `-> "AgentRunResult[Any]"`.
- **M1-T03-ISS-11** ✅ RESOLVED (conservative) — fallthrough branch kept; `test_unsupported_provider_raises_configuration_error` exercises it via `model_construct`.
- **M1-T03-ISS-12** ⏸️ DEFERRED — `TierConfig.max_retries` ownership transferred to Task 07 (tiers loader).
