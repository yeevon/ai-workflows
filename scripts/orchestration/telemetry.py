"""Telemetry wrapper for per-cycle sub-agent invocation records.

Task: M20 Task 22 — Per-cycle token telemetry per agent.
Relationship: Orchestration-layer helper (scripts/orchestration/); no dependency on
  ai_workflows/ package. Called by slash-command orchestrators at each Task-spawn
  boundary to persist raw token counts + model + effort + wall-clock + verdict to
  ``runs/<task>/cycle_<N>/<agent>.usage.json``.

  Downstream consumers:
  - T06 (shadow-audit study): reads these records to compute per-cell quota deltas.
  - T07 (dynamic model dispatch): calibrates defaults against observed counts.
  - T23 (cache-breakpoint discipline): reads cache_read_input_tokens for verification.
  - T27 (tool-result clearing): reads input_tokens for rotation trigger.

  Quota / cost proxy aggregation is T06's analysis-script scope (not this script).

CLI:
    python scripts/orchestration/telemetry.py spawn  --task m20_t01 --cycle 1
        --agent auditor --model claude-opus-4-7 --effort high

    python scripts/orchestration/telemetry.py complete --task m20_t01 --cycle 1
        --agent auditor --input-tokens 12450 --output-tokens 387
        --cache-creation 8200 --cache-read 4250
        --verdict PASS --fragment-path 'runs/m20_t01/cycle_1/auditor_issue.md'
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def _record_path(task: str, cycle: int, agent: str) -> Path:
    """Return the canonical path for a telemetry record.

    Path convention: ``runs/<task>/cycle_<N>/<agent>.usage.json``.
    The ``<task>`` component uses the zero-padded ``m<MM>_t<NN>`` shorthand
    per audit M12 convention.

    Args:
        task: Zero-padded task shorthand, e.g. ``m20_t01``.
        cycle: 1-based cycle number.
        agent: Agent name, e.g. ``auditor``.

    Returns:
        A ``pathlib.Path`` (not yet created).
    """
    return Path("runs") / task / f"cycle_{cycle}" / f"{agent}.usage.json"


def _now_iso() -> str:
    """Return current UTC time as an ISO-8601 string ending in ``Z``."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Atomic JSON read / write
# ---------------------------------------------------------------------------

