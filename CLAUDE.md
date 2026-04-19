# CLAUDE.md — ai-workflows conventions

Loaded into every Claude Code conversation. Defines Builder and Auditor
modes and shared project conventions. Step-by-step procedures live in
[.claude/commands/](.claude/commands/):

- `/implement <task>` — Builder, single pass.
- `/audit <task>` — Auditor, single pass.
- `/clean-implement <task>` — Builder → Auditor loop, up to 10 cycles.

When a skill says "follow Builder / Auditor mode from CLAUDE.md," the
rules below are what it means.

---

## Repo layout

- `ai_workflows/` — package. Three layered subpackages `primitives/`,
  `components/`, `workflows/`; enforced by `import-linter`.
- `tests/` — pytest, mirrors package structure.
- `design_docs/` — source of truth.
  - `design_docs/issues.md` — cross-cutting backlog (CRIT/IMP/OPS…).
  - `design_docs/phases/milestone_<N>_<name>/` — per milestone:
    `README.md` + `task_<NN>_<slug>.md` files.
  - `…/issues/task_<NN>_issue.md` — per-task audit file (only exists
    after an audit).
- `CHANGELOG.md` — Keep-a-Changelog, milestone/task scoped.

---

## Builder conventions

- **Issue file is authoritative amendment to task file.** If they
  disagree, task file wins; call out the conflict first. Deviations go
  into the issue file.
- **Carry-over section at bottom of task file = extra ACs.** Tick each
  as it lands.
- **Scope discipline.** Implement strictly against task + issue +
  carry-over. No invented scope, no drive-by refactors.
- **Tests.** Every AC (including carry-over) has a test under `tests/`
  mirroring the package path. Scaffolding tests may live at
  `tests/test_*.py`.
- **CHANGELOG entry.** Under `## [Unreleased]`, add
  `### Added — M<N> Task <NN>: <Title> (YYYY-MM-DD)`. List files touched,
  ACs satisfied, deviations from spec.
- **Docstrings.** Every new module: docstring citing the task and
  relationship to other modules. Every public class/function: docstring.
  Inline comments only when *why* is non-obvious.
- **No commits, PRs, or pushes unless the user asks.**
- **Stop and ask** if spec is ambiguous, an AC can't be met as written,
  or the task would break prior work.

---

## Auditor conventions

- **Full project scope, not just diff.** Verify task file, milestone
  `README.md`, sibling tasks, `pyproject.toml`, `CHANGELOG.md`,
  `.github/workflows/ci.yml`, every claimed file, the `tests/` tree,
  related `design_docs/issues.md` entries.
- **Run every gate locally.** Don't trust prior output. Include
  task-specific checks the spec calls out (e.g. Task 01 secret-scan:
  plant a test `sk-ant-…` and confirm the grep triggers).
- **Grade each AC individually.** Passing tests ≠ done.
- **Be extremely critical.** Look for ACs that look met but aren't,
  silently skipped deliverables, additions beyond spec that add
  coupling/complexity, test gaps, doc drift, secrets shortcuts.
- **Do not modify code during an audit** unless the user asks.
- **Update the existing issue file on re-audit** — no `_v2` copies. Tick
  items off, flip severities, mark `RESOLVED (commit sha)` as work lands.

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

- Include an **Action** / **Recommendation** line: which file to edit,
  which test to add, which task owns follow-up, trade-offs if relevant.
- If the fix is unclear (two reasonable options, crosses milestones,
  needs spec change) — **stop and ask the user** before finalising. No
  invented direction.
- Same rule applies to issues surfaced outside the audit file (chat,
  PRs, status updates): pair each with a solution or an explicit ask.

### Forward-deferral propagation

When an audit defers work to a future task:

1. Log the deferral in the current issue file as DEFERRED with explicit
   owner (milestone + task number).
2. Append a "Carry-over from prior audits" section at the bottom of the
   **target** task's spec file. Each `- [ ]` entry has: issue ID,
   severity, concrete "what to implement" line, source link back, and
   alternative owner if any.
3. Close the loop in the current issue file with a "Propagation status"
   footer linking to each target file.

Non-optional. Without propagation, the target Builder can't see the
deferral — issue files only exist after an audit and carry-over sections
are the only channel the Builder workflow reads.

When the target Builder finishes, they tick the carry-over; on re-audit,
flip DEFERRED → RESOLVED in the originating issue file.

---

## Canonical file locations

| Purpose                | Path                                                                |
| ---------------------- | ------------------------------------------------------------------- |
| Task spec              | `design_docs/phases/milestone_<M>_<name>/task_<NN>_<slug>.md`       |
| Task issue / audit log | `design_docs/phases/milestone_<M>_<name>/issues/task_<NN>_issue.md` |
| Milestone overview     | `design_docs/phases/milestone_<M>_<name>/README.md`                 |
| Cross-cutting backlog  | `design_docs/issues.md`                                             |
| Changelog              | `CHANGELOG.md`                                                      |
| CI gates               | `.github/workflows/ci.yml`                                          |
| Mode skills            | `.claude/commands/{implement,audit,clean-implement}.md`             |

---

## Non-negotiables

- **Layer discipline.** `primitives` ∌ `components`/`workflows`;
  `components` ∌ `workflows`. Enforced by `import-linter`.
- **Docstring discipline.** Every module/class/public function has one.
  Module docstrings cite the task and relationship to other modules.
- **Secrets discipline.** No API keys in committed files. CI
  `secret-scan` is backstop, not license.
- **Changelog discipline.** Every code-touching task updates
  `CHANGELOG.md` in the same commit.
- **Propagation discipline.** Forward-deferred items must appear as
  carry-over in the target task before the audit is complete.
- **Ask before** force-push, `reset --hard`, or any destructive git op.
