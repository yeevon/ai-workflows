# M20 — Autonomy Loop Optimization — Task Analysis

**Round:** 2
**Analyzed on:** 2026-04-27
**Specs analyzed:** task_01, task_02, task_03, task_04, task_05, task_06, task_07, task_08, task_09, task_20, task_21, task_22, task_23, task_27, task_28 (15 specs)
**Analyst:** task-analyzer agent
**Working location:** `/home/papa-jochy/prj/ai-workflows-m20/` (worktree on `workflow_optimization` branch)
**Reference:** round 1 baseline at commit 05f630b (6 HIGH + 17 MEDIUM + 8 LOW); round 1 analysis overwritten by this report.

## Summary

| Severity | Count |
| --- | --- |
| 🔴 HIGH | 2 |
| 🟡 MEDIUM | 6 |
| 🟢 LOW | 2 |
| Total | 10 |

**Stop verdict:** OPEN

(2 HIGH + 6 MEDIUM block the loop. Round-1 fixes mostly held — H1, H3, H5, H6, M1, M3, M6, M7, M8, M9 (partial), M10, M11 (partial), M12 (partial), M13, M14 (partial), M15, M16, M17, plus all 8 LOWs land cleanly. Round-1 H2 (terminal-gate restructuring), H4 (runs/ paths), and M2 (T01 blocking) are also clean. The remaining findings are: (a) **partial-fix residuals** — the round-1 mechanical replace_all left contradictory paragraphs in T03, T05, and T22; (b) **one new issue** — T22 smoke test asserts a field that the M9 fix removed; (c) **one cross-spec inconsistency** newly visible — T01's `runs/<task>/agent_<name>_raw_return.txt` (top-level) contradicts T03's M11-fixed nesting rule.)

This is **not loop-failure**. Findings are concrete + mechanical-to-fix, not architectural drift. Convergence is on track; one more round should clear or push to LOW-only.

---

## Findings

### 🔴 HIGH

#### H1 — T22 smoke test asserts `quota_consumption_proxy` field that the M9 fix removed

**Task:** task_22_per_cycle_telemetry.md
**Location:** task_22.md line 148:
> `assert d['agent']=='auditor' and d['quota_consumption_proxy']>0 and d['verdict']=='PASS'`

Also: line 90 (the Telemetry-summary aggregation table T22's hook appends to T04's iter_shipped.md) still has a `Quota proxy` column.

**Issue:** Round 1 M9 fix removed per-model coefficient computation at T22 capture time and reframed: "T22 captures **raw token counts only** ... per-cell quota-proxy aggregations are computed by **T06's analysis script**." The §Captured fields JSON (lines 23–41) was correctly stripped of the `quota_consumption_proxy` field. But:

1. **The smoke test (line 148) still asserts the field exists.** When the Builder lands T22 per the M9-corrected spec, the JSON file will not contain `quota_consumption_proxy`. The smoke command's `python -c "...d['quota_consumption_proxy']>0..."` will raise `KeyError` — the smoke fails at runtime (HIGH per CLAUDE.md *Code-task verification is non-inferential*: smoke that references a wrong-name field is HIGH).
2. **The Telemetry-summary table (line 90) still lists `Quota proxy` as a column.** If T22 owns the aggregation table format, then T22's aggregation script still has to compute the proxy at aggregation time — which is the wrong layer per M9 (T06 is supposed to own that). Either T22's aggregation table drops the column, or T22's "owns aggregation" claim is wrong and T06 should own the entire iter_shipped Telemetry-summary insertion.

**Recommendation:** Two coordinated edits. Pick one of (a) or (b) for the layering question:

- (a) **T22 owns aggregation, raw-only.** Drop `Quota proxy` column from line 90's table. Drop `quota_consumption_proxy` assertion from line 148. T06's analysis script computes the proxy in its own analysis output (`design_docs/analysis/autonomy_model_dispatch_study.md`), not in the iter_shipped artifact.
- (b) **T06 owns aggregation including proxy.** T22 drops the entire "Aggregation hook for T04" section (lines 82–94). T06 takes ownership of the iter_shipped Telemetry-summary insertion AND the proxy. T22's deliverable scope shrinks to "per-spawn JSON capture only."

Option (a) is cleaner — it preserves the round-1 layering (T22 measurement substrate; T06 analysis layer) while honouring the M9 raw-counts decision. Option (b) is simpler but moves more work to T06.

