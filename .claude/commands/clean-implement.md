---
model: claude-opus-4-7
thinking: max
---

You are running the **Clean Implementation loop** for: $ARGUMENTS

This loop drives a task to a clean audit by cycling implement → audit up to 10 times.
You are the loop controller — you invoke the implement and audit skills yourself by
following their instructions directly (do not call `/implement` or `/audit` as slash
commands; execute their steps inline).

---

## Stop conditions (check after every audit, in priority order)

1. **BLOCKER** — The audit issue file contains a HIGH issue marked `🚧 BLOCKED`
   that requires user input to resolve. Stop immediately. Surface the blocker
   verbatim to the user. Do not start another iteration.

2. **USER INPUT REQUIRED** — The audit identified any issue (any severity) where the
   recommended resolution says "stop and ask the user" or "user decision needed".
   Stop immediately. List every such issue to the user. Do not start another iteration.

3. **CLEAN** — The audit issue file status line reads `✅ PASS` with no OPEN issues
   (ISS-XX entries marked OPEN or 🟡/🟢 OPEN). Stop and report success.

4. **CYCLE LIMIT** — 10 implement→audit cycles completed without hitting conditions
   1–3. Stop and present the outstanding issue list to the user.

---

## Loop procedure

For each cycle (1 … 10):

### Implement phase

Follow the Builder mode instructions from CLAUDE.md exactly:
1. Read the task file in full.
2. Read the matching issue file if it exists — treat it as authoritative amendments.
3. Read the milestone README for scope context.
4. Implement strictly against the task file + issue file. Do not invent scope.
5. Write tests for every acceptance criterion under `tests/`.
6. Run the full gate: `uv run pytest`, `uv run lint-imports`, `uv run ruff check`.
7. Update CHANGELOG.md under `## [Unreleased]`.
8. Every new module gets a docstring; every public class and function gets a docstring.

**Before implementing:** check the issue file for any HIGH `🚧 BLOCKED` issue. If
found, stop immediately and surface it (stop condition 1).

### Audit phase

Follow the Auditor mode instructions from CLAUDE.md exactly:
1. Load the full project scope (task file, milestone README, sibling tasks,
   pyproject.toml, CHANGELOG.md, ci.yml, all claimed files, tests, issues.md).
2. Run every gate locally: `uv run pytest`, `uv run lint-imports`, `uv run ruff check`.
3. Grade each acceptance criterion individually.
4. Be extremely critical — assume the implementer missed something.
5. Write or update the issue file with HIGH/MEDIUM/LOW findings, each with a
   concrete proposed solution.
6. Do not modify code in the audit phase.

**After auditing:** evaluate stop conditions 1–3. If none apply and cycles remain,
start the next cycle targeting only the OPEN issues the audit identified.

---

## Reporting

At the end of each cycle, print a one-line status:
`Cycle N/10 — [CLEAN | OPEN: <count> issues | BLOCKED: <issue-id> | USER INPUT: <issue-id>]`

On final stop, summarise:
- Which stop condition triggered
- Cycle count reached
- Any remaining OPEN issues (id + one-line description)
- What the user needs to do next (if anything)
