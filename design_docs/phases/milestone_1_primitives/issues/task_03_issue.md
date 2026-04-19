# Task 03 — Model Factory — Audit Issues

**Source task:** [../task_03_model_factory.md](../task_03_model_factory.md)
**Audited on:** 2026-04-18
**Audit scope:** full Task 03 surface —
`ai_workflows/primitives/llm/model_factory.py`, `ai_workflows/primitives/tiers.py`,
`ai_workflows/primitives/cost.py`, `tests/primitives/test_model_factory.py`,
`CHANGELOG.md` (M1 Task 03 section), the milestone `README.md`, all sibling
task files in `milestone_1_primitives/` (to catch spec drift on `TierConfig`,
`CostTracker`, and the provider → pydantic-ai Model mapping against tasks 02,
04, 07, 09), `design_docs/issues.md` (CRIT-05, CRIT-06, P-06, P-09, P-10),
`.github/workflows/ci.yml`, and `pyproject.toml`. All three gates executed
locally. pydantic-ai 1.x `AnthropicProvider` / `OpenAIProvider` /
`GoogleProvider` APIs probed via REPL to confirm the `provider=` wrapper
pattern is required (direct `anthropic_client=` kwarg on the Model was removed
in 1.0). `google-genai`'s `_api_client.retry_args()` source inspected to
verify default retry behaviour when `retry_options=None`.
**Status:** 🚧 BLOCKED — pending user-provided credentials.
AC-4 (live Anthropic integration test) has never actually executed because
`ANTHROPIC_API_KEY` is unset in this environment; the test is `pytest.mark.skipif`-gated
and was skipped on every run. No live Ollama endpoint is configured either,
so the Ollama build path is only verified at the "client constructs"
level — there is zero evidence that `build_model()` → `Agent.run()` →
`_convert_usage()` → `cost_tracker.record()` works end-to-end against a
real provider. Eight issues filed (1 HIGH · 2 MEDIUM · 5 LOW). Blocker
is **M1-T03-ISS-08**; see below for the exact re-audit steps once the user
exports `ANTHROPIC_API_KEY` and a live Ollama `base_url`.

**Original verdict (superseded):** PASS-WITH-CONDITIONS — every spec AC was
graded satisfied on the assumption that a skipped integration test still
counts as "confirms." That reading was too lenient: the spec's AC-4 verb is
"confirms", which requires the test to have actually run. Grading corrected
below.

---

## 🔴 HIGH

### M1-T03-ISS-08 — AC-4 integration test never executed (BLOCKED on credentials)

**Severity:** HIGH · **Status:** 🚧 BLOCKED — awaits user-provided credentials
**Where:** [`tests/primitives/test_model_factory.py:233-261`](../../../../tests/primitives/test_model_factory.py#L233-L261) (`test_integration_cost_recorded_after_real_agent_run`)

The spec's AC-4 reads:

> Integration test with real Anthropic key confirms cost recording fires
> after an `agent.run()`.

The test exists structurally but is gated by

```python
@pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set — skipping live integration test",
)
```

`ANTHROPIC_API_KEY` is not exported in this environment (confirmed from the
pytest summary: `53 passed, 1 skipped`). The one skipped test IS this
integration test. Consequences:

1. The live path `build_model()` → `pydantic_ai.Agent(model).run()` →
   `AgentRunResult.usage()` → `_convert_usage(RunUsage)` → `CostTracker.record()`
   has **never been executed end-to-end**.
2. `_convert_usage()` pulls four fields off pydantic-ai's `RunUsage` —
   `input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_write_tokens`.
   The unit test populates only the first two on a `MagicMock`. Real
   Anthropic responses populate all four; any field rename or semantic
   change in pydantic-ai ≥ 1.0 would surface only in a live call.
3. CRIT-07 (prompt caching) in [`design_docs/issues.md`](../../../issues.md)
   explicitly requires `cache_read_input_tokens > 0` verification on
   turn 2+. That hinges on `_convert_usage()` correctly mapping
   `RunUsage.cache_read_tokens` → our `TokenUsage.cache_read_tokens`. Task 04
   depends on this pipeline working, so shipping Task 04 on top of an
   unverified Task 03 compounds risk.

Secondary concern, same blocker: no live Ollama endpoint is configured
either. The Ollama build path is verified only at the "client constructs
with `max_retries=0`" level (unit test points at the fake IP
`192.168.1.100:11434`). The milestone README's exit criterion —

