# Task 06 — `aiw list-runs` CLI Command — Audit Issues

**Source task:** [../task_06_cli_list_cost.md](../task_06_cli_list_cost.md)
**Audited on:** 2026-04-20 (initial) · 2026-04-20 (re-audit after cycle 2 doc-propagation fixes)
**Audit scope:** `aiw list-runs` implementation (cli.py + storage.py), new test suite, CHANGELOG entry, task spec reframe, nice_to_have.md §9 deferral, and downstream doc drift created by the reframe.
**Status:** ✅ PASS — 0 HIGH / 0 MEDIUM / 0 LOW. All ACs met, no design drift, no open issues. All three MEDIUMs from cycle 1 (doc propagation of the reframe) resolved in cycle 2.

---

## Design-drift check (against architecture.md + cited KDRs)

| Vector | Finding |
| --- | --- |
| New dependency added? | No. Only reuses `typer`, `asyncio`, `sqlite3` (stdlib) — already listed in architecture.md §6. ✅ |
| New module or layer? | No. Edits confined to `ai_workflows/cli.py` (surfaces) + `ai_workflows/primitives/storage.py`. Respects the `primitives → graph → workflows → surfaces` contract. ✅ |
| Import-linter contract | 3/3 kept (verified). ✅ |
| LLM call added? | No. `list-runs` never touches `TieredNode` / LiteLLM / Claude Code CLI. ✅ KDR-003 / KDR-004 untouched. |
| Checkpoint / resume logic? | No. Command never opens the checkpointer, never compiles a graph. ✅ KDR-009 respected (Storage-only read). |
| Retry logic? | No. ✅ KDR-006 untouched. |
| Observability? | Uses `StructuredLogger` via `configure_logging(level="INFO")` — same entry pattern as `aiw run` / `aiw resume`. No external backends introduced. ✅ |
| Anthropic SDK import? | None (`grep -n "anthropic" ai_workflows/cli.py` → no match). ✅ |
| `ANTHROPIC_API_KEY` read? | None. ✅ |
| Storage schema change? | None. `workflow_filter` is a pure SELECT extension — `WHERE workflow_id = ?` AND-ed with the existing `status` clause. No migration. ✅ |
| Tests for every AC? | Yes (6 tests, one per spec test case). ✅ |

No KDR violated. No architecture section contradicted *by the code*. The MEDIUM findings below are downstream doc-sync items the user-approved reframe created — they don't affect runtime correctness.

---

## AC grading (against task spec ACs after reframe)

| # | AC | Status | Evidence |
| --- | --- | --- | --- |
| 1 | `aiw list-runs` supports `--workflow`, `--status`, `--limit`. | ✅ | [cli.py](../../../../ai_workflows/cli.py) `list_runs` defines all three Typer options; [tests/cli/test_list_runs.py](../../../../tests/cli/test_list_runs.py) covers each filter individually (`test_list_runs_workflow_filter`, `test_list_runs_status_filter`, `test_list_runs_limit_caps_rows`). |
| 2 | Command is a pure read (no INSERT / UPDATE). | ✅ | Implementation calls only `SQLiteStorage.list_runs(...)` (a single `SELECT ... WHERE ... ORDER BY started_at DESC LIMIT ?`). `test_list_runs_is_pure_read` reads row count before + after and asserts equality. |
| 3 | `runs.total_cost_usd` surfaced; NULL renders as `—`. | ✅ | `_emit_list_runs_table` uses `f"${cost_raw:.4f}" if cost_raw is not None else "—"`. `test_list_runs_cost_column_rendering` seeds one row with `UPDATE ... SET total_cost_usd = NULL` (schema defaults to `0.0`, so NULL must be produced by direct SQL) and asserts both `"$0.0033"` and `"—"` appear. |
| 4 | `uv run pytest tests/cli/test_list_runs.py` green. | ✅ | 6/6 passed locally. Full-suite run: 295 passed / 0 failed. |
| 5 | `uv run lint-imports` 3/3 kept. | ✅ | Verified locally; ruff clean too. |

Dropped from original spec (at user-approved reframe): `aiw cost-report <run_id> --by model|tier|provider` + its ACs + its `CostTracker.from_storage` replay source. Reasoning in the task spec's "Design drift and reframe (2026-04-20)" section and mirrored in [nice_to_have.md §9](../../../nice_to_have.md).

---

## 🔴 HIGH

None.

---

## 🟡 MEDIUM

