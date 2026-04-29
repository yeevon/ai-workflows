# M21 Autonomy Loop Continuation — Task Analysis

**Round:** 8 (overall) / Round 3 (T26)
**Analyzed on:** 2026-04-29
**Specs analyzed:** task_10 (locked), task_11 (locked), task_12 (locked), task_24 (locked), task_26 (primary target)
**Analyst:** task-analyzer agent

## Summary

| Severity | Count |
| --- | --- |
| 🔴 HIGH | 0 |
| 🟡 MEDIUM | 0 |
| 🟢 LOW | 3 |
| Total | 3 |

**Stop verdict:** LOW-ONLY

Round-7 H1 + M1 + M2 fixes all verified applied and structurally correct. No new HIGH or MEDIUM findings surface in round 8. The three LOWs are the same ones carried from round 7 (L1 / L2 / L3) — they remain pending pushdown into the spec's "Carry-over from task analysis" section via the orchestrator's LOW-ONLY exit step. Per /clean-tasks loop semantics, LOW-ONLY exits the loop; the orchestrator pushes LOW carry-over before handoff.

## Findings

### 🟢 LOW

#### L1 — Pattern section ~580 tokens (carried unchanged from round 7)

**Task:** task_26_two_prompt_long_running.md
**Issue:** T24 rubric is ≤500 tokens per section. Spec's `## Pattern (locked at T26)` section (lines 13–49) is ~434 words ≈ ~580 tokens. The spec itself isn't enforced by `md_discoverability.py`, but a Builder transposing this section verbatim into `agent_docs/long_running_pattern.md` as a single H2 would fail T24 rubric at smoke step 2.
**Recommendation:** Builder must promote each H3 (Trigger / File shape / Builder cycle-N spawn / Auditor writes progress.md / Initializer step) to a top-level H2 in `agent_docs/long_running_pattern.md`. The spec's "Sections" list at lines 56–62 already names these as the doc's H2s — Builder just has to follow it transitively.
**Push to spec:** yes — append to T26 carry-over: "When transposing the spec's '## Pattern (locked at T26)' content into `agent_docs/long_running_pattern.md`, promote each H3 (Trigger / File shape / Builder cycle-N spawn / Auditor writes progress.md / Initializer step / Reference Builder loop) to H2 so each section stays ≤500 tokens per T24 rubric."

#### L2 — AC 8(b) `old_string` uses backslash-escaped backticks (carried from round 7)

