# M20 — Autonomy Loop Optimization — Task Analysis

**Round:** 4
**Analyzed on:** 2026-04-27
**Specs analyzed:** task_01, task_02, task_03, task_04, task_05, task_06, task_07, task_08, task_09, task_20, task_21, task_22, task_23, task_27, task_28 (15 specs)
**Analyst:** task-analyzer agent
**Working location:** `/home/papa-jochy/prj/ai-workflows-m20/` (worktree on `workflow_optimization` branch)
**Reference:** round 3 baseline at commit 1ddf5c8 (0 HIGH + 4 MEDIUM + 2 LOW); round 3 analysis overwritten by this report.

## Summary

| Severity | Count |
| --- | --- |
| 🔴 HIGH | 0 |
| 🟡 MEDIUM | 1 |
| 🟢 LOW | 2 |
| Total | 3 |

**Stop verdict:** OPEN

(Zero HIGH; 1 MEDIUM concentrates on a T04 smoke-test grep that will fail at audit-runtime against the chosen flat-hyphenated path convention; 2 LOW on (a) a T22 Out-of-scope sentence wording residual from the round-2 H1 fix, (b) T04 test-description shorthand mirroring the L2 issue from round 3. Convergence trajectory: round 1 → 2 → 3 → 4 = 6/2/0/0 HIGH; 17/6/4/1 MEDIUM; 8/2/2/2 LOW. One more round should clear to CLEAN or LOW-ONLY.)

The MEDIUM finding (M1) is a **propagation residual of round-3 L2**: round 3 corrected only AC #3's path-convention wording but did not sweep the spec's smoke-test greps that use the same shorthand against the chosen flat-hyphenated convention. The Auditor's smoke run will fail; the Builder cannot satisfy AC #4's "smoke passes" without either correcting the grep or coincidentally writing the shorthand into `autopilot.md`. Mechanical fix.

The LOW findings are wordsmithing residuals — one in T22's Out-of-scope section that still references "T22's quota proxy" (which T22 no longer has per round-2 H1), one in T04's test-description prose mirroring the round-3 L1/L2 shorthand pattern.

This is **not loop-failure**. All 3 findings are mechanical and locally-correct edits. No new architectural drift, no KDR violation, no new user-arbitration question.

---

## Findings

### 🟡 MEDIUM

#### M1 — T04 smoke-test greps use `iter_<N>_shipped.md` shorthand (underscores) that won't match the chosen `iter<N>-shipped.md` flat-hyphenated path form

**Task:** task_04_cross_task_iteration_compaction.md
**Location:** task_04.md lines 110–114 (smoke-test block):
> ```bash
> # Verify autopilot describes iter_<N>_shipped emission
> grep -q "iter_<N>_shipped.md" .claude/commands/autopilot.md && echo "autopilot emit OK"
>
> # Verify autopilot describes the read-only-latest-shipped rule
> grep -q "iter_<N>_shipped" .claude/commands/autopilot.md && echo "autopilot read OK"
> ```

**Issue:** Round 2 M5 (user arbitration) pinned T04's path convention to **flat hyphenated**: `runs/autopilot-<run-ts>-iter<N>-shipped.md`. T04's §Path convention (lines 65–78) and §Deliverables (lines 52–64) consistently describe the hyphenated form. However, the §Smoke test block at lines 110–114 still greps for the **underscored shorthand** `iter_<N>_shipped.md` (and `iter_<N>_shipped`).

When the Builder implements the deliverable per §Path convention, `autopilot.md` will contain the literal substring `runs/autopilot-<run-ts>-iter<N>-shipped.md` (or `iter<N>-shipped.md`) — **not** `iter_<N>_shipped.md`. The Auditor running the smoke test sees both greps fail, the smoke aborts, and the audit can't pass AC #4 ("`tests/orchestrator/test_iter_shipped_emission.py` passes for the 3-iteration simulation" — though strictly the smoke is line-114-grep, not the test).

