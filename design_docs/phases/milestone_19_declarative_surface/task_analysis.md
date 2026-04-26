# M19 Declarative Authoring Surface — Task Analysis

**Round:** 5 (final round of /clean-tasks loop)
**Analyzed on:** 2026-04-26
**Specs analyzed:** README.md, task_01_workflow_spec.md, task_02_compiler.md, task_03_result_shape.md, task_04_summarize_proof_point.md, task_05_writing_workflow_rewrite.md, task_06_writing_custom_step.md, task_07_extension_model_propagation.md, task_08_milestone_closeout.md
**Analyst:** task-analyzer agent

## Summary

| Severity | Count |
| --- | --- |
| 🔴 HIGH | 0 |
| 🟡 MEDIUM | 0 |
| 🟢 LOW | 1 |
| Total | 1 |

**Stop verdict:** LOW-ONLY

All four round-4 MEDIUMs (M1 T04 §Out-of-scope reframe, M2 README slot-allocation propagation, M3 T04 existing-test migration, M4 README §Exit criterion 5 wire-level test count) verified landed cleanly. L2 (README §Decisions item 7 historical record) was also addressed — line 186 now explicitly acknowledges the "originally 2 wire-level tests... expanded to 5 tests post-locked-H1" expansion, resolving the apparent contradiction with §Exit criterion 5.

L1 (the `_dispatch._run_workflow` → `_dispatch.run_workflow` sed sweep) **mostly** landed: of the ten cited sites in the round-4 report, eight were corrected to `_dispatch.run_workflow` cleanly. Two stragglers slipped past the sed pattern because they don't carry the `_dispatch.` prefix in their immediate textual context — a parenthetical list-item in T02:10 ("(`_dispatch._import_workflow_module`, `_run_workflow`)") and an inline-code-comment fragment in T04:214 ("`pass inputs to _run_workflow.`"). Both remaining sites name `_run_workflow` (with leading underscore — non-existent symbol), but each appears alongside corrected `_dispatch.run_workflow` references in the same spec, so the Builder reading the spec sees the canonical name and self-corrects without ambiguity. Push these to spec carry-over rather than block.

No new drift introduced by the round-4 fixes; all cross-references are coherent; KDR + layer-rule honored across all eight specs; `nice_to_have.md` slot §23 verified free; `RetryPolicy` + `_dispatch.run_workflow:493` + `tests/cli/test_run.py:261-264` all verified live.

Per /clean-tasks contract, the orchestrator runs Phase 3 (push the LOW to T02 + T04 spec carry-over sections) and exits the loop. M19 specs are spec-clean; loop converged at 5 rounds (HIGH 7 → 3 → 0 → 0 → 0; MEDIUM 11 → 8 → 4 → 4 → 0; total 24 → 13 → 6 → 6 → 1).

## Findings

### 🟢 LOW

#### L1 — Two `_run_workflow` (without `_dispatch.` prefix) stragglers slipped past the round-4 L1 sed

**Task:** task_02_compiler.md, task_04_summarize_proof_point.md

**Issue:** Round 4's L1 noted ten sites where the spec text named `_dispatch._run_workflow` — a non-existent symbol; the actual function is `_dispatch.run_workflow` (verified at `ai_workflows/workflows/_dispatch.py:493 — async def run_workflow(...)`). The orchestrator's round-4 sed sweep corrected eight of the ten sites cleanly. Two sites slipped past because they don't carry the `_dispatch.` prefix at the immediate match position:

- `task_02_compiler.md:10` — "`(\`_dispatch._import_workflow_module\`, \`_run_workflow\`)`" — the lone `_run_workflow` token in the parenthetical list (after a comma; the sed pattern presumably anchored on `_dispatch._run_workflow`).
- `task_04_summarize_proof_point.md:214` — "`# ... existing dispatch path unchanged: pass \`inputs\` to _run_workflow.`" — Python comment in the cli.py extension sketch; same anchoring miss.

Both spec-text-only references; not in test-callable code-blocks. Each appears alongside corrected `_dispatch.run_workflow` references in the same file (T02 has six corrected sites at lines 125, 149, 169, 174, 192; T04 has three corrected sites at lines 147, 160, 228), so the Builder reading either spec sees the canonical name elsewhere and self-corrects without ambiguity at code-write time. Not a runtime blocker — they're prose, not function calls.

**Recommendation:** Mechanical replace of the two remaining `_run_workflow` tokens to `run_workflow`. Optional polish; orchestrator can treat as carry-over rather than a 6th-round fix.