**Apply this fix (option a — recommended):**

`old_string` (in task_22.md line 148):
```
  assert d['agent']=='auditor' and d['quota_consumption_proxy']>0 and d['verdict']=='PASS'"
```

`new_string`:
```
  assert d['agent']=='auditor' and d['input_tokens']==100 and d['verdict']=='PASS'"
```

Also in task_22.md line 90 — drop the `Quota proxy` column from the Telemetry-summary table:

`old_string`:
```
| Cycle | Agent | Model | Effort | Input tokens | Output tokens | Cache hit % | Quota proxy | Verdict |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
```

`new_string`:
```
| Cycle | Agent | Model | Effort | Input tokens | Output tokens | Cache hit % | Verdict |
| --- | --- | --- | --- | --- | --- | --- | --- |

(Quota / cost proxies — per audit M9 — are computed by T06's analysis script in its own output (design_docs/analysis/autonomy_model_dispatch_study.md), not at T22's capture or T04's iter_shipped retrofit time. T22 + T04's iter_shipped table is raw-counts + cache-hit-% only.)
```

Note: line 144 in the smoke test (`test -f runs/m20_t22_smoke/1/auditor.usage.json`) also uses the old non-nested path `m20_t22_smoke/1/` rather than `m20_t22_smoke/cycle_1/` — fix in the same edit pass:

`old_string` (line 133-141 area):
```
mkdir -p runs/m20_t22_smoke/1
python scripts/orchestration/telemetry.py spawn \
  --task m20_t22_smoke --cycle 1 --agent auditor \
  --model claude-opus-4-7 --effort high
python scripts/orchestration/telemetry.py complete \
  --task m20_t22_smoke --cycle 1 --agent auditor \
  --input-tokens 100 --output-tokens 50 \
  --cache-creation 80 --cache-read 20 \
  --verdict PASS --fragment-path '/tmp/x'

# Verify the record landed
test -f runs/m20_t22_smoke/1/auditor.usage.json && echo "record landed"
```

`new_string`:
```
mkdir -p runs/m20_t22_smoke/cycle_1
python scripts/orchestration/telemetry.py spawn \
  --task m20_t22_smoke --cycle 1 --agent auditor \
  --model claude-opus-4-7 --effort high
python scripts/orchestration/telemetry.py complete \
  --task m20_t22_smoke --cycle 1 --agent auditor \
  --input-tokens 100 --output-tokens 50 \
  --cache-creation 80 --cache-read 20 \
  --verdict PASS --fragment-path '/tmp/x'

# Verify the record landed (per audit M11 — nested cycle_<N>/ directory)
test -f runs/m20_t22_smoke/cycle_1/auditor.usage.json && echo "record landed"
```

---

#### H2 — T05 has a duplicate `## Mechanism — fragment files` section, and the second one uses the legacy `<cycle>` shorthand contradicting the M11 standardization

**Task:** task_05_parallel_terminal_gate.md
**Location:** task_05.md lines 37–48 vs 49–61.

**Issue:** Round 1 prepended a corrected Mechanism block (lines 37–48 with `runs/<task>/cycle_<N>/<agent>-review.md`) but did not delete the old Mechanism block (lines 49–61 with `runs/<task>/<cycle>/<agent>-review.md`). The spec now has two `## Mechanism — fragment files` headings back-to-back, with contradictory path conventions:

- Lines 41–43 (block 1): `runs/<task>/cycle_<N>/sr-dev-review.md` (correct, post-M11)
- Lines 53–55 (block 2): `runs/<task>/<cycle>/sr-dev-review.md` (legacy form, pre-M11)
- Line 57 (block 2): `<task> is m<N>_t<NN>` (single-digit M, contradicts M12 fix that pinned `m<MM>_t<NN>` zero-padded)
- Line 68 (Reviewer-agent updates section): `runs/<task>/<cycle>/<agent>-review.md` (legacy form)
- Line 158 (smoke test grep): `runs/.*<cycle>.*review.md\|runs/<task>/<cycle>/` (greps for legacy form)

A Builder reading the spec sees one section, then a contradictory section immediately after — picks one convention, fails the smoke test of the other. The smoke test on line 158 will pass either way (its grep is permissive enough to match both forms), but the production paths the Builder lands will be inconsistent across spec citation sites.

**Recommendation:** Delete the duplicate block (lines 49–61). Update lines 68 and 158 to use the canonical `cycle_<N>/` form per M11.

