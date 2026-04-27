# Writing a Graph Primitive

> **Audience:** This guide is for **framework contributors** authoring new graph-layer primitives — not for downstream consumers. If you're an external workflow author, see [`writing-a-workflow.md`](writing-a-workflow.md) (Tier 1 + Tier 2) and [`writing-a-custom-step.md`](writing-a-custom-step.md) (Tier 3) instead. The four-tier extension model is documented in [`design_docs/architecture.md` §Extension model](../design_docs/architecture.md#extension-model----extensibility-is-a-first-class-capability) (builder-only, on design branch).

A walkthrough for extending the graph layer itself — adding a new adapter under `ai_workflows/graph/` that composes existing primitives. The "graph primitives" referred to here are the nodes, edges, and callbacks that LangGraph workflows compose: `TieredNode`, `ValidatorNode`, `HumanGate`, `RetryingEdge`, `CostTrackingCallback`, and the `SqliteSaver` checkpointer wrapper.

If you want to write a workflow that composes existing primitives rather than extending the graph layer, see [writing-a-workflow.md](writing-a-workflow.md). This document is for the case where the same node-wiring pattern has appeared in two or more workflows and is ready to be promoted to the `graph/` layer.

## When to write a new graph primitive

This is the **Tier 3 → graph-layer graduation path**: when a custom step type proves broadly useful — the same *wiring* pattern (not just the step semantics) appears in two or more workflows — it graduates from a custom step in the workflows layer to a graph primitive in `ai_workflows/graph/`. Solo usage or step-only reuse stays in the workflows layer; only wiring patterns that compose across step types belong in the graph layer.

Heuristic: **if the same wiring pattern appears in two or more workflows**, promote it to `ai_workflows/graph/`. Solo usage stays inline in the workflow module. This keeps the graph layer small and every primitive earn-its-weight-tested.

See [`design_docs/architecture.md` §Extension model](../design_docs/architecture.md#extension-model----extensibility-is-a-first-class-capability) (builder-only, on design branch) for the full four-tier framing: Tier 1 (compose) → Tier 2 (parameterise) → Tier 3 (custom step) → Tier 4 (this guide, graph-layer extension for framework contributors).

Counter-indicators — do not promote if:

- The pattern is one node, no composition. A bare `TieredNode` call does not need a wrapper; workflows use `TieredNode` directly.
- The pattern couples to a specific workflow's state shape. Graph primitives take state through LangGraph's usual channels; if a wrapper reaches into `state["my_workflow_specific_field"]`, it belongs in the workflow, not the graph layer.
- The pattern would pull a new dependency into `pyproject.toml`. New deps require a new KDR in `design_docs/architecture.md §6` plus an ADR — not a primitive.

## The `graph/` layer contract

The graph layer imports from `primitives` + stdlib + `langgraph`. It does **not** import from `workflows/` or any surface (`cli.py`, `mcp/`). The import-linter contract at [`pyproject.toml` `[tool.importlinter]`](../pyproject.toml) enforces this — `uv run lint-imports` will report a broken contract if a graph primitive reaches upward.

Every graph primitive:

- Is a class (preferred, for composability) or a function that returns a LangGraph `node` or a `Runnable`.
- Owns one concern. A primitive that combines cost tracking with retry routing is two primitives — split them.
- Has a module docstring citing the KDR(s) it implements and the primitives it composes over.
- Has a public class or function docstring describing its state-channel inputs and outputs.
- Emits `StructuredLogger` events at entry and exit.

## The composition pattern

Every existing primitive wraps something. `TieredNode` wraps a provider adapter from `primitives`. `ValidatorNode` wraps a Pydantic model's `model_validate`. `CostTrackingCallback` wraps a LangGraph callback. `RetryingEdge` wraps a conditional edge with bucket-classified routing.

The pattern for a new primitive is: **take the thing being wrapped as a constructor argument, expose a `__call__` or `node` method LangGraph can wire, and delegate the actual work to the wrapped primitive.** Do not reimplement; compose.

## Worked example — `MaxLatencyNode`

A primitive that wraps an arbitrary inner node, records wall-clock runtime, and emits a `StructuredLogger` event at node exit. Useful for per-node latency budgets in production workflows.

```python
"""MaxLatencyNode — wall-clock latency wrapper for an inner graph node.

Added per [M<N> Task <NN>](...) to surface per-node latency into the
StructuredLogger stream without reaching for an external observability
backend (KDR-007 — StructuredLogger only at v0.1.0).

Composes over: an arbitrary callable inner node. Emits: a single
``max_latency_node.exit`` event with ``{node_name, duration_ms}``.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from ai_workflows.primitives.logging import StructuredLogger


class MaxLatencyNode:
    """Wrap ``inner`` and log its wall-clock duration at exit."""

    def __init__(
        self,
        inner: Callable[[dict[str, Any]], dict[str, Any]],
        *,
        name: str,
        logger: StructuredLogger,
    ) -> None:
        self._inner = inner
        self._name = name
        self._logger = logger

    def __call__(self, state: dict[str, Any]) -> dict[str, Any]:
        start = time.monotonic()
        try:
            return self._inner(state)
        finally:
            duration_ms = (time.monotonic() - start) * 1000
            self._logger.info(
                "max_latency_node.exit",
                node_name=self._name,
                duration_ms=round(duration_ms, 2),
            )
```

The wrap-and-delegate shape here matches `CostTrackingCallback` at [`ai_workflows/graph/cost_callback.py`](../ai_workflows/graph/cost_callback.py) — read that module for a production-grade reference.

## Testing a graph primitive

Unit-test against a trivial LangGraph — one node, one edge, deterministic input. Compose over `primitives` stubs (e.g. `StubLLMAdapter` at [`ai_workflows/evals/_stub_adapter.py`](../ai_workflows/evals/_stub_adapter.py)) rather than mocking LangGraph itself. LangGraph's state machine is fast and deterministic; mocking it loses more coverage than it saves.

The tests under `tests/graph/` are the reference gallery.

## KDR alignment self-check

Before opening a PR for a new primitive, verify:

- **KDR-003** — the module does not import `anthropic` and does not read `ANTHROPIC_API_KEY`. Claude access goes through `ClaudeCodeSubprocess` (OAuth CLI only).
- **KDR-006** — no bespoke `try`/`except` retry loop. Retry routing goes through `RetryingEdge`.
- **KDR-007** — only `StructuredLogger` is used for observability. No Langfuse, OpenTelemetry, or LangSmith imports.
- **KDR-009** — no hand-rolled checkpoint writes. If the primitive needs to persist state, it delegates to LangGraph's `SqliteSaver` or to `SQLiteStorage` from the primitives layer.

A primitive that violates any of the four is a design drift — the audit that grades it will flag it HIGH and ask for a rework or an ADR that retires the KDR.

## Where to deep-dive

- `design_docs/architecture.md §3` (four-layer contract), `§9` (KDR grid), and `§Extension model` (the full four-tier extension framing) — the full context for every rule above.
- The existing primitives in [`ai_workflows/graph/`](../ai_workflows/graph/) — every one is a composition reference for a new primitive.
