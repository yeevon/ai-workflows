# sweep runbook

The runbook provides spawn-prompt templates for the three reviewers invoked by the sweep Skill.
It documents the precedence rule for aggregating SHIP / FIX-THEN-SHIP / BLOCK verdicts into a single SWEEP verdict.
It includes one CLEAN and one FIX-THEN-SHIP example consolidated report.

## Spawn-prompt templates

Use these minimal-preload prompts when spawning reviewers in parallel. Each template references
only what the reviewer needs; full agent prompts load from `.claude/agents/<name>.md`.

**sr-dev prompt:**

> You are sr-dev. Review the attached diff for correctness, layer discipline, and KDR compliance.
> Files touched: `<files-list>`. Diff: `<diff-content>`.
> Write your review fragment to `runs/sweep/<timestamp>/sr-dev-review.md`.
> Return 3 lines: `verdict: SHIP | FIX-THEN-SHIP | BLOCK`, `file: <path>`, `section: —`.

**sr-sdet prompt:**

> You are sr-sdet. Review the attached diff for test coverage, edge cases, and AC coverage.
> Files touched: `<files-list>`. Diff: `<diff-content>`.
> Write your review fragment to `runs/sweep/<timestamp>/sr-sdet-review.md`.
> Return 3 lines: `verdict: SHIP | FIX-THEN-SHIP | BLOCK`, `file: <path>`, `section: —`.

**security-reviewer prompt:**

> You are security-reviewer. Review the attached diff for secrets, injection risks, and
> threat-model violations (loopback / single-machine scope; see `.claude/agents/security-reviewer.md#threat-model`).
> Files touched: `<files-list>`. Diff: `<diff-content>`.
> Write your review fragment to `runs/sweep/<timestamp>/security-review.md`.
> Return 3 lines: `verdict: SHIP | FIX-THEN-SHIP | BLOCK`, `file: <path>`, `section: —`.

## Precedence rule

Aggregate the three reviewer verdicts using this strict hierarchy:

| Condition | SWEEP verdict |
|---|---|
| Any reviewer returns BLOCK | SWEEP-BLOCK |
| Any reviewer returns FIX-THEN-SHIP (no BLOCK) | SWEEP-FIX |
| All three return SHIP | SWEEP-CLEAN |

Rule source: mirrors `auto-implement.md` §G2 (terminal-gate aggregation).

## Example reports

### Example 1 — SWEEP-CLEAN

```
runs/sweep/2026-04-29T12-00-00/report.md

## Sweep verdict: SWEEP-CLEAN

Base ref: HEAD. Files: .claude/skills/sweep/SKILL.md, .claude/skills/sweep/runbook.md.

| Reviewer | Verdict | Fragment |
|---|---|---|
| sr-dev | SHIP | runs/sweep/2026-04-29T12-00-00/sr-dev-review.md |
| sr-sdet | SHIP | runs/sweep/2026-04-29T12-00-00/sr-sdet-review.md |
| security-reviewer | SHIP | runs/sweep/2026-04-29T12-00-00/security-review.md |

All three reviewers returned SHIP. No action required.
```

### Example 2 — SWEEP-FIX

```
runs/sweep/2026-04-29T13-00-00/report.md

## Sweep verdict: SWEEP-FIX

Base ref: main. Files: ai_workflows/workflows/loader.py.

| Reviewer | Verdict | Fragment |
|---|---|---|
| sr-dev | SHIP | runs/sweep/2026-04-29T13-00-00/sr-dev-review.md |
| sr-sdet | FIX-THEN-SHIP | runs/sweep/2026-04-29T13-00-00/sr-sdet-review.md |
| security-reviewer | SHIP | runs/sweep/2026-04-29T13-00-00/security-review.md |

sr-sdet returned FIX-THEN-SHIP: missing edge-case test for empty module list.
Address the finding before committing.
```
