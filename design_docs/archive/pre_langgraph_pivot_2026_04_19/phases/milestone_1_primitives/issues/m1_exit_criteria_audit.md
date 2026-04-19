# Milestone 1 — Exit-Criteria Audit (post-Task 12)

**Source:** [../README.md](../README.md) + all Task 01–12 issue files.
**Audited on:** 2026-04-19
**Audit scope:** End-to-end verification that M1 is "fully implemented"
and that the provider-strategy architecture (Claude Code CLI for
`opus`/`sonnet`/`haiku`, Ollama for `local_coder`, Gemini API for
`gemini_flash` only) is handled correctly by the primitives layer.
Covers `tiers.yaml`, `pricing.yaml`, `ai_workflows/primitives/tiers.py`,
`ai_workflows/primitives/llm/model_factory.py`, `scripts/m1_smoke.py`,
M1 README, all twelve task specs and their issue files, CI workflow,
and M4 planning docs (propagation target for `claude_code` carry-over).
**Status:** 🟠 CONDITIONAL PASS — both HIGH findings (H-1, H-2) were
addressed by M1 Task 13 (executed 2026-04-19). H-1 ruff reorder: fixed
in [scripts/m1_smoke.py](../../../../scripts/m1_smoke.py). H-2
`claude_code` subprocess design-validation spike: executed, all five
architectural assumptions validated against the real `claude` CLI
v2.1.114, net outcome **Confirm-path** with three narrow 🔧 ADJUSTMENTS
propagated to [../../../milestone_4_orchestration/task_00_claude_code_launcher.md](../../milestone_4_orchestration/task_00_claude_code_launcher.md)
(newly inserted before `task_01_planner.md`). Findings in
[../task_13_claude_code_spike.md](../task_13_claude_code_spike.md).
The remaining MEDIUM / LOW items (M-1..M-3, L-1..L-3) are out of scope
for Task 13 per its AC-8 non-goals and remain OPEN for separate
follow-up.

---

## Exit-criteria grading

Exit criteria (from M1 `README.md:7`): *"you can make an LLM call from
a Python REPL through our tier system. It gets logged to SQLite with
cost, budget cap protects you from runaway spend, retried on rate
limits, and the run is visible in `aiw list-runs`. Prompt caching is
verified (`cache_read_input_tokens > 0` on turn 2+)."*

| Criterion | Verdict | Evidence |
| --- | --- | --- |
| LLM call from Python REPL through tier system | ✅ PASS (partial — 2 of 5 tiers) | `scripts/m1_smoke.py` drives `gemini_flash` and `local_coder` end-to-end through `build_model()` → `run_with_cost()`. `opus`/`sonnet`/`haiku` correctly raise `NotImplementedError` at `build_model()` (AC-6 in Task 03, pinned by `test_build_model_claude_code_raises_not_implemented`). This is architecturally correct for M1 — the `claude_code` provider is deferred to M4 — but see H-2 for the propagation gap. |
| Logged to SQLite with cost | ✅ PASS | Both smoke legs write a row to `runs`, `llm_calls`, and update the run total. Verified via `aiw list-runs` / `aiw inspect`. |
| Budget cap protects against runaway spend | ✅ PASS (unit) / 🟢 PARTIAL (smoke) | `CostTracker` enforcement pinned by `tests/primitives/test_cost.py` (Task 09 audit, AC-2). The smoke's `budget_cap_usd=0.10` leg cannot realistically fire for a one-turn "2+2" prompt; the `BudgetExceeded` branch in `_run_tier` is cosmetic, not exercised. See L-3. |
| Retried on rate limits | ✅ PASS | Task 10 audit ✅ PASS. `retry_on_rate_limit` covered by `tests/primitives/test_retry.py`. Not exercised live by the smoke (would require a rate-limit response). |
| Run visible in `aiw list-runs` | ✅ PASS | Task 12 audit ✅ PASS with 16 pinning tests; confirmed live via `uv run aiw --db-path /tmp/aiw_m1_smoke.db list-runs`. |
| **Prompt caching verified (`cache_read_input_tokens > 0` on turn 2+)** | ⏸️ PERMANENTLY N/A (inconsistent with the stated architecture — see M-1) | No Anthropic API in the runtime tier set. `README.md:48` (Key Decisions table) itself says caching is "Not active — Claude tiers run via CLI, not API." The exit-criteria sentence on `README.md:7` has not been reconciled with that decision. |