**Apply this fix:**

Delete task_05.md lines 49–61 (the second Mechanism block including its blank-line separator):

`old_string`:
```
## Mechanism — fragment files (per research brief §Lens 1.4)

Each reviewer writes its verdict to a deterministic fragment path instead of editing the issue file directly:

- sr-dev → `runs/<task>/<cycle>/sr-dev-review.md`
- sr-sdet → `runs/<task>/<cycle>/sr-sdet-review.md`
- security-reviewer → `runs/<task>/<cycle>/security-review.md`

(Where `<task>` is `m<N>_t<NN>` and `<cycle>` is the current cycle number.)

This avoids file-write contention on the issue file. The three reviewers run truly concurrently; no Edit-collision races. After all three return, the orchestrator reads the three fragment files in one Read pass and stitches them into the issue file under their respective `## Sr. Dev review`, `## Sr. SDET review`, `## Security review` sections in one Edit pass.

The Read tool's "Read multiple files at once" pattern (one tool message, multiple Read invocations) keeps the stitch step single-turn.
```

`new_string`:
```
The Read tool's "Read multiple files at once" pattern (one tool message, multiple Read invocations) keeps the stitch step single-turn.
```

Also in task_05.md line 68 (`## Reviewer-agent updates` section):

`old_string`:
```
- **New:** "Write your full review to `runs/<task>/<cycle>/<agent>-review.md`. The orchestrator stitches it into the issue file in a follow-up turn. Your `## Return to invoker` value (T01) points `file:` at the fragment path; `section:` is the `## <name> review` heading the orchestrator will use when stitching."
```

`new_string`:
```
- **New:** "Write your full review to `runs/<task>/cycle_<N>/<agent>-review.md` (where `<task>` is the zero-padded `m<MM>_t<NN>` shorthand per audit M12 and cycle_<N>/ is the per-cycle subdirectory per audit M11). The orchestrator stitches it into the issue file in a follow-up turn. Your `## Return to invoker` value (T01) points `file:` at the fragment path; `section:` is the `## <name> review` heading the orchestrator will use when stitching."
```

Also in task_05.md line 158 (smoke test grep):

`old_string`:
```
  grep -q "runs/.*<cycle>.*review.md\|runs/<task>/<cycle>/" .claude/agents/$agent.md \
```

`new_string`:
```
  grep -q "runs/.*cycle_<N>.*review.md\|runs/<task>/cycle_<N>/" .claude/agents/$agent.md \
```

---

### 🟡 MEDIUM

#### M1 — T03 §Out of scope contradicts T03's own §Deliverables on Phase 5 vs Phase 7

**Task:** task_03_in_task_cycle_compaction.md
**Location:** task_03.md line 138:
> `**Modifying the Auditor's existing audit phases** — T03 only adds Phase 7. Phases 1–6 (design-drift check, gate re-run, AC grading, critical sweep, issue-file write, forward-deferral propagation) are unchanged.`

**Issue:** Round 1 M14 fix correctly moved T03 from "new Phase 7" to "extend existing Phase 5" (lines 35-39: `extend Phase 5 (issue-file write) to also emit cycle_<N>/summary.md ... No new phase numbering introduced; Phases 1-6 stay 1-6`). The Out-of-scope section was not touched and still says "T03 only adds Phase 7." Internal contradiction within a single spec.

The live auditor.md has Phases 1–6 (verified — no Phase 7 exists). T03 should not introduce a Phase 7. The Out-of-scope wording needs to match the M14-corrected Deliverables.

**Recommendation:** Replace "T03 only adds Phase 7" with "T03 only extends Phase 5 (issue-file write)" so all references in the spec agree.

**Apply this fix:**

`old_string` (in task_03.md line 138):
```
- **Modifying the Auditor's existing audit phases** — T03 only adds Phase 7. Phases 1–6 (design-drift check, gate re-run, AC grading, critical sweep, issue-file write, forward-deferral propagation) are unchanged.
```

`new_string`:
```
- **Modifying the Auditor's existing audit phases beyond Phase 5** — T03 only extends Phase 5 (issue-file write) with the cycle-summary emission per audit M14. Phases 1–4 (design-drift check, gate re-run, AC grading, critical sweep) and Phase 6 (forward-deferral propagation) are unchanged. No new phase numbering introduced.
```

---

#### M2 — T20 §Mechanism mentions a "Phase 7" that doesn't exist in the live auditor (confusing reference)

