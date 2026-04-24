# CLAUDE.md — ai-workflows conventions

Loaded into every Claude Code conversation. Defines Builder and Auditor modes and shared project conventions. Step-by-step procedures live in [.claude/commands/](.claude/commands/):

- `/clean-implement <task>` — Builder → Auditor loop, up to 10 cycles.

When a skill says "follow Builder / Auditor mode from CLAUDE.md," the rules below are what it means.

---

## Grounding (read before any task)

- [design_docs/architecture.md](design_docs/architecture.md) — the architecture of record. Every task cites at least one KDR from §9.
- [design_docs/analysis/langgraph_mcp_pivot.md](design_docs/analysis/langgraph_mcp_pivot.md) — the grounding decision behind the current architecture. Design-mode, not code.
- [design_docs/roadmap.md](design_docs/roadmap.md) — milestone index.
- [design_docs/nice_to_have.md](design_docs/nice_to_have.md) — **deferred parking lot.** Do not plan work for anything listed there without an explicit trigger firing. No tasks, no milestones, no drive-by adoption.

Archived pre-pivot docs live under `design_docs/archive/pre_langgraph_pivot_2026_04_19/`. Reference only — they are not specs.

---

## Repo layout

- `ai_workflows/` — package. Four layered subpackages:
  - `primitives/` — storage, cost, tiers, providers, retry, logging.
  - `graph/` — LangGraph adapters (`TieredNode`, `ValidatorNode`, `HumanGate`, `CostTrackingCallback`, `RetryingEdge`, checkpointer).
  - `workflows/` — concrete LangGraph `StateGraph` modules.
  - `cli/` + `mcp/` — the two surfaces.
  Enforced by `import-linter`: `primitives → graph → workflows → surfaces`.
- `tests/` — pytest, mirrors package structure.
- `design_docs/` — source of truth.
  - `design_docs/architecture.md`, `design_docs/roadmap.md`, `design_docs/nice_to_have.md` — top-level.
  - `design_docs/analysis/` — grounding decisions.
  - `design_docs/adr/` — architecture decision records (file per ADR).
  - `design_docs/phases/milestone_<N>_<name>/` — per milestone: `README.md` + `task_<NN>_<slug>.md` files.
  - `design_docs/phases/milestone_<N>_<name>/issues/task_<NN>_issue.md` — per-task audit file (only exists after an audit).
  - `design_docs/archive/` — pre-pivot docs, reference-only.
- `CHANGELOG.md` — Keep-a-Changelog, milestone/task scoped.
- `.claude/commands/` — `/implement`, `/audit`, `/clean-implement` slash commands.

**Cross-cutting backlog:** there is no `design_docs/issues.md` anymore (archived). Cross-cutting items land as forward-deferred carry-over on the appropriate future task (see *Forward-deferral propagation* below). If a finding truly spans milestones and has no natural owner yet, file it in the issue file of the audit that raised it with `DEFERRED (owner: TBD)` and surface the gap to the user.

---

## Builder conventions

- **Issue file is authoritative amendment to task file.** If they disagree, task file wins; call out the conflict first. Deviations go into the issue file.
- **Carry-over section at bottom of task file = extra ACs.** Tick each as it lands.
- **Scope discipline.** Implement strictly against task + issue + carry-over. No invented scope, no drive-by refactors, no nice_to_have.md adoption.
- **Tests.** Every AC (including carry-over) has a test under `tests/` mirroring the package path. Scaffolding tests may live at `tests/test_*.py`.
- **CHANGELOG entry.** Under `## [Unreleased]`, add `### Added — M<N> Task <NN>: <Title> (YYYY-MM-DD)`. List files touched, ACs satisfied, deviations from spec.
- **Docstrings.** Every new module: docstring citing the task and relationship to other modules. Every public class/function: docstring. Inline comments only when *why* is non-obvious.
- **KDR citation.** Commit message references the KDR(s) the task implements (e.g. `M1.03 remove pydantic-ai substrate (KDR-001, KDR-005)`).
- **No commits, PRs, or pushes unless the user asks.**
- **Stop and ask** if spec is ambiguous, an AC can't be met as written, or the task would break prior work.

---

## Auditor conventions

- **Full project scope, not just diff.** Verify task file, milestone `README.md`, sibling tasks, `pyproject.toml`, `CHANGELOG.md`, `.github/workflows/ci.yml`, every claimed file, the `tests/` tree, any open issue files for sibling tasks in the same milestone, **and [design_docs/architecture.md](design_docs/architecture.md) plus every KDR the task cites**. Architecture grounding is mandatory — an audit that does not open architecture.md is incomplete.
- **Design-drift check (mandatory).** Before grading ACs, cross-check the implementation against architecture.md:
  - New dependency added? It must appear in [architecture.md §6](design_docs/architecture.md) or be justified by an ADR. Dependencies listed in [nice_to_have.md](design_docs/nice_to_have.md) are a hard stop — flag as HIGH.
  - New module or layer? It must fit the four-layer contract from [architecture.md §3](design_docs/architecture.md). Import-linter violations are HIGH.
  - LLM call added? Confirm it routes through `TieredNode` and is paired with a `ValidatorNode` (KDR-004). Confirm it does not import the `anthropic` SDK or read `ANTHROPIC_API_KEY` (KDR-003).
  - Checkpoint / resume logic added? Confirm it delegates to LangGraph's `SqliteSaver` — no hand-rolled checkpoint writing (KDR-009).
  - Retry logic added? Confirm it uses the three-bucket taxonomy from KDR-006; no bespoke try/except retry loops outside `RetryingEdge`.
  - Observability added? Confirm it uses `StructuredLogger` only. External backends (Langfuse, OTel, LangSmith) are nice_to_have.md items — HIGH if pulled in without trigger.
  - Any drift found is logged as HIGH with a `Violates KDR-XXX` or `Contradicts architecture.md §X` line. The task cannot pass audit while a drift HIGH is open.
