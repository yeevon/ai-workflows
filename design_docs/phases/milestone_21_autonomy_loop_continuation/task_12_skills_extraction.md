# Task 12 — Skills extraction (`.claude/skills/dep-audit/`)

**Status:** 📝 Planned.
**Kind:** Slimming / code + doc.
**Grounding:** [milestone README](README.md) · [research brief §T12 (SUPPORT + MODIFY, item #1)](../milestone_20_autonomy_loop_optimization/research_analysis.md) — line 269, "Skills extraction (per-agent capabilities — test-quality eval, dep-audit shortcuts)" verdict, plus line 145 ("T12 (Skills extraction) aligns directly with Anthropic's Agent Skills pattern"). · [T24 spec](task_24_md_discoverability.md) (✅ Done — rubric-conformant `.claude/agents/*.md` is the substrate Skills' progressive disclosure depends on) · [existing Skill](../../../.claude/skills/ai-workflows/SKILL.md) (one prior Skill — `ai-workflows` — establishes the SKILL.md frontmatter shape). KDR drift checks apply per M21 scope note (autonomy-infra task; no direct KDR citation needed).

## Why this task exists

Anthropic's Agent Skills pattern (Oct 2025, expanded through 2026) demonstrates progressive disclosure at scale: at session start only ~100 tokens of Skill metadata enter context; the full SKILL.md (≤ 5K tokens) loads only when triggered; helper files load only when needed. The ai-workflows project has agent capabilities (e.g. dep-audit shortcuts, test-quality eval, wheel-contents check) that are currently inlined into agent prompts — every spawn pays the full cost regardless of whether the capability fires.

T12 establishes the Skills extraction pattern by extracting **one concrete capability** (`dep-audit-shortcuts`) from `dependency-auditor.md` into `.claude/skills/dep-audit/SKILL.md`. The pattern serves as the template for future extractions (test-quality eval, wheel-contents check, threat-model walk, etc.) which are explicitly out of scope for T12. Phase F's productivity-command Skills (T13–T16) are also out of scope — those add *new* surfaces; T12 *extracts* existing capabilities.

The minimum-viable scope keeps T12 small enough to ship in 1–2 cycles while still proving the pattern works. Future T12-shaped tasks land as `task_<NN>_skills_extraction_<capability>.md` once the pattern is locked.

## Skill structure (locked at T12)

Every Skill under `.claude/skills/` must satisfy:

1. **Canonical SKILL.md frontmatter.** `name:` (kebab-case, matches dir name) and `description:` (≤ 200 chars, leads with the routing trigger — "Use when...", "Run when..."). The `description:` is the routing key Claude reads at session start; it must be tight and trigger-led so routing is unambiguous.
2. **Body ≤ 5K tokens.** SKILL.md body covers: when to use, when NOT to use, the procedure (step-by-step), and references to helper files. Helper files (e.g. `runbook.md`, `checks.py`) live alongside SKILL.md and load only when the Skill body's body references them.
3. **Body references helper files; does NOT inline them.** Per Anthropic's progressive-disclosure pattern. If an inline code block exceeds 20 lines, move it to a helper file or a `src/foo.py:line` reference (same rubric as T24's discoverability rule 4).
4. **No silent agent-prompt duplication.** When a Skill is extracted from an agent prompt, the agent prompt must replace the inlined capability with a one-line pointer ("**Dep-audit shortcuts.** See `.claude/skills/dep-audit/SKILL.md`."), not silently retain both copies. T10's `_common/` pattern is the precedent.

The structure applies to T12's `.claude/skills/dep-audit/` and is the template downstream Skills follow.

## What to Build

### Step 1 — Define the dep-audit-shortcuts Skill

Identify the dep-audit capability already present in `.claude/agents/dependency-auditor.md`. The capability covers (verify against on-disk content before extraction):

- Pre-publish wheel-contents check: `uv build` then `unzip -l dist/*.whl` — must contain only `ai_workflows/` + `LICENSE` + `README.md` + `CHANGELOG.md`.
- `pyproject.toml` / `uv.lock` change-detection (triggers full dep audit).
- Lockfile-diff inspection on dep bumps (`uv lock` differential).
- CVE-shape findings (categories: install-time RCE, wheel leakage).

The Skill body codifies the procedure as a recipe card, not as a copy-paste of the agent prompt's full review-discipline material. Behavioral rules and threat model stay in the agent prompt (`dependency-auditor.md`). The Skill is the *operational shortcut* — it tells Claude (in any context) how to run the wheel-contents check and parse its output.

### Step 2 — Create `.claude/skills/dep-audit/SKILL.md`

Sections:

```markdown
---
name: dep-audit
description: Run the ai-workflows pre-publish wheel-contents check and dep-manifest change-detection. Use before `uv publish`, when pyproject.toml or uv.lock change, or for wheel-contents audits.
---

# dep-audit

The dep-audit Skill runs the pre-publish wheel-contents check (`uv build` + `unzip -l dist/*.whl`).
It also handles dep-manifest change-detection on any `pyproject.toml` or `uv.lock` diff.
Helper file `runbook.md` carries the long-form assertion lists, error-message catalog, and edge cases.

## When to use

- Before any `uv publish` invocation (wheel contents must be clean — see `runbook.md` §pre-publish).
- When `pyproject.toml` or `uv.lock` change in a commit (dep-audit gate per CLAUDE.md non-negotiable).
- When the user asks "what's in the wheel?" or "is this dep new?" or "audit the lockfile bump".

## When NOT to use

- Full threat-model review of a code change → use `security-reviewer` agent instead.
- CVE database lookup for a single dep → use `dependency-auditor` agent's Tier-A check.
- Internal dep updates (e.g. `tiktoken` patch bump with no API change) — that's the regular `dependency-auditor` flow, not this Skill.

## Procedure

1. Wheel-contents check (pre-publish):
   - Run `uv build`.
   - Inspect with `unzip -l dist/*.whl` — see `runbook.md` §wheel-contents for the full assertion list.
   - **HALT** on any unexpected file: `.env*`, `design_docs/`, `runs/`, `*.sqlite3`, `.claude/`, `htmlcov/`.

2. Dep-manifest change-detection (per-commit):
   - `git diff <pre-task>..HEAD pyproject.toml uv.lock` — see `runbook.md` §dep-detection.
   - On any non-zero diff, the dep-audit gate fires; spawn the `dependency-auditor` agent.

3. Lockfile-diff inspection (on bump):
   - `uv lock --diff` — see `runbook.md` §lockfile-diff for parsing patterns.

## Helper files

- `runbook.md` — full assertion lists, error-message catalog, edge cases.

## Pointers

- Threat model: `.claude/agents/security-reviewer.md#threat-model`.
- Full dep-audit procedure: `.claude/agents/dependency-auditor.md`.
```

The body is ≤ 5K tokens; helper file `runbook.md` carries the long-form details.

### Step 3 — Create `.claude/skills/dep-audit/runbook.md`

Top-of-file 3-line summary (per T24 rubric rule 1, applied transitively): one physical line per concrete procedure (wheel-contents, dep-detection, lockfile-diff). Suggested wording:

```
The runbook details wheel-contents inspection — the file allowlist (ai_workflows/, LICENSE, README.md, CHANGELOG.md) and denylist (.env, design_docs/, runs/, *.sqlite3).
It documents dep-manifest change-detection — `git diff <pre-task>..HEAD pyproject.toml uv.lock` semantics and the trigger threshold for the dep-audit gate.
It describes lockfile-diff inspection — `uv lock --diff` parsing patterns for `+ added`, `- removed`, `~ bumped` entries.
```

Then sections (each ≤ 500 tokens per T24's discoverability rubric, applied transitively):

- `## Wheel-contents` — full assertion list (file allowlist, denylist with rationale per file pattern).
- `## Dep-detection` — `git diff` invocation form, exit-code semantics.
- `## Lockfile-diff` — `uv lock --diff` parsing patterns (`+ added`, `- removed`, `~ bumped`).

Include real example outputs, not synthetic ones. Keep the prose tight.

### Step 4 — Update `dependency-auditor.md` agent prompt (surgical-edit list)

The dep-audit material in `dependency-auditor.md` is scattered across multiple sites. T12 makes **only the edits enumerated below**; all other content is preserved verbatim:

1. **Add a new `## Operational shortcuts` section** at the bottom of the agent body (after existing sections, before the `## Load-bearing KDRs` table). Body:
   ```markdown
   ## Operational shortcuts

   The pre-publish wheel-contents check and dep-manifest change-detection procedure live in the dep-audit Skill at `.claude/skills/dep-audit/SKILL.md`. The Skill is invocable in main context (e.g. during `/autopilot` or future `/check`) without spawning this agent. The agent retains threat-model framing, severity grading, and final-verdict authority; the Skill carries the operational shortcut.
   ```
2. **Leave the frontmatter `description:` line unchanged** — it's the agent-routing key and references both wheel-contents and dep-audit at the agent level (correct).
3. **Leave the §"What actually matters — wheel" section unchanged** — that's *threat framing*, which stays in the agent (per spec §Why this task exists "Behavioral rules and threat model stay in the agent prompt").
4. **Leave the §"Commands you can run" section unchanged** — those are commands the agent may invoke during its own review; they are not the Skill's operational shortcuts.
5. **Leave the §Output format issue-file template unchanged** — that's the agent's deliverable shape, separate from the Skill.

The Skill is the *operational shortcut* invocable in main context; the agent retains everything it had before, plus the new pointer section. Behavior is preserved — the agent still owns threat-model framing, severity grading, and final verdict.

### Step 5 — Document the extraction pattern

Create new file `.claude/agents/_common/skills_pattern.md` carrying the Skill-extraction pattern documentation. This is a separate topic from autonomous-mode boundaries (T24 rubric rule 5: one topic per file), so it lives in its own file regardless of token budget. The file follows T24's discoverability rubric end-to-end (3-line summary, `##` anchors, ≤500-token sections, no inline code > 20 lines, one topic per file).

Top-of-file 3-line summary: one line per pattern aspect (when, structure, validation).

Sections (each ≤ 500 tokens, `##` anchors per T24 rule 2):

- **`## When to extract`** — one paragraph. Criteria for promoting an agent capability into a Skill: reusable across contexts (not agent-specific behavior), has a tight description (≤ 200 chars, trigger-led), helper files worth deferring under progressive disclosure.
- **`## The 4-rule Skill structure`** — bullet list. Frontmatter with `name:` + ≤200-char trigger-led `description:`; body ≤5K tokens; helper-file references rather than inlined code; no silent agent-prompt duplication.
- **`## How to validate`** — one paragraph. Omit-the-Skill operator-side test (research-brief §T12 — anchor: `T12 — Skills extraction (per-agent capabilities`). Operator-runnable, not Auditor-gated.

Future T12-shaped tasks (test-quality eval, threat-model walk, etc.) follow this pattern by reference.

## Deliverables

- `.claude/skills/dep-audit/SKILL.md` — new file (≤ 5K tokens).
- `.claude/skills/dep-audit/runbook.md` — new file (each `##` section ≤ 500 tokens per T24 rubric).
- Edits to `.claude/agents/dependency-auditor.md` — add a `## Operational shortcuts` section pointing to the Skill (per surgical-edit list in §Step 4).
- New file `.claude/agents/_common/skills_pattern.md` — Skill-extraction pattern documentation.
- `CHANGELOG.md` updated under `[Unreleased]`.
- M21 README — add new exit criterion §G6 covering Skill extraction (text suggested: `**(G6)** At least one extraction Skill (e.g. dep-audit) lands in M21; pattern locked for downstream extractions. Test: SKILL.md frontmatter + body ≤5K tokens + helper file present + agent prompt references the Skill.`) AND amend G6 prose in-place at T12 close-out with a satisfaction parenthetical naming `dep-audit` as the extracted Skill. (G3 — productivity-command Skills — is T13–T16's lane, not T12's.)

## Tests / smoke (Auditor runs)

```bash
# 1. Skill files exist and frontmatter is well-formed.
test -f .claude/skills/dep-audit/SKILL.md && echo "SKILL.md exists"
test -f .claude/skills/dep-audit/runbook.md && echo "runbook.md exists"

# 2. SKILL.md frontmatter has name + description; description ≤ 200 chars.
grep -qE '^name: dep-audit$' .claude/skills/dep-audit/SKILL.md && echo "name field correct"
grep -qE '^description: ' .claude/skills/dep-audit/SKILL.md && echo "description field present"
desc=$(grep -m1 '^description: ' .claude/skills/dep-audit/SKILL.md | sed 's/^description: //')
test ${#desc} -le 200 && echo "description ≤ 200 chars (was ${#desc})"

# 3. SKILL.md body ≤ 5K tokens (proxy: words × 1.3 ≤ 5000 i.e. ≤ 3846 words).
words_skill=$(wc -w < .claude/skills/dep-audit/SKILL.md)
test $((words_skill * 13 / 10)) -le 5000 && echo "SKILL.md ≤ 5K tokens"

# 4. T24 rubric holds transitively for `.claude/skills/dep-audit/` (all four checks).
uv run python scripts/audit/md_discoverability.py --check summary --target .claude/skills/dep-audit/
uv run python scripts/audit/md_discoverability.py --check section-budget --target .claude/skills/dep-audit/
uv run python scripts/audit/md_discoverability.py --check code-block-len --target .claude/skills/dep-audit/ --max 20
uv run python scripts/audit/md_discoverability.py --check section-count --target .claude/skills/dep-audit/ --min 2

# 5. dependency-auditor.md has the Operational shortcuts section pointing to the Skill.
grep -qE '^## Operational shortcuts' .claude/agents/dependency-auditor.md && echo "agent has Operational shortcuts section"
grep -qF '.claude/skills/dep-audit/SKILL.md' .claude/agents/dependency-auditor.md && echo "agent prompt references Skill"

# 6. Skill-extraction pattern documented in dedicated file.
test -f .claude/agents/_common/skills_pattern.md \
  && grep -qF "Skill-extraction pattern" .claude/agents/_common/skills_pattern.md \
  && echo "Skill pattern doc present in _common/skills_pattern.md"

# 7. T10 invariant preserved (all 9 agents still reference _common/non_negotiables.md).
rm -f /tmp/aiw_t12_t10inv.txt
grep -lF '_common/non_negotiables.md' .claude/agents/architect.md .claude/agents/auditor.md \
  .claude/agents/builder.md .claude/agents/dependency-auditor.md \
  .claude/agents/roadmap-selector.md .claude/agents/security-reviewer.md \
  .claude/agents/sr-dev.md .claude/agents/sr-sdet.md .claude/agents/task-analyzer.md \
  > /tmp/aiw_t12_t10inv.txt
awk 'END { exit !(NR == 9) }' /tmp/aiw_t12_t10inv.txt && echo "T10 invariant held (9/9)"

# 8. T24 invariant preserved (audit script smoke checks pass on .claude/agents/).
uv run python scripts/audit/md_discoverability.py --check summary --target .claude/agents/
uv run python scripts/audit/md_discoverability.py --check section-budget --target .claude/agents/
uv run python scripts/audit/md_discoverability.py --check code-block-len --target .claude/agents/ --max 20
uv run python scripts/audit/md_discoverability.py --check section-count --target .claude/agents/ --min 2

# 9. CHANGELOG entry exists.
grep -qE '^### (Added|Changed) — M21 Task 12:' CHANGELOG.md && echo "CHANGELOG anchor present"
```

## Acceptance criteria

1. `.claude/skills/dep-audit/SKILL.md` exists, has well-formed frontmatter (`name: dep-audit`, `description:` ≤ 200 chars and trigger-led — gated by smoke step 2's `${#desc} ≤ 200`), body ≤ 5K tokens (smoke step 3). Smoke step 4's four T24-rubric checks all pass against the `.claude/skills/dep-audit/` directory (transitive rubric application).
2. `.claude/skills/dep-audit/runbook.md` exists; covered by smoke step 4 (section-budget, summary, code-block-len, section-count all pass at the `.claude/skills/dep-audit/` target).
3. `.claude/agents/dependency-auditor.md` carries exactly one new `## Operational shortcuts` section pointing to the Skill (per surgical-edit list in §Step 4); no other section is rewritten. Smoke step 5 passes.
4. Skill-extraction pattern documented in dedicated file `_common/skills_pattern.md` (separate topic from autonomous-mode boundaries per T24 rubric rule 5). Smoke step 6 confirms file presence + magic-phrase grep; smoke step 8 confirms T24-rubric conformance via the `_common/` walk (the audit script's `_get_md_files` walks `_common/`, so `skills_pattern.md` is checked transitively).
5. T10 invariant held (smoke step 7 = 9).
6. T24 invariant held — `.claude/agents/*.md` still passes the discoverability audit (smoke step 8 all four checks zero exit).
7. `CHANGELOG.md` updated under `[Unreleased]` with `### Added — M21 Task 12: Skills extraction (.claude/skills/dep-audit/; pattern locked)`.
8. Status surfaces flip together: (a) T12 spec `**Status:**` line moves from `📝 Planned` to `✅ Done`, (b) M21 README task-pool row 72 Status column moves from `📝 Candidate` to `✅ Done`, (c) M21 README **§Exit criteria gains a new G6** ("**(G6)** At least one extraction Skill lands in M21; pattern locked for downstream extractions.") with a satisfaction parenthetical naming `dep-audit` as the extracted Skill. **Do NOT amend G3** — that's T13–T16's lane.

## Out of scope

- **Extracting more than one capability into a Skill.** T12 establishes the pattern via one concrete extraction (`dep-audit-shortcuts`). Future T12-shaped tasks (`task_<NN>_skills_extraction_<capability>.md`) land separately for test-quality eval, threat-model walk, wheel-contents-only sub-skill, etc.
- **Phase F productivity commands as Skills.** T13 (`/triage`), T14 (`/check`), T15 (`/ship`), T16 (`/sweep`) are *new* surfaces, not extractions of existing agent capabilities. They have separate specs and follow this Skill pattern but are scoped per their own task spec.
- **Re-architecting `.claude/skills/ai-workflows/SKILL.md`.** That Skill exists and is correct; T12 leaves it alone.
- **Validating the extraction by omission.** Research-brief §T12 line 269 suggests testing the Skill by omitting it and confirming Claude underperforms. That's a useful sanity check but not Auditor-runnable in this task's smoke. Captured as a manual one-shot the operator can run; not gated.
- **Adding a CI gate for Skill discovery / well-formedness.** Deferred to T25 (periodic skill / scheduled-task efficiency audit) — same destination as T24's TA-LOW-02 (audit-script CI hookup).
- **Changing the agent's behavioral rules.** The Skill carries the operational shortcut; the agent retains the threat-model framing + severity grading. No agent rewrite.
- **Adopting items from `nice_to_have.md`.**
- **Runtime code changes** (per M21 scope note).

## Dependencies

- **Built on T10 + T11 + T24.** Requires `_common/non_negotiables.md`, the slimmed CLAUDE.md, and the rubric-conformant agent prompts. All ✅ shipped.
- **Blocks future T12-shaped tasks.** The pattern locked here is the template for subsequent extractions. Each future Skill is its own task; no batch extraction in this milestone.

## Carry-over from prior milestones

*None.*

## Carry-over from prior audits

*None at draft time. Populated if a Builder cycle's audit surfaces forward-deferred items.*

## Carry-over from task analysis

- [ ] **TA-LOW-01 — Switch grounding-link line numbers to anchor strings (broadened round 5)** (severity: LOW, source: task_analysis.md round 3, re-affirmed round 4, broadened round 5 / T12 round 3)
      Spec §Grounding (line 5) AND §Out of scope "Validating the extraction by omission" both hard-code `line 269` for the research brief. Verified accurate today, but the line numbers will drift with future re-flow.
      **Recommendation:** Replace **each** occurrence of `line 269` → `(matching \`### T12 — Skills extraction (per-agent capabilities)\`)`; replace `line 145` (line 5 only) → `(matching \`T12 (Skills extraction) aligns directly with Anthropic's Agent Skills pattern\`)`. Anchor strings survive re-flow. Builder migrates **both** sites at implement time.

- [ ] **TA-LOW-02 — Mandate the literal phrase "Skill-extraction pattern" in `_common/skills_pattern.md` body** (severity: LOW, source: task_analysis.md round 5 / T12 round 3)
      Smoke step 6 asserts `grep -qF "Skill-extraction pattern" .claude/agents/_common/skills_pattern.md` — a literal case-sensitive substring match. Step 5's body content (sections "When to extract", "The 4-rule Skill structure", "How to validate") does not require the phrase verbatim. A Builder writing freehand could use synonyms ("extraction recipe", "Skill extraction guidance") and pass T24 rubric checks but fail smoke step 6.
      **Recommendation:** Builder includes the literal phrase **Skill-extraction pattern** in the file body (intro paragraph or first section) so smoke step 6's grep is satisfied unambiguously. Two-line edit at implement time, no scope drift.

(Prior round-3 TA-LOW-01 — dead memory-file pointer in SKILL.md template — was absorbed pre-emptively by the orchestrator at round-4 close per round-4 L1; carry-over slot freed.)
