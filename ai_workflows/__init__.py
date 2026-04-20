"""ai-workflows: composable AI-workflow framework on LangGraph + MCP.

The package is split into four strictly layered sub-packages per
[architecture.md §3](../design_docs/architecture.md):

* :mod:`ai_workflows.primitives` — storage, cost, tiers, providers,
  retry, logging. Has no dependencies on higher layers.
* :mod:`ai_workflows.graph` — LangGraph adapters (``TieredNode``,
  ``ValidatorNode``, ``HumanGate``, ``CostTrackingCallback``,
  ``RetryingEdge``) over primitives. Populated in M2.
* :mod:`ai_workflows.workflows` — concrete LangGraph ``StateGraph``
  modules. Populated from M3 onward.
* :mod:`ai_workflows.cli` + :mod:`ai_workflows.mcp` — surfaces. The
  ``aiw`` CLI and the FastMCP server both consume
  :mod:`ai_workflows.workflows` and :mod:`ai_workflows.primitives`.

Layer boundaries are enforced at lint time by ``import-linter``
contracts declared in ``pyproject.toml`` (M1 Task 12 installs the
four-layer shape).
"""

__version__ = "0.1.0"
