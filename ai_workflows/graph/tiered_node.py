"""TieredNode adapter (M2 Task 03 — KDR-003, KDR-004, KDR-006, KDR-007,
[architecture.md §4.2](../../design_docs/architecture.md)).

Factory that returns an async LangGraph node for a logical provider tier
("planner", "implementer", "local_coder", ...). On invocation the node
resolves the tier via an injected ``TierRegistry``-shaped mapping,
dispatches to :class:`LiteLLMAdapter` or :class:`ClaudeCodeSubprocess`
based on the route kind, records the call with the graph's
:class:`CostTrackingCallback`, emits exactly one structured-log record
per invocation (architecture §8.1 shape), and classifies any raised
exception via the three-bucket taxonomy (KDR-006) so
:class:`RetryingEdge` can route.

Contracts & design choices
--------------------------
* **No module-level globals.** The tier registry, cost callback, run id,
  per-tier semaphores, and (Claude Code) pricing table are all passed
  via LangGraph's ``RunnableConfig``'s ``configurable`` dict. The factory
  is stateless across runs — one node instance can safely serve many
  concurrent graph runs.
* **Per-tier semaphore enforcement.** ``TierConfig.max_concurrency`` is
  enforced *inside* the node function via an ``asyncio.Semaphore``
  keyed by tier name and provided by the caller. Enforcing here (not in
  the adapter) keeps the adapter dependency-free and lets a workflow
  author share one semaphore across many nodes that target the same
  tier.
* **Exception handling (option (b) from M2-T07-ISS-01).** The node
  raises the classified bucket (``RetryableTransient`` or
  ``NonRetryable``) verbatim — preserving the task spec's
  "adapter raises ``litellm.RateLimitError`` → node raises
  ``RetryableTransient``" test contract. A LangGraph-native error
  handler wrapper (to be wired by M2 Task 08 per the deferred issue)
  is what converts the raised bucket into the state-update shape
  :class:`RetryingEdge` reads. On the success path the node explicitly
  clears ``state['last_exception']`` (returning ``None`` for the key)
  so a subsequent retry turn does not re-fire on stale data — this is
  the T07 carry-over's "clear on success" requirement and it lands
  here regardless of which option the integration picks.
* **Exactly-once invariants.** Per-invocation: one provider call, one
  :meth:`CostTracker.record` via the callback (success path only —
  a failed invocation has no :class:`TokenUsage` to record), and one
  structured log record (success or failure). Failures log at ``ERROR``
  with ``event="node_failed"`` and the classified bucket in the
  ``bucket`` extra.
* **Tier annotation on usage.** Provider adapters do not know the
  logical tier (``"planner"``/``"implementer"``/...); this node stamps
  ``TokenUsage.tier`` before handing the record to the callback so
  :meth:`CostTracker.by_tier` groups correctly.

Relationship to sibling modules
-------------------------------
* ``primitives/llm/litellm_adapter.py`` (M2 Task 01) — the LiteLLM
  dispatch path. Used for ``LiteLLMRoute`` tiers (Gemini + Ollama/Qwen).
* ``primitives/llm/claude_code.py`` (M2 Task 02) — the Claude Code CLI
  dispatch path. Used for ``ClaudeCodeRoute`` tiers; requires a
  ``pricing`` table in the ``configurable`` dict so the driver can
  compute per-call cost.
* ``graph/cost_callback.py`` (M2 Task 06) — single invocation surface
  for the per-run ledger + budget cap.
* ``graph/validator_node.py`` (M2 Task 04) — conceptually paired per
  KDR-004. Every ``TieredNode`` output is validated by a following
  ``validator_node``.
* ``graph/retrying_edge.py`` (M2 Task 07) — reads ``last_exception`` /
  ``_retry_counts`` / ``_non_retryable_failures`` out of state. This
  module raises; the deferred wrapper (M2 Task 08) does the write.
* ``primitives/retry.py`` — :func:`classify` maps provider exceptions
  to the three-bucket taxonomy; :class:`RetryableTransient` /
  :class:`NonRetryable` / :class:`RetryableSemantic` are the bucket
  types.
* ``primitives/logging.py`` — :func:`log_node_event` enforces the §8.1
  field set; this module is the primary emitter of that record shape.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable, Mapping
from typing import Any

import structlog
from pydantic import BaseModel

from ai_workflows.graph.cost_callback import CostTrackingCallback
from ai_workflows.primitives.circuit_breaker import CircuitBreaker, CircuitOpen
from ai_workflows.primitives.cost import TokenUsage
from ai_workflows.primitives.llm.claude_code import ClaudeCodeSubprocess
from ai_workflows.primitives.llm.litellm_adapter import LiteLLMAdapter
from ai_workflows.primitives.logging import log_node_event
from ai_workflows.primitives.retry import (
    NonRetryable,
    RetryableSemantic,
    RetryableTransient,
    classify,
)
from ai_workflows.primitives.tiers import (
    ClaudeCodeRoute,
    LiteLLMRoute,
    ModelPricing,
    TierConfig,
)

__all__ = ["tiered_node"]

_MID_RUN_TIER_OVERRIDES_STATE_KEY = "_mid_run_tier_overrides"
"""State key carrying ``dict[logical, replacement]`` for the M8 T04
fallback gate: the ``FALLBACK`` choice stamps this key so subsequent
:func:`tiered_node` invocations resolve the tripped tier to its
workflow-declared replacement for the remainder of the run."""

GraphState = Mapping[str, Any]

_LOG = structlog.get_logger(__name__)


def tiered_node(
    *,
    tier: str,
    prompt_fn: Callable[[GraphState], tuple[str | None, list[dict]]],
    output_schema: type[BaseModel] | None = None,
    node_name: str,
) -> Callable[[GraphState, Any], Awaitable[dict[str, Any]]]:
    """Build an async LangGraph node bound to a logical tier.

    Parameters
    ----------
    tier:
        Logical tier name (``"planner"`` / ``"implementer"`` /
        ``"local_coder"`` / ...). Resolved at invocation time via the
        ``tier_registry`` in the LangGraph ``config.configurable`` dict.
    prompt_fn:
        Synchronous builder that reads current graph state and returns
        ``(system, messages)`` — the provider call's input. ``system``
        may be ``None``; ``messages`` is a list of ``{"role", "content"}``
        dicts in OpenAI / LiteLLM shape.
    output_schema:
        Optional pydantic model forwarded to the provider as
        ``response_format``. LiteLLM uses it for native structured-output
        on supporting providers; the ``ClaudeCodeSubprocess`` driver
        accepts it for signature parity but ignores it. Validation is
        the paired ``validator_node``'s job (KDR-004) regardless.
    node_name:
        Identifier used in the structured log record, as the state key
        the raw text lands under (``f"{node_name}_output"``), and as
        the retry-counter key that :class:`RetryingEdge` will read
        (``state['_retry_counts'][node_name]``). Keep it unique within
        a graph.

    Returns
    -------
    An ``async`` LangGraph node function of shape
    ``(state, config) -> dict``. The function reads the following from
    ``config['configurable']`` (raising :class:`NonRetryable` with a
    clear message if any required key is missing, so the configuration
    error fails loudly instead of retrying into oblivion):

    * ``tier_registry`` — ``dict[str, TierConfig]``. Required.
    * ``cost_callback`` — :class:`CostTrackingCallback`. Required.
    * ``run_id`` — ``str``. Required.
    * ``semaphores`` — optional ``dict[str, asyncio.Semaphore]`` keyed
      by tier name. When absent for a given tier, no concurrency cap is
      enforced at the node boundary (the caller owns the decision).
    * ``pricing`` — optional ``dict[str, ModelPricing]``. Required only
      when the tier routes through ``ClaudeCodeRoute``; used by the
      subprocess driver to compute per-call cost.
    * ``workflow`` — optional ``str`` forwarded to the structured log
      record's ``workflow`` field.

    On success the node returns
    ``{f"{node_name}_output": text, "last_exception": None}``.
    The ``last_exception: None`` clears any stale classified exception
    from a prior retry turn so ``RetryingEdge`` does not re-fire on
    out-of-date state (T07 carry-over).

    Raises
    ------
    RetryableTransient
        Wraps any provider exception classified as a transient failure
        (LiteLLM ``Timeout`` / ``APIConnectionError`` /
        ``RateLimitError`` / ``ServiceUnavailableError``;
        ``subprocess.TimeoutExpired``).
    NonRetryable
        Wraps any other provider exception, configuration error, or
        unknown-tier miss. Auth failures, ``BadRequestError``,
        ``ContextWindowExceededError``, and ``CalledProcessError`` all
        surface here.
    RetryableSemantic
        Passed through untouched if the provider (or a wrapper) emits
        it — the validator is the canonical producer, but preserving
        pass-through keeps the contract symmetric.
    """

    async def _node(state: GraphState, config: Any = None) -> dict[str, Any]:
        configurable = _get_configurable(config)
        try:
            tier_registry: dict[str, TierConfig] = configurable["tier_registry"]
            cost_callback: CostTrackingCallback = configurable["cost_callback"]
            run_id: str = configurable["run_id"]
        except KeyError as exc:
            raise NonRetryable(
                f"TieredNode({node_name!r}) requires config.configurable[{exc.args[0]!r}]"
            ) from exc

        semaphores: Mapping[str, asyncio.Semaphore] = (
            configurable.get("semaphores") or {}
        )
        pricing: Mapping[str, ModelPricing] = configurable.get("pricing") or {}
        workflow_name: str | None = configurable.get("workflow")
        breakers: Mapping[str, CircuitBreaker] = (
            configurable.get("ollama_circuit_breakers") or {}
        )

        resolved_tier = _resolve_tier(tier, state, configurable)
        try:
            tier_config = tier_registry[resolved_tier]
        except KeyError as exc:
            raise NonRetryable(
                f"TieredNode({node_name!r}) unknown tier: {resolved_tier!r}"
            ) from exc

        route = tier_config.route
        provider = _provider_from_route(route)
        model_id = _model_from_route(route)
        system, messages = prompt_fn(state)
        semaphore = semaphores.get(resolved_tier)
        breaker = _resolve_breaker(route, resolved_tier, breakers)

        if breaker is not None and not await breaker.allow():
            # Short-circuit: breaker denies the call before any dispatch.
            # Raising CircuitOpen lets :func:`wrap_with_error_handler`
            # catch the specific type and the workflow-layer edge route
            # to the M8 T03 fallback :class:`HumanGate` rather than
            # through the standard three-bucket retry path.
            raise CircuitOpen(
                tier=resolved_tier,
                last_reason=breaker.last_reason,
            )

        log_extras: dict[str, Any] = {}
        if breaker is not None:
            log_extras["breaker_state"] = breaker.state.value

        start = time.monotonic()
        try:
            if semaphore is not None:
                async with semaphore:
                    text, usage = await _dispatch(
                        route=route,
                        tier_config=tier_config,
                        pricing=pricing,
                        system=system,
                        messages=messages,
                        output_schema=output_schema,
                    )
            else:
                text, usage = await _dispatch(
                    route=route,
                    tier_config=tier_config,
                    pricing=pricing,
                    system=system,
                    messages=messages,
                    output_schema=output_schema,
                )
            usage_with_tier = (
                usage
                if usage.tier
                else usage.model_copy(update={"tier": resolved_tier})
            )
            # Cost callback lives inside the try block so a budget-breach
            # NonRetryable raised by ``CostTracker.check_budget`` (§8.5)
            # goes through the same single-log failure path as a provider
            # exception — preserves the "exactly one structured log per
            # invocation" invariant on the budget-cap path.
            cost_callback.on_node_complete(run_id, node_name, usage_with_tier)
            if breaker is not None:
                await breaker.record_success()
                # Re-read the state after record_success so the log line
                # shows the post-success state (e.g. HALF_OPEN → CLOSED).
                log_extras["breaker_state"] = breaker.state.value
            # Optional eval-capture callback (M7 T02). Duck-typed —
            # TieredNode does not import ``ai_workflows.evals`` because
            # ``graph`` must not reach ``evals`` (lower-layer-reaches-higher
            # violation). The capture callback is wired at dispatch time
            # via ``config.configurable["eval_capture_callback"]``. Any
            # exception it raises is swallowed by the callback itself
            # (capture must never break a live run).
            eval_capture = configurable.get("eval_capture_callback")
            if eval_capture is not None:
                eval_capture.on_node_complete(
                    run_id=run_id,
                    node_name=node_name,
                    inputs=dict(state),
                    raw_output=text,
                    output_schema=output_schema,
                )
        except RetryableSemantic:
            # Pass-through: validators own this bucket, but if a wrapper
            # emits it here we must not re-classify.
            raise
        except (RetryableTransient, NonRetryable) as exc:
            if breaker is not None and isinstance(exc, RetryableTransient):
                await breaker.record_failure(reason=type(exc).__name__)
                log_extras["breaker_state"] = breaker.state.value
            duration_ms = int((time.monotonic() - start) * 1000)
            log_node_event(
                _LOG,
                event="node_failed",
                run_id=run_id,
                workflow=workflow_name,
                node=node_name,
                tier=resolved_tier,
                provider=provider,
                model=model_id,
                duration_ms=duration_ms,
                input_tokens=None,
                output_tokens=None,
                cost_usd=None,
                level="error",
                error_class=type(exc).__name__,
                bucket=type(exc).__name__,
                **log_extras,
            )
            raise
        except Exception as exc:  # noqa: BLE001 — classification boundary
            bucket_cls = classify(exc)
            if breaker is not None and bucket_cls is RetryableTransient:
                await breaker.record_failure(reason=type(exc).__name__)
                log_extras["breaker_state"] = breaker.state.value
            duration_ms = int((time.monotonic() - start) * 1000)
            log_node_event(
                _LOG,
                event="node_failed",
                run_id=run_id,
                workflow=workflow_name,
                node=node_name,
                tier=resolved_tier,
                provider=provider,
                model=model_id,
                duration_ms=duration_ms,
                input_tokens=None,
                output_tokens=None,
                cost_usd=None,
                level="error",
                error_class=type(exc).__name__,
                bucket=bucket_cls.__name__,
                **log_extras,
            )
            if bucket_cls is RetryableTransient:
                raise RetryableTransient(str(exc)) from exc
            # classify() never returns RetryableSemantic for provider
            # exceptions (validators own that bucket) — everything else
            # funnels to NonRetryable so misclassified errors fail loud.
            raise NonRetryable(str(exc)) from exc

        duration_ms = int((time.monotonic() - start) * 1000)
        log_node_event(
            _LOG,
            event="node_completed",
            run_id=run_id,
            workflow=workflow_name,
            node=node_name,
            tier=resolved_tier,
            provider=provider,
            model=model_id,
            duration_ms=duration_ms,
            input_tokens=usage_with_tier.input_tokens,
            output_tokens=usage_with_tier.output_tokens,
            cost_usd=usage_with_tier.cost_usd,
            level="info",
            **log_extras,
        )

        return {
            f"{node_name}_output": text,
            "last_exception": None,
        }

    return _node


def _resolve_tier(
    logical: str, state: GraphState, configurable: Mapping[str, Any]
) -> str:
    """Resolve the logical tier to its runtime replacement (M8 T04).

    Precedence (spec §Mid-run tier override plumbing):

    1. ``state[_mid_run_tier_overrides][logical]`` — the M8 T04 fallback
       gate stamps this on ``FallbackChoice.FALLBACK`` so the swap
       applies for the remainder of the run.
    2. ``configurable['tier_overrides'][logical]`` — the M5 T04
       start-of-run override path. Kept for forward compatibility;
       :mod:`ai_workflows.workflows._dispatch` currently applies these
       by rewriting the registry before the node sees it, so this
       layer is usually a no-op in production.
    3. ``logical`` — registry default.

    The first match wins; the second and third layers are not
    consulted. Returns the logical name unchanged when no layer
    supplies an override.
    """
    state_overrides = state.get(_MID_RUN_TIER_OVERRIDES_STATE_KEY) or {}
    if logical in state_overrides:
        return state_overrides[logical]
    config_overrides = configurable.get("tier_overrides") or {}
    if logical in config_overrides:
        return config_overrides[logical]
    return logical


def _resolve_breaker(
    route: LiteLLMRoute | ClaudeCodeRoute,
    resolved_tier: str,
    breakers: Mapping[str, CircuitBreaker],
) -> CircuitBreaker | None:
    """Return the breaker for ``resolved_tier`` iff the route is Ollama-backed.

    Consult rule (spec AC-1): only ``LiteLLMRoute`` tiers whose
    ``route.model`` starts with ``"ollama/"`` are breakered. Gemini-backed
    LiteLLM tiers and every :class:`ClaudeCodeRoute` tier bypass the
    breaker even if the configurable map lists them (KDR-003 /
    architecture.md §8.4 — breakers exist for the local Ollama daemon,
    not hosted providers with their own rate-limit semantics).
    """
    if not isinstance(route, LiteLLMRoute):
        return None
    if not route.model.startswith("ollama/"):
        return None
    return breakers.get(resolved_tier)


async def _dispatch(
    *,
    route: LiteLLMRoute | ClaudeCodeRoute,
    tier_config: TierConfig,
    pricing: Mapping[str, ModelPricing],
    system: str | None,
    messages: list[dict],
    output_schema: type[BaseModel] | None,
) -> tuple[str, TokenUsage]:
    """Dispatch to the adapter matching ``route.kind`` and return its result.

    Centralises the route-kind dispatch so the two call paths share the
    same exception surface (whatever the adapter raises propagates to
    the node's classifier) and the same success shape.
    """
    if isinstance(route, LiteLLMRoute):
        adapter = LiteLLMAdapter(
            route=route,
            per_call_timeout_s=tier_config.per_call_timeout_s,
        )
        return await adapter.complete(
            system=system, messages=messages, response_format=output_schema
        )
    if isinstance(route, ClaudeCodeRoute):
        claude_adapter = ClaudeCodeSubprocess(
            route=route,
            per_call_timeout_s=tier_config.per_call_timeout_s,
            pricing=dict(pricing),
        )
        return await claude_adapter.complete(
            system=system, messages=messages, response_format=output_schema
        )
    raise NonRetryable(f"Unsupported route kind: {type(route).__name__}")


def _get_configurable(config: Any) -> Mapping[str, Any]:
    """Return the ``configurable`` sub-mapping from a LangGraph ``config``.

    LangGraph passes ``RunnableConfig`` as a ``Mapping``-like dict with
    a ``configurable`` key. Nodes invoked without a config (standalone
    unit tests that forget the kwarg) are treated as missing-configurable
    so the downstream ``KeyError`` path produces a clear
    ``NonRetryable`` message.
    """
    if config is None:
        return {}
    if isinstance(config, Mapping):
        inner = config.get("configurable")
        if inner is None:
            return {}
        if isinstance(inner, Mapping):
            return inner
    return {}


def _provider_from_route(route: LiteLLMRoute | ClaudeCodeRoute) -> str:
    """Return the §8.1 ``provider`` label for a resolved route."""
    if isinstance(route, LiteLLMRoute):
        return "litellm"
    if isinstance(route, ClaudeCodeRoute):
        return "claude_code"
    return "unknown"


def _model_from_route(route: LiteLLMRoute | ClaudeCodeRoute) -> str | None:
    """Return the §8.1 ``model`` label for a resolved route."""
    if isinstance(route, LiteLLMRoute):
        return route.model
    if isinstance(route, ClaudeCodeRoute):
        return route.cli_model_flag
    return None
