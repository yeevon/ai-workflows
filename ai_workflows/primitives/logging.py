"""Canonical ``structlog`` configuration + node-record emission helper.

Produced by M1 Task 09 (``StructuredLogger sanity pass``). Supersedes
the pre-pivot M1 Task 11 shape that layered a second observability
backend alongside ``structlog``: per
[architecture.md §8.1](../../design_docs/architecture.md) external
observability backends (Langfuse, LangSmith, OpenTelemetry) are
deferred to [nice_to_have.md](../../design_docs/nice_to_have.md)
§1/§3/§8, and the prior second-backend dependency was dropped from
``pyproject.toml`` by M1 Task 02. ``StructuredLogger`` (this module)
is now the **single** observability surface the codebase ships.

Two sinks
---------
1. **stderr** — :class:`structlog.dev.ConsoleRenderer` when ``level ==
   "DEBUG"`` (human-readable with level tokens and key=value pairs),
   :class:`structlog.processors.JSONRenderer` otherwise (one JSON object
   per line).
2. **per-run file** — ``<run_root>/<run_id>/run.log`` — always JSON, one
   object per line. One file per run; no rotation (each run is fresh).
   Created only when ``run_id`` is supplied.

Node record shape (architecture.md §8.1)
----------------------------------------
:func:`log_node_event` emits every field named in §8.1 — ``run_id``,
``workflow``, ``node``, ``tier``, ``provider`` (``"litellm"`` or
``"claude_code"``), ``model``, ``duration_ms``, ``input_tokens``,
``output_tokens``, ``cost_usd``. Fields unknown at emit time flow
through as ``None`` (rendered as ``null`` in JSON) rather than dropped
or replaced with a placeholder, so downstream consumers (M2 Pipeline
rollup, M3 cost-report CLI) see a consistent schema for every record.

Log-level conventions
---------------------
* ``INFO`` — run lifecycle, cost summaries, HumanGate events, retries.
* ``DEBUG`` — full LLM I/O, tool I/O, token counts per call.
* ``WARNING`` — missing pricing rows, rate-limit retries, cache misses
  on static prompts.
* ``ERROR`` — unrecoverable failures, ``NonRetryable("budget exceeded")``
  ([architecture.md §8.5](../../design_docs/architecture.md)),
  ``SecurityError``, HumanGate rejections.

Related
-------
* :mod:`ai_workflows.primitives.retry` — ``NonRetryable`` is the
  ERROR-level exemplar above; it is the post-M1-T08 route for budget
  breaches.
* :mod:`ai_workflows.primitives.cost` — :class:`CostTracker` is the
  other half of the observability triad (cost ledger alongside the
  structured log).
* ``.github/workflows/ci.yml`` — the secret-scan grep regex is parsed
  at test time by ``tests/test_scaffolding.py`` so the scaffolding test
  always tracks the live pattern.
"""

from __future__ import annotations

import logging as _stdlib_logging
import sys
from pathlib import Path
from typing import IO, Any

import structlog

__all__ = [
    "DEFAULT_RUN_ROOT",
    "NODE_LOG_FIELDS",
    "configure_logging",
    "log_node_event",
]


DEFAULT_RUN_ROOT = Path.home() / ".ai-workflows" / "runs"
"""Default root for per-run log files. Overridable in :func:`configure_logging`."""


NODE_LOG_FIELDS: tuple[str, ...] = (
    "run_id",
    "workflow",
    "node",
    "tier",
    "provider",
    "model",
    "duration_ms",
    "input_tokens",
    "output_tokens",
    "cost_usd",
)
"""The ten fields §8.1 mandates per node record.

See [architecture.md §8.1](../../design_docs/architecture.md).
"""


