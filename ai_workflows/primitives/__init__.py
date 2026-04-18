"""Primitives layer — the foundation of ai-workflows.

This package contains the lowest-level building blocks of the framework:

* :mod:`ai_workflows.primitives.llm` — typed LLM message/response model and
  the model factory that turns a tier name into a configured pydantic-ai
  ``Model`` instance.
* :mod:`ai_workflows.primitives.tools` — tool registry, the standard
  filesystem / shell / http / git tool implementations, and the forensic
  logger that records every tool call for post-hoc auditing.
* ``tiers``, ``workflow_hash``, ``storage``, ``cost``, ``retry``, ``logging``
  — single-file modules covering tier loading, content hashing of a workflow
  directory, SQLite-backed run storage, budget enforcement, retry policy,
  and structured logging respectively.

Architectural rule (enforced by ``import-linter``): nothing in this package
is allowed to import from :mod:`ai_workflows.components` or
:mod:`ai_workflows.workflows`. Primitives are the bedrock; higher layers
depend on them, never the other way around.
"""
