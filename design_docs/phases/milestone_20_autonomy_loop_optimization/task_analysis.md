# M20 — Autonomy Loop Optimization — Task Analysis

**Round:** 3
**Analyzed on:** 2026-04-27
**Specs analyzed:** task_01, task_02, task_03, task_04, task_05, task_06, task_07, task_08, task_09, task_20, task_21, task_22, task_23, task_27, task_28 (15 specs)
**Analyst:** task-analyzer agent
**Working location:** `/home/papa-jochy/prj/ai-workflows-m20/` (worktree on `workflow_optimization` branch)
**Reference:** round 2 baseline at commit 6186c18 (2 HIGH + 6 MEDIUM + 2 LOW); round 2 analysis overwritten by this report.

## Summary

| Severity | Count |
| --- | --- |
| 🔴 HIGH | 0 |
| 🟡 MEDIUM | 4 |
| 🟢 LOW | 2 |
| Total | 6 |

**Stop verdict:** OPEN

(Zero HIGH; 4 MEDIUM concentrate on the round-2 H1 fix not propagating to README + T06; 2 LOW on path-shape residuals in tests + an AC reference. Convergence trajectory: round 1 → round 2 → round 3 = 6/2/0 HIGH and 17/6/4 MEDIUM. One more round should clear or push to LOW-only.)

The findings here are **all propagation residuals from the round-2 H1 fix.** Round 2 corrected T22 to "raw counts only; T06 owns the proxy", but the change did not flow back to (a) the README task-pool table that describes T22's deliverables, (b) the T06 spec that consumes T22's data and still claims "quota proxy" is in T22's record, and (c) two stray path-shape citations (T03 test description; T04 AC #3) that reference the convention they didn't pick.

This is **not loop-failure**. All 6 findings are mechanical and locally-correct edits. No new architectural drift, no KDR violation, no new user-arbitration question.

---

## Findings

### 🟡 MEDIUM

#### M1 — README task-pool row for T22 still claims it captures the "Max-quota consumption proxy"; contradicts the round-2 H1 fix that moved proxy ownership to T06

**Task:** README.md (M20 milestone README, line 123) — affects how T22 + T06 relate.
**Location:** README.md line 123:
> `| 22 | **NEW** — Per-cycle token + cost telemetry per agent (wrapper captures cache + input + output tokens, model, effort, **and Max-quota consumption proxy**; persists to runs/<task>/cycle_<N>/<agent>.usage.json). **Lands second in Phase C** — T06 study cannot produce evidence without it. | NEW (research-brief T22) | Model-tier / code | 📝 Candidate |`

**Issue:** Round 2 H1 fix (verified holding in T22 spec lines 43, 90, 149) made T22 capture **raw token counts only**, with quota / cost proxies computed by T06's analysis script. README task-pool row 123 was not updated and still bolds **"Max-quota consumption proxy"** as one of T22's captured fields. Three downstream effects:

1. **Status-surface drift.** CLAUDE.md non-negotiable: per-task spec, milestone README task-pool row, milestone "Done when" exit criteria flip together. The T22 spec landed the round-2 fix; the README row didn't track it. At T22 close-time the Auditor will flag this as status-surface mismatch (HIGH per Auditor's design-drift catch).

2. **Builder confusion.** The T22 Builder reading both spec + README sees contradictory "captures the quota proxy" (README) vs "raw counts only — T06 owns the proxy" (spec). The CLAUDE.md non-negotiable says spec wins on conflict, so T22's Builder likely resolves correctly — but the disagreement is preventable.

3. **Cascades into M2 + M3 below.** T06's spec inherits the same outdated framing.

