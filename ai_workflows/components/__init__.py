"""Components layer — reusable mid-level workflow building blocks.

Components compose primitives into named, configurable units that workflows
wire together. The taxonomy (filled in over M2 and M4) is:

* ``Worker`` — single-shot LLM call with strong determinism guarantees.
* ``Validator`` — runs after a Worker / AgentLoop output to gate progress.
* ``Fanout`` — parallel map over a small set of inputs (5–8 max).
* ``Pipeline`` (M2) — linear sequence of components. The default workflow
  shape until DAG orchestration lands.
* ``AgentLoop`` (M4) — open-ended tool-using loop on top of
  ``pydantic_ai.Agent``. Documented weak guarantee — outputs must be gated
  by a Validator.
* ``Planner`` (M4) — two-phase exploration → plan generation.
* ``Orchestrator`` (M4) — DAG executor that promotes ``Pipeline``.
* ``HumanGate`` (M4) — pauses execution for human review; survives restart.

Architectural rules (enforced by ``import-linter``):

1. Components MAY import primitives, but MUST NOT import workflows.
2. Components MAY import each other's public surface, but MUST NOT touch
   another component's underscore-prefixed internals.
"""