**Task:** task_20_carry_over_checkbox_cargo_cult_extended.md
**Location:** task_20.md line 40:
> `Both inspections live within Phase 4's existing critical-sweep mandate; no new phase is created. Phase 5 / Phase 6 / **Phase 7** numbering stays untouched.`

**Issue:** The live auditor.md has Phases 1-6 only (verified: lines 19, 35, 41, 45, 58, 101). Phase 7 does not exist. Round 1 M14 also rejected the "T03 adds Phase 7" framing (T03 now extends Phase 5). T20's Mechanism still references "Phase 7 numbering stays untouched" as a reassurance — which falsely implies Phase 7 is a thing, contradicts the M14-corrected T03 framing, and would confuse the Builder.

Minor — easily mistaken as drift if not flagged.

**Recommendation:** Drop "Phase 7" from the list. The reassurance is "Phases 5 / 6 numbering stays untouched."

**Apply this fix:**

`old_string` (in task_20.md line 40):
```
Both inspections live within Phase 4's existing critical-sweep mandate; no new phase is created. Phase 5 / Phase 6 / Phase 7 numbering stays untouched. (T03's cycle-summary emission, per audit M14, similarly extends an existing phase rather than introducing Phase 7.)
```

`new_string`:
```
Both inspections live within Phase 4's existing critical-sweep mandate; no new phase is created. Phases 5 and 6 (issue-file write, forward-deferral propagation) stay untouched. The live auditor has Phases 1–6 only (no Phase 7). Per audit M14, T03's cycle-summary emission similarly extends an existing phase (Phase 5) rather than introducing a new one.
```

---

#### M3 — T08 uses `runs/<task>/<cycle>/` (legacy form) where every other M11-corrected spec uses `runs/<task>/cycle_<N>/`

**Task:** task_08_gate_output_integrity.md
**Location:** task_08.md lines 17, 19, 32, 60, 69, plus the AC chain.

**Issue:** Round 1 M11 standardized the path convention to nested `runs/<task>/cycle_<N>/` (e.g. T03 line 9, T22 line 9, T05 line 41-43, README lines 35/40/54/61, T27 line 26). T08 was missed in the round-1 mechanical replace_all — five citations still use `runs/<task>/<cycle>/`.

The `<cycle>` shorthand is ambiguous (could mean `cycle_<N>` or `<N>` directly). The M11 fix makes the shape concrete: nested directory with `cycle_` prefix on the directory name. T08 should match.

A Builder satisfying T08 lands `runs/m20_t08/<cycle>/gate_pytest.txt` interpreting `<cycle>` literally as `<cycle>` (filesystem-friendly but non-conformant), or as `1` / `2` / `3` (a different shape than the M11-standardized `cycle_1/` / `cycle_2/`), or correctly as `cycle_1/` (matches T03/T05/T22 but only by lucky inference). All three failure modes are real.

**Recommendation:** `replace_all` `runs/<task>/<cycle>/` → `runs/<task>/cycle_<N>/` in T08.

**Apply this fix:** In task_08_gate_output_integrity.md, `replace_all` occurrences of `runs/<task>/<cycle>/` → `runs/<task>/cycle_<N>/`. Five sites (lines 17, 19, 32, 60, 69).

---

#### M4 — T01's verdict-table durable-artifact paths use top-level `runs/<task>/...` form; contradicts T03's M11-corrected nested form for `agent_<name>_raw_return.txt`

**Task:** task_01_sub_agent_return_value_schema.md vs task_03_in_task_cycle_compaction.md
**Location:**

- T01 line 34 (verdict table for `builder` row): `runs/<task>/cycle_<N>_builder_handoff.md` (top-level filename with `cycle_<N>_` prefix; not nested)
- T01 line 72: `runs/<task>/agent_<name>_raw_return.txt` (top-level)
- T01 line 76: same (smoke surface text)
- T03 line 72 (directory layout): `agent_<name>_raw_return.txt` listed inside `cycle_<N>/` block
- T03 line 81: `**agent_<name>_raw_return.txt** lives **per-cycle** (full audit trail), not top-level. Per cycle, per agent, latest invocation wins within that cycle.`

**Issue:** T03's M11-corrected directory layout is authoritative on per-cycle artifact placement. T01 was not updated — its verdict-table and orchestrator-side parser section still use the pre-M11 top-level form. Two specs disagree on where the same file lives:

- T01 says `runs/<task>/agent_<name>_raw_return.txt` (one file per agent across ALL cycles, latest wins).
- T03 says `runs/<task>/cycle_<N>/agent_<name>_raw_return.txt` (one file per agent per cycle, full audit trail).

These are **functionally different** decisions (round 1 M11 picked the per-cycle form for safer audit trail). T01 should match. Same for the builder handoff — should be `runs/<task>/cycle_<N>/builder_handoff.md` (per-cycle file inside per-cycle dir), not `runs/<task>/cycle_<N>_builder_handoff.md` (top-level file with prefix).

**Recommendation:** Update T01's verdict table line 34 and parser-section lines 72 + 76 to use the nested `cycle_<N>/` form.

**Apply this fix:**

In task_01.md line 34:

`old_string`:
```
| `builder` | `BUILT` / `BLOCKED` / `STOP-AND-ASK` | `runs/<task>/cycle_<N>_builder_handoff.md` (NEW per T03) | `—` |
```

`new_string`:
```
| `builder` | `BUILT` / `BLOCKED` / `STOP-AND-ASK` | `runs/<task>/cycle_<N>/builder_handoff.md` (NEW per T03 — per-cycle nested directory per audit M11) | `—` |
```

In task_01.md line 72:

`old_string`:
```
1. Captures the agent's full text return into `runs/<task>/agent_<name>_raw_return.txt` (durable record for debugging).
```

`new_string`:
```
1. Captures the agent's full text return into `runs/<task>/cycle_<N>/agent_<name>_raw_return.txt` (durable record for debugging — per-cycle nested directory per audit M11; T03 §directory layout is authoritative on artifact placement).
```

In task_01.md line 76:

`old_string`:
```
5. On any failure: halt the loop, surface `🚧 BLOCKED: agent <name> returned non-conformant text — see runs/<task>/agent_<name>_raw_return.txt for full output`. Do not auto-retry.
```

`new_string`:
```
5. On any failure: halt the loop, surface `🚧 BLOCKED: agent <name> returned non-conformant text — see runs/<task>/cycle_<N>/agent_<name>_raw_return.txt for full output`. Do not auto-retry.
```

---

#### M5 — T04 §What to Build line 11 cites a hyphenated flat path while §Deliverables + §Directory convention use a nested form

**Task:** task_04_cross_task_iteration_compaction.md
**Location:**

- task_04.md line 11: `T04 emits a structured **iteration-shipped artifact** (`runs/autopilot-<run-ts>-iter<N>-shipped.md`) at each autopilot iteration boundary.` (flat hyphenated)
- task_04.md line 54: `Update /autopilot's outer-loop Step D to write the iteration-shipped artifact at `runs/autopilot-<run-ts>/iter_<N>_shipped.md`.` (nested directory)
- task_04.md lines 65–74: directory convention shows `runs/autopilot-<run-ts>/iter_1.md` + `iter_1_shipped.md` (nested directory)
- existing autopilot.md line 66: `Recommendation file path: runs/autopilot-<run-timestamp>-iter<N>.md` (flat hyphenated — TODAY's convention)

**Issue:** Three different conventions appear: T04's §What to Build uses the flat hyphenated form (matches today's autopilot but with `-shipped` suffix). T04's §Deliverables + §Directory convention use a nested directory form. Today's autopilot.md uses the flat hyphenated form.

If T04 ships nested, today's `iter_<N>.md` recommendation files (per autopilot.md line 66) and the new `iter_<N>_shipped.md` close-out files end up in different locations — the recommendation files at `runs/autopilot-<run-ts>-iter<N>.md` (flat) and the shipped files at `runs/autopilot-<run-ts>/iter_<N>_shipped.md` (nested). Inconsistent. T04 line 69 even claims `iter_1.md (existing — recommendation file, queue-pick output)` would land in the nested directory, but today autopilot.md emits it flat — so the Builder would have to also migrate today's recommendation-file path to the nested form, which is unsignaled scope.

**Recommendation:** Decide between flat and nested. The nested form is cleaner long-term but is a path migration for today's autopilot recommendation-file convention.

Option (a) — pin nested (cleaner): T04's deliverables include migrating autopilot.md's existing recommendation-file path to the nested form. Adds scope but consistent.
Option (b) — pin flat (less scope): rewrite T04's deliverables + directory convention to use the flat hyphenated form (`runs/autopilot-<run-ts>-iter<N>-shipped.md`). Matches today's convention; no migration needed.

