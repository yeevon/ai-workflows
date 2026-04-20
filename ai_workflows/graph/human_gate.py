"""HumanGate adapter (M2 Task 05 — KDR-001, KDR-009,
[architecture.md §4.2 / §8.3](../../design_docs/architecture.md)).

Factory that returns an async LangGraph node wrapping
:func:`langgraph.types.interrupt` with the strict-review semantics from
[architecture.md §8.3](../../design_docs/architecture.md). Persists the
gate prompt on pause and the user response on resume through the
:class:`ai_workflows.primitives.storage.StorageBackend` protocol
(trimmed by M1 Task 05), so every gate transition remains auditable
from the run log without this node owning any checkpoint state of its
own — LangGraph's ``SqliteSaver`` (KDR-009) does that.

Relationship to sibling modules
-------------------------------
* ``graph/tiered_node.py`` (M2 Task 03) — dependency-resolution peer.
  Both read runtime collaborators (storage here, tier registry there)
  from LangGraph's ``config["configurable"]`` dict rather than from
  module-level globals, so workflows can swap backends per-run.
* ``graph/validator_node.py`` (M2 Task 04) — sibling factory. Both are
  thin wrappers over LangGraph primitives with no primitives-layer
  dependency churn.
* ``primitives/storage.py`` — ``record_gate`` / ``record_gate_response``
  come from the trimmed M1 Task 05 protocol. No new schema is required
  by this task.

No in-house timeout plumbing
----------------------------
Architecture §4.2 + §8.3 both say the node does **not** enforce a
timeout itself — timeout policy is a graph/surface concern. ``timeout_s``
and ``default_response_on_timeout`` therefore ship only as part of the
interrupt payload so a higher layer can enforce them. When
``strict_review=True`` the payload sets both fields to ``None``, making
the ignored-ness of the timeout explicit to any observer.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.types import interrupt

__all__ = ["human_gate"]

GraphState = Mapping[str, Any]


def human_gate(
    *,
    gate_id: str,
    prompt_fn: Callable[[GraphState], str],
    strict_review: bool = False,
    timeout_s: int | None = 1800,
    default_response_on_timeout: str = "abort",
) -> Callable[[GraphState, RunnableConfig], Awaitable[dict[str, Any]]]:
    """Build an async LangGraph node wrapping ``interrupt`` with gate persistence.

    Parameters
    ----------
    gate_id:
        Stable identifier for this gate within a run. Used as part of
        the ``(run_id, gate_id)`` primary key on ``gate_responses`` and
        as the suffix of the state key the response is written to
        (``f"gate_{gate_id}_response"``).
    prompt_fn:
        Pure function that renders the review prompt from the current
        graph state. Called once per node invocation; the string it
        returns is both persisted via ``Storage.record_gate`` and
        forwarded as part of the ``interrupt`` payload.
    strict_review:
        When ``True``, no timeout is enforced and the ``timeout_s`` /
        ``default_response_on_timeout`` arguments are set to ``None`` in
        the interrupt payload. The gate can only be cleared by an
        explicit resume. Matches [architecture.md §8.3](../../design_docs/architecture.md).
    timeout_s:
        Wall-clock seconds the surface/graph may wait before applying
        ``default_response_on_timeout``. Only forwarded to the
        interrupt payload when ``strict_review`` is ``False``; the node
        itself never starts a timer.
    default_response_on_timeout:
        Response to apply if the surface's timeout fires. Forwarded as
        part of the interrupt payload when ``strict_review`` is
        ``False``; ignored when strict.

    Returns
    -------
    An ``async`` callable taking ``(state, config)``. The factory leans
    on LangGraph's runtime config dict — ``state["run_id"]`` names the
    run, ``config["configurable"]["storage"]`` supplies the
    ``StorageBackend``. On first invocation the node writes the pending
    gate row, then raises the LangGraph interrupt that pauses the
    graph. On resume (delivered via ``Command(resume=...)``) the node
    re-runs from the top — ``record_gate`` is a no-op upsert, ``interrupt``
    returns the resume value, ``record_gate_response`` stamps the row,
    and ``{f"gate_{gate_id}_response": response}`` flows into state.
    """

    async def _node(state: GraphState, config: RunnableConfig) -> dict[str, Any]:
        run_id = state["run_id"]
        storage = config["configurable"]["storage"]
        prompt = prompt_fn(state)

        await storage.record_gate(run_id, gate_id, prompt, strict_review)

        payload: dict[str, Any] = {
            "gate_id": gate_id,
            "prompt": prompt,
            "strict_review": strict_review,
            "timeout_s": None if strict_review else timeout_s,
            "default_response_on_timeout": (
                None if strict_review else default_response_on_timeout
            ),
        }
        response = interrupt(payload)

        await storage.record_gate_response(run_id, gate_id, response)
        return {f"gate_{gate_id}_response": response}

    return _node
