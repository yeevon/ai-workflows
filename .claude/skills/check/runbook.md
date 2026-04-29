# check runbook

The runbook documents the state-classification matrix for the check Skill.
It maps each of the six states to a concrete next-action command.
It also covers git invocations with example outputs and PyPI version comparison.

## Classification matrix

| State | Condition | Next action |
|---|---|---|
| CLEAN-AND-SYNCED | empty `git status`, local-ahead=0, remote-ahead=0 | No action needed. |
| AHEAD-NEEDS-PUSH | empty `git status`, local-ahead>0, remote-ahead=0 | `git push origin <branch>` |
| BEHIND-NEEDS-PULL | empty `git status`, local-ahead=0, remote-ahead>0 | `git pull --ff-only` |
| DIVERGED | local-ahead>0 AND remote-ahead>0 | Inspect diff; rebase or merge with care; `git log --oneline @{u}..HEAD` |
| DIRTY-WORKING-TREE | `git status --short` non-empty | Commit or stash changes first; re-run `/check`. |
| PUBLISH-DRIFT | pyproject version != PyPI latest (--pypi flag only) | Run `/ship` to publish; or bump `pyproject.toml` version. |

## Git invocations

Detection sequence — run each command in order:

```bash
git rev-parse --abbrev-ref HEAD
```

Example output: `workflow_optimization`

```bash
git rev-parse --abbrev-ref --symbolic-full-name @{u}
```

Example output: `origin/workflow_optimization`
If this exits non-zero: no upstream — classify `LOCAL-ONLY`, skip remote checks.

```bash
git status --short
```

Empty output = clean working tree. Any output = `DIRTY-WORKING-TREE`.

```bash
git log --oneline @{u}..HEAD
```

Empty = not ahead. One or more lines = local-ahead count. Example:

```
abc1234 M21 Task 14: /check Skill
```

```bash
git log --oneline HEAD..@{u}
```

Empty = not behind. One or more lines = remote-ahead count.

```bash
git diff @{u}..HEAD --stat
```

Use for the per-surface inventory section of the report.

## PyPI version compare

Invoke with `--pypi <package>` flag:

```bash
curl -sf https://pypi.org/pypi/<package>/json
```

Parse `.info.version` from the JSON response. Compare to local:

```bash
grep '^version' pyproject.toml
```

Example JSON shape (relevant fields only):

```json
{ "info": { "version": "0.3.1" } }
```

If local `pyproject.toml` version == PyPI `info.version`: no PUBLISH-DRIFT.
If local > PyPI: unreleased changes exist; classify `PUBLISH-DRIFT` if operator expected them to be live.
If local < PyPI: unexpected state — note in report for operator inspection.
