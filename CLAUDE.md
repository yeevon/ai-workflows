# CLAUDE.md — workflow instructions for ai-workflows

This file is loaded into every Claude Code conversation in this repo. It
defines the two canonical modes of operation — **Builder** and **Auditor**
— and the project conventions both modes rely on.

The step-by-step procedures for each mode live in the slash-command skills
under [.claude/commands/](.claude/commands/):

- `/implement <task>` — Builder mode, single pass.
- `/audit <task>` — Auditor mode, single pass.
- `/clean-implement <task>` — Builder → Auditor loop, up to 10 cycles.

The skills list the numbered steps (read task file, run gates, update
CHANGELOG, etc.). **This file defines the conventions those steps operate
under** — file layout, issue-file structure, severity rubric, forward-
deferral propagation, and non-negotiables. When a skill says "follow the
Builder / Auditor mode instructions from CLAUDE.md exactly," the rules
here are what it means.

---

## Repo layout (for quick orientation)

- `ai_workflows/` — the package. Three strictly layered subpackages:
  `primitives/`, `components/`, `workflows/`. Layer rules are enforced by
  `import-linter` contracts in `pyproject.toml`.
- `tests/` — pytest suite. Mirrors the package structure.
- `design_docs/` — the canonical design. This is the source of truth.
  - `design_docs/issues.md` — cross-cutting issue backlog (CRIT/IMP/OPS…).
  - `design_docs/phases/milestone_<N>_<name>/` — one directory per
    milestone. Contains a `README.md` (milestone goal + task list) and
    `task_<NN>_<slug>.md` files.
  - `design_docs/phases/milestone_<N>_<name>/issues/task_<NN>_issue.md`
    — per-task audit file (see **Auditor conventions** below). Only
    exists if an audit has been performed.
- `CHANGELOG.md` — Keep-a-Changelog style, milestone/task-scoped.

---

## Builder conventions

**Invoked by:** `/implement` or `/clean-implement` (see skills).
**Prompt shape:** "build task NN of milestone M" (or similar).

Rules the skill's procedure assumes:

- **Issue files are authoritative amendments to the task file.** When the
  two disagree, the task file wins — but call out the conflict before
  changing code. Deviations are recorded in the issue file.
- **Carry-over sections at the bottom of a task file must be treated as
  additional acceptance criteria.** These propagate forward-deferred work
  from prior audits (see Auditor conventions → Forward-deferral
  propagation). Tick each item when the test or change lands.
- **Scope discipline.** Implement strictly against the task file + issue
  file + carry-over. Do not invent new scope. Do not refactor adjacent
  code unless the task requires it.
- **Test coverage.** Every acceptance criterion (including carry-over
  entries) has at least one automated test under `tests/`, mirroring the
  package path. Scaffolding-level tests may live at `tests/test_*.py`.
- **CHANGELOG entry format.** Under `## [Unreleased]`, add a section named
  `### Added — M<N> Task <NN>: <Task Title> (YYYY-MM-DD)`. List every file
  added or modified, every acceptance criterion satisfied, and every
  deviation from the spec.
- **Docstring discipline.** Every new module gets a docstring that
  explains what it is, which task produced it, and how it relates to
  other modules. Every public class and function gets a docstring. Use
  inline comments only when the *why* is non-obvious.
- **Commit discipline.** Do not open a PR, push, or commit unless the
  user explicitly asks.
- **Stop and ask** if the spec is ambiguous or self-contradictory, an
  acceptance criterion cannot be satisfied as written, or implementing
  the task would break a prior task's behaviour or tests.

---

## Auditor conventions

**Invoked by:** `/audit` or `/clean-implement` (see skills).
**Prompt shape:** "audit task NN of milestone M" / "confirm task NN
complete, be critical" / "is task NN actually done?".

Rules the skill's procedure assumes:

- **Full project scope, not just the diff.** An audit is not trustworthy
  if it only reads changed files. Always verify the task file, milestone
  `README.md`, sibling task files, `pyproject.toml`, `CHANGELOG.md`,
  `.github/workflows/ci.yml`, every file the task claims to have created
  or modified, the relevant `tests/` tree, and related
  `design_docs/issues.md` entries.
- **Run every gate locally** — do not trust a prior run's output. Include
  any task-specific verification the spec calls out (e.g. Task 01's CI
  secret-scan: plant a test `sk-ant-…` and confirm the grep triggers).
- **Grade every acceptance criterion individually.** A task is not "done"
  because tests pass; it is done when every criterion is satisfied
  as-written, or the deviation is documented.
- **Be extremely critical.** Assume the implementer missed something.
  Look for: criteria that look satisfied but aren't, files listed in the
  spec's directory tree that were silently skipped, additions beyond spec
  that introduce hidden coupling or unearned complexity, test gaps,
  documentation drift, security / secret handling shortcuts.
