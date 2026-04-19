---
model: claude-opus-4-7
thinking: max
---

# /clean-implement

You are running the **Clean Implementation loop** for: $ARGUMENTS

This loop drives a task to a clean audit by cycling implement → audit up to 10 times.
You are the loop controller — the implement and audit steps are owned by the
[`/implement`](implement.md) and [`/audit`](audit.md) skills. This file does not
restate those steps; invoke those skills as the authoritative source.

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

**Before implementing:** check the issue file for any HIGH `🚧 BLOCKED` issue. If
found, stop immediately and surface it (stop condition 1).

Otherwise, run the [`/implement`](implement.md) skill against `$ARGUMENTS`. That
skill is the single source of truth for Builder-mode procedure — follow it exactly
as written there; do not re-derive its steps from memory.

### Audit phase — MANDATORY, no shortcuts

**Rule 0: every implement phase is followed by a full audit phase.** No exceptions.
The cycle is not complete until the audit skill has run end-to-end and written its
findings to the issue file. Skipping or shortcutting the audit breaks the loop — the
loop has no way to evaluate stop conditions 1–3 without a fresh audit result.

Run the [`/audit`](audit.md) skill against `$ARGUMENTS`. That skill is the single
source of truth for Auditor-mode procedure, including the mandatory
`architecture.md` read and the design-drift check. Follow it exactly as written
there; do not re-derive its steps from memory.

**What does NOT count as an audit.** Any of the following, on their own or in
combination, is a **shortcut and forbidden** as a substitute for the audit skill:

- Running the gates (`uv run pytest` / `uv run lint-imports` / `uv run ruff check`)
  alone. Gates are a subset of the audit, not the whole thing.
- Grepping / reading only the lines the /implement phase just edited to "verify the
  fix". Auditor mode re-grades **every** AC against the **full** project scope, not
  only the just-edited surface.
- Loop-controller edits to the issue file status line (e.g. flipping to `✅ PASS`
  without the audit skill running). The issue file is the audit skill's output —
  the loop controller must **never** write to it directly.
- Relying on the implement phase's own self-assessment ("I fixed both issues, so
  it should be clean"). Implementers self-grade optimistically; that is exactly
  what the audit exists to check.

**What the audit must do before the cycle can end.** Every cycle's audit must:

1. Re-load the full task scope (task spec, issue file, sibling pre-build issue
   files if present, `pyproject.toml`, `CHANGELOG.md`, `ci.yml`, every claimed
   file, tests, plus [architecture.md](../../design_docs/architecture.md) and every
   cited KDR).
2. Run every gate.
3. Do the design-drift cross-check.
4. Re-grade **every** AC — not only the ones tied to the issues that were just
   closed. A fix to one AC can regress another.
5. Update the issue file with fresh findings. Flip `RESOLVED` on issues the
   implement phase closed; add new `OPEN` entries for anything the re-grade
   surfaces. Refresh the `Audited on` line and the `Gate summary` / `Issue log`
   tables. The status header reflects the **post-audit** state, not the
   loop controller's guess.

**After auditing:** read the freshly updated issue file and evaluate stop
conditions 1–3 against what the audit wrote — not what the implement phase
claimed. If none apply and cycles remain, start the next cycle targeting only the
OPEN issues the audit identified.

---

## Reporting

At the end of each cycle, print a one-line status:

`Cycle N/10 — [CLEAN | OPEN: <count> issues | BLOCKED: <issue-id> | USER INPUT: <issue-id>]`

On final stop, summarise:

- Which stop condition triggered
- Cycle count reached
- Any remaining OPEN issues (id + one-line description)
- What the user needs to do next (if anything)