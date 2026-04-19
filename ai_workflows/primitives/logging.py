"""Canonical structlog + logfire configuration.

Produced by M1 Task 11 (P-42, P-43, P-44; resolves carry-overs
``M1-T05-ISS-02`` and ``M1-T01-ISS-08``). Wires ``structlog`` for
structured application logging and ``logfire`` for OTel GenAI
observability.

Two sinks
---------
1. **stderr** — :class:`structlog.dev.ConsoleRenderer` when ``level ==
   "DEBUG"`` (human-readable with level tokens and key=value pairs),
   :class:`structlog.processors.JSONRenderer` otherwise (one JSON object
   per line).
2. **per-run file** — ``<run_root>/<run_id>/run.log`` — always JSON, one
   object per line. One file per run; no rotation (each run is fresh).
   Created only when ``run_id`` is supplied.

Log-level conventions (P-43)
----------------------------
* ``INFO`` — run lifecycle, cost summaries, HumanGate events, retries,
  forensic hits.
* ``DEBUG`` — full LLM I/O, tool I/O, token counts per call.
* ``WARNING`` — forensic pattern hits, missing pricing rows, rate-limit
  retries, cache misses on static prompts.
* ``ERROR`` — unrecoverable failures, ``BudgetExceeded``,
  ``SecurityError``, HumanGate rejections.

What is *not* here
------------------
``logfire.instrument_anthropic()`` / ``instrument_openai()`` are
deferred to M3 (task IMP-02). At M1 we only need the configuration hook
so downstream modules can call :func:`structlog.get_logger` with a
working processor chain.

Related
-------
* :mod:`ai_workflows.primitives.tools.forensic_logger` — emits
  ``tool_output_suspicious_patterns`` WARNINGs whose delivery through
  the production pipeline is pinned by the ``M1-T05-ISS-02`` carry-over
  test.
* ``.github/workflows/ci.yml`` — the secret-scan grep regex is now
  parsed at test time (``M1-T01-ISS-08`` carry-over) so the scaffolding
  test always tracks the live pattern.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import IO, Any

import logfire
import structlog

__all__ = ["DEFAULT_RUN_ROOT", "configure_logging"]


DEFAULT_RUN_ROOT = Path.home() / ".ai-workflows" / "runs"
"""Default root for per-run log files. Overridable in :func:`configure_logging`."""


def configure_logging(
    level: str = "INFO",
    run_id: str | None = None,
    run_root: Path | None = None,
    *,
    stream: IO[str] | None = None,
) -> None:
    """Configure ``structlog`` and ``logfire`` once per process.

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

    Notes
    -----
    * ``send_to_logfire="if-token-present"`` honours AC-5: logfire only
      ships spans to ``logfire.dev`` when the ``LOGFIRE_TOKEN`` env var
      is set. Without a token, the SDK still configures its OTel
      provider locally (so ``instrument_*`` calls in M3 work) but never
      attempts network egress.
    * ``logfire.instrument_pydantic(record="all")`` replaces the
      spec's ``pydantic_plugin=PydanticPlugin(record="all")`` — that
      kwarg was moved to ``DeprecatedKwargs`` in logfire ≥ 3. The
      observable behaviour is identical.
    """
    level = level.upper()
    numeric_level = getattr(logging, level, logging.INFO)

    logfire.configure(
        send_to_logfire="if-token-present",
        service_name="ai_workflows",
    )
    logfire.instrument_pydantic(record="all")

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
