"""Forensic logger for tool-output inspection.

Produced by M1 Task 05 (CRIT-04). This module is the **rebrand** of the former
regex "sanitizer": it scans tool outputs for known prompt-injection marker
patterns and emits a ``WARNING``-level structlog event so a human can audit
what the model was asked to do after a bad run.

**This is NOT a security control.**

Pattern matching is theatre against an adversarial opponent — Simon Willison's
writing on prompt injection is unambiguous on this point. Keeping a sanitizer
under that name invites downstream code to rely on it for defence, which
creates false confidence. The real defences live elsewhere:

* ``ContentBlock`` ``tool_result`` wrapping (M1 Task 02) — tool outputs are
  framed as *data*, not instructions, by the model adapter protocol.
* ``run_command`` CWD restriction + executable allowlist + ``dry_run`` mode
  (M1 Task 06).
* ``HumanGate`` on destructive operations (M2+).
* Per-component tool allowlists (the :class:`ToolRegistry` in
  :mod:`ai_workflows.primitives.tools.registry` — this task's sibling module).

This logger runs *after* the tool returns; it never modifies the output that
is fed back to the model. Its sole output is a log line. Use it for post-hoc
investigation, **never** for pre-delivery filtering.

Related
-------
* :mod:`ai_workflows.primitives.tools.registry` — wraps every registered tool
  so its output passes through :func:`log_suspicious_patterns` before being
  returned to pydantic-ai.
* ``design_docs/issues.md`` — CRIT-04 records the rationale for the rebrand.
"""

from __future__ import annotations

import re

import structlog

__all__ = ["INJECTION_PATTERNS", "log_suspicious_patterns"]


_logger = structlog.get_logger(__name__)


# Known prompt-injection marker patterns. This list is deliberately coarse —
# the signal is "an attacker is probing the seam between tool output and
# instruction", not "this output is adversarial". False positives are the
# norm; they get reviewed by a human, not auto-filtered.
INJECTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"IGNORE\s+(PREVIOUS|ABOVE|ALL)\s+INSTRUCTIONS", re.IGNORECASE),
    re.compile(r"YOU\s+ARE\s+NOW", re.IGNORECASE),
    re.compile(r"^\s*SYSTEM\s*:", re.IGNORECASE | re.MULTILINE),
    re.compile(r"<\|im_start\|>"),
    re.compile(r"\[INST\]"),
    re.compile(r"###\s+(NEW\s+)?INSTRUCTION", re.IGNORECASE),
    re.compile(r"DISREGARD\s+(THE\s+)?ABOVE", re.IGNORECASE),
]


def log_suspicious_patterns(
    *,
    tool_name: str,
    output: str,
    run_id: str,
) -> None:
    """Scan ``output`` for known injection patterns and emit a WARNING if any match.

    **This is forensic logging for post-hoc analysis, NOT a security control.**
    Pattern matching is not a defence against adversarial content. The real
    defences are the :class:`~ai_workflows.primitives.llm.types.ContentBlock`
    ``tool_result`` wrapping (Task 02), ``run_command``'s CWD / allowlist
    constraints (Task 06), ``HumanGate`` (M2+), and the per-component tool
    allowlists enforced by
    :class:`~ai_workflows.primitives.tools.registry.ToolRegistry`.

    Behaviour
    ---------
    * Iterates over :data:`INJECTION_PATTERNS`; if any pattern matches, emits
      a single structlog ``warning`` event named
      ``tool_output_suspicious_patterns`` with ``tool_name``, ``run_id``, the
      matched pattern strings, and the output length.
    * Returns ``None`` either way; **does NOT modify the output** that is
      passed back to the model.
    * Non-matching outputs produce no log line at all (the happy path is
      silent).

    Parameters
    ----------
    tool_name:
        Registered tool name (as used by :class:`ToolRegistry`).
    output:
        Raw stringified tool output. Binary blobs should be stringified by the
        caller; this function treats ``output`` as opaque text.
    run_id:
        The current run's id, lifted from ``RunContext[WorkflowDeps].deps``.
        Pass ``"unknown"`` only if the caller genuinely has no run context.
    """
    matches = [pattern.pattern for pattern in INJECTION_PATTERNS if pattern.search(output)]
    if matches:
        _logger.warning(
            "tool_output_suspicious_patterns",
            tool_name=tool_name,
            run_id=run_id,
            patterns=matches,
            output_length=len(output),
        )