**Recommendation:** Update README line 123's T22 row description to match the spec's round-2-corrected scope (raw counts only at capture; T06's analysis script computes the proxy from those counts).

**Apply this fix:**

`old_string` (in README.md line 123):
```
| 22 | **NEW** — Per-cycle token + cost telemetry per agent (wrapper captures cache + input + output tokens, model, effort, **and Max-quota consumption proxy**; persists to `runs/<task>/cycle_<N>/<agent>.usage.json`). **Lands second in Phase C** — T06 study cannot produce evidence without it. | NEW (research-brief T22) | Model-tier / code | 📝 Candidate |
```

`new_string`:
```
| 22 | **NEW** — Per-cycle token telemetry per agent (wrapper captures **raw counts only**: cache + input + output tokens, model, effort, wall-clock, verdict; persists to `runs/<task>/cycle_<N>/<agent>.usage.json`). Per-cell quota / cost proxies are computed by T06's analysis script from these raw counts (T22 is the measurement substrate; T06 owns the proxy / aggregation layer per round-2 H1 fix). **Lands second in Phase C** — T06 study cannot produce evidence without T22's records. | NEW (research-brief T22) | Model-tier / code | 📝 Candidate |
```

---

#### M2 — T06 §What to Build line 14 sources the quota proxy from "T22's quota proxy"; T22 doesn't have one per the round-2 H1 fix

**Task:** task_06_shadow_audit_study.md
**Location:** task_06.md line 14:
> `- **Max-subscription weekly-quota consumption delta** (binding constraint per KDR-003). Sourced from T22's quota proxy. **Primary metric** for the GO/NO-GO recommendation.`

**Issue:** Round 2 H1 fix (T22 captures raw counts only; T06's analysis script computes the proxy) is correctly inscribed in T22's spec — but T06's spec text still says the **delta is sourced from T22's quota proxy**. Per the corrected layering, T22 has no `quota_consumption_proxy` field; T06's own analysis script must compute the proxy from T22's `input_tokens` + `output_tokens` + `cache_creation_input_tokens` + `cache_read_input_tokens` raw counts, applying a per-model coefficient (API-price ratio, observed Max-quota consumption from the T06 runs themselves, or both) at analysis time.

A T06 Builder reading line 14 will look in T22's records for a `quota_consumption_proxy` field that doesn't exist. They'll either (a) infer the corrected layering from T22's spec and proceed correctly, or (b) file a "T22 missing field" issue, ignoring T22's spec as authoritative. Both outcomes waste cycles.

**Recommendation:** Update T06 line 14's wording to match the corrected layering: T06's analysis script computes the proxy from T22's raw counts.

**Apply this fix:**

`old_string` (in task_06.md line 14):
```
- **Max-subscription weekly-quota consumption delta** (binding constraint per KDR-003). Sourced from T22's quota proxy. **Primary metric** for the GO/NO-GO recommendation.
```

`new_string`:
```
- **Max-subscription weekly-quota consumption delta** (binding constraint per KDR-003). Computed by T06's own analysis script from T22's raw `input_tokens` + `output_tokens` + `cache_*` records (per-model coefficient applied at analysis time — API-price ratio and / or observed Max-quota consumption from the T06 runs themselves). **Primary metric** for the GO/NO-GO recommendation.
```

---

#### M3 — T06 §Methodology line 51 describes T22's record format as including "quota-proxy"; same residual as M2 in a different paragraph

**Task:** task_06_shadow_audit_study.md
**Location:** task_06.md line 51:
> `T22's record format (input/output tokens + cache-* + quota-proxy + wall-clock + verdict + cycle-count) is exactly the data the study consumes; no additional instrumentation needed.`

**Issue:** Same residual from the round-2 H1 fix. T22's record format contains `input_tokens`, `output_tokens`, `cache_creation_input_tokens`, `cache_read_input_tokens`, `wall_clock_seconds`, `model`, `effort`, `verdict`, `fragment_path`, `section`, `task`, `cycle`, `agent`, `spawn_ts`, `complete_ts` (verified against T22 spec lines 23–41). It does **not** contain a `quota_consumption_proxy` field per the H1 fix. T06's claim that T22's record format includes "quota-proxy" is wrong.

The "+ cycle-count" framing is also slightly off — T22 records `cycle: <int>` per spawn, not a cycle-count aggregate. T06's analysis script aggregates per-cell.

**Recommendation:** Correct line 51's record-format description to match T22's actual fields.

**Apply this fix:**

`old_string` (in task_06.md line 51):
```
T22's record format (input/output tokens + cache-* + quota-proxy + wall-clock + verdict + cycle-count) is exactly the data the study consumes; no additional instrumentation needed.
```

`new_string`:
```
T22's record format (input/output tokens + cache-creation/read tokens + wall-clock + model + effort + verdict, per spawn) is exactly the raw measurement substrate the study consumes; T06's own analysis script computes per-cell quota / cost proxy aggregations from those raw counts (per round-2 H1 layering — T22 substrate, T06 analysis layer).
```

---

#### M4 — T06 §What to Build line 12 still uses the legacy `runs/<task>/<cycle>/` path form; missed by round-2 M3 path standardization

**Task:** task_06_shadow_audit_study.md
**Location:** task_06.md line 12:
> `- **Token-cost delta.** Total input + output tokens consumed per cell. Sourced from T22's `runs/<task>/<cycle>/<agent>.usage.json` records.`

**Issue:** Round 2 M3 fix standardized path convention to nested `runs/<task>/cycle_<N>/<agent>.usage.json` (verified across T01, T02, T03, T05, T08, T22, T27, README). T06 was missed in the round-2 mechanical replace_all — line 12 still uses `runs/<task>/<cycle>/<agent>.usage.json` (legacy `<cycle>` shorthand without the `cycle_` prefix).

Same failure shape as round-2 M3 against T08: a Builder reading T06 sees one path shape; the rest of the milestone uses a different shape. Either resolves correctly by lucky inference, files a "wrong path" issue, or lands inconsistent with the rest of the milestone.

**Recommendation:** Replace `runs/<task>/<cycle>/<agent>.usage.json` → `runs/<task>/cycle_<N>/<agent>.usage.json` in T06.

**Apply this fix:**

`old_string` (in task_06.md line 12):
```
- **Token-cost delta.** Total input + output tokens consumed per cell. Sourced from T22's `runs/<task>/<cycle>/<agent>.usage.json` records.
```

`new_string`:
```
- **Token-cost delta.** Total input + output tokens consumed per cell. Sourced from T22's `runs/<task>/cycle_<N>/<agent>.usage.json` records (path convention per round-2 M3 — nested `cycle_<N>/` directory).
```

---

### 🟢 LOW

#### L1 — T03 test descriptions on lines 93–95 use the flat `cycle_1_summary.md` filename form; spec elsewhere uses nested `cycle_1/summary.md`

**Task:** task_03_in_task_cycle_compaction.md
**Issue:** T03's §directory layout (lines 55–82) is the canonical statement of path convention for the milestone — every per-cycle artifact lives at `runs/<task>/cycle_<N>/<artifact>.md`, including `cycle_<N>/summary.md` (line 60). T03's own test descriptions on lines 93–95 use the flat-with-underscore form `cycle_1_summary.md` (filename in the parent dir, not nested):

> `- After cycle 1: runs/<task>/cycle_1_summary.md exists, parses to the expected structure.`
> `- After cycle 2: cycle_2_summary.md exists; cycle_1_summary.md unchanged.`
> `- After cycle 3: cycle_3_summary.md exists.`

A T03 Builder reading the test descriptions either (a) writes the test against the flat form (fails the spec's directory-layout AC) or (b) reads the spec's directory layout as authoritative and writes the nested form (test description doesn't match what they wrote). Builder absorbs at implement-time but it's preventable.

**Recommendation:** Replace the three test-description lines to use the nested form: `cycle_1/summary.md`, `cycle_2/summary.md`, `cycle_3/summary.md` instead of `cycle_1_summary.md` etc.

**Push to spec:** yes — append to T03 carry-over for Builder to absorb at implement-time.

---

#### L2 — T04 §Acceptance criteria #3 references "`runs/autopilot-<run-ts>/` directory convention"; the round-2 M5 fix chose flat hyphenated (no directory)

**Task:** task_04_cross_task_iteration_compaction.md
**Issue:** T04's round-2 M5 fix pinned **flat hyphenated** path convention (line 65–78: each iteration emits `runs/autopilot-<run-ts>-iter<N>-shipped.md` flat at `runs/`, no per-run subdirectory). The §Acceptance criteria #3 (line 100) still says:

> `3. runs/autopilot-<run-ts>/ directory convention documented in autopilot.md.`

This references a directory (`runs/autopilot-<run-ts>/`) that doesn't exist in the chosen flat convention — there is no `autopilot-<run-ts>/` directory at all; everything lives at `runs/autopilot-<run-ts>-iter<N>(-shipped)?.md` directly.

A T04 Builder reading AC #3 either (a) re-interprets the AC charitably as "the flat-path naming convention" or (b) tries to match the AC literally and creates a redundant directory. The Auditor will flag the latter as inconsistent with §Path convention.

**Recommendation:** Reword AC #3 to match the flat convention: "Path naming convention (`runs/autopilot-<run-ts>-iter<N>(-shipped)?.md`) documented in autopilot.md per §Path convention."

**Push to spec:** yes — append to T04 carry-over for Builder to absorb at implement-time.

---

## What's structurally sound

Round 2 fixes that held up cleanly:

- **H1 (T22 quota proxy removal)** — T22 spec lines 43, 90, 149 all correctly say "raw counts only; T06 owns the proxy". Smoke test asserts `input_tokens==100`, no `quota_consumption_proxy`. Telemetry summary table is 8 columns (Quota proxy column dropped). Round-3 M1+M2+M3 are propagation residuals to README + T06, not regression in T22 itself.
- **H2 (T05 duplicate Mechanism block)** — T05 has exactly one `## Mechanism — fragment files` section (line 37). Reviewer-agent updates use `cycle_<N>/`. Smoke grep tightened to pin `cycle_<N>/` form.
- **M1 (T03 Out-of-scope Phase 5 wording)** — T03 line 138 correctly says "T03 only extends Phase 5". No internal contradiction.
- **M2 (T20 Phase 7 reference dropped)** — T20 line 40 says "Phases 5 and 6 (issue-file write, forward-deferral propagation) stay untouched. The live auditor has Phases 1–6 only (no Phase 7)." Clean.
- **M3 (T08 path standardization)** — All five T08 sites use `runs/<task>/cycle_<N>/`. Verified via grep — zero `<cycle>` legacy form in T08.
- **M4 (T01 nested paths)** — T01 line 34 (builder handoff), 72, 76 (agent_raw_return) all use `runs/<task>/cycle_<N>/<filename>` per audit M11.
- **M5 (T04 flat hyphenated convention)** — T04 §Path convention (lines 65–78) pins the flat form; the §Out-of-scope and §Deliverables match. Round-3 L2 is a stale residual at AC #3 only, not a contradiction with the chosen path shape.
- **M6 (T02 regex proxy committed; tiktoken hedge dropped)** — T02 line 48 correctly says "via the **regex-based proxy** ... no `tiktoken` test-only dep added per round-1 L8 carry-over". Path is `runs/<task>/cycle_<N>/spawn_<agent>.tokens.txt`.
- **All round-2 LOWs (L1, L2)** — both pushed cleanly to per-spec carry-over sections (T22 carry-over line 175 for L1; T05 carry-over line 177 for L2).

KDR + layer rule: **No drift.** M20's specs do not introduce upward imports, do not move source-of-truth off the MCP substrate, do not import the Anthropic SDK, do not bypass the layer rule. The seven KDRs (002 / 003 / 004 / 006 / 008 / 009 / 013) plus KDR-014 are all preserved.

Cross-spec consistency at the dependency level: T01 → T05 / T08 (blocking) is clean. T21 → T06 / T07 (blocking) is clean. T22 → T06 / T23 / T27 (blocking) is structurally correct, modulo the M2+M3 wording residuals. T03 → T20 / T27 (synergistic) is clean. T28 → T03+T04 (composition) is clean.

Surface-feasibility theme — all round-1 + round-2 surface-feasibility wins (T01 falling back to orchestrator-side parsing; T22 surface-check pre-step; T27 Path B only; T28 broader surface check) are intact in round 3.

---

## Cross-cutting context

- **Convergence trajectory is healthy.** Round 1 → 2 → 3 = 6/2/0 HIGH; 17/6/4 MEDIUM; 8/2/2 LOW. The MEDIUM count is non-monotone (6 → 4) but each round's MEDIUMs are different items — round 3's are pure round-2-fix-propagation residuals (read: the round-2 fixes were locally correct but didn't sweep all cross-references).
- **Round 3 fix mechanics are uniformly mechanical.** Every M1/M2/M3/M4 has a literal `old_string → new_string` edit. No user arbitration needed. L1 + L2 are spec carry-over text, also mechanical. Estimated time-to-clear: 5–10 minutes of edits across 3 files (README.md, task_06.md, task_03.md, task_04.md — three with carry-over additions).
- **Project memory state.** Memory shows M20 active (autopilot validated 2026-04-27); CS300 pivot status unchanged; M16 T01 shipped. M20 is not on hold or pending external trigger.
- **Surface-feasibility theme is now stable.** Round 1 had 3 surface-feasibility issues; round 2 had 1; round 3 has 0. The pattern "Anthropic SDK exposes X but Claude Code Task wrapper may not surface X" is fully absorbed into T01 / T22 / T27 / T28 spec design. Future rounds (Builder + Auditor implementation) will discover what's actually accessible.
- **README is mostly consistent with specs.** Round 3 finding M1 is the only README inconsistency (the T22 task-pool row); all other README references (cycle_<N>/ paths, dependencies, exit criteria, KDR-014 affirmation) tracked the round-2 fixes correctly. The T22-row miss happened because round 2 fixed T22 spec but didn't sweep the README task-pool description — a category of fix the orchestrator can add to its round-applies checklist.
- **Round 3 anticipated effort to clear:** ~10 minutes of mechanical edits (4 MEDIUMs across 3 files; 2 LOWs to carry-over).
- **No new HIGH-severity findings.** The round-2 → round-3 transition cleared all HIGH findings, which matches healthy convergence on a milestone of this size + complexity.

---

**Verdict for round 3:** OPEN — 0 HIGH + 4 MEDIUM + 2 LOW. Round 4 should converge to LOW-only or CLEAN. Loop is on track.
