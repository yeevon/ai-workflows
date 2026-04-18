"""ai-workflows: a composable framework for building AI workflows.

The package is split into three strictly layered sub-packages:

* :mod:`ai_workflows.primitives` — low-level building blocks (LLM client
  factory, tool registry, storage, cost tracking, retry, logging). Has no
  dependencies on higher layers.
* :mod:`ai_workflows.components` — reusable mid-level building blocks
  (Worker, Validator, Pipeline, AgentLoop, HumanGate, …). Built on top of
  primitives.
* :mod:`ai_workflows.workflows` — concrete workflow definitions that wire
  components together for specific tasks (JVM modernization, doc generation,
  code review, …).

Layer boundaries are enforced at lint time by ``import-linter`` contracts
declared in ``pyproject.toml``. See ``design_docs/`` for the full
architecture.
"""

__version__ = "0.1.0"
