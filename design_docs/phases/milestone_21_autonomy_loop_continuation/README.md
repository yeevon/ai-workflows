# Milestone 21 — Autonomy Loop Continuation

**Status:** 📝 Drafting (split from M20 2026-04-27 per audit recommendation M3 — M20's 27-task scope was too large for a single milestone). M21 carries Phases E (Slimming), F (Productivity commands), G (Parallel-builders foundation). Branch: continuation work happens on `workflow_optimization` after M20 lands, or on a new branch named at M21 kickoff.

**Grounding:** Same as M20 — research brief `design_docs/phases/milestone_20_autonomy_loop_optimization/research_analysis.md` (Q1–Q2 2026 best-practices synthesis post-Opus-4.6) and the model-dispatch-specific `design_docs/analysis/autonomy_model_dispatch_study.md` · project memory `project_autonomy_optimization_followups.md` · `architecture.md` §9 KDRs · M20 close-out (post-shipment baseline measurements).

**Scope note.** Same scope-shape as M20: changes the autonomy infrastructure (`.claude/agents/`, `.claude/commands/`, CLAUDE.md), not the runtime (`ai_workflows/`). KDR drift checks still apply. M21 builds on the empirical baseline M20 ships.

---

## Why this milestone exists

M20 closes the four token leaks (compaction quartet), parallelizes the terminal gate, lands evidence-based model dispatch, and adds defense-in-depth integrity checks. After M20, the autonomy loop is dramatically cheaper per task and the orchestrator carries less cross-task context. **M21 is the second-order optimization** — given a measurably-smaller per-task floor, what redundancy remains to remove, what productivity surfaces are missing, and how does parallel-Builders foundation come together?

Three load-bearing reasons M21 exists distinct from M20:

1. **Slimming benefits compound on top of compaction.** Moving threat-model + KDR-table out of CLAUDE.md (T11) saves ~X tokens per conversation forever. That win is independent of compaction but greater when measured against a smaller post-compaction floor — the numerator (tokens saved by slimming) doesn't change, the denominator (per-task cost) drops, so the relative-percentage win is bigger.
2. **Productivity commands shouldn't gate on optimization work.** `/triage`, `/check`, `/ship`, `/sweep` are independent surfaces with their own value (post-halt diagnosis, on-disk vs pushed verification, manual happy-path, ad-hoc review). Carving them into M21 keeps M20 focused on optimization while not blocking the productivity wins indefinitely.
3. **Parallel-Builders foundation is its own architectural unit.** The spec format extension (T17) is the actual blocker for parallel work; T18 + T19 are stretch goals. None of these blocks M20's optimization work, and M20's defense-in-depth (T08, T09, T22) makes T18+T19 safer when they land.

---

## Goals

1. **Agent-prompt deduplication.** Extract shared non-negotiables into `.claude/agents/_common/`; each agent's prompt declares it follows the shared block instead of inlining it. CLAUDE.md becomes a thin index — agent-specific sections (threat model, KDR table, verification discipline) move into the agents that read them, with a 1-paragraph summary + section-anchor pointer remaining in CLAUDE.md so main-context Claude can answer ad-hoc questions without spawning a sub-agent.
2. **MD-file discoverability.** One topic per file in `agent_docs/`, ≤500-token sections with `##` anchors, top-of-file 3-line summary, no inlined code (link to `src/foo.py:42` instead). One-time work that pays off every sub-agent spawn thereafter.
3. **New productivity commands.** Land `/triage`, `/check`, `/ship`, `/sweep` as Skills (`.claude/skills/triage/`, etc.) following the Anthropic Agent Skills pattern (progressive disclosure, ~100 tokens metadata, full skill loads only on trigger). At minimum the highest-value surface (`/triage`) ships in M21; full set scoped per task spec.
4. **Parallel-builders foundation.** Spec format extension that enumerates per-slice file/symbol scope (T17) — benefits serial Builders too via clearer review signatures. Worktree-coordinated parallel Builder spawn (T18) and orchestrator-owned close-out (T19) lean on Claude Code v2.1.49's native `--worktree` and `isolation: worktree` frontmatter. T18 + T19 are stretch goals — explicit defer-to-M22 if M21 scope grows.
5. **Continuous-improvement infrastructure.** Periodic skill / scheduled-task efficiency audit (T25) and two-prompt long-running pattern (T26) as continuous-improvement hooks rather than one-shot tasks.

---

## Exit criteria

(Goal-numbered.)

1. **(G1)** `.claude/agents/_common/non_negotiables.md` exists, ≤ 500 tokens, referenced explicitly in each agent's frontmatter. CLAUDE.md slim: threat-model section moves to `security-reviewer.md`, seven-KDR table moves to `auditor.md` + `task-analyzer.md` + `architect.md` + `dependency-auditor.md`, "Verification discipline" block moves to `_common/verification_discipline.md`. **Each removed section retains a 1-paragraph summary + section-anchor pointer in CLAUDE.md** (e.g. threat-model summary → `[.claude/agents/security-reviewer.md#threat-model]`). Test: `wc -l CLAUDE.md` shows ≥ 30% reduction; `grep -q "security-reviewer.md#threat-model" CLAUDE.md` confirms each removed section has a placeholder summary + anchor link. **(Satisfied at T11; CLAUDE.md is now 83 lines — 39% reduction from 136.)**
2. **(G2)** MD-file discoverability audit completed. Every file in `agent_docs/` and `.claude/agents/*.md` has: (a) one topic per file, (b) ≤500-token sections with `##` heading anchors, (c) top-of-file 3-line summary, (d) no inline code (links to `src/foo.py:line` instead). Sub-agents can request just the section they need. (rubric locked at T24; `.claude/agents/*.md` and `_common/*.md` portion satisfied; `agent_docs/` portion deferred to T26 — audit script reusable there)
3. **(G3)** At least one new productivity command lands as a Skill (`/triage` recommended). Spec covers full set; M21 ships at minimum the highest-value surface.
4. **(G4)** `/clean-tasks` spec format extension enumerates per-slice file/symbol scope when ACs decompose into file-disjoint slices. Gates the parallel-build flag on this format being present; tasks without it run serial as today. Native `isolation: worktree` frontmatter on the parallel-builder sub-agent. Concurrency capped at 3–4 worktrees. Tasks T18 + T19 stretch — explicit "deferred to M22 if scope-bounded" line in M21 close-out.
5. **(G5)** Quarterly audit prompt over each Skill and slash-command lands as a runnable command (`/audit-skills` or similar). Two-prompt pattern documented in `agent_docs/long_running_pattern.md` with reference Builder loop.

---

## Non-goals

- **No runtime code changes.** Same as M20.
- **No new KDRs locked at M21.** Propose via architect agent if surfaced.
- **No compaction or model-dispatch changes.** That's M20's scope; M21 builds on M20's baseline.
- **No `nice_to_have.md` adoption** beyond what M20's threads already cover.

---

## Key decisions in effect

| Decision | Reference |
|---|---|
| All M20 key decisions remain in effect | M20 README · same memory + research brief grounding |
| Build on M20's measured baseline — no re-optimization of M20 territory | M20 close-out report |
| KDR-014 affirmation continues — operator knobs only, no user-facing quality knobs | architecture.md KDR-014 · ADR-0009 |

---

## Task pool

### Phase E — Slimming (deduplication + on-demand context loading)

| # | Task | Research-brief verdict | Phase / Kind | Status |
|---|---|---|---|---|
| 10 | Common-rules extraction (`.claude/agents/_common/non_negotiables.md` ≤500 tokens, plus `_common/verification_discipline.md`; each agent's frontmatter references them) | SUPPORT + EXTEND (T10 from #4) | Slimming / doc | ✅ Done |
| 11 | CLAUDE.md slim (threat-model → `security-reviewer.md`; seven-KDR table → `auditor.md` + `task-analyzer.md` + `architect.md` + `dependency-auditor.md`; CLAUDE.md becomes a one-page index with summary+pointer per removed section) | STRONGLY SUPPORT (T11 from #3) | Slimming / doc | ✅ Done |
| 12 | Skills extraction (per-agent capabilities; canonical SKILL.md frontmatter with tight `description:` for routing; body references helper files rather than inlining) | SUPPORT + MODIFY (T12 from #1) | Slimming / code + doc | 📝 Candidate |
| 24 | MD-file discoverability audit (one topic per file in `agent_docs/`; ≤500-token sections with `##` anchors; top-of-file 3-line summary; no inline code — links to `src/foo.py:line` instead) | NEW (research-brief T24) | Slimming / doc | ✅ Done |
| 25 | Periodic skill / scheduled-task efficiency audit (quarterly audit prompt over each Skill and slash-command: redundant tool round-trips? screenshots where text-extraction would do? re-reads of files already in memory? missing tool declarations forcing repeated ToolSearch?) | NEW (research-brief T25, citing Nate Jones / Nicholas Rhodes "automated task bloat" pattern) | Slimming / doc + code | 📝 Candidate |
| 26 | Two-prompt long-running pattern for multi-cycle Builder runs (initializer prompt produces `iter_<N>_plan.md` and `iter_<N>_progress.md`; subsequent cycles update only progress file) | NEW (research-brief T26) | Slimming / doc + code | 📝 Candidate |

### Phase F — Productivity commands (independent; pick highest-value first)

| # | Task | Research-brief verdict | Phase / Kind | Status |
|---|---|---|---|---|
| 13 | `/triage` (halt-diagnosis surface — reads latest issue file + recommendation file + recent commits) — structured as Skill (`.claude/skills/triage/`) | SUPPORT + MODIFY (T13 from #2a) | Productivity / code + doc | 📝 Candidate |
| 14 | `/check` (verify on-disk vs pushed state) — Skill | SUPPORT + MODIFY (T14 from #2b) | Productivity / code + doc | 📝 Candidate |
| 15 | `/ship` (manual happy-path: build wheel + release_smoke + uv publish; host-only) — Skill | SUPPORT + MODIFY (T15 from #2c) | Productivity / code + doc | 📝 Candidate |
| 16 | `/sweep` (sr-dev + sr-sdet + security-reviewer against current diff, no auto-implement loop) — Skill | SUPPORT + MODIFY (T16 from #2d) | Productivity / code + doc | 📝 Candidate |

### Phase G — Parallel-builders foundation (T17 in scope; T18/T19 stretch)

| # | Task | Research-brief verdict | Phase / Kind | Status |
|---|---|---|---|---|
| 17 | Spec format extension — per-slice file/symbol scope (parallel-Builders foundation; benefits serial Builders too via clearer review signatures) | STRONGLY SUPPORT (T17 from #15-X) | Parallelism / doc + code | 📝 Candidate |
| 18 | Worktree-coordinated parallel Builder spawn — leans on Claude Code v2.1.49 `--worktree` and `isolation: worktree` frontmatter; concurrency capped at 3–4 | STRONGLY SUPPORT + MODIFY (T18 from #15-Y) | Parallelism / code | 📝 Stretch |
| 19 | Orchestrator-owned close-out (CHANGELOG + status-surface flips after parallel-builder merge) | SUPPORT (T19 from #15-Z) | Parallelism / code | 📝 Stretch |
| ZZ | Milestone close-out | n/a | Closeout / doc | 📝 Planned |

---

## Suggested phasing

| Phase | Tasks | Rationale |
|---|---|---|
| **E — Slimming (redundancy + on-demand)** | T10 → T11 → T24 → T12 → T26 → T25 | T10 (`_common/` extraction) lands first because T11's removed CLAUDE.md sections need a destination. T11 second — highest-leverage anchor. T24 (MD discoverability) before T12 (Skills) because Skills depend on having scannable source material. T26 (two-prompt pattern) and T25 (periodic audit) are continuous-improvement, not blocking. |
| **F — Productivity commands** | T13 → T14 → T16 → T15 | Independent of E + G. `/triage` highest value (post-halt diagnosis is the most-frequent user need). `/ship` last because it's host-only and has the largest blast radius. |
| **G — Parallel-builders foundation** | T17 → (T18, T19 stretch) | T17 spec extension benefits any reviewer (precise per-slice signatures help even serial Builders). T18+T19 stretch — explicit defer-to-M22 if M21 scope grows. |

---

## Cross-phase dependencies

- **T10** (common-rules extraction) → blocks **T11** (CLAUDE.md slim — moved sections need a destination).
- **T24** (MD discoverability) → strongly precedes **T12** (Skills) — Skills' progressive-disclosure pattern depends on the source MDs being scannable.
- **T17** → blocks **T18** and **T19**.
- **No cross-milestone dependencies blocking M21** — M20 close-out is the prerequisite, but specific M20 tasks don't need to land in any particular order before M21 starts (M20 must just be **closed** for the baseline measurements to be stable).

---

## Dependencies on prior milestones

- **M20 must be fully closed.** M21's slimming wins are measured against M20's post-shipment baseline. Before M20 closes, slimming numbers are noisy.

---

## Carry-over from prior milestones

None at draft time. Will land here if any M20 audit forward-defers a finding to M21.

## Carry-over from task analysis

None at draft time. Populated by `/clean-tasks m21` runs.

## Propagation status

Filled in at audit time. Anticipated forward-deferrals from M21:

- **T18 + T19 (parallel Builder spawn + orchestrator close-out)** — explicit `nice_to_have.md` entry with trigger "T17 spec format adopted on ≥ 5 tasks AND user requests parallel-Builder execution" if deferred from M21 to M22.
- **Multi-orchestrator parallelism** (concurrent `/auto-implement` runs) — same trigger as M20's version: "first time queue depth + per-task wall-clock makes a single-orchestrator drain take > 24h."
- **Continuous-improvement audit cadence** — if T25 lands as one-shot rather than recurring, document the cadence promotion trigger.

---

## Issues

Land under `issues/` after each task's first audit.

---

## Source

Split from M20 2026-04-27 per audit recommendation M3 (27-task scope was too large for a single milestone). M20 retains Phases A (compaction quartet + T28), B (parallel terminal gate), C (model-tier rationalization), D (defense-in-depth integrity). M21 carries Phases E (slimming), F (productivity commands), G (parallel-builders foundation). Each phase is internally cohesive; no task crosses the M20/M21 boundary.
