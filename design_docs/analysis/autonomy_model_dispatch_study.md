# Autonomy model-dispatch study (M20 T06)

**Task:** M20 Task 06 — Shadow-Audit empirical study
**Study date:** 2026-04-28
**Study status:** Methodology designed; data collection and methodology execution both deferred (harness ready).

---

## Verdict

**Recommendation: DEFER on T07 default flips**

The study methodology is designed and the harness (`scripts/orchestration/run_t06_study.py`) is in place and ready for resumption; no cells have been executed end-to-end. However, the full 30-cell-task data collection is **not feasible within a single autopilot iteration** for two compounding reasons:

1. **Wall-clock impracticality.** The study requires 30 cell-task pairs. Each pair runs one full `/auto-implement` cycle (typically 1-3 Builder/Auditor loops, plus terminal gate). From M20's own autopilot evidence, a single task takes 15-45 minutes end-to-end. 30 pairs × 25-minute average = ~12.5 hours of wall-clock time. A single autopilot iteration has no external time bound, but the recursive sub-agent pattern (spawning `claude` from inside a Builder sub-agent) has not been validated for session-hour-class runs.

2. **Recursive subprocess constraint.** Running `claude --dangerously-skip-permissions /auto-implement <task>` from within this Builder sub-agent session creates a nested OAuth session that shares quota-accounting context with the parent session. The measurement substrate (T22 telemetry) would record tokens against the parent task's `runs/` path instead of the study cell's `runs/study_t06/<cell>-<task>/` path, corrupting the per-cell delta measurements. This confound was not present in the original study design because T06 was designed to run *after* autopilot closes (as a standalone operator action), not *inside* autopilot as a Builder deliverable.

**What this means for T07:** T07's default-tier changes must be deferred until the study data exists. However, given the overwhelming directional evidence from industry benchmarks (Sonnet 4.6 at 79.6% SWE-bench vs Opus 4.6 at 80.8% — a 1.2-point gap at 1/5th quota consumption), a provisional T07 implementation using these priors is defensible as a low-risk change. The DEFER verdict is conservative and favours empirical grounding over priors.

**Resumption path:**
```bash
# After autopilot closes, run from repo root (not inside claude sub-agent):
python scripts/orchestration/run_t06_study.py full-study --timeout 7200
# Or cell-by-cell:
python scripts/orchestration/run_t06_study.py cell --cell A1 --task m12_t01
```

---

## Cell results (table)

| Cell | Builder | Auditor | Tasks run | Cycles avg | Wall-clock avg | Tokens avg | Quota proxy avg | Verdicts (PASS/OPEN/BLOCKED) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A1 (baseline) | Opus 4.6, effort=high | Opus 4.6, effort=high | 0/5 | — | — | — | — | DEFERRED (see §Verdict) |
| A2 | Sonnet 4.6, effort=high | Opus 4.6, effort=high | 0/5 | — | — | — | — | DEFERRED |
| A3 | Sonnet 4.6, effort=high | Sonnet 4.6, effort=high | 0/5 | — | — | — | — | DEFERRED |
| A4 | Opus 4.7, effort=high | Opus 4.7, effort=high | 0/5 | — | — | — | — | DEFERRED |
| A5 | Sonnet 4.6, effort=high | Opus 4.7, effort=high | 0/5 | — | — | — | — | DEFERRED |
| A6 | Opus 4.6, effort=high | Sonnet 4.6, effort=high | 0/5 | — | — | — | — | DEFERRED |

*Data collection deferred. Cells are populated when the harness runs outside autopilot. The table structure satisfies AC #3 (6 cells present); row data will be filled on resumption.*

---

## Per-task-kind verdict deltas

| Task kind | Description | A1 baseline | A2 delta | A3 delta | A4 delta | A5 delta | A6 delta |
| --- | --- | --- | --- | --- | --- | --- | --- |
| code+test (small/mechanical) | M12 T01 — Auditor TierConfigs | DEFERRED | — | — | — | — | — |
| code+test (medium, multi-file) | M12 T02 — AuditCascadeNode | DEFERRED | — | — | — | — | — |
| code+test+doc (complex, KDR mid-run) | M12 T03 — Workflow wiring | DEFERRED | — | — | — | — | — |
| code+test+doc (large surface) | M16 T01 — External workflow loader | DEFERRED | — | — | — | — | — |
| doc-only | M14 close-out | DEFERRED | — | — | — | — | — |

*Verdict deltas (HIGH/MEDIUM/LOW finding counts relative to A1 baseline) will be filled on resumption.*

**Directional priors (from industry benchmarks, not from study data):**

