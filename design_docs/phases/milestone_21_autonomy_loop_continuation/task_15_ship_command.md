# Task 15 — `/ship` manual happy-path publish Skill (host-only)

**Status:** 📝 Planned.
**Kind:** Productivity / code + doc.
**Grounding:** [milestone README](README.md) · [research brief §T13–T16](../milestone_20_autonomy_loop_optimization/research_analysis.md) — anchor `### T13–T16 — New commands (/triage, /check, /ship, /sweep)` · [T13/T14/T16 specs](task_13_triage_command.md) (✅ Done — Phase F template precedent) · [`scripts/release_smoke.sh`](../../../scripts/release_smoke.sh) (canonical release smoke procedure) · [`tests/release/test_install_smoke.py`](../../../tests/release/test_install_smoke.py) (real-install gate, KDR-discipline). KDR drift checks apply per M21 scope note. **Threat-relevant** because /ship invokes `uv publish` — read carefully against the autonomous-mode boundaries and the project memory `feedback_autonomous_mode_boundaries.md`.

## Why this task exists

The pre-publish ceremony (`uv build` + `unzip -l dist/*.whl` wheel-contents check + `tests/release/test_install_smoke.py` real-install smoke + `uv publish`) is currently a hand-walked operator procedure. The exact sequence + the exact gates + the exact halt-conditions are documented across `scripts/release_smoke.sh`, `dep-audit` SKILL.md, and project memory `reference_pypi_token_dotenv.md`, but no single one-shot surface ties them together for the operator.

`/ship` makes the **manual happy-path publish** a one-shot Skill that walks the operator (or the operator-spawned Claude session) through every gate, halts on any non-clean result, and never autonomously runs `uv publish` itself.

**Critical constraint** (per `feedback_autonomous_mode_boundaries.md` Rule 1): `/ship` is **host-only** and **operator-confirmed**. The Skill produces a checklist + executes the verification gates, but the actual `uv publish` invocation is gated on explicit operator approval. Autopilot / auto-implement / orchestrator must NEVER invoke `/ship`. The Skill body explicitly forbids autonomous-mode invocation.

T15 is the fourth Phase F Skill, shipped last per README phasing rationale ("host-only, largest blast radius").

## Skill structure (per `_common/skills_pattern.md`)

T15 follows the 4-rule shape:

1. Frontmatter: `name: ship`, `description:` (≤ 200 chars, trigger-led, mentions host-only), `allowed-tools: Bash` (T15 invokes `uv build`, `unzip`, `pytest`, `git`, and — only on operator approval — `uv publish`).
2. Body ≤ 5K tokens.
3. Body references `runbook.md` for full gate matrix; doesn't inline.
4. New Skill — no agent-prompt duplication risk.

## What to Build

### Step 1 — Create `.claude/skills/ship/SKILL.md`

Body (≤ 5K tokens) with required `## Inputs / ## Procedure / ## Outputs / ## Return schema` anchors plus `## When to use` / `## When NOT to use` (T13 precedent) plus a leading **`## ⚠️ Host-only`** section that names the autonomy-mode boundary explicitly:

