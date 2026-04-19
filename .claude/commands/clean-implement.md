---
model: claude-opus-4-7
thinking: max
---

# /clean-implement

You are running the **Clean Implementation loop** for: $ARGUMENTS

This loop drives a task to a clean audit by cycling implement → audit up to 10 times. You are the loop controller — execute the Builder and Auditor steps **inline** in this conversation. Do **not** call `/implement` or `/audit` as separate skills; follow the steps described below directly.

---

## Stop conditions (check after every audit phase, in priority order)

1. **BLOCKER** — The audit issue file contains a HIGH issue marked `🚧 BLOCKED` that requires user input to resolve. Stop immediately. Surface the blocker verbatim to the user. Do not start another iteration.
2. **USER INPUT REQUIRED** — The audit identified any issue (any severity) where the recommended resolution says "stop and ask the user" or "user decision needed". Stop immediately. List every such issue to the user. Do not start another iteration.
3. **CLEAN** — The audit issue file status line reads `✅ PASS` with no OPEN issues (no `ISS-XX` entries marked OPEN, 🟡, or 🟢). Stop and report success.
4. **CYCLE LIMIT** — 10 implement→audit cycles completed without hitting conditions 1–3. Stop and present the outstanding issue list to the user.

At the start of the very first cycle only: if the issue file already contains an unresolved BLOCKER from a prior session, treat that as condition 1 immediately — don't run the implement phase against an open blocker.

---

## Loop procedure

For each cycle (1 … 10), run the implement phase and the audit phase **back-to-back in the same conversation**. The audit phase must run after every implement phase — no text summary, no verdict, no todo update between them. The audit phase is the only thing that can decide whether the task is clean; your self-assessment does not count.

### Implement phase — Builder mode (CLAUDE.md)

**Before implementing:** open the issue file at `design_docs/phases/milestone_<N>_<name>/issues/task_<NN>_issue.md`. If a HIGH issue is marked `🚧 BLOCKED`, stop immediately and surface it (stop condition 1). Do not run the implement phase against an open blocker.

Otherwise, follow Builder-mode from CLAUDE.md exactly:

1. Read the task file in full.
2. Read the matching issue file if it exists — treat it as an authoritative amendment to the task file. If the two disagree, the task file wins; call out the conflict first. Deviations go into the issue file.
3. Read the milestone `README.md` for scope context and the task-order dependency graph.
4. Read any carry-over section at the bottom of the task file — these are extra ACs from prior audits and must be ticked off as they land.
5. Implement strictly against the task file + issue file + carry-over. No invented scope, no drive-by refactors, no adoption of items from `design_docs/nice_to_have.md`.
6. Write tests for every acceptance criterion (including carry-over) under `tests/`, mirroring the package path. Scaffolding tests may live at `tests/test_*.py`.
7. Run the full gate locally: `uv run pytest`, `uv run lint-imports`, `uv run ruff check`. Fix anything red before handing off to the audit phase.
8. Update `CHANGELOG.md` under `## [Unreleased]` with a `### Added — M<N> Task <NN>: <Title> (YYYY-MM-DD)` entry listing files touched, ACs satisfied, and deviations from spec.
9. Every new module gets a docstring citing the task and its relationship to other modules. Every public class and function gets a docstring. Inline comments only where the *why* is non-obvious.
10. No commits, PRs, or pushes unless the user asks.
11. **Stop and ask** if the spec is ambiguous, an AC is unsatisfiable as written, or implementing would break prior task behaviour. Do not invent direction.

### Audit phase — Auditor mode (CLAUDE.md)

The moment the implement phase finishes, move straight into the audit phase. Forbidden between phases:

- A summary of what the implement phase did.
- A verdict on the gates ("gates pass, so the cycle is clean…").
- A "ready for audit" or self-predicted cycle status.
- Any todo-list update.
- Editing the issue file to flip its status line to `✅ PASS` — that is the audit's output, not a prediction.

Follow Auditor-mode from CLAUDE.md exactly:

