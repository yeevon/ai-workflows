# triage runbook

The runbook documents the halt-classification taxonomy and detection patterns for the triage Skill.
It provides option matrices (2-3 ranked next-actions per halt class) so the operator has concrete commands.
It includes worked examples for cycle-limit and user-input-ambiguity halts.

## Halt classifications

Detection signal per halt class:

| Classification | Detection signal |
|---|---|
| Cycle limit | Issue body contains `cycle limit` or `10/10`; last commit prefix is `task-out:` |
| BLOCKER | Issue `**Status:**` line contains `🚧 BLOCKED`; a HIGH finding with no resolution |
| USER INPUT REQUIRED | Issue or auditor return contains `USER INPUT REQUIRED` or `user arbitration` |
| Sub-agent disagreement | Auditor return has `verdict: BLOCK` from one reviewer and `verdict: SHIP` from another |
| Pre-flight failure | No task-out commit; no Builder spawn; `runs/<task>/cycle_1/` directory absent |

Detection regexes (Python-compatible, case-insensitive):

- Cycle limit: `r'cycle\s+limit|10/10\s+cycles'`
- BLOCKER: `r'🚧\s*BLOCKED|HIGH.*requires user action'`
- USER INPUT REQUIRED: `r'USER INPUT REQUIRED|user arbitration'`
- Sub-agent disagreement: `r'verdict:\s*BLOCK'` paired with `r'verdict:\s*SHIP'`
- Pre-flight failure: absence of `runs/<task>/cycle_1/` directory

## Option matrices

Ranked by blast radius (rank 1 = lowest). One table per halt class.

**Cycle limit:**

| Rank | Option | Command |
|---|---|---|
| 1 | Resume with a fresh cycle | `/auto-implement m<M> t<NN>` — Builder re-reads carry-over |
| 2 | Decompose ACs into sub-tasks | Edit spec; re-run `/clean-tasks` |
| 3 | Manual fix | Edit source; run gate suite; commit |

**BLOCKER:**

| Rank | Option | Command |
|---|---|---|
| 1 | Resolve blocker | Address HIGH finding; clear `🚧 BLOCKED`; re-run `/auto-implement` |
| 2 | Downgrade finding | Edit issue if mis-classified HIGH; re-run auditor |
| 3 | Skip task | Mark `🚫 Skipped` in README; advance queue |

**USER INPUT REQUIRED:**

| Rank | Option | Command |
|---|---|---|
| 1 | Answer the question | Provide decision; re-run `/auto-implement` with explicit instruction |
| 2 | Update spec | Edit task spec to remove ambiguity; re-run `/auto-implement` |
| 3 | Accept recommendation | Endorse auditor default; re-run |

**Sub-agent disagreement:**

| Rank | Option | Command |
|---|---|---|
| 1 | Lens-specialisation bypass | Different lenses (sr-dev vs sr-sdet) = Builder re-loop, not HARD HALT |
| 2 | User arbitration | Read both verdicts; instruct Builder with higher-priority concern |
| 3 | Re-scope | Edit spec to remove scope ambiguity; re-run from cycle 1 |

**Pre-flight failure:**

| Rank | Option | Command |
|---|---|---|
| 1 | Check branch + sandbox | `git rev-parse --abbrev-ref HEAD` — confirm design_branch |
| 2 | Clean working tree | Commit or stash untracked files; re-run `/auto-implement` |
| 3 | Confirm CLI available | `which ollama`; `claude --version` |

## Example reports

### Example 1 — Cycle limit

```
runs/triage/2026-04-29T10-00-00/report.md

## Halt signature

Command: /auto-implement. Task: M21 T13. Cycle: 10/10.
Classification: Cycle limit — Builder reached 10 cycles without satisfying all ACs.

## Run-state inventory

spec:  design_docs/.../task_13_triage_command.md
issue: design_docs/.../issues/task_13_issue.md
runs:  runs/auto-implement-m21t13-iter10-shipped.md

## Next-action options

1. Resume: /auto-implement m21 t13 — Builder re-reads carry-over.
2. Decompose: split remaining ACs into sub-tasks; re-run /clean-tasks.
3. Manual: edit files directly; run gate suite; commit.
```

### Example 2 — User-input ambiguity

```
runs/triage/2026-04-29T11-00-00/report.md

## Halt signature

Command: /autopilot. Task: M21 T17. Cycle: 3/10.
Classification: USER INPUT REQUIRED — auditor surfaced ambiguous AC
on concurrency cap (3 vs 4 worktrees); no authoritative answer in spec.

## Run-state inventory

spec:  design_docs/.../task_17_spec_format_extension.md
issue: design_docs/.../issues/task_17_issue.md

## Next-action options

1. Answer: reply with explicit concurrency cap; re-run /auto-implement m21 t17.
2. Update spec: add concurrency cap to task_17 spec; re-run from cycle 1.
3. Accept default: auditor recommended cap=3; endorse and re-run.
```