def _read_record(path: Path) -> dict:
    """Read a JSON record from disk; return empty dict if missing."""
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _write_record_atomic(path: Path, record: dict) -> None:
    """Write ``record`` to ``path`` atomically via temp-file + rename.

    Creates the parent directory tree if needed.  The rename is atomic on
    POSIX filesystems, so concurrent writers cannot produce a partially-written
    JSON file.

    Args:
        path: Destination path for the JSON record.
        record: Python dict to serialise.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    # Write to a temp file in the same directory so rename is same-filesystem.
    dir_fd = path.parent
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=dir_fd,
        suffix=".tmp",
        delete=False,
    ) as tmp:
        json.dump(record, tmp, indent=2)
        tmp_path = Path(tmp.name)
    # Atomic rename: replaces destination if it exists (POSIX guarantee).
    tmp_path.replace(path)


# ---------------------------------------------------------------------------
# Subcommand: spawn
# ---------------------------------------------------------------------------

def cmd_spawn(args: argparse.Namespace) -> None:
    """Create (or overwrite) the spawn-time portion of a telemetry record.

    Captures: task, cycle, agent, spawn_ts, model, effort.
    Leaves completion fields absent (they are filled by ``cmd_complete``).

    Args:
        args: Parsed CLI arguments with task, cycle, agent, model, effort.

    Raises:
        SystemExit: On any write error.
    """
    path = _record_path(args.task, args.cycle, args.agent)
    record: dict = {
        "task": args.task,
        "cycle": args.cycle,
        "agent": args.agent,
        "spawn_ts": _now_iso(),
        "complete_ts": None,
        "wall_clock_seconds": None,
        "model": args.model,
        "effort": args.effort,
        "input_tokens": None,
        "output_tokens": None,
        "cache_creation_input_tokens": None,
        "cache_read_input_tokens": None,
        "verdict": None,
        "fragment_path": None,
        "section": None,
    }
    try:
        _write_record_atomic(path, record)
    except OSError as exc:
        print(f"telemetry spawn: write error — {exc}", file=sys.stderr)
        sys.exit(1)
    print(f"telemetry spawn: record created at {path}")


# ---------------------------------------------------------------------------
# Subcommand: complete
# ---------------------------------------------------------------------------

def cmd_complete(args: argparse.Namespace) -> None:
    """Update an existing spawn record with completion metrics.

    Reads the spawn record, merges completion fields, and atomically rewrites.
    If the spawn record is missing (orchestrator skipped spawn or wrote to the
    wrong path), creates a new record with ``spawn_ts=null`` and a warning.

    Args:
        args: Parsed CLI arguments with task, cycle, agent, completion metrics.

    Raises:
        SystemExit: On any read/write error.
    """
    path = _record_path(args.task, args.cycle, args.agent)
    try:
        record = _read_record(path)
    except (OSError, json.JSONDecodeError) as exc:
        print(
            f"telemetry complete: could not read spawn record ({exc}); "
            "creating new record with spawn_ts=null",
            file=sys.stderr,
        )
        record = {}

    # When no spawn record exists, populate a complete stub with all fields.
    if not record:
        print(
            "telemetry complete: no spawn record found; creating stub with spawn_ts=null",
            file=sys.stderr,
        )
        record = {
            "task": args.task,
            "cycle": args.cycle,
            "agent": args.agent,
            "spawn_ts": None,
            "complete_ts": None,
            "wall_clock_seconds": None,
            "model": None,
            "effort": None,
            "input_tokens": None,
            "output_tokens": None,
            "cache_creation_input_tokens": None,
            "cache_read_input_tokens": None,
            "verdict": None,
            "fragment_path": None,
            "section": None,
        }

    complete_ts = _now_iso()
    spawn_ts = record.get("spawn_ts")
    if spawn_ts:
        try:
            t0 = datetime.fromisoformat(spawn_ts.replace("Z", "+00:00"))
            t1 = datetime.fromisoformat(complete_ts.replace("Z", "+00:00"))
            wall_clock = int((t1 - t0).total_seconds())
        except ValueError:
            wall_clock = None
    else:
        wall_clock = None

    record.update({
        "complete_ts": complete_ts,
        "wall_clock_seconds": wall_clock,
        "input_tokens": args.input_tokens,
        "output_tokens": args.output_tokens,
        "cache_creation_input_tokens": args.cache_creation,
        "cache_read_input_tokens": args.cache_read,
        "verdict": args.verdict,
        "fragment_path": args.fragment_path,
        "section": args.section,
    })

    try:
        _write_record_atomic(path, record)
    except OSError as exc:
        print(f"telemetry complete: write error — {exc}", file=sys.stderr)
        sys.exit(1)
    print(f"telemetry complete: record updated at {path}")


# ---------------------------------------------------------------------------
# Aggregation helper (for T04 iter-shipped retrofit)
# ---------------------------------------------------------------------------

def aggregate_cycle_records(task: str, cycle: int) -> list[dict]:
    """Read all ``*.usage.json`` files for a given task/cycle.

    Returns a list of record dicts, sorted by agent name.  Records with no
    ``complete_ts`` (spawn-only, e.g. from a crashed orchestrator) are included
    with their null fields — callers decide how to render them.

    Args:
        task: Zero-padded task shorthand, e.g. ``m20_t01``.
        cycle: 1-based cycle number.

    Returns:
        Sorted list of record dicts (empty if the directory does not exist).
    """
    cycle_dir = Path("runs") / task / f"cycle_{cycle}"
    if not cycle_dir.exists():
        return []
    records = []
    for json_file in sorted(cycle_dir.glob("*.usage.json")):
        try:
            with json_file.open("r", encoding="utf-8") as fh:
                records.append(json.load(fh))
        except (OSError, json.JSONDecodeError):
            pass  # Skip corrupt files silently — orchestrator logs the error.
    return records


def format_telemetry_table(records: list[dict]) -> str:
    """Render a Markdown telemetry table from a list of usage records.

    Columns: Cycle | Agent | Model | Effort | Input tokens | Output tokens |
             Cache hit % | Verdict.

    Cache hit % = cache_read / (cache_read + cache_creation) × 100, or ``—``
    if both are null (surface-check found them unavailable).

    Args:
        records: List of record dicts from :func:`aggregate_cycle_records`.

    Returns:
        Markdown table string including the header row.  Empty string if no
        records are provided.
    """
    if not records:
        return ""

    header = (
        "| Cycle | Agent | Model | Effort | Input tokens | Output tokens "
        "| Cache hit % | Verdict |\n"
        "| --- | --- | --- | --- | --- | --- | --- | --- |"
    )
    rows: list[str] = []
    for r in records:
        cycle = r.get("cycle", "—")
        agent = r.get("agent", "—")
        model = r.get("model") or "—"
        effort = r.get("effort") or "—"
        input_tok = r.get("input_tokens")
        output_tok = r.get("output_tokens")
        cache_creation = r.get("cache_creation_input_tokens")
        cache_read = r.get("cache_read_input_tokens")
        verdict = r.get("verdict") or "—"

        input_str = str(input_tok) if input_tok is not None else "—"
        output_str = str(output_tok) if output_tok is not None else "—"

        if cache_read is not None and cache_creation is not None:
            total_cache = cache_read + cache_creation
            if total_cache > 0:
                pct = round(cache_read / total_cache * 100, 1)
                cache_pct_str = f"{pct}%"
            else:
                cache_pct_str = "0.0%"
        else:
            cache_pct_str = "—"

        rows.append(
            f"| {cycle} | {agent} | {model} | {effort} | {input_str} "
            f"| {output_str} | {cache_pct_str} | {verdict} |"
        )

    return header + "\n" + "\n".join(rows)


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    """Build and return the argument parser for the telemetry CLI.

    Returns:
        Configured :class:`argparse.ArgumentParser`.
    """
    parser = argparse.ArgumentParser(
        prog="telemetry.py",
        description=(
            "Per-cycle sub-agent telemetry capture. "
            "Records land at runs/<task>/cycle_<N>/<agent>.usage.json."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # spawn subcommand
    p_spawn = sub.add_parser(
        "spawn",
        help="Create the spawn-time record (call before Task spawn).",
    )
    p_spawn.add_argument("--task", required=True, help="Task shorthand, e.g. m20_t01")
    p_spawn.add_argument("--cycle", required=True, type=int, help="Cycle number (1-based)")
    p_spawn.add_argument("--agent", required=True, help="Agent name, e.g. auditor")
    p_spawn.add_argument("--model", required=True, help="Model slug, e.g. claude-opus-4-7")
    p_spawn.add_argument(
        "--effort",
        required=True,
        choices=["low", "medium", "high", "max", "xhigh"],
        help="Effort level passed to the Task spawn",
    )

    # complete subcommand
    p_complete = sub.add_parser(
        "complete",
        help="Update the record with completion metrics (call after Task return).",
    )
    p_complete.add_argument("--task", required=True, help="Task shorthand, e.g. m20_t01")
    p_complete.add_argument("--cycle", required=True, type=int, help="Cycle number (1-based)")
    p_complete.add_argument("--agent", required=True, help="Agent name, e.g. auditor")
    p_complete.add_argument(
        "--input-tokens",
        required=True,
        type=int,
        help="input_tokens from Task response (or regex proxy)",
    )
    p_complete.add_argument(
        "--output-tokens",
        required=True,
        type=int,
        help="output_tokens from Task response",
    )
    p_complete.add_argument(
        "--cache-creation",
        required=False,
        type=int,
        default=None,
        help="cache_creation_input_tokens (null if surface-check found unavailable)",
    )
    p_complete.add_argument(
        "--cache-read",
        required=False,
        type=int,
        default=None,
        help="cache_read_input_tokens (null if surface-check found unavailable)",
    )
    p_complete.add_argument(
        "--verdict",
        required=True,
        help="Verdict string from T01 schema (e.g. PASS, BUILT, SHIP)",
    )
    p_complete.add_argument(
        "--fragment-path",
        required=False,
        default=None,
        help="Path to the durable artifact the agent wrote (from T01 'file:' line)",
    )
    p_complete.add_argument(
        "--section",
        required=False,
        default=None,
        help="Section header from T01 'section:' line",
    )

    return parser


def main(argv: list[str] | None = None) -> None:
    """Entry point for the telemetry CLI.

    Args:
        argv: Optional argument list (defaults to ``sys.argv[1:]``).
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "spawn":
        cmd_spawn(args)
    elif args.command == "complete":
        cmd_complete(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