All three MEDIUMs below were raised in cycle 1 and resolved in cycle 2 by the same task's follow-on doc edits (doc-only; no code change).

### M3-T06-ISS-01 — `architecture.md §4.4` still lists `aiw cost-report` + MCP `get_cost_report` — RESOLVED (cycle 2)

The T06 reframe moved `cost-report` from M3 scope to [nice_to_have.md §9](../../../nice_to_have.md) and explicitly re-specced the M4 `get_cost_report` MCP tool as inheriting the same reframe ("When M4 opens, re-spec the tool as total-only (or drop it entirely in favour of a `list_runs`-equivalent structured return)" — task_06 reframe section). But architecture.md §4.4 still reads:

- Line 97 — CLI: "`aiw run <workflow> <inputs>`, `aiw resume <run_id>`, `aiw list-runs`, `aiw cost-report`."
- Line 102 — MCP: "`get_cost_report(run_id) → CostReport`."

This is the same kind of doc drift CLAUDE.md Auditor mode calls out: the source-of-truth design doc now contradicts the committed scope reframe.

**Action / Recommendation:** update architecture.md §4.4 to list the three CLI commands that actually ship in M3 (`aiw run`, `aiw resume`, `aiw list-runs`) and drop the `aiw cost-report` mention; add a parenthetical pointing at [nice_to_have.md §9](../../../nice_to_have.md) for the deferred command. For the MCP tool row — leave `get_cost_report` listed but flag it as "scope inherited from T06 reframe; will be re-specced at M4 start — see [milestone_3 T06 reframe](../phases/milestone_3_first_workflow/task_06_cli_list_cost.md)". This is a doc-only edit; no KDR change needed because the reframe is a scope decision, not an architectural pivot.

Severity: **MEDIUM** — architecture.md is the quoted source of truth in CLAUDE.md ("Grounding: read before any task"). Stale text in §4.4 will mislead the next Builder.

**Cycle 2 fix:** line 97 of `architecture.md` now reads "`aiw run <workflow> <inputs>`, `aiw resume <run_id>`, `aiw list-runs`" with a parenthetical pointing at [nice_to_have.md §9](../../../nice_to_have.md) for the deferred `aiw cost-report`. Line 102 annotates the MCP `get_cost_report` row with the same reframe note. Verified via `grep -n "cost-report" architecture.md`.

### M3-T06-ISS-02 — M3 README still lists `aiw cost-report` as a T06 deliverable — RESOLVED (cycle 2)

`design_docs/phases/milestone_3_first_workflow/README.md`:

- Line 15 — milestone goal: "`aiw list-runs` and `aiw cost-report <run_id>` return the expected structured output."
- Line 46 — task table row 06: "CLI `aiw list-runs` + `aiw cost-report` commands."

Both lines still treat `cost-report` as M3 scope.

**Action / Recommendation:** edit both lines to drop `cost-report`. Suggested replacements: line 15 → "`aiw list-runs` returns the expected structured output (cost-report deferred to nice_to_have.md §9 per T06 reframe)"; line 46 → "CLI `aiw list-runs` command (cost-report deferred — see T06 reframe)." Keeps the audit trail visible without bloating the README.

Severity: **MEDIUM** — the milestone README is what a Builder reads to understand milestone shape; stale scope there will cause re-invention.

**Cycle 2 fix:** line 15 of `milestone_3_first_workflow/README.md` now reads "`aiw list-runs` returns the expected structured output. (The originally-paired `aiw cost-report` command was dropped at T06 reframe …)". Line 46's task table row 06 now reads "CLI `aiw list-runs` command (cost-report deferred — see T06 reframe)". Verified via `grep`.

### M3-T06-ISS-03 — M3 T08 closeout still acceptance-checks `aiw cost-report` — RESOLVED (cycle 2)

`design_docs/phases/milestone_3_first_workflow/task_08_milestone_closeout.md` line 21:

> "- CLI commands revived (tasks 04–06): `aiw run`, `aiw resume`, `aiw list-runs`, `aiw cost-report`."

This is a closeout-task acceptance bullet. If not fixed, the M3 closeout audit will either fail on a non-existent command or silently pass an unmet AC.

**Action / Recommendation:** strike `aiw cost-report` from the bullet and add a follow-up line: "`aiw cost-report` deferred to [nice_to_have.md §9](../../nice_to_have.md) at T06 reframe (2026-04-20); promotion requires one of the three triggers in that entry." Single-line edit.

Severity: **MEDIUM** — T08 is the gating audit for the milestone; a missed bookkeeping fix here propagates into the closeout gate.

