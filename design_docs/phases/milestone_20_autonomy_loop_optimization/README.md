# Milestone 20 — Autonomy Loop Optimization

**Status:** ✅ Complete (2026-04-28). Branch: `workflow_optimization` (user-named; milestone doc uses `autonomy_loop_optimization` to avoid overloading the existing `ai_workflows/workflows/` package term). Grounding: research brief `design_docs/analysis/m20_orchestration_research_brief.md` (Q1–Q2 2026 best-practices synthesis post-Opus-4.6) · project memory `project_autonomy_optimization_followups.md` · `architecture.md` §9 KDRs · autonomy validation (M12 T01 a7f3e8f, T02 fc8ef19, T03 1677889 — autopilot end-to-end validation 2026-04-27).

**Scope note.** Every milestone before M20 changed the runtime (`ai_workflows/` package). M20 changes the autonomy infrastructure — agent prompts (`.claude/agents/`), slash commands (`.claude/commands/`), and the project context doc (`CLAUDE.md`). Runtime code is read-only at this milestone except where a finding requires a runtime hook (e.g. a structured log line the orchestrator parses, or per-agent telemetry capture). KDR drift checks still apply — M20 must not violate the seven load-bearing KDRs while reshaping the loop that enforces them.

---

## Why this milestone exists

Autopilot validated end-to-end on 2026-04-27 (M12 T01-T03 + T08 shipped autonomously over 4 iterations). The infrastructure works. Three structural shifts since the autopilot validation now define the optimization space:

1. **Adaptive thinking is the new dial.** `thinking: {type: "enabled", budget_tokens: N}` is deprecated on Opus 4.6 / Sonnet 4.6 and rejected with HTTP 400 on Opus 4.7. The replacement is `thinking: {type: "adaptive"}` paired with `effort: low | medium | high | max` (plus `xhigh` exclusive to Opus 4.7). Every agent currently using `thinking: max` will break on the next model migration.
2. **Server-side compaction is now first-class.** `compact_20260112` and `clear_tool_uses_20250919` strategies plus the Memory tool are shipped primitives. M20's compaction quartet (T01-T04) is structurally correct but composes with these primitives rather than replacing them.
3. **The Sonnet–Opus gap collapsed for everyday agentic coding.** Sonnet 4.6 scores 79.6% on SWE-bench Verified vs Opus 4.6's 80.8% (1.2-point gap) at one-fifth the price. Opus's strongholds shifted upmarket — GPQA Diamond (91.3% vs Sonnet 74.1%), 1M-token MRCR v2 (76% vs Sonnet 18.5% — true qualitative shift), BrowseComp, ARC-AGI-2. The cost case for "default-Sonnet, escalate to Opus on demand" is now overwhelming for the bulk of Builder/Auditor work. **Cost framing for ai-workflows specifically:** runs go through the Claude Code OAuth subprocess (KDR-003), so the binding constraint is **Max-subscription weekly quota consumption**, not per-token API spend. The published 1/5× price ratio is directional; quota-consumption delta per cell is the actual measurement T06 must produce, and T07's framing is "expand the autopilot's queue-drain capacity within the existing weekly quota," not "5× cheaper at the API."

Beyond these shifts, the per-task token cost has four leaks compounding multiplicatively (sub-agent input, sub-agent output, in-task cycle, cross-task iteration), most agents currently default to `claude-opus-4-7` with `thinking: max` regardless of role complexity, and CLAUDE.md is loaded into every conversation including sections that only specific agents read. The model-tier rationalization is the single highest-leverage intervention; the compaction quartet plugs the four leaks; deduplication and progressive disclosure shrink the per-spawn floor.

---

## Optimization themes (load-bearing, define the milestone shape)

1. **Token-usage minimization** — minimize context window when appropriate, compact and clear when appropriate. The four-leak framing (input prune / output schema / in-task cycle / cross-task iteration) plugs the four accumulation surfaces; partial adoption leaves a leak open.
2. **On-demand context loading** — reduce files agents reference to only what's needed; let them pull more context only when absolutely necessary. Pre-feed *certainty*, not speculation. Asymmetry favours under-pre-feeding post-Opus-4.6.
3. **MD-file searchability** — restructure docs so agents pull the section they need (one topic per file, ≤500-token sections with `##` anchors, top-of-file 3-line summary, no inlined code).
4. **Selective parallelization** — fan out where work is genuinely independent (terminal gate, parallel builders on file-disjoint slices). Anthropic's own data: most coding tasks have fewer parallelizable slices than research; over-parallelization burns tokens for negative gain. Cap at 3–4 worktrees on shared infrastructure.
5. **Pre-feed sub-agents the context they should need** — bundle the spec + the cited KDR sections + the current diff up front; let the agent pull the rest on demand from the searchable MD index. Reduces in-spawn discovery time.
6. **Model-tier rationalization** — leverage Haiku 4.5 for mechanical work, default Sonnet 4.6 for orchestration and most reasoning, reserve Opus 4.6/4.7 for the small set of jobs that genuinely need it. Migrate from `thinking: max` to adaptive thinking + `effort` parameter. Never switch model mid-context — escalate by spawning a fresh sub-agent.

