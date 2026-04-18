"""Workflows layer — concrete workflow definitions.

Each subpackage in here is a single workflow: a directory containing the
component wiring, prompt templates, and any workflow-specific tools. The
content hash of a workflow directory is what ``aiw resume`` compares
against to detect breaking edits between runs (see ``workflow_hash`` in
:mod:`ai_workflows.primitives`).

Initial workflows (filled in over M3, M5, M6):

* ``test_coverage_gap_fill`` (M3) — first end-to-end workflow, uses the
  Pipeline component and Haiku.
* ``slice_refactor`` (M5) — multi-file refactor; first DAG workflow.
* ``jvm_modernization`` (M6) — the original motivating use case.

Architectural rule: workflows are the top of the stack. Nothing imports
from this package — it's strictly an entry-point layer.
"""