(b) is the safer minimum-viable choice. Recommend (b) unless the user wants the nested layout for cross-iteration cleanup.

**Apply this fix (option b — recommended):** Manual — see Recommendation. Stop and ask the user if they want the migration scope expanded (option a) or want T04 narrowed to match today's flat convention (option b).

If option (b):
- Replace `runs/autopilot-<run-ts>/iter_<N>_shipped.md` → `runs/autopilot-<run-ts>-iter<N>-shipped.md` throughout task_04.md.
- Replace the directory-convention block (lines 65–74) with a flat-path note: "Each iteration emits `runs/autopilot-<run-ts>-iter<N>-shipped.md`; the kick-off recommendation file `runs/autopilot-<run-ts>-iter<N>.md` (existing) lands alongside as a sibling."

---

#### M6 — T02 still hedges between `tiktoken` and regex proxy; L8 carry-over from round 1 said pick the regex proxy across T01/T02/T03/T22/T23

**Task:** task_02_sub_agent_input_prune.md
**Location:** task_02.md line 48:
> `Each Task spawn captures the spawn-prompt size (in tokens, via `tiktoken` cl100k_base or a regex-based proxy — token-counting accuracy is not load-bearing here, magnitude is) into ...`

**Issue:** Round 1 L8 carry-over (pushed into spec carry-over sections) said: *"Pick the regex proxy across T01, T02, T03, T22, T23. Drop tiktoken references everywhere."* T01's `tiktoken` reference was dropped (verified at line 98 — uses regex proxy, no `tiktoken`). T02 is still hedging.

T01's carry-over (line 167) cites the agreement: *"Use the regex-based proxy (`len(re.findall(r"\S+", text)) * 1.3`) ... same proxy as T02 / T22 for consistency."* — this assumes T02 has already committed to it. But T02's source text still says "via `tiktoken` ... or a regex-based proxy" — undoing the consistency.

A Builder reading T02 picks one (likely whichever is mentioned first — `tiktoken`), adds it to `pyproject.toml` test-only deps, triggers the dependency-auditor agent. CLAUDE.md non-negotiable — adds review surface to a foundation task.

**Recommendation:** Drop the `tiktoken` hedge in T02 line 48. Match T01's framing.

**Apply this fix:**

`old_string` (in task_02.md line 48):
```
Each Task spawn captures the spawn-prompt size (in tokens, via `tiktoken` cl100k_base or a regex-based proxy — token-counting accuracy is not load-bearing here, magnitude is) into `runs/<task>/spawn_<agent>_<cycle>.tokens.txt`. Aggregated by T22 (per-cycle telemetry). T02 only emits the per-spawn measurement; T22 builds the aggregation surface.
```

`new_string`:
```
Each Task spawn captures the spawn-prompt size (in tokens, via the **regex-based proxy** `len(re.findall(r"\S+", text)) * 1.3` — token-counting accuracy is not load-bearing here, magnitude is; same proxy used by T01, T22, T23 for consistency; no `tiktoken` test-only dep added per round-1 L8 carry-over) into `runs/<task>/cycle_<N>/spawn_<agent>.tokens.txt`. Aggregated by T22 (per-cycle telemetry). T02 only emits the per-spawn measurement; T22 builds the aggregation surface.
```

(Note also: the path `runs/<task>/spawn_<agent>_<cycle>.tokens.txt` is top-level form. Per audit M11 it should be `runs/<task>/cycle_<N>/spawn_<agent>.tokens.txt` — nested directory, drop the `_<cycle>` suffix from the filename since the directory provides the namespace. Included in the same fix.)

---

### 🟢 LOW

#### L1 — T22's surface-check pre-step references `python scripts/orchestration/check_task_response_fields.py` but T27's surface-check rationale doesn't mention it

**Task:** task_22_per_cycle_telemetry.md (and cross-ref to task_27)
**Issue:** T22 line 15 names a one-off helper `scripts/orchestration/check_task_response_fields.py`. T27 (line 13) cites a parallel surface-check concern but routes it to T28's broader surface-check work. T28 (lines 39, Section 2 Q1) similarly references "does Claude Code's Task tool surface `context_management.edits`?" without naming a helper. There's an opportunity to consolidate: one helper script that probes the Task-tool response payload for ALL the surface-check concerns (cache-* fields for T22, `context_management.edits` for T27/T28, `outputFormat` for the T01 retrospective). The Builder for T22 will write `check_task_response_fields.py`; the Builders for T27/T28 might duplicate-write similar probes.
**Recommendation:** Add a one-line cross-reference in T22 saying "T27 + T28's surface-check questions can extend this same helper." Builder absorbs at implementation.
**Push to spec:** yes — append to T22 carry-over.