```markdown
---
name: ship
description: Manual happy-path publish for jmdl-ai-workflows. Host-only — runs build + wheel-contents + real-install smoke + (on operator approval) uv publish. Forbidden in autonomy mode.
allowed-tools: Bash
---

# ship

Manual happy-path publish Skill. Walks build + wheel-contents + real-install smoke gates and halts on any non-clean result. The actual `uv publish` invocation requires explicit operator approval; never autonomous.

## ⚠️ Host-only — autonomy-mode forbidden

`/ship` MUST NOT be invoked by `/autopilot`, `/auto-implement`, or any orchestrator agent. Per `feedback_autonomous_mode_boundaries.md` Rule 1: only the operator runs `uv publish`, and only on the host (not in the Docker autonomy sandbox). If a sub-agent / orchestrator attempts to invoke `/ship`, that's a HARD HALT.

The Skill's procedure body refuses to proceed past the wheel-contents check unless an operator has explicitly typed approval.

## When to use

- Pre-publish for a new release version (operator has bumped `pyproject.toml` `version` and updated CHANGELOG `[Unreleased]` → `[<version>]`).
- Smoke-testing a release candidate against a clean install before tagging.

## When NOT to use

- Inside `/autopilot` / `/auto-implement` — those flows must NEVER touch the publish path.
- For dep-audit / wheel-contents inspection without intent to publish — use `dep-audit` Skill.
- For verifying on-disk vs pushed-state — use `/check` instead.

## Inputs

Default targets:

- `pyproject.toml` — read `[project]` `name` + `version` + dependency-set.
- `CHANGELOG.md` — read latest version block (must NOT be `[Unreleased]`).
- `dist/` — built artefacts (created by `uv build`).
- `.env` — must contain `PYPI_TOKEN` (per `reference_pypi_token_dotenv.md`).

Optional flags:
- `--dry-run` — run all gates but skip `uv publish` even on operator approval.
- `--from-clean` — `rm -rf dist/` before `uv build` to avoid stale artefacts.
- `--yes` — pre-approve the publish step (skips the typed-token approval prompt). Combine with `--dry-run` to dry-run a pre-approved invocation. Precedence: `--dry-run` overrides everything; otherwise `--yes` skips the approval prompt; otherwise the typed-token prompt is the default.

## Procedure

1. **Pre-flight (sanity)** — six checks:
   - Verify branch is `main` (not `design_branch` / `workflow_optimization`).
   - Verify working tree is clean (`git status --short` empty).
   - Verify `pyproject.toml` `version` is not `0.x.0+dev` or otherwise pre-release-tagged unless that's intentional.
   - Verify `CHANGELOG.md` latest block is NOT `[Unreleased]` (i.e. version was tagged).
   - Verify `.env` exists and contains `PYPI_TOKEN`.
   - Verify `dist/` is empty or `--from-clean` was passed (no stale-wheel risk).
   - HALT on any failure with the failing-check name verbatim.

2. **Build + wheel-contents (delegates to dep-audit Skill)**:
   - Run `uv build`.
   - Inspect `unzip -l dist/*.whl` per the `dep-audit` Skill's runbook.
   - HALT on any unexpected file (`.env*`, `design_docs/`, `runs/`, `*.sqlite3`, `.claude/`, etc.).

3. **Real-install smoke**:
   - Run `bash scripts/release_smoke.sh` (canonical procedure — full real-install in fresh venv).
   - Run `uv run pytest tests/release/test_install_smoke.py` (assertion-form gate).
   - HALT on any failure.

4. **Operator-approval prompt**:
   - Surface the report so far + the exact `uv publish` command line that WOULD be run.
   - Wait for explicit operator approval (typed token like "ship it" or `--yes` flag passed). On `--dry-run`, skip this step and exit DRY-RUN-CLEAN.
   - If no approval, exit with verdict `OPERATOR-WITHHELD-APPROVAL`.

5. **Publish**:
   - Run `set -a && . ./.env && set +a && uv publish --token "$PYPI_TOKEN"` (per `reference_pypi_token_dotenv.md`).
   - Capture output. HALT on non-zero exit.
   - On success, run `git tag <version> && git push origin <version>`.

6. **Post-publish verification (Bash-native; Skills do not chain)**:
   - Fetch the live PyPI version via `curl -s https://pypi.org/pypi/jmdl-ai-workflows/json | python -c "import sys, json; print(json.load(sys.stdin)['info']['version'])"` and compare to the just-published version. This mirrors the `check` Skill's PyPI-comparison logic but does not invoke the Skill — Skills do not chain (per project memory `feedback_skill_chaining_reuse.md`).
   - Note discrepancy in the report. PyPI propagation can lag a few seconds; if mismatch, retry once after a short sleep before flagging.

## Outputs

Write `runs/ship/<timestamp>/report.md` with:

- **Pre-flight summary** — six-check pass/fail.
- **Build + wheel-contents summary** — wheel filename, size, file count, denylist matches.
- **Real-install smoke summary** — pytest exit-code + scripts/release_smoke.sh exit-code.
- **Approval status** — APPROVED / WITHHELD / DRY-RUN.
- **Publish status** — PUBLISHED / SKIPPED / FAILED — with exact uv publish exit code if attempted.
- **Post-publish verification** — PyPI version match status.

## Return schema

3-line `verdict: / file: / section:` matching `.claude/commands/_common/agent_return_schema.md`. Verdict values: `SHIPPED | DRY-RUN-CLEAN | OPERATOR-WITHHELD-APPROVAL | HALTED`. `file:` = report path.

## Helper files

- `runbook.md` — full pre-flight check matrix; example operator-approval prompts; example HALT messages per gate.
```

### Step 2 — Create `.claude/skills/ship/runbook.md`

T24-rubric-conformant. Sections:

- 3-line summary (mentions host-only, operator-approval, publish path).
- `## Pre-flight check matrix` — six pre-flight checks with exact failure messages.
- `## Build + wheel-contents` — pointer to `dep-audit` Skill's runbook.
- `## Real-install smoke` — `scripts/release_smoke.sh` invocation + `tests/release/test_install_smoke.py` invocation.
- `## Operator-approval prompts` — exact token examples (`ship it`, `--yes`, etc.).
- `## Publish failure modes` — auth failures, network failures, version-already-exists.

### Step 3 — Add `tests/test_t15_ship.py`

Mirror `tests/test_t13_triage.py` shape (one test function per acceptance-criterion sub-claim — frontmatter parse, char/token budgets, four required anchors, helper-file ref, T24-rubric subprocesses, Live-Skills line, CHANGELOG). **Plus one extra test** specific to T15: assert that the SKILL.md body contains the substring `host-only` (case-insensitive) — the autonomy-mode boundary anchor MUST be present.

### Step 4 — Update README §G3

Extend §G3 satisfaction list: `(satisfied at T13 with /triage; T14 adds /check; T16 adds /sweep; T15 adds /ship — Phase F complete)`. With T15 landing, Phase F is fully done.

### Step 5 — Update `_common/skills_pattern.md`

Extend Live Skills line with `, ship (T15)` (single line; do not add a second).

## Deliverables

- `.claude/skills/ship/SKILL.md` — new (≤ 5K tokens).
- `.claude/skills/ship/runbook.md` — new (T24-rubric).
- `tests/test_t15_ship.py` — new (mirrors `tests/test_t13_triage.py` shape; adds one extra test for the `host-only` anchor).
- Edit to `_common/skills_pattern.md` Live-Skills line.
- Edit to M21 README §G3 prose.
- `CHANGELOG.md` updated.

## Tests / smoke (Auditor runs)

```bash
# 1. Skill files exist + frontmatter valid.
test -f .claude/skills/ship/SKILL.md && echo "SKILL.md exists"
test -f .claude/skills/ship/runbook.md && echo "runbook.md exists"
grep -qE '^name: ship$' .claude/skills/ship/SKILL.md && echo "name correct"
grep -qE '^description: ' .claude/skills/ship/SKILL.md && echo "description present"
grep -qE '^allowed-tools: ' .claude/skills/ship/SKILL.md && echo "allowed-tools declared"

# 2. Description ≤ 200 chars (Bash-safe).
awk -F': ' '/^description: /{ exit !(length(substr($0, 14)) <= 200) }' .claude/skills/ship/SKILL.md && echo "description ≤ 200 chars"

# 3. Body ≤ 5K tokens (Bash-safe).
awk '{ w += NF } END { exit !(w * 13 / 10 <= 5000) }' .claude/skills/ship/SKILL.md && echo "SKILL.md ≤ 5K tokens"

# 4. T24 rubric on .claude/skills/ship/.
uv run python scripts/audit/md_discoverability.py --check summary --target .claude/skills/ship/
uv run python scripts/audit/md_discoverability.py --check section-budget --target .claude/skills/ship/
uv run python scripts/audit/md_discoverability.py --check code-block-len --target .claude/skills/ship/ --max 20

# 5. Required four `##` anchors.
grep -qE '^## Inputs' .claude/skills/ship/SKILL.md && echo "Inputs"
grep -qE '^## Procedure' .claude/skills/ship/SKILL.md && echo "Procedure"
grep -qE '^## Outputs' .claude/skills/ship/SKILL.md && echo "Outputs"
grep -qE '^## Return schema' .claude/skills/ship/SKILL.md && echo "Return schema"

# 6. Host-only anchor present (T15-specific safety check).
grep -qiF 'host-only' .claude/skills/ship/SKILL.md && echo "host-only anchor present"
grep -qiF 'autonomy-mode' .claude/skills/ship/SKILL.md && echo "autonomy-mode reference present"

# 7. T25 skills_efficiency clean.
uv run python scripts/audit/skills_efficiency.py --check all --target .claude/skills/

# 8. T10 invariant.
rm -f /tmp/aiw_t15_t10inv.txt
grep -lF '_common/non_negotiables.md' .claude/agents/architect.md .claude/agents/auditor.md \
  .claude/agents/builder.md .claude/agents/dependency-auditor.md \
  .claude/agents/roadmap-selector.md .claude/agents/security-reviewer.md \
  .claude/agents/sr-dev.md .claude/agents/sr-sdet.md .claude/agents/task-analyzer.md \
  > /tmp/aiw_t15_t10inv.txt
awk 'END { exit !(NR == 9) }' /tmp/aiw_t15_t10inv.txt && echo "T10 9/9"

# 9. T24 invariant on .claude/agents/.
uv run python scripts/audit/md_discoverability.py --check section-budget --target .claude/agents/

# 10. Tests pass.
uv run pytest tests/test_t15_ship.py -q

# 11. CHANGELOG anchor.
grep -qE '^### (Added|Changed) — M21 Task 15:' CHANGELOG.md && echo "CHANGELOG anchor"

# 12. _common/skills_pattern.md Live Skills line lists ship.
grep -qE '^Live Skills:.*ship' .claude/agents/_common/skills_pattern.md && echo "skills_pattern lists ship"
```

## Acceptance criteria

1. `.claude/skills/ship/SKILL.md` exists; valid frontmatter; body ≤ 5K tokens; four required anchors. Smoke 1–3 + 5 pass.
2. `.claude/skills/ship/runbook.md` exists; T24-rubric conformant. Smoke 4 passes.
3. **Host-only safety anchor** — SKILL.md body contains "host-only" + "autonomy-mode" references (smoke 6). The autonomy-mode boundary MUST be explicit; a Skill that publishes without this anchor is unacceptable.
4. T25 skills_efficiency clean (smoke 7).
5. T10 invariant held (smoke 8).
6. T24 invariant held (smoke 9).
7. `tests/test_t15_ship.py` passes (smoke 10).
8. `_common/skills_pattern.md` Live Skills line lists ship (smoke 12).
9. `CHANGELOG.md` updated with `### Added — M21 Task 15: /ship manual happy-path publish Skill (host-only)` (smoke 11).
10. Status surfaces flip together: (a) T15 spec `**Status:**` → `✅ Done`, (b) M21 README task-pool T15 row Status → `✅ Done` (anchor by row content), (c) M21 README §G3 prose extended to mark Phase F complete with all four Skills named.

## Out of scope

- **Auto-trigger.** Operator-only; never autopilot/auto-implement.
- **In-Docker publish.** Host-only.
- **Multi-package publish.** Single package (jmdl-ai-workflows) at T15 time.
- **Pre-version-bump automation.** /ship assumes version bump already happened.
- **Rollback / yank automation.** Operator runs `uv publish --yank` manually if needed.
- **Adopting items from `nice_to_have.md`.**
- **Runtime code changes** (per M21 scope note).

## Dependencies

- **Built on T12, T13, T14, T16, T24, T25, T26.** Same Phase F Skill template + T24 rubric + T25 skills_efficiency CI gate + autonomy-mode boundary documented at `_common/non_negotiables.md` + `feedback_autonomous_mode_boundaries.md`.
- **Closes Phase F.** With T15 shipped, all four Phase F productivity Skills (`/triage`, `/check`, `/sweep`, `/ship`) exist.
- **Precedes Phase G.** T17 (parallel-builders spec format) is next; T18/T19 stretch.

## Carry-over from prior milestones

*None.*

## Carry-over from prior audits

*None.*

## Carry-over from task analysis

- [ ] **TA-LOW-01 — Smoke step 8 hard-pinned agent count is cross-spec fragile** (severity: LOW, source: task_analysis.md round 18, carried through round 19)
      Smoke step 8 lists 9 agent files + `awk 'END { exit !(NR == 9) }'`. If a future task adds a 10th agent, every M21 task spec's smoke breaks (T13/T14/T16 use the same pin).
      **Recommendation:** Acceptable for T15 (sibling parity is higher value). Future cleanup task may swap the hard-coded 9 for a dynamic count across all M21 specs.

- [ ] **TA-LOW-02 — In-prose Skill references use leading-slash form** (severity: LOW, source: task_analysis.md round 18, carried through round 19)
      Spec body refers to `/triage`, `/check`, `/ship`, `/sweep` with leading slash, but Skills live under `.claude/skills/<name>/SKILL.md` (not `.claude/commands/`). Sibling specs use the same form — parity takes precedence.
      **Recommendation:** No spec-internal change. Carry-over reminder for a future doc-cleanup pass.

- [ ] **TA-LOW-03 — `curl -s` should be `curl -sf` for PyPI-compare robustness** (severity: LOW, source: task_analysis.md round 19)
      Procedure step 6 uses `curl -s https://pypi.org/...` which prints HTML error bodies on PyPI 5xx, causing `json.load` to raise. Sibling `check` Skill runbook uses `curl -sf` (fails fast on HTTP error).
      **Recommendation:** Builder uses `curl -sf` instead of `curl -s` for PyPI-compare. One-character fix at implement time.