- **Do not modify code during an audit** unless the user asks. The
  Auditor reports; the Builder fixes.
- **Update the issue file on re-audit** — do not create `_v2` copies.
  Keep the running log; tick items off, flip severities, or mark them
  `RESOLVED (commit sha)` when the underlying task picks them up.

### Issue file structure

Write (or update) the issue file at
`design_docs/phases/milestone_<M>_<name>/issues/task_<NN>_issue.md`:

```markdown
# Task NN — <title> — Audit Issues

**Source task:** [../task_NN_slug.md](../task_NN_slug.md)
**Audited on:** YYYY-MM-DD
**Audit scope:** <what was actually inspected>
**Status:** <one-line verdict>

## 🔴 HIGH — <one issue per subsection>
## 🟡 MEDIUM — …
## 🟢 LOW — …

## Additions beyond spec — audited and justified
## Gate summary  (table of each gate + pass/fail)
## Issue log — tracked for cross-task follow-up
(M<N>-T<NN>-ISS-NN IDs, severity, owner / next touch point)
```

### Severity rubric

- **HIGH** — an acceptance criterion is unmet, a spec deliverable is
  missing, or an architectural rule is broken.
- **MEDIUM** — a deliverable is partially met, a documented convention
  was skipped, or a gap creates real risk for a downstream task.
- **LOW** — cosmetic, forward-looking, or a flag-only observation.

### Every issue carries a proposed solution

A report that only names problems is half an audit. For each issue
(HIGH/MEDIUM/LOW, and every entry in the issue log):

- Include a concrete **Action** / **Recommendation** line that names the
  fix: which file to edit, which test to add, which task owns the
  follow-up, and (when relevant) the trade-offs between alternatives.
- If the correct fix is **not** clear — e.g. two reasonable options
  exist, the issue crosses milestone boundaries, or resolution requires
  a spec change — **stop and ask the user** how they want to handle it
  before finalizing the issue file. Do not invent a direction.
- The same rule applies whenever issues are surfaced *outside* the audit
  file (chat summaries, PR descriptions, status updates): every listed
  issue gets a paired solution or an explicit request for user
  direction.

### Forward-deferral propagation

When an audit defers work to a future task (e.g. "owner: M1 Task 11" or
"owner: M2 Worker"), the audit is not complete until the deferral has
been **propagated** to its target. The mechanism:

1. **Log the deferral** in the current task's issue file as a DEFERRED
   item with an explicit owner (milestone + task number).
2. **Append a "Carry-over from prior audits" section** at the bottom of
   the **target** task's spec file. Each entry lists:
   - the issue ID (`M<N>-T<NN>-ISS-NN`)
   - severity
   - a concrete "what to implement" line
   - a source link back to the originating issue file
   - the alternative owner, if one exists

   Use `- [ ]` checkbox format so the entry becomes an additional
   acceptance criterion for the target task's Builder.
3. **Close the loop** in the current issue file with a "Propagation
   status" footer that links to each target file where the carry-over
   was written.

This is non-optional. Without propagation, forward-deferred work is
invisible to the target Builder, because issue files only exist after an
audit and the carry-over sections are the only channel the canonical
Builder workflow reads.

When the target task's Builder finishes, they mark the carry-over
checkbox done and the originating issue file can be flipped from
DEFERRED → RESOLVED on the next audit.

---

## Canonical file locations

| Purpose                              | Path                                                                          |
| ------------------------------------ | ----------------------------------------------------------------------------- |
| Task spec                            | `design_docs/phases/milestone_<M>_<name>/task_<NN>_<slug>.md`                 |
| Task issue / audit log               | `design_docs/phases/milestone_<M>_<name>/issues/task_<NN>_issue.md`           |
| Milestone overview                   | `design_docs/phases/milestone_<M>_<name>/README.md`                           |
| Cross-cutting backlog                | `design_docs/issues.md`                                                       |
| Changelog                            | `CHANGELOG.md`                                                                |
| CI gates                             | `.github/workflows/ci.yml`                                                    |
| Mode skills                          | `.claude/commands/{implement,audit,clean-implement}.md`                       |

---

## Non-negotiables

- **Layer discipline:** `primitives` never imports `components` or
  `workflows`. `components` never imports `workflows`. Enforced by
  `import-linter`.
- **Docstring discipline:** every module, class, and public function has
  a docstring. Module docstrings explain which task produced the module
  and how it relates to others.
- **Secrets discipline:** no API keys in committed files. CI's
  `secret-scan` job is not a substitute for not pasting keys in the
  first place.
- **Changelog discipline:** every task that adds or changes code updates
  `CHANGELOG.md` in the same commit.
- **Propagation discipline:** every forward-deferred audit item must
  appear as a carry-over entry in the target task's spec file before
  the audit is considered complete.
- **Ask before force-push, reset --hard, or any destructive git op.**