This is the **same shape** as the round-3 H2 grep-tightening fix on T05 (which pinned `cycle_<N>/` against the legacy `<cycle>` shorthand). Round-3 L2 corrected AC #3's directory-convention wording but did not sweep the smoke greps using the underscored shorthand against the chosen hyphenated form.

The fix: replace the shorthand `iter_<N>_shipped.md` in the smoke greps with the actual file form `iter<N>-shipped.md` (or, more robustly, the full path `runs/autopilot-<run-ts>-iter<N>-shipped.md`).

**Recommendation:** Update T04's smoke-test greps to match the chosen flat-hyphenated path convention.

**Apply this fix:**

`old_string` (in task_04.md lines 110–114):
```
# Verify autopilot describes iter_<N>_shipped emission
grep -q "iter_<N>_shipped.md" .claude/commands/autopilot.md && echo "autopilot emit OK"

# Verify autopilot describes the read-only-latest-shipped rule
grep -q "iter_<N>_shipped" .claude/commands/autopilot.md && echo "autopilot read OK"
```

`new_string`:
```
# Verify autopilot describes the iteration-shipped emission (flat-hyphenated form per round-2 M5)
grep -qE "iter<N>-shipped\.md|autopilot-<run-ts>-iter<N>-shipped" .claude/commands/autopilot.md \
  && echo "autopilot emit OK"

# Verify autopilot describes the read-only-latest-shipped rule
grep -qE "iter<N>-shipped|autopilot-<run-ts>-iter<N>-shipped" .claude/commands/autopilot.md \
  && echo "autopilot read OK"
```

(The `-E` extended-regex is needed for the alternation; the alternative form documents both the bare suffix and the full-path form so the smoke is robust against either rendering by the Builder.)

---

### 🟢 LOW

#### L1 — T22 §Out-of-scope line 159 still refers to "T22's quota proxy" — round-2 H1 fix removed the quota proxy from T22 entirely

**Task:** task_22_per_cycle_telemetry.md
**Location:** task_22.md line 159:
> `- **Cost reconciliation against the upstream Anthropic dashboard** — out of scope by design. Per #52502, the dashboard is opaque about per-model breakdown in multi-agent stacks. T22's quota proxy is the local-best-estimate; reconciliation would require Anthropic API surface that doesn't exist.`

**Issue:** Round 2 H1 fix moved quota / cost proxy aggregation from T22 to T06's analysis script (verified holding at T22 lines 9, 43, 90, 94, 118, 129, 149). T22 captures **raw token counts only**. But the Out-of-scope section at line 159 still names T22 as owning "the local-best-estimate" quota proxy — a residual the round-2 sweep missed because it was in the Out-of-scope rationale, not the §What to Build section.

A T22 Builder reading line 159 sees a contradiction with §What to Build (lines 9–11) and §Captured fields (lines 21–45). They'll either (a) treat §What to Build as authoritative (correct) or (b) add a quota_proxy field anyway (regression of the H1 fix). Pre-empting the ambiguity is a one-line edit.

**Recommendation:** Reword line 159 to acknowledge T06's ownership of the proxy / aggregation layer.

**Push to spec:** yes — append to T22 carry-over for Builder to absorb at implement-time. (Mechanical wording fix; same surface as round-3 L1/L2 carry-over.)

Suggested replacement text:
```
- **Cost reconciliation against the upstream Anthropic dashboard** — out of scope by design. Per #52502, the dashboard is opaque about per-model breakdown in multi-agent stacks. T22's raw-count records (input/output/cache-* tokens) plus T06's analysis-script proxy aggregation are the local-best-estimate; reconciliation would require Anthropic API surface that doesn't exist.
```

---

#### L2 — T04 test-description prose at lines 85–87 uses flat shorthand `iter_1_shipped.md`; chosen path is `runs/autopilot-<run-ts>-iter1-shipped.md`

