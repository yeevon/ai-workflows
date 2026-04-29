# Task 06 — Shadow-Audit empirical study (6-cell matrix: Sonnet/Opus 4.6/Opus 4.7 × Builder/Auditor)

**Status:** ✅ Done (2026-04-28) — harness shipped; study report at DEFER verdict; AC #7 (30 cell-task dirs) deferred to T06-resume (see issue file carry-over).
**Kind:** Model-tier / analysis (no production code at T06; produces the study report that gates T07).
**Grounding:** [milestone README](README.md) · [research brief `research_analysis` §Lens 3.5](research_analysis.md) · memory `project_autonomy_optimization_followups.md` thread #7 · sibling [task_21](task_21_adaptive_thinking_migration.md) (must land first — Opus 4.7 cells require adaptive thinking) · sibling [task_22](task_22_per_cycle_telemetry.md) (must land first — study consumes telemetry records).

## What to Build

A **decision document** at `design_docs/analysis/autonomy_model_dispatch_study.md` that empirically evaluates a 6-cell matrix of `{Sonnet 4.6, Opus 4.6, Opus 4.7} × {Builder, Auditor}` across 5 representative tasks. The study produces per-cell deltas on:

- **Verdict-count delta.** How many HIGH / MEDIUM / LOW findings each (Builder × Auditor) pair surfaces vs the baseline cell. Catches regressions where Sonnet-Auditor would miss a finding Opus-Auditor would catch.
- **Token-cost delta.** Total input + output tokens consumed per cell. Sourced from T22's `runs/<task>/cycle_<N>/<agent>.usage.json` records (path convention per round-2 M3 — nested `cycle_<N>/` directory).
- **Wall-clock delta.** Time from task spawn to PASS verdict per cell.
- **Max-subscription weekly-quota consumption delta** (binding constraint per KDR-003). Computed by T06's own analysis script from T22's raw `input_tokens` + `output_tokens` + `cache_*` records (per-model coefficient applied at analysis time — API-price ratio and / or observed Max-quota consumption from the T06 runs themselves). **Primary metric** for the GO/NO-GO recommendation.

Recommendation framing: *"expand the autopilot's queue-drain capacity within the existing weekly quota,"* not *"5× cheaper at the API"* (the published per-token API ratio is directional, not binding for ai-workflows operators).

## Cell layout

| Cell | Builder | Auditor | Rationale |
|---|---|---|---|
| **A1** (baseline) | Opus 4.6, effort=high | Opus 4.6, effort=high | Today's de-facto setup. Reference cell. |
| A2 | Sonnet 4.6, effort=high | Opus 4.6, effort=high | Validates the research-brief prior — most cost-saving comes from cheaper Builder, while Auditor remains Opus. |
| A3 | Sonnet 4.6, effort=high | Sonnet 4.6, effort=high | Validates whether Sonnet-Auditor matches Opus-Auditor on routine tasks. The 1.2-point SWE-bench gap (research brief §3.1) hints at near-parity. |
| A4 | Opus 4.7, effort=high | Opus 4.7, effort=high | Tokenizer overhead 1.0–1.35× vs 4.6; offset by improved instruction-following. Worth measuring before defaulting. |
| A5 | Sonnet 4.6, effort=high | Opus 4.7, effort=high | Mindstudio's "Opus 4.7 is the better Auditor" claim test (research brief §3.2). |
| A6 | Opus 4.6, effort=high | Sonnet 4.6, effort=high | Reverse of A2. Tests whether Auditor downgrade alone (without Builder downgrade) breaks anything. |

## Task selection

5 representative tasks from the M12-M16 shipped set — covering the main task kinds:

1. **M12 T01** (Auditor TierConfigs — code + test, small/mechanical)
2. **M12 T02** (AuditCascadeNode primitive — code + test, medium complexity, multi-file)
3. **M12 T03** (Workflow wiring — code + test + doc, complex with KDR proposal mid-run)
4. **M16 T01** (External workflow loader — code + test + doc, large surface)
5. **M14** close-out (doc-only — captures a different task shape)

