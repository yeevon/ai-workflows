# Task 12 — Import-Linter Contract Rewrite — Audit Issues

**Source task:** [../task_12_import_linter_rewrite.md](../task_12_import_linter_rewrite.md)
**Source audit:** [../audit.md](../audit.md) (produced by [M1 Task 01](../task_01_reconciliation_audit.md))
**Audited on:** 2026-04-19
**Audit scope:** `pyproject.toml` `[tool.importlinter]` block + `[dependency-groups]` comment, `ai_workflows/__init__.py`, `ai_workflows/primitives/__init__.py`, `ai_workflows/graph/__init__.py`, `ai_workflows/workflows/__init__.py`, `ai_workflows/mcp/__init__.py`, deletion of `ai_workflows/components/` + `tests/components/`, `tests/test_scaffolding.py`, `tests/graph/__init__.py`, `tests/mcp/__init__.py`, `.github/workflows/ci.yml`, `CHANGELOG.md` Unreleased block, full-suite gate run, [architecture.md §3 / §4.1 / §4.2 / §4.4](../../../architecture.md), nice_to_have.md §1 / §3 / §4 / §8, T06 / T10 / T11 / T13 carry-over state.
**Status:** ✅ PASS on all five ACs plus both pre-build amendments (AUD-12-01 + AUD-12-02).

## Design-drift check (architecture.md + pre-build amendments)

| Drift axis | Verdict | Notes |
| --- | --- | --- |
| New dependency introduced? | ✅ None | `pyproject.toml` `[project].dependencies` unchanged; only the `[tool.importlinter]` block was rewritten. |
| New module / layer? | ✅ Aligned | Two new **empty** packages: `ai_workflows.graph` (graph layer) and `ai_workflows.mcp` (surfaces). Both are explicitly required by [architecture.md §3](../../../architecture.md) and [§4.2](../../../architecture.md) / [§4.4](../../../architecture.md). `ai_workflows.components` collapsed into `graph/` exactly as the architecture mandates ("the `components/` layer from the archived design is collapsed into `graph/`"). |
| LLM call added? | ✅ None | No tier config, no provider, no `TieredNode`. Task is pure structural reshape. |
| Checkpoint / resume logic? | ✅ None | No `SqliteSaver`, no checkpointer code. |
| Retry logic? | ✅ None | No `RetryPolicy` / `RetryingEdge` touched. |
| Observability? | ✅ None | No Langfuse / OTel / LangSmith touched. `StructuredLogger` not touched. nice_to_have.md §1, §3, §8 remain deferred. |
| nice_to_have.md §4 (Typer → Click swap) | ✅ Not triggered | Task does not touch the CLI; Typer stays. |
| Four-layer contract faithfulness | ✅ Exact | The three contracts committed to `pyproject.toml` match the task-spec code block byte-for-byte (ordering, forbidden-module lists, contract names). |

No drift HIGHs. Proceed to AC grading.

## AC grading

| AC | Claim | Verdict | Evidence |
| --- | --- | --- | --- |
| AC-1 | `ai_workflows/components/` no longer exists. | ✅ PASS | `ls ai_workflows/components` → exit 2 "No such file or directory". `find ai_workflows -type d -name components` → no output. |
| AC-2 | `ai_workflows/graph/`, `ai_workflows/workflows/`, `ai_workflows/mcp/` exist with package docstrings only. | ✅ PASS | All three `__init__.py` files exist. Each is docstring-only (no imports, no statements). `graph/__init__.py` cites [architecture.md §3 / §4.2](../../../architecture.md); `mcp/__init__.py` cites [§4.4](../../../architecture.md), KDR-002, KDR-008; `workflows/__init__.py` was already docstring-only from T10 (cites §4.3 + ADR-0001). |
| AC-3 | `uv run lint-imports` succeeds and reports three contracts passing. | ✅ PASS | Live run: `Analyzed 11 files, 2 dependencies. ... Contracts: 3 kept, 0 broken.` The three names match the task-spec: "primitives cannot import graph, workflows, or surfaces", "graph cannot import workflows or surfaces", "workflows cannot import surfaces". |
| AC-4 | `grep -r "ai_workflows.components" . --include="*.py" --include="*.toml"` returns zero matches. | ✅ PASS | Live grep executed: zero output (exit 1). Documentation `.md` hits in `design_docs/archive/` and `design_docs/phases/milestone_1_reconciliation/task_12_*.md` + `task_13_*.md` are excluded by the grep's file-type filter — archive references are reference-only per CLAUDE.md; the task-spec references are the AC itself. |
| AC-5 | `uv run pytest` green. | ✅ PASS | Full-suite: **142 passed**, 0 failed, 2 pre-existing warnings (yoyo datetime adapter, not T12-introduced). |

## Pre-build amendment follow-through

