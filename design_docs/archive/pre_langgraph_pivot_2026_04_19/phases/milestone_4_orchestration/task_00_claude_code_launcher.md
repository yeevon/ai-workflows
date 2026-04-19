# Task 00 — `claude_code` Provider Launcher

**Status:** 📋 Drafted — 2026-04-19. Owns the implementation of the
`claude_code` provider that M1 reserved in `tiers.yaml` +
`model_factory.py`. Sequenced **before** `task_01_planner.md` because the
Planner's `planning_tier` default is `opus`, which is a `claude_code`
tier — the Planner cannot run until this lands.

**Issues resolved by this task:** `M1-EXIT-ISS-02` (carried over from
`design_docs/phases/milestone_1_primitives/issues/m1_exit_criteria_audit.md`).
Design questions that would normally be open at the start of this task
were front-loaded into the M1 Task 13 spike — see
[`design_docs/phases/milestone_1_primitives/task_13_claude_code_spike.md`](../milestone_1_primitives/task_13_claude_code_spike.md)
for the validated assumptions; the Carry-over from prior audits section
at the bottom of this file lists every decision the spike baked in.

## What to Build

A subprocess-backed pydantic-ai `Model` subclass that drives the `claude`
CLI against the developer's Claude Max subscription, plus the tier-config
and capability plumbing to expose it uniformly through `build_model()`
and `run_with_cost()`.

### `ai_workflows/primitives/llm/claude_code_model.py`

New module — sibling of `model_factory.py`. Houses:

- `ClaudeCodeModel(pydantic_ai.models.Model)`: overrides `request()` to
  shell out to `claude --print --output-format json --model <id>
  --tools "" --no-session-persistence [--system-prompt ...] <prompt>`,
  parses the JSON envelope, returns a `ModelResponse` whose single
  `TextPart` holds `result` and whose usage is populated from the
  `usage` field.
- `ClaudeCodeError` exception hierarchy mapped onto the Task 10 retry
  taxonomy (see Carry-over § Error taxonomy).
- Internal helpers: `_flatten_messages()` collapses `list[ModelMessage]`
  into a single prompt string + system-prompt string (text-only; error
  out on tool-call history — the CLI cannot ingest a tool-call turn).

### `ai_workflows/primitives/llm/model_factory.py`

Replace the `NotImplementedError` branch:

```python
if config.provider == "claude_code":
    return _build_claude_code(config)
```