- **Run every gate locally.** Don't trust prior output. Include task-specific checks the spec calls out (e.g. `grep -r pydantic_ai` for M1.03; `lint-imports` against the four-layer contract for M1.12).
- **Grade each AC individually.** Passing tests ≠ done.
- **Be extremely critical.** Look for ACs that look met but aren't, silently skipped deliverables, additions beyond spec that add coupling/complexity, test gaps, doc drift, secrets shortcuts, nice_to_have.md scope creep, silent architecture drift.
- **Do not modify code during an audit** unless the user asks.
- **Update the existing issue file on re-audit** — no `_v2` copies. Tick items off, flip severities, mark `RESOLVED (commit sha)` as work lands.

### Issue file structure

At `design_docs/phases/milestone_<M>_<name>/issues/task_<NN>_issue.md`:

```markdown
# Task NN — <title> — Audit Issues

**Source task:** [../task_NN_slug.md](../task_NN_slug.md)
**Audited on:** YYYY-MM-DD
**Audit scope:** <what was inspected>
**Status:** <one-line verdict>

## 🔴 HIGH — <one issue per subsection>
## 🟡 MEDIUM — …
## 🟢 LOW — …

## Additions beyond spec — audited and justified
## Gate summary  (table: gate + pass/fail)
## Issue log — cross-task follow-up
(M<N>-T<NN>-ISS-NN IDs, severity, owner / next touch point)
```

### Severity

- **HIGH** — AC unmet, spec deliverable missing, architectural rule broken.
- **MEDIUM** — deliverable partial, convention skipped, downstream risk.
- **LOW** — cosmetic, forward-looking, flag-only.

### Every issue carries a proposed solution

For every issue (any severity, including issue log entries):

- Include an **Action** / **Recommendation** line: which file to edit, which test to add, which task owns follow-up, trade-offs if relevant.
- If the fix is unclear (two reasonable options, crosses milestones, needs spec change) — **stop and ask the user** before finalising. No invented direction.
- Same rule applies to issues surfaced outside the audit file (chat, PRs, status updates): pair each with a solution or an explicit ask.

### Forward-deferral propagation

When an audit defers work to a future task:

1. Log the deferral in the current issue file as `DEFERRED` with explicit owner (milestone + task number).
2. Append a **"Carry-over from prior audits"** section at the bottom of the **target** task's spec file. Each `- [ ]` entry has: issue ID, severity, concrete "what to implement" line, source link back, and alternative owner if any.
3. Close the loop in the current issue file with a "Propagation status" footer linking to each target file.

Non-optional. Without propagation, the target Builder can't see the deferral — issue files only exist after an audit, and carry-over sections are the only channel the Builder workflow reads.

When the target Builder finishes, they tick the carry-over; on re-audit, flip `DEFERRED → RESOLVED` in the originating issue file.

### nice_to_have.md boundary

If a finding naturally maps to an item in [design_docs/nice_to_have.md](design_docs/nice_to_have.md):

- Do **not** forward-defer to a future task — these items have no milestone.
- Note the match in the issue file under a `## Deferred to nice_to_have` section with the nice_to_have §N reference and the trigger that would justify promotion.
- Keep the finding itself addressed against the actual task's scope (don't skip the audit because the "real fix" is deferred).

---

## Canonical file locations

| Purpose                | Path                                                                |
| ---------------------- | ------------------------------------------------------------------- |
| Architecture           | `design_docs/architecture.md`                                       |
| Roadmap                | `design_docs/roadmap.md`                                            |
| Deferred parking lot   | `design_docs/nice_to_have.md`                                       |
| Grounding analyses     | `design_docs/analysis/*.md`                                         |
| ADRs                   | `design_docs/adr/*.md`                                              |
| Milestone overview     | `design_docs/phases/milestone_<M>_<name>/README.md`                 |
| Task spec              | `design_docs/phases/milestone_<M>_<name>/task_<NN>_<slug>.md`       |
| Task issue / audit log | `design_docs/phases/milestone_<M>_<name>/issues/task_<NN>_issue.md` |
| Changelog              | `CHANGELOG.md`                                                      |
| CI gates               | `.github/workflows/ci.yml`                                          |
| Slash commands         | `.claude/commands/{implement,audit,clean-implement}.md`             |

---

## Non-negotiables

- **Layer discipline.** `primitives → graph → workflows → surfaces`. `primitives` imports nothing above itself; `graph` imports only `primitives`; `workflows` imports `graph` + `primitives`; surfaces (`cli`, `mcp`) import `workflows` + `primitives`. Enforced by `import-linter`.
- **No Anthropic API (KDR-003).** Claude access is OAuth-only via the `claude` CLI subprocess. No `ANTHROPIC_API_KEY` lookup, no `anthropic` SDK import.
- **Validator after every LLM node (KDR-004).** Workflows that add an LLM node without a paired validator fail audit.
- **Docstring discipline.** Every module/class/public function has one. Module docstrings cite the task and relationship to other modules.
- **Secrets discipline.** No API keys in committed files. CI `secret-scan` is backstop, not license.
- **Changelog discipline.** Every code-touching task updates `CHANGELOG.md` in the same commit.
- **Propagation discipline.** Forward-deferred items must appear as carry-over in the target task before the audit is complete.
- **nice_to_have discipline.** Items listed in `nice_to_have.md` are out of scope by default. Adoption requires a new KDR in `architecture.md` plus an ADR — not a task.
- **Ask before** force-push, `reset --hard`, or any destructive git op.
