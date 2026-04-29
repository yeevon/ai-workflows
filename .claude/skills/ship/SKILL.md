---
name: ship
description: Manual happy-path publish for jmdl-ai-workflows. Host-only — runs build + wheel-contents + real-install smoke + (on operator approval) uv publish. Forbidden in autonomy mode.
allowed-tools: Bash
---

# ship

Manual happy-path publish Skill. Walks build + wheel-contents + real-install smoke gates
and halts on any non-clean result. The actual `uv publish` invocation requires explicit
operator approval; never autonomous.

## ⚠️ Host-only — autonomy-mode forbidden

`/ship` MUST NOT be invoked by `/autopilot`, `/auto-implement`, or any orchestrator agent.
Per `feedback_autonomous_mode_boundaries.md` Rule 1: only the operator runs `uv publish`,
and only on the host (not in the Docker autonomy sandbox). If a sub-agent / orchestrator
attempts to invoke `/ship`, that is a HARD HALT.

The Skill's procedure body refuses to proceed past the wheel-contents check unless an
operator has explicitly typed approval.

## When to use

- Pre-publish for a new release version (operator has bumped `pyproject.toml` `version`
  and updated CHANGELOG `[Unreleased]` → `[<version>]`).
- Smoke-testing a release candidate against a clean install before tagging.

## When NOT to use

- Inside `/autopilot` / `/auto-implement` — those flows must NEVER touch the publish path.
- For dep-audit / wheel-contents inspection without intent to publish — use `dep-audit` Skill.
- For verifying on-disk vs pushed-state — use `/check` instead.

## Inputs

Default targets:

- `pyproject.toml` — read `[project]` `name` + `version` + dependency-set.
- `CHANGELOG.md` — read latest version block (must NOT be `[Unreleased]`).
- `dist/` — built artefacts (created by `uv build`).
- `.env` — must contain `PYPI_TOKEN` (per `reference_pypi_token_dotenv.md`).

Optional flags:

- `--dry-run` — run all gates but skip `uv publish` even on operator approval.
- `--from-clean` — `rm -rf dist/` before `uv build` to avoid stale artefacts.
- `--yes` — pre-approve the publish step (skips the typed-token approval prompt).
  Precedence: `--dry-run` overrides everything; `--yes` skips the approval prompt;
  otherwise typed-token prompt is the default.

## Procedure

1. **Pre-flight (sanity)** — six checks:
   - Verify branch is `main` (not `design_branch` / `workflow_optimization`).
   - Verify working tree is clean (`git status --short` empty).
   - Verify `pyproject.toml` `version` is not a pre-release tag unless intentional.
   - Verify `CHANGELOG.md` latest block is NOT `[Unreleased]` (version was tagged).
   - Verify `.env` exists and contains `PYPI_TOKEN`.
   - Verify `dist/` is empty or `--from-clean` was passed (no stale-wheel risk).
   - HALT on any failure with the failing-check name verbatim (see `runbook.md` §Pre-flight check matrix).

2. **Build + wheel-contents (delegates to dep-audit Skill logic)**:
   - If `--from-clean` was passed, run `rm -rf dist/` first.
   - Run `uv build`.
   - Inspect `unzip -l dist/*.whl` per the `dep-audit` Skill's runbook.
   - HALT on any unexpected file (`.env*`, `design_docs/`, `runs/`, `*.sqlite3`, `.claude/`, etc.).

3. **Real-install smoke**:
   - Run `bash scripts/release_smoke.sh` (canonical procedure — full real-install in fresh venv).
   - Run `uv run pytest tests/release/test_install_smoke.py` (assertion-form gate).
   - HALT on any failure.

4. **Operator-approval prompt**:
   - Surface the report so far + the exact `uv publish` command line that WOULD be run.
   - Wait for explicit operator approval (typed token like "ship it" or `--yes` flag passed).
   - On `--dry-run`, skip this step and exit `DRY-RUN-CLEAN`.
   - If no approval, exit with verdict `OPERATOR-WITHHELD-APPROVAL`.

5. **Publish**:
   - Run `set -a && . ./.env && set +a && uv publish --token "$PYPI_TOKEN"` (per `reference_pypi_token_dotenv.md`).
   - Capture output. HALT on non-zero exit.
   - On success, run `git tag <version> && git push origin <version>`.

6. **Post-publish verification**:
   - Fetch the live PyPI version via `curl -sf https://pypi.org/pypi/jmdl-ai-workflows/json`
     and parse `info.version`. Compare to the just-published version.
   - Note: Skills do not chain — this mirrors the `check` Skill's PyPI-comparison logic
     but does not invoke the Skill (per `feedback_skill_chaining_reuse.md`).
   - If mismatch, retry once after a short sleep before flagging (PyPI propagation lag).

## Outputs

Write `runs/ship/<timestamp>/report.md` with:

- **Pre-flight summary** — six-check pass/fail.
- **Build + wheel-contents summary** — wheel filename, size, file count, denylist matches.
- **Real-install smoke summary** — pytest exit-code + scripts/release_smoke.sh exit-code.
- **Approval status** — APPROVED / WITHHELD / DRY-RUN.
- **Publish status** — PUBLISHED / SKIPPED / FAILED — with exact uv publish exit code if attempted.
- **Post-publish verification** — PyPI version match status.

## Return schema

3-line `verdict: / file: / section:` matching `.claude/commands/_common/agent_return_schema.md`.
Verdict values: `SHIPPED | DRY-RUN-CLEAN | OPERATOR-WITHHELD-APPROVAL | HALTED`.
`file:` = report path. `section:` = `—`.

## Helper files

- `runbook.md` — full pre-flight check matrix; example operator-approval prompts; example HALT
  messages per gate; publish failure modes.