| Amendment | Verdict | Notes |
| --- | --- | --- |
| AUD-12-01 — rename `.github/workflows/ci.yml` import-linter step from "3-layer architecture" to "4-layer architecture" | ✅ | Applied: `.github/workflows/ci.yml:31` reads `Lint imports (4-layer architecture)`. Command (`uv run lint-imports`) unchanged. [task 13 pre-close checklist row](task_13_issue.md) can tick this. |
| AUD-12-02 — add `tests/graph/__init__.py` and `tests/mcp/__init__.py` package markers (optional in this task) | ✅ | Applied: both markers present as empty files. Saves M2 Task 01 / M4 Task 01 the scaffolding step. |

## Changes beyond the task spec's explicit deliverable list — audited and justified

1. **`ai_workflows/__init__.py` docstring rewrite.** The task spec's deliverable list names the `components/` deletion and the `graph/` / `mcp/` additions, but the top-level package docstring still described "three strictly layered sub-packages: primitives / components / workflows" — directly contradicting architecture.md §3. The task spec's REMOVE block says "Any trailing references to `ai_workflows.components` … anywhere else"; the `__init__.py` docstring is a "trailing reference" by plain reading. Rewriting it to the four-layer shape is in-scope.
2. **`ai_workflows/primitives/__init__.py` docstring layer list update.** Same rationale: the architectural-rule block read "nothing in this package is allowed to import from `ai_workflows.components` or `ai_workflows.workflows`". After `components/` is removed the rule is false-by-reference. Updated to the four-element forbidden list that matches the actual import-linter contract.
3. **`tests/test_scaffolding.py` adjustments.** Two edits were unavoidable: (a) the parametrized `test_layered_packages_import` listed `ai_workflows.components` — pytest would fail to import it; replaced with `graph` + `mcp` alongside the surviving layers so the test pins the full four-layer tree. (b) `test_pyproject_declares_expected_importlinter_contracts` asserted the old two-contract shape including the substring `components cannot import workflows` — no longer in the toml; rewritten against the three-contract four-layer vocabulary with `len(contracts) == 3`. Both are necessary tests-following-code changes, not scope creep.
4. **`ai_workflows.workflows` appears in the layer-import smoke test's parametrization.** Already there pre-T12; kept.

All four changes are strictly consequential to "remove trailing references to `ai_workflows.components`" plus the AC-5 requirement that the test suite be green; none introduce new coverage or behaviour.

## 🔴 HIGH

_None._

## 🟡 MEDIUM

_None._

## 🟢 LOW

_None._

## Gate summary

| Gate | Result | Notes |
| --- | --- | --- |
| `uv run pytest` | ✅ 142 passed | 0 failed, 2 pre-existing warnings (yoyo datetime adapter). +1 vs. T11's 141 (new `ai_workflows.mcp` parameter row in `test_layered_packages_import`). |
| `uv run lint-imports` | ✅ 3 kept / 0 broken | All three contracts (primitives / graph / workflows) report KEPT. |
| `uv run ruff check` | ✅ All checks passed | No new ruff debt. |
| Task-spec AC-3 lint-imports contract-count probe | ✅ exactly 3 contracts | `len(contracts) == 3` asserted in `test_pyproject_declares_expected_importlinter_contracts`. |
| Task-spec AC-4 grep | ✅ exit 1, zero matches | `grep -r "ai_workflows.components" . --include="*.py" --include="*.toml"` — zero hits. |
| nice_to_have.md adoption scan | ✅ zero hits | `grep -rn "langfuse|langsmith|instructor|docker-compose|mkdocs|deepagents|opentelemetry" pyproject.toml ai_workflows/` → no output. |

## Issue log — cross-task follow-up

_None._ T12 closed cleanly against its own AC list, the pre-build amendments AUD-12-01 + AUD-12-02, and the four-layer contract from [architecture.md §3](../../../architecture.md). No new IDs issued.

The T13 pre-close checklist row for AUD-12-01 ("CI import-lint step renamed away from '3-layer architecture'") is now satisfied — [task_13_issue.md](task_13_issue.md)'s next touch point can tick it.

## Deferred to `nice_to_have.md`

_None in scope._ nice_to_have.md §4 (Typer → Click / pydantic-native CLI) remains deferred but was out of T12's scope anyway (CLI not touched).

## Carry-over from prior audits

_None landed on T12._ T06-ISS-04 and T10-ISS-01 (both about `scripts/m1_smoke.py`) are owned by T13, not T12. T11's propagation status was zero forward-deferrals. No cross-task items need execution here.

## Propagation status

Zero open findings and zero forward-deferrals. No carry-over blocks appended to later task spec files. The milestone's next gate is T13 (close-out); T13's pre-close checklist has one rewarded tick (AUD-12-01 CI rename) — everything else on T13's list is owned by T13 itself or by pre-existing T06 / T10 `scripts/m1_smoke.py` carry-over.
