"""Primitives layer — the foundation of ai-workflows.

This package contains the lowest-level building blocks of the framework,
aligned with [architecture.md §4.1](../../design_docs/architecture.md):
``storage``, ``cost``, ``tiers``, ``retry``, and ``logging``. Provider
drivers (LiteLLM adapter + Claude Code subprocess) land under
``primitives/providers`` in M2; the pre-pivot ``llm/`` subpackage was
removed in M1 Task 03 per KDR-001 / KDR-005. The pre-pivot ``tools/``
subpackage is removed in M1 Task 04 per KDR-002 / KDR-008. The
pre-pivot ``workflow_hash`` primitive is retired in M1 Task 10 per
[ADR-0001](../../design_docs/adr/0001_workflow_hash.md) — directory
hashing does not fit the module-based workflow layout declared in
[architecture.md §4.3](../../design_docs/architecture.md), and a
drift-detect primitive, if needed, is deferred to M3 resume design.

Architectural rule (enforced by ``import-linter``): nothing in this
package is allowed to import from :mod:`ai_workflows.graph`,
:mod:`ai_workflows.workflows`, :mod:`ai_workflows.cli`, or
:mod:`ai_workflows.mcp`. Primitives are the bedrock; higher layers
depend on them, never the other way around. M1 Task 12 installs the
four-layer contract (primitives → graph → workflows → surfaces) that
enforces this rule.
"""