**Cycle 2 fix:** line 21 of `task_08_milestone_closeout.md` now reads "`aiw run`, `aiw resume`, `aiw list-runs`. (`aiw cost-report` was dropped at T06 reframe on 2026-04-20 and deferred to [nice_to_have.md §9] …)". Verified via `grep`.

---

## 🟢 LOW

None.

---

## Additions beyond spec — audited and justified

- **`SQLiteStorage.list_runs` gains `workflow_filter` kwarg + matching `StorageBackend` protocol update.** Called out explicitly in the task spec ("add the optional `workflow_filter` parameter — it is a pure SELECT, no schema change, no migration"). ✅ In-scope.
- **`cli.py` module docstring + `_root` Typer-callback docstring updated to reflect the reframe** (name only `list-runs` as the T06 deliverable; point readers to nice_to_have.md §9 for cost-report). Pure-text change; no behaviour delta. ✅ In-scope (reframe bookkeeping).
- **Replaced two `TODO(M3)` stubs at the bottom of cli.py** (`list-runs` + `cost-report`) with a single `TODO(M4)` pointing at the MCP mirror; added a one-line pointer to nice_to_have.md §9 so the deferred-cost-report trail stays visible from the code. ✅ In-scope (the reframe drops the M3 cost-report TODO).
- **CHANGELOG entry includes a ~40-line "Scope reframe from spec" block** reproducing the three reasons for dropping cost-report. Arguably long, but per CLAUDE.md every code-touching task documents deviations from spec — the reframe is the deviation, so the block is the required form. ✅ In-scope.

No abstraction was introduced beyond what the spec prescribed. No drive-by refactors. No `nice_to_have.md` items were silently adopted (the §9 entry was *created* as the deferral channel, which is the inverse operation and is the user-approved reframe direction).

---

## Gate summary

| Gate | Status | Notes |
| --- | --- | --- |
| `uv run pytest tests/cli/test_list_runs.py` | ✅ 6 passed | All six ACs exercised, one per test. |
| `uv run pytest` (full suite) | ✅ 295 passed | No regressions from prior 289; the +6 are the new T06 tests. |
| `uv run lint-imports` | ✅ 3/3 kept | `primitives → graph → workflows → surfaces` contract preserved. |
| `uv run ruff check` | ✅ clean | No lint findings on the new code. |
| Architecture grounding | ✅ | Cycle 1 flagged three doc drifts (architecture.md §4.4, M3 README, T08 closeout); cycle 2 resolved all three in place — no references to `aiw cost-report` as in-scope remain. |
| KDR grounding | ✅ | KDR-003 / KDR-004 / KDR-006 / KDR-009 untouched. KDR-009 actively honoured (list-runs never opens the checkpointer or the graph). |

---

## Issue log — cross-task follow-up

| ID | Severity | Target | Status |
| --- | --- | --- | --- |
| M3-T06-ISS-01 | MEDIUM | `design_docs/architecture.md` §4.4 (drop `aiw cost-report`; annotate MCP `get_cost_report`) | RESOLVED (cycle 2) |
| M3-T06-ISS-02 | MEDIUM | `design_docs/phases/milestone_3_first_workflow/README.md` (lines 15 + 46) | RESOLVED (cycle 2) |
| M3-T06-ISS-03 | MEDIUM | `design_docs/phases/milestone_3_first_workflow/task_08_milestone_closeout.md` (line 21) | RESOLVED (cycle 2) |

---

## Deferred to nice_to_have

| Finding | Maps to | Trigger |
| --- | --- | --- |
| `aiw cost-report <run_id>` (the command itself, not the doc-drift) | [nice_to_have.md §9](../../../nice_to_have.md) | Any of: Claude Max overages routine / second per-token-billed provider integrated / Gemini moves off free-tier backup. |

This is the *original* deferral channel for the dropped half of the task; it is recorded here for audit completeness. It does **not** get forward-deferred to a future task.

---

## Propagation status

M3-T06-ISS-01, -02, -03 are doc-sync items owned by T06 itself (next implement cycle) — they are immediately resolvable and don't need forward-deferral to a downstream task. No `## Carry-over from prior audits` section added to other task files because the targets are not task files.

The M4 `get_cost_report` MCP tool re-spec is already documented in the T06 spec reframe + nice_to_have.md §9 + in the proposed annotation for M3-T06-ISS-01. When M4 opens, the M4 T04 spec should be re-read against the reframe before its Builder runs.
