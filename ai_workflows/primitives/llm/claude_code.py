"""Claude Code CLI subprocess driver (M2 Task 02 — KDR-003, KDR-007,
[architecture.md §4.1](../../../design_docs/architecture.md)).

Invokes ``claude -p --output-format json --model <cli_model_flag>``,
feeds the prompt via stdin, parses the JSON result, and maps it onto
``(text, TokenUsage)``. LiteLLM does not cover OAuth-authenticated
subprocess providers (KDR-007), so this driver stays bespoke — the
counterpart to :class:`~ai_workflows.primitives.llm.litellm_adapter.LiteLLMAdapter`
for the Claude Max tiers (``opus`` / ``sonnet`` / ``haiku``).

Scope discipline
----------------
* **No Anthropic API** (KDR-003). Auth is OAuth + keychain, already
  held by the CLI; this module never reads the Anthropic API-key env
  var and never imports the ``anthropic`` SDK. Grep-checked in the
  task test suite and again in the milestone audit.
* **No classification / retry.** ``subprocess.TimeoutExpired`` and
  ``subprocess.CalledProcessError`` bubble up verbatim; the M1 Task 07
  ``classify()`` function buckets them (``RetryableTransient`` and
  ``NonRetryable`` respectively) at the M2 ``TieredNode`` boundary.
* **No schema validation.** ``response_format`` is accepted for
  signature parity with :class:`LiteLLMAdapter` but intentionally
  ignored — the CLI does not expose a structured-output mode and the
  KDR-004 ``ValidatorNode`` runs after every LLM node regardless.

CLI invocation shape
--------------------
Hermetic flag set validated by the M1 Task 13 spike:

* ``--print`` — non-interactive single-shot; exit when the model finishes.
* ``--output-format json`` — structured JSON on stdout including ``result``,
  ``usage``, and the ``modelUsage`` sub-model breakdown.
* ``--tools ""`` — disable CLI-builtin tools so the call is a pure
  text→text round-trip.
* ``--no-session-persistence`` — do not leave resumable sessions behind.
* ``--system-prompt`` (conditional) — forward the caller's ``system`` arg.
* ``--model <cli_model_flag>`` — route to the requested tier.

The prompt is fed via stdin (per the task spec), which sidesteps argv
length limits and avoids shell-quoting ambiguity.

Relationship to sibling modules
-------------------------------
* ``primitives/tiers.py`` — owns ``ClaudeCodeRoute`` + ``ModelPricing``.
  Both are construction-time inputs here.
* ``primitives/cost.py`` — owns ``TokenUsage`` and its recursive
  ``sub_models`` field, populated from every ``modelUsage`` row the
  CLI emits (so a ``opus`` call that internally spawns a haiku
  auto-classifier is recorded as two distinct entries).
* ``primitives/retry.py`` — ``classify()`` maps the two subprocess
  exceptions we raise onto the three-bucket taxonomy above this layer.
"""

from __future__ import annotations

import asyncio
import json
import subprocess
from typing import Any

from pydantic import BaseModel

from ai_workflows.primitives.cost import TokenUsage
from ai_workflows.primitives.tiers import ClaudeCodeRoute, ModelPricing

__all__ = ["ClaudeCodeSubprocess"]