**Task:** task_26_two_prompt_long_running.md
**Location:** AC 8(b), line 146
**Issue:** AC 8(b) gives the README row 76 fix as a literal `replace X with Y`, but X and Y are written with backslash-escaped backticks (`\``). The README's actual text (line 76) has unescaped backticks. If a Builder copies AC 8(b)'s old_string verbatim into an Edit call, the Edit fails. Builder will hand-correct on first attempt but it costs a round-trip.
**Recommendation:** Soften AC 8(b) to either (a) name the README line and the desired post-edit content, leaving the exact Edit string-shape to the Builder, or (b) replace `\`` with `` ` `` (unescaped backticks) so the AC 8(b) old_string is copy-paste-able.
**Push to spec:** yes — append to T26 carry-over: "AC 8(b)'s old_string/new_string fragments are written with backslash-escaped backticks; in `Edit` tool calls use unescaped backticks (the README's actual text has unescaped backticks). Trivial Builder hand-correction."

#### L3 — Builder return-text schema reminder defensive note (carried from round 7)

**Task:** task_26_two_prompt_long_running.md
**Location:** Step 3 line 74
**Issue:** Round-7 H1 fix correctly placed the schema-purity reminder in `builder.md` §Hard rules. The bullet text is correct ("3-line return-text schema is unchanged; `progress.md` is owned by the Auditor"). Project memory `feedback_builder_schema_non_conformance.md` shows recurring schema violations under multi-cycle pressure; the reminder is necessary defensive insurance. No change required to the spec — this LOW is a forward-tracking note that the Builder must preserve the schema-purity sentence verbatim when wiring §Hard rules, not soften it.
**Recommendation:** Builder copies the exact bullet text from spec line 74 into `builder.md` §Hard rules. Do not paraphrase.
**Push to spec:** yes — append to T26 carry-over: "When wiring the `builder.md` §Hard rules edit (Step 3 second bullet), copy the exact spec text — the schema-purity sentence ('3-line return-text schema is unchanged; `progress.md` is owned by the Auditor (Phase 5b extension), not the Builder') is the explicit anchor against the recurring schema-non-conformance pattern. Do not paraphrase."

## What's structurally sound

- **Round-7 H1 fix verified applied:** Step 3 (lines 68–76) split into two surgical edits — `auto-implement.md` line ~126 (cycle-input override on existing §`### Builder spawn — read-only-latest-summary rule`) + `builder.md` §Hard rules (line 37, schema-purity bullet). Both edit targets exist live: `auto-implement.md:126` (`### Builder spawn — read-only-latest-summary rule`), `builder.md:37` (`## Hard rules`). The broken `§Builder cycle inputs` reference from round 7 is gone.
- **Round-7 M1 fix verified applied:** Deliverables list (lines 88–94) now explicitly includes the auditor.md Phase 5b edit (line 91) and the M21 README row 76 description amend (line 92). Both Step 3b and AC 8(b) are now Deliverables-backed.
- **Round-7 M2 fix verified applied:** Smoke step 4 (lines 115–119) uses semantic phrase patterns (`grep -qE`) — `T26.*long.running|plan\.md.*progress\.md` for builder.md, `progress\.md.*Phase 5b|Phase 5b.*progress\.md|append.*progress\.md` for auditor.md, `T26.*long.running.*trigger|plan\.md.*progress\.md` for auto-implement.md. Wrong-section drops are no longer pass-through.
- **T10 invariant (9 agents reference `_common/non_negotiables.md`)** — re-verified live: 9/9. Held.
- **T24 invariant (`md_discoverability.py` exists and supports all four `--check` flags)** — verified at `scripts/audit/md_discoverability.py:115-119, 135` (`summary`, `section-budget`, `code-block-len`, `section-count`).
- **`agent_docs/` does not exist on disk yet** — verified absent; T26 correctly claims this is the directory it creates.
- **Auditor Phase 5b anchor exists at `auditor.md:98`** — Step 3b's "extend Phase 5b" instruction has a real target.
- **`auto-implement.md` `## Project setup` exists at line 238** — Step 2's "immediately after `## Project setup`" insert point is concrete.
- **M21 README row 76** — confirmed live at line 76 with the exact `iter_<N>_plan.md` / `iter_<N>_progress.md` phrasing AC 8(b) targets.
- **T26 still KDR-clean** against the seven load-bearing KDRs: autonomy-infra-only (no `ai_workflows/` runtime touch), no Anthropic SDK, no MCP schema change, no checkpoint-write change, no validator pairing, no retry-loop change, no external-workflow code change. Layer rule N/A.
- **Sibling specs (T10/T11/T12/T24)** — all ✅ Done. No drift detected after re-read in round 8.
- **`_common/non_negotiables.md` Rule 1 commit-discipline** — verified at line 8; the round-7 fix's reference pattern (Step 3 line 76: "mirrors the `_common/non_negotiables.md` Rule 1 commit-discipline reminder pattern") is anchored on a real rule.

## Cross-cutting context

- **Project memory (`project_m12_autopilot_2026_04_27_checkpoint.md`):** M12 autopilot has demonstrated multi-cycle Builder spawns (T01–T08, last commit `8c664f6`). T26's pattern is meta-infra for those flows; T17/T18 (parallel-builders) are the named downstream consumers.
- **Project memory (`feedback_builder_schema_non_conformance.md`):** drives L3. Builder schema violations recur as LOW; defensive spec language is cheap insurance.
- **Sibling specs (T10/T11/T12/T24):** all ✅ Done. No drift detected.
- **CS300 pivot status (memory `project_m13_shipped_cs300_next.md`):** M21 is autonomy-infra; CS300 pivot status does not gate T26.
- **Status:** M21 is the active autonomy-infra milestone; T26 is the last Phase E pattern wiring task before T25; no cross-milestone block.
- **Round trajectory:** Round 6 had 1 HIGH + 3 MEDIUM (4 actionable). Round 7 had 1 HIGH + 2 MEDIUM (3 actionable). Round 8 has 0 HIGH + 0 MEDIUM (0 actionable, 3 carry-over LOWs). Convergence pattern: each round closed all prior actionable findings without introducing new ones. Spec is ready to exit /clean-tasks; LOW carry-over goes into the spec's "Carry-over from task analysis" section before /clean-implement consumes it.
- **Loop limit:** This is round 5 of 5 per /clean-tasks per-task limit. LOW-ONLY verdict exits the loop cleanly without hitting the halt condition.
