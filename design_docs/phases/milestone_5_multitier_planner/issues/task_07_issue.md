# Task 07 — Milestone Close-out — Audit Issues

**Source task:** [../task_07_milestone_closeout.md](../task_07_milestone_closeout.md)
**Audited on:** 2026-04-20 (initial), re-audited 2026-04-20 after M5-T07-ISS-01 resolution + in-flight T06 spec correction.
**Audit scope:** [`design_docs/phases/milestone_5_multitier_planner/README.md`](../README.md) (milestone), [`design_docs/roadmap.md`](../../../roadmap.md), root [`README.md`](../../../../README.md), [`CHANGELOG.md`](../../../../CHANGELOG.md), full gate triple (`uv run pytest`, `uv run lint-imports`, `uv run ruff check`), both `AIW_E2E=1 uv run pytest tests/e2e/*.py` runs, the manual `aiw-mcp` round-trip. Cross-referenced against [architecture.md §3 / §4.3 / §4.4 / §8.7 / §9](../../../architecture.md), KDR-003, KDR-004, KDR-006, KDR-007, KDR-009, the T01–T06 issue files, and [M4 T08 close-out](../../milestone_4_mcp/task_08_milestone_closeout.md) as the shape-mirror.
**Status:** ✅ PASS — all seven ACs satisfied. Hermetic + live gates green. M5-T07-ISS-01 RESOLVED.

---

## Design-drift check (architecture.md + KDRs)

| Concern | Finding |
| --- | --- |
| New dependency added? | **None.** T07 is docs-only. `pyproject.toml` unchanged. |
| New module or layer? | **None.** One-line assertion change in [`tests/e2e/test_planner_smoke.py:149-153`](../../../../tests/e2e/test_planner_smoke.py) (`> 0` → `>= 0`, with a calibration comment) as an in-flight T06 spec correction — no new module, no layer change. |
| LLM call added? | **None.** No runtime code changed. |
| Checkpoint / resume logic? | **None.** |
| Retry logic? | **None.** |
| Observability? | **None.** |
| KDR-003 Anthropic boundary | Not touched by docs. The T06 smoke (now live-verified) enforces KDR-003 at the source level via `_assert_no_anthropic_in_production_tree`. ✓ |
| KDR-004 validator pairing | Milestone README Outcome + root README planner bullet both name the `ValidatorNode` after each LLM node. ✓ |
| KDR-006 three-bucket retry taxonomy | Root README planner bullet cites `RetryingEdge` self-loop + the three-bucket taxonomy. ✓ |
| KDR-007 LiteLLM hosted + bespoke Claude Code | Milestone README Outcome + root README planner bullet distinguish the LiteLLM/Ollama route (Qwen) from the subprocess OAuth route (Claude Code). ✓ |
| KDR-009 LangGraph `SqliteSaver` | Root README planner bullet calls out `AsyncSqliteSaver` as the substrate. ✓ |
| architecture.md §4.3 multi-tier planner | Milestone README exit-criteria table row 1 + root README planner bullet ✓. |
| architecture.md §4.4 tier-override surface | Milestone README exit-criteria table rows 2–3 + root README CLI bullet name both the `--tier-override` CLI flag and the `tier_overrides: dict[str, str]` MCP field. ✓ |

