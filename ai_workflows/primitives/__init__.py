"""Primitives layer — the foundation of ai-workflows.

This package contains the lowest-level building blocks of the framework,
aligned with [architecture.md §4.1](../../design_docs/architecture.md):
``storage``, ``cost``, ``tiers``, ``retry``, ``logging``, and
``workflow_hash``. Provider drivers (LiteLLM adapter + Claude Code
subprocess) land under ``primitives/providers`` in M2; the pre-pivot
``llm/`` subpackage was removed in M1 Task 03 per KDR-001 / KDR-005.
The pre-pivot ``tools/`` subpackage is removed in M1 Task 04 per
KDR-002 / KDR-008.

Architectural rule (enforced by ``import-linter``): nothing in this package
is allowed to import from :mod:`ai_workflows.components` or
:mod:`ai_workflows.workflows`. Primitives are the bedrock; higher layers
depend on them, never the other way around.
"""
