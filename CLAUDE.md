# CLAUDE.md — workflow instructions for ai-workflows

This file is loaded into every Claude Code conversation in this repo. It
defines two canonical modes of operation: **Auditor** and **Builder**.
Every task in `design_docs/phases/milestone_*/` is expected to be worked
in Builder mode and verified in Auditor mode.

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
    — per-task audit file (see **Auditor** below). Only exists if an
    audit has been performed.
- `CHANGELOG.md` — Keep-a-Changelog style, milestone/task-scoped.

---

## Mode 1 — Builder

**Prompt shape:** "build task NN of milestone M" (or similar).

**Default behaviour — follow this unless the user overrides:**

1. **Read the task file** in full:
   `design_docs/phases/milestone_<M>_<name>/task_<NN>_<slug>.md`.
2. **Read the matching issue file if it exists:**
   `design_docs/phases/milestone_<M>_<name>/issues/task_<NN>_issue.md`.
   Issue files record deviations, deferrals, and carry-over work from
   prior audits of the same task. Treat them as authoritative amendments
   to the task file.
3. **Read the milestone `README.md`** for scope context and to
   understand how this task fits with sibling tasks.
4. **Implement strictly against the task file + issue file.** Do not
   invent new scope. Do not refactor adjacent code unless the task
   requires it. If the task file and the code disagree, the task file
   wins — but call out the conflict before changing code.
5. **Write tests** for every acceptance criterion. Tests live under
   `tests/` mirroring the package path (e.g. a primitives task's tests
   go under `tests/primitives/`). Scaffolding-level tests may live at
   `tests/test_*.py`.
6. **Run the full gate locally** before declaring complete:
   - `uv run pytest`
   - `uv run lint-imports`
   - `uv run ruff check`
7. **Update `CHANGELOG.md`** under `## [Unreleased]` with a section named
   `### Added — M<N> Task <NN>: <Task Title> (YYYY-MM-DD)`. List every
   file added or modified, the acceptance criteria satisfied, and any
   deviations from the spec.
8. **Comment thoroughly.** Every new module gets a module docstring that
   explains what it is, which task produced it, and how it relates to
   other modules. Every public class and function gets a docstring. Use
   inline comments only when the *why* is non-obvious.
9. **Stop and ask** if any of the following happens:
   - The task spec is ambiguous or self-contradictory.
   - An acceptance criterion cannot be satisfied as written (e.g. the
     tool behaves differently than the spec assumes).
   - Implementing the task would require breaking a prior task's
     behaviour or tests.

**Do not** open a PR, push, or commit unless the user explicitly asks.

---

## Mode 2 — Auditor

**Prompt shape:** "audit task NN of milestone M" / "confirm task NN
complete, be critical" / "is task NN actually done?".

**Default behaviour:**

1. **Load the full project scope.** An audit is not trustworthy if it
   only looks at the changed files. Always read/verify:
   - the task file for the task under audit
   - the milestone `README.md` and sibling task files (to catch
     spec drift between tasks)
   - `pyproject.toml`, `CHANGELOG.md`, `.github/workflows/ci.yml`
   - every file the task claims to have created or modified
   - the relevant `tests/` tree
   - any related `design_docs/issues.md` entries
2. **Run every gate locally** — do not trust a prior run's output:
   - `uv run pytest`
   - `uv run lint-imports`
   - `uv run ruff check`
   - any task-specific verification the spec calls out (e.g. Task 01's
     CI secret-scan: plant a test `sk-ant-…` and confirm the grep
     triggers)
3. **Grade each acceptance criterion** from the task file individually.
   A task is not "done" because tests pass; it is done when every
   criterion is satisfied as-written, or when the deviation is
   documented.
4. **Be extremely critical.** Assume the implementer missed something.
   Actively look for:
   - acceptance criteria that look satisfied but actually aren't (e.g.
     "three contracts" vs. two contracts present)
   - files listed in the spec's directory tree that were silently
     skipped
   - additions beyond spec that might introduce hidden coupling or
     unearned complexity
   - test gaps — criteria that are not covered by an automated test
   - documentation drift — module docstrings that reference files that
     don't exist, or CHANGELOG entries that don't match reality
   - security / secret handling shortcuts
5. **Write (or update) the issue file** at
   `design_docs/phases/milestone_<M>_<name>/issues/task_<NN>_issue.md`.
   Use this structure:

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

   Severity rubric:
   - **HIGH** — an acceptance criterion is unmet, a spec deliverable is
     missing, or an architectural rule is broken.
   - **MEDIUM** — a deliverable is partially met, a documented convention
     was skipped, or a gap creates real risk for a downstream task.
   - **LOW** — cosmetic, forward-looking, or a flag-only observation.

   **Every issue must carry a proposed solution.** A report that only
   names problems is half an audit. For each issue (HIGH/MEDIUM/LOW,
   and every entry in the issue log):
   - Include a concrete **Action** / **Recommendation** line that names
     the fix: which file to edit, which test to add, which task owns
     the follow-up, and (when relevant) the trade-offs between
     alternatives.
   - If the correct fix is **not** clear — e.g. two reasonable options
     exist, the issue crosses milestone boundaries, or resolution
     requires a spec change — **stop and ask the user** how they want
     to handle it before finalizing the issue file. Do not invent a
     direction.
   - The same rule applies whenever issues are surfaced *outside* the
     audit file (chat summaries, PR descriptions, status updates):
     every listed issue gets a paired solution or an explicit request
     for user direction.

6. **Update the issue file on re-audit** — do not create `_v2` copies.
   Keep the running log there; tick items off, flip severities, or mark
   them `RESOLVED (commit sha)` when the underlying task picks them up.

7. **Do not modify code during an audit** unless the user asks. The
   Auditor reports; the Builder fixes.

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
- **Ask before force-push, reset --hard, or any destructive git op.**
