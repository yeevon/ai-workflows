# Milestone 20 — Autonomy Loop Optimization

**Status:** 📝 Drafting (planning canvas — pending user content for additional optimization threads).
**Branch:** `workflow_optimization` (user-named; milestone doc uses `autonomy_loop_optimization` to avoid overloading the existing `ai_workflows/workflows/` package term).
**Grounding:** [project memory `project_autonomy_optimization_followups.md`](../../../.. /memory/) (15 threads — captures #1-15) · [architecture.md §9 KDRs](../../architecture.md) · [autonomy validation](../../../CHANGELOG.md) (M12 T01 a7f3e8f, T02 fc8ef19, T03 1677889 — autopilot end-to-end validation 2026-04-27).

> **Scope note.** Every milestone before M20 changed the **runtime** (`ai_workflows/` package). M20 changes the **autonomy infrastructure** — agent prompts (`.claude/agents/`), slash commands (`.claude/commands/`), and the project context doc (`CLAUDE.md`). Runtime code is read-only at this milestone except where a finding requires a runtime hook (e.g. a structured log line the orchestrator parses). KDR drift checks still apply — M20 must not violate the seven load-bearing KDRs while reshaping the loop that enforces them.

## Why this milestone exists

Autopilot validated end-to-end on 2026-04-27 (M12 T01-T03 + T08 shipped autonomously over 4 iterations). The infrastructure works. The question now is whether each task carries the right **per-task cost** — measured in three dimensions:

1. **Tokens.** Sub-agent input + sub-agent output + cross-cycle accumulation + cross-task accumulation. Today's loop ships ~30-50K tokens per Builder→Auditor cycle, and that history accumulates linearly across cycles within a task and across tasks within an autopilot run. By task 5 the orchestrator carries ~200K of prior-task chatter the new task does not need.
2. **Wall-clock.** Sequential sub-agent invocation at the terminal gate (sr-dev → sr-sdet → security-reviewer) is the obvious offender. A single-Builder serial pass on multi-file tasks is the second offender. Other agents (auditor, task-analyzer) run with full-scope reads even when the diff is small.
3. **Redundancy.** All 9 agents carry near-identical "no git mutations / no publish" non-negotiable blocks. CLAUDE.md is loaded into every conversation — including the seven-KDR table and threat-model section that only specific agents read. Agent prompts re-state behavioural rules that could live in a shared reference.

The optimization framing is **the four leaks compound multiplicatively**. Sub-agent input prune (#8), output prune (#12), in-task cycle prune (#9), and cross-task iteration prune (#13) each plug a different leak; skipping any one leaves the corresponding accumulation unaddressed. Performance and redundancy threads complement the compaction quartet.

## Goal

1. **Compaction quartet** — close the four token leaks (sub-agent input/output, in-task cycle, cross-task iteration). Combined target: ≥ 50% reduction in orchestrator token-use across a multi-task autopilot run, validated on a re-run of the M12 task slice.
2. **Parallel terminal gate** — sr-dev + sr-sdet + security-reviewer spawn in a single message; each writes to a per-reviewer fragment file; orchestrator stitches into the issue file. Wall-clock at the terminal gate drops from sum-of-three to max-of-three (target ≥ 2× improvement).
3. **Empirically-grounded model dispatch** — Shadow-Audit study (Sonnet Builder vs Opus Auditor on 5 tasks) lands first; default-Sonnet is conditional on the study showing strict-loop-compliance holds. No defaults flip without the data.
4. **Defense-in-depth integrity** — gate-output integrity check (parse raw stdout, fail-closed on missing output) + task-integrity check (orchestrator independently verifies non-empty diff + at least one named gate before stamping AUTO-CLEAN).
5. **Agent-prompt deduplication** — extract shared non-negotiables into `.claude/agents/_common/` references; each agent's prompt declares it follows the shared block instead of inlining it. CLAUDE.md slims by moving agent-specific sections (threat model, KDR table) into the agents that read them.
6. **New commands** — at least one of (`/triage`, `/check`, `/ship`, `/sweep`) lands as a productivity surface alongside the optimization work; full set scoped per task spec.
7. **Parallel-builders foundation** — spec format extension that enumerates per-slice file/symbol scope (Task X of #15). Worktree-coordinated parallel Builder spawn (Task Y) and orchestrator-owned close-out (Task Z) are stretch goals — they can defer to M21 if M20 grows beyond a quarter's worth of scope.

## Exit criteria

> **Pending user content.** Exit criteria are placeholder-shaped at draft time. The user will refine after adding additional optimization threads. Each criterion below ties to a goal-numbered above.

1. (Goal 1) Sub-agent return-value schema enforced across all 9 agents. Hard 3-line schema (`verdict / file / section`); orchestrator stops carrying chat-summary bodies into stop-condition evaluation. Test: spawn each agent on a fixture task; assert returned text length ≤ N tokens (TBD: define N empirically — likely 50-100 tokens).
2. (Goal 1) Sub-agent input prune — orchestrator passes scoped context only (task spec + KDR-relevant architecture sections + current diff). Whole-milestone-README and unrelated-sibling-issue pre-loads removed. Test: re-run M12 T01 audit; orchestrator's input-token-count to auditor drops by ≥ 30% from baseline.
3. (Goal 1) In-task `cycle_summary.md` per cycle. Auditor emits structured summary (files changed / gates pass-fail / open issues). Orchestrator reads ONLY the latest summary, not the full Builder+Audit chat text. Test: 3-cycle task; cycle 3's orchestrator-context size at Builder spawn matches cycle 1's (constant, not linear).
4. (Goal 1) Cross-task `iter_<N>_shipped.md` at autopilot iteration boundaries. Orchestrator treats prior iteration's chat history as compacted-to-summary. Test: 5-iteration autopilot run; iteration 5's orchestrator-context size matches iteration 1's.
5. (Goal 2) `/auto-implement` terminal gate spawns sr-dev + sr-sdet + security-reviewer in a single multi-Task message. Each writes to `runs/<task>/<reviewer>-review.md`. Orchestrator stitches three fragments into the issue file in one Edit pass. Test: terminal-gate wall-clock measured end-to-end; ≥ 2× improvement over baseline serial.
6. (Goal 3) Shadow-Audit study report written to `design_docs/analysis/autonomy_model_dispatch_study.md`. Findings: per-task-kind verdict-count delta (Sonnet Builder + Opus Auditor) vs baseline (Opus Builder + Opus Auditor) across 5 tasks. Recommendation: default-Sonnet GO / NO-GO + complexity-threshold rule.
7. (Goal 3) Conditional on study GO: `get_model_for_task(task_kind, complexity)` helper in the loop controller; `--expert` / `--high-complexity` flag pins Opus. Default-tier change lands on a separate isolated commit per autonomy decision 2.
8. (Goal 4) Loop controller parses raw stdout of gate commands (or `tail -3` of a captured log file) before stamping AUTO-CLEAN. Missing structured output = treat as failed gate. Test: synthetic Builder report claiming "all gates pass" with empty actual stdout — orchestrator catches and halts.
9. (Goal 4) Pre-commit ceremony: `git diff --stat <prev-commit>..HEAD` confirms non-trivial diff (or test-only-no-code is explicitly allowed by spec). Empty diff after AUTO-CLEAN = halt. Orchestrator independently re-runs at least one named gate (e.g. `pytest -q` tail) before stamping.
10. (Goal 5) `.claude/agents/_common/non_negotiables.md` exists; each agent's prompt references it instead of inlining the "no git mutations / no publish" block. CLAUDE.md slims by moving (a) the threat-model section into `security-reviewer.md`, (b) the seven-KDR table into `auditor.md` + `task-analyzer.md` + `architect.md`. Main-context Claude reads from CLAUDE.md what it needs for ad-hoc questions; agent-specific detail loads only when the agent runs.
11. (Goal 6) At least one new command lands (`/triage` recommended — "this task halted, help me understand why" — reads latest issue file + recommendation file + recent commits in one shot). Spec covers full set; M20 ships at minimum the highest-value surface.
12. (Goal 7) `/clean-tasks` spec format extension enumerates per-slice file/symbol scope when ACs decompose into file-disjoint slices. Gates the parallel-build flag on this format being present; tasks without it run serial as today. Tasks Y + Z are stretch — explicit "deferred to M21 if scope-bounded" line in M20 close-out.

## Non-goals

- **No runtime code changes** beyond the minimum hooks the orchestrator needs (e.g. structured log lines for gate-output integrity). The 9 KDRs and 4-layer rule still police runtime; M20 does not touch `ai_workflows/`.
- **No new KDRs locked at M20.** If a M20 finding implies a new architectural rule, propose it via the `architect` agent and land the KDR on its own commit (per autonomy decision 2). M20's scope is the loop, not the architecture.
- **No `nice_to_have.md` adoption** at M20. Threads not in the 15-item memo + user-added content are out of scope.
- **No CI / test infrastructure overhaul.** The pytest gate, lint-imports contracts, ruff config are untouched. M20 changes only the autonomy orchestration that *runs* those gates.
- **No removal of the Auditor's full-scope read.** The Auditor's "load the full task scope, not the diff" invariant is load-bearing; #8 prunes the *orchestrator's* pre-loads, not the Auditor's own reads. The Auditor still pulls architecture.md + sibling issues on-demand inside its own run.
- **No batching of Builder→Auditor cycles.** The Auditor still runs after every Builder cycle. Compaction (#9) reduces the *carried context* across cycles, not the cycle frequency itself.
- **No multi-orchestrator parallelism.** Two concurrent `/auto-implement` runs against the same `design_branch` are out of scope (git contention is its own architectural problem). Parallel Builders within a single orchestrator run (#15) is in scope as a stretch goal.

## Key decisions in effect

| Decision | Reference |
| --- | --- |
| Autonomy boundaries — design_branch only, no main, no publish, KDR-isolated commits, sub-agent disagreement = halt | [memory `feedback_autonomous_mode_boundaries.md`](../../../..) · [CLAUDE.md §Non-negotiables](../../../CLAUDE.md) |
| Autopilot validated baseline (4 iterations, 2 tasks shipped, 1 milestone hardened, 0 KDR additions) | [memory `project_autonomy_optimization_followups.md`](../../../..) (state 2026-04-27) |
| Compaction-quartet must land together — partial adoption leaves a leak open | [memory §"Compaction scope summary"](../../../..) |
| Empirical Shadow-Audit before defaulting model dispatch | [memory thread #7](../../../..) — no default flips without data |
| KDR-013 boundary holds — agent edits do not police user-owned external workflow code | [architecture.md KDR-013](../../architecture.md) |

## Task order — candidate pool (pending user content)

> **Format note.** This table is a candidate pool. Each row maps to a memo thread (#1-15) or a user-added thread (placeholder rows below). The user adds more content next; the orchestrator runs `/clean-tasks m20` after to harden specs. **Do not run `/auto-implement m20` until specs are hardened by /clean-tasks.**

| # | Task | Memo thread | Phase | Kind | Status |
| --- | --- | --- | --- | --- | --- |
| 01 | Sub-agent return-value schema (3-line `verdict / file / section`) | #12 | Compaction | doc | 📝 Candidate |
| 02 | Sub-agent input prune (orchestrator-side scope discipline) | #8 | Compaction | doc + code | 📝 Candidate |
| 03 | In-task cycle compaction (`cycle_summary.md` per Auditor) | #9 | Compaction | doc + code | 📝 Candidate |
| 04 | Cross-task iteration compaction (`iter_<N>_shipped.md`) | #13 | Compaction | doc + code | 📝 Candidate |
| 05 | Parallel terminal gate (sr-dev + sr-sdet + security-reviewer in one message; fragment files) | #14 | Performance | doc + code | 📝 Candidate |
| 06 | Shadow-Audit empirical study (Sonnet Builder × Opus Auditor on 5 tasks) | #7 | Performance | analysis | 📝 Candidate |
| 07 | Dynamic model dispatch (conditional on T06 GO; default-Sonnet + `--expert` override) | #6 | Performance | code | 📝 Candidate (gated on T06) |
| 08 | Gate-output integrity (parse raw stdout, fail-closed on missing output) | #10 | Safeguards | code | 📝 Candidate |
| 09 | Task-integrity safeguards (non-empty-diff check + independent gate re-run) | #11 | Safeguards | code | 📝 Candidate |
| 10 | Common-rules extraction (`.claude/agents/_common/non_negotiables.md` + agent reference) | #4 | Slimming | doc | 📝 Candidate |
| 11 | CLAUDE.md slim (move threat-model + KDR table into the agents that read them) | #3 | Slimming | doc | 📝 Candidate |
| 12 | Skills extraction (per-agent capabilities — test-quality eval, dep-audit shortcuts, etc.) | #1 | Slimming | code + doc | 📝 Candidate |
| 13 | New command — `/triage` (halt-diagnosis surface) | #2a | Productivity | code + doc | 📝 Candidate |
| 14 | New command — `/check` (verify on-disk vs pushed) | #2b | Productivity | code + doc | 📝 Candidate |
| 15 | New command — `/ship` (manual happy-path: build wheel + release_smoke + uv publish; host-only) | #2c | Productivity | code + doc | 📝 Candidate |
| 16 | New command — `/sweep` (sr-dev + sr-sdet + security-reviewer against current diff, no auto-implement loop) | #2d | Productivity | code + doc | 📝 Candidate |
| 17 | Spec format extension — per-slice file/symbol scope (parallel-Builders foundation) | #15-X | Parallelism | doc + code | 📝 Candidate |
| 18 | Worktree-coordinated parallel Builder spawn | #15-Y | Parallelism | code | 📝 Stretch |
| 19 | Orchestrator-owned close-out (CHANGELOG + status-surface flips) | #15-Z | Parallelism | code | 📝 Stretch |
| 20 | Carry-over checkbox-cargo-cult catch — validate the post-M12-T01 patch held | #5 | Safeguards | doc | 📝 Candidate |
| -- | **(user-added thread A)** | TBD | TBD | TBD | 📝 Pending user content |
| -- | **(user-added thread B)** | TBD | TBD | TBD | 📝 Pending user content |
| -- | **(user-added thread C)** | TBD | TBD | TBD | 📝 Pending user content |
| ZZ | Milestone close-out | n/a | Closeout | doc | 📝 Planned |

### Suggested phasing

| Phase | Tasks | Rationale |
| --- | --- | --- |
| **A — Compaction (token reduction)** | T01 → T02 → T03 → T04 | Foundation. T01 (output schema) gates everything else — without it, downstream pruning leaks the same way. T02-T04 plug one accumulation surface each. Sequential within the phase. |
| **B — Parallel terminal gate (perf)** | T05 | Independent of Phase A. Could run in parallel iteration if /autopilot runs Phase A and Phase B concurrent — but keeping serial is safer for first-pass validation. |
| **C — Slimming (redundancy)** | T10 → T11 → T12 | Land after compaction so the new token-floor is measurable; slimming on top should compound the win. |
| **D — Empirical study + model dispatch** | T06 → T07 (gated) | Study before defaulting. T07 conditional on T06's GO verdict. |
| **E — Safeguards** | T08 → T09 → T20 | Defense-in-depth. Lands BEFORE Phase D in priority, because T07 (default-Sonnet) makes T08+T09 more load-bearing — Sonnet is more likely to confidently misreport than Opus. Re-order if Phase D is deferred. |
| **F — Productivity commands** | T13 → T14 → T15 → T16 | Independent. Can land any time; pick highest-value first (recommended T13 `/triage`). |
| **G — Parallel Builders foundation** | T17 → (T18, T19 stretch) | Spec format extension benefits serial Builders too (precise per-slice signatures help any reviewer). T18+T19 are stretch — explicit defer-to-M21 if M20 scope grows. |

### Cross-phase dependencies

- T01 (return-value schema) → blocks T05 (parallel gate; fragment-file format reuses the schema).
- T03 (in-task cycle compaction) → benefits from T01 but does not strictly block.
- T07 (default-Sonnet) → blocks T08+T09 from being optional. If T07 ships, T08+T09 are required.
- T17 → blocks T18, T19.
- T11 (CLAUDE.md slim) → must land AFTER T10 (common-rules extraction) so the moved sections have a destination.

## Dependencies

- **No runtime dependency on prior milestones.** M20 reshapes orchestration; runtime invariants are unchanged. KDR drift checks still apply.
- **M12 must be fully closed.** M20 baselines its before/after measurements against the M12 task slice. T04-T07 of M12 are still open at M20 draft time; M12 close-out (M12 T07) lands before M20 T01 can establish a clean baseline.

## Carry-over from prior milestones

- *None at draft time.* Will land here if any M19 / M12 / M16 audit forward-defers a finding to M20.

## Carry-over from task analysis

- *None at draft time.* Populated by `/clean-tasks m20` runs.

## Propagation status

Filled in at audit time. Anticipated forward-deferrals from M20:

- Multi-orchestrator parallelism (concurrent `/auto-implement` runs) — `nice_to_have.md` entry with trigger "first time queue depth + per-task wall-clock makes a single-orchestrator drain take > 24h."
- Per-task model-tier learning (build a per-task-kind dispatch table from observed verdicts) — `nice_to_have.md` entry with trigger "T06 study identifies 3+ task-kinds with stable Sonnet-vs-Opus delta patterns."
- Builder-side worktree parallelism (T18 + T19 if deferred from M20) — `nice_to_have.md` entry with trigger "post-M20 measurement shows Builder is the new wall-clock bottleneck after parallel-reviewers + compaction land."

## Issues

Land under [issues/](issues/) after each task's first audit.

---

## User-content scratchpad

> **Use this section to capture additional optimization threads before /clean-tasks generates per-task specs.** Format suggestion: one numbered item per thread, with rough fields `Thread name / Bottleneck signal / Proposed mechanism / Estimated cost / Phase`. The orchestrator will fold these into the candidate-pool table above when /clean-tasks runs.

(empty — pending user input)