1. **Load the full project scope — not just the diff.** Task file, milestone `README.md`, sibling task files and their issue files if present, `pyproject.toml`, `CHANGELOG.md`, `.github/workflows/ci.yml`, every claimed file, the `tests/` tree, **plus `design_docs/architecture.md` and every KDR the task cites**. Opening `architecture.md` is mandatory — skipping it is an incomplete audit.
2. **Design-drift check (before grading ACs).** Cross-reference every change against `architecture.md`:
   - New dependency? It must appear in `architecture.md §6` or be justified by an ADR. Items in `design_docs/nice_to_have.md` are a hard stop — flag HIGH.
   - New module or layer? It must fit the four-layer contract from `architecture.md §3`. Import-linter violations are HIGH.
   - LLM call added? Must route through `TieredNode` paired with a `ValidatorNode` (KDR-004); must not import the `anthropic` SDK or read `ANTHROPIC_API_KEY` (KDR-003).
   - Checkpoint / resume logic? Must delegate to LangGraph's `SqliteSaver` — no hand-rolled checkpoint writes (KDR-009).
   - Retry logic? Must use the three-bucket taxonomy (KDR-006) via `RetryingEdge`; no bespoke try/except retry loops.
   - Observability? Must use `StructuredLogger` only. External backends (Langfuse, OTel, LangSmith) are `nice_to_have.md` items — HIGH if pulled in without trigger.

   Any drift is logged as HIGH with a `Violates KDR-XXX` or `Contradicts architecture.md §X` line. A drift HIGH blocks audit pass.
3. **Run every gate locally — don't trust prior output.** `uv run pytest`, `uv run lint-imports`, `uv run ruff check`, plus any task-specific verification the spec calls out (e.g. `grep -r pydantic_ai` for M1.03, the four-layer contract for M1.12).
4. **Grade each AC individually.** Passing tests ≠ done. Carry-over items count as ACs and are graded individually.
5. **Be extremely critical.** Look for ACs that look met but aren't, silently skipped deliverables, additions beyond spec that add coupling, test gaps, doc drift, secrets shortcuts, `nice_to_have.md` scope creep, silent architecture drift.
6. **Write or update the issue file** at `design_docs/phases/milestone_<N>_<name>/issues/task_<NN>_issue.md` — update in place on re-audit, never create a `_v2`. Structure per CLAUDE.md: status line, design-drift check section, AC grading table, HIGH / MEDIUM / LOW sections, additions-beyond-spec, gate summary, issue log, deferred-to-nice_to_have, propagation status. Every finding (any severity) carries an **Action** / **Recommendation** line with the file to edit, test to add, or task to own follow-up. Every drift finding cites the violated KDR or architecture section.
7. **Forward-deferral propagation.** If a finding is deferred to a future task: log it as `DEFERRED` in this issue file with explicit owner (milestone + task number); append a `## Carry-over from prior audits` entry to the **target** task's spec file with issue ID, severity, concrete "what to implement" line, and back-link; and close the loop with a `## Propagation status` footer. Without propagation, the target Builder can't see the deferral. Findings that map to `nice_to_have.md` are recorded under a `## Deferred to nice_to_have` section with the §N reference — they are **not** forward-deferred to a task.
8. **Do not modify code during the audit** unless the user explicitly asks.

### After the audit phase

Evaluate the four stop conditions, in order, against **what the audit actually wrote in the issue file** — not what the implement phase claimed. If none apply and cycles remain, start the next cycle at the implement phase, targeting only the OPEN issues the audit identified.

---

## Reporting

At the end of each cycle, print a one-line status:

`Cycle N/10 — [CLEAN | OPEN: <count> issues | BLOCKED: <issue-id> | USER INPUT: <issue-id>]`

On final stop, summarise:

- Which stop condition triggered.
- Cycle count reached.
- Any remaining OPEN issues (id + one-line description).
- What the user needs to do next, if anything.

---

## Why the implement → audit ordering is absolute

Implementers self-grade optimistically — "I fixed both issues, so it should be clean" is the exact wrong-but-plausible voice the audit exists to check against. Gates alone aren't an audit (gates are a subset). Re-grading only the lines you just edited isn't an audit (a fix to one AC can regress another). Editing the issue file yourself isn't an audit result. The audit phase's re-load of the full task scope, `architecture.md`, and every cited KDR is the part that catches design drift — and none of that happens unless the audit phase is actually executed, in full, after every implement phase. When in doubt: run the audit phase.