---

## Goals

1. **Compaction quartet.** Close the four token leaks (sub-agent input, sub-agent output, in-task cycle, cross-task iteration). Combined target: ≥ 50% reduction in orchestrator token-use across a multi-task autopilot run, validated on a re-run of the M12 task slice.
2. **Parallel terminal gate.** sr-dev + sr-sdet + security-reviewer spawn in a single message; each writes to a per-reviewer fragment file (`runs/<task>/cycle_<N>/<agent>-review.md`); orchestrator stitches into the issue file. Wall-clock at the terminal gate drops from sum-of-three to max-of-three (target ≥ 2× improvement).
3. **Empirically-grounded model dispatch.** Shadow-Audit study lands first on a 6-cell matrix (Sonnet/Opus-4.6/Opus-4.7 × Builder/Auditor across 5 tasks). Study produces verdict-count delta, token-cost delta, wall-clock delta, **and Max-subscription weekly-quota consumption delta** per cell — quota is the binding constraint per KDR-003, not per-token price. Default-Sonnet + `--expert` Opus override + `--cheap` Haiku for mechanical roles is conditional on the study showing strict-loop-compliance holds. No defaults flip without the data.
4. **Adaptive-thinking migration.** Eliminate every `thinking: max` and `budget_tokens` reference in the agent prompts and slash-commands; migrate to `thinking: {type: "adaptive"}` + per-role `effort` settings. Required for forward compatibility with Opus 4.7 and any future model that rejects manual budgets.
5. **Defense-in-depth integrity.** Gate-output integrity check (parse raw stdout, fail-closed on missing output, paired with T01's orchestrator-side schema parsing as the first-defence layer) plus task-integrity check (orchestrator independently verifies non-empty diff, non-empty test diff for feature work, and at least one named gate before stamping AUTO-CLEAN).
6. **Cache-breakpoint discipline.** Pin orchestrator and sub-agent cache breakpoints on the *last stable block* (loaded non_negotiables + agent system prompt + tool definitions), explicitly *before* the dynamic per-cycle context. Verify with empirical cache-hit telemetry. Critical: the literature documents 5–20× session cost blowups from misplaced breakpoints.
7. **Per-cycle telemetry.** Wrap each sub-agent invocation to capture `cache_read_input_tokens`, `cache_creation_input_tokens`, `input_tokens`, `output_tokens`, model, effort. Persist to `runs/<task>/cycle_<N>/<agent>.usage.json`. This is the basis for evidence-based decisions on T07 defaults and for catching the metering-opacity failure mode (anthropics/claude-code #52502).

**Goals 8-11 (agent-prompt deduplication, MD-file discoverability, productivity commands, parallel-builders foundation) moved to [M21](../milestone_21_autonomy_loop_continuation/README.md) per audit recommendation M3.**

---

## Exit criteria

(Goal-numbered. Empirical thresholds replace the previous "pending user content" placeholders.)

1. ✅ **(G1)** Sub-agent return-value schema enforced across all 9 agents via **prompt-mandate + orchestrator-side parsing**. Hard 3-line schema (verdict / file / section); orchestrator stops carrying chat-summary bodies into stop-condition evaluation. Note: the research brief named SDK-native `outputFormat: json_schema` as the mechanism, but Claude Code's `Task` tool surface (ai-workflows' spawn primitive) does not expose schema-enforcement parameters; orchestrator-side parsing is the practical enforcement layer. If Claude Code later exposes `outputFormat` on Task, the parser becomes redundant — future change, not an M20 dep. Test: spawn each agent on a fixture task; assert returned text length ≤ 100 tokens and parses cleanly to (verdict, file, section). **[T01 Done — 2026-04-28]**
2. ✅ **(G1)** Sub-agent input prune — orchestrator passes scoped context only (task spec + KDR-relevant architecture sections + current diff). Whole-milestone-README and unrelated-sibling-issue pre-loads removed. Output budget cap enforced (1–2 K for read-only sub-agents, 4 K for code-writing). Test: re-run M12 T01 audit; orchestrator's input-token-count to auditor drops by ≥ 30% from baseline. **[T02 Done — 2026-04-28]**
3. ✅ **(G1)** In-task `cycle_summary.md` per cycle. Auditor emits structured summary (state-as-of-now / what changed this cycle / open issues / decisions made with rationale / files touched). Orchestrator reads ONLY the latest summary, not the full Builder+Audit chat text. Test: 3-cycle task; cycle 3's orchestrator-context size at Builder spawn matches cycle 1's (constant, not linear). **[T03 Done — 2026-04-28]**
4. ✅ **(G1)** Cross-task `iter_<N>_shipped.md` at autopilot iteration boundaries. Orchestrator treats prior iteration's chat history as compacted-to-summary. Test: 5-iteration autopilot run; iteration 5's orchestrator-context size matches iteration 1's. **[T04 Done — 2026-04-28]**
5. ✅ **(G2)** `/auto-implement` terminal gate spawns sr-dev + sr-sdet + security-reviewer in a single multi-Task message. Each writes to `runs/<task>/cycle_<N>/<agent>-review.md`. Orchestrator stitches three fragments into the issue file in one Edit pass. Test: terminal-gate wall-clock measured end-to-end; ≥ 2× improvement over baseline serial. **[T05 Done — 2026-04-28]**
6. ✅ **(G3)** Shadow-Audit study report written to `design_docs/analysis/autonomy_model_dispatch_study.md`. Harness at `scripts/orchestration/run_t06_study.py`. Verdict: DEFER (recursive-subprocess confound + multi-day wall-clock makes full 30-cell study infeasible inside single autopilot iteration). Provisional default-tier rule + complexity-threshold + `--expert`/`--cheap` scope documented from benchmark priors. AC #7 (30 cell-task dirs) deferred to T06-resume. **[T06 Done — 2026-04-28]**
7. **(G3)** Conditional on study GO: `get_model_for_agent_role(role, complexity, flag)` helper in the loop controller. Defaults: Builder=Sonnet 4.6, Auditor=Sonnet 4.6 (routine) / Opus 4.6 (`--expert`), task-analyzer=Opus 4.6, architect=Opus 4.6, file-router-style sub-agents=Haiku 4.5. Default-tier change lands on a separate isolated commit per autonomy decision 2.
8. ✅ **(G4)** Zero `budget_tokens` references and zero `thinking: max` literal directives anywhere in `.claude/agents/*.md` and `.claude/commands/*.md`. All replaced by `thinking: {type: "adaptive"}` plus per-role `effort` setting. Test: `grep -rE "budget_tokens|thinking:[[:space:]]*max" .claude/` returns zero hits. **[T21 Done — 2026-04-28]**
9. ✅ **(G5)** Loop controller parses raw stdout of gate commands (or `tail -3` of a captured log file) before stamping AUTO-CLEAN. Missing structured output = treat as failed gate. T01's orchestrator-side schema parser is the first line of defence (catches malformed agent verdict-lines); raw-stdout parsing with fail-closed is the second (catches Builder claims of "gates pass" without actual gate output). Test: synthetic Builder report claiming "all gates pass" with empty actual stdout — orchestrator catches and halts. **[T08 Done — 2026-04-28]**
10. ✅ **(G5)** Pre-commit ceremony: `git diff --stat <prev-commit>..HEAD` confirms non-trivial diff. For feature work, separate non-empty *test* diff assertion (a Builder can satisfy a non-empty-diff check by editing a comment). Empty diff after AUTO-CLEAN = halt. Orchestrator independently re-runs at least one named gate (e.g. `pytest -q` tail) before stamping. **[T09 Done — 2026-04-28]**
11. ✅ **(G6)** Cache breakpoints pinned on the last stable block in every orchestrator and sub-agent invocation. Stable-prefix discipline documented in `spawn_prompt_template.md` §Stable-prefix discipline; 2-call verification harness at `scripts/orchestration/cache_verify.py`; operator runbook at `runs/cache_verification/methodology.md`. Empirical validation (assert cache_read > 80% on call 2) deferred to operator-resume per T06 L5 precedent. **[T23 Done — 2026-04-28]**
12. ✅ **(G7)** Per-sub-agent telemetry wrapper captures cache + input + output token counts plus model + effort, persists to `runs/<task>/cycle_<N>/<agent>.usage.json`, aggregates into `iter_<N>_shipped.md`. The basis for T07 defaults and for surfacing accounting opacity early. **[T22 Done — 2026-04-28]**

**Exit criteria for slimming (former G6/G7), productivity commands (former G10), parallel-builders foundation (former G11) are now [M21](../milestone_21_autonomy_loop_continuation/README.md) exit criteria.**

---

## Non-goals

- **No runtime code changes** beyond the minimum hooks the orchestrator needs (structured log lines for gate-output integrity, telemetry capture wrapper). The seven KDRs and four-layer rule still police runtime; M20 does not touch `ai_workflows/`.
- **No new KDRs locked at M20.** If an M20 finding implies a new architectural rule, propose via the architect agent and land the KDR on its own commit (per autonomy decision 2). M20's scope is the loop, not the architecture.
- **No `nice_to_have.md` adoption at M20.** Threads not in the research brief or this milestone's task pool are out of scope.
- **No CI / test infrastructure overhaul.** The pytest gate, lint-imports contracts, ruff config are untouched. M20 changes only the autonomy orchestration that runs those gates.
- **No removal of the Auditor's full-scope read.** The Auditor's "load the full task scope, not the diff" invariant is load-bearing; T02 prunes the orchestrator's pre-loads, not the Auditor's own reads. The Auditor still pulls architecture.md + sibling issues on-demand inside its own run.
- **No batching of Builder→Auditor cycles.** The Auditor still runs after every Builder cycle. Compaction (T03) reduces the carried context across cycles, not the cycle frequency.
- **No multi-orchestrator parallelism.** Two concurrent `/auto-implement` runs against the same `design_branch` are out of scope (git contention is its own architectural problem). Parallel Builders within a single orchestrator run (T17) is in scope as a stretch goal.
- **No Agent Teams adoption.** Anthropic's `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` is a peer-to-peer pattern (file locking, shared task list, agent-to-agent messaging). Builder→Auditor has no peer-to-peer requirement; sub-agents remain the right primitive. Note for a future milestone if adversarial-debate auditing ever lands.
- **No mid-context model switching.** Cache invalidation makes this a footgun; escalate by spawning a fresh sub-agent in the heavier model.
- **No `--continue` / `--resume` reliance for orchestrator state.** The Claude Code resume cache-invalidation bugs (#27048, #34629, #42338, #43657) make this fragile. T03 / T04 file-based memory is the continuity mechanism.

---

## Key decisions in effect

| Decision | Reference |
|---|---|
| Autonomy boundaries — `design_branch` only, no main, no publish, KDR-isolated commits, sub-agent disagreement = halt | memory `feedback_autonomous_mode_boundaries.md` · CLAUDE.md §Non-negotiables |
| Autopilot validated baseline (4 iterations, 2 tasks shipped, 1 milestone hardened, 0 KDR additions) | memory `project_autonomy_optimization_followups.md` (state 2026-04-27) |
| Compaction quartet must land together — partial adoption leaves a leak open | memory §"Compaction scope summary" |
| Empirical Shadow-Audit before defaulting model dispatch — no default flips without data | memory thread #7 |
| Adaptive thinking + `effort` is the new contract | research brief §Lens 3.3; Anthropic API docs `whats-new-claude-4-7` |
| Orchestrators never downgrade to Haiku — empirical evidence does not support it for non-trivial workflows | research brief §Lens 3.4 (Caylent, ClaudeFa.st, SolidNumber convergence) |
| Never switch model mid-context — cache invalidation footgun | research brief §Lens 2.2 |
| KDR-013 boundary holds — agent edits do not police user-owned external workflow code | architecture.md KDR-013 |
| **KDR-014 affirmation** — slash-command flags `--expert` / `--cheap` (T07) and env-var overrides (`AIW_*`) are operator-surface knobs, NOT user-facing quality knobs. Conform to KDR-014's framework-vs-operator boundary by analogy with `AIW_AUDIT_CASCADE` (M12 / ADR-0009). End-user `*Input` schemas, `WorkflowSpec` fields, MCP tool schemas remain free of quality knobs. | architecture.md KDR-014 · ADR-0009 |

---

## Task pool (revised — supersedes the prior 20 candidates)

The pool is reorganized into seven phases keyed to the optimization themes. Each row maps to a research-brief finding (`SUPPORT` / `MODIFY` / new candidate `T21+`) and a memo thread (`#1-15` from the prior project memory). Order within a phase is roughly the suggested implementation order, not a hard sequence.

### Phase A — Compaction quartet + server-side primitive evaluation (token-leak closure, sequential within phase)

| # | Task | Research-brief verdict | Phase / Kind | Status |
|---|---|---|---|---|
| 01 | Sub-agent return-value schema (3-line verdict / file / section), enforced via prompt-mandate + orchestrator-side parsing (Claude Code Task tool does not expose SDK `outputFormat`) | SUPPORT + MODIFY (T01 from #12) | Compaction / doc + code | ✅ Done |
| 02 | Sub-agent input prune (orchestrator-side scope discipline, plus per-spawn output token budget) | SUPPORT + EXTEND (T02 from #8) | Compaction / doc + code | ✅ Done |
| 03 | In-task cycle compaction (`cycle_summary.md` per Auditor, structured template) | SUPPORT (T03 from #9) | Compaction / doc + code | ✅ Done |
| 04 | Cross-task iteration compaction (`iter_<N>_shipped.md` at autopilot iteration boundaries) | SUPPORT (T04 from #13) | Compaction / doc + code | ✅ Done |
| 28 | **NEW** — Evaluate server-side `compact_20260112` strategy for orchestrator runs through Agent SDK (research brief §Lens 2.1). GO / NO-GO / use-alongside-T03-T04 decision; if GO, integrates with `pause_after_compaction` so orchestrator can re-stitch state from cycle_summary / iter_shipped files post-compaction. Does NOT replace T03/T04 (file-based memory remains the auditable durable record); composes on top. | NEW (audit M1, research-brief §Lens 2.1) | Compaction / analysis + code | ✅ Done (DEFER — 2026-04-28) |

### Phase B — Parallel terminal gate (perf, can run alongside Phase A)

| # | Task | Research-brief verdict | Phase / Kind | Status |
|---|---|---|---|---|
| 05 | Parallel terminal gate (sr-dev + sr-sdet + security-reviewer in one Task message; fragment files; orchestrator stitches in next turn) | STRONGLY SUPPORT + EXTEND (T05 from #14) | Performance / doc + code | ✅ Done |

### Phase C — Model-tier rationalization (foundational; Phase D safeguards lean on it)

| # | Task | Research-brief verdict | Phase / Kind | Status |
|---|---|---|---|---|
| 21 | **NEW** — Adaptive-thinking migration (eliminate every `thinking: <literal>` shorthand and `budget_tokens` directive — confirmed 7 hits across `.claude/commands/` 2026-04-27 grep: 6 × `thinking: max` + 1 × `thinking: high` in `implement.md`; migrate to `thinking: {type: "adaptive"}` + per-role `effort`; required for Opus 4.7 forward compatibility AND for T06's Opus 4.7 cells to not 400-error during the study) | NEW (research-brief T21) | Model-tier / doc + code | ✅ Done |
| 22 | **NEW** — Per-cycle token telemetry per agent (wrapper captures **raw counts only**: cache + input + output tokens, model, effort, wall-clock, verdict; persists to `runs/<task>/cycle_<N>/<agent>.usage.json`). Per-cell quota / cost proxies are computed by T06's analysis script from these raw counts (T22 is the measurement substrate; T06 owns the proxy / aggregation layer per round-2 H1 fix). **Lands second in Phase C** — T06 study cannot produce evidence without T22's records. | NEW (research-brief T22) | Model-tier / code | ✅ Done |
| 06 | Shadow-Audit empirical study (6-cell matrix: Sonnet/Opus 4.6/Opus 4.7 × Builder/Auditor on 5 tasks; consumes T22's telemetry; produces verdict-count + token + wall-clock + quota-consumption deltas per cell) | STRONGLY SUPPORT + MODIFY (T06 from #7) | Model-tier / analysis | ✅ Done (DEFER verdict; harness shipped; AC #7 deferred to T06-resume) |
| 07 | Dynamic model dispatch (`get_model_for_agent_role` helper; default-Sonnet + `--expert` Opus + `--cheap` Haiku for mechanical roles; never switch mid-context) | STRONGLY SUPPORT + EXTEND (T07 from #6) | Model-tier / code | 📝 Planned (gated on T06) |

### Phase D — Defense-in-depth integrity (load-bearing if Phase C lands; less so otherwise)

| # | Task | Research-brief verdict | Phase / Kind | Status |
|---|---|---|---|---|
| 08 | Gate-output integrity (parse raw stdout, fail-closed on missing output, paired with T01's orchestrator-side schema parser as first-defence layer) | SUPPORT + EXTEND (T08 from #10) | Safeguards / code | ✅ Done |
| 09 | Task-integrity safeguards (non-empty-diff check + non-empty test-diff for feature work + independent gate re-run) | SUPPORT + EXTEND (T09 from #11) | Safeguards / code | ✅ Done |
| 20 | Carry-over checkbox-cargo-cult catch — extended to inspect (a) checkboxes marked done without diff/test, (b) two consecutive cycles producing near-identical output, (c) Auditor rubber-stamping pattern | SUPPORT + EXTEND (T20 from #5) | Safeguards / doc | ✅ Done |
| 23 | **NEW** — Cache-breakpoint discipline (pin breakpoints on last stable block; verify empirically with 2-call cache-hit telemetry; addresses the 5–20× session-cost blowup failure mode) | NEW (research-brief T23) | Safeguards / code | ✅ Done |
| 27 | **NEW** — Tool-result clearing for long Auditor runs (`clear_tool_uses_20250919` strategy with `keep` window of 3–5 most recent tool results) | NEW (research-brief T27) | Safeguards / code | ✅ Done |
| ZZ | M20 milestone close-out (Phases A-D done; baseline measurements published; M21 unblocked) | n/a | Closeout / doc | ✅ Done |

### Phases E (Slimming), F (Productivity commands), G (Parallel-builders) — moved to M21

Per audit recommendation M3 (2026-04-27), M20's original 27-task scope was too large for a single milestone. **Phases E, F, and G now live in [M21 — Autonomy Loop Continuation](../milestone_21_autonomy_loop_continuation/README.md).** M21 prerequisites M20 close-out (the slimming wins are measured against M20's post-shipment baseline). Tasks T10, T11, T12, T13, T14, T15, T16, T17, T18, T19, T24, T25, T26 all live in M21's scope.

---

## Suggested phasing

| Phase | Tasks | Rationale |
|---|---|---|
| **A — Compaction (token reduction)** | T01 → T02 → T03 → T04 → T28 | Foundation. T01 (output schema) gates everything else — without it, downstream pruning leaks the same way. T02–T04 plug one accumulation surface each. Sequential within the phase. T28 (server-side `compact_20260112` evaluation) lands last — informs whether to compose the Anthropic primitive with file-based memory or keep file-based as the only continuity mechanism; doesn't replace T03/T04 either way (file-based memory remains the auditable record). **T28 verdict: DEFER (2026-04-28) — surface mismatch; Claude Code `Task` tool does not expose `context_management.edits`. See `design_docs/analysis/server_side_compaction_evaluation.md` + `nice_to_have.md §24`.** |
| **B — Parallel terminal gate (perf)** | T05 | Independent of Phase A. Could run in parallel iteration with Phase A. |
| **C — Model-tier rationalization** | T21 → T22 → T06 → T07 (gated on T06) | T21 (adaptive-thinking migration) lands first — confirmed 7 hits of `thinking:` shorthand across `.claude/commands/` 2026-04-27 (6 × max + 1 × high in implement.md) will 400-error on Opus 4.7 mid-study otherwise. T22 (telemetry) lands second — T06 cannot produce evidence without measurement infrastructure. T06 study third. T07 conditional on T06 GO verdict. |
| **D — Safeguards** | T08 → T09 → T20 → T23 → T27 | Defense-in-depth. T23 (cache-breakpoint discipline) is the highest-impact-per-effort item in this phase. **Lands BEFORE Phase C completes** in priority — Sonnet-default makes safeguards more load-bearing. Re-order if Phase C is deferred. |

Phases **E, F, G** moved to **[M21](../milestone_21_autonomy_loop_continuation/README.md)** per audit recommendation M3 (split). M20 close-out (post-Phase-D baseline measurements) is M21's prerequisite.

---

## Cross-phase dependencies

- **T01** (return-value schema) → blocks **T05** (parallel gate; fragment-file format reuses the schema) and **T08** (gate-output integrity uses T01's orchestrator-side schema parser as first defence layer).
- **T03** (in-task cycle compaction) → benefits from T01 but does not strictly block.
- **T07** (default-Sonnet) → makes T08 + T09 + T22 + T23 effectively required. Sonnet is more likely to confidently misreport than Opus; safeguards become load-bearing.
- **T21** (adaptive thinking) → blocks **T06** AND **T07**. Blocks T06 because the study's Opus 4.7 cells will 400-error without adaptive-thinking migration. Blocks T07 because shipping dispatch with deprecated `thinking: max` directives breaks on the next model migration.
- **T22** (telemetry) → blocks **T06**. The study cannot produce per-cell deltas (verdict-count, token, wall-clock, quota-consumption) without measurement infrastructure. T22 is also strongly precedent to T07 — `--cheap` Haiku flag scope and `--expert` Opus threshold should be calibrated against telemetry data, not picked from priors.

**Cross-milestone:** M20 close-out → blocks M21 (slimming wins are measured against M20's post-shipment baseline; before M20 closes, M21 numbers are noisy).

---

## Dependencies on prior milestones

- **M12 must be fully closed.** M20 baselines its before/after measurements against the M12 task slice. M12 close-out (M12 T07) lands before M20 T01 can establish a clean baseline.
- **No runtime dependency on prior milestones.** M20 reshapes orchestration; runtime invariants are unchanged. KDR drift checks still apply.

---

## Outcome (2026-04-28)

M20 shipped 11 of 13 candidate tasks (T01–T06, T08, T09, T20, T21, T22, T23, T27, T28 = 11 shipped + T06/T23/T28 carrying DEFER verdicts). T07 remains open, blocked on T06 GO/NO-GO.

### T01–T05 — Compaction quartet + parallel terminal gate (Phase A + B)

**T01** enforces the hard 3-line return-value schema (verdict / file / section) across all 9 sub-agents via prompt-mandate + orchestrator-side parsing. **T02** establishes orchestrator-side scope discipline (spawns receive scoped context only; output budget enforced). **T03** introduces per-cycle `cycle_<N>/summary.md` compaction, making orchestrator context O(1) instead of linear-in-cycle. **T04** introduces cross-task `iter_<N>-shipped.md` compaction at autopilot iteration boundaries, keeping the outer-loop context O(1). **T05** parallelises the terminal gate: sr-dev + sr-sdet + security-reviewer spawn in a single multi-Task message; each writes to a fragment file; orchestrator stitches in one Edit pass. Together these close the four token-accumulation surfaces (sub-agent input, output, in-task cycle, cross-task iteration) and form the structural foundation for the autonomy loop's compaction substrate. Telemetry records under `runs/<task>/cycle_<N>/<agent>.usage.json`.

### T06 — Shadow-Audit empirical study (DEFER verdict)

Methodology designed; data collection deferred to operator-resume. Harness `scripts/orchestration/run_t06_study.py` (791 lines) reproducibly drives the 6-cell × 5-task matrix; bail-out check fires after the first A1 task pair (spec L5 wording). Hermetic harness tests (7) cover projection arithmetic, bail-manifest aggregate shape, dry-run end-to-end, single-cell CLI bail contract. Per-cell measurements deferred to `runs/study_t06/<cell>-<task>/` populated by operator outside autopilot. DEFER verdict rationale: recursive-subprocess confound + multi-day wall-clock make full 30-cell data collection infeasible inside a single autopilot iteration.

### T07 — Dynamic model dispatch (📝 Planned, gated on T06's GO verdict, operator-resume)

Does not ship at M20. T07's spec exists but is gated on T06 producing a non-DEFER verdict (study data populated, GO/NO-GO calibrated). Until the operator runs the harness outside autopilot, T07 stays open; it carries to M21 only when the operator confirms the study verdict and unblocks the dispatch defaults.

### T08–T09 — Gate-output integrity + task-integrity safeguards (Phase D)

**T08**'s `_common/gate_parse_patterns.md` is the single source of truth for gate-footer regex (pytest, ruff, lint-imports); the orchestrator independently captures and parses raw gate stdout before stamping AUTO-CLEAN. **T09**'s `_common/integrity_checks.md` is the canonical reference for the three pre-stamp checks (non-empty diff, non-empty test-diff for code tasks, independent gate re-run). Both form the defense-in-depth pre-AUTO-CLEAN ceremony.

### T20 — Auditor anti-cargo-cult inspections

M12-T01 carry-over-patch ported from template; Phase 4 extended with cycle-N-vs-(N-1) overlap detection + rubber-stamp detection. `scripts/orchestration/cargo_cult_detector.py` ships 50/51 boundary tests.

### T21–T22 — Adaptive-thinking migration + per-cycle telemetry

**T21** eliminated every `thinking: max` literal and `budget_tokens` directive; all 9 agent frontmatters + 7 slash commands now carry `thinking: {type: "adaptive"}` + explicit `effort:` per role. **T22** records `cache_read_input_tokens` / `cache_creation_input_tokens` / `input_tokens` / `output_tokens` / `model` / `effort` per agent invocation under `runs/<task>/cycle_<N>/<agent>.usage.json`.

### T23 — Cache-breakpoint discipline (AC-7 deferred)

Stable-prefix-discipline section added to `_common/spawn_prompt_template.md`; 2-call verification harness `scripts/orchestration/cache_verify.py` with hermetic tests; methodology stub at `runs/cache_verification/methodology.md` for operator-resume. AC-7 empirical validation deferred per parallel L5-equivalent bail-out (recursive-subprocess confound + TTL fragility).

### T27 — Auditor input-volume rotation trigger

Client-side simulation of `clear_tool_uses_20250919`. **Path A explicitly rejected per audit H6** — Claude Code Task tool agent frontmatter does not surface `context_management.edits` (verified across all 9 existing agents — frontmatter accepts only `name`/`description`/`tools`/`model`). Threshold tunable via `AIW_AUDITOR_ROTATION_THRESHOLD` (60K default).

### T28 — Server-side compaction evaluation (DEFER verdict)

Surface mismatch — Claude Code Task tool does not expose `context_management.edits`; analysis at `design_docs/analysis/server_side_compaction_evaluation.md`; recorded under `nice_to_have.md §24` for re-open if Anthropic / Claude Code surface evolves.

### Manual-verification autopilot baseline

The 6-task autopilot run on 2026-04-28 (timestamp `20260428T153748Z`, branch `workflow_optimization`, `AIW_AUTONOMY_SANDBOX=1`) shipped T06 (d76f93f), T08 (0dd91f4), T09 (8e572dc), T20 (851274f), T23 (b39efbf), T27 (a266996) across 6 autopilot iterations (iter1–iter6 artifacts at `runs/autopilot-20260428T153748Z-iter1-shipped.md` through `iter6-shipped.md`). T01–T05, T21, T22, T28 shipped in earlier iterations or pre-autopilot: T04 (7caecbd), T05 (bd27945), T21 (628b975), T22 (426c7fb), T28 (21c37ba). Total cycles across 6 tasks: T06=5, T08=2, T09=1, T20=3, T23=2, T27=2 (15 total). Total agent invocations: ~70+. Cumulative tokens: ~3.5M.

### Green-gate snapshot (close-out)

`uv run pytest` — 1293 passed, 1 pre-existing environmental fail (`test_design_docs_absence_on_main` on `workflow_optimization` branch; LOW-3, out of ZZ scope). `uv run lint-imports` — 5 contracts kept, 0 broken (no new layer contracts at M20; orchestration infrastructure does not touch the package layer rule). `uv run ruff check` — all checks passed.

---

## Carry-over from prior milestones

None at draft time. Will land here if any M19 / M12 / M16 audit forward-defers a finding to M20.

## Carry-over from task analysis

None at draft time. Populated by `/clean-tasks m20` runs.

## Propagation status

Recorded at M20 close-out (2026-04-28):

- **M21 agent-prompt-hardening absorbing task** — not yet specced. M21 README at `design_docs/phases/milestone_21_autonomy_loop_continuation/README.md` exists; `/clean-tasks m21` is unblocked now that M20 closes. Absorbing scope: Builder return-schema non-conformance (16+ occurrences across 6 tasks in 6 autopilot iterations), Auditor cycle-summary write refusal (multiple cycle boundaries), Builder pre-stamp "Auditor verdict" pattern, Builder pre-stamp "Locked decision" pattern, sr-dev `Write` tool missing from tools list, and the harness write-policy + orchestrator-owned post-spawn summary write reframe (LOW-11). All 10 LOWs from T06 §C4 (LOW-1 through LOW-8 + LOW-10 + LOW-11) plus subsequent task recurrences feed this absorbing task. Priority: HIGH (empirical recurrence data is the smoking gun).
- **T07 dynamic model dispatch** — carries to M21. Unblocks when operator runs `python scripts/orchestration/run_t06_study.py full-study` outside autopilot AND T06 verdict flips from DEFER to GO/NO-GO.
- **T06 30-cell empirical study** — operator-resume per `runs/study_t06/A1-m12_t01/methodology_note.json`. Outside autopilot.
- **T23 cache-verification empirical** — operator-resume per `runs/cache_verification/methodology.md`. Outside autopilot.
- **T28 nice_to_have §24** — re-open trigger documented at `design_docs/nice_to_have.md §24`; stays deferred. Re-open condition: Claude Code `Task` exposes `context_management.edits` (stable release) AND T22 telemetry shows Auditor sessions still hitting >80K tokens.
- **No new milestone generated by ZZ.** M21 (Autonomy Loop Continuation) is the next load-bearing milestone; M21's task-out happens via `/clean-tasks m21`.

---

## Issues

Land under `issues/` after each task's first audit.

---

## Risk flags carried from research brief (track, not yet actionable)

- **Opus 4.7 tokenizer change.** 1.0–1.35× more tokens per byte than 4.6. Direct cost implication for any switch. Wait for Opus 4.7 to settle before making it the default `--expert` model; 4.6 remains the safer choice through Q2 2026.
- **Claude Code default-effort drift.** The Mar 3 → Apr 7, 2026 episode where Claude Code's default `effort` was lowered to `medium` and quality regressed shows that ai-workflows should *explicitly* set `effort` rather than relying on Claude Code's defaults, which can change without warning. T21 addresses this by making every `effort` setting explicit.
- **Cache-invalidation bugs in Claude Code resume.** Issues #27048, #34629, #42338, #43657 document that `--continue` / `--resume` can blow up the cache. ai-workflows prefers fresh-session orchestrator invocations; T03 / T04 file-based memory is the continuity mechanism.
- **Anthropic metering opacity.** Bug #52502 (Apr 23, 2026) suggests Opus-orchestrator + Haiku-pinned-subagent setups burn weekly limits faster than expected, with no per-model breakdown in the dashboard. T22 (per-cycle telemetry) addresses this from ai-workflows' side; the upstream issue may also resolve.

---

## Diff from prior M20 draft (summary)

- **+7 new tasks** (T21 adaptive-thinking, T22 per-cycle telemetry, T23 cache-breakpoint discipline, T24 MD discoverability, T25 periodic audit, T26 two-prompt long-running, T27 tool-result clearing).
- **All 20 prior tasks retained**, every one annotated with its research-brief verdict (SUPPORT / MODIFY / EXTEND).
- **Goals expanded from 7 to 11** to surface adaptive-thinking, MD discoverability, cache discipline, and telemetry as first-class.
- **Exit criteria fully populated** (was "pending user content"); each criterion now has empirical thresholds.
- **Phasing reorganized** to put model-tier rationalization (Phase C) ahead of slimming (Phase E) and to interleave safeguards (Phase D) earlier given Sonnet-default's load-bearing safeguard implications.
- **Non-goals expanded** with three new explicit non-goals (no Agent Teams, no mid-context model switching, no `--continue` reliance for orchestrator state) sourced from the research brief's risk-flag section.
- **Cross-phase dependencies updated** with T21 → T07 (Opus 4.7 forward compatibility blocker) and T22 → T07 (telemetry as evidence-gathering for default-tier picks).
