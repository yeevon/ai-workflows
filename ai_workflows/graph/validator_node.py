"""ValidatorNode adapter (M2 Task 04 — KDR-004,
[architecture.md §4.2 / §8.2](../../design_docs/architecture.md)).

Factory that returns an async LangGraph node pairing with any upstream
``TieredNode``. Parses the upstream node's raw text against a pydantic
schema; on success, writes the parsed instance back into state; on
failure, raises :class:`ai_workflows.primitives.retry.RetryableSemantic`
with a ``revision_hint`` derived from the :class:`pydantic.ValidationError`
so the next retry turn can course-correct.

Budget-exhaustion escalation (M6 Task 07 — resolves M6-T03-ISS-01)
------------------------------------------------------------------
The stock :func:`retrying_edge`'s semantic budget check keys off its
``on_semantic`` *routing target* — typically the upstream LLM node's
name — while :func:`ai_workflows.graph.error_handler.wrap_with_error_handler`
bumps ``state['_retry_counts']`` under the **failing node's own name**.
In the canonical wiring (validator wrapped with ``node_name=X_validator``,
``on_semantic=X``), the edge's budget check therefore always sees ``0``
for semantic failures originating inside the validator, and the retry
loop would run forever.

This module resolves the gap in the validator itself: when
``state['_retry_counts'][node_name]`` has already been bumped
``max_attempts - 1`` times (i.e. this call is the last allowed
attempt and it failed), the validator escalates
:class:`RetryableSemantic` → :class:`NonRetryable`. The paired
``retrying_edge`` then routes to ``on_terminal`` on the next hop
regardless of its own semantic budget check.

The escalation contract requires the outer
:func:`wrap_with_error_handler`'s ``node_name`` to match the one
passed here — otherwise the counter is written under one key and
read under another and the exhaustion never fires. Every caller in
the repo (planner / slice_refactor) already honours that invariant.

Relationship to sibling modules
-------------------------------
* ``graph/tiered_node.py`` (M2 Task 03) — conceptual pair. Every
  ``TieredNode`` in a workflow is followed by a ``validator_node`` per
  KDR-004.
* ``graph/retrying_edge.py`` (M2 Task 07) — consumes the
  ``RetryableSemantic`` bucket raised here and routes the graph back
  to the upstream LLM node. The edge's own budget check is a
  belt-and-braces guard; the authoritative exhaustion signal now
  comes from this module's in-validator escalation (see above).
* ``graph/error_handler.py`` — owns the ``_retry_counts`` bump this
  module reads for its exhaustion check.
* ``primitives/retry.py`` — defines the three-bucket taxonomy. This
  node raises :class:`RetryableSemantic` on every attempt prior to
  the last, then :class:`NonRetryable` on exhaustion.

Pure validation: no LLM call, no cost record, no structured log
emission. Those concerns live at the ``TieredNode`` boundary.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from pydantic import BaseModel, ValidationError

from ai_workflows.primitives.retry import NonRetryable, RetryableSemantic

__all__ = ["validator_node"]

GraphState = Mapping[str, Any]


def validator_node(
    *,
    schema: type[BaseModel],
    input_key: str,
    output_key: str,
    node_name: str,
    max_attempts: int = 3,
) -> Callable[[GraphState], Awaitable[dict[str, Any]]]:
    """Build an async LangGraph node that validates ``state[input_key]``.

    Parameters
    ----------
    schema:
        Pydantic model the raw text must parse into.
    input_key:
        State key holding the upstream node's raw text output.
    output_key:
        State key to which the parsed pydantic instance is written on
        success.
    node_name:
        Identifier used in the ``reason`` string of a raised
        :class:`RetryableSemantic`, **and** the key the in-validator
        exhaustion check reads from ``state['_retry_counts']`` to
        decide when to escalate to :class:`NonRetryable`. Must match
        the ``node_name`` supplied to the outer
        :func:`ai_workflows.graph.error_handler.wrap_with_error_handler`
        call — otherwise the counter is written under one key and read
        under another and the escalation never fires (M6 Task 07 /
        M6-T03-ISS-01). Keep it aligned with the paired ``TieredNode``'s
        ``node_name`` so the retry log line reads naturally.
    max_attempts:
        Attempt budget enforced **here**: on the ``max_attempts``-th
        failing call (prior bumps under ``node_name`` == ``max_attempts - 1``),
        the validator escalates :class:`RetryableSemantic` →
        :class:`NonRetryable` so the paired :func:`retrying_edge`
        routes to ``on_terminal``. Validated ``>= 1`` so a
        mis-configured zero surfaces at build time rather than at run
        time. The edge's own ``policy.max_semantic_attempts`` check is
        a belt-and-braces guard — this validator is the authoritative
        exhaustion signal under the canonical wiring.

    Returns
    -------
    An ``async`` callable suitable for registration as a LangGraph
    node. On success it returns ``{output_key: parsed,
    f"{input_key}_revision_hint": None}`` — clearing any stale hint
    from a prior retry. On :class:`ValidationError`:

    * Attempts 1..``max_attempts - 1``: raises
      :class:`RetryableSemantic` with a human-readable hint
      enumerating the schema mismatches.
    * Attempt ``max_attempts``: raises :class:`NonRetryable` with the
      same hint embedded in the reason so the run log preserves the
      diagnostic trail.
    """
    if max_attempts < 1:
        raise ValueError(f"max_attempts must be >= 1, got {max_attempts!r}")

    async def _node(state: GraphState) -> dict[str, Any]:
        text = state[input_key]
        try:
            parsed = schema.model_validate_json(text)
        except ValidationError as exc:
            revision_hint = _format_revision_hint(schema, exc)
            retry_counts = state.get("_retry_counts") or {}
            prior_failures = retry_counts.get(node_name, 0)
            if prior_failures >= max_attempts - 1:
                raise NonRetryable(
                    f"{node_name}: exhausted semantic retry budget after "
                    f"{prior_failures + 1} attempts — last output still "
                    f"fails {schema.__name__} validation. "
                    f"Last hint: {revision_hint}"
                ) from exc
            raise RetryableSemantic(
                reason=f"{node_name}: output failed {schema.__name__} validation",
                revision_hint=revision_hint,
            ) from exc
        return {
            output_key: parsed,
            f"{input_key}_revision_hint": None,
        }

    return _node


def _format_revision_hint(schema: type[BaseModel], exc: ValidationError) -> str:
    """Turn a pydantic ``ValidationError`` into a prompt-ready hint.

    The hint lists each schema mismatch with its dotted location and
    the pydantic error message so the upstream LLM can see exactly
    which field to fix on the retry turn. Invalid-JSON errors surface
    as a single ``$: <message>`` entry — same structure, different
    root location.
    """
    lines = [
        f"Your previous output did not match the {schema.__name__} schema.",
        "Please revise and re-emit valid JSON. Issues:",
    ]
    for err in exc.errors():
        loc = ".".join(str(part) for part in err.get("loc", ())) or "$"
        msg = err.get("msg", "invalid value")
        lines.append(f"- {loc}: {msg}")
    return "\n".join(lines)