def configure_logging(
    level: str = "INFO",
    run_id: str | None = None,
    run_root: Path | None = None,
    *,
    stream: IO[str] | None = None,
) -> None:
    """Configure ``structlog`` once per process.

    Intended to be called exactly once at CLI startup (or at the top of
    a test that needs the production pipeline). Calling it again
    replaces the previous configuration.

    Parameters
    ----------
    level:
        Minimum log level as a string (case-insensitive): ``"DEBUG"``,
        ``"INFO"``, ``"WARNING"``, ``"ERROR"``, ``"CRITICAL"``.
        ``"DEBUG"`` activates :class:`structlog.dev.ConsoleRenderer` for
        the stderr sink; any other level uses
        :class:`structlog.processors.JSONRenderer`.
    run_id:
        If set, a per-run JSON sink is attached at
        ``<run_root>/<run_id>/run.log``. The directory is created if it
        does not already exist.
    run_root:
        Override for the per-run directory root. Defaults to
        :data:`DEFAULT_RUN_ROOT` (``~/.ai-workflows/runs``). Primarily
        for tests; production callers should pass ``None``.
    stream:
        Override for the console sink. Defaults to :data:`sys.stderr`.
        Primarily for tests that need deterministic capture without
        fighting pytest's own stream capture — pass a :class:`io.StringIO`.
    """
    level = level.upper()
    numeric_level = getattr(_stdlib_logging, level, _stdlib_logging.INFO)

    file_path: Path | None = None
    if run_id:
        root = run_root if run_root is not None else DEFAULT_RUN_ROOT
        run_dir = root / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        file_path = run_dir / "run.log"
        file_path.touch(exist_ok=True)

    processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
    ]
    if level == "DEBUG":
        stderr_renderer: Any = structlog.dev.ConsoleRenderer(colors=False)
    else:
        stderr_renderer = structlog.processors.JSONRenderer()
    processors.append(_TeeRenderer(stderr_renderer, file_path))

    console_stream = stream if stream is not None else sys.stderr
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(numeric_level),
        logger_factory=structlog.PrintLoggerFactory(file=console_stream),
        cache_logger_on_first_use=False,
    )


def log_node_event(
    logger: Any,
    event: str = "node_completed",
    *,
    run_id: str | None = None,
    workflow: str | None = None,
    node: str | None = None,
    tier: str | None = None,
    provider: str | None = None,
    model: str | None = None,
    duration_ms: int | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    cost_usd: float | None = None,
    level: str = "info",
    **extra: Any,
) -> None:
    """Emit one node record in the [architecture.md §8.1](../../design_docs/architecture.md) shape.

    Every field in :data:`NODE_LOG_FIELDS` is attached to the record —
    fields unknown at emit time flow through as ``None`` (rendered as
    ``null`` in the JSON sink) so downstream consumers see a consistent
    schema across records.

    Parameters
    ----------
    logger:
        A bound ``structlog`` logger (``structlog.get_logger(__name__)``).
    event:
        The ``event`` name in the emitted record. Defaults to
        ``"node_completed"`` because the call-site is typically a
        TieredNode finishing work; overridable for lifecycle events
        (``"node_started"``, ``"node_retrying"``, ...).
    run_id, workflow, node, tier, provider, model:
        Identity fields. ``provider`` is expected to be either
        ``"litellm"`` or ``"claude_code"`` per §4.1 / §8.1.
    duration_ms, input_tokens, output_tokens, cost_usd:
        Per-call measurements. ``cost_usd`` is typically ``None`` until
        LiteLLM / the Claude Code driver enriches the ``TokenUsage``.
    level:
        The log method to call on ``logger`` (``"info"`` / ``"debug"`` /
        ``"warning"`` / ``"error"``). Case-insensitive. Defaults to
        ``"info"`` — DEBUG-level detail belongs in a separate record
        with full LLM I/O.
    **extra:
        Additional keyword arguments forwarded to the logger. Useful
        for retry counts, validator-revision counts, or workflow-
        specific fields.
    """
    emit = getattr(logger, level.lower(), logger.info)
    emit(
        event,
        run_id=run_id,
        workflow=workflow,
        node=node,
        tier=tier,
        provider=provider,
        model=model,
        duration_ms=duration_ms,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost_usd,
        **extra,
    )


class _TeeRenderer:
    """Final-stage processor that renders to stderr and optionally a file.

    The per-run file always receives JSON (via a dedicated
    :class:`structlog.processors.JSONRenderer`) so downstream tooling can
    parse it unambiguously; the stderr stream uses whichever renderer
    was chosen for the configured level. The event dict is copied before
    being handed to the JSON renderer so the stderr renderer sees the
    original unmutated state.
    """

    def __init__(self, stderr_renderer: Any, file_path: Path | None) -> None:
        self._stderr_renderer = stderr_renderer
        self._file_path = file_path
        self._json_renderer = structlog.processors.JSONRenderer()

    def __call__(
        self, logger: Any, method_name: str, event_dict: dict[str, Any]
    ) -> str:
        if self._file_path is not None:
            json_line = self._json_renderer(logger, method_name, dict(event_dict))
            with open(self._file_path, "a", encoding="utf-8") as handle:
                handle.write(json_line + "\n")
        return self._stderr_renderer(logger, method_name, event_dict)