> you can make an LLM call from a Python REPL through our tier system

— is unmet for the Ollama tier until a real endpoint is reachable.

**Action / Recommendation (when unblocked):**

1. User exports `ANTHROPIC_API_KEY` (real key) and provides a reachable
   Ollama `base_url` (e.g. `http://<host>:11434/v1`). Document the Ollama
   URL in `tiers.local.yaml` (already gitignored) so it doesn't leak.
2. Re-run the existing live test with the key available:

   ```bash
   uv run pytest tests/primitives/test_model_factory.py::test_integration_cost_recorded_after_real_agent_run -v
   ```

   Expect: 1 passed. Record the `RunUsage` values in the audit re-run log
   (at minimum `input_tokens > 0`, `output_tokens > 0`).
3. Add a parallel live Ollama test that mirrors the Anthropic integration:

   ```python
   @pytest.mark.asyncio
   @pytest.mark.skipif(
       not os.environ.get("AIWORKFLOWS_OLLAMA_BASE_URL"),
       reason="AIWORKFLOWS_OLLAMA_BASE_URL not set — skipping live Ollama test",
   )
   async def test_integration_ollama_agent_run():
       tiers = {"local_coder": TierConfig(
           provider="ollama",
           model="qwen2.5-coder:32b",
           base_url=os.environ["AIWORKFLOWS_OLLAMA_BASE_URL"],
           max_tokens=512,
           temperature=0.1,
       )}
       tracker = _null_tracker()
       model, _ = build_model("local_coder", tiers, tracker)
       agent = Agent(model, output_type=str)
       deps = WorkflowDeps(run_id="int-ollama-1", workflow_id="int-wf-1",
                           component="test", tier="local_coder", project_root="/tmp")
       result = await run_with_cost(agent, "Say 'ok'.", deps, tracker)
       assert result is not None
       tracker.record.assert_awaited_once()
   ```

   This proves the OpenAI-compat → Ollama wiring works against a real
   server.
4. Flip this issue to ✅ RESOLVED once both live tests pass, record the
   test output in `## Gate summary`, regrade AC-4 to ✅ PASS, and flip the
   top-of-file Status line back to PASS-WITH-CONDITIONS (remaining issues
   are ISS-01..ISS-07). Then Task 04 can begin.
5. Do not resolve ISS-01 (Google implicit retry) through this path —
   Google has no free-tier-on-demand live test story and the user has not
   indicated they want to provision a `GOOGLE_API_KEY` for this milestone.
   ISS-01 stays MEDIUM and is addressed independently by passing explicit
   `HttpOptions` at construction time.

**Re-audit checklist (for the unblocking pass):**

- [ ] `ANTHROPIC_API_KEY` exported locally for the re-audit shell.
- [ ] Ollama `base_url` set via `AIWORKFLOWS_OLLAMA_BASE_URL` env var.
- [ ] `uv run pytest` shows 0 skipped on the two integration tests.
- [ ] Captured `RunUsage` output pasted into `## Gate summary` below.
- [ ] AC-4 grade flipped from ⏸️ BLOCKED to ✅ PASS.
- [ ] Top-of-file Status flipped from 🚧 BLOCKED to PASS-WITH-CONDITIONS.
- [ ] `design_docs/issues.md` CRIT-06 flipped to `[~]` or `[x]` per
      ISS-01 resolution path (separate from this blocker).

## 🟡 MEDIUM

### M1-T03-ISS-01 — Google tier's SDK retry control is inherited, not set (CRIT-06)

