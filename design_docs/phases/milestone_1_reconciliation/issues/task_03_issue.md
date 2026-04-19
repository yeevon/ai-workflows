# Task 03 — Remove pydantic-ai LLM Substrate — Pre-build Audit Amendments

**Source task:** [../task_03_remove_llm_substrate.md](../task_03_remove_llm_substrate.md)
**Source audit:** [../audit.md](../audit.md) (produced by [M1 Task 01](../task_01_reconciliation_audit.md))
**Created on:** 2026-04-19
**Status:** 📋 PENDING BUILDER — gates not yet run; this file encodes pre-build amendments only. One **🔴 HIGH** divergence between audit and task spec — read the "Known amendments" section before implementing.

## Why this file exists

Task files `task_02`…`task_13` were drafted **before** the reconciliation audit ran. Per [CLAUDE.md](../../../../CLAUDE.md) Builder conventions ("Issue file is authoritative amendment to task file"), this file is the bridge.

## Required reading order for Builder

1. [../../../architecture.md](../../../architecture.md) — especially KDR-001 / KDR-005 / §4.1.
2. [../audit.md](../audit.md) — authoritative source. Rows targeting `task 03` apply here.
3. [../task_03_remove_llm_substrate.md](../task_03_remove_llm_substrate.md) — deliverables + ACs.
4. This file — **contains one HIGH divergence from the task spec** (see §Known amendments).
5. If audit and task disagree, **raise the conflict before implementing** per CLAUDE.md Builder conventions.

## Rows from audit.md this task must execute

### REMOVE (production code)

| Path | Reason |
| --- | --- |
| `ai_workflows/primitives/llm/__init__.py` | `llm/` subpackage removal target per KDR-001 / KDR-005. |
| `ai_workflows/primitives/llm/caching.py` | pydantic-ai `ModelResponse` caching; no replacement — LiteLLM owns retry + caching. |
| `ai_workflows/primitives/llm/model_factory.py` | Builds pydantic-ai `Model`; replaced by `TieredNode` + LiteLLM adapter in M2. |
| `ai_workflows/primitives/llm/types.py` | Message/response types bespoke to pydantic-ai; LiteLLM supplies the OpenAI-shaped contract. |

### REMOVE (tests)

| Path | Reason |
| --- | --- |
| `tests/primitives/test_caching.py` | Covers `primitives/llm/caching.py` (removed). |
| `tests/primitives/test_model_factory.py` | Covers `primitives/llm/model_factory.py` (removed). |
| `tests/primitives/test_types.py` | Covers `primitives/llm/types.py` (removed). |

### MODIFY

| Path | Reason |
| --- | --- |
| `ai_workflows/primitives/__init__.py` | Docstring re-exports `llm` + `tools` subpackages which are being deleted. Rewrite docstring; drop any re-exports so the package loads clean. |
| `tests/conftest.py` | Verify no pydantic-ai fixtures leak; trim any that do. |

## Known amendments vs. task spec

### 🔴 HIGH — AUD-03-01: `llm/__init__.py` is REMOVE, not KEEP-as-stub

**Task spec** ([../task_03_remove_llm_substrate.md](../task_03_remove_llm_substrate.md) §"Keep (minimal stub)") tells the Builder to leave `ai_workflows/primitives/llm/__init__.py` in place as a one-line-docstring empty package, reasoning that M2 will populate it.

**Audit** marks `ai_workflows/primitives/llm/__init__.py` as **REMOVE**. Rationale:

- [architecture.md §4.1](../../../architecture.md) lists primitive sub-topics as storage / cost / tiers / providers / retry / logging. There is no `llm/` sub-topic — the M2 LiteLLM adapter lands under `primitives/providers/` (or as a flat `primitives/litellm_adapter.py`), not under `primitives/llm/`.
- [Task 12](../task_12_import_linter_rewrite.md) creates fresh `ai_workflows/graph/`, `ai_workflows/workflows/`, `ai_workflows/mcp/` packages when needed. M2 can create `primitives/providers/` the same way; pre-creating an empty `llm/` package that the architecture doesn't name is drift.
- Leaving an empty `llm/__init__.py` carries forward a dead naming convention (`primitives.llm` → "LLM clients") at odds with `primitives.providers` from [architecture.md §4.1](../../../architecture.md) "Provider drivers".

**Resolution.** Delete `ai_workflows/primitives/llm/` entirely (including `__init__.py`). Skip the "Keep (minimal stub)" deliverable in the task spec. M2 Task 01 ([milestone_2_graph/task_01_litellm_adapter.md](../../milestone_2_graph/task_01_litellm_adapter.md)) will create the correctly-named package when the LiteLLM adapter lands.

**If the Builder disagrees,** stop and surface the conflict to the user. Do not silently keep the stub.

### 🟡 MEDIUM — AUD-03-02: test file paths in task spec are wrong

**Task spec** §"Delete" says "Matching tests under `tests/primitives/llm/`."

**Audit** places the test files at the flat `tests/primitives/` level (no `llm/` subdirectory): `tests/primitives/test_caching.py`, `tests/primitives/test_model_factory.py`, `tests/primitives/test_types.py`. There is no `tests/primitives/llm/` directory.

**Resolution.** Delete the three flat-path test files listed in this file's REMOVE (tests) table. Ignore the spec's `tests/primitives/llm/` path.

## Carry-over from prior audits

_None._

## Propagation status

Post-build audit of this task will overwrite this file with implementation findings. The two amendments above must be resolved in the Builder's output; failure to apply AUD-03-01 leaves an architectural-drift landmine for M2.
