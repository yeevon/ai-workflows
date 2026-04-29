# ship runbook

The runbook documents the pre-flight check matrix, operator-approval prompts, and publish
failure modes for the ship Skill. Host-only — publish path requires explicit operator approval.
Skills do not chain; all gate logic is Bash-native within this Skill.

## Pre-flight check matrix

Six checks run in order. HALT immediately on the first failure — report the check name verbatim.

| Check | Command | Failure condition | HALT message |
|---|---|---|---|
| Branch is main | `git rev-parse --abbrev-ref HEAD` | Output != `main` | `HALT: branch-not-main (got: <branch>)` |
| Clean working tree | `git status --short` | Non-empty output | `HALT: dirty-working-tree` |
| Version not pre-release | `grep '^__version__' ai_workflows/__init__.py` | Version string contains `dev`, `a`, `b`, `rc` | `HALT: pre-release-version (got: <version>)` |
| CHANGELOG not Unreleased | Head of CHANGELOG.md | Latest version block is `[Unreleased]` | `HALT: changelog-unreleased` |
| .env has PYPI_TOKEN | `grep PYPI_TOKEN .env` | Key absent or file missing | `HALT: missing-pypi-token` |
| dist/ is empty or --from-clean | `ls dist/ 2>/dev/null` | Non-empty and --from-clean not passed | `HALT: stale-dist-artefacts` |

## Build + wheel-contents

Delegate wheel-contents inspection to the dep-audit Skill's runbook logic. Denylist:

```
.env*
design_docs/
runs/
*.sqlite3
.claude/
__pycache__/
```

Any match → `HALT: wheel-denylist-hit (<filename>)`.

Expected wheel contents (must ALL be present):

```
ai_workflows/
LICENSE
README.md
CHANGELOG.md
```

## Real-install smoke

Run in order; HALT on first non-zero exit:

```bash
bash scripts/release_smoke.sh
```

Then:

```bash
uv run pytest tests/release/test_install_smoke.py -q
```

HALT message on failure: `HALT: real-install-smoke-failed (exit <code>)`.

## Operator-approval prompts

Surface the following block before asking for approval:

```
--- /ship approval gate ---
Pre-flight: PASS
Build + wheel-contents: PASS
Real-install smoke: PASS

Command that WILL run on approval:
  set -a && . ./.env && set +a && uv publish --token "$PYPI_TOKEN"

Type "ship it" to approve, or any other input to abort.
---------------------------
```

Accepted approval tokens (case-insensitive): `ship it`, `yes`, `y`, `approve`.

On `--yes` flag: skip the prompt entirely; log `approval: pre-approved via --yes flag`.

On `--dry-run`: skip the prompt and log `approval: dry-run — skipped`.

## Publish failure modes

| Mode | Detection | Recommended action |
|---|---|---|
| Auth failure | `uv publish` exits non-zero; stderr contains `401` or `403` | Verify `PYPI_TOKEN` in `.env`; re-run `/ship` |
| Network failure | `uv publish` exits non-zero; stderr contains `timeout` or `connection refused` | Check network; retry `/ship` |
| Version already exists | `uv publish` exits non-zero; stderr contains `already exists` | Bump version in `pyproject.toml`; update CHANGELOG; re-run `/ship` |
| Tag push failure | `git push origin <tag>` exits non-zero | Check remote permissions; push tag manually |