---

#### L2 — T05 §Acceptance criteria #6 + smoke test reference `runs/.*<cycle>.*review.md` regex; permissive match could miss path drift

**Task:** task_05_parallel_terminal_gate.md (separate from H2 — H2 fixes the contradictory paragraph; this is about the smoke-test grep robustness)
**Issue:** Line 158's grep `grep -q "runs/.*<cycle>.*review.md\|runs/<task>/<cycle>/"` will succeed on any path that contains "review.md" with `<cycle>` somewhere; it doesn't enforce the post-M11 `cycle_<N>/` form. After H2 lands, the grep should pin to the cycle_<N>/ form so future drift is caught.
**Recommendation:** Tighten the grep to `runs/.*cycle_<N>.*review.md`. (Already in H2's apply-fix; flag here as a separate observability concern in case H2 doesn't fully land.)
**Push to spec:** yes — append to T05 carry-over.

---

## What's structurally sound

Round 1 fixes that held up cleanly:

- **H1 (T22 ai_workflows/orchestration/ rejection)** — only references remain in the round-1 analysis text; specs are clean.
- **H3 (T21 implement.md inclusion)** — spec includes 7 commands; smoke greps for all `thinking: <literal>` shorthand variants (max/high/medium/low); verified 7 hits (6 max + 1 high) via live grep.
- **H5 (T20 M12-T01 patch as REQUIRED)** — verified missing from live auditor.md; verified present in template; T20 spec correctly says "REQUIRED — verified missing" and ports verbatim.
- **H6 (T27 Path B only)** — Path A explicitly rejected with surface-feasibility evidence; T28 owns the broader surface check; T27 cleanly Path-B-only.
- **H2 (terminal gate restructuring)** — spec correctly names old SECURITY/TEAM gate sections to delete, defines TERMINAL CLEAN/BLOCK/FIX precedence rule with security-reviewer-precedence, dependency-auditor stays conditional+standalone.
- **H4 (.cycle/ → runs/<task>/cycle_<N>/)** — README + every spec path-citation replaced (modulo M3-M5 above which are the few residual leftovers).
- **M1 (tests/orchestrator/ standardization)** — all 9 specs use `tests/orchestrator/`; zero `tests/orchestration/` references in spec sources.
- **M2 (T01 blocking T05 + T08)** — both specs correctly say "blocking" with content-rationale citations.
- **M3 (Kind: line on every spec)** — all 15 specs have a `**Kind:**` line in the Status block. T09's parser correctly references it as the source of truth with README-fallback.
- **M6 (`_common/` directory creation in T01)** — T01 line 80–82 explicitly handles `mkdir -p .claude/commands/_common/` and lists subsequent tasks that populate it.
- **M7 (T22 surface-check pre-step)** — T22 lines 13–19 correctly add the surface-check pre-step; describes IS-exposed / NOT-exposed / partial-exposure paths; downgrades T23 if cache-* fields not exposed.
- **M8 (T07 reverter-friendly commit isolation framing)** — T07 line 90–92 correctly reframes "KDR-isolation" → "reverter-friendly commit isolation (analogy to autonomy decision 2)" with explicit not-a-KDR caveat.
- **M9 (T22 raw counts only at capture; T06 owns proxy)** — §Captured fields JSON example is correctly stripped of `quota_consumption_proxy`; T06 line 14 correctly cites T22 telemetry as the source. Residual issue at line 90 (Telemetry summary table) and line 148 (smoke test) → folded into H1 above.
- **M10 (scripts/orchestration/ namespace)** — all M20-introduced helpers (telemetry.py, dispatch.py, cache_verify.py, run_t06_study.py) consistently nest under `scripts/orchestration/`.
- **M11 (T03 nested cycle_<N>/ directory layout)** — T03 §directory convention is correct; T05/T22/T27/README all align. M3+M4 above are residual leftovers in T08 + T01 only.
- **M12 (zero-padded m<MM>_t<NN> shorthand)** — T03 line 84 is canonical; T22 line 67 + T05 line 45 cite it. T05 line 57 (in the duplicate Mechanism block — to be deleted by H2) is the only residual pre-M12 reference.
- **M13 (T02 path-stays / content-goes auditor pre-load)** — T02 line 22 correctly distinguishes path references (stay) from content inlining (goes); preserves Auditor full-task-scope invariant.
- **M14 (T03 Phase 5 amendment + T20 Phase 4 amendment)** — T03 §Deliverables (lines 35-39) correctly cites Phase 5 amendment; T20 (lines 33–40) correctly cites Phase 4 amendment. Both avoid introducing a new phase. Residual M1+M2 above are about Out-of-scope and Mechanism wording that didn't track the M14 fix.
- **M15 (T22 retrofit hook for T04)** — T22 lines 82–94 correctly frames T22 as retrofitting T04's pre-shipped iter_shipped.md format; T04 line 47 has the placeholder section. Residual at line 90 (Quota proxy column) → folded into H1 above.
- **M16 (T20 difflib + tunable threshold)** — T20 line 23 correctly uses `difflib.SequenceMatcher(...).ratio() > 0.70` with `AIW_LOOP_DETECTION_THRESHOLD` env-var override.
- **M17 (analysis-index handling)** — T06 line 110 + T28 §Deliverables both correctly note `design_docs/analysis/README.md` is absent and don't require an index update.
- **All 8 LOWs** — L1 through L8 cleanly pushed to per-spec carry-over sections with self-contained Builder-actionable text.

