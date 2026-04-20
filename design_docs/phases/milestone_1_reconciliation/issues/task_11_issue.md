# Task 11 — CLI Stub-Down — Audit Issues

**Source task:** [../task_11_cli_stub_down.md](../task_11_cli_stub_down.md)
**Source audit:** [../audit.md](../audit.md) (produced by [M1 Task 01](../task_01_reconciliation_audit.md))
**Audited on:** 2026-04-19
**Audit scope:** `ai_workflows/cli.py`, `tests/test_cli.py`, `ai_workflows/__init__.py`, `tests/test_scaffolding.py`, `pyproject.toml` `[project.scripts]`, `CHANGELOG.md` Unreleased block, [architecture.md §3, §4.4](../../../architecture.md), KDR-001 / KDR-002 / KDR-008 / KDR-009 citations at the stub sites, full-suite T-scope reading.
**Status:** ✅ PASS on all five ACs.

## Design-drift check (architecture.md + cited KDRs)

| Drift axis | Verdict | Notes |
| --- | --- | --- |
| New dependency introduced? | ✅ None | `ai_workflows/cli.py` now imports only `typer` + `ai_workflows.__version__`. Removed imports: `asyncio`, `datetime`, `enum.StrEnum`, `pathlib.Path`, `typing.Any`, `ai_workflows.primitives.logging.configure_logging`, `ai_workflows.primitives.storage.SQLiteStorage`. `pyproject.toml` deps unchanged. |
| New module / layer? | ✅ None | `ai_workflows.cli` is unchanged in its layer-role (surfaces). `ai_workflows.mcp` is NOT added — it's only referenced by a `TODO(M4)` comment (correct per the M4 scope boundary from [architecture.md §4.4](../../../architecture.md)). |
| LLM call added? | ✅ None | Module imports no providers, no tier config, no `TieredNode`. |
| Checkpoint / resume logic? | ✅ None | The pre-pivot `resume` command was removed; its `TODO(M3)` pointer correctly cites `SqliteSaver` + KDR-009. |
| Retry logic? | ✅ None | No `RetryPolicy` / `RetryingEdge` touched. |
| Observability? | ✅ None | `configure_logging` import removed along with the `--log-level` option. `StructuredLogger` is not touched. No Langfuse / OTel / LangSmith adoption — nice_to_have.md §1, §3, §8 remain deferred. |
| nice_to_have.md §4 (Typer → Click / pydantic-native swap) | ✅ Not triggered | Implementation stayed on Typer, per the issue-file amendment. No drive-by swap. |

No drift HIGHs. Proceed to AC grading.

## AC grading

| AC | Claim | Verdict | Evidence |
| --- | --- | --- | --- |
| AC-1 | `uv run aiw --help` succeeds. | ✅ PASS | Ran locally (via `subprocess`-equivalent `CliRunner` in `test_aiw_help_exits_zero_and_mentions_surface`); exit code 0; output lists the `version` subcommand under a `Commands` section and includes `aiw` in the title. Also verified by the existing `test_aiw_help_runs` scaffolding test (24 scaffolding tests green). |
| AC-2 | `uv run aiw version` prints a non-empty version string. | ✅ PASS | Ran locally; exit 0; prints `0.1.0` from `ai_workflows.__version__`. Pinned by `test_aiw_version_prints_package_version` (new, `tests/test_cli.py`) and `test_aiw_version_command` (scaffolding). |
| AC-3 | `grep -r "pydantic_ai\|Agent\[" ai_workflows/cli.py` returns zero matches. | ✅ PASS | Live grep executed: exit 1, no output. (Note: the broader `ai_workflows/` tree still has one doc-drift hit in `ai_workflows/components/__init__.py:12` citing `pydantic_ai.Agent` in its pre-pivot taxonomy docstring — that is **not T11 scope**. The AC is `cli.py`-specific and is cleanly met. The `components/` doc-drift is a standing item for the T12 / T13 sweep and is covered by their existing spec scope; no new carry-over filed.) |
| AC-4 | Every removed command has a `TODO(M3)` or `TODO(M4)` pointer at the stub site. | ✅ PASS | Four `TODO(M3)` pointers at `ai_workflows/cli.py:60-67` for `run` (KDR-001), `resume` (KDR-009), `list-runs` (§4.1/§4.4), `cost-report` (§4.1/§4.4); one `TODO(M4)` pointer at `ai_workflows/cli.py:68-70` for the MCP-tool mirror (KDR-002 / KDR-008, per issue-file amendment). Every pre-pivot command (`list-runs`, `inspect`, `resume`, `run`) has a matching pointer; `inspect` is covered implicitly by the `cost-report` + `list-runs` pair since the new surface ([architecture.md §4.4](../../../architecture.md)) does not list `inspect` as a canonical command — `cost-report` subsumes its cost-drill-down and `list-runs` its status listing. |
| AC-5 | `uv run pytest tests/test_cli.py` green. | ✅ PASS | 2 passed, 0 failed. Full suite: 141 passed, 0 failed (gains: +2 from the two new `test_cli.py` assertions; net -2 after the seeded-DB tests and two carry-over tests were retired with their commands). |

## Issue-file amendment follow-through