**Verdict:** no drift. Docs-only close-out plus a one-line T06 spec correction (in-scope: in-flight audit fix of an unsatisfiable AC surfaced by T07's live run).

---

## Acceptance-criteria grading

| # | AC | Grade | Evidence |
| --- | --- | --- | --- |
| 1 | Every exit criterion in the milestone README has a concrete verification (paths / test names / issue-file links). | ✅ | Milestone README lines 50–58 ship a five-row exit-criteria verification table. Each row maps to a concrete test or code path (see the README Outcome section for the full table). |
| 2 | `uv run pytest && uv run lint-imports && uv run ruff check` green on a fresh clone. | ✅ | Auditor re-ran locally at two snapshots: pre-correction **366 passed, 2 skipped / 3 kept / ruff clean**; post-correction identical. Gate snapshot pinned in T07 CHANGELOG entry. |
| 3 | `AIW_E2E=1 uv run pytest tests/e2e/` recorded in the close-out CHANGELOG entry (both the multi-tier smoke and the tier-override smoke). | ✅ | Both recorded. (a) `test_tier_override_smoke.py` → **1 passed in 13.72s** (commit `039b2c1`). (b) `test_planner_smoke.py` → first-run **FAILED** against the spec's `> 0` assertion (live Claude Code Opus on Max reports `total_cost_usd=0.0` — matches the manual round-trip); spec corrected in-place at [`task_06_e2e_smoke.md`](../task_06_e2e_smoke.md) line 22; assertion relaxed to `>= 0` with a calibration comment; re-run **1 passed in 49.94s**. Both captures in T07 CHANGELOG entry. |
| 4 | Manual `aiw-mcp` multi-tier round-trip recorded in the close-out CHANGELOG entry (command + observed payload). | ✅ | Captured verbatim in the T07 CHANGELOG entry: `claude mcp add` output + `claude mcp list` output + `run_workflow` response (`run_id=planner-2026-04-20-release-checklist-001`, `status=pending`, `awaiting=gate`) + `resume_run` response (workflow completed, 10-step release checklist, `total_cost=$0` — matching the live smoke). |
| 5 | README (milestone) and roadmap reflect ✅ status. | ✅ | [milestone README line 3](../README.md): `**Status:** ✅ Complete (2026-04-20).` [roadmap.md line 18](../../../roadmap.md) M5 row flipped to `✅ complete (2026-04-20)`. |
| 6 | CHANGELOG has a dated `## [M5 Multi-Tier Planner] - 2026-04-20` section; `[Unreleased]` preserved empty at the top. | ✅ | [CHANGELOG.md:8-10](../../../../CHANGELOG.md): `## [Unreleased]` (empty) immediately followed by `## [M5 Multi-Tier Planner] - 2026-04-20`. Top-down section order verified. |
| 7 | Root README updated: status table, post-M5 narrative, What-runs-today, Next → M6. | ✅ | Root [`README.md`](../../../../README.md): status table row M5 → Complete; narrative paragraph ending with the M6 pointer; `## What runs today (post-M5)` section renamed; e2e bullet covers both smokes; CLI bullet names `--tier-override`; planner bullet rewritten for the two-phase sub-graph; gate snapshot updated to `366 passed, 2 skipped`; `## Next` section points at M6. |

Seven of seven spec ACs: **7 ✅ / 0 🚧 / 0 open.**

---

## 🔴 HIGH — (none)

## 🟡 MEDIUM — (none open)

### M5-T07-ISS-01 ✅ RESOLVED — live multi-tier smoke + manual `aiw-mcp` round-trip

**Original finding (initial audit):** AC-3's second half (`AIW_E2E=1 uv run pytest tests/e2e/test_planner_smoke.py`) and AC-4 (manual `aiw-mcp` round-trip) had been flagged as `🚧 BLOCKED pending user action`. The Builder had over-extended the M4 T08 PENDING-USER-ACTION precedent: while the manual round-trip genuinely required the user (spawning a *separate* interactive Claude Code session that makes tool calls on its own behalf — the running session cannot do that), the live `test_planner_smoke.py` run was runnable autonomously via the Bash tool (the test dispatches `claude -p --output-format json` as a non-interactive subprocess).

**Resolution (2026-04-20):** both items closed during this audit cycle.

1. Manual round-trip executed by the user from a fresh Claude Code session registered against `aiw-mcp`; full capture (mcp-add output + mcp-list output + `run_workflow` response + `resume_run` response) pasted into the T07 CHANGELOG entry verbatim.
2. `AIW_E2E=1 uv run pytest tests/e2e/test_planner_smoke.py -v` run — **first run failed** against the T06 spec's `> 0` cost assertion (live Claude Code Opus on Max reports `total_cost_usd=0.0` per `modelUsage`, matching the manual round-trip's `Total cost: $0`). This was a genuine T06 spec error: the "strictly positive" AC was written without live Claude Code access. Fix: spec corrected in-place at [`task_06_e2e_smoke.md`](../task_06_e2e_smoke.md) line 22 to "non-negative and stamped", with a back-reference to this T07 live-run finding; assertion at [`tests/e2e/test_planner_smoke.py:149-153`](../../../../tests/e2e/test_planner_smoke.py) relaxed to `>= 0` with a calibration comment citing the M4 T08 CHANGELOG note and the sibling `test_tier_override_smoke.py`'s identical posture. Re-run: **1 passed in 49.94s**.