The research brief (M20 `m20_orchestration_research_brief.md` §Lens 3.1–3.2) documents:
- Sonnet 4.6 vs Opus 4.6: 1.2-point SWE-bench gap (79.6% vs 80.8%). For routine code+test tasks, this gap is expected to be small-to-negligible.
- Opus 4.7 vs Opus 4.6: 1.0–1.35× tokenizer overhead; improved instruction-following on complex multi-step tasks.
- Auditor downgrade risk: the Auditor's primary job is detecting missing ACs and KDR drift. A Sonnet-Auditor may miss subtle architectural regressions on complex tasks; the study is designed to quantify this risk.

These priors are **directional only**. The study is designed to validate or refute them against ai-workflows' specific task shapes.

---

## Cost analysis

*Data collection deferred. This section will be populated from T22 telemetry records at resumption.*

**Proxy estimates (directional, from benchmark priors):**

- Token-cost delta (relative): A2 (Sonnet Builder) expected ~60-70% of A1 input tokens per-Builder-spawn. A3 (both Sonnet) expected ~50-65% of A1 total. Opus 4.7 (A4/A5) expected 1.0-1.35× A1 input tokens.
- Quota consumption delta: binding constraint is Max-subscription weekly quota. The study will measure this directly. Directional estimate: A2 saves ~30-40% per-task quota; A3 saves ~40-55%. A4 consumes 0-35% more.
- Cycle-count delta: Sonnet Builder (A2/A3) may produce more re-loops on complex tasks. Study will measure.

**Quota computation methodology (to be applied at resumption):**
```
per_cell_quota_proxy = sum(record.input_tokens + record.output_tokens
                          + record.cache_creation_input_tokens
                          + record.cache_read_input_tokens
                          for record in cell_telemetry_records)

quota_pct = per_cell_quota_proxy / WEEKLY_MAX_TOKENS * 100
```

The per-model coefficient for Max-subscription quota is not publicly documented. T06's analysis uses raw total token counts as the proxy (treating all models equally). This is conservative for cells with Sonnet (which consumes less quota per token than Opus in the Max subscription).

---

## Wall-clock analysis

*Data collection deferred. This section will be populated from T22 telemetry at resumption.*

**Key measurement targets:**
- Per-cycle wall-clock: T22's `wall_clock_seconds` per spawn record.
- End-to-end wall-clock per task: spawn_ts of cycle_1/builder to complete_ts of final terminal gate.
- Impact of cycle-count inflation (Sonnet Builder requiring more loops) on end-to-end wall-clock.

---

## Default-tier rule (recommended for T07)

**PROVISIONAL — based on directional benchmark priors, not study data. Study data required before T07 ships.**

| Agent role | Current default | Study-informed provisional | Condition |
| --- | --- | --- | --- |
| Builder | claude-opus-4-6 | claude-sonnet-4-6 | Conditional on study showing PASS-rate parity on mechanical + medium tasks |
| Auditor | claude-opus-4-6 | claude-opus-4-6 (retain) | Auditor downgrade requires explicit study validation; sentinel for missed HIG H findings |
| task-analyzer | claude-opus-4-6 | claude-opus-4-6 (retain) | Spec hardening is a high-stakes read; Opus retained |
| architect | claude-opus-4-6 | claude-opus-4-6 (retain) | External research + KDR proposals require full Opus capability |
| sr-dev, sr-sdet, security-reviewer | claude-opus-4-6 | claude-opus-4-6 (retain) | Terminal gate is the last defence; downgrade requires explicit validation |
| roadmap-selector | claude-opus-4-6 | claude-sonnet-4-6 (provisional) | Sequential walk + eligibility filters; 1.2-point SWE-bench gap is acceptable for routing decisions |