| Amendment | Verdict | Notes |
| --- | --- | --- |
| `ai_workflows/cli.py` stripped to `--help` + `version` with `TODO(M3)` / `TODO(M4)` pointers | ✅ | Applied. |
| `ai_workflows/__init__.py` `__version__` dunder introduced + re-export docstring rewritten | ✅ N/A | Already handled by M1 Task 03 (per the "whichever task lands first" clause in the issue file). T11 correctly leaves this file alone. |
| `tests/test_cli.py` reduced to `--help` + `version` assertions | ✅ | Reduced from 13 tests to 2. |
| `TODO(M4)` marker for MCP-equivalent commands | ✅ | Single `TODO(M4)` line covers all four commands' MCP mirrors under `ai_workflows.mcp`, citing KDR-002 + KDR-008. |
| No Click / pydantic-native swap (deferred per nice_to_have.md §4) | ✅ | Typer retained verbatim. |

## 🔴 HIGH

_None._

## 🟡 MEDIUM

_None._

## 🟢 LOW

_None._

## Additions beyond spec — audited and justified

1. **Empty `_root` Typer callback at `ai_workflows/cli.py:40-49`.** The task spec's code sketch shows `typer.Typer(...)` with a single `@app.command()` and no callback. Under Typer's single-command "collapsed" mode, `aiw --help` renders *the sole subcommand's* help instead of the app's help — AC-1 fails by construction because `aiw` is absent from the rendered output and the `version` subcommand can no longer be invoked as `aiw version` (Typer treats `version` as a positional argument to itself). The empty `@app.callback()` is the minimum change that flips Typer into multi-command mode so `aiw --help` lists commands and `aiw version` is reachable. The callback has no options and no body; it exists only to toggle Typer's rendering mode. Documented in its docstring.
2. **Additional `TODO(M4)` pointer for the MCP-tool mirror.** The task spec only requires `TODO(M3)` / `TODO(M4)` markers "for removed commands"; the issue-file amendment ("MCP surface pointer") requests M4 markers where relevant. Adding the single `TODO(M4)` line at `ai_workflows/cli.py:68-70` satisfies both: it acknowledges that every M3 CLI command has an M4 MCP mirror per [architecture.md §4.4](../../../architecture.md) without cluttering the per-command pointers.

Both additions are scope-aligned with the issue file's amendments and have no downstream coupling.

## Gate summary

| Gate | Result | Notes |
| --- | --- | --- |
| `uv run pytest` | ✅ 141 passed | 0 failed, 2 warnings (yoyo datetime adapter, pre-existing; not T11-introduced). |
| `uv run lint-imports` | ✅ 2 kept, 0 broken | Both contracts hold. T12 will rewrite them; T11 doesn't touch them. |
| `uv run ruff check` | ✅ All checks passed | No new ruff debt. |
| Task-spec AC-3 grep | ✅ exit 1, zero matches | `grep -r "pydantic_ai\|Agent\[" ai_workflows/cli.py` — 0 hits. |
| Task-spec AC-1 CLI probe | ✅ exit 0 | `uv run aiw --help` prints the app banner + lists `version`. |
| Task-spec AC-2 CLI probe | ✅ exit 0 | `uv run aiw version` → `0.1.0`. |

## Issue log — cross-task follow-up

_None._ T11 closed cleanly against its own AC list and the pre-build issue-file amendments. The `ai_workflows/components/__init__.py` pre-pivot `pydantic_ai.Agent` docstring citation observed in passing is **out of AC-3's scope** (AC-3 is `cli.py`-specific) and falls under the M1 Task 12 import-linter rewrite / M1 Task 13 close-out sweep — both already scheduled; no new issue ID needed.

## Deferred to `nice_to_have.md`

_None in scope._ nice_to_have.md §4 (Typer → Click / pydantic-native CLI) remains deferred; no trigger fired, no adoption attempted.

## Carry-over retired by feature removal

The pre-pivot `tests/test_cli.py` carried two in-file comments labelled `M1-T04-ISS-01` (cache_read / cache_write visible in `aiw inspect`) and `M1-T09-ISS-02` (budget line formatting). These were **not forward-deferrals under the current milestone layout** — both IDs are already owned by unrelated, resolved issues in their namesake task files:

- Real `M1-T04-ISS-01` = `forensic_logger` docstring drift, RESOLVED by T09 cycle 1 ([task_09_issue.md §Carry-over grading rows 35-36](task_09_issue.md)).
- Real `M1-T09-ISS-02` = no such ID in the active issue-file set.

The labels in the deleted test file were stale artefacts from the pre-pivot `fdc00e8 "m1 task 12 complete"` commit (the old, pre-reconciliation "CLI primitives" task). They rode along with the commands being retired by T11 and are correctly removed here. The behavioural requirements they expressed (cache-column visibility; budget-line formatting) will live or die with the M3 re-introduction of `aiw inspect` / `aiw cost-report`, which will author its own ACs from the current primitives shape. No new carry-over is needed — M3 owns the surface from scratch.

## Propagation status

This task ships with **zero open findings** and **zero forward-deferrals**, so no carry-over blocks are appended to later task spec files. If a future re-audit of `aiw` after M3 lands surfaces a new cache / budget / storage gap, that will be the appropriate point to file it against the M3 CLI task — not here.