**Severity:** MEDIUM
**Where:** [`ai_workflows/primitives/llm/model_factory.py:180-193`](../../../../ai_workflows/primitives/llm/model_factory.py#L180-L193) (`_build_google`)

The Anthropic and OpenAI-compat paths explicitly construct their SDK clients
with `max_retries=0`. The Google path does not — it calls
`GoogleProvider(api_key=api_key)` and relies on the `google-genai` default
behaviour for `retry_options=None`, which happens to be
`tenacity.stop_after_attempt(1)` (one attempt, no retries) per
`google.genai._api_client.retry_args`. So the code is currently *compliant by
accident*, but CRIT-06 says:

> Set `max_retries=0` on every underlying SDK client at adapter construction
> (Anthropic, OpenAI, httpx).

The implementation inherits the SDK default instead of *setting* the value.
Two risks:

1. A future `google-genai` release could change the default (e.g. turn on
   retries by default), silently amplifying retry counts the same way CRIT-06
   was written to prevent.
2. There is no test on the Google path asserting retries are off, so the
   above regression would not trip any gate.

**Action / Recommendation:**

Make the retry-off policy explicit, mirroring the other two branches:

```python
from google.genai.types import HttpOptions, HttpRetryOptions
...
def _build_google(config: TierConfig) -> tuple[GoogleModel, ClientCapabilities]:
    api_key = _require_env(config.api_key_env or "GOOGLE_API_KEY")
    http_options = HttpOptions(retry_options=HttpRetryOptions(attempts=1))
    model = GoogleModel(
        config.model,
        provider=GoogleProvider(api_key=api_key, http_options=http_options),
    )
    ...
```

(Note: `GoogleProvider.__init__` does not accept `http_options` directly — it
takes a pre-built `google.genai.Client`. The idiomatic wiring is to build the
`Client` ourselves and pass `provider=GoogleProvider(client=client)`.)

Add a test (see ISS-02) that asserts the retry stop-strategy is
`stop_after_attempt(1)`:

```python
def test_google_client_retries_disabled(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "test")
    model, _ = build_model("google_native", _tiers(), _null_tracker())
    # google-genai stores retry behaviour on the client's _retry handler
    assert model.provider.client._retry.stop.max_attempt_number == 1
```

Alternative (cheaper, accepts the risk): keep the current behaviour and add a
comment in `_build_google()` documenting the reliance on the
`google-genai`-default `stop_after_attempt(1)` policy, plus a single test
asserting the default stays at 1. Either approach resolves CRIT-06's intent;
the first is more durable.

### M1-T03-ISS-02 — No test exercises the `google` provider branch

**Severity:** MEDIUM
**Where:** [`tests/primitives/test_model_factory.py:49-55`](../../../../tests/primitives/test_model_factory.py#L49-L55) (fixture declared), no test consumes it

`GOOGLE_TIER` is declared and wired into the `_tiers()` helper under the key
`"google_native"`, but no test actually calls `build_model("google_native",
...)`. `_build_google()` therefore has zero automated coverage even though
`google` is one of the four supported providers in the spec's mapping table.
Combined with ISS-01, this means the Google path could silently regress
without breaking any gate.

**Action / Recommendation:**

Add three tests mirroring the Anthropic / Ollama coverage:

```python
def test_build_google_model_returns_correct_type(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "test")
    from pydantic_ai.models.google import GoogleModel
    model, caps = build_model("google_native", _tiers(), _null_tracker())
    assert isinstance(model, GoogleModel)
    assert caps.provider == "google"
    assert caps.max_context == 1_000_000

def test_google_capabilities_flags(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "test")
    _, caps = build_model("google_native", _tiers(), _null_tracker())
    assert caps.supports_vision is True
    assert caps.supports_thinking is True
    assert caps.supports_parallel_tool_calls is True

def test_missing_google_key_raises_configuration_error(monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    with pytest.raises(ConfigurationError) as exc_info:
        build_model("google_native", _tiers(), _null_tracker())
    assert "GOOGLE_API_KEY" in str(exc_info.value)
```

## 🟢 LOW

### M1-T03-ISS-03 — `cost_tracker` parameter on `build_model()` is dead weight

**Severity:** LOW
**Where:** [`ai_workflows/primitives/llm/model_factory.py:47-60`](../../../../ai_workflows/primitives/llm/model_factory.py#L47-L60)

`build_model()` accepts `cost_tracker: CostTracker` in its signature per spec,
but the body never touches it — `# noqa: ARG001 — reserved for future usage
callback wiring` silences the lint. The task spec's rationale is that
pydantic-ai exposes a usage callback hook; probing pydantic-ai 1.x confirms
no such hook exists (no `on_usage`, no `usage_callback`, no relevant field on
`ModelSettings` / `AnthropicModelSettings`). Active cost recording lives
entirely in `run_with_cost()`.

The CHANGELOG's "Deviations from spec" section already calls this out, so
it's documented — but the module itself gives no signal to a future
maintainer that the parameter is intentional-but-inert.

**Action / Recommendation:** Add a one-line comment in `build_model()` body
(not just the param annotation) making the intent explicit, e.g.

```python
# cost_tracker is reserved: pydantic-ai 1.x exposes no usage-callback hook,
# so active cost recording happens in run_with_cost(). Accepting the param
# here keeps the factory signature stable for when a hook lands.
_ = cost_tracker
```

Optionally drop the `noqa` once the comment is in place. Do NOT remove the
parameter — the spec mandates it and downstream call sites will pass it.

### M1-T03-ISS-04 — Ollama base-url test assertion is weak

**Severity:** LOW
**Where:** [`tests/primitives/test_model_factory.py:119-122`](../../../../tests/primitives/test_model_factory.py#L119-L122)

`test_build_ollama_base_url_from_config` only asserts
`"192.168.1.100" in str(model.provider.client.base_url)`. Regressions that
dropped the scheme, port, or `/v1` path would not trip this — the `/v1`
segment in particular is essential because we're using `AsyncOpenAI` against
Ollama's OpenAI-compat endpoint (not Ollama's native `/api/*` endpoint).

**Action / Recommendation:** tighten the assertion to cover every meaningful
segment, e.g.:

```python
base = str(model.provider.client.base_url)
assert base.startswith("http://192.168.1.100:11434/v1"), base
```

### M1-T03-ISS-05 — `openai_compat` with no `base_url` silently hits OpenAI

**Severity:** LOW
**Where:** [`ai_workflows/primitives/llm/model_factory.py:162-177`](../../../../ai_workflows/primitives/llm/model_factory.py#L162-L177) (`_build_openai_compat`)

If a user declares `TierConfig(provider="openai_compat", model="...", ...)`
without setting `base_url`, the code passes `base_url=None` to `AsyncOpenAI`,
which then falls back to OpenAI's canonical URL. The user's intent with
`openai_compat` is by definition NOT canonical OpenAI — they meant DeepSeek,
OpenRouter, Gemini-via-compat, etc. A misconfigured tier therefore gets
silently routed to the wrong provider.

**Action / Recommendation:** raise `ConfigurationError` at the top of
`_build_openai_compat()` when `config.base_url` is falsy, naming the tier:

```python
if not config.base_url:
    raise ConfigurationError(
        f"openai_compat tier requires base_url; got None for model {config.model!r}"
    )
```

Add a `test_openai_compat_requires_base_url` guard. Not urgent (nothing in
M1 points an `openai_compat` tier at missing-base_url today), but cheap to
fix and prevents a class of hard-to-debug runtime failures.

### M1-T03-ISS-06 — Task-completion marking not applied

**Severity:** LOW
**Where:** [`../task_03_model_factory.md`](../task_03_model_factory.md),
[`../README.md`](../README.md) line 54

Repeats the Task 02 ISS-05 pattern: the task spec is missing its
top-of-file `**Status:** ✅ Complete (2026-04-18)` line, none of the five AC
checkboxes are ticked, and the milestone `README.md` entry for Task 03 does
not carry the `— ✅ **Complete** (2026-04-18)` suffix.

**Action / Recommendation:** once HIGH/MEDIUM issues here are resolved, apply
the same three-file bookkeeping that closed Task 02's ISS-05:

1. Prepend `**Status:** ✅ Complete (2026-04-18) — see [issues/task_03_issue.md](issues/task_03_issue.md).` to [`task_03_model_factory.md`](../task_03_model_factory.md) and tick all AC checkboxes to `[x]`.
2. In [`../README.md`](../README.md) line 54, append `— ✅ **Complete** (2026-04-18)` to the Task 03 entry.
3. Add a `#### Completion marking (2026-04-18)` subsection under the existing Task 03 CHANGELOG heading.

### M1-T03-ISS-07 — `design_docs/issues.md` CRIT-05 / CRIT-06 status unchanged

**Severity:** LOW
**Where:** [`../../../issues.md`](../../../issues.md) lines 26-27

- **CRIT-05** (`ClientCapabilities` descriptor) is still marked `[~]` with
  the note "per-adapter factory wiring lands in M1 Task 03." Task 03 now
  wires per-adapter `ClientCapabilities` in all four `_build_*` helpers, so
  CRIT-05 should flip to `[x]` with a "Resolved by M1 Task 03" pointer.
- **CRIT-06** (`max_retries=0` on every underlying SDK client) remains `[ ]`.
  With ISS-01 unresolved, the Anthropic and OpenAI-compat branches are
  compliant but Google inherits its policy implicitly. Mark `[~]` now; flip
  to `[x]` once ISS-01 is closed.

**Action / Recommendation:** update the two lines as above in the same
follow-up commit that resolves ISS-01.

---

## Additions beyond spec — audited and justified

| Addition | Justification |
| --- | --- |
| `ai_workflows/primitives/tiers.py` (`TierConfig`) | Task 03's `build_model()` signature requires `TierConfig` as a parameter type; Task 07 later expands this module with `load_tiers()` / `load_pricing()`. Creating the stub here is the minimum needed for Task 03 to type-check and unblock Task 04 (`AnthropicModel` caching wraps). Field names and defaults match the Task 07 spec exactly, so Task 07 will expand — not redefine — the model. |
| `ai_workflows/primitives/cost.py` (`CostTracker` Protocol) | Required for the `cost_tracker` parameter of `build_model()` and `run_with_cost()`. Using a `Protocol` (rather than importing the concrete class from a not-yet-written Task 09 module) keeps Task 03 decoupled from the storage layer and lets Task 09 implement the same interface on a concrete `CostTracker` class. Signature matches Task 09's spec exactly. |
| `ConfigurationError` | Referenced by AC-5 but not explicitly defined in the spec. Creating a dedicated exception avoids overloading `ValueError` and gives callers a specific `except` target. |
| Unit test for `run_with_cost()` (`test_run_with_cost_calls_record`) | Not explicitly listed in the AC, but the spec includes `run_with_cost()` as a named deliverable. Pinning its wiring contract (that `record()` is called with the right kwargs derived from `deps` + `agent.model.model_name`) prevents a silent regression when Task 09 implements `CostTracker.record` for real. |
| `_null_tracker()` / `_tiers()` test helpers | Pure test plumbing. No production surface added. |

No additions import from `components` or `workflows`. No adapter-specific
types leaked into shared modules.

---

## Gate summary

| Gate | Result |
| --- | --- |
| `uv run pytest` | ⚠️ 53 passed, **1 skipped** — the skipped test IS AC-4's live integration test (`test_integration_cost_recorded_after_real_agent_run`). See ISS-08. |
| `uv run lint-imports` | ✅ 2 kept / 0 broken — primitives still free of components/workflows imports |
| `uv run ruff check` | ✅ All checks passed |
| REPL probe: `build_model()` across all four providers | ✅ Anthropic / Ollama / openai_compat / google all construct correctly with env vars set |
| REPL probe: `max_retries == 0` on anthropic / openai_compat / ollama clients | ✅ Verified |
| REPL probe: Google client retry-stop strategy (ISS-01) | ⚠️ Relies on google-genai default `stop_after_attempt(1)` — not explicitly set |
| REPL probe: `AnthropicModel.model_name` is a property returning `str` | ✅ Verified — `run_with_cost()`'s `str(agent.model.model_name)` is safe |
| REPL probe: `pydantic_ai.usage.RunUsage` exposes `input_tokens` / `output_tokens` / `cache_read_tokens` / `cache_write_tokens` | ✅ All four fields match `_convert_usage` |
| `pydantic_ai.Agent.__init__` accepts `output_type=str` | ✅ Verified (AC-4 integration test is syntactically valid) |
| CHANGELOG entry format matches CLAUDE.md prescription | ✅ `### Added — M1 Task 03: Model Factory (2026-04-18)` with Files / ACs / Deviations subsections |

---

## Acceptance-criterion grading

| AC | Verdict | Evidence |
| --- | --- | --- |
| AC-1: `build_model("sonnet", ...)` → `(AnthropicModel, caps)` with `supports_prompt_caching=True` | ✅ PASS | `test_build_anthropic_model_returns_correct_type` + `test_anthropic_capabilities_flags` + REPL probe |
| AC-2: `build_model("local_coder", ...)` → `(OpenAIChatModel, caps)` with Ollama base_url | ✅ PASS (weak base_url assertion — see ISS-04) | `test_build_ollama_model_returns_correct_type` + `test_build_ollama_base_url_from_config` + REPL probe |
| AC-3: Underlying SDK clients have `max_retries=0` | ✅ PASS for Anthropic / OpenAI-compat / Ollama; ⚠️ implicit-only for Google (see ISS-01) | `test_anthropic_client_max_retries_is_zero` + `test_ollama_client_max_retries_is_zero` + `test_openai_compat_client_max_retries_is_zero`; Google path has no test and inherits SDK default |
| AC-4: Integration test with real Anthropic key confirms cost recording fires after an `agent.run()` | ⏸️ BLOCKED — see ISS-08 | Test exists but `ANTHROPIC_API_KEY` is unset → skipped on every run. Spec verb "confirms" requires actual execution, which has not happened. Unblocks when the user exports a key and the test runs green. |
| AC-5: Missing env var raises `ConfigurationError` naming the variable | ✅ PASS | `test_missing_anthropic_key_raises_configuration_error` + `test_missing_custom_api_key_env_names_var` + `test_unknown_tier_raises_configuration_error` |

---

## Issue log — tracked for cross-task follow-up

- **M1-T03-ISS-08** (HIGH) 🚧 BLOCKED — AC-4 live integration test has never
  executed because `ANTHROPIC_API_KEY` is unset; Ollama end-to-end path is
  also unverified for lack of a reachable endpoint. Unblocks when user
  exports `ANTHROPIC_API_KEY` and sets `AIWORKFLOWS_OLLAMA_BASE_URL`.
  Owner: user (credential provisioning) → Task 03 re-audit.
- **M1-T03-ISS-01** (MEDIUM) — Google tier's SDK retry control is implicit
  (relies on `google-genai` default `stop_after_attempt(1)`). Owner: Task 03
  re-build.
- **M1-T03-ISS-02** (MEDIUM) — No test exercises the `google` provider
  branch in `build_model()`. Owner: Task 03 re-build (bundle with ISS-01
  fix).
- **M1-T03-ISS-03** (LOW) — `cost_tracker` parameter on `build_model()` is
  accepted-but-inert; add an in-body comment documenting the forward-compat
  intent. Owner: Task 03 re-build; may be closed out when a pydantic-ai
  usage-callback hook lands (post-M1).
- **M1-T03-ISS-04** (LOW) — Ollama base-url test assertion only checks the
  host octet; tighten to full prefix. Owner: Task 03 re-build.
- **M1-T03-ISS-05** (LOW) — `openai_compat` tier with no `base_url` silently
  falls back to OpenAI's canonical URL; raise `ConfigurationError` instead.
  Owner: Task 03 re-build.
- **M1-T03-ISS-06** (LOW) — Task-completion marking (Status line, AC
  checkboxes, README suffix) not applied. Owner: Task 03 completion commit.
- **M1-T03-ISS-07** (LOW) — `design_docs/issues.md` CRIT-05 / CRIT-06
  statuses unchanged. Owner: Task 03 completion commit (bundle with ISS-06).
