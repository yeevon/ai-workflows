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

0.1.2 patch: ``__version__`` below is the **single source of truth**
for the package's version string. ``pyproject.toml`` declares
``dynamic = ["version"]`` and ``[tool.hatch.version]`` points at this
module — hatchling parses the ``__version__`` assignment at build
time and writes it into the wheel's metadata. Consumers that need
the version at runtime can read either ``ai_workflows.__version__``
(this dunder, direct) or
``importlib.metadata.version("jmdl-ai-workflows")`` (the installed
wheel's metadata); both resolve to the same string. A regression
test pins that invariant.
"""

__version__ = "0.3.0"