**Push to spec:** yes — append to T02 and T04 Carry-over sections as TA-LOW-10 (continuing the TA-LOW-N convention from prior rounds). Suggested carry-over text:

> **TA-LOW-10 — Two `_run_workflow` references (round 4 L1 sed remnant)** (severity: LOW, source: task_analysis.md round 5)
> Two prose references to `_run_workflow` (T02 line 10 — parenthetical list; T04 line 214 — Python comment in cli.py sketch) escaped the round-4 sed sweep. The actual function is `_dispatch.run_workflow` (no leading underscore on the function name); fix the two stragglers at implement time.

## What's structurally sound

Round-4 fixes verified intact in round 5:

- **M1 (T04 §Out-of-scope reframe) landed.** task_04_summarize_proof_point.md:286 now reads "No MCP schema changes" + the explicit clarifier "**The CLI surface IS extended in this task** (per locked H1 + Deliverable 4 — `aiw run --input KEY=VALUE` is new in M19); only the MCP schema is out-of-scope." The internal contradiction between Out-of-scope §6 and Deliverable 4 / AC-5 / AC-9 is resolved.
- **M2 (README slot-allocation propagation) landed.** README.md:115 (Exit criterion 12) reads "Slot number recorded at T07 implement time per locked Q1 (M19 takes one slot at the next-free section, currently §23)"; README.md:173 (§Dependencies on M10) reads "M19 takes one slot starting at §23 and M10's T05 re-greps at thaw to pick the next-free range after M19 lands (M19's smaller footprint means M10 has more contiguous space than originally projected)." Both sibling references aligned with §Decisions item 1.
- **M3 (T04 existing-test migration) landed.** task_04_summarize_proof_point.md:219 has the new "Existing-test migration" sub-section explaining the failure-path shift from typer-parser to dispatch-layer pydantic validation; AC-9 at line 265 reframed to distinguish success-path byte-identity (preserved) from failure-path migration (test updated as part of T04 with same exit code 2 + error message containing 'goal' + 'required'). Migration is fully specified.
- **M4 (README §Exit criterion 5 wire-level test count) landed.** README.md:108 enumerates 5 wire-level tests (`--input KVs` path, help-text rendering, planner-flag-conflict-raises, MCP via fastmcp.Client, cross-surface artefact identity). Matches T04 Deliverable 5 enumeration + AC-6.
- **L1 partially landed** (8/10 sites corrected); 2 stragglers carried to L1 above for push-to-spec.
- **L2 (README §Decisions item 7 historical record) landed.** README.md:186 acknowledges "originally 2 wire-level tests ... expanded to 5 tests post-locked-H1," resolving the apparent contradiction with §Exit criterion 5 while preserving the round-2 lock-time historical framing.

KDR-honoring + layer-rule validations re-verified:

- **KDR-002 (MCP-as-substrate)** — T04's wire-level integration test rides through `fastmcp.Client` against the in-process MCP server. T04 AC-6 explicitly verifies through both `aiw run --input` and `aiw-mcp run_workflow`.
- **KDR-003 (no Anthropic API)** — T04's `summarize-llm` tier targets Gemini Flash via `LiteLLMRoute(model="gemini/gemini-2.5-flash")`. Zero `anthropic` SDK references; zero `ANTHROPIC_API_KEY` reads anywhere in the eight specs.
- **KDR-004 (validator pairing)** — T01 `LLMStep.response_format` required; T02 §AC-3 asserts the construction invariant; T04 composes `LLMStep` + redundant `ValidateStep` to deliberately exercise both. T07's KDR-004 row update at Deliverable 2 reflects the construction-invariant graduation for spec-authored workflows.
- **KDR-006 (three-bucket retry)** — `RetryPolicy` re-exported from `ai_workflows.primitives.retry` (verified live at `primitives/retry.py:105`); T02's `LLMStep.compile()` wraps existing `retrying_edge` factory; no bespoke retry loops anywhere in the M19 spec set.
- **KDR-008 (FastMCP + pydantic schema)** — T03 schema rename adds `artifact` field with `deprecated=True` annotation on the `plan` alias; backward-compatible, no MCP wire-shape change.
- **KDR-009 (SqliteSaver-only checkpoints)** — T02 §AC-5 explicitly preserves the existing checkpointer; the synthesized `StateGraph` compiles via `builder().compile(checkpointer=...)` in `_dispatch.run_workflow:554` without modification.
- **KDR-013 (user-owned external workflow code)** — T07 §Deliverable 2 documents the boundary shift (specs are data; custom step types are code); KDR-013 row update spec'd.
- **Layer rule preserved** — `summarize.py` imports `ai_workflows.workflows` (spec types) + `pydantic` only; `summarize_tiers.py` imports `ai_workflows.primitives.tiers` (downward); T02's compiler imports `ai_workflows.graph.*` (workflows → graph downward); cli.py extension stays within the surfaces layer.

