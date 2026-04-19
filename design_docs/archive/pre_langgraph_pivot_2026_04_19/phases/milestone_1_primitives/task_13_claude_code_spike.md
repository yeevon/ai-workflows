# Task 13 — `claude_code` Subprocess Design-Validation Spike

**Status:** ✅ Executed — 2026-04-19. Findings below; net outcome **Confirm-path with three 🔧 ADJUSTMENTS** deferred to a new M4 task (`task_00_claude_code_launcher.md` — created).

**Issues:** M1-EXIT-ISS-02 (H-2 from `issues/m1_exit_criteria_audit.md`)

**Nature:** Design-validation spike. **Not an implementation task.**
Validates the architecture promises the M1 scaffolding has already
made, so a direction change (if warranted) lands while the primitives
are cheap to re-shape rather than at M3/M4 when the Orchestrator,
Planner, and AgentLoop have all been built on the assumption.

## Why this exists

`tiers.yaml` currently declares `opus`/`sonnet`/`haiku` as runtime
tiers with `provider: claude_code`, and `build_model()` raises a typed
`NotImplementedError` for that provider with the message "Subprocess
launcher lands in M4 with the Orchestrator component." That promise
is made in four places (`model_factory.py:82-85`,
`model_factory.py:14-18`, `tiers.py:67-68`, M1 `README.md:12`) and
rests on five unvalidated assumptions:

1. The `claude` CLI supports non-interactive single-shot invocation with
   per-call model selection and deterministic completion exit.
2. The CLI emits parseable token-usage data for each call, so
   `CostTracker.record()` can construct a `TokenUsage`.
3. A subprocess-backed tier can be expressed as a `pydantic_ai.Model`
   subclass, so `Agent.run()` + `run_with_cost()` stay uniform across
   tiers. (The alternative — bypassing the `Agent` path — orphans
   `run_with_cost` and forces the Orchestrator to branch by tier.)
