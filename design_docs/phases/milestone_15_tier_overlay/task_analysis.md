# M15 — Task Analysis

**Round:** 4 | **Analyzed on:** 2026-04-30 | **Analyst:** task-analyzer agent
**Specs analyzed:** task_03_aiw_list_tiers_and_circuit_open_cascade.md

## Summary

| Severity | Count |
| --- | --- |
| HIGH | 0 |
| MEDIUM | 0 |
| LOW | 0 |

**Stop verdict:** CLEAN

## Round-3 fixes verified clean

- **H1 (CircuitOpen import path)** — fixed at spec line 131. Now reads `from ai_workflows.primitives.circuit_breaker import CircuitOpen`. Verified:
  - `CircuitOpen` is defined at `ai_workflows/primitives/circuit_breaker.py:79` (`__all__` at line 56 confirms it as a public symbol).
  - This import form matches all four existing canonical call sites: `ai_workflows/graph/tiered_node.py:90`, `ai_workflows/graph/error_handler.py:64`, `ai_workflows/workflows/planner.py:68`, `ai_workflows/workflows/slice_refactor.py:195`.
  - The Builder writing this import gets the same module path the production cascade code uses; no `ImportError` at collection. ✅

- **L1 (sync template contradiction)** — pushed to spec carry-over at lines 222-224 (TA-LOW-01). Builder is explicitly redirected to ship a flat sync `list_tiers` command with no `_async` helper and no `asyncio.run`. The template at lines 21-39 is now flagged as illustrative-only by both the inline disclaimer (line 65) and the carry-over checkbox. ✅

- **L2 (misleading analog citation)** — pushed to spec carry-over at lines 226-228 (TA-LOW-02). Builder is redirected to `tests/workflows/test_compiler.py:215` or `tests/workflows/test_spec.py:235` — both verified as direct `register_workflow(synthetic_spec)` call sites (compiler test at line 215, spec test at line 235). The misleading heredoc analog at `tests/mcp/test_scaffold_workflow_http.py:128-149` is no longer load-bearing. ✅

## Findings

None at HIGH, MEDIUM, or LOW. The spec is implementation-ready.

## What's structurally sound

- **CircuitOpen import path** — spec line 131 (`from ai_workflows.primitives.circuit_breaker import CircuitOpen`) matches the production module and all four existing callers. Stub adapter raises the same exception class the real `LiteLLMAdapter` raises through `tiered_node.py`'s cascade path.
- **Stub adapter shape** — `__init__(self, *, route, per_call_timeout_s)` (kwarg-only) is call-compatible with `LiteLLMAdapter.__init__(self, route, per_call_timeout_s)` (positional-or-keyword) at `litellm_adapter.py:53`, given that `tiered_node.py` invokes the constructor with both names as kwargs.
- **`complete` signature** — `(*, system, messages, response_format=None)` mirrors the call at `tiered_node.py:679-681`.
- **TokenUsage construction** — `input_tokens`, `output_tokens`, `cost_usd`, `model` match the dataclass at `cost.py:89-94`.
- **WorkflowSpec required fields** — `name`, `input_schema`, `output_schema`, `steps`, `tiers` all populated in the synthetic spec at lines 117-123. Matches the required-field set at `spec.py:348-360`.
- **TierConfig surface** — `fallback: list[Route]` is a real field at `tiers.py:102` (M15 T01 deliverable, ✅ Built). `LiteLLMRoute` + `ClaudeCodeRoute` are the discriminated-union route types at `tiers.py:55-78`. `TierConfig.fallback` round-tripping through `register_workflow` is exercised by T01's tests.
- **Test isolation** — `_clean_registry` autouse fixture using `workflows._reset_for_tests()` (defined at `workflows/__init__.py:209`) is the canonical isolation pattern.
- **Public API surface** — `list_workflows` at `workflows/__init__.py:167` and `get_spec` at `workflows/__init__.py:151`; both are in `__all__` (lines 92-93). Both synchronous, supporting the spec's directive to ship a sync `list_tiers` command.
- **Layer discipline** — `cli.py` importing from `workflows` and `primitives.tiers` is surfaces → workflows / surfaces → primitives, both allowed by architecture.md §6 dep table.
- **KDR alignment** — KDR-002 (MCP-as-substrate, no schema change), KDR-003 (no Anthropic SDK), KDR-004 (validator pairing untouched), KDR-006 (no bespoke retry — cascade test exercises the existing `RetryingEdge` budget-exhaust path), KDR-008 (no MCP schema change), KDR-009 (no checkpoint touch), KDR-013 (no external workflow concern). All clean.
- **Status surfaces** — milestone README task-order row 03 says `code + test + doc`; spec line 165 explicitly addresses the doc component (CHANGELOG-only). Aligned.
- **Out-of-scope section** — defers ADR-0006 + tiers.yaml relocation + writing-a-workflow.md to T04, and HTTP all-exhausted envelope to T05. Matches the milestone README task order.
- **Dependencies** — line 197 correctly states T01 + T02 are ✅ Built and that M15 ships ≥ 0.5.0 (consistent with project memory: 0.3.1 live, M16 + M19 shipped, next minor is 0.4.0+).

## Cross-cutting context

- Project memory (`project_m13_shipped_cs300_next.md`) flags M15 as deferred — implement after M17 close-out. Spec status line at line 3 says `📝 Planned`. Milestone README line 3 says *"deferred — implement after M17 close-out."* No drift; informational only.
- T03 is the only T03 spec in the milestone directory; no sibling-task contract conflicts to check this round.
- `nice_to_have.md` slot drift not relevant — T03 does not cite a slot.
- No new HIGH/MEDIUM surfaced from this round's verification. The spec is ready for `/clean-implement` (or autopilot pickup) once M17 closes.
