# Task 23 — Cache-breakpoint discipline (pin on last stable block; verify with 2-call telemetry)

**Status:** ✅ Done (2026-04-28).
**Kind:** Safeguards / code.
**Grounding:** [milestone README](README.md) · [research brief `research_analysis` §Lens 2.2 (cache-invalidation footgun)](research_analysis.md) · anthropics/claude-code issues #27048 / #34629 / #42338 / #43657 (5–20× session-cost blowups from misplaced breakpoints) · sibling [task_22](task_22_per_cycle_telemetry.md) (T23 reads T22's `cache_read_input_tokens` field for verification).

## What to Build

A discipline + verification harness for cache breakpoints in orchestrator + sub-agent invocations, addressing the **highest-impact-per-effort** failure mode in Phase D (per memory thread #10): wrongly-placed cache breakpoints can 5–20× a session's input cost. Per the research brief §Lens 2.2:

> Cache breakpoints must sit on the last *stable* block, not the last block. If your last block is a per-request timestamp, the breakpoint walks backwards finding nothing previously written and forces a full re-cache. Several issues in Claude Code's own issue tracker were exactly this bug: a 1-byte newline difference invalidating a 500K-token prefix.

The breakpoint should pin on:
1. Loaded `_common/non_negotiables.md` (M21 T10 produces this; for M20, use the existing CLAUDE.md prefix).
2. Agent system prompt (the per-agent Markdown body before frontmatter substitution).
3. Tool definitions (Claude Code locks these at startup).

…and **explicitly before** the dynamic per-cycle context (current diff, issue-file content, cycle_summary).

## Mechanism

ai-workflows' Claude Code orchestrator surface doesn't expose cache breakpoints directly — Claude Code manages the cache implicitly. T23 establishes the discipline at the **prompt-construction** layer:

1. Each spawn prompt is structured `<stable prefix>\n\n<dynamic context>`. The orchestrator constructs the spawn prompt by concatenating *first* the stable prefix (agent system prompt + non-negotiables + tool list — these are byte-identical across spawns), *then* the dynamic context (task-specific data).
2. The stable prefix is **byte-stable** across spawns within a session. No timestamps, no per-request UUIDs, no hostname interpolation in the prefix.
3. The dynamic context follows in a separate paragraph after `\n\n`. Claude Code's cache-detection sees the byte-identical prefix and caches it.

### Verification

T22's per-cycle telemetry captures `cache_read_input_tokens` and `cache_creation_input_tokens` per spawn. T23 adds a **2-call verification harness**: spawn the same agent twice in close succession (within the 5-min cache TTL), and assert:

- Spawn 1: `cache_creation_input_tokens` ≈ stable-prefix-token-count, `cache_read_input_tokens` ≈ 0.
- Spawn 2 (within 5 min): `cache_read_input_tokens` ≈ stable-prefix-token-count.

If spawn 2's `cache_read_input_tokens` is 0, the breakpoint is wrong (or cache was invalidated). Surface as a HIGH finding `🚧 Cache breakpoint regression — see runs/<task>/cache_verification.txt`.

## Deliverables

### `.claude/commands/_common/spawn_prompt_template.md` — stable-prefix discipline

(This file is created by T02; T23 extends it.) Add a section "Stable-prefix discipline" that mandates:
- No timestamps, UUIDs, or per-request strings in the prefix.
- Tool list is fixed at session start; never modified mid-session (per research brief §Lens 2.2: adding/removing MCP tools mid-session invalidates the entire conversation cache).
- Agent system prompt (frontmatter + body) is byte-identical between spawns within a session.

### `scripts/orchestration/cache_verify.py` (NEW)

Verification harness. Runs at `/auto-implement` start (or on demand via `/check-cache`) for each agent in the fleet:

```bash
python scripts/orchestration/cache_verify.py --agent auditor --task <task-shorthand>
```

Spawns the named agent twice with identical inputs, reads T22's telemetry, asserts spawn 2's `cache_read_input_tokens` > 80% of stable-prefix-token-count. If not, halts with the HIGH-finding surface.

### `.claude/commands/auto-implement.md` — invoke verifier on cycle 1

Cycle 1 of every `/auto-implement` run kicks off `scripts/orchestration/cache_verify.py` for the agents the run will use (Builder, Auditor, the three reviewers). Verification runs in parallel with cycle 1's Builder spawn; if verification halts, the autopilot loop halts.

### Logging — `runs/<task>/cache_verification.txt`

Verification output captured here for debugging. Spawn-1 + spawn-2 telemetry records inline, plus the stable-prefix token count baseline.

## Tests

### `tests/orchestrator/test_cache_breakpoint_verification.py` (NEW)

Hermetic test of the verification harness:
- Synthetic spawn-1 + spawn-2 with byte-identical prefix → verification passes.
- Synthetic spawn-1 + spawn-2 with prefix containing a per-call timestamp → verification fails (cache_read = 0 on spawn 2).
- Synthetic spawn-1 outside cache TTL (> 5 min gap) → verification skips (TTL boundary, not a regression).

### `tests/orchestrator/test_stable_prefix_construction.py` (NEW)

- Constructed spawn prompts have no timestamps, UUIDs, hostname strings in the prefix segment.
- Stable prefix and dynamic context are separated by `\n\n` (cache-friendly boundary).

## Acceptance criteria

1. `.claude/commands/_common/spawn_prompt_template.md` has the stable-prefix discipline section (T23 extends T02's file).
2. `scripts/orchestration/cache_verify.py` exists with the 2-call harness.
3. `.claude/commands/auto-implement.md` invokes the verifier on cycle 1.
4. Verification halt-surface fires correctly on prefix-instability.
5. `tests/orchestrator/test_cache_breakpoint_verification.py` passes.
6. `tests/orchestrator/test_stable_prefix_construction.py` passes.
7. Empirical validation: re-run M12 T01 audit cycle with T23 in place; assert spawn 2's `cache_read_input_tokens` is > 80 % of stable-prefix-token-count.
8. CHANGELOG.md updated under `[Unreleased]` with `### Added — M20 Task 23: Cache-breakpoint discipline (stable-prefix construction + 2-call verification harness; addresses anthropics/claude-code #27048 / #34629 / #42338 / #43657 5–20× session-cost blowup failure mode)`.
9. Status surfaces flip together.

## Smoke test (Auditor runs)

```bash
# Verify scripts/orchestration/cache_verify.py exists and runs
test -x scripts/orchestration/cache_verify.py || test -f scripts/orchestration/cache_verify.py && echo "cache_verify exists"

# Verify spawn-prompt template has stable-prefix discipline
grep -q "stable-prefix\|Stable-prefix discipline" .claude/commands/_common/spawn_prompt_template.md \
  && echo "discipline OK"

# Verify auto-implement invokes the verifier on cycle 1
grep -q "cache_verify.py\|Cache-breakpoint verification" .claude/commands/auto-implement.md \
  && echo "auto-implement integration OK"

# Run cache-discipline tests
uv run pytest tests/orchestrator/test_cache_breakpoint_verification.py tests/orchestrator/test_stable_prefix_construction.py -v
```

## Out of scope

- **Cache breakpoints in the ai_workflows runtime package** — out of scope. ai-workflows' runtime calls Claude Code via subprocess (KDR-003); cache management is Claude Code's concern, not ai-workflows runtime's.
- **Cross-session cache reuse** — out of scope. Cache TTL is 5 min (or 1 hr with `extended-cache-ttl-2025-04-11` header); cross-session reuse is a Claude Code feature ai-workflows doesn't directly invoke.
- **Mid-context tool-list modification protection** — flagged as anti-pattern in `_common/spawn_prompt_template.md`; T23 documents the rule but doesn't enforce programmatically (Claude Code locks the tool list at startup, so the rule is enforced by the platform).
- **Manual `/clear` / `/compact` invocations** — out of scope for verification. Those are user-initiated; T23 verifies orchestrator-side breakpoint discipline, not user-initiated cache events.

## Dependencies

- **T22** (per-cycle telemetry) — **blocking**. T23's verification harness reads T22's `cache_read_input_tokens` records.
- **T02** (input prune) — strongly precedent. T02 establishes `_common/spawn_prompt_template.md`; T23 extends it with stable-prefix rules.

## Carry-over from prior milestones

*None.*

## Carry-over from task analysis

(populated by `/clean-tasks m20`)

## Carry-over from prior audits

(populated by `/clean-implement` audit cycles)