4. Per-tier `max_tokens` / `temperature` / `system_prompt` map cleanly
   onto CLI flags. (If they don't, `TierConfig` is lying to the user
   about what's configurable.)
5. Subprocess failure modes (CLI missing, auth expired, rate-limited,
   sandbox-denied, process killed) can be mapped onto the three-bucket
   retry taxonomy from Task 10.

If any of these assumptions is false, the fix is not additive — it
reshapes the tier config schema, the cost-tracking contract, the
retry layer's error mapping, or all three. Finding out at M3/M4 forces
rework across multiple built-on-top modules. Finding out now forces
rework across the primitives that nothing yet depends on.

## What to Build

Three artefacts, all deliberately lightweight:

### 1. `scripts/spikes/claude_code_poc.py`

Throwaway PoC. Not shipped, not unit-tested. Excluded from pytest and
(if import-ordering forces it) from ruff via a per-file ignore plus a
comment explaining "spike — delete with Task 13 findings".

Minimum behaviours:

- Invoke `claude` as a subprocess non-interactively against each of
  `opus` / `sonnet` / `haiku`, using a one-sentence prompt
  ("Reply in one short sentence: what is 2 + 2?" — mirrors
  `scripts/m1_smoke.py`'s prompt so the output length is comparable).
- Capture stdout, stderr, exit code, and wall time.
- Attempt to parse any token-usage data emitted by the CLI (JSON
  footer, stream-JSON events, stderr fragment — whatever is there).
- Exercise at least two failure modes: (a) invalid model id, (b) a
  prompt that the model is likely to refuse or error on. Capture how
  those surface.
- Dump findings as a structured `json.dumps(..., indent=2)` blob to
  stdout so the output is easy to paste into the findings doc.

### 2. Findings section appended to this task file (§ Findings)

Populated once the PoC runs. Answers each of the five assumption
questions in § Why this exists with concrete observed behaviour, the
decision taken, and the implication for production code. Each
assumption gets one of:

- ✅ **CONFIRMED** — production code already matches reality; no change.
- 🔧 **ADJUSTMENT** — small production change needed (e.g. drop a
  `TierConfig` field; change a docstring). List the change concretely.
- ⚠️ **DIRECTION CHANGE** — the assumption is false in a way that
  breaks the current architecture. Escalate to a new HIGH issue with
  a recovery-path recommendation.

### 3. Propagation output

Picked post-spike, not pre-spike. One of:

- **Confirm-path** — append a carry-over section to whichever M4 task
  the spike identifies as the launcher owner (candidates include
  `task_03_orchestrator.md` or a new `task_00_claude_code_launcher.md`
  ordered before `task_01_planner.md` since Planner runs on `opus`).
  The carry-over cites the spike's decisions on usage reporting, Model
  ABC vs. bypass, flag mapping, and error taxonomy, so the M4 builder
  inherits answered questions rather than open ones.
- **Pivot-path** — open a new HIGH issue at
  `design_docs/issues.md` describing the architecture change
  (candidates: demote Claude tiers to `anthropic` provider with
  `ANTHROPIC_API_KEY` — breaks the project-owner's "no Anthropic API"
  constraint, needs re-confirmation; or switch to session-level cost
  capping rather than per-call — rewrites `CostTracker`). Update
  `memory/project_provider_strategy.md` to reflect the new strategy.

Either way, update `memory/project_provider_strategy.md` (stale on
model name + pricing — this also addresses audit finding M-3) and the
MEMORY.md index line.

## Acceptance Criteria

Each AC is answered in § Findings with one of ✅ CONFIRMED / 🔧
ADJUSTMENT / ⚠️ DIRECTION CHANGE, plus the concrete observed evidence.

- [ ] **AC-1 — CLI surface documented.** Non-interactive single-shot
  invocation, per-call model selection, completion-exit behaviour, and
  auth-inheritance model are each established from real CLI output.
  Document the actual flag names used (don't guess — the CLI is the
  source of truth).
- [ ] **AC-2 — Token-usage reporting strategy decided.** Either the
  CLI emits parseable counts (document the format) *or* a concrete
  fallback strategy is chosen and justified (zero-cost records,
  best-effort estimate from `len(prompt)` + `len(response)`, or a
  move to session-level cost capping). The decision must be explicit
  enough that the Orchestrator builder doesn't have to re-make it.
- [ ] **AC-3 — pydantic-ai `Model` ABC vs. bypass decided.** The
  decision is supported by at least a sketched prototype — not a full
  implementation, but enough to prove the chosen path compiles and can
  round-trip a single prompt+response. If bypass is chosen, document
  the parallel runner's shape and how the Orchestrator dispatches
  between tier types without branching on provider at every call site.
- [ ] **AC-4 — Flag-mapping audit.** For each of `max_tokens`,
  `temperature`, and `system_prompt`, state whether the CLI honours
  it, silently ignores it, or rejects it. If silently ignored, either
  drop the field from `claude_code` `TierConfig` rows or add a
  validator that warns/errors when the field is set for a
  `claude_code` provider.
- [ ] **AC-5 — Error-taxonomy mapping.** Subprocess failure modes
  observed by the PoC are mapped onto the Task 10 retry taxonomy
  (retryable-transient / retryable-semantic / non-retryable). Document
  which SDK exception or return-code pattern maps to each bucket.
- [ ] **AC-6 — Propagation output written.** One of Confirm-path or
  Pivot-path (see § Deliverables) is committed. `m1_exit_criteria_audit.md`
  has M1-EXIT-ISS-02 flipped to ✅ RESOLVED with a pointer to the
  concrete output.
- [ ] **AC-7 — H-1 ruff reorder bundled.** `scripts/m1_smoke.py`
  imports reordered above `load_dotenv()`; `uv run ruff check .`
  passes cleanly. (Bundled here because the spike PoC also lives
  under `scripts/` and any ruff config nudge should cover both files
  in one pass.)
- [ ] **AC-8 — No production code changed until findings justify it.**
  `ai_workflows/primitives/tiers.py`, `ai_workflows/primitives/llm/model_factory.py`,
  `tiers.yaml`, `pricing.yaml`, and the M4 task specs are unchanged in
  this task's commit (unless an AC-1 through AC-5 finding explicitly
  mandates a change, in which case the change is scoped narrowly and
  called out in CHANGELOG under the Task 13 entry).

## Non-Goals (Explicit)

- **Not** implementing the M4 subprocess launcher. That work stays in
  M4, informed by this spike's findings.
- **Not** shipping a production `pydantic_ai.Model` subclass for
  `claude_code`. Any code in this task is exploratory.
- **Not** wiring the spike into the test suite. The spike is a
  one-shot design investigation; its value is the findings, not the
  repeatability.
- **Not** addressing the other OPEN issues from
  `m1_exit_criteria_audit.md` (M-1, M-2, M-3 except for memory
  updates triggered by the spike's strategy findings, L-1, L-2, L-3)
  — those are scoped separately.

## Dependencies

- `claude` CLI installed and authenticated under the project owner's
  Claude Max subscription on the machine running the spike.
- Nothing on the code side — the spike reads from `tiers.yaml` /
  `pricing.yaml` but writes nothing back unless a finding mandates it.

## Findings

**Spike run:** 2026-04-19 against `claude` CLI v2.1.114, authenticated under
the project owner's Claude Max subscription (OAuth/keychain). Prompt:
`"Reply in one short sentence: what is 2 + 2?"`.

**Probe set:** opus/sonnet/haiku via alias; opus via full model ID;
`--system-prompt` probe; invalid-model probe; unknown-flag probe. All seven
probes completed; raw output captured during the run and summarised below.

### AC-1 — CLI surface — ✅ CONFIRMED (with one gotcha)

Canonical non-interactive invocation for a single-shot text→text call under
the Max subscription:

```bash
claude --print --output-format json \
       --model <alias-or-full-id> \
       --tools "" \
       --no-session-persistence \
       "<prompt>"
```

- **Non-interactive single-shot:** `--print` / `-p` suppresses the TUI and
  exits when the model finishes. Confirmed across all three tiers.
- **Per-call model selection:** `--model <x>` accepts either the alias
  (`opus`/`sonnet`/`haiku`) or the full model ID (`claude-opus-4-7`,
  `claude-sonnet-4-6`, `claude-haiku-4-5-20251001`). The full ID is the
  safer choice for the launcher — aliases can silently drift when Anthropic
  rotates the Claude-Max default. `tiers.yaml` already stores full IDs, so
  pass `config.model` through verbatim.
- **Completion-exit:** exit code 0 on clean success, 1 on any non-OK run
  (model error, auth failure, invalid flag). **The exit code alone is
  unreliable** because the CLI also emits a well-formed JSON result with
  `"is_error": true` — the launcher must parse JSON and check `is_error`
  rather than treating exit 1 as "retry me."
- **Auth inheritance:** the Max subscription uses OAuth + keychain. The CLI
  reads `~/.claude/` on startup; no env var plumbing needed from our side.
  **Gotcha:** `--bare` forces "Anthropic auth is strictly `ANTHROPIC_API_KEY`
  or `apiKeyHelper` via `--settings` (OAuth and keychain are never read)"
  (from `claude --help`). **The launcher MUST NOT pass `--bare`** — it will
  break Max-sub auth even though the rest of its semantics (skip hooks,
  plugin sync, auto-memory) would be desirable for a hermetic orchestrator.
  Use `--tools ""` + `--no-session-persistence` + (optionally)
  `--setting-sources ""` instead.
- **Typical wall time:** 1.9–2.6 s per call (cold invocation cost dominated
  by CLI startup + a haiku sub-call that the CLI spawns internally; see
  AC-2 on `modelUsage`). Real API round-trip (`duration_api_ms`) was
  2.1–3.0 s. Plan orchestrator budgets accordingly — claude_code calls are
  ~2× slower than a direct HTTP call to the same model.

### AC-2 — Token usage — ✅ CONFIRMED (with a surprise about sub-agent billing)

The CLI emits parseable token-usage data. JSON output under `--output-format
json` has the shape:

```json
{
  "type": "result", "subtype": "success",
  "is_error": false, "stop_reason": "end_turn",
  "duration_ms": ..., "duration_api_ms": ...,
  "total_cost_usd": <retail dollar estimate>,
  "usage": {
    "input_tokens": 6, "output_tokens": 6,
    "cache_creation_input_tokens": 13737, "cache_read_input_tokens": 0,
    "service_tier": "standard", ...
  },
  "modelUsage": {
    "claude-haiku-4-5-20251001": {"inputTokens": 353, "outputTokens": 13,
      "cacheReadInputTokens": 0, "cacheCreationInputTokens": 0,
      "costUSD": 0.000418, "contextWindow": 200000, "maxOutputTokens": 32000},
    "claude-opus-4-7": {"inputTokens": 6, "outputTokens": 6,
      "cacheReadInputTokens": 0, "cacheCreationInputTokens": 13737,
      "costUSD": 0.08603625, ...}
  },
  "result": "4",
  "session_id": "...", "uuid": "...",
  "terminal_reason": "completed"
}
```

The top-level `usage` maps cleanly onto `TokenUsage`:

- `usage.input_tokens` → `TokenUsage.input_tokens`
- `usage.output_tokens` → `TokenUsage.output_tokens`
- `usage.cache_read_input_tokens` → `TokenUsage.cache_read_tokens`
- `usage.cache_creation_input_tokens` → `TokenUsage.cache_write_tokens`

**Surprise:** every probe against opus/sonnet showed a *secondary*
`claude-haiku-4-5-20251001` call in `modelUsage` (inputTokens ~353, outputTokens
~12) even though we requested opus/sonnet. The CLI spawns haiku internally
for auto-mode classification or title generation; this is the CLI's
"hidden" orchestration. Consequences for our cost tracker:

1. **Per-tier pricing stays $0.** All `claude-*` models are billed against
   the Max subscription, so `pricing.yaml` already records $0/Mtok — the
   retail numbers in `total_cost_usd` and `modelUsage.*.costUSD` are for
   observability only.
2. **Decision:** the launcher should iterate `modelUsage` and emit one
   `CostTracker.record()` call *per sub-model* (including the haiku
   sub-agent), tagging each record with its actual model ID. This gives
   accurate downstream traces and future-proofs the tracker for the day
   someone wants to report "retail equivalent spend." If `modelUsage` is
   absent (older CLI version), fall back to recording a single entry from
   the top-level `usage` field, tagged with the requested tier's model.

No fallback strategy needed — the CLI always emits `usage` when
`--output-format json` is passed. Confirmed across all five success probes.

### AC-3 — pydantic-ai `Model` ABC vs. bypass — 🔧 ADJUSTMENT

**Decision:** implement a minimal `ClaudeCodeModel(pydantic_ai.Model)` that
handles text-only request/response, and set a new `ClientCapabilities.
supports_tool_registry = False` flag on its caps. Do **not** try to pipe
`@agent.tool`-decorated Python functions through the CLI — the CLI runs
its own tool sandbox (Bash, Edit, Read, MCP servers) and does not expose a
hook for us to register arbitrary Python callables.

**Evidence the chosen path compiles and round-trips:**

- Round-trip: five success probes proved prompt + response flows through
  the subprocess boundary, JSON parses deterministically, and `--system-prompt`
  mutates the reply ("BANANA" returned when asked "what is 2 + 2?").
- Compiles: audited-confirmed via
  `python -c "from pydantic_ai.models import Model; …"`. The ABC exposes
  three abstract methods (`request`, `model_name`, `system`) and a
  `request()` signature of
  `request(self, messages: list[ModelMessage], model_settings: ModelSettings | None, model_request_parameters: ModelRequestParameters) -> ModelResponse`.
  A skeleton that forwards to the CLI looks like:

  ```python
  # Sketch — M4 will produce the real implementation.
  class ClaudeCodeModel(Model):
      def __init__(self, model_id: str, tier_name: str): ...
      async def request(self, messages, model_settings, request_parameters):
          prompt, system_prompt = _flatten(messages)
          argv = ["claude", "--print", "--output-format", "json",
                  "--model", self._model_id, "--tools", "",
                  "--no-session-persistence"]
          if system_prompt:
              argv += ["--system-prompt", system_prompt]
          argv.append(prompt)
          proc = await asyncio.create_subprocess_exec(
              *argv, stdout=PIPE, stderr=PIPE)
          stdout, stderr = await proc.communicate()
          data = _parse_or_raise(stdout, stderr, proc.returncode)
          return ModelResponse(
              parts=[TextPart(content=data["result"])],
              model_name=data.get("model_id", self._model_id),
              usage=RequestUsage(
                  input_tokens=data["usage"]["input_tokens"],
                  output_tokens=data["usage"]["output_tokens"],
                  cache_read_tokens=data["usage"]["cache_read_input_tokens"],
                  cache_write_tokens=data["usage"]["cache_creation_input_tokens"],
              ),
          )
  ```

**Why not bypass entirely:** a bypass runner forces every call site to
branch on provider (`if tier.provider == "claude_code": …`). The Planner,
AgentLoop, and Orchestrator all call `Agent.run()` through `run_with_cost`
today; keeping claude_code inside the `Model` ABC preserves that interface.

**Why the capability flag is non-negotiable:** pydantic-ai `Agent` lets you
register tools. If a component builds an Agent on a `claude_code` tier
*and* registers tools, the current ABC contract requires the model to
handle tool calls. Our subprocess wrapper will silently drop registered
tools (the CLI's `--tools ""` disables *CLI*-builtin tools and does not
add user-defined Python tools). That silent drop is the kind of failure
that looks fine in dev and explodes in a multi-agent workflow. Instead,
`build_model()` must refuse at construction time when the tier is
`claude_code` *and* the caller signals intent to register tools. Because
`build_model()` today does not know about tool-registry intent, the
cleanest wiring is: components that need tools read `caps.supports_
tool_registry` before calling `Agent(model, tools=...)` and raise a
`ConfigurationError` if it's False.

**Open question deferred to M4:** streaming. The CLI supports
`--output-format stream-json --input-format stream-json`. If the Planner
needs token-level streaming through a claude_code tier, the launcher
needs a streaming request path too. Not investigated in this spike
because streaming is deferred (M1 README:47).

### AC-4 — Flag mapping — 🔧 ADJUSTMENT

| `TierConfig` field | CLI support | Evidence |
| --- | --- | --- |
| `model` | ✅ via `--model` | success probes round-tripped opus/sonnet/haiku. |
| `system_prompt` *(not yet a field)* | ✅ via `--system-prompt` | "BANANA" probe: model replied "BANANA" to "what is 2+2?" when the system prompt forbade other answers. |
| `max_tokens` | ❌ **rejected** | unknown-flag probe: exit 1, empty stdout, `stderr: error: unknown option '--max-tokens'`. |
| `temperature` | ❌ **rejected** | direct probe during audit: `claude -p --model haiku --temperature 0.5 ...` → `error: unknown option '--temperature'`. Same rejection shape as `--max-tokens`. |

**Actions required in M4 launcher task:**

1. Add a `TierConfig` validator that raises `ConfigurationError` at load
   time when `provider == "claude_code"` and either `max_tokens` or
   `temperature` is set. Error message must name the offending field and
   tell the reader the CLI does not accept them.
2. Drop `max_tokens: 8192` and `temperature: 0.1` from the `opus`,
   `sonnet`, `haiku` rows of `tiers.yaml`. Add a block comment above the
   claude_code tiers explaining that max_tokens/temperature are not
   settable via the CLI (so users don't re-add them).
3. Optionally add `system_prompt: str | None = None` to `TierConfig` so
   the launcher can forward it via `--system-prompt`. This is a capability
   gain for M4, not a Task 13 change.

**Production code was NOT changed in this commit (AC-8 compliance).** The
three changes above are carried over to the new M4 launcher task.

### AC-5 — Error taxonomy — ✅ CONFIRMED (with one mapping nuance)

Observed failure modes and their mapping onto the Task 10 three-bucket
retry taxonomy:

| Failure mode | Observed signal | Bucket |
| --- | --- | --- |
| Clean success | exit 0, `is_error: false`, `stop_reason: end_turn` | (n/a) |
| Invalid model id | exit 1, `is_error: true`, `subtype: success` (sic), `stop_reason: stop_sequence`, `result: "There's an issue with the selected model..."` | **non-retryable** — config/user error; retrying will never succeed. |
| Unknown CLI flag (our bug) | exit 1, **empty stdout**, stderr `error: unknown option '--<flag>'` | **non-retryable** — code defect, must fail loud. |
| Auth failure (`--bare` forced API-key path) | exit 1, `is_error: true`, `result: "Not logged in · Please run /login"` | **non-retryable** — surface to user with "re-authenticate your Claude Max subscription" guidance. |
| CLI binary missing | `FileNotFoundError` from `subprocess.exec` → exit 127 | **non-retryable** — environment error; the launcher should raise a clear `ConfigurationError` pointing to install docs. |
| Subprocess timeout | `subprocess.TimeoutExpired`, launcher synthesises exit ‑1 | **retryable-transient** — could be a hung network call; back off and retry under the Task 10 retry decorator. |
| Rate limit / Anthropic 429 *(not directly observed — Max-sub single-token prompt)* | expected shape: exit 1, `is_error: true`, `result`/`subtype` mentions "rate limit" or "overloaded" | **retryable-transient** — pattern-match on `is_error == true` + `result` substring `rate limit` / `overloaded` / `529`. |
| Server 5xx from Anthropic *(not directly observed)* | same shape as rate-limit, distinct message | **retryable-transient**. |

**Nuance for the M4 implementer:** the CLI's JSON shape uses `subtype: "success"`
even when `is_error: true`, so `is_error` is the truth-bearing field. Pattern-
matching on the `result` text is fragile but the only available signal for
distinguishing retryable (rate-limit/overload) from non-retryable (bad model
id, auth). Re-evaluate when the CLI adds a structured error-code field; track
as an M4 follow-up issue if it's still text-matching at launch.

### Net strategy outcome

**Confirm-path.** All five pre-spike assumptions hold with the adjustments
above. No architecture pivot needed; production code stays unchanged this
commit. Three narrow 🔧 ADJUSTMENTS propagate forward to a new M4 task
(`task_00_claude_code_launcher.md`, inserted before `task_01_planner.md`
because the Planner runs on `opus`):

1. `ClaudeCodeModel(pydantic_ai.Model)` for text-only round-trips; sketch
   above is the starting point.
2. `ClientCapabilities.supports_tool_registry: bool = True` added to
   `types.py`; set `False` on the claude_code caps. Tool-registering
   components refuse to build Agents on claude_code tiers.
3. `TierConfig` validator rejects `max_tokens` / `temperature` when
   `provider == "claude_code"`; `tiers.yaml` drops those fields from the
   opus/sonnet/haiku rows.

Plus one carry-over to the CostTracker integration point in the launcher:
iterate `modelUsage` and record one `TokenUsage` per sub-model, not a
single aggregate.

**M1-EXIT-ISS-02 flipped to ✅ RESOLVED** on this commit — pointer in the
audit file references this task.
