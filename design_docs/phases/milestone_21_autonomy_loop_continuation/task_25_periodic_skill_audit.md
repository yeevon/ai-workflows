# Task 25 — Periodic skill / scheduled-task efficiency audit (`/audit-skills`)

**Status:** ✅ Done.
**Kind:** Slimming / doc + code.
**Grounding:** [milestone README](README.md) · [research brief §T25 (NEW)](../milestone_20_autonomy_loop_optimization/research_analysis.md) — anchor `### T25 — Periodic skill/scheduled-task efficiency audit (citing Nate Jones / Nicholas Rhodes pattern)` · [Nate Jones "Your Claude Sessions Cost 10x What They Should"](https://research_analysis.md#L135) (cited; "automated task bloat" framing) · [Nicholas Rhodes "I found 350,000 tokens hiding in plain sight"](https://research_analysis.md#L135) (cited; the 11,800-tokens-per-run example) · [T24 spec](task_24_md_discoverability.md) (✅ Done — TA-LOW-02 deferred to T25 for `scripts/audit/md_discoverability.py` CI hookup) · [T12 spec](task_12_skills_extraction.md) (✅ Done — Out of scope says "Adding a CI gate for Skill discovery / well-formedness. Deferred to T25") · [T26 spec](task_26_two_prompt_long_running.md) (✅ Done — agent_docs/ rubric inheritance also lands here for the periodic walk). KDR drift checks apply per M21 scope note.

## Why this task exists

Build-and-forget agents accumulate token waste invisibly: correct output and efficient output look identical from outside. The cure (per Nate Jones / Nicholas Rhodes) is a *periodic audit prompt* that re-reviews each Skill and slash-command for the four documented failure modes:

1. Redundant tool round-trips (e.g. multiple `Read` calls when one would do).
2. Screenshots where text-extraction would work (`get_page_text` vs an image grab).
3. Re-reading files the model already has in memory.
4. Missing tool declarations forcing repeated `ToolSearch` round-trips.

ai-workflows currently has **two prior unresolved CI-hookup deferrals** that T25 absorbs:

- **T24 TA-LOW-02** — `scripts/audit/md_discoverability.py --check section-budget --target .claude/agents/` should run in CI so post-T24 agent-prompt growth is caught at PR time.
- **T12 (out of scope)** — A CI gate for Skill discovery / well-formedness (`.claude/skills/dep-audit/SKILL.md` and future Skills) should land alongside the periodic-audit infrastructure.

T25 lands `/audit-skills` as a new slash command + a `scripts/audit/skills_efficiency.py` audit script + a single CI step that wires both T24's md_discoverability check AND the new skills_efficiency check. The `/audit-skills` command is operator-runnable (quarterly cadence per research brief); the CI step catches regressions automatically.

## What to Build

### Step 1 — `scripts/audit/skills_efficiency.py` (new)

Audit script that walks `.claude/skills/*/SKILL.md` + `.claude/skills/*/runbook.md` (and any other Skill helpers) and reports per-skill findings under the two CI-gated failure modes (the operator-only ones live in the `/audit-skills` slash command, see Step 2). ≤ 200 lines (matching T24's `md_discoverability.py` size budget). Spec-API:

```
uv run python scripts/audit/skills_efficiency.py --check {screenshot-overuse|missing-tool-decl|all} --target .claude/skills/
```

Failure-mode heuristics (proxy checks; not behavioral evaluations). Two heuristics are CI-gated (mechanically reliable); two are operator-only (judgement-rich, surfaced via the `/audit-skills` slash command):

- **CI-gated heuristics:**
  - **screenshot-overuse** — flag SKILL.md / runbook.md mentions of `screenshot` or `image` without an adjacent text-extraction reference (matching `text-extraction`, `parse`, or any tool name suggesting text retrieval). Forward-looking; no live Skill currently triggers.
  - **missing-tool-decl** — flag SKILL.md frontmatter without an `allowed-tools` field when the body procedure invokes ≥ 2 distinct tools — but only count tool-name occurrences inside fenced code blocks or at the start of bullets (`- Read X`, ` ```bash\nRead X\n``` `), NOT in mid-prose ("Read the plan"). Tightened to avoid false positives against `.claude/skills/ai-workflows/SKILL.md` documentation prose.
- **Operator-only heuristics (surfaced by `/audit-skills` slash command, NOT in `--check all` CI gate):**
  - **tool-roundtrips** — judgement call about whether ≥ 3 separate fenced bash blocks at the same `## Procedure` level could be batched. Not mechanically reliable; relies on operator's read-through. The slash command summarizes the SKILL.md procedures and asks the operator: "do these three bash blocks need three separate invocations or can they batch?"
  - **file-rereads** — judgement call about whether the procedure tells Claude to re-read a file already in context. Operator-runnable.

The audit script supports `--check {screenshot-overuse|missing-tool-decl|all}` for CI use (where `all` means just those two). The `/audit-skills` slash command surfaces the operator-only heuristics in addition. **No `tool-roundtrips` or `file-rereads` flag in the audit script's `--check` arg list** — those are slash-command-only.

Each finding writes to stdout in the standard `Rule N FAIL — <skill>: <one-line reason>` shape (matches T24 audit script). Exit 0 on no findings; exit 1 on any FAIL.

### Step 1b — Add `allowed-tools:` frontmatter to existing Skills (in-scope clean-tree precondition)

The two existing Skills on disk (`.claude/skills/ai-workflows/SKILL.md` and `.claude/skills/dep-audit/SKILL.md`) currently have no `allowed-tools:` frontmatter. T25's `missing-tool-decl` heuristic — even tightened per Step 1 — would flag both of them on the very first CI run if their procedures invoke ≥ 2 distinct tools inside fenced blocks.

T25 ships with the Skills heuristic-clean: add `allowed-tools:` frontmatter to both existing Skills enumerating the tools their procedures actually invoke. For `dep-audit`: `allowed-tools: Bash` (uv build, unzip, git diff). For `ai-workflows`: `allowed-tools: Bash` (the existing Skill calls the MCP server / aiw CLI via Bash). This is in scope for T25 because it is a **clean-tree precondition** for the audit infrastructure to land green.

The fix is mechanical: insert one frontmatter line per file (between `description:` and the closing `---`). No Skill body content is changed. T26's `nice_to_have.md` adoption rule does not apply (these are existing files getting metadata, not new feature adoption).

### Step 2 — `/audit-skills` slash command (new)

Create `.claude/commands/audit-skills.md` — a slash command that walks the same surfaces as Step 1 + `.claude/commands/*.md` (slash-command files themselves) plus the operator-only heuristics (`tool-roundtrips`, `file-rereads`) and produces a `runs/audit-skills/<timestamp>/report.md` with per-Skill + per-command findings. Quarterly cadence per research brief; operator-invoked, not auto-triggered.

**Required slash-command body sections** (T25 introduces this canonical four-anchor shape for audit-style slash commands; existing sibling commands like `audit.md` / `auto-implement.md` / `clean-tasks.md` use free-form section shapes — future audit-style commands inherit T25's anchor set):

- **§Inputs** — target directories (default: `.claude/skills/`, `.claude/commands/`).
- **§Procedure** — invoke `scripts/audit/skills_efficiency.py --check all` for the CI-gated heuristics, then perform the operator-only heuristic walks (`tool-roundtrips`: count fenced bash blocks per `##` section in each SKILL.md; `file-rereads`: scan for literal duplicate `Read X` patterns), then walk `.claude/commands/*.md` for slash-command-specific patterns (inline-procedure size > 200 lines, missing canonical reference anchors).
- **§Outputs** — write `runs/audit-skills/<timestamp>/report.md` with one section per Skill + per command. Each section names the heuristic, the verdict (`OK | FLAG`), and a one-line reason if FLAGged.
- **§Return schema** — 3-line `verdict: / file: / section:` matching the established autonomy-mode return shape (`.claude/commands/_common/agent_return_schema.md`).

Smoke step 1 (below) is updated to grep for these four `##` section anchors so the Auditor can verify body shape.

### Step 3 — CI integration (`.github/workflows/ci.yml`)

Add one CI step to the existing CI workflow that runs:

```yaml
- name: Audit infrastructure files (md discoverability + skills efficiency)
  run: |
    uv run python scripts/audit/md_discoverability.py --check section-budget --target .claude/agents/
    uv run python scripts/audit/md_discoverability.py --check section-budget --target agent_docs/
    uv run python scripts/audit/skills_efficiency.py --check all --target .claude/skills/
```

This single step closes T24 TA-LOW-02 and T12's deferred CI gate together. The audit scripts exit non-zero on any finding, so CI fails on regressions.

### Step 4 — Update `nice_to_have.md` (close existing deferrals)

Two prior deferrals close at T25 land time:

1. T24's TA-LOW-02 carry-over (CI hookup for `scripts/audit/md_discoverability.py`) — record as resolved in the T24 issue file.
2. T12's `## Out of scope` deferral — note in this task's issue file that T25 absorbs it.

No new `nice_to_have.md` slot is created.

### Step 5 — Update README §G5

M21 README §G5 currently reads: "Quarterly audit prompt over each Skill and slash-command lands as a runnable command (`/audit-skills` or similar). Two-prompt pattern documented in `agent_docs/long_running_pattern.md` with reference Builder loop." T26 already amended G5's two-prompt half. T25 amends the audit-prompt half with a satisfaction parenthetical: `(satisfied at T25; /audit-skills + scripts/audit/skills_efficiency.py landed; CI walks both audit scripts every PR)`.

## Deliverables

- `scripts/audit/skills_efficiency.py` — new (≤ 200 lines).
- `.claude/commands/audit-skills.md` — new slash command (§Inputs, §Procedure, §Outputs, §Return schema sections required).
- Edit to `.claude/skills/ai-workflows/SKILL.md` — add `allowed-tools:` frontmatter line (Step 1b).
- Edit to `.claude/skills/dep-audit/SKILL.md` — add `allowed-tools:` frontmatter line (Step 1b).
- Edit to `.github/workflows/ci.yml` — one new step running both audit scripts (md_discoverability + skills_efficiency).
- Edit to T24 issue file — record TA-LOW-02 as RESOLVED at T25.
- `tests/test_t25_skills_efficiency.py` — new (covers the two CI-gated `--check` flags + the `all` aggregate path + invalid-target error handling, matches T24 test pattern; synthetic fixtures exercise both rule-fires-on-violation paths).
- `CHANGELOG.md` updated under `[Unreleased]`.
- M21 README §G5 prose amended with satisfaction parenthetical for the audit-prompt half.

## Tests / smoke (Auditor runs)

```bash
# 1. Audit script + slash command exist.
test -f scripts/audit/skills_efficiency.py && echo "skills_efficiency.py exists"
test -f .claude/commands/audit-skills.md && echo "audit-skills.md exists"

# 2. Each CI-gated --check flag exits 0 against the live .claude/skills/ (two Skills:
# ai-workflows + dep-audit, both heuristic-clean after Step 1b's allowed-tools frontmatter
# additions).
uv run python scripts/audit/skills_efficiency.py --check screenshot-overuse --target .claude/skills/
uv run python scripts/audit/skills_efficiency.py --check missing-tool-decl --target .claude/skills/
uv run python scripts/audit/skills_efficiency.py --check all --target .claude/skills/

# 2b. Existing Skills carry allowed-tools frontmatter (Step 1b precondition).
grep -qE '^allowed-tools:' .claude/skills/ai-workflows/SKILL.md && echo "ai-workflows has allowed-tools"
grep -qE '^allowed-tools:' .claude/skills/dep-audit/SKILL.md && echo "dep-audit has allowed-tools"

# 3. CI step is wired.
grep -qE 'scripts/audit/md_discoverability\.py' .github/workflows/ci.yml && echo "md_discoverability in CI"
grep -qE 'scripts/audit/skills_efficiency\.py' .github/workflows/ci.yml && echo "skills_efficiency in CI"

# 4. Test file passes.
uv run pytest tests/test_t25_skills_efficiency.py -q

# 5. T10 invariant preserved.
rm -f /tmp/aiw_t25_t10inv.txt
grep -lF '_common/non_negotiables.md' .claude/agents/architect.md .claude/agents/auditor.md \
  .claude/agents/builder.md .claude/agents/dependency-auditor.md \
  .claude/agents/roadmap-selector.md .claude/agents/security-reviewer.md \
  .claude/agents/sr-dev.md .claude/agents/sr-sdet.md .claude/agents/task-analyzer.md \
  > /tmp/aiw_t25_t10inv.txt
awk 'END { exit !(NR == 9) }' /tmp/aiw_t25_t10inv.txt && echo "T10 invariant held (9/9)"

# 6. T24 invariant preserved.
uv run python scripts/audit/md_discoverability.py --check section-budget --target .claude/agents/

# 7. CHANGELOG anchor.
grep -qE '^### (Added|Changed) — M21 Task 25:' CHANGELOG.md && echo "CHANGELOG anchor present"

# 8. Audit-script line budget (Bash-safe — no command substitution per _common/verification_discipline.md).
awk 'END { exit !(NR <= 200) }' scripts/audit/skills_efficiency.py && echo "skills_efficiency.py ≤ 200 lines"

# 9. /audit-skills slash command body has the four required section anchors.
grep -qE '^## (Inputs|Procedure|Outputs|Return schema)' .claude/commands/audit-skills.md && echo "audit-skills section anchors present"
```

## Acceptance criteria

1. `scripts/audit/skills_efficiency.py` exists, supports two CI-gated `--check` flags (`screenshot-overuse`, `missing-tool-decl`) + `all`, exits non-zero on findings, ≤ 200 lines (smoke steps 1–2 + 8 pass).
2. `.claude/commands/audit-skills.md` exists as a runnable slash command and carries the four required `##` section anchors (Inputs, Procedure, Outputs, Return schema). Smoke steps 1 + 9 pass.
2b. Both existing Skills (`.claude/skills/ai-workflows/SKILL.md` and `.claude/skills/dep-audit/SKILL.md`) carry `allowed-tools:` frontmatter (Step 1b clean-tree precondition). Smoke step 2b passes.
3. CI workflow wires both audit scripts (smoke step 3 passes).
4. `tests/test_t25_skills_efficiency.py` exists, covers all four checks + the all-aggregate path, exits 0 (smoke step 4 passes).
5. T24 issue file's TA-LOW-02 marked RESOLVED with reference to T25 commit.
6. T10 invariant held (smoke step 5 = 9).
7. T24 invariant held (smoke step 6 zero exit).
8. `CHANGELOG.md` updated under `[Unreleased]` with `### Added — M21 Task 25: Periodic skill / scheduled-task efficiency audit (/audit-skills + scripts/audit/skills_efficiency.py + CI hookup)`.
9. Status surfaces flip together: (a) T25 spec `**Status:**` line moves to `✅ Done`, (b) M21 README task-pool row 75 (the T25 row) Status moves to `✅ Done`, (c) M21 README §Exit criteria §G5 prose's audit-prompt half is amended in-place with satisfaction parenthetical (e.g. `(satisfied at T25; /audit-skills + scripts/audit/skills_efficiency.py landed; CI walks both audit scripts every PR)`). Do NOT amend the two-prompt half (that was T26's lane).

## Out of scope

- **Behavioral evaluation of Skills** (e.g. "does this Skill produce correct output"). T25 is heuristic / proxy-check only — it spots common waste patterns, not correctness regressions.
- **Adding new Skills.** T25 audits whatever exists (currently 2: `ai-workflows` and `dep-audit`); future Skills (test-quality eval, threat-model walk) inherit the audit when they land. Step 1b adds `allowed-tools:` frontmatter to the two existing Skills as a clean-tree precondition for the heuristic to land green — that is metadata-only, not a Skill-body change.
- **Quarterly automated runner.** T25 ships the slash command + CI gate; the operator runs `/audit-skills` quarterly. Cron / scheduler integration is deferred; a future scheduling Skill (e.g. `/schedule`) can adopt this audit when added.
- **Auditing pre-2026 archived content.** Archived skills / commands under `archive/` are out of scope.
- **Replacing T20's checkbox-cargo-cult catch** (M20 work). That's a separate failure-mode catcher; T25's four heuristics are different (tool-roundtrips / screenshots / file-rereads / missing-tool-decl).
- **Adopting items from `nice_to_have.md`.**
- **Runtime code changes** (per M21 scope note).

## Dependencies

- **Built on T24** — reuses the `scripts/audit/` directory and pattern; closes T24 TA-LOW-02.
- **Built on T12** — closes T12's deferred CI gate for Skill well-formedness.
- **Built on T26** — `agent_docs/` is a target the CI step also walks (md_discoverability against agent_docs/).
- **Precedes Phase F productivity commands.** T13/T14/T15/T16 add new slash commands as Skills; once they land, the next operator `/audit-skills` run will catch any anti-patterns automatically.

## Carry-over from prior milestones

*None.*

## Carry-over from prior audits

- **T24 TA-LOW-02** (deferred to T25): CI hookup for `scripts/audit/md_discoverability.py --check section-budget --target .claude/agents/`. Resolved by Step 3 + tracked in T24 issue file at T25 close.
- **T12 §Out of scope** (deferred to T25): CI gate for Skill discovery / well-formedness. Resolved by Step 1 + Step 3.

## Carry-over from task analysis

- [x] **TA-LOW-01 — Smoke step 8 Bash-safe rewrite (round 9 L1, applied at round 9)** (severity: LOW, source: task_analysis.md round 9, re-verified rounds 10–11)
      Smoke step 8 swapped from `$(wc -l < scripts/audit/skills_efficiency.py)` to `awk 'END { exit !(NR <= 200) }' scripts/audit/skills_efficiency.py` per `_common/verification_discipline.md` §Bash-safety rule (no command substitution / parameter expansion in smoke commands). Reference for future audit-script size gates.
      **Recommendation:** Use the same `awk` pattern when adding new line-budget smoke checks.

- [x] **TA-LOW-02 — Operator-only heuristics' synthetic-fixture testing (round 9 L2)** (severity: LOW, source: task_analysis.md round 9, carried through round 11)
      `tool-roundtrips` and `file-rereads` are operator-only heuristics surfaced via `/audit-skills`. If implemented in `scripts/audit/skills_efficiency.py` (not required), unit tests should drive the rule-fires-on-violation paths via synthetic fixtures (not against live `.claude/skills/`, which is heuristic-clean by Step 1b construction). If they live solely in slash-command procedure prose with no Python implementation, no unit-test coverage is needed.
      **Recommendation:** Builder picks at implement time; either choice is acceptable.

- [x] **TA-LOW-03 — `screenshot-overuse` Anthropic-tool-name framing (round 9 L3)** (severity: LOW, source: task_analysis.md round 9, carried through round 11)
      `screenshot-overuse` heuristic uses `get_page_text` (Anthropic Computer Use tool name) verbatim from the Nicholas Rhodes source. ai-workflows is a CLI/MCP project, not Computer Use.
      **Recommendation:** Builder may keep verbatim (deliberate research-brief cite) OR generalize the adjacency regex to local-context terms (e.g. `text-extraction|parse|extract|read.*text`). Either choice is acceptable; document the chosen framing in the audit script's module docstring.
