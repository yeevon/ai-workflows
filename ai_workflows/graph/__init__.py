"""LangGraph adapters over primitives. Populated in M2.

Per [architecture.md §3 / §4.2](../../design_docs/architecture.md), the
``graph`` layer holds LangGraph adapters (``TieredNode``,
``ValidatorNode``, ``HumanGate``, ``CostTrackingCallback``,
``RetryingEdge``, checkpointer wiring) that translate primitives
semantics into LangGraph idioms. This layer replaces the pre-pivot
``components/`` package, which M1 Task 12 removes.

Architectural rule (enforced by ``import-linter``): ``graph`` may
import :mod:`ai_workflows.primitives` only — never
:mod:`ai_workflows.workflows` or the surfaces
(:mod:`ai_workflows.cli`, :mod:`ai_workflows.mcp`).
"""