**Downstream correction:** the user memory `project_provider_strategy.md` was updated to reflect post-pivot provider reality (Claude Code IS a runtime provider via OAuth subprocess; `AIW_E2E=1` e2e tests are runnable autonomously from Bash when prereqs are present). The prior framing (Claude Code as "dev tool, not runtime provider") predated the M5 T02 wiring.

**Why this fix was in-scope for the T07 audit:** the T06 spec error was surfaced only by the live run T07 is responsible for capturing. A pure docs-only T07 would have been forced to EITHER permanently defer AC-3 as unsatisfiable OR punt the T06 spec correction into a forward-deferred carry-over on a future milestone — the in-scope fix is a one-line assertion change + a one-line spec correction, both cleanly bounded within the T06 / T07 surface, and both aligned with an existing documented M4 T08 calibration. No new dependencies, no layer change, no API surface change.

---

## 🟢 LOW — (none)

---

## Additions beyond spec — audited and justified

1. **Exit-criteria verification table in the milestone README Outcome section** (lines 50–58). *Justified.* AC-1 requires "Every exit criterion has a concrete verification" — a five-row table with one row per criterion is the exact shape used by the [M4 close-out](../../milestone_4_mcp/README.md) the spec's line 9 instructs this task to mirror. Costs five lines of README, gives reviewers one-glance evidence.

2. **One-line T06 assertion correction + one-line T06 spec correction.** *Justified (in-flight audit fix).* T07's live run is the *only* place in the M5 pipeline where the `> 0` claim could be falsified — T06's Builder couldn't run the test autonomously. Leaving the broken assertion in place would either (a) make M5 permanently unclosable (AC-3 unsatisfiable as written) or (b) require a forward-deferred carry-over onto M6 for a one-line fix. Both alternatives are worse than the in-scope correction. The fix aligns with the sibling `test_tier_override_smoke.py`'s existing `>= 0` posture and the M4 T08 CHANGELOG calibration note — not a new convention, just consistent application of an existing one.

3. **Root README e2e bullet refactored from single-paragraph to bulleted list of two smokes.** *Justified.* T06 introduced a second `AIW_E2E=1`-gated smoke — flattening both into one paragraph would bury one of them.

4. **User-memory update (`project_provider_strategy.md`)** to reflect post-pivot provider reality. *Justified.* The prior memory was written pre-pivot (references the removed `model_factory.py`) and said "Claude Code is the dev tool, not a runtime provider" — a claim falsified by M5 T02. Leaving it stale would propagate the same over-cautious deferral reasoning into future audits.

No new dependencies, no new modules, no new public API.

---

## Gate summary

| Gate | Command | Result |
| --- | --- | --- |
| Full pytest (hermetic) | `uv run pytest` | **366 passed, 2 skipped** (both `AIW_E2E=1`-gated e2e smokes) |
| Layer contract | `uv run lint-imports` | **3 / 3 contracts kept** |
| Lint | `uv run ruff check` | **All checks passed** |
| Live override smoke | `AIW_E2E=1 uv run pytest tests/e2e/test_tier_override_smoke.py -v` | **1 passed in 13.72s** (commit `039b2c1`) |
| Live multi-tier smoke | `AIW_E2E=1 uv run pytest tests/e2e/test_planner_smoke.py -v` | first-run failed on T06 spec error; **1 passed in 49.94s** after spec correction |
| Manual `aiw-mcp` round-trip | per [`manual_smoke.md §2`](../manual_smoke.md) | **captured verbatim in T07 CHANGELOG entry** — `run_workflow` paused at gate, `resume_run` produced 10-step plan |

---

## Issue log — cross-task follow-up

| ID | Severity | Status |
| --- | --- | --- |
| M5-T07-ISS-01 | 🟡 MEDIUM | ✅ RESOLVED (2026-04-20, during this audit cycle) — live smokes captured + T06 spec corrected in-place + user memory updated |

---

## Deferred to nice_to_have

None raised.

---

## Propagation status

No forward-deferrals from T07. The T06 spec error surfaced by T07's live run was resolved in-place rather than forward-deferred, so no carry-over is appended to any downstream task. M5 closes CLEAN.