KDR + layer rule: **No drift.** M20's specs do not introduce upward imports, do not move source-of-truth off the MCP substrate, do not import the Anthropic SDK, do not bypass the layer rule. The seven KDRs (002 / 003 / 004 / 006 / 008 / 009 / 013) plus KDR-014 are all preserved.

Surface-feasibility risk (T01 / T22 / T27 / T28): all four specs now correctly absorb the pattern that "Anthropic SDK exposes X but Claude Code Task wrapper may not surface X" — surface-check pre-steps + path-A/B fallbacks + raw-only capture defaults are all documented.

---

## Cross-cutting context

- **Round-1 fix mechanics worked.** 6 HIGHs + 17 MEDIUMs + 8 LOWs from round 1 reduced to 2 HIGHs + 6 MEDIUMs + 2 LOWs. The remaining issues are partial-fix residuals (round-1 mechanical edits left some sites uncorrected) and one new issue (T22 smoke test asserts a removed field). Convergence is on track.
- **Loop is not stuck.** Round 1 had 31 findings; round 2 has 10. Round 3 should clear or push to LOW-only. No HIGH/MEDIUM here requires user-arbitration (unlike round 1's H2 / H6); all 8 are mechanical edits. M5 (T04 path convention flat-vs-nested) is the closest to an arbitration question and is flagged as Stop-and-ask if the user wants the larger-scope Option A.
- **Project memory state.** Memory shows M20 active (autopilot validated 2026-04-27); CS300 pivot status unchanged; M16 T01 shipped. M20 is not on hold or pending external trigger.
- **Surface-feasibility theme persists.** Three round-1 HIGHs (H1, H6) and two round-1 MEDIUMs (M7) were surface-feasibility issues — Anthropic SDK exposes X, Claude Code Task wrapper may not. Round 2 has one residual (H1 — T22 smoke test asserts a field removed in M9; the field's removal was *because* of surface-feasibility uncertainty; the smoke test didn't track the M9 layering decision). Future M20 rounds will likely produce more findings here as Builders + Auditors discover what's actually accessible from inside Claude Code.
- **README is consistent with specs.** README's Goals / Exit criteria / Task pool table all use `runs/<task>/cycle_<N>/<agent>.usage.json` and the M11-corrected paths. M1 / M3 / M4 above are spec-side residuals, not README contradictions.
- **Round 1 user-arbitrated decisions held.** Both H2 (Option A — unified terminal gate) and H6 (Option A — Path B only) cleanly land in the specs; round 2 finds no contradictions with those decisions.
- **Round 2 anticipated effort to clear:** ~15 minutes of mechanical edits across 5 specs (T01, T02, T03, T05, T08, T20, T22) plus 1 user-arbitration prompt for M5 (T04 path convention).

---

**Verdict for round 2:** OPEN — 2 HIGH + 6 MEDIUM + 2 LOW. Round 3 should converge to LOW-only or CLEAN.
