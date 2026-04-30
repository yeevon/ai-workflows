# Task 04 — Milestone Close-out

**Status:** ✅ Done (2026-04-30).
**Grounding:** [milestone README](README.md) · [CLAUDE.md](../../../CLAUDE.md) close-out conventions · [M12 T07](../milestone_12_audit_cascade/task_07_milestone_closeout.md) (pattern mirrored) · [design_docs/roadmap.md](../../roadmap.md) · [CHANGELOG.md](../../../CHANGELOG.md) · [pyproject.toml](../../../pyproject.toml) (version bump to 0.4.0).

## What to Build

Close M17. Confirm every exit criterion from the [milestone README](README.md) landed across T01–T03. Bump version from `0.3.1` to `0.4.0` in `pyproject.toml`. Promote the accumulated `[Unreleased]` CHANGELOG entries into a dated `## [0.4.0]` section. Flip M17 complete in `design_docs/roadmap.md`. Update root `README.md`. No production logic change — any finding becomes a forward-deferred carry-over or a `nice_to_have.md` entry, never a drive-by fix.

Mirrors [M12 Task 07](../milestone_12_audit_cascade/task_07_milestone_closeout.md) so reviewers get identical close-out muscle memory.

## Deliverables

### Version bump

Bump `__version__` from `"0.3.1"` to `"0.4.0"` in `ai_workflows/__init__.py:33`. This is the single source of truth — `pyproject.toml` declares `dynamic = ["version"]` and reads from there. No `pyproject.toml` version line to change directly.

### [CHANGELOG.md](../../../CHANGELOG.md)

Promote the accumulated `[Unreleased]` M17 entries into a dated section `## [0.4.0] - <date>`. Keep the top-of-file `[Unreleased]` section as a fresh empty skeleton. The dated section summarises all four tasks (T01–T04) and the milestone's net delivery:

- T01 — `scaffold_workflow` StateGraph: input validation, synthesis (`TieredNode`/Opus), AST validator (`ValidatorNode`), `HumanGate` preview, atomic write-to-disk. `aiw run-scaffold` CLI alias. KDR-003/004/006/008/009/013/014 compliant.
- T02 — Prompt template iterated; live-mode smoke (`tests/release/test_scaffold_live_smoke.py`); CS300 dogfood documented. Carry-over items LOW-2/LOW-3/ADV-1/ADV-2 closed.
- T03 — ADR-0010 (user-owned generated code); skill-install §Generating-your-own-workflow; `docs/writing-a-workflow.md` §Scaffolding.
- T04 — Milestone close-out; version bump to 0.4.0.

### Milestone [README.md](README.md)

- Flip **Status** from `📝 Planned` to `✅ Complete (<date>)`.
- Confirm all `[ ]` exit criteria are `[x]` or explicitly noted as deferred to `nice_to_have.md`.
- Flip task row 04 in §Task order from `📝 Planned` to `✅ Done`.
- Append an **Outcome** section summarising all four tasks (same format as M12 T07 §Outcome).

### [design_docs/roadmap.md](../../roadmap.md)

Flip the M17 row `Status` from `📝 planned` to `✅ complete (<date>)`.

Also fix two stale references on the M17 narrative line (line 58 at spec-generation time):
- Replace `[ADR-0008](adr/0008_user_owned_generated_code.md)` (twice) with `[ADR-0010](adr/0010_user_owned_generated_code.md)` — ADR-0008 is occupied by the declarative authoring surface; ADR-0010 is M17's actual slot.
- Replace `AIW_WORKFLOWS_PATH` with `AIW_EXTRA_WORKFLOW_MODULES` — M16 shipped with the env-var renamed (verified at `ai_workflows/workflows/loader.py:46`).

### Root [README.md](../../../README.md)

- Flip the M17 row in the milestone status table from planned/in-progress to `Complete (<date>)`.
- Update any narrative paragraph referencing M17 as planned or in progress.

## Acceptance Criteria

- **AC-1 — Version bumped.** `ai_workflows/__init__.py` `__version__ = "0.4.0"` (single source of truth; `pyproject.toml` reads it dynamically). Also fix two stale roadmap.md references: ADR-0008 → ADR-0010, `AIW_WORKFLOWS_PATH` → `AIW_EXTRA_WORKFLOW_MODULES`.
- **AC-2 — CHANGELOG promoted.** `## [0.4.0] - <date>` section exists with T01–T04 summary; `[Unreleased]` is a fresh empty skeleton.
- **AC-3 — roadmap.md flipped.** M17 row shows `✅ complete`.
- **AC-4 — Milestone README complete.** Status ✅ Complete; all exit criteria ✅ (or explicitly deferred); §Outcome section present summarising all four tasks.
- **AC-5 — Root README updated.** M17 row in milestone table shows Complete.
- **AC-6 — Gates green.** `uv run pytest` + `uv run lint-imports` + `uv run ruff check` all pass. (No logic changes from T04 itself — version bump only. Gates confirm no regressions.)
- **AC-7 — Dependency audit passed.** `pyproject.toml` version bump triggers the dependency-auditor gate. No new dependencies introduced at T04. Wheel contents clean: `uv build` + `unzip -l dist/*.whl` shows only `ai_workflows/` + `LICENSE` + `README.md` + `CHANGELOG.md`. No `.env*`, `design_docs/`, `runs/`, `*.sqlite3` in wheel.

## Dependencies

- T01 ✅, T02 ✅, T03 ✅ (all M17 tasks complete before close-out).

## Out of scope

- Prompt changes. T02.
- New production logic or new source modules. (Close-out is doc + version bump only.)
- KDR additions. (ADR-0010 landed at T03; no new KDRs at close-out.)
- `uv publish`. The publish step is a manual step outside the autonomous loop per the autonomous-mode boundary (CLAUDE.md §Non-negotiables). T04 prepares the release artefact; the human operator runs `uv publish`.

## Carry-over from task analysis

- [x] **TA-LOW-02 — Dependency-auditor terminal-gate framing** (severity: LOW, source: task_analysis.md round 1)
      AC-7's dependency-auditor gate runs as a parallel terminal-gate reviewer alongside sr-dev / sr-sdet (autopilot boundary, locked 2026-04-27). No deps change at T04, so the audit is short — but it must run.
      **Recommendation:** Auditor and orchestrator will trigger dep-auditor automatically per CLAUDE.md; this carry-over is a reminder that it is not optional even for a version-bump-only commit.
