"""ValidatorNode adapter (M2 Task 04 — KDR-004,
[architecture.md §4.2 / §8.2](../../design_docs/architecture.md)).

Factory that returns an async LangGraph node pairing with any upstream
``TieredNode``. Parses the upstream node's raw text against a pydantic
schema; on success, writes the parsed instance back into state; on
failure, raises :class:`ai_workflows.primitives.retry.RetryableSemantic`
with a ``revision_hint`` derived from the :class:`pydantic.ValidationError`
so the next retry turn can course-correct.

Relationship to sibling modules
-------------------------------
* ``graph/tiered_node.py`` (M2 Task 03) — conceptual pair. Every
  ``TieredNode`` in a workflow is followed by a ``validator_node`` per
  KDR-004.
* ``graph/retrying_edge.py`` (M2 Task 07) — consumes the
  ``RetryableSemantic`` bucket raised here and routes the graph back
  to the upstream LLM node. ``max_attempts`` is a soft documentation
  hint; enforcement lives in ``RetryingEdge``.
* ``primitives/retry.py`` — defines the three-bucket taxonomy. This
  node only ever raises ``RetryableSemantic`` (never ``NonRetryable``)
  because a schema miss is always revisable by re-prompting the LLM.

Pure validation: no LLM call, no cost record, no structured log
emission. Those concerns live at the ``TieredNode`` boundary.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from pydantic import BaseModel, ValidationError

from ai_workflows.primitives.retry import RetryableSemantic

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
        :class:`RetryableSemantic`. Keep it aligned with the paired
        ``TieredNode``'s ``node_name`` so the retry log line reads
        naturally.
    max_attempts:
        Soft documentation hint for callers and log readers. **Not
        enforced here** — the attempt budget is owned by
        :class:`ai_workflows.graph.retrying_edge.RetryingEdge` (M2 Task
        07). Validated ``>= 1`` so a mis-configured zero surfaces at
        build time rather than at run time.

    Returns
    -------
    An ``async`` callable suitable for registration as a LangGraph
    node. On success it returns ``{output_key: parsed,
    f"{input_key}_revision_hint": None}`` — clearing any stale hint
    from a prior retry. On any :class:`ValidationError` (invalid JSON,
    missing field, wrong type) it raises
    :class:`RetryableSemantic` with a human-readable hint that
    enumerates the schema mismatches.
    """
    if max_attempts < 1:
        raise ValueError(f"max_attempts must be >= 1, got {max_attempts!r}")

    async def _node(state: GraphState) -> dict[str, Any]:
        text = state[input_key]
        try:
            parsed = schema.model_validate_json(text)
        except ValidationError as exc:
            raise RetryableSemantic(
                reason=f"{node_name}: output failed {schema.__name__} validation",
                revision_hint=_format_revision_hint(schema, exc),
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
