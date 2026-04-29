---
name: sweep
description: Run sr-dev + sr-sdet + security-reviewer against the working-tree diff. Use for ad-hoc review of a branch / fix / exploratory diff outside the auto-implement terminal gate.
allowed-tools: Bash
---

# sweep

Ad-hoc reviewer Skill: spawns sr-dev + sr-sdet + security-reviewer against the current
`git diff` and produces a consolidated three-fragment report. Operator-invoked only —
not part of the /auto-implement terminal gate (which already runs the trio).

## When to use

- For ad-hoc review of a working-tree diff that hasn't shipped through /auto-implement.
- For a fix-in-progress when you want reviewer feedback before committing.
- For an exploratory branch that's outside the autonomy-mode flow but needs the same lens-set.

## When NOT to use

- During /auto-implement runs — the terminal gate already runs the three reviewers; /sweep duplicates that.
- For post-halt diagnosis — use /triage instead.
- For pre-publish wheel inspection — use dep-audit Skill.

## Inputs

Default: `git diff HEAD` (working tree vs current commit). Optional flags:

- `--base <ref>` — diff against a specific base ref (e.g. `--base main` for branch-vs-main).
- `--files <list>` — restrict to a comma-separated file list.

## Procedure

1. Compute the diff via `git diff <base> [-- <files>]`. Capture stat + name-only output.
   Skip if diff is empty (verdict: NO-DIFF).
2. Aggregate the files-touched list (passed to all three reviewers).
3. Spawn sr-dev + sr-sdet + security-reviewer in parallel via three Task tool calls in one
   orchestrator turn (per `_common/parallel_spawn_pattern.md`). Each reviewer writes its
   fragment to `runs/sweep/<timestamp>/<reviewer>-review.md`.
4. After all three complete, parse the 3-line return-schema verdicts.
5. Apply the precedence rule from `auto-implement.md` §G2 (see `runbook.md` §Precedence rule):
   any BLOCK → SWEEP-BLOCK; any FIX-THEN-SHIP (no BLOCK) → SWEEP-FIX; all SHIP → SWEEP-CLEAN.

## Outputs

Write `runs/sweep/<timestamp>/report.md` (consolidated) plus per-reviewer fragments:

- **Consolidated report** — overall verdict + per-reviewer summary line + pointer to each fragment.
- **Per-reviewer fragments** — full review content as written by the agent.

## Return schema

3-line `verdict: / file: / section:` matching `.claude/commands/_common/agent_return_schema.md`.
Verdict values: `SWEEP-CLEAN | SWEEP-FIX | SWEEP-BLOCK | NO-DIFF`. `file:` = consolidated
report path. `section:` = `—`.

## Helper files

- `runbook.md` — spawn-prompt templates per reviewer (sr-dev / sr-sdet / security-reviewer);
  precedence-rule reminder; example consolidated reports.
