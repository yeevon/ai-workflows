---
name: dep-audit
description: Run the ai-workflows pre-publish wheel-contents check and dep-manifest change-detection. Use before `uv publish`, when pyproject.toml or uv.lock change, or for wheel-contents audits.
---

# dep-audit

The dep-audit Skill runs the pre-publish wheel-contents check (`uv build` + `unzip -l dist/*.whl`).
It also handles dep-manifest change-detection on any `pyproject.toml` or `uv.lock` diff.
Helper file `runbook.md` carries the long-form assertion lists, error-message catalog, and edge cases.

## When to use

- Before any `uv publish` invocation (wheel contents must be clean — see `runbook.md` §Wheel-contents).
- When `pyproject.toml` or `uv.lock` change in a commit (dep-audit gate per CLAUDE.md non-negotiable).
- When the user asks "what's in the wheel?" or "is this dep new?" or "audit the lockfile bump".

## When NOT to use

- Full threat-model review of a code change: use `security-reviewer` agent instead.
- CVE database lookup for a single dep: use `dependency-auditor` agent's Tier-A check.
- Internal dep updates (e.g. `tiktoken` patch bump with no API change) — that's the regular `dependency-auditor` flow, not this Skill.

## Procedure

1. Wheel-contents check (pre-publish):
   - Run `uv build`.
   - Inspect with `unzip -l dist/*.whl` — see `runbook.md` §Wheel-contents for the full assertion list.
   - **HALT** on any unexpected file: `.env*`, `design_docs/`, `runs/`, `*.sqlite3`, `.claude/`, `htmlcov/`.

2. Dep-manifest change-detection (per-commit):
   - `git diff <pre-task>..HEAD -- pyproject.toml uv.lock` — see `runbook.md` §Dep-detection.
   - On any non-zero diff, the dep-audit gate fires; spawn the `dependency-auditor` agent.

3. Lockfile-diff inspection (on bump):
   - `git diff <pre-task-commit>..HEAD -- uv.lock` — see `runbook.md` §Lockfile-diff for parsing patterns.

## Helper files

- `runbook.md` — full assertion lists, error-message catalog, and edge cases.

## Pointers

- Threat model: `.claude/agents/security-reviewer.md#threat-model`.
- Full dep-audit procedure: `.claude/agents/dependency-auditor.md`.
