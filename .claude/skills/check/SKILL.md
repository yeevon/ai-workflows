---
name: check
description: Verify on-disk vs local-branch vs remote-branch (and optionally PyPI) state convergence. Use after autopilot/auto-implement runs to confirm pushed state matches local.
allowed-tools: Bash
---

# check

On-disk vs pushed-state verifier. Reads the current branch + remote tracking ref +
(optionally) PyPI latest version, and reports drift across the three surfaces.

Note: `allowed-tools: Bash` only — T14's procedure is fully Bash-native (git, curl,
cat, grep inside Bash subprocess calls). No Read/Grep tool round-trips needed.

## When to use

- After /autopilot or /auto-implement runs to confirm local + remote agree.
- Before declaring a release ready (compare local CHANGELOG `[Unreleased]` vs PyPI latest version).
- When returning to a paused session and unsure whether prior commits pushed.

## When NOT to use

- For diagnosing a halt — use `/triage` instead.
- For test-failure investigation — use `uv run pytest` directly.
- For green-path autopilot runs that just landed — `/check` is for verification after the fact, not part of the autopilot procedure.

## Inputs

Default targets (auto-detected from working directory):

- Current branch: `git rev-parse --abbrev-ref HEAD`.
- Remote tracking ref: `git rev-parse --abbrev-ref --symbolic-full-name @{u}` (skip if no upstream).
- Working-tree state: `git status --short`.
- Local-ahead commits: `git log --oneline @{u}..HEAD` (if upstream exists).
- Remote-ahead commits: `git log --oneline HEAD..@{u}` (if upstream exists).
- CHANGELOG.md `[Unreleased]` block (if present).

Optional flags:

- `--pypi <package>` — also fetch latest PyPI version via `curl https://pypi.org/pypi/<package>/json` and compare to local `pyproject.toml` version + the `[Unreleased]` block.
- `--branch <name>` — override branch detection.

## Procedure

1. Detect current branch + upstream. If no upstream is set, classify as `LOCAL-ONLY` and skip remote comparison.
2. Run the six default git inspections above. Categorize each non-empty output.
3. (Optional) If `--pypi <package>` passed, fetch PyPI JSON via `curl`. Compare `info.version` to local `pyproject.toml`'s `version`. Note discrepancy in the report.
4. Classify the overall state using the six categories in `runbook.md` §Classification matrix:
   - **CLEAN-AND-SYNCED** — empty `git status`, zero local-ahead, zero remote-ahead.
   - **AHEAD-NEEDS-PUSH** — empty `git status`, local-ahead > 0, remote-ahead = 0.
   - **BEHIND-NEEDS-PULL** — empty `git status`, local-ahead = 0, remote-ahead > 0.
   - **DIVERGED** — both local-ahead > 0 AND remote-ahead > 0.
   - **DIRTY-WORKING-TREE** — `git status --short` non-empty.
   - **PUBLISH-DRIFT** — local pyproject version != PyPI latest (only when `--pypi` is passed).
5. Produce the report (see Outputs).

## Outputs

Write `runs/check/<timestamp>/report.md` with:

- **State classification** (one of the six categories above; one-paragraph summary).
- **Per-surface inventory** (working tree, local branch, remote branch, PyPI if applicable).
- **Next-action recommendation** (one ranked next step the operator should take, or "no action — clean").

## Return schema

3-line `verdict: / file: / section:` matching `.claude/commands/_common/agent_return_schema.md`.
Verdict values: `CLEAN | DRIFT | LOCAL-ONLY`. `file:` is the report path. `section:` is `—`.

## Helper files

- `runbook.md` — state-classification matrix (the six classifications mapped to next-action commands); PyPI-comparison example outputs.
