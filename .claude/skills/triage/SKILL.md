---
name: triage
description: Post-halt diagnosis for autopilot/auto-implement runs. Use after a HALT/BLOCKED/cycle-limit return when you need a structured "what failed / why / next move" report.
allowed-tools: Read, Bash, Grep
---

# triage

Post-halt diagnosis for autonomy-mode runs. Loads the latest run-state surfaces
(issue file, iter-shipped, cycle summaries), parses the halt signal, and produces
a structured report so the operator can decide retry / fix / skip.

## When to use

- After any /autopilot or /auto-implement run that returned HALT, BLOCKED, USER INPUT REQUIRED, or "cycle limit reached".
- When the git working tree is dirty after an autonomy run and you need to know what is safe to commit vs. what was mid-cycle.
- When the operator returns to a paused autonomy session and needs to resume from a clean state.

## When NOT to use

- For routine sr-dev / sr-sdet review of a clean diff — use `/sweep` (T16) instead.
- For pre-publish wheel-contents inspection — use the `dep-audit` Skill.
- For green-path autopilot runs (no halt) — `/triage` is for halts only.

## Inputs

Default targets (auto-detected from working directory):

- Latest `design_docs/phases/milestone_*/issues/task_*_issue.md` by mtime.
- Latest `runs/autopilot-*-iter*-shipped.md` by mtime.
- Latest `runs/<task>/cycle_*/summary.md` by mtime (if mid-task).
- `git log --oneline -5` for recent-commit context.
- `git status --short` and `git diff --stat` for working-tree state.

Optional override: pass `--task <task-shorthand>` to scope diagnosis to one specific
task's issue file and cycle summaries.

## Procedure

1. Read the latest issue file in full. Parse the `**Status:**` line — `✅ PASS` means
   no halt; `🚧 BLOCKED` or `OPEN` means a halt is recorded.
2. Read the latest `iter-shipped.md` (autopilot-level) and the latest
   `cycle_<N>/summary.md` (task-level if present). Note which is more recent.
3. Read `git log --oneline -5`. Note whether the last commit is task-out
   (`task-out:` prefix) vs task-close (`Task <NN>:` prefix). A task-out with a
   dirty tree indicates a mid-cycle halt; a task-close with a clean tree indicates
   a green run.
4. Read `git status --short` and `git diff --stat`. Map every modified or untracked
   file to one of: task spec / issue file / runs artefact / source code.
5. Classify the halt (see `runbook.md` §Halt classifications for detection regexes):
   - **Cycle limit (10/10)** — auto-implement reached cycle limit without convergence.
   - **BLOCKER** — issue file has a HIGH 🚧 BLOCKED finding requiring user action.
   - **USER INPUT REQUIRED** — auditor surfaced an ambiguous decision needing user arbitration.
   - **Sub-agent disagreement** — terminal-gate split (one BLOCK, others SHIP).
   - **Pre-flight failure** — sandbox / branch / clean-tree check failed before agents spawned.
6. For each halt category, name 2-3 next-action options the operator can take.
   Reference `runbook.md` §Option matrices for the full option table per classification.

## Outputs

Write `runs/triage/<timestamp>/report.md` with:

- **Halt signature** — one paragraph: which command, which task, which cycle, which classified halt.
- **Run-state inventory** — file list grouped by category (spec / issue / runs / source).
- **Next-action options** — 2-3 ranked options for the operator; each names the command and concrete consequence.

## Return schema

3-line `verdict: / file: / section:` matching `.claude/commands/_common/agent_return_schema.md`.
Verdict values: `DIAGNOSED | INCONCLUSIVE`. `file:` is the report path. `section:` is `—`.

## Helper files

- `runbook.md` — option matrices keyed by halt classification; example reports for each category.