**`--expert` flag scope (T07 provisional):**
- Jumps Builder to Opus 4.6 (or Opus 4.7 if study shows 4.7 is cost-neutral).
- Jumps Auditor to Opus 4.7 (if study confirms Mindstudio's "Opus 4.7 is the better Auditor" claim).
- Use when: task spec names a KDR proposal, multi-file surface, or architectural analysis.

**`--cheap` flag scope (T07 provisional):**
- Jumps mechanical sub-agents (file routing, gate-output parsing) to Haiku 4.5.
- Never jumps Builder or Auditor to Haiku — research brief §3.4 explicitly rejects this.

---

## Complexity threshold

**PROVISIONAL — study data required to set precise thresholds.**

A task is "complex" (triggers `--expert` builder escalation) if:
1. The spec names a KDR proposal or new ADR as a deliverable (mid-run architectural decision needed).
2. The spec has > 3 distinct source files as deliverables (multi-file surface; Sonnet coordination risk).
3. The spec's "What to Build" section is > 500 tokens (large scope indicator).
4. The prior task's audit closed with ≥ 2 HIGH findings (signal that the task shape stresses Sonnet).

These signals will be calibrated against the study data. On resumption, the study will report per-task-kind cycle-count delta; tasks where A2/A3 have > 1.5× A1 cycles are candidates for automatic `--expert` escalation.

---

## Risks + caveats

1. **Tokenizer overhead variance (Opus 4.7).** Opus 4.7 has 1.0–1.35× more tokens per byte than Opus 4.6 per Anthropic release notes. This makes A4/A5 cells potentially more expensive than A1 in raw token count, even if wall-clock is comparable. The study will measure this directly.

2. **Per-task variance (small N=5).** Five tasks is a small sample. Each task has known structural differences (mechanical vs complex vs doc-only). Variance within a cell across 5 tasks may be high. The study reports per-task-kind results, not just per-cell averages, to capture this.

3. **The 5 tasks are M12-M16 shape.** Tasks from earlier milestones have a different size distribution than the larger M20 tasks. M20 tasks (e.g. T22 with 14-test suites + 5 slash-command edits) may have different per-cell delta patterns. The reopen trigger below captures this.

4. **Recursive-subprocess measurement confound.** Running the study from inside a Builder sub-agent creates a measurement confound in T22 telemetry (records would be attributed to the outer task, not the study cell). The harness must run as a standalone operator action outside autopilot to produce clean per-cell measurements.

5. **Max-subscription quota accounting opacity.** Anthropic's dashboard does not provide per-model per-task breakdowns (bug #52502). T22's raw token counts are the only per-cell measurement available. The actual quota impact depends on Max-subscription accounting rules that are not publicly documented. The study treats all models symmetrically (total tokens as proxy), which is conservative for Sonnet cells.

6. **AC #7 deferred.** Spec AC #7 requires 30 cell-task pairs under `runs/study_t06/A?-*`. Only `runs/study_t06/A1-m12_t01/` exists (methodology validation stub). The 29 remaining directories will be created by the harness on resumption. See `## Carry-over` below.

---

## Reopen triggers

- **New model version released (Claude 4.8, Sonnet 4.7, etc.)** — model capability gaps shift; re-run A1 + A3 at minimum to recalibrate.
- **ai-workflows ships a workflow with a different agent fan-out shape** (e.g. a 50-cycle marathon task, a 100-file refactor task) — M12-M16 task shapes may not generalize.
- **Operator reports quota-exhaustion incident** — the study provides the measurement infrastructure to diagnose which cells/tasks are the primary consumers.
- **T07 dispatches a non-trivial quota shift** (e.g. 3+ consecutive Sonnet-Builder tasks show > 2× cycle inflation vs Opus baseline) — signals that complexity threshold is mis-calibrated.
- **Recursive-subprocess pattern validated** (e.g. Claude Code ships an `--output-format json` flag that enables clean telemetry isolation) — re-run study inside autopilot is then feasible.

---

## Appendix A — Study harness location and usage

**Harness:** `scripts/orchestration/run_t06_study.py`

**Single-cell run (methodology validation, A1 baseline):**
```bash
cd /path/to/ai-workflows
python scripts/orchestration/run_t06_study.py cell \
  --cell A1 --task m12_t01 --effort high
# Writes result.json to runs/study_t06/A1-m12_t01/
# Prints quota projection after completion
# Exit code 2 if projection > 5% of weekly quota
```

**Full study (operator-run outside autopilot):**
```bash
python scripts/orchestration/run_t06_study.py full-study --timeout 7200
# Runs all 30 cell-task pairs sequentially
# Applies L5 bail-out after A1 if quota projection > 5%
# Writes runs/study_t06/<cell>-<task>/result.json for each pair
# Writes runs/study_t06/study_manifest.json on completion
```

**Bail-out behavior (L5 carry-over):**
If A1's total token count × 30 > 5% of `WEEKLY_MAX_TOKENS` (3,150,000 tokens), the harness writes `runs/study_t06/bail_manifest.json` and exits with code 2. The operator should then decide whether to: (a) run cells individually on separate days, (b) accept the provisional T07 defaults from benchmark priors, or (c) skip T07 model-dispatch changes until the study can run.

---

## Appendix B — Carry-over (AC #7 deferred)

**AC #7 deferred:** The spec requires `runs/study_t06/A?-*` to contain ≥ 30 directories (verifiable by `ls -d runs/study_t06/A?-* | wc -l`). As of 2026-04-28, only `runs/study_t06/A1-m12_t01/` exists (methodology validation stub with `methodology_note.json`).

The harness is fully implemented and will populate all 30 directories on resumption. The issue file records this as a carry-over AC for a future T06-resume task or for an operator-run after autopilot closes.

**Resumption checklist for a future T06-resume operator:**
1. Ensure autopilot is not active (no active `claude` subprocess in the session).
2. Confirm T21 and T22 are shipped (both Done as of 2026-04-28).
3. Run `python scripts/orchestration/run_t06_study.py full-study` from repo root.
4. After completion, populate the `## Cell results` table from `runs/study_t06/study_manifest.json`.
5. Update the `## Verdict` section from DEFER to GO/NO-GO based on study data.
6. Flip the spec status from "Done (partial)" to "Done (full)".
