"""Workflows layer — concrete workflow definitions.

Each module in here exports a built LangGraph ``StateGraph`` per
[architecture.md §4.3](../../design_docs/architecture.md); a workflow
is a Python module, not a directory of YAML + prompts. Graph instances
are registered by name so surfaces (``aiw`` CLI, MCP server) can reach
them.

Initial workflows (filled in over M3, M5, M6):

* ``planner`` (M3) — two-phase sub-graph (explorer → planner →
  validator); reusable as a sub-graph.
* ``slice_refactor`` (M5) — outermost DAG wiring the ``planner``
  sub-graph to parallel per-slice worker nodes.
* ``jvm_modernization`` (M6) — the original motivating use case.

The pre-pivot reference to a ``workflow_hash`` drift guard has been
retired per [ADR-0001](../../design_docs/adr/0001_workflow_hash.md);
if ``aiw resume`` eventually needs a source-code drift guard, it will
be designed against the module-based shape in M3, not the directory
hash.

Architectural rule: workflows are the top of the stack. Nothing imports
from this package — it's strictly an entry-point layer.
"""
