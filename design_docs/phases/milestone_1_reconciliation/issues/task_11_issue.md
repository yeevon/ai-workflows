# Task 11 — CLI Stub-Down — Pre-build Audit Amendments

**Source task:** [../task_11_cli_stub_down.md](../task_11_cli_stub_down.md)
**Source audit:** [../audit.md](../audit.md) (produced by [M1 Task 01](../task_01_reconciliation_audit.md))
**Created on:** 2026-04-19
**Status:** 📋 PENDING BUILDER — gates not yet run; this file encodes pre-build amendments only.

## Why this file exists

Task files `task_02`…`task_13` were drafted **before** the reconciliation audit ran. Per [CLAUDE.md](../../../../CLAUDE.md) Builder conventions, this file is the bridge to the [audit.md](../audit.md) source of truth.

## Required reading order for Builder

1. [../../../architecture.md](../../../architecture.md) — especially §4.4.
2. [../audit.md](../audit.md) — authoritative source. Rows targeting `task 11` apply here.
3. [../task_11_cli_stub_down.md](../task_11_cli_stub_down.md) — deliverables + ACs.
4. This file — amendments.
5. If audit and task disagree, **raise the conflict before implementing** per CLAUDE.md Builder conventions.

## Rows from audit.md this task must execute

### MODIFY

| Path | Reason |
| --- | --- |
| `ai_workflows/cli.py` | Strip every command whose body imports pydantic-ai; leave `--help` + `version` stubs with `TODO(M3)` / `TODO(M4)` pointers per [architecture.md §4.4](../../../architecture.md). |
| `ai_workflows/__init__.py` | Needs `__version__` dunder for `aiw version` deliverable. Current docstring re-exports `llm` + `tools` subpackages being deleted — rewrite it. |
| `tests/test_cli.py` | Reduce to `aiw --help` + `aiw version` assertions; drop every test of a removed command. |

## Known amendments vs. task spec

- **Consistency with [task 03](../task_03_remove_llm_substrate.md).** `ai_workflows/__init__.py` is also targeted by the [task_03](../task_03_remove_llm_substrate.md) row (docstring + re-exports rewrite). Coordinate: whichever task lands first handles both the docstring rewrite and the `__version__` dunder introduction; the later task leaves it alone.
- **MCP surface pointer.** [architecture.md §4.4](../../../architecture.md) adds the MCP server as a first-class surface (`ai_workflows.mcp`). The `TODO(...)` pointers left behind by the stub should include `TODO(M4)` markers for MCP-equivalent commands where relevant (e.g. `cost-report` is both a CLI subcommand and an MCP tool).
- **Click / Typer.** Task spec and current code both use Typer. [architecture.md §4.4](../../../architecture.md) notes "Click-based for now; see [nice_to_have.md §4](../../../nice_to_have.md) for the Typer / pydantic-native option if CLI and MCP schemas start diverging" — this is phrased loosely and the current stack is Typer. **Do not swap to Click** as a drive-by; the Typer → Click or Typer → pydantic-native swap is deferred per [nice_to_have.md §4](../../../nice_to_have.md).

## Carry-over from prior audits

_None._

## Propagation status

Post-build audit will overwrite this file with implementation findings.
