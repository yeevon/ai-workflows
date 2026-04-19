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

### Audit phase

Run the [`/audit`](audit.md) skill against `$ARGUMENTS`. That skill is the single
source of truth for Auditor-mode procedure, including the mandatory
`architecture.md` read and the design-drift check. Follow it exactly as written
there; do not re-derive its steps from memory.

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