Cross-spec consistency holds for the round-5 spot-check items:

- **T04 ships 5 wire-level + 5 hermetic tests + the H1 `aiw run --input` extension.** Verified across T04 Deliverable 3 (5 hermetic), Deliverable 5 (5 wire-level), AC-4 + AC-6, README §Exit criterion 5, README §Decisions item 7.
- **planner + slice_refactor stay deferred per locked H2 + Q5.** Both keep their existing `register("planner", build_planner)` and `register("slice_refactor", build_slice_refactor)` registrations; T04 AC-8 asserts zero diff to either module; README §Decisions item 4 + item 7 record the lock.
- **`summarize.py` uses `prompt_template` (Tier 1 sugar).** T04 Deliverable 1 lines 75-79 spec the literal template; field-level details at line 101 explicitly call out the `prompt_template` path choice. Other spec references (T05, T06, README §Goal Tier-1) consistent.
- **`RetryPolicy` is re-exported from `ai_workflows.primitives.retry`** with field names `max_transient_attempts`, `max_semantic_attempts`, `transient_backoff_base_s`, `transient_backoff_max_s` — consistent across T01, T02, T04, T05.
- **`compile_step_in_isolation` ships in T06.** T06 §Deliverable 1 + AC-5 + AC-10 commit; T05 line 119 + README §Exit criterion 8 reference correctly.
- **`_dispatch.run_workflow` (no leading underscore on function name).** Eight of ten sites corrected; two stragglers in L1 above.

Prior-round fixes verified intact:

- **Round-3 H1 (CLI extension)** — T04 Deliverable 4 + 5 wire-level tests + AC-5/9/12 all coherent.
- **Round-3 H2 (mechanical bundle on summarize_tiers.py)** — T04 Deliverable 2 imports + tier shape verified live against `primitives/tiers.py`.
- **Round-3 H3 (stale-planner-port framing)** — all eight stale references replaced; only the H2-decision-history record at README:186 + T04:251 retain the "planner port" phrasing as defensible historical context.
- **TA-LOW pushdowns intact** — TA-LOW-01 (T03 + T05), TA-LOW-02 (T04), TA-LOW-04 (T06), TA-LOW-05 (T08), TA-LOW-06 (T05), TA-LOW-07 (T02), TA-LOW-08 (T08), TA-LOW-09 (T06). TA-LOW-03 was absorbed during inter-round renumbering and is not a round-5 concern.
- **`nice_to_have.md` highest section is §22** (verified live: §22 is "Hot-reload for `aiw-mcp --transport http` external workflows"); slot §23 free as the M19 spec set claims.
- **CHANGELOG vocabulary** — T03 + T04 + T07 + T08 all use Keep-a-Changelog vocabulary only (Added / Changed / Deprecated / Fixed); no rogue tags.

## Cross-cutting context

- **M19 status = spec-clean / pending-implement** at end of round 5. Per `project_m10_specs_clean_pending_implement.md` memory, the project is in a CS-300 hold pattern; M19 specs land cleanly during this lull and `/clean-implement m19 t01` will fire when CS-300 returns. Round 5's LOW-ONLY verdict means the loop is converged; the orchestrator's Phase 3 push of L1 to T02 + T04 carry-overs is the final step before milestone-locked.
- **Convergence trajectory** — HIGH 7 → 3 → 0 → 0 → 0 (settled at round 3); MEDIUM 11 → 8 → 4 → 4 → 0 (settled at round 5); total 24 → 13 → 6 → 6 → 1. The trajectory matches the round-4 prediction ("round 5 should hit CLEAN or LOW-ONLY"); 5 rounds is the budget cap.
- **No new architectural concerns surfaced** in round 5. The remaining LOW is documentation typography only — both stragglers are prose-context references that the Builder will edit at implement time as part of normal code-write hygiene; neither constitutes runtime spec rot. The eight M19 task specs are now coherent against the live codebase, the seven load-bearing KDRs, the four-layer rule, the architecture-of-record, sibling milestone READMEs (M10, M16, M14, M15, M17), and `nice_to_have.md` (§22 highest, §23 free).
- **No M19 implementation runs immediately.** M19 carries the locked-spec / pending-implement label until CS-300 returns; the loop converged at the right time.
