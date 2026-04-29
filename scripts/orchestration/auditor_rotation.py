"""Auditor input-volume rotation trigger for the clean-implement / auto-implement loop.

Task: M20 Task 27 — Auditor input-volume threshold for cycle-rotation (client-side
  simulation of ``clear_tool_uses_20250919``).
Relationship: Orchestration-layer helper (scripts/orchestration/); no dependency on
  the ai_workflows/ package. Read by slash-command orchestrators after each Auditor
  spawn completes to decide whether the next Auditor spawn should receive a compacted
  input (cycle_summary.md + current diff only) instead of the standard pre-load set.

Downstream consumers:
- auto-implement.md: calls should_rotate() after reading auditor.usage.json for
  cycle N; uses the result to select the Auditor spawn input for cycle N+1.
- clean-implement.md: same pattern.
- T22 (telemetry.py): produces the auditor.usage.json records this module reads.
- T03 (cycle_summary.md): produces the compacted-input source (cycle_N/summary.md).

Design rationale:
- Path A (server-side clear_tool_uses_20250919 via agent frontmatter) is rejected per
  audit H6: Claude Code's Task tool accepts only name/description/tools/model in
  frontmatter; there is no mechanism to pass context_management.edits through.
- Path B (client-side rotation at cycle boundary) is what T27 ships: when an Auditor
  spawn's input_tokens climbs above 60K, the orchestrator gives the next cycle a
  compacted spawn input, simulating the effect of tool-result clearing.
- Threshold is 60K by default, tunable via AIW_AUDITOR_ROTATION_THRESHOLD env var.
- Compaction recovery target: the compacted input should be <= 30K tokens
  (cycle_summary + current diff + spec).

CLI smoke test (no agent spawns required):
    python scripts/orchestration/auditor_rotation.py --input-tokens 65000 --verdict OPEN
    # → prints ROTATE

    python scripts/orchestration/auditor_rotation.py --input-tokens 30000 --verdict OPEN
    # → prints NO-ROTATE

    python scripts/orchestration/auditor_rotation.py --input-tokens 65000 --verdict PASS
    # → prints NO-ROTATE (loop ends on PASS regardless of volume)
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Core rotation-decision logic
# ---------------------------------------------------------------------------

DEFAULT_THRESHOLD = 60_000


def get_threshold() -> int:
    """Return the rotation threshold from the environment (or the default).

    Reads AIW_AUDITOR_ROTATION_THRESHOLD as an integer.  Falls back to
    60000 (DEFAULT_THRESHOLD) if the env var is absent or does not parse as a
    positive integer string.

    Accepted values: positive integer strings only (e.g. ``"40000"``).
    All of the following fall back to the 60K default:
    - Absent env var.
    - Non-numeric strings (e.g. ``"not-a-number"``).
    - Negative integers (e.g. ``"-1"``): ``str.isdigit()`` returns False; silent
      fallback. There is no "disable rotation" sentinel — set the threshold to a
      very large value (e.g. ``"2000000"``) to suppress rotation in practice.
    - Zero (``"0"``): ``str.isdigit()`` returns True for ``"0"``, so ``get_threshold``
      would return 0 — which would cause every OPEN cycle to rotate (runaway behaviour).
      Callers that accept zero should guard explicitly; the helper itself does not
      accept zero as a valid threshold.
    - Float-formatted strings (e.g. ``"60000.0"``): ``str.isdigit()`` returns False;
      silent fallback to 60K default. Document the limitation: only pure positive
      integer strings are accepted.

    Returns:
        A positive integer token count at or above which rotation fires.
    """
    raw = os.environ.get("AIW_AUDITOR_ROTATION_THRESHOLD", "")
    stripped = raw.strip()
    if stripped.isdigit() and int(stripped) > 0:
        return int(stripped)
    return DEFAULT_THRESHOLD


def should_rotate(cycle_usage: dict, threshold: int = DEFAULT_THRESHOLD) -> bool:
    """Return True if the next Auditor spawn should use a compacted input.

    Reads the input_tokens and verdict fields from a T22 auditor.usage.json
    record (``cycle_usage``).  Fires when BOTH conditions hold:

    1. ``input_tokens >= threshold``.
    2. ``verdict`` is ``"OPEN"`` (loop continues — PASS ends the loop, so no
       rotation is needed; BLOCKED surfaces to the user before cycle N+1 starts).

    Path A (server-side clear_tool_uses_20250919) is explicitly NOT implemented
    here — see module docstring and audit H6.

    Args:
        cycle_usage: Dict with at least ``"input_tokens"`` (int) and
            ``"verdict"`` (str, one of PASS/OPEN/BLOCKED) keys.
            Extra keys (e.g. output_tokens, model) are ignored.
        threshold: Input-token count at or above which rotation fires.
            Defaults to 60000. Callers should use :func:`get_threshold` to
            honour the AIW_AUDITOR_ROTATION_THRESHOLD env var.

    Returns:
        True → use compacted input for the next Auditor spawn.
        False → use standard spawn input (no rotation).

    Examples:
        >>> should_rotate({"input_tokens": 65000, "verdict": "OPEN"})
        True
        >>> should_rotate({"input_tokens": 30000, "verdict": "OPEN"})
        False
        >>> should_rotate({"input_tokens": 65000, "verdict": "PASS"})
        False
        >>> should_rotate({"input_tokens": 65000, "verdict": "OPEN"}, threshold=40000)
        True
    """
    input_tokens = int(cycle_usage.get("input_tokens", 0))
    verdict = str(cycle_usage.get("verdict", "")).upper()

    # PASS ends the loop; BLOCKED surfaces to user — neither triggers rotation.
    if verdict != "OPEN":
        return False

    return input_tokens >= threshold


# ---------------------------------------------------------------------------
# Rotation log writer
# ---------------------------------------------------------------------------

def write_rotation_log(
    task_shorthand: str,
    cycle_n: int,
    input_tokens: int,
    runs_root: Path | None = None,
) -> Path:
    """Write the one-line rotation event record for cycle N.

    Record format (per T27 spec §Telemetry hook):
        ROTATED: cycle <N> input_tokens=<value>; cycle <N+1> spawn input
        compacted (cycle_summary + diff only)

    File lands at runs/<task>/cycle_<N>/auditor_rotation.txt.

    Args:
        task_shorthand: Zero-padded task shorthand, e.g. ``"m20_t27"``.
        cycle_n: The cycle number whose Auditor spawn triggered rotation.
        input_tokens: The input_tokens value from the cycle_N auditor.usage.json.
        runs_root: Override the root ``runs/`` directory (used by tests to
            redirect output to a tmp_path). Defaults to ``Path("runs")``.

    Returns:
        The Path of the rotation log file that was written.
    """
    if runs_root is None:
        runs_root = Path("runs")

    log_path = runs_root / task_shorthand / f"cycle_{cycle_n}" / "auditor_rotation.txt"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    record = (
        f"ROTATED: cycle {cycle_n} input_tokens={input_tokens}; "
        f"cycle {cycle_n + 1} spawn input compacted (cycle_summary + diff only)\n"
    )
    log_path.write_text(record, encoding="utf-8")
    return log_path


# ---------------------------------------------------------------------------
# Compacted-input builder
# ---------------------------------------------------------------------------

def build_compacted_auditor_spawn_input(
    task_spec_path: str,
    issue_file_path: str,
    project_context_brief: str,
    git_diff: str,
    cycle_summary_path: str,
    cycle_summary_content: str,
    cited_kdrs: list[str] | None = None,
) -> str:
    """Build the compacted Auditor spawn input for the next cycle after rotation.

    Per T27 §Mechanism step 2, the compacted input includes:
    - Task spec path (existing)
    - Issue file path (existing)
    - Current git diff (existing)
    - cycle_N/summary.md content (T03's structured summary) — replaces full
      prior chat history.

    NOT included:
    - Prior Builder reports' chat content.
    - Prior Auditor verdict text.
    - Prior tool-result content.
    - Whole milestone README content.
    - Whole architecture.md content.

    Args:
        task_spec_path: Repo-relative path to the task spec.
        issue_file_path: Repo-relative path to the issue file.
        project_context_brief: Verbatim project context brief.
        git_diff: Current git diff output.
        cycle_summary_path: Repo-relative path to the cycle N summary file.
        cycle_summary_content: Full content of the cycle N summary.
        cited_kdrs: KDR identifiers cited in the task spec. If None or empty,
            the §9 grid header pointer is used.

    Returns:
        A compacted spawn-prompt string for the Auditor.
    """
    if cited_kdrs:
        kdr_line = (
            "Relevant KDRs: " + ", ".join(cited_kdrs) +
            " — read §9 of design_docs/architecture.md on-demand for full text."
        )
    else:
        kdr_line = (
            "| ID | Decision | Source |\n"
            "| --- | --- | --- |\n"
            "(read §9 of design_docs/architecture.md on-demand for the full table)"
        )

    budget_directive = (
        "Output budget: 1-2K tokens. Durable findings live in the issue file you write;\n"
        "the return is the 3-line schema only — "
        "see .claude/commands/_common/agent_return_schema.md"
    )
    schema_reminder = (
        "Return per .claude/commands/_common/agent_return_schema.md — exactly 3 lines:\n"
        "verdict: <token>\n"
        "file: <path or —>\n"
        "section: <## header or —>\n"
        "No prose, no preamble, no chat body outside those three lines."
    )
    rotation_note = (
        "[T27 rotation: compacted input — prior tool-result content excluded; "
        "context reconstructed from cycle summary only]"
    )

    return (
        f"Task spec path: {task_spec_path}\n"
        f"Issue file path: {issue_file_path}\n\n"
        f"## Project context brief\n\n{project_context_brief}\n\n"
        f"## Relevant KDRs\n\n{kdr_line}\n\n"
        f"## Current diff\n\n```diff\n{git_diff}\n```\n\n"
        f"## Cycle summary ({cycle_summary_path})\n\n"
        f"{rotation_note}\n\n"
        f"{cycle_summary_content}\n\n"
        f"## Output budget\n\n{budget_directive}\n\n"
        f"## Return schema\n\n{schema_reminder}\n"
    )


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "Auditor rotation-trigger helper. "
            "Reads input_tokens + verdict and prints ROTATE or NO-ROTATE."
        ),
    )
    p.add_argument(
        "--input-tokens",
        type=int,
        required=True,
        help="input_tokens value from auditor.usage.json for cycle N.",
    )
    p.add_argument(
        "--verdict",
        required=True,
        choices=["PASS", "OPEN", "BLOCKED"],
        help="Auditor verdict for cycle N.",
    )
    p.add_argument(
        "--threshold",
        type=int,
        default=None,
        help=(
            "Rotation threshold override. If omitted, reads "
            "AIW_AUDITOR_ROTATION_THRESHOLD env var (default: 60000)."
        ),
    )
    return p


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for the auditor rotation trigger.

    Returns:
        0 → NO-ROTATE (standard spawn input).
        1 → ROTATE (compacted spawn input for next cycle).
    """
    parser = _build_parser()
    args = parser.parse_args(argv)

    threshold = args.threshold if args.threshold is not None else get_threshold()
    cycle_usage = {
        "input_tokens": args.input_tokens,
        "verdict": args.verdict,
    }
    if should_rotate(cycle_usage, threshold=threshold):
        print("ROTATE")
        return 1
    else:
        print("NO-ROTATE")
        return 0


if __name__ == "__main__":
    sys.exit(main())
