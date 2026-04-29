"""Orchestrator-side agent-return parser — test helper.

Task: M20 Task 01 (Sub-agent return-value schema).
Relationship: Extracted from the slash-command markdown procedures in
  `.claude/commands/_common/agent_return_schema.md` for hermetic unit
  testability. The production parser runs in the slash-command (markdown)
  context; this module provides an equivalent Python implementation so
  `tests/agents/test_orchestrator_parser.py` can exercise every branch
  without spawning live agents.

This module intentionally lives under `tests/` (not `ai_workflows/`) because
it is test infrastructure for the autonomy orchestration layer (`.claude/`),
not part of the runtime Python package. Adding it to `ai_workflows/` would
create a new subpackage with no runtime caller, violating the layer discipline
(`primitives → graph → workflows → surfaces`) that `uv run lint-imports`
enforces.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Allowed verdict tokens per agent (mirrors the spec table in
# `.claude/commands/_common/agent_return_schema.md`).
# ---------------------------------------------------------------------------

AGENT_VERDICT_TOKENS: dict[str, frozenset[str]] = {
    "builder": frozenset({"BUILT", "BLOCKED", "STOP-AND-ASK"}),
    "auditor": frozenset({"PASS", "OPEN", "BLOCKED"}),
    "security-reviewer": frozenset({"SHIP", "FIX-THEN-SHIP", "BLOCK"}),
    "dependency-auditor": frozenset({"SHIP", "FIX-THEN-SHIP", "BLOCK"}),
    "task-analyzer": frozenset({"CLEAN", "LOW-ONLY", "OPEN"}),
    "architect": frozenset({"ALIGNED", "MISALIGNED", "OPEN", "PROPOSE-NEW-KDR"}),
    "sr-dev": frozenset({"SHIP", "FIX-THEN-SHIP", "BLOCK"}),
    "sr-sdet": frozenset({"SHIP", "FIX-THEN-SHIP", "BLOCK"}),
    "roadmap-selector": frozenset({"PROCEED", "NEEDS-CLEAN-TASKS", "HALT-AND-ASK"}),
}

# Regex for a single schema line: "key: value" (value may contain spaces / slashes)
_LINE_RE = re.compile(r"^(verdict|file|section): ?(.+)$")

# Expected key order
_EXPECTED_KEYS = ("verdict", "file", "section")


class MalformedAgentReturn(ValueError):
    """Raised when an agent return does not conform to the 3-line schema.

    The orchestrator catches this and halts the autonomy loop rather than
    retrying (a non-conformant return signals a deeper problem with the agent
    prompt or reasoning — halt-and-surface is safer than masking the bug).
    """


def parse_agent_return(
    text: str,
    agent_name: str | None = None,
) -> tuple[str, str, str]:
    """Parse a 3-line agent return into (verdict, file, section).

    Args:
        text: The raw text returned by the agent.  Must be exactly 3 non-empty
            lines matching ``^(verdict|file|section): ?(.+)$`` in order.
        agent_name: Optional agent name for verdict-set validation.  When
            supplied, the parsed ``verdict`` must be in the agent's allowed
            token set (from ``AGENT_VERDICT_TOKENS``).  When ``None``, verdict
            content is not validated beyond regex conformance.

    Returns:
        A ``(verdict, file, section)`` tuple — the literal right-hand-side
        values from each schema line.

    Raises:
        MalformedAgentReturn: On any of:
            - empty / whitespace-only input
            - fewer or more than 3 non-empty lines
            - a line that does not match ``^(verdict|file|section): ?(.+)$``
            - keys in the wrong order
            - a whitespace-only value on any line
            - ``verdict`` outside the agent's allowed set (when
              ``agent_name`` is supplied and recognised)
    """
    if not text or not text.strip():
        raise MalformedAgentReturn("Agent return is empty or whitespace-only.")

    # Collect non-empty lines (ignore trailing blank lines the terminal may add)
    lines = [ln for ln in text.splitlines() if ln.strip()]

    if len(lines) != 3:
        raise MalformedAgentReturn(
            f"Expected exactly 3 non-empty lines; got {len(lines)}."
        )

    parsed: dict[str, str] = {}
    for expected_key, line in zip(_EXPECTED_KEYS, lines, strict=True):
        match = _LINE_RE.match(line)
        if match is None:
            raise MalformedAgentReturn(
                f"Line {line!r} does not match the schema "
                f"`^(verdict|file|section): ?(.+)$`."
            )
        key, value = match.group(1), match.group(2)
        if key != expected_key:
            raise MalformedAgentReturn(
                f"Expected key {expected_key!r} at this position; got {key!r}."
            )
        if not value.strip():
            raise MalformedAgentReturn(
                f"Value for key {key!r} is whitespace-only."
            )
        parsed[key] = value.strip()

    verdict = parsed["verdict"]
    file_val = parsed["file"]
    section = parsed["section"]

    # Validate verdict token when agent name is known
    if agent_name is not None:
        allowed = AGENT_VERDICT_TOKENS.get(agent_name)
        if allowed is not None and verdict not in allowed:
            raise MalformedAgentReturn(
                f"Verdict {verdict!r} is not in the allowed set for agent "
                f"{agent_name!r}: {sorted(allowed)}."
            )

    return verdict, file_val, section


def token_count_proxy(text: str) -> float:
    """Approximate token count using a whitespace-word proxy.

    Uses ``len(re.findall(r'\\S+', text)) * 1.3`` — the same proxy as T02 /
    T22 canonical definition (L8, round 1, 2026-04-27).  Accuracy is not
    load-bearing; magnitude is.  No ``tiktoken`` dependency — adding a
    test-only dep would trigger the dependency-auditor on a foundation task.

    Args:
        text: Any string (typically an agent's full return text).

    Returns:
        An approximate floating-point token count.
    """
    return len(re.findall(r"\S+", text)) * 1.3
