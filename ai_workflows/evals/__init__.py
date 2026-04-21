"""Eval harness — the prompt-regression guard promised by KDR-004.

This package is the substrate for M7's eval harness. Per the milestone
README at
[design_docs/phases/milestone_7_evals/README.md](../../design_docs/phases/milestone_7_evals/README.md),
the harness captures input/expected-output pairs from real workflow runs
as JSON fixtures under ``evals/`` and replays them against the current
graph to catch the failure modes determinism cannot: prompt-template
drift, validator-schema drift, tier-wiring drift, and (in live mode)
provider-output drift.

Task 01 lands the schema substrate only: ``EvalCase``, ``EvalSuite``,
``EvalTolerance`` pydantic v2 models plus ``save_case`` / ``load_suite``
/ ``load_case`` storage helpers. Downstream consumers:

* M7 Task 02 — ``CaptureCallback`` in :mod:`ai_workflows.graph` emits
  one :class:`EvalCase` per LLM-node call during an opted-in live run.
* M7 Task 03 — ``EvalRunner`` loads suites via :func:`load_suite` and
  replays them in deterministic (stub adapter) or live mode.
* M7 Task 04 — ``aiw eval capture`` / ``aiw eval run`` CLI commands
  drive capture + replay.

Architectural placement (import-linter contract 4 of 4, added by this
task): ``evals`` may import :mod:`ai_workflows.primitives` and
:mod:`ai_workflows.graph` (T03's replay runner needs ``TieredNode`` /
``ValidatorNode`` adapters) but must not reach workflows or surfaces.
``graph`` must not import evals — a companion AST-grep test enforces
the one-direction rule that import-linter cannot express cleanly as a
single contract. ``workflows`` imports evals at dispatch time
(M7 T02 ``_dispatch.run_workflow`` attaches ``CaptureCallback`` when
``AIW_CAPTURE_EVALS`` is set). Surfaces (:mod:`ai_workflows.cli`,
:mod:`ai_workflows.mcp`) may import ``evals`` at T04 to drive the
replay runner.

Schemas are bare-typed per KDR-010 (no ``Field(min_length/...)``
bounds) — evals data is mostly already-validated workflow output and
we match the same light-touch schema discipline the rest of the
codebase uses for internal pydantic models.
"""

from ai_workflows.evals.capture_callback import CaptureCallback, output_schema_fqn
from ai_workflows.evals.runner import EvalReport, EvalResult, EvalRunner
from ai_workflows.evals.schemas import EvalCase, EvalSuite, EvalTolerance
from ai_workflows.evals.storage import (
    EVALS_ROOT,
    default_evals_root,
    fixture_path,
    load_case,
    load_suite,
    save_case,
)

__all__ = [
    "CaptureCallback",
    "EvalCase",
    "EvalReport",
    "EvalResult",
    "EvalRunner",
    "EvalSuite",
    "EvalTolerance",
    "EVALS_ROOT",
    "default_evals_root",
    "fixture_path",
    "load_case",
    "load_suite",
    "output_schema_fqn",
    "save_case",
]