**Task:** task_04_cross_task_iteration_compaction.md
**Location:** task_04.md lines 84–87 (test description block):
> ```
> Hermetic test simulating a 3-iteration autopilot run with stub queue-pick + Builder + Auditor agents. Asserts:
> - After iter 1: `iter_1_shipped.md` exists; parses to expected structure with the verdict + commit sha + reviewer verdicts.
> - After iter 2: `iter_2_shipped.md` exists; iter_1_shipped.md unchanged.
> - After iter 3: `iter_3_shipped.md` exists.
> ```

**Issue:** Same shape as round-3 L1 against T03. The chosen path convention (T04 §Path convention lines 65–78, per round-2 M5) is `runs/autopilot-<run-ts>-iter<N>-shipped.md` — flat hyphenated. The test descriptions reference `iter_1_shipped.md` (underscored shorthand, no `runs/` prefix, no `<run-ts>` segment).

A T04 Builder writing `tests/orchestrator/test_iter_shipped_emission.py` reads the test descriptions, then either (a) writes the test against the shorthand path (test never finds the file the deliverable creates) or (b) reads §Path convention as authoritative and writes the test against the hyphenated form (test descriptions don't match the test). Builder absorbs at implement-time but it's preventable.

**Recommendation:** Replace the three test-description lines to use the chosen path form: `runs/autopilot-<run-ts>-iter1-shipped.md`, `runs/autopilot-<run-ts>-iter2-shipped.md`, `runs/autopilot-<run-ts>-iter3-shipped.md` (or describe the path-shape generically with a `<run-ts>` placeholder).

**Push to spec:** yes — append to T04 carry-over for Builder to absorb at implement-time.

---

## What's structurally sound

Round 3 fixes that held up cleanly:

- **M1 (README T22 task-pool row)** — README line 123 verified updated to "raw counts only; T06 owns the proxy / aggregation layer per round-2 H1 fix". Status-surface drift cleared at the README.
- **M2 (T06 line 14 quota-proxy source)** — T06 line 14 verified as "Computed by T06's own analysis script from T22's raw `input_tokens` + `output_tokens` + `cache_*` records (per-model coefficient applied at analysis time...)". Cleanly restated.
- **M3 (T06 line 51 record-format description)** — T06 line 51 verified as "input/output tokens + cache-creation/read tokens + wall-clock + model + effort + verdict, per spawn) is exactly the raw measurement substrate the study consumes". Cleanly restated.
- **M4 (T06 line 12 path form)** — T06 line 12 verified as `runs/<task>/cycle_<N>/<agent>.usage.json` (with explicit "path convention per round-2 M3 — nested `cycle_<N>/` directory" annotation). Cleanly restated.
- **L1 (T03 carry-over)** — T03 line 152 verified as carrying the "Update the three test-description lines to use the nested form" note for Builder absorption.
- **L2 (T04 carry-over)** — T04 line 139 verified as carrying the "Reword AC #3 to: 'Path naming convention (`runs/autopilot-<run-ts>-iter<N>(-shipped)?.md`)...'" note.

Round 2 fixes still holding (carried through round 4):

- **H1 (T22 quota proxy removal)** — T22 spec lines 9, 43, 90, 94, 118, 129, 149 all consistent with "raw counts only; T06 owns proxy / aggregation". L1 (round 4) is a single residual sentence in §Out-of-scope at line 159; everything else in T22 is correct.
- **H2 (T05 duplicate Mechanism block)** — T05 has exactly one `## Mechanism — fragment files` section. Reviewer-agent updates use `cycle_<N>/`. Smoke grep at line 146 tightened to pin `cycle_<N>/` form. Clean.
- **M3 (T08 path standardization)** — All five T08 sites use `runs/<task>/cycle_<N>/`. Verified via grep — zero `<cycle>` legacy form across the milestone.
- **M4 (T01 nested paths)** — T01 lines 34, 72, 76 all use `runs/<task>/cycle_<N>/<filename>` per audit M11.
- **M5 (T04 flat hyphenated convention)** — T04 §Path convention (lines 65–78) pins flat hyphenated; §Out-of-scope and §Deliverables match. Round-4 M1 is a stale smoke grep at lines 110–114, not a contradiction with the chosen path shape.
- **M6 (T02 regex proxy committed)** — T02 line 48 says "via the **regex-based proxy** ... no `tiktoken` test-only dep added". Path is `runs/<task>/cycle_<N>/spawn_<agent>.tokens.txt`. Clean.

Round 1 fixes still holding:

- **All round-1 surface-feasibility wins** (T01 falling back to orchestrator-side parsing; T22 surface-check pre-step; T27 Path B only; T28 broader surface check) intact in round 4.
- **All round-1 LOWs** pushed cleanly to per-spec carry-over sections; never bubbled back as MEDIUMs.

KDR + layer rule: **No drift.** M20's specs do not introduce upward imports, do not move source-of-truth off the MCP substrate, do not import the Anthropic SDK, do not bypass the layer rule. The seven KDRs (002 / 003 / 004 / 006 / 008 / 009 / 013) plus KDR-014 are all preserved.

Cross-spec consistency at the dependency level: T01 → T05 / T08 (blocking) is clean. T21 → T06 / T07 (blocking) is clean. T22 → T06 / T23 / T27 (blocking) is structurally correct. T03 → T20 / T27 (synergistic) is clean. T28 → T03+T04 (composition) is clean.

Surface-feasibility theme: round 4 has 0 surface-feasibility issues — the pattern "Anthropic SDK exposes X but Claude Code Task wrapper may not surface X" is fully absorbed into T01 / T22 / T27 / T28 spec design. No regressions.

README ↔ spec consistency: round 3 finding M1 (README T22 row) was the last README-vs-spec inconsistency; round 4 sweep finds zero new ones. The §Optimization themes, §Goals, §Exit criteria, §Task pool, §Suggested phasing, §Cross-phase dependencies, and §Key decisions sections all track the per-task spec content correctly.

Smoke-test executability sweep: 14 of 15 specs have smoke tests that will resolve cleanly when their deliverables land. T04 is the one exception (round-4 M1).

---

## Cross-cutting context

- **Convergence trajectory is healthy.** Round 1 → 2 → 3 → 4 = 6/2/0/0 HIGH; 17/6/4/1 MEDIUM; 8/2/2/2 LOW. The MEDIUM count converges monotonically post-round-2. Each round's findings are different items — round 4's are pure shorthand-vs-actual-path residuals from round-3 L2's partial sweep (only AC #3 was caught; the smoke greps and test descriptions weren't).
- **Round 4 fix mechanics are uniformly mechanical.** M1 has a literal `old_string → new_string` edit. L1 and L2 are spec carry-over text, also mechanical. Estimated time-to-clear: ~3 minutes of edits across 2 files (task_04.md M1; carry-over additions to task_22.md and task_04.md).
- **Project memory state.** Memory shows M20 active (autopilot validated 2026-04-27); CS300 pivot status unchanged; M16 T01 shipped. M20 is not on hold or pending external trigger. Round 4 doesn't change this.
- **The shorthand-vs-actual-path pattern.** Three rounds (2 / 3 / 4) have found this same shape: a chosen path convention is pinned in one section, but referencing prose elsewhere uses informal shorthand that doesn't match the canonical form. Future rounds (and the orchestrator's round-applies checklist) should add a sweep step: when a path convention is pinned, grep for all references to the same conceptual file across the spec and reconcile them. The drift is consistently small (2–5 sites per occurrence) but consistently appears.
- **Round 4 anticipated effort to clear:** ~3 minutes of mechanical edits (1 MEDIUM in 1 file; 2 LOWs to carry-over).
- **No new HIGH-severity findings.** The round-3 → round-4 transition keeps HIGH at zero. All findings are wording/path mechanics.
- **Loop is on track.** Round 5 (after these fixes apply) should converge to CLEAN or LOW-ONLY, exiting the `/clean-tasks` loop.

---

**Verdict for round 4:** OPEN — 0 HIGH + 1 MEDIUM + 2 LOW. Round 5 should clear to LOW-only or CLEAN.
