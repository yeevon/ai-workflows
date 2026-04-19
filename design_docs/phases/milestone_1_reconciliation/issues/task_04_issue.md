# Task 04 — Remove Tool Registry + Stdlib Tools — Pre-build Audit Amendments

**Source task:** [../task_04_remove_tool_registry.md](../task_04_remove_tool_registry.md)
**Source audit:** [../audit.md](../audit.md) (produced by [M1 Task 01](../task_01_reconciliation_audit.md))
**Created on:** 2026-04-19
**Status:** 📋 PENDING BUILDER — gates not yet run; this file encodes pre-build amendments only.

## Why this file exists

Task files `task_02`…`task_13` were drafted **before** the reconciliation audit ran. Per [CLAUDE.md](../../../../CLAUDE.md) Builder conventions, this file is the bridge to the [audit.md](../audit.md) source of truth.

## Required reading order for Builder

1. [../../../architecture.md](../../../architecture.md) — especially KDR-002 / KDR-008 / §8.1.
2. [../audit.md](../audit.md) — authoritative source. Rows targeting `task 04` apply here.
3. [../task_04_remove_tool_registry.md](../task_04_remove_tool_registry.md) — deliverables + ACs.
4. This file — amendments.
5. If audit and task disagree, **raise the conflict before implementing** per CLAUDE.md Builder conventions.

## Rows from audit.md this task must execute

### REMOVE (production code)

| Path | Reason |
| --- | --- |
| `ai_workflows/primitives/tools/__init__.py` | Tool-registry package removal — no consumer under [architecture.md §4.1](../../../architecture.md). |
| `ai_workflows/primitives/tools/forensic_logger.py` | Pre-pivot tool-call forensic ledger; observability is `StructuredLogger` only per [architecture.md §8.1](../../../architecture.md). |
| `ai_workflows/primitives/tools/fs.py` | Stdlib tool; no consumer. |
| `ai_workflows/primitives/tools/git.py` | Stdlib tool; no consumer. |
| `ai_workflows/primitives/tools/http.py` | Stdlib tool; also the only direct `httpx` consumer in `ai_workflows/` (post-removal `httpx` is transitive via LiteLLM only). |
| `ai_workflows/primitives/tools/registry.py` | Tool registry core — no concept in the new architecture. |
| `ai_workflows/primitives/tools/shell.py` | Stdlib tool; no consumer. |
| `ai_workflows/primitives/tools/stdlib.py` | Stdlib tool wiring; no consumer. |

### REMOVE (tests)

| Path | Reason |
| --- | --- |
| `tests/primitives/test_tool_registry.py` | Covers the tool registry (removed). Note the path: flat under `tests/primitives/`, not under `tests/primitives/tools/`. |
| `tests/primitives/tools/__init__.py` | Package marker for a removed subpackage. |
| `tests/primitives/tools/conftest.py` | Fixtures for deleted tools. |
| `tests/primitives/tools/test_fs.py` | Covers `primitives/tools/fs.py`. |
| `tests/primitives/tools/test_git.py` | Covers `primitives/tools/git.py`. |
| `tests/primitives/tools/test_http.py` | Covers `primitives/tools/http.py`. |
| `tests/primitives/tools/test_shell.py` | Covers `primitives/tools/shell.py`. |
| `tests/primitives/tools/test_stdlib.py` | Covers `primitives/tools/stdlib.py`. |

## Known amendments vs. task spec

### 🟡 MEDIUM — AUD-04-01: "If audit keeps any stdlib helper" branch is a no-op

**Task spec** ([../task_04_remove_tool_registry.md](../task_04_remove_tool_registry.md) §"If audit keeps any stdlib helper") includes a conditional path: move any KEEP helper out of `primitives/tools/` into a flat `primitives/` module.

**Audit** marks **every** file under `ai_workflows/primitives/tools/` as REMOVE. No helper is retained. The conditional branch has no work.

**Resolution.** Skip the "If audit keeps any stdlib helper" section entirely. Delete `ai_workflows/primitives/tools/` wholesale; do not create any flat replacement module under `primitives/`.

### 🟢 LOW — AUD-04-02: `tests/primitives/test_tool_registry.py` lives at the flat level

**Task spec** §"Delete" lumps "Matching tests under `tests/primitives/tools/`" together. That phrase misses `tests/primitives/test_tool_registry.py`, which is at the flat `tests/primitives/` level, one directory above the `tools/` subtree.

**Resolution.** Delete both: the flat `tests/primitives/test_tool_registry.py` and the entire `tests/primitives/tools/` directory. The task's AC `grep -r "forensic_logger\|ToolRegistry\|from ai_workflows.primitives.tools" ai_workflows/ tests/` catches this regardless, but calling it out here prevents a "tests gone missing" post-build audit finding.

## Carry-over from prior audits

### From [M1-T02-ISS-01](task_02_issue.md#-medium--m1-t02-iss-01-post-t02-interim-gate-red-state-forward-deferral-propagated) (T02 post-build audit, 2026-04-19)

Task 02 removed `pydantic-ai>=1.0` from `pyproject.toml` but left the code that imports it under `ai_workflows/primitives/tools/*`. This task owns the matching deletion. Expected side effect: closes 5 of the 11 `uv run pytest` collection errors left open by T02 (plus `tests/primitives/test_tool_registry.py` at the flat level, covered by AUD-04-02).

- [ ] **M1-T02-ISS-01 · MEDIUM** — Delete `ai_workflows/primitives/tools/` wholesale (`fs.py`, `git.py`, `http.py`, `shell.py`, `stdlib.py`, `registry.py` each carry a `from pydantic_ai import RunContext | Tool`). Verified effect on pytest: `tests/primitives/tools/test_fs.py`, `test_git.py`, `test_http.py`, `test_shell.py`, `test_stdlib.py` collection errors clear. Source: [task_02_issue.md §Propagation status](task_02_issue.md#propagation-status).

## Propagation status

Post-build audit will overwrite this file with implementation findings. When the T02 carry-over checkbox ticks, [task_02_issue.md](task_02_issue.md) flips ISS-01 from `DEFERRED` to `RESOLVED` on the next T02 re-audit touch point.