class ClaudeCodeSubprocess:
    """Drive the ``claude`` CLI as a one-shot subprocess provider.

    One instance per tier is the intended pattern — the ``route`` pins
    which ``--model`` flag the subprocess runs under, and ``pricing``
    supplies per-million-token rates for every model ID that may appear
    in the response's ``modelUsage`` block.
    """

    def __init__(
        self,
        route: ClaudeCodeRoute,
        per_call_timeout_s: int,
        pricing: dict[str, ModelPricing],
    ) -> None:
        self._route = route
        self._per_call_timeout_s = per_call_timeout_s
        self._pricing = pricing

    async def complete(
        self,
        *,
        system: str | None,
        messages: list[dict],
        response_format: type[BaseModel] | None = None,
    ) -> tuple[str, TokenUsage]:
        """Spawn the CLI, feed the prompt via stdin, return ``(text, TokenUsage)``.

        ``system`` is forwarded verbatim via ``--system-prompt`` when
        set. ``messages`` are flattened into a single text blob on stdin
        (the CLI runs single-shot, not multi-turn). ``response_format``
        is accepted for API parity with :class:`LiteLLMAdapter` but not
        forwarded — schema validation is the ``ValidatorNode``'s job
        (KDR-004).

        Raises
        ------
        subprocess.TimeoutExpired
            Per-call wall-clock exceeded; the M1 Task 07 ``classify()``
            buckets this as ``RetryableTransient``.
        subprocess.CalledProcessError
            Non-zero exit or a body that reports ``is_error: true``;
            ``classify()`` buckets this as ``NonRetryable``.
        json.JSONDecodeError
            CLI emitted a non-JSON body (CLI version mismatch, stdout
            corruption). ``classify()`` defaults to ``NonRetryable``
            for unknown exception types.
        """
        del response_format  # kept for API parity; see module docstring.

        argv: list[str] = [
            "claude",
            "--print",
            "--output-format",
            "json",
            "--model",
            self._route.cli_model_flag,
            "--tools",
            "",
            "--no-session-persistence",
        ]
        if system is not None:
            argv.extend(["--system-prompt", system])

        stdin_payload = _flatten_messages(messages).encode("utf-8")

        proc = await asyncio.create_subprocess_exec(
            *argv,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(stdin_payload),
                timeout=self._per_call_timeout_s,
            )
        except TimeoutError as exc:
            # Kill the subprocess so its resources are released before
            # the caller's retry-loop (RetryingEdge) spawns the next one.
            proc.kill()
            await proc.wait()
            raise subprocess.TimeoutExpired(
                cmd=argv, timeout=float(self._per_call_timeout_s)
            ) from exc

        if proc.returncode != 0:
            raise subprocess.CalledProcessError(
                returncode=proc.returncode or 1,
                cmd=argv,
                output=stdout_bytes,
                stderr=stderr_bytes,
            )

        data: dict[str, Any] = json.loads(stdout_bytes.decode("utf-8") or "{}")

        # Per M1 Task 13 spike: the CLI sometimes emits exit 0 with
        # ``is_error: true`` (e.g. invalid model id → exit 1, but other
        # logical failures may surface here). ``is_error`` is the
        # truth-bearing field — treat it as a CalledProcessError so
        # classify() buckets it as NonRetryable.
        if data.get("is_error") is True:
            raise subprocess.CalledProcessError(
                returncode=proc.returncode,
                cmd=argv,
                output=stdout_bytes,
                stderr=stderr_bytes,
            )

        text = str(data.get("result", ""))
        usage = _build_usage(data, route=self._route, pricing=self._pricing)
        return text, usage


def _flatten_messages(messages: list[dict]) -> str:
    """Join message contents into a single CLI-friendly prompt blob.

    Multi-turn ``messages`` lists are collapsed to one text payload
    because the CLI runs single-shot. Non-string contents are coerced
    to strings; empty contents are dropped so role-tags never leak a
    bare separator.
    """
    parts: list[str] = []
    for message in messages:
        content = message.get("content")
        if content is None or content == "":
            continue
        parts.append(str(content))
    return "\n\n".join(parts)


def _build_usage(
    data: dict[str, Any],
    *,
    route: ClaudeCodeRoute,
    pricing: dict[str, ModelPricing],
) -> TokenUsage:
    """Map the CLI's JSON into :class:`TokenUsage` with a sub-model tree.

    When ``modelUsage`` is present (current CLI versions always emit
    it under ``--output-format json``), the primary ``TokenUsage`` is
    built from the modelUsage entry whose key matches the requested
    ``cli_model_flag``; every other modelUsage row becomes a
    ``sub_models`` child so the haiku auto-classifier the CLI spawns
    for opus/sonnet calls is visible to ``CostTracker.by_model``.

    When ``modelUsage`` is absent (older CLI versions, per the spike's
    fallback note), the top-level ``usage`` block is used directly and
    ``sub_models`` stays empty.
    """
    model_usage = data.get("modelUsage") or {}
    top_usage = data.get("usage") or {}

    if not isinstance(model_usage, dict) or not model_usage:
        return _usage_from_top_level(top_usage, route.cli_model_flag, pricing)

    primary_key = _find_primary_key(route.cli_model_flag, list(model_usage.keys()))

    sub_models: list[TokenUsage] = []
    primary_entry: TokenUsage | None = None
    for model_id, row in model_usage.items():
        entry = _row_to_usage(row, model_id=model_id, pricing=pricing)
        if model_id == primary_key:
            primary_entry = entry
        else:
            sub_models.append(entry)

    if primary_entry is None:
        # No modelUsage row matched the requested tier — fall back to
        # the top-level usage block for the primary and record every
        # modelUsage row as a sub-model so no cost signal is lost.
        primary_entry = _usage_from_top_level(top_usage, route.cli_model_flag, pricing)
        sub_models = [
            _row_to_usage(row, model_id=model_id, pricing=pricing)
            for model_id, row in model_usage.items()
        ]

    primary_entry.sub_models = sub_models
    return primary_entry


