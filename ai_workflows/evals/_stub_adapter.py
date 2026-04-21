"""Stub LLM adapter for deterministic eval replay (M7 Task 03).

Shape-matches :class:`ai_workflows.primitives.llm.litellm_adapter.LiteLLMAdapter`
so the :class:`ai_workflows.evals.EvalRunner` can monkey-patch
``tiered_node_module.LiteLLMAdapter`` during a case replay and have
:func:`ai_workflows.graph.tiered_node.tiered_node` pass its ``complete``
call through the stub instead of a live provider. The stub reads its
answer from a class-level ``_pending_output`` slot the runner arms
before every ``ainvoke``:

* :meth:`StubLLMAdapter.arm` — set the pending case's
  ``expected_output`` and clear the call log.
* :meth:`StubLLMAdapter.disarm` — revert to the "no case armed"
  state so a stray call raises loudly (the AC-5 invariant:
  incomplete suites must not silently pass).

Why a class-level slot rather than ``__init__`` state
-----------------------------------------------------
:func:`ai_workflows.graph.tiered_node._dispatch` instantiates the
adapter **fresh** per node call (``adapter = LiteLLMAdapter(...)``),
so instance-level state would be thrown away before the stub could
see a second case. The class slot mirrors the T02 integration tests'
``_StubLiteLLMAdapter.script`` pattern — same idea, same reason.

Single-case-per-invoke invariant
--------------------------------
The runner builds a single-node replay graph per case (``START →
<node> → <validator> → END``), so at most one adapter call fires per
invoke. A second concurrent replay would race on the class slot —
the runner therefore replays cases sequentially. This is the T03
spec's explicit shape ("each case runs through a single-node replay
graph"); parallelism is out of scope (revisit post-M7 if the need is
real).

Not in the public export list
-----------------------------
Underscore-prefixed module. Consumed by :mod:`ai_workflows.evals.runner`
only — callers drive replay through :class:`EvalRunner`, not this
stub directly.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from ai_workflows.primitives.cost import TokenUsage
from ai_workflows.primitives.tiers import LiteLLMRoute

__all__ = ["StubAdapterMissingCaseError", "StubLLMAdapter"]


class StubAdapterMissingCaseError(RuntimeError):
    """Raised when the stub fires with no armed case.

    Surfaces AC-5: "the stub adapter raises loudly when a case is
    missing — incomplete suites do not silently pass". The runner
    catches this at the replay boundary and stamps the failing
    :class:`EvalResult` with ``error='case not found in suite'``.
    """


class StubLLMAdapter:
    """In-process LLM adapter that returns an armed case's expected output.

    Class-level state — see module docstring for the "why fresh
    adapters every call" justification. Tests and the runner both
    call :meth:`arm` / :meth:`disarm` to control which output the
    next ``complete`` call returns.
    """

    _pending_output: str | None = None
    _calls: list[dict[str, Any]] = []

    def __init__(self, *, route: LiteLLMRoute, per_call_timeout_s: int) -> None:
        """Match :class:`LiteLLMAdapter`'s ``__init__`` signature verbatim.

        ``route`` + ``per_call_timeout_s`` are stored so the stub can
        stamp them into the synthetic :class:`TokenUsage` it returns
        (the runner never reads ``per_call_timeout_s`` back, but
        ``route.model`` shows up in the call log for debuggability).
        """

        self._route = route
        self._per_call_timeout_s = per_call_timeout_s

    async def complete(
        self,
        *,
        system: str | None,
        messages: list[dict],
        response_format: type[BaseModel] | None = None,
    ) -> tuple[str, TokenUsage]:
        """Return the armed case's expected output + a zero-cost TokenUsage."""

        cls = type(self)
        cls._calls.append(
            {
                "route": self._route.model,
                "system": system,
                "messages": messages,
                "response_format": (
                    response_format.__name__ if response_format else None
                ),
            }
        )
        if cls._pending_output is None:
            raise StubAdapterMissingCaseError(
                "case not found in suite: StubLLMAdapter fired with no "
                "armed case (the runner did not arm the stub before "
                "ainvoke — suite likely missing a case for this node)"
            )
        return cls._pending_output, TokenUsage(
            input_tokens=0,
            output_tokens=0,
            cost_usd=0.0,
            model=self._route.model,
        )

    @classmethod
    def arm(cls, *, expected_output: str) -> None:
        """Pin the string the next ``complete`` call will return."""

        cls._pending_output = expected_output
        cls._calls = []

    @classmethod
    def disarm(cls) -> None:
        """Clear the armed output so any further ``complete`` call raises."""

        cls._pending_output = None

    @classmethod
    def calls(cls) -> list[dict[str, Any]]:
        """Return a copy of the per-arm call log (for test assertions)."""

        return list(cls._calls)
