# Task 11 — CLAUDE.md slim

**Status:** ✅ Done.
**Kind:** Slimming / doc.
**Grounding:** [milestone README](README.md) · [research brief §T11 (STRONGLY SUPPORT, item #3)](../milestone_20_autonomy_loop_optimization/research_analysis.md) · [CLAUDE.md](../../../CLAUDE.md) (current, 136 lines) · [T10 spec](task_10_common_rules_extraction.md) (T11 absorbs T10's four advisory carry-overs) · [T10 issue file](issues/task_10_issue.md) M21-T10-ISS-03.

## Why this task exists

CLAUDE.md is loaded into every conversation. At 136 lines it carries content that's only relevant to specific subagents (full threat model is for `security-reviewer`; full KDR table is drift-check material for `auditor` + `task-analyzer` + `architect` + `dependency-auditor`; verification discipline is now in `_common/verification_discipline.md`). The cost is paid every conversation, including those that don't spawn the relevant subagent.

T11 moves agent-specific content out of CLAUDE.md and into the agents that actually read it, leaving a one-paragraph summary + section-anchor pointer in CLAUDE.md so main-context Claude can answer ad-hoc questions without spawning a subagent. Exit criterion G1 requires ≥ 30% line reduction (i.e. ≤ 95 lines, since current is 136).

## What to Build

### Move 1 — Threat model

**Source:** CLAUDE.md §Threat model (lines 85–97).

**Destination:** `.claude/agents/security-reviewer.md` — append as a `## Threat model` section after the agent's existing system-prompt body. Verify the agent's existing prompt does not already duplicate the content; if it does, replace inline with the moved authoritative version.

**Replacement in CLAUDE.md:** one-paragraph summary + anchor link. Suggested wording:
```markdown
## Threat model

ai-workflows is single-user, local-machine, MIT-licensed. Two real attack surfaces: (1) the published wheel on PyPI, (2) subprocess execution (Claude Code OAuth, Ollama HTTP at localhost, LiteLLM dispatch). No multi-user surface, no untrusted network. Generic web-app concerns are noise. **Full threat model + finding categories: see [`.claude/agents/security-reviewer.md#threat-model`](.claude/agents/security-reviewer.md#threat-model).**
```

### Move 2 — Seven-KDR table

**Source:** CLAUDE.md §Grounding §Load-bearing KDRs (lines 39–50, the `| KDR | Rule |` table).

**Destination:** identical copy appended to each of `.claude/agents/auditor.md`, `.claude/agents/task-analyzer.md`, `.claude/agents/architect.md`, `.claude/agents/dependency-auditor.md` as a `## Load-bearing KDRs (drift-check anchors)` section. These are the four agents that use the KDR table as a drift-check anchor; the other 5 agents (builder/sr-dev/sr-sdet/security-reviewer/roadmap-selector) reference KDRs by ID via `_common/non_negotiables.md` (or already inline a relevant subset) and do not need the full table.

**Replacement in CLAUDE.md:** the table summary line plus an anchor link to one canonical copy:
```markdown
### Load-bearing KDRs (seven, as of 0.2.0)

The seven load-bearing KDRs are 002 (MCP-as-substrate), 003 (no Anthropic API), 004 (validator pairing), 006 (three-bucket retry via RetryingEdge), 008 (FastMCP + pydantic schema), 009 (SqliteSaver-only checkpoints), 013 (user-owned external workflow code). The Auditor uses these as drift-check anchors. **Full table: see [`.claude/agents/auditor.md#load-bearing-kdrs-drift-check-anchors`](.claude/agents/auditor.md#load-bearing-kdrs-drift-check-anchors).** (Identical copies live in `task-analyzer.md`, `architect.md`, `dependency-auditor.md`.)
```

### Move 3 — Verification discipline (already in `_common/verification_discipline.md`)

T10 already created `.claude/agents/_common/verification_discipline.md`. CLAUDE.md still inlines the same rules under §Non-negotiables. T11 removes them from CLAUDE.md and replaces with a pointer:
```markdown
- **Verification discipline.** Code-task verification is non-inferential (build-clean is necessary, not sufficient); smoke tests must be wire-level; real-install release smoke is non-skippable. **Full rules: see [`.claude/agents/_common/verification_discipline.md`](.claude/agents/_common/verification_discipline.md).**
```

### Move 4 — Slash-command bullet list

**Source:** CLAUDE.md lines 5–11 (six slash-command one-liners — `/clean-tasks`, `/clean-implement`, `/auto-implement`, `/queue-pick`, `/autopilot`, `/implement`, `/audit`).

**Destination:** content already lives in `.claude/commands/*.md` (canonical per-command procedure files).

**Replacement in CLAUDE.md:** one line:
```markdown
Step-by-step procedures live in `.claude/agents/` (subagents) and `.claude/commands/` (slash commands — `/clean-tasks`, `/clean-implement`, `/auto-implement`, `/queue-pick`, `/autopilot`, `/implement`, `/audit`).
```

### Move 5 — Subagent bullet list

**Source:** CLAUDE.md lines 13–23 (10 subagent one-liners — `task-analyzer`, `builder`, `auditor`, `security-reviewer`, `dependency-auditor`, `architect`, `roadmap-selector`, `sr-dev`, `sr-sdet`).

**Destination:** content already lives in `.claude/agents/*.md`.

**Replacement in CLAUDE.md:** one line, names the agents inline:
```markdown
Subagents under `.claude/agents/`: `task-analyzer`, `builder`, `auditor`, `security-reviewer`, `dependency-auditor`, `architect`, `roadmap-selector`, `sr-dev`, `sr-sdet`. Each agent's procedure lives in its own file.
```

### Move 6 — Builder + Auditor mode summaries

**Source:** CLAUDE.md lines 71–81 (Builder mode + Auditor mode one-paragraph summaries).

**Destination:** content already lives in `.claude/agents/builder.md` and `.claude/agents/auditor.md` (both files have the canonical full procedure).

**Replacement in CLAUDE.md:** two lines:
```markdown
- **Builder mode** — see [`.claude/agents/builder.md`](.claude/agents/builder.md).
- **Auditor mode** — see [`.claude/agents/auditor.md`](.claude/agents/auditor.md).
```

### Net line-count math

| Move | Source lines | Replacement lines | Net Δ |
| ---- | ------------ | ----------------- | ----- |
| 1. Threat model | 11 | 4 | -7 |
| 2. KDR table | 13 | 4 | -9 |
| 3. Verification discipline | 2 | 1 | -1 |
| 4. Slash-command bullet list | 7 | 1 | -6 |
| 5. Subagent bullet list | 10 | 1 | -9 |
| 6. Builder + Auditor summaries | 10 | 2 | -8 |
| **Total** | **53** | **13** | **-40** |

Starting from 136 lines, target after T11: ~96 lines. Smoke step 1's `wc -l ≤ 95` is satisfiable at the upper end; if the moves shrink slightly more on inspection, we land below 95 cleanly. If a Builder finds the math undershoots by 1–2 lines, an additional one-line tightening on §Repo layout (lines 54–69 — could compress the bulleted layered-subpackages list by one line) is in scope.

### T10 carry-over absorption

Apply M21-T10-ISS-03 in the same task, since T11 is already rewriting the relevant agent-prompt content:

1. **Sr. Dev ADV-1** — strip the `**No git mutations or publish.**` preamble from each agent's body line that points to `_common/non_negotiables.md` Rule 1; retain only the agent-specific consequence + a "Rule 1 applies." pointer. Example: `builder.md:39` becomes `- **Commit discipline.** Cite the planned commit message in your report (per existing rule), but do not commit. _common/non_negotiables.md Rule 1 applies.`
2. **Sr. Dev ADV-2** — restore the `(read-only on source code; smoke tests required)` parenthetical on each agent's `**Verification discipline:**` reference line. Edit pattern: `**Verification discipline:**` → `**Verification discipline (read-only on source code; smoke tests required):**`.
3. **Sr. SDET ADV-2** — record per-agent prompt sizes (`wc -w .claude/agents/*.md`) in T11's issue file as a baseline for future slimming; no enforced budget yet.

(Sr. SDET ADV-1 — "smoke step 4 redundancy" — was Auditor-context only and does not require a downstream-task edit; T10 is shipped TERMINAL CLEAN at commit `2f73143` and is not retroactively edited.)

## Deliverables

- Edits to `CLAUDE.md` — apply six moves above (threat-model, KDR table, verification-discipline, slash-command list, subagent list, builder/auditor summaries); each replaced with summary/anchor or pointer; final `wc -l CLAUDE.md` ≤ 95.
- Append `## Threat model` to `.claude/agents/security-reviewer.md`.
- Append `## Load-bearing KDRs (drift-check anchors)` to `.claude/agents/auditor.md`, `task-analyzer.md`, `architect.md`, `dependency-auditor.md`.
- 9 edits to `.claude/agents/*.md` for ADV-1 + ADV-2 carry-over.
- Edit M21 README §Exit criteria §G1 prose to record T11 satisfaction + final CLAUDE.md line count (per AC9c).
- `CHANGELOG.md` updated under `[Unreleased]`.
- T11 issue file gets per-agent `wc -w` baseline (Sr. SDET ADV-2).

## Tests / smoke (Auditor runs)

Each smoke step uses one Bash invocation and avoids `$(...)` command-substitution + parameter expansion inside loop bodies (per `_common/verification_discipline.md` §Bash-safety rules — those patterns trip the harness's shell-injection heuristic and break unattended autonomy).

```bash
# 1. CLAUDE.md ≥ 30% line reduction (was 136 → target ≤ 95). Visual + assertion in two steps.
wc -l CLAUDE.md
# Threshold check (separate call):
awk 'END { exit !(NR <= 95) }' CLAUDE.md && echo "CLAUDE.md ≤ 95 lines (≥ 30% reduction from 136)"

# 2. Each removed section has a summary + anchor pointer in CLAUDE.md.
grep -q "security-reviewer.md#threat-model" CLAUDE.md && echo "threat-model anchor present"
grep -q "auditor.md#load-bearing-kdrs" CLAUDE.md && echo "kdr-table anchor present"
grep -q "_common/verification_discipline.md" CLAUDE.md && echo "verification-discipline pointer present"

# 3. Threat model lives in security-reviewer.md.
grep -q "^## Threat model" .claude/agents/security-reviewer.md && echo "threat-model section in security-reviewer.md"

# 4. KDR table copied to each of the four drift-check agents (unrolled, no loop body).
grep -q "^## Load-bearing KDRs" .claude/agents/auditor.md && echo "auditor.md has KDR table"
grep -q "^## Load-bearing KDRs" .claude/agents/task-analyzer.md && echo "task-analyzer.md has KDR table"
grep -q "^## Load-bearing KDRs" .claude/agents/architect.md && echo "architect.md has KDR table"
grep -q "^## Load-bearing KDRs" .claude/agents/dependency-auditor.md && echo "dependency-auditor.md has KDR table"

# 5. T10 ADV-1 absorbed: no agent body retains the `**No git mutations or publish.**` preamble.
# Capture file list first; assert count separately.
grep -lF '**No git mutations or publish.**' .claude/agents/architect.md .claude/agents/auditor.md .claude/agents/builder.md .claude/agents/dependency-auditor.md .claude/agents/roadmap-selector.md .claude/agents/security-reviewer.md .claude/agents/sr-dev.md .claude/agents/sr-sdet.md .claude/agents/task-analyzer.md > /tmp/aiw_t11_adv1.txt
# Empty file = ADV-1 absorbed; non-empty = preamble still present.
awk 'END { exit !(NR == 0) }' /tmp/aiw_t11_adv1.txt && echo "ADV-1: preamble stripped from all 9 agents"

# 6. T10 ADV-2 absorbed: parenthetical restored on `**Verification discipline:**` reference line.
grep -lF '**Verification discipline (read-only on source code; smoke tests required):**' .claude/agents/architect.md .claude/agents/auditor.md .claude/agents/builder.md .claude/agents/dependency-auditor.md .claude/agents/roadmap-selector.md .claude/agents/security-reviewer.md .claude/agents/sr-dev.md .claude/agents/sr-sdet.md .claude/agents/task-analyzer.md > /tmp/aiw_t11_adv2.txt
awk 'END { exit !(NR == 9) }' /tmp/aiw_t11_adv2.txt && echo "ADV-2: parenthetical restored in 9/9 agents"

# 7. T10 invariant: pointer to `_common/non_negotiables.md` present in 9/9 agents.
grep -lF '_common/non_negotiables.md' .claude/agents/architect.md .claude/agents/auditor.md .claude/agents/builder.md .claude/agents/dependency-auditor.md .claude/agents/roadmap-selector.md .claude/agents/security-reviewer.md .claude/agents/sr-dev.md .claude/agents/sr-sdet.md .claude/agents/task-analyzer.md > /tmp/aiw_t11_t10inv.txt
awk 'END { exit !(NR == 9) }' /tmp/aiw_t11_t10inv.txt && echo "T10 pointer invariant held (9/9)"
```

## Acceptance criteria

1. `wc -l CLAUDE.md` returns a value ≤ 95 (≥ 30% reduction from 136).
2. CLAUDE.md retains a one-paragraph summary + anchor link for each of: threat model, KDR table, verification discipline.
3. `security-reviewer.md` has the full `## Threat model` section.
4. `auditor.md`, `task-analyzer.md`, `architect.md`, `dependency-auditor.md` each carry the full `## Load-bearing KDRs (drift-check anchors)` table.
5. ADV-1 absorbed (smoke step 5 = 0).
6. ADV-2 absorbed (smoke step 6 ≥ 9).
7. T10 invariant held (smoke step 7 = 9 — `_common/non_negotiables.md` pointer present).
8. CHANGELOG.md updated under `[Unreleased]` with `### Changed — M21 Task 11: CLAUDE.md slim (..., ADV-1/2 absorbed from T10)`.
9. Status surfaces flip together: (a) T11 spec `**Status:**` line moves from `📝 Planned` to `✅ Done`, (b) M21 README task-pool row 71 Status column moves from `📝 Candidate` to `✅ Done`, (c) M21 README §Exit criteria §G1 prose is amended in-place to record that CLAUDE.md slim landed (e.g. add a parenthetical `(satisfied at T11; CLAUDE.md is now N lines)`).

## Out of scope

- **Skill extraction (`.claude/skills/...`)** — that's T12.
- **MD-file discoverability audit** — that's T24.
- **Removing the seven-KDR _content_ from architecture.md §9** — T11 only deduplicates the *table copy* in CLAUDE.md; architecture.md §9 remains the canonical source.
- **Editing T10's already-shipped spec smoke** — T11 may absorb the cosmetic fix as Sr. SDET ADV-1, but it's optional. T10 ships in its current form regardless.
- **Adding new non-negotiables.** Pure consolidation only.
- **Runtime code changes.** Per the M21 scope note.

## Dependencies

- **Blocks T12.** T12 (Skills extraction) builds on the slimmed CLAUDE.md.
- **Built on T10.** Requires `_common/non_negotiables.md` and `_common/verification_discipline.md` from T10 (✅ shipped, commit `2f73143`).

## Carry-over from prior milestones

*None.*

## Carry-over from prior audits

*None at draft time. Populated if a Builder cycle's audit surfaces forward-deferred items.*

## Carry-over from task analysis

- [x] **TA-LOW-01 — Move-table cosmetic numbers** (severity: LOW, source: task_analysis.md round 5 / T11 round 2)
      Move 1 cites lines 85–97 (actual 85–94 + divider 96); Move 2 cites lines 39–50 (heading at 38 → spans 38–50); Move 5 says "10 subagent one-liners" but enumerates 9 names (the 10th is the leading "Subagents:" header). Smoke verifies the global threshold so cosmetic.
      **Recommendation:** Builder may correct the cosmetic numbers in the Move-table while applying the moves; if not corrected, no functional impact.

- [x] **TA-LOW-02 — Move 1 instruction sequencing** (severity: LOW, source: task_analysis.md round 5)
      `.claude/agents/security-reviewer.md` line 21 already carries a `## Threat model (read first)` stub header. The Move 1 instruction reads as "append → discover duplicate → replace," which is workable but indirect.
      **Recommendation:** Builder treats this as "replace the existing `## Threat model (read first)` stub (line 21 + any body) with the full moved-from-CLAUDE.md content; rename heading to `## Threat model` (drop `(read first)`) so the section lands once with the canonical title."

- [x] **TA-LOW-03 — AC9c may also tighten G1's tautological grep example** (severity: LOW, source: task_analysis.md round 5)
      M21 README §Exit criteria §G1 currently includes `grep -c "^## " CLAUDE.md confirms each removed section has a placeholder summary + anchor link` — a tautological test (a count of `##` headings doesn't prove anchor links exist).
      **Recommendation:** Builder may optionally replace that grep example with one that actually verifies anchor presence (e.g. `grep -q "security-reviewer.md#threat-model" CLAUDE.md`); satisfaction parenthetical is the load-bearing edit.