`_build_claude_code()` returns `(ClaudeCodeModel, ClientCapabilities)`
with `supports_tool_registry=False`. Keep `max_retries=0` as the invariant
(there's no SDK client, but document in the builder that the `claude`
CLI's own retry behaviour must also be disabled — see carry-over).

### `ai_workflows/primitives/llm/types.py`

Add `supports_tool_registry: bool = True` to `ClientCapabilities`.
Default `True` (matches current behaviour of every other provider). Set
`False` on the `claude_code` caps returned by `_build_claude_code()`.

### `ai_workflows/primitives/tiers.py`

Add a post-validator to `TierConfig` that raises `ConfigurationError`
when `provider == "claude_code"` and either `max_tokens` or `temperature`
is non-None. Error message: name the offending field and cite that the
`claude` CLI does not expose the flag.

### `tiers.yaml`

Drop `max_tokens: 8192` and `temperature: 0.1` from the `opus`, `sonnet`,
`haiku` rows. Add a block comment above those tiers explaining that these
fields are rejected for `claude_code` (and why).

### `run_with_cost()`

Extend to iterate the launcher's result-usage when the model is a
`ClaudeCodeModel` — one `CostTracker.record()` call per sub-model in the
CLI's `modelUsage` breakdown (not just the aggregate `usage`). Tag each
record with its actual model ID. Falls back to a single `usage`-based
record when `modelUsage` is absent (older CLI versions).

## Acceptance Criteria

- [ ] **AC-1** — `build_model("opus", tiers, tracker)` returns a working
  `(ClaudeCodeModel, ClientCapabilities)` pair; `caps.supports_tool_registry`
  is `False`; `caps.provider == "claude_code"`.
- [ ] **AC-2** — `Agent(model).run("what is 2+2?")` through a `claude_code`
  tier returns a string response; cost tracker records one entry per
  entry in `modelUsage` (typically two: the requested tier's model *and*
  the CLI-internal haiku sub-call).
- [ ] **AC-3** — Building an `Agent(model, tools=[...])` on a `claude_code`
  tier raises `ConfigurationError` at `Agent` construction time (or at
  tool-registration time, whichever pydantic-ai makes inspectable). The
  error message names the tier and cites the capability flag.
- [ ] **AC-4** — Loading `tiers.yaml` with `max_tokens: 8192` re-added to
  the `opus` row raises `ConfigurationError` at `load_tiers()` time.
  Same for `temperature: 0.1`.
- [ ] **AC-5** — Failure-mode dispatch: invalid model id → non-retryable;
  unknown-flag subprocess error → non-retryable; `TimeoutExpired` →
  retryable-transient; `FileNotFoundError` from `subprocess.exec` →
  non-retryable with a message pointing at install docs. Tests cover
  each bucket by monkeypatching `subprocess.exec`.
- [ ] **AC-6** — End-to-end smoke in `scripts/m1_smoke.py` (or a new
  `scripts/m4_smoke.py`) exercises all three claude_code tiers and
  prints the per-tier cost breakdown, verifying the sub-model split.
- [ ] **AC-7** — M1-EXIT-ISS-02 flipped to RESOLVED in the audit file
  and this task referenced as owner.

## Non-Goals

- **Not** implementing streaming (`--output-format stream-json`). Deferred
  to whichever task first needs token-level streaming through a Claude
  tier; tracked as an M4 follow-up issue if Planner/AgentLoop hit it.
- **Not** implementing prompt caching through the CLI. The CLI already
  handles its own caching internally (visible via `cache_creation_input_
  tokens` / `cache_read_input_tokens`); we neither control it nor need to.

## Dependencies

- M1 Task 13 spike findings (this file's Carry-over section).
- `claude` CLI v2.1.114+ installed and authenticated under the
  developer's Max subscription. The launcher module enforces via a
  clear startup error when `claude --version` fails.

## Carry-over from M1 Task 13 spike — pre-answered design questions

Every item below was validated against the real `claude` CLI in
[`../milestone_1_primitives/task_13_claude_code_spike.md`](../milestone_1_primitives/task_13_claude_code_spike.md).
The builder for Task 00 inherits these as decisions, not open questions.

### CLI surface (spike AC-1)

- Canonical argv: `claude --print --output-format json --model <id>
  --tools "" --no-session-persistence <prompt>`. Add `--system-prompt
  <text>` when a system prompt is present. Do **not** add `--bare` — it
  disables OAuth/keychain and breaks Max-sub auth.
- Exit code 0 on success, 1 on any failure. **Do not trust exit code
  alone** — always parse JSON and check `is_error`. Exit 1 can mean
  "well-formed error response, report to user" (model id wrong, auth
  expired) rather than "retry me."
- CLI startup cost is ~2 s per call on top of API round-trip. Orchestrator
  concurrency budgets should assume claude_code calls are ~2× slower than
  direct HTTP.

### Token-usage reporting (spike AC-2)

- JSON `usage` field maps 1:1 onto `TokenUsage`:
  `input_tokens → input_tokens`, `output_tokens → output_tokens`,
  `cache_read_input_tokens → cache_read_tokens`,
  `cache_creation_input_tokens → cache_write_tokens`.
- `modelUsage` (top-level, dict keyed by model ID) breaks the call down
  per model. **Iterate this and emit one `CostTracker.record()` per
  entry.** The requested tier (e.g. opus) and an internal haiku sub-call
  are both present — recording each gives accurate traces without
  affecting dollars (pricing.yaml is $0 for all claude_* IDs).
- If `modelUsage` is absent on an older CLI version, fall back to one
  record from the top-level `usage`, tagged with the requested model.

### Model ABC vs. bypass (spike AC-3)

- **Subclass `pydantic_ai.models.Model`**, do not bypass. Text-only
  round-trip through `request()` compiles and round-trips cleanly.
- **Set `ClientCapabilities.supports_tool_registry=False`.** The CLI's
  tool sandbox is not extensible with our Python callables, and silently
  dropping tools is unacceptable. Agents that try to register tools on a
  claude_code tier must fail fast at construction.
- A tool-call ModelMessage in the history is a code defect for
  claude_code tiers — surface it as a `TypeError`/`ConfigurationError`
  from `_flatten_messages()`, not a silent drop.

### Flag mapping (spike AC-4)

| Field | CLI flag | Status |
| --- | --- | --- |
| `model` | `--model <id>` | honoured (alias or full ID; pass full ID) |
| `system_prompt` *(new field)* | `--system-prompt <text>` | honoured |
| `max_tokens` | — | CLI has no such flag → reject at config load |
| `temperature` | — | CLI has no such flag → reject at config load |

Drop `max_tokens` and `temperature` from `tiers.yaml` claude_code rows;
validator raises on re-addition.

### Error taxonomy (spike AC-5)

| Outcome | Detection | Bucket |
| --- | --- | --- |
| Clean success | exit 0, `is_error: false` | (n/a) |
| Invalid model id | exit 1, `is_error: true`, `result` mentions "issue with the selected model" | non-retryable |
| Unknown flag (our bug) | exit 1, empty stdout, stderr `error: unknown option '...'` | non-retryable (fail loud) |
| Auth lost | exit 1, `is_error: true`, `result` contains "Not logged in" / "Please run /login" | non-retryable — prompt user to re-auth |
| CLI missing | `FileNotFoundError` from `subprocess.exec` → exit 127 | non-retryable — install-docs hint |
| Timeout | `subprocess.TimeoutExpired` | retryable-transient |
| Rate limit / overload (inferred — not directly observed on Max-sub single-token prompt) | exit 1, `is_error: true`, `result` contains "rate limit" / "overloaded" / "529" | retryable-transient |

Pattern-matching on `result` text is fragile but currently the only
signal. File an M4 follow-up issue if the CLI exposes a structured
error-code field by the time this task starts; if so, switch the
dispatcher to match on that instead.