def _find_primary_key(cli_flag: str, keys: list[str]) -> str | None:
    """Return the modelUsage key that best matches the requested tier.

    The CLI accepts either an alias (``opus`` / ``sonnet`` / ``haiku``)
    or a full model ID (``claude-opus-4-7``) as ``--model``.
    ``modelUsage`` reports full IDs regardless, so the lookup is:
    exact match first (full-ID configurations), then substring-of-key
    (alias configurations). Case-insensitive to match the CLI's own
    handling of aliases.
    """
    if cli_flag in keys:
        return cli_flag
    lowered = cli_flag.lower()
    for key in keys:
        if lowered in key.lower():
            return key
    return None


def _row_to_usage(
    row: dict[str, Any],
    *,
    model_id: str,
    pricing: dict[str, ModelPricing],
) -> TokenUsage:
    """Build a :class:`TokenUsage` from a single ``modelUsage`` row."""
    input_tokens = _int_field(row, "inputTokens")
    output_tokens = _int_field(row, "outputTokens")
    cache_read = _int_field(row, "cacheReadInputTokens")
    cache_write = _int_field(row, "cacheCreationInputTokens")
    cost = _compute_cost(
        model_id=model_id,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_read=cache_read,
        cache_write=cache_write,
        pricing=pricing,
    )
    return TokenUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_read_tokens=cache_read,
        cache_write_tokens=cache_write,
        cost_usd=cost,
        model=model_id,
    )


def _usage_from_top_level(
    top: dict[str, Any],
    cli_model_flag: str,
    pricing: dict[str, ModelPricing],
) -> TokenUsage:
    """Build a :class:`TokenUsage` from the top-level ``usage`` block."""
    input_tokens = _int_field(top, "input_tokens")
    output_tokens = _int_field(top, "output_tokens")
    cache_read = _int_field(top, "cache_read_input_tokens")
    cache_write = _int_field(top, "cache_creation_input_tokens")
    cost = _compute_cost(
        model_id=cli_model_flag,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_read=cache_read,
        cache_write=cache_write,
        pricing=pricing,
    )
    return TokenUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_read_tokens=cache_read,
        cache_write_tokens=cache_write,
        cost_usd=cost,
        model=cli_model_flag,
    )


def _int_field(row: dict[str, Any], key: str) -> int:
    """Coerce a JSON number field to ``int`` with a zero default."""
    value = row.get(key, 0) or 0
    return int(value)


def _compute_cost(
    *,
    model_id: str,
    input_tokens: int,
    output_tokens: int,
    cache_read: int,
    cache_write: int,
    pricing: dict[str, ModelPricing],
) -> float:
    """Multiply token counts by the per-million-token rates from pricing.yaml.

    Returns ``0.0`` when the model is absent from the pricing table —
    that is the expected case for Claude Max tiers (which are billed
    by subscription, not per-token), so the missing-row path must not
    raise.
    """
    row = pricing.get(model_id)
    if row is None:
        return 0.0
    million = 1_000_000.0
    return (
        (input_tokens / million) * row.input_per_mtok
        + (output_tokens / million) * row.output_per_mtok
        + (cache_read / million) * row.cache_read_per_mtok
        + (cache_write / million) * row.cache_write_per_mtok
    )
