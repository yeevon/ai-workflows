# Task 12 — Import-Linter Contract Rewrite — Pre-build Audit Amendments

**Source task:** [../task_12_import_linter_rewrite.md](../task_12_import_linter_rewrite.md)
**Source audit:** [../audit.md](../audit.md) (produced by [M1 Task 01](../task_01_reconciliation_audit.md))
**Created on:** 2026-04-19
**Status:** 📋 PENDING BUILDER — gates not yet run; this file encodes pre-build amendments only.

## Why this file exists

Task files `task_02`…`task_13` were drafted **before** the reconciliation audit ran. Per [CLAUDE.md](../../../../CLAUDE.md) Builder conventions, this file is the bridge to the [audit.md](../audit.md) source of truth.

## Required reading order for Builder

1. [../../../architecture.md](../../../architecture.md) — especially §3 (the four-layer contract this task enforces).
2. [../audit.md](../audit.md) — authoritative source. Rows targeting `task 12` apply here.
3. [../task_12_import_linter_rewrite.md](../task_12_import_linter_rewrite.md) — deliverables + ACs.
4. This file — amendments.
5. If audit and task disagree, **raise the conflict before implementing** per CLAUDE.md Builder conventions.

## Rows from audit.md this task must execute

### REMOVE

| Path | Reason |
| --- | --- |
| `ai_workflows/components/__init__.py` | `components/` layer is collapsed into `graph/` per [architecture.md §3](../../../architecture.md); deleting the empty package also satisfies the four-layer contract. |
| `tests/components/__init__.py` | Mirrors the removed `ai_workflows/components/` package. |

### ADD (not in audit — created by this task's scope)

| Path | Reason |
| --- | --- |
| `ai_workflows/graph/__init__.py` | Graph-layer package per [architecture.md §3 / §4.2](../../../architecture.md). Empty shell with docstring. |
| `ai_workflows/mcp/__init__.py` | MCP-surface package per [architecture.md §4.4](../../../architecture.md). Empty shell with docstring. |

## Known amendments vs. task spec

### 🟡 MEDIUM — AUD-12-01: CI file references "3-layer architecture"

**Task spec** already contains the correct four-layer `[tool.importlinter.contracts]` block.

**Out of task-spec scope but inside the four-layer reshape:** `.github/workflows/ci.yml` currently has a step named `"Lint imports (3-layer architecture)"`. Post-reshape the name is misleading. **Rename this step** (e.g. `"Lint imports (4-layer architecture)"`) as part of this task.

**Resolution.** Add a deliverable to this task's Builder pass: edit [.github/workflows/ci.yml](../../../../.github/workflows/ci.yml) to rename the step. Keep the command (`uv run lint-imports`) unchanged.

### 🟢 LOW — AUD-12-02: `tests/graph/` and `tests/mcp/` package markers

`tests/` mirrors the package tree per [CLAUDE.md](../../../../CLAUDE.md). After this task creates `ai_workflows/graph/` and `ai_workflows/mcp/`, the matching `tests/graph/__init__.py` and `tests/mcp/__init__.py` markers should also land so M2/M4 Builders don't need to scaffold them. Optional in this task — if not done here, M2 Task 01 and M4 Task 01 own the matching creation.

## Carry-over from prior audits

_None._

## Propagation status

Post-build audit will overwrite this file with implementation findings.