Selection rationale: covers code-only / mechanical / complex / multi-file / doc-only kinds. Each task has a known good Auditor verdict (PASS) from the original run, providing a ground-truth baseline for the verdict-count delta.

## Methodology

For each (cell, task) pair (6 × 5 = 30 runs):

1. Reset to the pre-task commit on a throwaway branch.
2. Run `/auto-implement <task>` with the cell's Builder + Auditor model assignments.
3. T22's telemetry captures every spawn's metrics.
4. Record final Auditor verdict, total cycles, total wall-clock.
5. Aggregate per-cell across the 5 tasks.

T22's record format (input/output tokens + cache-creation/read tokens + wall-clock + model + effort + verdict, per spawn) is exactly the raw measurement substrate the study consumes; T06's own analysis script computes per-cell quota / cost proxy aggregations from those raw counts (per round-2 H1 layering — T22 substrate, T06 analysis layer).

**Run order:** A1 baseline first (re-runs validate the methodology against today's known PASS results). Then A2-A6 in any order. Each cell-task pair is independent; can be parallelized across days if convenient (no cross-cell state).

**Hermetic constraint:** runs use the actual Claude Code CLI subprocess (this is the production path — no mock can capture quota consumption). Acceptable cost: 30 runs × ~3 cycles avg × ~5 agent invocations per cycle = ~450 sub-agent spawns total. Estimate: 1-2% of weekly Max quota for the study.

## Document structure

```markdown
# Autonomy model-dispatch study (M20 T06)

## Verdict
**Recommendation: <GO | NO-GO | DEFER on T07 default flips>**

## Cell results (table)
| Cell | Tasks | Cycles avg | Wall-clock avg | Tokens avg | Quota proxy avg | Verdicts (PASS/OPEN/BLOCKED) |
| --- | --- | --- | --- | --- | --- | --- |

## Per-task-kind verdict deltas
(Mechanical / multi-file / complex / doc-only — verdict-count delta vs A1 baseline)

## Cost analysis
- Token-cost delta (relative)
- Quota-consumption delta (relative)
- Cycle-count delta (does Sonnet-Builder produce more re-loops?)

## Wall-clock analysis
- Per-cycle wall-clock
- End-to-end wall-clock per task

## Default-tier rule (recommended for T07)
- Builder default: <model>
- Auditor default: <model> for routine, <model> for hostile-spec / multi-file
- task-analyzer default: <model>
- architect default: <model>
- Mechanical-role sub-agents default: <model>
- `--expert` flag scope: <which agents jump to which model>
- `--cheap` flag scope: <which agents jump to Haiku>

## Complexity threshold
(How does the study identify "complex" tasks where the default fails?)

## Risks + caveats
- Tokenizer overhead variance (Opus 4.7)
- Per-task variance (small N=5)
- The 5 tasks are M12-M16 shape; tasks with very different shape could behave differently.

## Reopen triggers
- New model version released (4.8, etc.)
- ai-workflows ships a workflow with a different agent fan-out shape
- Operator reports quota-exhaustion incident
```

## Deliverables

- **`design_docs/analysis/autonomy_model_dispatch_study.md`** — the study report.
- **`runs/study_t06/`** directory — per-cell-task run artifacts (telemetry records, issue files, recommendation files). Gitignored per `runs/` rule.
- **`scripts/orchestration/run_t06_study.py`** (or shell-script equivalent) — reproducible harness that runs the 30 cell-task pairs against the throwaway branch. Optional but useful for re-running if methodology questions surface. (Per audit M10, M20 helpers nest under `scripts/orchestration/`.)
- **No production code changes.** T06 is analysis-only.
- **Analysis-index entry** (per audit M17) — verified absent 2026-04-27 (`design_docs/analysis/README.md` does not exist); T06 lands the study report directly without an index update. A future M21 task can add the analysis-index README if `design_docs/analysis/` grows.

## Tests

T06 is analysis-only. Validation is the document itself + reproducibility via the harness script.

The study's quality is assessed by:
- Are the 5 tasks selected diverse in shape?
- Are the 6 cells covered?
- Does the recommendation cite specific evidence from the data?
- Does the document name reopen-triggers (so a future operator knows when to re-run)?

These are reviewer-judgement criteria, not automated-test criteria.

## Acceptance criteria

1. `design_docs/analysis/autonomy_model_dispatch_study.md` exists with all sections populated.
2. The Verdict line is one of GO / NO-GO / DEFER and is justified by the study's evidence.
3. Per-cell metrics table is populated with real data from `runs/study_t06/` telemetry records.
4. Per-task-kind verdict deltas table is populated.
5. Default-tier rule recommendation is concrete (specific model assignments per agent role).
6. Complexity threshold rule is concrete (specific signal that triggers `--expert`).
7. The 30 cell-task runs landed at `runs/study_t06/` (verifiable by directory listing — even if the records themselves are gitignored).
8. CHANGELOG.md updated under `[Unreleased]` with `### Added — M20 Task 06: Autonomy model-dispatch study (6-cell × 5-task matrix; recommendation gates T07; design_docs/analysis/autonomy_model_dispatch_study.md)`.
9. Status surfaces flip together.

## Smoke test (Auditor runs)

```bash
# Document exists and is non-trivial
test -f design_docs/analysis/autonomy_model_dispatch_study.md && echo "doc exists"
test $(wc -l < design_docs/analysis/autonomy_model_dispatch_study.md) -ge 200 && echo "doc has ≥ 200 lines"

# Verdict line is one of GO / NO-GO / DEFER
grep -iE "Recommendation.*(GO|NO-GO|DEFER)" design_docs/analysis/autonomy_model_dispatch_study.md \
  && echo "verdict line OK"

# Cell results table has all 6 cells
test $(grep -c "^| A[1-6]" design_docs/analysis/autonomy_model_dispatch_study.md) -ge 6 \
  && echo "6 cells in table"

# Per-cell run directories exist
test $(ls -d runs/study_t06/A?-* 2>/dev/null | wc -l) -ge 30 \
  && echo "30 cell-task runs landed"
```

## Out of scope

- **Implementing T07's dispatch logic** — that's T07's scope. T06 produces the recommendation; T07 implements it.
- **A 7th cell with Haiku** — Haiku as Builder or Auditor is rejected per research brief §3.4 (orchestrators never downgrade to Haiku; Haiku is for mechanical sub-agents only). Mechanical sub-agents (file routing, gate-output parsing) are not in the Builder/Auditor matrix.
- **Multi-tenant / SaaS-shape benchmarks** — not relevant for ai-workflows' single-user-local deployment.
- **Cost reconciliation against the Anthropic dashboard** — see T22's out-of-scope rationale.
- **Tasks of "fundamentally different shape"** — the 5 selected tasks cover M12-M16 patterns. If a future M-something task has a wholly different shape (e.g. a 50-cycle marathon, a 100-file refactor), T06's recommendations may not generalize. The study document names this as a reopen-trigger.

## Dependencies

- **T21** (adaptive-thinking migration) — **blocking**. Cells A4 + A5 require Opus 4.7 with adaptive thinking; without T21, those cells will 400-error during the study.
- **T22** (per-cycle telemetry) — **blocking**. The study's per-cell deltas come from T22's records. Without T22, no measurement infrastructure exists.

## Carry-over from prior milestones

*None.*

## Carry-over from task analysis

- **L5 (round 1, 2026-04-27):** The "1–2 % of weekly Max quota for the study" estimate is a guess without source. Reframe as: "expected to consume 1–2 % of weekly quota based on prior observation; instrument with T22 telemetry from the first cell run and **bail if cost exceeds 5 % projected to study end**." The bail-out makes the study self-limiting.

## Carry-over from prior audits

(populated by `/clean-implement` audit cycles)
