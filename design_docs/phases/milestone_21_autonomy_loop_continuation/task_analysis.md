# M21 Autonomy Loop Continuation — Task Analysis

**Round:** 19 (T15 round 2; T10/T11/T12/T13/T14/T16/T24/T25/T26 locked from prior rounds)
**Analyzed on:** 2026-04-29
**Specs analyzed:** task_15_ship_command.md (primary; round 2)
**Locked specs (not re-analyzed):** task_10/11/12/13/14/16/24/25/26 — all `✅ Done` per README task pool.
**Analyst:** task-analyzer agent

## Summary

| Severity | Count |
| --- | --- |
| 🔴 HIGH | 0 |
| 🟡 MEDIUM | 0 |
| 🟢 LOW | 3 |
| Total | 3 |

**Stop verdict:** LOW-ONLY

## Round 18 fix verification

All four blockers from round 18 are confirmed landed:

- **H1 (Skills can't chain).** §Procedure step 6 (lines 105–107) now reads "Post-publish verification (Bash-native; Skills do not chain)" and uses `curl -s https://pypi.org/pypi/jmdl-ai-workflows/json | python -c "import sys, json; print(json.load(sys.stdin)['info']['version'])"` with an explicit citation to project memory `feedback_skill_chaining_reuse.md`. The wording mirrors the `check` Skill's PyPI-compare logic without invoking it. ✅
- **M1 (six-check enumeration).** §Procedure step 1 (lines 76–82) now lists six checks explicitly: branch, working-tree, version-string, CHANGELOG, `.env`+`PYPI_TOKEN`, and the new `dist/` clean check. Matches §Outputs (line 113) and §Step 2 runbook (line 134). ✅
- **M2 (test count framing).** §Step 3 (line 142) now reads "Mirror `tests/test_t13_triage.py` shape (one test function per acceptance-criterion sub-claim — frontmatter parse, char/token budgets, four required anchors, helper-file ref, T24-rubric subprocesses, Live-Skills line, CHANGELOG). **Plus one extra test** specific to T15 …" — drops the "6 / 7" literal counts and references the precedent file. ✅
- **M3 (`--yes` flag).** §Inputs Optional flags (line 72) now declares `--yes` with explicit precedence rule: `--dry-run` overrides everything; otherwise `--yes` skips the approval prompt; otherwise the typed-token prompt is the default. §Procedure step 4 (line 97) consistent. ✅

## Findings

### 🟢 LOW

#### L1 — Smoke step 8 hard-pins agent count to 9 — fragile against future agent additions

**Task:** task_15_ship_command.md
**Issue:** §Tests/smoke step 8 (lines 196–202) explicit-lists 9 agent files + `awk 'END { exit !(NR == 9) }'`. If a future task lands a 10th agent, every M21 task spec's smoke breaks. Cross-spec fragility, not T15-specific (T13/T14/T16 use the same 9-pin).
**Recommendation:** Acceptable as-is for T15 (sibling parity is the higher-value invariant). Carry-over note for a future cleanup that swaps the hard-coded 9 for a dynamic count.
**Push to spec:** yes — append to T15 "Carry-over from task analysis" as a future-cleanup hint.

#### L2 — In-prose Skill references use leading-slash form (`/check`, `/ship`)

**Task:** task_15_ship_command.md
**Issue:** Skills are NOT slash-commands; they live under `.claude/skills/<name>/SKILL.md`. The spec body (and sibling locked T13/T14/T16 specs) refers to the four Phase F surfaces as `/triage`, `/check`, `/ship`, `/sweep`. After H1 was fixed in round 18, the round-2 step-6 prose correctly uses unprefixed `check` Skill (line 106: "mirrors the `check` Skill's PyPI-comparison logic"), so the worst-case ambiguity at the H1 site is resolved. Remaining slash-prefixed references are stylistic.
**Recommendation:** Parity with sibling specs takes precedence — no spec-internal change needed. Carry-over reminder for future doc-cleanup pass.
**Push to spec:** yes — append to T15 "Carry-over from task analysis" as a clarification reminder; not a blocker.

#### L3 — `curl -s` vs `curl -sf` minor drift with `check` Skill's PyPI-compare runbook

**Task:** task_15_ship_command.md
**Location:** §Procedure step 6 (line 106): `curl -s https://pypi.org/pypi/jmdl-ai-workflows/json | python -c "..."`. The sibling `check` Skill's runbook (`.claude/skills/check/runbook.md` line 68) uses `curl -sf` (the `-f` flag fails on HTTP error rather than printing the error body to stdout).
**Issue:** With `curl -s` (no `-f`) and the JSON pipe, an HTTP error response would print the HTML error body to stdin, and `json.load` would raise — so the Builder will see a noisy traceback rather than a clean exit code on transient PyPI 5xx. Minor robustness gap; the spec's "retry once after a short sleep" already covers the propagation-lag case.
**Recommendation:** Add `-f` to the `curl` invocation for parity with the `check` Skill runbook: `curl -sf https://pypi.org/...`. Builder can apply at implement-time. Not a blocker — `python` will fail visibly either way.
**Push to spec:** yes — append to T15 "Carry-over from task analysis" with the one-line Builder hint: "in step 6, use `curl -sf` (not `curl -s`) for parity with `.claude/skills/check/runbook.md`".

## What's structurally sound

Verified against the live codebase and held up across both rounds:

- **All cited paths exist** — `scripts/release_smoke.sh`, `tests/release/test_install_smoke.py`, `tests/test_t13_triage.py`, `.claude/skills/{check,triage,sweep}/{SKILL.md,runbook.md}`, `.claude/agents/_common/skills_pattern.md`, `.claude/agents/_common/non_negotiables.md`, `scripts/audit/{md_discoverability,skills_efficiency}.py`.
- **Project memory citations are live** — `feedback_skill_chaining_reuse.md` (Skills don't chain), `feedback_autonomous_mode_boundaries.md` Rule 1 (host-only `uv publish`), `reference_pypi_token_dotenv.md` (`set -a && . ./.env && set +a && uv publish --token "$PYPI_TOKEN"`).
- **Autonomy-mode boundary correctly anchored** — leading `## ⚠️ Host-only — autonomy-mode forbidden` SKILL section + smoke step 6 (`grep -qiF 'host-only'` + `grep -qiF 'autonomy-mode'`) + AC3 explicit safety claim. Defense-in-depth on top of `_common/non_negotiables.md` Rule 1.
- **KDR drift checks: clean.** No runtime code under `ai_workflows/` is touched (per M21 scope note). KDRs 002/003/004/006/008/009/013 unaffected. Pre-publish wheel-contents check correctly delegated to `dep-audit` Skill in step 2.
- **SEMVER:** doc-only + skill-config — no public-API surface change.
- **Status-surface plan complete.** AC10 lists three surfaces (spec Status, README task-pool row anchor, README §G3 prose update) — matches the four-surface non-negotiable (the `tasks/README.md` surface is N/A for M21).
- **Cross-spec consistency.** Template shape, smoke-test structure, T10/T24 invariant checks, and Live-Skills-line update mechanism all parity with sibling locked T13/T14/T16 specs. The `--yes` precedence rule (round-18 M3 fix) is the one place T15 extends the template — and it does so cleanly.
- **Round-1 → round-2 fix-application is clean.** Each of H1/M1/M2/M3 landed at the cited line with no collateral drift; carry-over section is correctly still empty (L1/L2/L3 to be pushed by orchestrator on this round's exit).

## Cross-cutting context

- **CS300 pivot active per project memory; M21 runs in parallel**, not blocked. T15 is the last of four Phase F productivity Skills; with T15 landed, Phase F closes and M21 advances toward Phase G (T17 spec format extension; T18+T19 stretch).
- **`/ship` blast radius is real.** PyPI publishes are non-reversible (yank exists but the version slot is permanently consumed). Primary control is operator-approval at procedure step 4; `## ⚠️ Host-only` anchor + smoke greps are defense-in-depth. The round-18 H1 fix (no Skill-chaining) is what makes the post-publish verification step robust — without it the Skill would silently no-op.
- **Round-2 verdict: LOW-ONLY.** All four round-1 blockers cleared with no regression. Three remaining LOWs (L1 future cleanup, L2 doc-style parity, L3 `curl -sf` parity) all push to spec carry-over. T15 spec is implementable as written.
