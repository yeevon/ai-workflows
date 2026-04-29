"""Cache-breakpoint verification harness for orchestrator sub-agent spawns.

Task: M20 Task 23 — Cache-breakpoint discipline.
Relationship: Reads T22 telemetry records (``runs/<task>/cycle_<N>/<agent>.usage.json``)
  and asserts that spawn 2's ``cache_read_input_tokens`` > 80% of the stable-prefix
  token count, confirming Claude Code's cache breakpoint is correctly placed on the
  last *stable* block.

  Addresses the 5–20x session-cost blowup failure mode documented in
  anthropics/claude-code issues #27048 / #34629 / #42338 / #43657.

Background
----------
Claude Code caches the stable prefix of each sub-agent spawn prompt.  If the
cache breakpoint sits *inside* the dynamic context (e.g. because the prefix
contains a per-call timestamp), Claude re-caches on every spawn and the
``cache_read_input_tokens`` on call 2 is 0 instead of ≈stable-prefix-size.

This script verifies the discipline by comparing two consecutive telemetry
records for the same agent:

- Spawn 1: ``cache_creation_input_tokens`` ≈ stable-prefix-token-count,
  ``cache_read_input_tokens`` ≈ 0.
- Spawn 2 (within 5-min TTL): ``cache_read_input_tokens``
  > 80% of stable-prefix-token-count.

If the assertion fails, the harness writes a HIGH finding and exits with
code 2 so that the caller (orchestrator) can surface it.

CLI
---
Real-run mode (operator uses this outside autopilot)::

    python scripts/orchestration/cache_verify.py \\
        --agent auditor --task m12_t01

Dry-run mode (hermetic, reads two existing telemetry records)::

    python scripts/orchestration/cache_verify.py \\
        --agent auditor --task m12_t01 --dry-run \\
        --spawn1-record runs/m12_t01/cycle_1/auditor.usage.json \\
        --spawn2-record runs/m12_t01/cycle_2/auditor.usage.json

Exit codes
----------
- 0 : Verification PASS (spawn 2 read ≥ 80% of stable-prefix tokens).
- 1 : Verification SKIP (TTL window expired, i.e. > 5 min between spawns).
- 2 : Verification FAIL (spawn 2 read < 80%; HIGH finding surfaced).
- 3 : Configuration / input error (bad record, missing fields).

Output
------
Results are written to ``runs/<task>/cache_verification.txt`` and echoed
to stdout.

AC-7 deferral
-------------
The empirical validation (re-running M12 T01 audit cycle twice in close
succession and asserting cache hit on spawn 2) is deferred to operator-resume
outside the autopilot iteration.  Reasons: recursive-subprocess confound when
invoking ``claude`` from inside an active claude session; 5-min cache TTL makes
timing fragile; telemetry attribution conflict (validation records would pollute
``runs/m12_t01/``).  See ``runs/cache_verification/methodology.md`` for the
operator runbook.  Parallel to M20 T06 L5 deferral.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Cache TTL on Claude Code (5 minutes, or 1 h with extended-cache-ttl header).
#: Verification skips if the gap between spawn 1 and spawn 2 exceeds this.
CACHE_TTL_SECONDS: int = 5 * 60  # 5 minutes

#: Minimum fraction of stable-prefix tokens that spawn 2 must read from cache
#: for the verification to PASS.
CACHE_HIT_THRESHOLD: float = 0.80

# ---------------------------------------------------------------------------
# Telemetry record helpers
# ---------------------------------------------------------------------------


def _read_record(path: Path) -> dict:
    """Read a JSON telemetry record from disk.

    Args:
        path: Path to a ``<agent>.usage.json`` record written by T22
            ``telemetry.py complete``.

    Returns:
        Parsed JSON dict.

    Raises:
        FileNotFoundError: If the record does not exist.
        ValueError: If the file is not valid JSON or is missing required fields.
    """
    if not path.exists():
        raise FileNotFoundError(f"Telemetry record not found: {path}")
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc
    return data


def _parse_ts(ts_str: str | None) -> datetime | None:
    """Parse an ISO-8601 timestamp string ending in Z into a UTC datetime.

    Args:
        ts_str: Timestamp string such as ``"2026-04-28T14:00:00Z"`` or ``None``.

    Returns:
        An aware :class:`datetime` in UTC, or ``None`` if ``ts_str`` is ``None``
        or cannot be parsed.
    """
    if ts_str is None:
        return None
    try:
        return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    except ValueError:
        return None


def _elapsed_seconds(record1: dict, record2: dict) -> float | None:
    """Compute elapsed seconds between spawn 1 completion and spawn 2 start.

    Uses ``complete_ts`` of record1 and ``spawn_ts`` of record2.  Returns
    ``None`` when either timestamp is absent or unparseable.

    Args:
        record1: Spawn-1 telemetry record dict.
        record2: Spawn-2 telemetry record dict.

    Returns:
        Elapsed seconds as a float, or ``None`` if timestamps are unavailable.
    """
    t1 = _parse_ts(record1.get("complete_ts"))
    t2 = _parse_ts(record2.get("spawn_ts"))
    if t1 is None or t2 is None:
        return None
    delta = (t2 - t1).total_seconds()
    return abs(delta)


# ---------------------------------------------------------------------------
# Core verification logic
# ---------------------------------------------------------------------------


class VerificationResult:
    """Outcome of a single 2-call cache-breakpoint verification.

    Attributes:
        status: One of ``"PASS"``, ``"FAIL"``, ``"SKIP"``, ``"ERROR"``.
        message: Human-readable explanation.
        spawn1_cache_creation: ``cache_creation_input_tokens`` from spawn 1 (or None).
        spawn1_cache_read: ``cache_read_input_tokens`` from spawn 1 (or None).
        spawn2_cache_read: ``cache_read_input_tokens`` from spawn 2 (or None).
        stable_prefix_tokens: Inferred stable-prefix token count (from spawn 1 creation).
        elapsed_seconds: Gap between spawn 1 completion and spawn 2 start (or None).
        threshold: Minimum hit fraction required (always :data:`CACHE_HIT_THRESHOLD`).
    """

    def __init__(
        self,
        status: str,
        message: str,
        spawn1_cache_creation: int | None = None,
        spawn1_cache_read: int | None = None,
        spawn2_cache_read: int | None = None,
        stable_prefix_tokens: int | None = None,
        elapsed_seconds: float | None = None,
    ) -> None:
        self.status = status
        self.message = message
        self.spawn1_cache_creation = spawn1_cache_creation
        self.spawn1_cache_read = spawn1_cache_read
        self.spawn2_cache_read = spawn2_cache_read
        self.stable_prefix_tokens = stable_prefix_tokens
        self.elapsed_seconds = elapsed_seconds
        self.threshold = CACHE_HIT_THRESHOLD

    def to_text(self, agent: str, task: str) -> str:
        """Render a human-readable verification report.

        Args:
            agent: Agent name (e.g. ``"auditor"``).
            task: Task shorthand (e.g. ``"m12_t01"``).

        Returns:
            Multi-line string suitable for ``runs/<task>/cache_verification.txt``.
        """
        lines = [
            f"# Cache-breakpoint verification — {agent} / {task}",
            f"Status: {self.status}",
            f"Message: {self.message}",
            f"Threshold: {self.threshold * 100:.0f}% of stable-prefix tokens",
        ]
        if self.elapsed_seconds is not None:
            lines.append(f"Elapsed between spawn 1 complete and spawn 2 start: "
                         f"{self.elapsed_seconds:.1f}s (TTL={CACHE_TTL_SECONDS}s)")
        lines.append("")
        lines.append("## Spawn 1 telemetry")
        lines.append(f"  cache_creation_input_tokens: {self.spawn1_cache_creation}")
        lines.append(f"  cache_read_input_tokens:     {self.spawn1_cache_read}")
        lines.append(f"  stable_prefix_tokens (inferred): {self.stable_prefix_tokens}")
        lines.append("")
        lines.append("## Spawn 2 telemetry")
        lines.append(f"  cache_read_input_tokens: {self.spawn2_cache_read}")
        if self.stable_prefix_tokens is not None and self.spawn2_cache_read is not None:
            ratio = (
                self.spawn2_cache_read / self.stable_prefix_tokens
                if self.stable_prefix_tokens > 0
                else 0.0
            )
            lines.append(f"  hit ratio: {ratio:.1%} (threshold: {self.threshold:.0%})")
        return "\n".join(lines) + "\n"


def verify_cache_discipline(
    record1: dict,
    record2: dict,
) -> VerificationResult:
    """Verify cache-breakpoint discipline using two consecutive telemetry records.

    Implements the 2-call verification logic:

    1. Check TTL: if elapsed time between spawn 1 complete and spawn 2 start
       is ≥ :data:`CACHE_TTL_SECONDS`, return SKIP (cache likely expired;
       result is indeterminate, not a regression).
    2. Infer stable-prefix token count from spawn 1's
       ``cache_creation_input_tokens``.  If 0 or None, return ERROR (no
       creation event means no cacheable prefix was written — possibly a first
       run in a fresh session, or cache_creation was not captured).
    3. Assert spawn 2's ``cache_read_input_tokens`` >= threshold × stable count.
       Return PASS or FAIL accordingly.

    Args:
        record1: Parsed T22 telemetry dict for spawn 1.
        record2: Parsed T22 telemetry dict for spawn 2.

    Returns:
        A :class:`VerificationResult` with status PASS / FAIL / SKIP / ERROR.
    """
    # Extract raw fields (all are nullable in the T22 schema).
    s1_creation = record1.get("cache_creation_input_tokens")
    s1_read = record1.get("cache_read_input_tokens")
    s2_read = record2.get("cache_read_input_tokens")

    elapsed = _elapsed_seconds(record1, record2)

    # Step 1 — TTL boundary.
    if elapsed is not None and elapsed >= CACHE_TTL_SECONDS:
        return VerificationResult(
            status="SKIP",
            message=(
                f"Elapsed {elapsed:.0f}s ≥ TTL {CACHE_TTL_SECONDS}s — cache likely "
                "expired between spawns; result is indeterminate, not a regression."
            ),
            spawn1_cache_creation=s1_creation,
            spawn1_cache_read=s1_read,
            spawn2_cache_read=s2_read,
            stable_prefix_tokens=s1_creation,
            elapsed_seconds=elapsed,
        )

    # Step 2 — Check spawn 1 created a non-zero cache entry.
    if not s1_creation:
        return VerificationResult(
            status="ERROR",
            message=(
                "Spawn 1 cache_creation_input_tokens is 0 or None — no stable prefix "
                "was written to cache.  Possible causes: first call in a fresh session "
                "with no prior cache, or the telemetry record did not capture "
                "cache_creation (cache_creation=null in T22 record)."
            ),
            spawn1_cache_creation=s1_creation,
            spawn1_cache_read=s1_read,
            spawn2_cache_read=s2_read,
            stable_prefix_tokens=s1_creation,
            elapsed_seconds=elapsed,
        )

    # Step 3 — Assert spawn 2 read ≥ threshold × stable-prefix.
    # Distinguish "key absent" (schema mismatch / partial T22 record) from
    # "key present and zero" (genuine cache miss); return ERROR in the former
    # case so the operator is not chasing a phantom cache regression.
    if s2_read is None and "cache_read_input_tokens" not in record2:
        return VerificationResult(
            status="ERROR",
            message=(
                "Spawn 2 record is missing the 'cache_read_input_tokens' field entirely — "
                "possible partial T22 capture or schema mismatch.  "
                "This is NOT the same as a genuine cache miss (value present and zero).  "
                "Inspect the spawn-2 telemetry record before reacting as a cache regression."
            ),
            spawn1_cache_creation=s1_creation,
            spawn1_cache_read=s1_read,
            spawn2_cache_read=None,
            stable_prefix_tokens=s1_creation,
            elapsed_seconds=elapsed,
        )
    stable_tokens: int = s1_creation
    read2: int = s2_read if s2_read is not None else 0
    ratio = read2 / stable_tokens if stable_tokens > 0 else 0.0

    if ratio >= CACHE_HIT_THRESHOLD:
        return VerificationResult(
            status="PASS",
            message=(
                f"Spawn 2 read {read2} / {stable_tokens} tokens "
                f"({ratio:.1%} ≥ {CACHE_HIT_THRESHOLD:.0%}) — "
                "cache breakpoint correctly placed on last stable block."
            ),
            spawn1_cache_creation=s1_creation,
            spawn1_cache_read=s1_read,
            spawn2_cache_read=s2_read,
            stable_prefix_tokens=stable_tokens,
            elapsed_seconds=elapsed,
        )
    else:
        return VerificationResult(
            status="FAIL",
            message=(
                f"🚧 Cache breakpoint regression — spawn 2 read {read2} / "
                f"{stable_tokens} tokens ({ratio:.1%} < {CACHE_HIT_THRESHOLD:.0%}). "
                "Likely cause: per-request timestamp, UUID, or hostname interpolated "
                "into the stable prefix (see spawn_prompt_template.md "
                "§Stable-prefix discipline)."
            ),
            spawn1_cache_creation=s1_creation,
            spawn1_cache_read=s1_read,
            spawn2_cache_read=s2_read,
            stable_prefix_tokens=stable_tokens,
            elapsed_seconds=elapsed,
        )


# ---------------------------------------------------------------------------
# CLI — dry-run mode
# ---------------------------------------------------------------------------


def run_dry_run(
    agent: str,
    task: str,
    spawn1_path: Path,
    spawn2_path: Path,
    output_dir: Path | None,
) -> int:
    """Run verification in dry-run mode using two existing telemetry records.

    No real ``claude`` subprocess is invoked.  The harness reads the records at
    ``spawn1_path`` and ``spawn2_path``, runs :func:`verify_cache_discipline`,
    writes the report to ``runs/<task>/cache_verification.txt``, and returns the
    appropriate exit code.

    Args:
        agent: Agent name (for report header).
        task: Task shorthand (for output path).
        spawn1_path: Path to spawn-1 telemetry record.
        spawn2_path: Path to spawn-2 telemetry record.
        output_dir: Directory for output file; defaults to ``runs/<task>/``.

    Returns:
        Exit code: 0=PASS, 1=SKIP, 2=FAIL, 3=ERROR.
    """
    try:
        record1 = _read_record(spawn1_path)
        record2 = _read_record(spawn2_path)
    except (FileNotFoundError, ValueError) as exc:
        msg = f"ERROR: {exc}"
        print(msg, file=sys.stderr)
        return 3

    result = verify_cache_discipline(record1, record2)
    report = result.to_text(agent, task)

    out_dir = output_dir if output_dir is not None else Path("runs") / task
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "cache_verification.txt"
    out_path.write_text(report, encoding="utf-8")

    print(report)
    print(f"Report written to: {out_path}")

    status_to_exit = {"PASS": 0, "SKIP": 1, "FAIL": 2, "ERROR": 3}
    return status_to_exit.get(result.status, 3)


# ---------------------------------------------------------------------------
# CLI — real-run mode (operator-side, outside autopilot)
# ---------------------------------------------------------------------------


def run_real(agent: str, task: str, output_dir: Path | None) -> int:
    """Print instructions for operator-side empirical validation.

    Real-run mode requires the operator to:
    1. Run the agent twice in close succession (within 5-min TTL) outside autopilot.
    2. Ensure T22 telemetry records were written for both spawns.
    3. Re-invoke with ``--dry-run --spawn1-record ... --spawn2-record ...``.

    This function prints the runbook and exits 0 (not an error — operator
    must follow up manually).  See ``runs/cache_verification/methodology.md``
    for the full operator runbook.

    Args:
        agent: Agent name.
        task: Task shorthand.
        output_dir: Unused in real-run mode (operator drives the flow).

    Returns:
        Exit code 0 (informational — no verification actually ran).
    """
    runbook = (
        f"# Cache-breakpoint verification — real-run mode\n"
        f"Agent: {agent}  Task: {task}\n\n"
        "Real-run mode does NOT invoke the 'claude' subprocess directly.\n"
        "Reason: recursive subprocess from inside an active claude session\n"
        "creates measurement confounds (per M20 T23 AC-7 deferral).\n\n"
        "Operator steps:\n"
        "  1. Outside an active autopilot session, run:\n"
        f"       python scripts/orchestration/telemetry.py spawn \\\n"
        f"           --task {task} --cycle 1 --agent {agent} \\\n"
        f"           --model claude-opus-4-7 --effort high\n"
        f"     Then invoke the agent (e.g. via /audit {task}).\n"
        f"     Then run:\n"
        f"       python scripts/orchestration/telemetry.py complete \\\n"
        f"           --task {task} --cycle 1 --agent {agent} \\\n"
        f"           --input-tokens <N> --output-tokens <N> \\\n"
        f"           --cache-creation <N> --cache-read <N> --verdict PASS\n\n"
        "  2. Immediately repeat for cycle 2 (within 5-min cache TTL).\n\n"
        "  3. Run verification in dry-run mode:\n"
        f"       python scripts/orchestration/cache_verify.py \\\n"
        f"           --agent {agent} --task {task} --dry-run \\\n"
        f"           --spawn1-record runs/{task}/cycle_1/{agent}.usage.json \\\n"
        f"           --spawn2-record runs/{task}/cycle_2/{agent}.usage.json\n\n"
        "See runs/cache_verification/methodology.md for the full runbook.\n"
    )
    print(runbook)
    return 0


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser.

    Returns:
        Configured :class:`argparse.ArgumentParser`.
    """
    parser = argparse.ArgumentParser(
        prog="cache_verify.py",
        description=(
            "Cache-breakpoint verification harness (M20 Task 23). "
            "Reads T22 telemetry records and asserts spawn 2's "
            "cache_read_input_tokens > 80% of stable-prefix-token-count."
        ),
    )
    parser.add_argument(
        "--agent",
        required=True,
        help="Agent name (e.g. 'auditor', 'builder').",
    )
    parser.add_argument(
        "--task",
        required=True,
        help="Task shorthand (e.g. 'm12_t01').",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Dry-run mode: read two existing telemetry records and verify "
            "without invoking a real 'claude' subprocess."
        ),
    )
    parser.add_argument(
        "--spawn1-record",
        type=Path,
        default=None,
        help="Path to spawn-1 telemetry record (required with --dry-run).",
    )
    parser.add_argument(
        "--spawn2-record",
        type=Path,
        default=None,
        help="Path to spawn-2 telemetry record (required with --dry-run).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help=(
            "Directory for cache_verification.txt output. "
            "Defaults to runs/<task>/."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point.

    Args:
        argv: Argument list (defaults to sys.argv[1:]).

    Returns:
        Exit code (see module docstring).
    """
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.dry_run:
        if args.spawn1_record is None or args.spawn2_record is None:
            parser.error("--dry-run requires --spawn1-record and --spawn2-record")
        return run_dry_run(
            agent=args.agent,
            task=args.task,
            spawn1_path=args.spawn1_record,
            spawn2_path=args.spawn2_record,
            output_dir=args.output_dir,
        )
    else:
        return run_real(
            agent=args.agent,
            task=args.task,
            output_dir=args.output_dir,
        )


if __name__ == "__main__":
    sys.exit(main())