## Per-task audit roll-up

| Task | Status | Carry-overs in/out |
| --- | --- | --- |
| 01 Project scaffolding | ✅ PASS | — |
| 02 Shared types | ✅ PASS | — |
| 03 Model factory | ✅ PASS | AC-6 (claude_code raises NotImpl) pinned; `ANTHROPIC_THIRD_PARTY_TIER` fixture retained |
| 04 Prompt caching helpers | ✅ PASS | M1-T04-ISS-01 (cache columns in `aiw inspect`) → RESOLVED by Task 12 |
| 05 Tool registry + forensic logger | ✅ PASS | M1-T05-ISS-02 resolved by Task 11 |
| 06 Stdlib tools | ✅ PASS | — |
| 07 Tiers loader | ✅ PASS | — |
| 08 Storage | ✅ PASS | — |
| 09 Cost tracker | ✅ PASS | M1-T09-ISS-02 (budget line format) → RESOLVED by Task 12 |
| 10 Retry | ✅ PASS | — |
| 11 Logging | ✅ PASS | M1-T01-ISS-08, M1-T05-ISS-02 resolved |
| 12 CLI primitives | ✅ PASS | Closes both inbound carry-overs |

## Gate summary (local, 2026-04-19)

| Gate | Result | Notes |
| --- | --- | --- |
| `uv run pytest` | ✅ 345 passed, 1 skipped | Deprecation warnings are the pre-existing yoyo-migrations `datetime` adapter notices, unrelated. |
| `uv run lint-imports` | ✅ 2 contracts kept / 0 broken | `primitives ∌ components/workflows`, `components ∌ workflows`. |
| `uv run ruff check .` | ❌ 7 errors — **H-1** | `scripts/m1_smoke.py` E402 × 7: `load_dotenv()` sits above the `ai_workflows.*` imports. |
| Default `tiers.yaml` round-trips through `load_tiers()` | ✅ | All 5 tiers (`opus`, `sonnet`, `haiku`, `local_coder`, `gemini_flash`) validate. |
| Default `pricing.yaml` round-trips through `load_pricing()` | ✅ | 5 model rows validate. |
| `build_model("opus" \| "sonnet" \| "haiku", ...)` surfaces typed failure | ✅ | All three raise `NotImplementedError` naming tier + model + "lands in M4" (verified live, not just via unit). |
| Live smoke — `gemini_flash` | ✅ | `gemini-2.5-flash`: 15 in / 2 out tokens, $0.000010, "Four.". |
| Live smoke — `local_coder` | ✅ | `qwen2.5-coder:32b`: 43 in / 8 out, $0.00 (`is_local=1`), "2 + 2 = 4". |

## 🔴 HIGH

### H-1 — Committed smoke script fails the CI ruff gate

**Where:** `scripts/m1_smoke.py:34-40` (seven imports below the `load_dotenv()` call).

**Evidence:**

```
$ uv run ruff check .
E402 Module level import not at top of file
  --> scripts/m1_smoke.py:34:1
... (×7)
Found 7 errors.
```

`.github/workflows/ci.yml:34` runs `uv run ruff check .` — no
per-directory scope, no `scripts/` exclusion in `[tool.ruff]`. Commit
`941cb2e` ("m1 task 12 complete, smoke test for m1 done") landed this
failure; CI on `main` will go red on next push, and any downstream PR
will be blocked.

