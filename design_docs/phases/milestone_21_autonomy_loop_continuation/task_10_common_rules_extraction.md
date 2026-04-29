# Task 10 — Common-rules extraction (`.claude/agents/_common/`)

**Status:** ✅ Complete.
**Kind:** Slimming / doc.
**Grounding:** [milestone README](README.md) · [research brief §T10 (SUPPORT + EXTEND, item #4)](../milestone_20_autonomy_loop_optimization/research_analysis.md) — line 263, "Common-rules extraction" verdict · [CLAUDE.md](../../../CLAUDE.md) §Non-negotiables · existing per-agent prompt files in `.claude/agents/`. Project memory: `feedback_autonomous_mode_boundaries.md` (8 hard rules locked 2026-04-27 — primary content for the autonomous-mode boundary section of `non_negotiables.md`). M20 close-out (commit `8c6e8a6`) is the post-shipment baseline; T10 is the first M21 win measured against that baseline.

## Why this task exists

Every agent prompt in `.claude/agents/` re-states the same load-bearing rules (no commits, no publish, no `nice_to_have.md` adoption, layer discipline, KDR drift checks, status-surface discipline, ...). These rules are also stated in `CLAUDE.md`. Multi-stating them in 9 agent prompts + 1 root-level `CLAUDE.md` = 10× drift surface. When a non-negotiable changes (e.g. the autonomy-mode boundary update locked 2026-04-27), the operator must remember to update all 10 sites.

T10 extracts the non-negotiables into a single source of truth at `.claude/agents/_common/non_negotiables.md`, and the per-agent verification rules into `.claude/agents/_common/verification_discipline.md`. Each agent prompt declares it follows the shared block instead of inlining it. CLAUDE.md keeps a 1-paragraph summary + section-anchor pointer (slim work happens at T11 — see Dependencies below).

## What to Build

Two new files under `.claude/agents/_common/`:

### File 1 — `.claude/agents/_common/non_negotiables.md`

A single source of truth for the autonomous-mode boundary rules every subagent must follow. Target ≤ 500 tokens (use `wc -w` × 1.3 as a rough word-to-token proxy; tighter accounting via `tiktoken` or the operator's editor token-counter is acceptable). Section content:

1. **Autonomous-mode boundaries (8 hard rules, locked 2026-04-27).** No subagent runs `git commit`, `git push`, `git merge`, `git rebase`, `git tag`, or `uv publish`. Source: project memory `feedback_autonomous_mode_boundaries.md` (faithful summary — only the subagent-relevant rules 1/2/3-decision-rule; remaining rules are operator-side infrastructure not loaded into subagent prompts).

**Other deduplication candidates (scope discipline, layer + KDR discipline, status-surface discipline, read-only file-write discipline, return-schema discipline) are deferred to T11 + T24** because they require coordinated edits across CLAUDE.md and the agent-specific specialisations of those rules — not just a verbatim move. Most agents' restatements of these rules are appropriate agent-specific specialisations (e.g. the Auditor's "HIGH if pulled in without trigger" framing of scope discipline) that should not be collapsed into a single shared block. T10 limits its extraction to the autonomy-boundary section, which is the highest-leverage and cleanest extraction.

### File 2 — `.claude/agents/_common/verification_discipline.md`

Captures the project's verification-discipline rules. Target ≤ 400 tokens. Sections:

1. **Code-task verification is non-inferential.** Build-clean is necessary but not sufficient. Every code task spec names an explicit smoke test the Auditor runs (end-to-end LangGraph run, MCP tool round-trip, CLI invocation, stub-LLM eval). Inferential claims about runtime behaviour from build success alone are HIGH at audit.
2. **Smoke tests must be wire-level.** Tests that pre-register workflows via fixtures or that bypass the published CLI / MCP dispatch path do NOT count as wire-level proof (the 0.3.0 spec-API dispatch regression is the canonical incident).
3. **Real-install release smoke.** Every release runs `aiw` against an `uv pip install dist/*.whl` install in a fresh venv (gate: `tests/release/test_install_smoke.py` + `scripts/release_smoke.sh` Stage 7). Non-skippable.
4. **Gate-rerun discipline.** The Auditor independently runs `uv run pytest`, `uv run lint-imports`, `uv run ruff check` — does not trust the Builder's claim. Captures via the gate-parse-patterns convention (`.claude/commands/_common/gate_parse_patterns.md`).

### Per-agent frontmatter reference

Each agent's prompt file in `.claude/agents/` (9 files: `architect.md`, `auditor.md`, `builder.md`, `dependency-auditor.md`, `roadmap-selector.md`, `security-reviewer.md`, `sr-dev.md`, `sr-sdet.md`, `task-analyzer.md`) gains a frontmatter line or top-of-file declaration referencing the shared blocks:

```markdown
**Non-negotiables:** see [`.claude/agents/_common/non_negotiables.md`](_common/non_negotiables.md) (read in full before first agent action).
**Verification discipline (read-only on source code; smoke tests required):** see [`.claude/agents/_common/verification_discipline.md`](_common/verification_discipline.md).
```

The agent prompt body keeps **only** the agent-specific content (e.g. the auditor's drift-check checklist, the security-reviewer's threat model — those move to dedicated files at T11). **Verbatim inline duplication** of the shared blocks is removed; each agent retains at most a one-line pointer plus an agent-specific specialization tail (e.g. "**No git mutations or publish.** See `_common/non_negotiables.md` Rule 1. <agent-specific tail>"). The shared file is the source of truth; the per-agent tail preserves useful specialization.

## Deliverables

- `.claude/agents/_common/non_negotiables.md` — new file, ≤ 500 tokens.
- `.claude/agents/_common/verification_discipline.md` — new file, ≤ 400 tokens.
- 9 edits to `.claude/agents/*.md` — replace inlined non-negotiables with references to the shared blocks.
- `CHANGELOG.md` updated under `[Unreleased]`.

## Tests / smoke (Auditor runs)

This is a doc-only task. The Auditor's smoke covers four checks:

```bash
# 1. Both shared files exist and are within token budget.
test -f .claude/agents/_common/non_negotiables.md && echo "non_negotiables exists"
test -f .claude/agents/_common/verification_discipline.md && echo "verification exists"

# Token budget proxy: words × 1.3
words_nn=$(wc -w < .claude/agents/_common/non_negotiables.md)
test $((words_nn * 13 / 10)) -le 500 && echo "non_negotiables ≤ 500 tokens (proxy)"

words_vd=$(wc -w < .claude/agents/_common/verification_discipline.md)
test $((words_vd * 13 / 10)) -le 400 && echo "verification ≤ 400 tokens (proxy)"

# 2. Every agent prompt references the shared blocks.
for f in .claude/agents/architect.md .claude/agents/auditor.md \
         .claude/agents/builder.md .claude/agents/dependency-auditor.md \
         .claude/agents/roadmap-selector.md .claude/agents/security-reviewer.md \
         .claude/agents/sr-dev.md .claude/agents/sr-sdet.md \
         .claude/agents/task-analyzer.md; do
  grep -q "_common/non_negotiables.md" "$f" || { echo "FAIL: $f missing reference"; exit 1; }
  grep -q "_common/verification_discipline.md" "$f" || { echo "FAIL: $f missing reference"; exit 1; }
done
echo "all 9 agents reference shared blocks"

# 3. No verbatim autonomy-boundary text inlined in agent prompts.
# Pre-T10 sentinel: every agent prompt inlined "Do not run `git commit`, `git push`...".
# Post-T10 final state: each agent has a one-line pointer + agent-specific specialization
# tail (e.g. "**No git mutations or publish.** See `_common/non_negotiables.md` Rule 1. <tail>").
# This is the intended pattern (per sr-sdet FIX-1 option b, locked terminal decision 2026-04-29):
# the shared file is the source of truth; per-agent tails preserve useful specialization.
# Sentinel: the *pre-T10* literal must be gone; the *post-T10* pointer must be present.
pre_t10=$(grep -lF 'Do not run `git commit`' .claude/agents/*.md | grep -v _common | wc -l)
test "$pre_t10" -eq 0 && echo "pre-T10 verbatim boundary text not inlined"
post_t10=$(grep -lF '_common/non_negotiables.md' .claude/agents/*.md | grep -v _common | wc -l)
test "$post_t10" -eq 9 && echo "all 9 agents reference _common/non_negotiables.md (pointer+tail pattern)"

# 4. Builder agent prompt declares the shared block at least once (sample-agent guard
# against a partially-applied edit; step 2 already covers all 9 agents).
test "$(grep -c '_common/non_negotiables' .claude/agents/builder.md)" -ge 1 \
  && echo "builder.md references _common/non_negotiables ≥ 1 time"
```

## Acceptance criteria

1. `.claude/agents/_common/non_negotiables.md` exists, contains the autonomy-boundary section listed above (faithful summary of subagent-relevant rules from project memory `feedback_autonomous_mode_boundaries.md`), ≤ 500 tokens by the proxy `wc -w × 1.3`.
2. `.claude/agents/_common/verification_discipline.md` exists, contains the four sections listed above, ≤ 400 tokens by the same proxy.
3. All 9 agent prompts in `.claude/agents/` reference both shared files via the prescribed wording (or equivalent — two greps must succeed per smoke-test step 2).
4. No agent prompt **re-states the autonomy-mode boundary text verbatim** after extraction; each agent has at most a one-line pointer + agent-specific specialization tail referencing `_common/non_negotiables.md` (smoke-test step 3: pre-T10 literal absent in 9/9, post-T10 pointer present in 9/9).
5. CHANGELOG.md updated under `[Unreleased]` with `### Added — M21 Task 10: Common-rules extraction (.claude/agents/_common/non_negotiables.md + verification_discipline.md; 9 agent prompts reference shared blocks)`.
6. Status surfaces flip together (spec `**Status:**` line, M21 README task-pool row, README "Done when" checkbox if any).

## Out of scope

- **CLAUDE.md slim.** That's T11. T10 produces the destination files; T11 moves the threat-model + KDR-table + verification-discipline sections out of CLAUDE.md and replaces them with summary + pointer.
- **Extracting the five non-autonomy-boundary non-negotiables.** T10 only extracts autonomy-boundary text + verification discipline; the other five rules (scope discipline, layer + KDR discipline, status-surface discipline, read-only file-write discipline, return-schema discipline) either remain inlined in CLAUDE.md (T11 may slim) or are agent-specific specialisations that should not be deduplicated. Re-evaluate at T11 / T24.
- **Skill extraction.** That's T12.
- **MD-file discoverability audit.** That's T24.
- **Adding new non-negotiables.** T10 only consolidates existing rules. New rules require a new KDR or ADR via the architect agent — not this task.
- **Editing `.claude/commands/_common/`.** Those are command-side shared files (parser conventions, spawn templates) and out of scope here. T10 creates the agent-side `_common/` directory.
- **Runtime code changes.** Per the M21 scope note, M21 changes autonomy infrastructure, not `ai_workflows/`.

## Dependencies

- **Blocks T11.** T11 (CLAUDE.md slim) needs the shared files to exist as the destination for moved content.
- **No prior-task dependencies.** M20 is closed (commit `8c6e8a6`); the autonomy-mode boundaries are stable.

## Carry-over from prior milestones

*None.*

## Carry-over from task analysis

- [x] **TA-LOW-01 — Frontmatter wording is loose** (severity: LOW, source: task_analysis.md round 3 — also surfaced as round-1 L2)
      §Per-agent frontmatter reference (line 36) says "frontmatter line or top-of-body declaration." The agent files use YAML frontmatter for `name`/`description`/`tools`/`model`/`thinking`/`effort`; the example shown is Markdown bold-text body content, not YAML.
      **Recommendation:** Place the two `**Non-negotiables:**` and `**Verification discipline:**` reference lines in the prompt body **immediately after** the YAML frontmatter's closing `---`, not inside the YAML block. Drop the "frontmatter line or" phrasing — there is no YAML field for this content.

## Carry-over from prior audits

(populated by `/clean-implement` audit cycles)
