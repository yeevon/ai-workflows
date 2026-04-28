# Task 21 — Adaptive-thinking migration (eliminate `thinking: max` literals; per-role `effort` settings)

**Status:** 📝 Planned.
**Grounding:** [milestone README](README.md) · [research brief `research_analysis` §Lens 3.3 (adaptive thinking is the new dial)](research_analysis) · audit recommendation M4 (2026-04-27 grep — 6 hits across `.claude/commands/`) · [Anthropic API docs `whats-new-claude-4-7`](https://docs.claude.com/en/api/whats-new-claude-4-7) · [`.claude/commands/auto-implement.md`](../../../.claude/commands/auto-implement.md) (and 5 sibling slash command files).

## What to Build

Eliminate every `thinking: max` literal directive in `.claude/commands/*.md` (6 confirmed hits via 2026-04-27 grep) and migrate to `thinking: {type: "adaptive"}` plus per-role `effort` settings in agent frontmatter and slash-command frontmatter. Per the research brief Lens 3.3:

- `thinking: {type: "enabled", budget_tokens: N}` is **deprecated** on Opus 4.6 / Sonnet 4.6 and **rejected with HTTP 400** on Opus 4.7.
- `thinking: max` (the older shorthand) is similarly deprecated.
- The replacement is `thinking: {type: "adaptive"}` plus `effort: low | medium | high | max` (plus `xhigh` exclusive to Opus 4.7) as a per-invocation behavioural signal.

T21 is a **forward-compatibility blocker**: T06 (model-dispatch study) includes Opus 4.7 in its 6-cell matrix, and those cells will 400-error during the study without T21 first. T07 (dynamic dispatch) ships dispatch logic that picks Opus 4.7 conditionally; without T21, that dispatch would crash on the first Opus 4.7 invocation.

## Per-role effort assignments

Per research brief Lens 3.3:

| Role | Recommended `effort` | Notes |
|---|---|---|
| Builder (Sonnet 4.6) | `high` | API default `high`; Claude Code's default since Mar 3, 2026 is `medium` (the cause of the widely-reported "Claude Code felt off in March" episode). Explicitly set `high` to avoid regression. |
| Auditor (Opus 4.6 routine) | `high` | Same rationale. |
| Auditor (Opus 4.7 hostile-spec / multi-file drift) | `max` | Hostile-spec analysis is exactly the case for max effort. |
| sr-dev / sr-sdet / security-reviewer (Sonnet 4.6) | `high` | Same as Builder. |
| dependency-auditor (Sonnet 4.6) | `medium` | Mostly mechanical (CVE scan + wheel-contents check). |
| task-analyzer (Opus 4.6) | `high` | Hostile re-read against codebase. |
| architect (Opus 4.6) | `high` (`max` for trigger-A KDR proposals) | Architectural reasoning depth needed. |
| roadmap-selector (Opus 4.6) | `medium` | Sequential walk + 3 filters; not deep reasoning. |
| Sub-agent on Haiku 4.5 | (no `effort` param available) | Use prompt-level brevity directives. |

**Critical rule (research brief §Lens 2.2):** never switch model mid-context. Cache invalidation makes this a footgun. T21 sets effort per-spawn at agent invocation; switching model means spawning a fresh sub-agent, never re-using a context across model boundaries.

## Deliverables

### Slash command frontmatter — migrate `thinking: max` to adaptive + effort

For each of the 6 confirmed hits (`auto-implement.md`, `audit.md`, `clean-tasks.md`, `clean-implement.md`, `queue-pick.md`, `autopilot.md`), replace:

```yaml
---
model: claude-opus-4-7
thinking: max
---
```

with:

```yaml
---
model: claude-opus-4-7
thinking:
  type: adaptive
effort: high
---
```

Effort assignment per slash command:
- `auto-implement` → `effort: high` (orchestrator running multi-cycle Builder→Auditor loops)
- `audit` → `effort: high` (single audit pass)
- `clean-tasks` → `effort: high` (loop + spec-fix application)
- `clean-implement` → `effort: high` (Builder→Auditor loop)
- `queue-pick` → `effort: medium` (sequential walk + 3 filters)
- `autopilot` → `effort: high` (meta-loop orchestrator)

### Agent frontmatter — explicit effort + adaptive

For each of the 9 agent files, add `effort:` + `thinking: { type: adaptive }` to frontmatter per the per-role table above. Today most agents have `model: claude-sonnet-4-6` or `model: claude-opus-4-7` but no explicit `effort` — they rely on Claude Code's default, which has drifted (Mar 3, 2026 default-medium episode). Explicit setting prevents future drift.

### `.claude/commands/_common/effort_table.md` (NEW)

Canonical reference for the per-role effort assignments. Each agent / command frontmatter links to this in a comment.

### Migration verification grep

The smoke test below + the test below verify zero `thinking: max` / `budget_tokens` literals remain.

## Tests

### `tests/orchestrator/test_no_deprecated_thinking_directives.py` (NEW)

Hermetic test:
- `grep -rE "thinking:[[:space:]]*max" .claude/` returns zero hits.
- `grep -rE "budget_tokens" .claude/` returns zero hits (none expected today; future-proof).
- Each slash command frontmatter has `thinking:\n  type: adaptive` and a matching `effort:` line.
- Each agent frontmatter has `thinking:\n  type: adaptive` (or no `thinking:` block at all if the agent runs on Haiku) and a matching `effort:` line where applicable.

### `tests/orchestrator/test_effort_table_consistency.py` (NEW)

Test that `_common/effort_table.md` lists every agent + slash command, and the assigned effort in the table matches the frontmatter.

## Acceptance criteria

1. Zero `thinking: max` literals in `.claude/`. Verified by grep.
2. Zero `budget_tokens` literals in `.claude/`. Verified by grep.
3. All 6 slash command frontmatters use `thinking: { type: adaptive }` + explicit `effort:` per the per-command assignment.
4. All 9 agent frontmatters use `thinking: { type: adaptive }` (where applicable) + explicit `effort:` per the per-role table.
5. `.claude/commands/_common/effort_table.md` exists and matches.
6. `tests/orchestrator/test_no_deprecated_thinking_directives.py` passes.
7. `tests/orchestrator/test_effort_table_consistency.py` passes.
8. CHANGELOG.md updated under `[Unreleased]` with `### Changed — M20 Task 21: Adaptive-thinking migration (eliminate thinking: max; per-role effort settings; research brief §Lens 3.3; required for T06 + T07)`.
9. Status surfaces flip together.

## Smoke test (Auditor runs)

```bash
# Verify zero deprecated literals
test $(grep -rE "thinking:[[:space:]]*max" .claude/ | wc -l) -eq 0 && echo "no thinking:max"
test $(grep -rE "budget_tokens" .claude/ | wc -l) -eq 0 && echo "no budget_tokens"

# Verify each slash command has adaptive thinking
for cmd in auto-implement audit clean-tasks clean-implement queue-pick autopilot; do
  grep -A 2 "^thinking:" .claude/commands/$cmd.md | grep -q "type: adaptive" \
    && echo "$cmd OK" \
    || { echo "$cmd FAIL"; exit 1; }
done

# Run tests
uv run pytest tests/orchestrator/test_no_deprecated_thinking_directives.py tests/orchestrator/test_effort_table_consistency.py -v
```

## Out of scope

- **Empirically tuning effort levels** — T21 sets the research-brief defaults. T06 (study) measures whether the defaults are right; T07 (dispatch) consumes T06's findings. T21 is the *migration*, not the *tuning*.
- **Haiku-specific `effort` parameter** — Haiku 4.5 doesn't expose `effort`. Sub-agents on Haiku get prompt-level brevity directives instead. T21 leaves Haiku frontmatters effort-less.
- **Mid-context effort switching** — out of scope per research brief §Lens 2.2 (cache invalidation footgun). Effort is set per-spawn; effort change requires fresh sub-agent.
- **Documentation of the Mar 3, 2026 Claude Code default-effort episode** — flagged in M20 README §Risk flags; T21 fixes the symptom (explicit effort everywhere) without documenting the historical episode.

## Dependencies

- **None blocking.** T21 is a self-contained migration that unblocks T06 + T07.

## Carry-over from prior milestones

*None.*

## Carry-over from task analysis

(populated by `/clean-tasks m20`)

## Carry-over from prior audits

(populated by `/clean-implement` audit cycles)