**Why it passed Task 12's audit:** the Task 12 audit ran
`uv run ruff check` while the smoke script was untracked (the
script's intent was always "manual validation, not wired into
pytest"). The subsequent commit bundled the script in but the gate
was not re-run against the tree as shipped.

**Action — Recommendation:** reorder `scripts/m1_smoke.py` so module
imports precede `load_dotenv()`. None of the imported symbols
(`cost`, `model_factory`, `types`, `logging`, `storage`, `tiers`,
`workflow_hash`) read env vars at import time — env-var access happens
inside `build_model()` which runs from `main()` — so `load_dotenv()`
can safely move to the first line of `main()` (or stay at module
level *after* the imports; it still runs before `asyncio.run(main())`
in the bottom `__main__` block). The explanatory comment at
`:30-31` moves with it. No `# noqa` needed.

**Do not** use `# noqa: E402` or add a `scripts/` ruff exclusion —
both hide the underlying ordering choice from future smoke scripts.

### H-2 — `claude_code` subprocess launcher promised to M4 but scoped in zero M4 tasks

**Where the promise is made (four call-sites):**

- `ai_workflows/primitives/llm/model_factory.py:82-85` — "Subprocess launcher lands in M4 with the Orchestrator component."
- `ai_workflows/primitives/llm/model_factory.py:14-18` — same claim in the module docstring.
- `ai_workflows/primitives/tiers.py:67-68` — same claim in the `TierConfig` docstring.
- `design_docs/phases/milestone_1_primitives/README.md:12` — "`claude_code` provider impl lands in M4 with the Orchestrator."
- `tiers.yaml:14-16` — comment reserves the tier names "so the loader AC can be verified".

**Where M4 doesn't scope it:** `grep -r 'claude_code\|claude CLI\|subprocess\|launcher\|Claude Max' design_docs/phases/milestone_4_orchestration/` returns zero matches. The M4 task order (`task_01_planner` → `task_02_agent_loop` → `task_03_orchestrator` → `task_04_human_gate` → `task_05_aiw_resume` → `task_06_ollama_infrastructure`) has no line-item for a CLI launcher.

**Why this is HIGH, not MEDIUM:**

- The entire Planner / Orchestrator design in `milestone_4_orchestration/README.md:22-25` assumes `opus` (Planner) and `sonnet` (AgentLoop implementer) are live runtime tiers. They're not — calling `build_model("opus", ...)` raises `NotImplementedError` today.
- `task_06_ollama_infrastructure.md`'s fallback decision ("On `ConnectionError`: pause run, prompt user to fall back to Haiku") *requires* the `haiku` tier to be a working runtime provider. It isn't.
- Non-trivial design questions are unresolved: (i) does the `claude` CLI report token usage in a parseable form, and if not how does `CostTracker.record()` get its `TokenUsage`? (ii) does the launcher implement pydantic-ai's `Model` ABC or bypass the `Agent.run()` path entirely (which would orphan `run_with_cost`)? (iii) how do per-tier `max_tokens` / `temperature` map onto `claude` CLI flags, which don't accept raw-completion parameters?
- Per CLAUDE.md propagation discipline: "Forward-deferred items must appear as carry-over in the target task before the audit is complete. Without propagation, the target Builder can't see the deferral." M4 has no carry-over.

**Action — Recommendation (user-approved 2026-04-19):**

Front-load design-risk validation with an M1 follow-up spike rather
than defer all of it to M4. Rationale: the user (project owner) flagged
that even though full integration isn't needed until M3/M4,
"scaffolding" that reserves tier names without validating the shape is
optimistic scaffolding. The cost of discovering at M4 that e.g.
`claude -p` can't emit parseable token usage, or that a subprocess
model can't fit pydantic-ai's `Model` ABC, is ripping out tier naming,
pricing config, cost-tracker tagging, and retry-layer assumptions —
roughly a week's rework instead of a day's spike.

**Chosen direction — new M1 task: `task_13_claude_code_spike.md`.**

Scope (non-integration; integration still lands in M4):

1. Document the `claude` CLI surface — does it support non-interactive
   single-shot (`claude -p "..."`), per-call model selection
   (`--model claude-opus-4-7`), deterministic completion exit? What
   auth model (Max session, login cache) does a subprocess inherit?
2. Verify token-usage reporting — does the CLI emit parseable token
   counts (stream-JSON, trailing summary, stderr)? If not, what does
   `CostTracker.record()` receive — a zero `TokenUsage`, a best-effort
   estimate, or does cost-tracking shift to session-cap rather than
   per-call? This is a strategy decision that needs to be made
   deliberately.
3. Decide pydantic-ai `Model` ABC subclass vs. bypass — does a
   subprocess tier subclass `pydantic_ai.Model` (keeping
   `Agent.run()` + `run_with_cost` uniform across tiers), or does it
   bypass the `Agent` path with a parallel runner? The Orchestrator
   downstream wants tier handling to look as uniform as possible.
4. Map `max_tokens` / `temperature` / `system_prompt` onto CLI flags.
   If they don't map, drop the fields from `claude_code` `TierConfig`
   rows or explicitly document them as ignored (and flip the
   `TierConfig` validator so nobody silently ships a `temperature:
   0.2` that has zero effect).
5. Map subprocess failure modes (CLI missing, auth expired,
   rate-limited, sandbox-denied) onto the retry-taxonomy's three
   buckets (retryable-transient / retryable-semantic / non-retryable).

Deliverables (lightweight, not gated at unit level):

- `design_docs/phases/milestone_1_primitives/task_13_claude_code_spike.md` — task spec + findings.
- `scripts/spikes/claude_code_poc.py` — throwaway PoC invoking the
  real `claude` CLI once against each of `opus`/`sonnet`/`haiku` and
  dumping observed behaviour. Excluded from pytest; if ruff
  configuration is needed, a targeted per-file or per-directory
  exclude with a justifying comment in `pyproject.toml`.
- Findings section updating `memory/project_provider_strategy.md` (and
  the MEMORY.md index line — also addresses M-3).
- If the spike finds a blocker, a new HIGH issue + M4 carry-over
  propagation tailored to the chosen recovery path (possibly
  re-introducing `anthropic` provider for the Claude tiers, or
  switching to a session-cap cost model).
- If the spike confirms the shape, a carry-over section appended to
  the eventual M4 implementation task (whichever of M4's existing
  tasks owns the launcher — decided post-spike based on spike
  findings, not pre-spike).

No production code changes to `tiers.py` / `model_factory.py` /
`pricing.yaml` / the existing M4 task files until the spike either
confirms the current shape or motivates a change. H-1's ruff reorder
is bundled into the same implementation pass.

## 🟡 MEDIUM

### M-1 — Exit-criteria text contradicts the Key Decisions table in the same README

**Where:** `design_docs/phases/milestone_1_primitives/README.md:7` vs. `:48`.

- `:7` — "Prompt caching is verified (`cache_read_input_tokens > 0` on turn 2+)."
- `:48` — "Prompt caching | Helpers built (Task 04); Anthropic API only. Not active — Claude tiers run via CLI, not API."

The stated exit criterion is unreachable under the stated architecture.
A future maintainer reading `:7` will not know whether caching is
required for M1 to close, or whether it was already accepted as
permanently N/A.

**Action — Recommendation:** rewrite `:7` to reflect the provider
strategy, e.g. drop the final sentence entirely, or replace with:
"Prompt caching remains architecturally N/A under the Claude-Code-CLI
provider strategy; helpers from Task 04 are retained unexercised for
third-party Anthropic-API deployments." Either way, add a one-line
rationale link back to `memory/project_provider_strategy.md`. No code
change.

### M-2 — `test_cost.py` fixture docstring falsely claims parity with production pricing

**Where:** `tests/primitives/test_cost.py:41-44`.

```python
"""
Matches the canonical ``pricing.yaml`` so the unit values
(``gemini-2.0-flash`` at ``$0.10`` / ``$0.40`` per MTok) stay in
lock-step with production pricing.
"""
```

Canonical `pricing.yaml` is now `gemini-2.5-flash` at $0.30 / $2.50 per
MTok (updated 2026-04-19 after the Gemini 2.0 deprecation was surfaced
by the smoke script). The fixture values did not move with the
production values, so the "lock-step" claim is false.

The test math still passes because the fixture is self-consistent — it
exercises the `calculate_cost()` arithmetic against its own declared
rates. But a reader diagnosing a cost-tracker bug in production will
assume the fixture mirrors production and will be misled.

**Action — Recommendation:** pick one:

- Option A (preferred) — update the fixture rows to
  `"gemini-2.5-flash": ModelPricing(input_per_mtok=0.30, output_per_mtok=2.50)`,
  and adjust the three asserts that bake the unit-cost math
  (`test_cost.py:93-95, :100-102`) to the new rates. Preserves the
  parity claim in the docstring.
- Option B — keep the fixture values but rewrite the docstring to say
  the fixture is intentionally decoupled from production
  ("representative rates, not tracked against `pricing.yaml`") and
  drop the "lock-step" language.

### M-3 — Memory index line and `project_provider_strategy.md` drift

**Where:**

- `~/.claude/projects/-home-papa-jochy-prj-ai-workflows/memory/MEMORY.md:3`
  currently reads: "Claude Code (Max sub) is the dev tool, not a
  runtime provider." The memory it indexes
  (`project_provider_strategy.md`) explicitly lists `opus`/`sonnet`/
  `haiku` as runtime tiers via the `claude_code` provider. The index
  tagline contradicts the file it points to.
- `project_provider_strategy.md:15` still lists `gemini-2.0-flash` and
  the `$0.10/$0.40` price point. Stale since 2026-04-19's bump to
  `gemini-2.5-flash` @ `$0.30/$2.50`.

**Action — Recommendation:** update both in one pass. The index line
should reflect that Claude Code *is* a runtime provider (delivered via
CLI subprocess, M4). The table row for `gemini_flash` should move to
`gemini-2.5-flash` / `$0.30/$2.50`.

## 🟢 LOW

### L-1 — Stale `gemini-2.0-flash` literals in test fixtures

**Where:**

- `tests/primitives/test_types.py:158`
- `tests/primitives/test_retry.py:242`
- `tests/primitives/test_model_factory.py:73`
- `tests/primitives/test_tiers_loader.py:354`
- `tests/primitives/test_cost.py` (18 call-sites — see grep hits)

All use the model id as an opaque string, so the tests pass. Keeping
them aligned with `tiers.yaml` / `pricing.yaml` avoids the "grep for
`gemini-2.0` returns results" confusion when triaging future issues.

**Action — Recommendation:** bulk-rename. If M-2 option A is taken,
the `test_cost.py` renames fold in with that work; otherwise they are
cosmetic-only. Sibling tests (`test_types.py`, `test_model_factory.py`,
`test_retry.py`, `test_tiers_loader.py`) are free renames.

### L-2 — Task 07 spec still shows `gemini-2.0-flash` in example snippets

**Where:** `design_docs/phases/milestone_1_primitives/task_07_tiers_loader.md:65, :96`.

Task 07 is ✅ Complete, so the spec's primary purpose is history. But
someone reading the spec to understand the canonical shape of
`tiers.yaml` / `pricing.yaml` today will see a model id that no longer
loads against any price row.

**Action — Recommendation:** replace both snippets with the current
`gemini-2.5-flash` rows.

### L-3 — Smoke budget-cap branch is architectural theater

**Where:** `scripts/m1_smoke.py:90-96`.

The `BudgetExceeded` branch in `_run_tier` prints "BUDGET CAP FIRED
(expected path)" but cannot fire for a one-turn "2+2" prompt at a
$0.10 cap against `gemini-2.5-flash` (priced at $0.30/$2.50 per MTok;
the cap maps to ~330 000 input or ~40 000 output tokens before
tripping). The Task 12 audit states the cap was "intentionally set
low"; post-bump it is not low relative to the prompt's real cost.

Budget enforcement *is* exercised by `tests/primitives/test_cost.py`
(Task 09 audit AC-2), so M1 is still covered — but the smoke script
is the document that claims "all major functional pieces work" and
it doesn't hit this one.

**Action — Recommendation:** either (a) add a third leg that pre-loads
the cost tracker with a synthetic `$0.10` charge so the next `record()`
trips the cap (exercises the production code path, no real spend), or
(b) drop the `BudgetExceeded` branch and its log lines so the smoke
doesn't advertise coverage it doesn't provide. Option (a) is stronger.

## Additions beyond the per-task scope — audited and justified

| Addition | Rationale |
| --- | --- |
| `scripts/m1_smoke.py` | Not scoped by any M1 task; added after Task 12 to satisfy the milestone-level exit criterion ("LLM call from a Python REPL through our tier system"). Intent is correct; execution has H-1 and L-3 open. |
| `claude_code` provider Literal in `TierConfig` + NotImpl branch in `build_model` | Scoped by Task 03 AC-6 + Task 07; fully pinned by `test_build_model_claude_code_raises_not_implemented` and `test_tier_config_accepts_claude_code_provider`. Valid. |

## Issue log — cross-task follow-up

| ID | Severity | Owner | Status |
| --- | --- | --- | --- |
| M1-EXIT-ISS-01 | 🔴 HIGH | Any — single-commit fix | ✅ RESOLVED 2026-04-19 — bundled into M1 Task 13 AC-7; imports in `scripts/m1_smoke.py` now sit above `load_dotenv()` (env lookups are in function bodies, so load order is irrelevant); `uv run ruff check .` passes. |
| M1-EXIT-ISS-02 | 🔴 HIGH | M1 Task 13 (spike) → then `M4 task_00_claude_code_launcher` | ✅ RESOLVED 2026-04-19 — M1 Task 13 executed; spike confirmed all five architectural assumptions against the real `claude` CLI v2.1.114. Three 🔧 ADJUSTMENTS (Model ABC subclass for text-only, supports_tool_registry capability flag, drop max_tokens/temperature from claude_code rows) propagated to [../../milestone_4_orchestration/task_00_claude_code_launcher.md](../../milestone_4_orchestration/task_00_claude_code_launcher.md). |
| M1-EXIT-ISS-03 | 🟡 MEDIUM | M1 doc maintenance | OPEN — M-1, exit-criteria / Key-Decisions contradiction in README |
| M1-EXIT-ISS-04 | 🟡 MEDIUM | M1 doc / test maintenance | OPEN — M-2, `test_cost.py` docstring vs. fixture drift |
| M1-EXIT-ISS-05 | 🟡 MEDIUM | Memory hygiene | OPEN — M-3, MEMORY.md index line + `project_provider_strategy.md` stale |
| M1-EXIT-ISS-06 | 🟢 LOW | Housekeeping | OPEN — L-1, stale `gemini-2.0-flash` string literals in tests |
| M1-EXIT-ISS-07 | 🟢 LOW | Doc hygiene | OPEN — L-2, Task 07 spec snippets still show retired model |
| M1-EXIT-ISS-08 | 🟢 LOW | Smoke hardening | OPEN — L-3, budget-cap branch unreachable for the current prompt |

## Propagation status

- **M1-EXIT-ISS-02** (H-2) ✅ RESOLVED 2026-04-19 — Task 13 spike
  executed against `claude` CLI v2.1.114 (Max-sub OAuth). All five
  pre-spike assumptions hold (Confirm-path). Three narrow 🔧 ADJUSTMENTS
  propagated to the new M4 task `task_00_claude_code_launcher.md`
  (sequenced before `task_01_planner.md` because the Planner's
  `planning_tier: "opus"` needs the launcher live). M4 README task
  order updated. No architecture rollback needed; no HIGH pivot
  issue opened.
- **M1-EXIT-ISS-01** (H-1) ✅ RESOLVED 2026-04-19 — bundled into
  Task 13 AC-7. `scripts/m1_smoke.py` imports now sit above
  `load_dotenv()`; the env-var loading happens before any function
  body actually reads env vars (all `os.environ.get` calls in
  `ai_workflows.*` are inside function bodies, never at module import
  time), so no semantic change. `uv run ruff check .` passes.
- All other issues (M1-EXIT-ISS-03–08) are local to existing
  artifacts; no forward-propagation needed.

---

**Bottom line:** M1 is functionally complete — the primitives layer
handles all five documented tiers correctly (two live, three raise a
typed, greppable deferral). The *seal* on M1 is blocked on two items:
(a) a 5-minute import-reorder fix for H-1, and (b) a user-level
architecture decision for H-2 about where in M4 the `claude_code`
subprocess launcher lives. Everything else is doc/fixture hygiene.
