"""Provider-driver primitives (M2 Task 01 — KDR-007,
[architecture.md §4.1](../../../design_docs/architecture.md)).

Subpackage that carries the post-pivot provider drivers: the LiteLLM
adapter (this task) and the ``ClaudeCodeSubprocess`` driver (M2
Task 02). Both return ``(text, TokenUsage)`` and both keep retry
classification *out* of the driver — the three-bucket taxonomy
(KDR-006) runs above this layer via the M2 ``TieredNode`` /
``RetryingEdge`` pair.

Relationship to sibling modules
-------------------------------
* ``primitives/tiers.py`` — owns ``LiteLLMRoute`` / ``ClaudeCodeRoute``,
  the inputs to these adapters.
* ``primitives/cost.py`` — owns ``TokenUsage``, the second half of the
  return tuple.
* ``primitives/retry.py`` — classifies the exceptions these adapters
  re-raise; the adapters themselves are classification-free.
"""
