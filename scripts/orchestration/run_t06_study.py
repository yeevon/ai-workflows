"""Harness for the M20 T06 Shadow-Audit empirical study.

Task: M20 Task 06 — Shadow-Audit empirical study (6-cell matrix).
Relationship: Orchestration-layer helper (scripts/orchestration/). No dependency on
  ai_workflows/ package. Drives one cell-task pair of the 6 × 5 study matrix by:

  1. Creating a throwaway git branch from the pre-task commit.
  2. Invoking ``claude --dangerously-skip-permissions`` with ``/auto-implement <task>``
     and cell-specific model assignments via ``AIW_BUILDER_MODEL`` / ``AIW_AUDITOR_MODEL``
     environment variables.
  3. Collecting T22 telemetry records from ``runs/<task>/``.
  4. Writing a per-cell result JSON to ``runs/study_t06/<cell>-<task>/result.json``.

Usage (single cell-task pair)::

    python scripts/orchestration/run_t06_study.py \\
        --cell A1 \\
        --task m12_t01 \\
        --pre-task-commit a7f3e8f^  \\
        --builder-model claude-opus-4-6 \\
        --auditor-model claude-opus-4-6 \\
        --effort high \\
        --timeout 3600

Usage (full study — runs all 30 pairs sequentially, bail-out aware)::

    python scripts/orchestration/run_t06_study.py --full-study

Bail-out logic (L5 carry-over):
  After the first task pair (A1-m12_t01 only), the harness reads the telemetry records
  and computes a projected total quota footprint.  The projection scale factor is 30
  (6 cells × 5 tasks) — one pair extrapolated to the full study.  If
  first_pair_tokens × 30 / WEEKLY_MAX_TOKENS exceeds BAIL_THRESHOLD (default 5%), the
  harness writes a partial-result manifest and exits with code 2.  The caller should
  treat exit code 2 as "study self-limited; DEFER verdict applies."

Exit codes:
  0  — cell ran successfully; result.json written.
  1  — hard error (bad arguments, git failure, subprocess crash).
  2  — bail-out triggered (quota projection > BAIL_THRESHOLD); partial manifest written.

Note for sub-agent operators:
  This script calls ``git checkout -b`` and ``git checkout`` (to create/restore throwaway
  branches). These are the only git mutations performed. They are safe inside a throwaway
  branch; the script always restores the original branch on exit. The orchestrator (not the
  Builder sub-agent) is responsible for running this script.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Approximate weekly Max-subscription token budget (input + output combined).
# Based on observed ~450K tokens / day observed during M20 autopilot runs ×7 days.
# This is a conservative lower-bound; actual ceiling may be higher.
# T06's L5 bail-out fires if A1_tokens × 30 / WEEKLY_MAX_TOKENS > BAIL_THRESHOLD.
WEEKLY_MAX_TOKENS: int = 3_150_000  # 450K/day × 7 days

# Bail threshold: if projected study cost > 5% of weekly quota, self-limit.
BAIL_THRESHOLD: float = 0.05

# Study matrix definition
CELLS: dict[str, dict[str, str]] = {
    "A1": {
        "builder_model": "claude-opus-4-6",
        "auditor_model": "claude-opus-4-6",
        "effort": "high",
        "rationale": "Baseline — today's de-facto setup. Reference cell.",
    },
    "A2": {
        "builder_model": "claude-sonnet-4-6",
        "auditor_model": "claude-opus-4-6",
        "effort": "high",
        "rationale": "Cheaper Builder, Opus Auditor — research-brief prior for most cost saving.",
    },
    "A3": {
        "builder_model": "claude-sonnet-4-6",
        "auditor_model": "claude-sonnet-4-6",
        "effort": "high",
        "rationale": "Both Sonnet — validates whether Sonnet-Auditor matches Opus-Auditor.",
    },
    "A4": {
        "builder_model": "claude-opus-4-7",
        "auditor_model": "claude-opus-4-7",
        "effort": "high",
        "rationale": "Opus 4.7 pair — measures tokenizer overhead vs improved instruction-following.",  # noqa: E501
    },
    "A5": {
        "builder_model": "claude-sonnet-4-6",
        "auditor_model": "claude-opus-4-7",
        "effort": "high",
        "rationale": (
            "Sonnet Builder + Opus 4.7 Auditor — tests Mindstudio"
            " 'Opus 4.7 is the better Auditor' claim (research brief §3.2)."
        ),
    },
    "A6": {
        "builder_model": "claude-opus-4-6",
        "auditor_model": "claude-sonnet-4-6",
        "effort": "high",
        "rationale": "Auditor downgrade alone — reverse of A2.",
    },
}

# Study tasks (in run order per spec)
STUDY_TASKS: list[dict[str, str]] = [
    {
        "task_id": "m12_t01",
        "invoke_id": "m12 t01",
        "pre_task_commit": "b44f8d4",  # Commit just before M12 T01 landed (clean-tasks hardening)
        "kind": "code+test (small/mechanical)",
        "description": "Auditor TierConfigs — auditor-sonnet + auditor-opus registrations",
    },
    {
        "task_id": "m12_t02",
        "invoke_id": "m12 t02",
        "pre_task_commit": "a7f3e8f",  # After T01 landed
        "kind": "code+test (medium, multi-file)",
        "description": "AuditCascadeNode primitive",
    },
    {
        "task_id": "m12_t03",
        "invoke_id": "m12 t03",
        "pre_task_commit": "e7e8a31",  # After T08 landed (T03 depends on T08)
        "kind": "code+test+doc (complex, KDR proposal mid-run)",
        "description": "Workflow wiring — module-constant cascade enable",
    },
    {
        "task_id": "m16_t01",
        "invoke_id": "m16 t01",
        "pre_task_commit": "2fccd51",  # Before M20 Phase D specs
        "kind": "code+test+doc (large surface)",
        "description": "External workflow loader",
    },
    {
        "task_id": "m14_closeout",
        "invoke_id": "m14 closeout",
        "pre_task_commit": "2fccd51",  # Placeholder — doc-only task
        "kind": "doc-only",
        "description": "M14 close-out (doc-only task shape)",
    },
]

# Output root for all study artifacts
STUDY_ROOT = Path("runs/study_t06")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    """Return current UTC time as ISO-8601 string ending in Z."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _cell_dir(cell: str, task_id: str) -> Path:
    """Return the canonical output directory for a cell-task pair."""
    return STUDY_ROOT / f"{cell}-{task_id}"


def _read_telemetry_records(task_id: str) -> list[dict]:
    """Read all usage.json files produced during a task run.

    Scans ``runs/<task_id>/cycle_*/`` for ``*.usage.json`` files.

    Args:
        task_id: Task shorthand, e.g. ``m12_t01``.

    Returns:
        List of record dicts (may be empty if no telemetry was written).
    """
    task_run_dir = Path("runs") / task_id
    records: list[dict] = []
    if not task_run_dir.exists():
        return records
    for json_file in sorted(task_run_dir.glob("cycle_*/*.usage.json")):
        try:
            with json_file.open("r", encoding="utf-8") as fh:
                records.append(json.load(fh))
        except (OSError, json.JSONDecodeError):
            pass
    return records


def _sum_tokens(records: list[dict]) -> dict[str, int]:
    """Sum token counts across a list of telemetry records.

    Args:
        records: List of usage record dicts from ``_read_telemetry_records``.

    Returns:
        Dict with keys: input_tokens, output_tokens, cache_creation_input_tokens,
        cache_read_input_tokens, total_tokens.
    """
    totals: dict[str, int] = {
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": 0,
    }
    for r in records:
        for key in totals:
            val = r.get(key)
            if isinstance(val, int):
                totals[key] += val
    totals["total_tokens"] = (
        totals["input_tokens"]
        + totals["output_tokens"]
        + totals["cache_creation_input_tokens"]
        + totals["cache_read_input_tokens"]
    )
    return totals


def _compute_quota_projection(a1_total_tokens: int, n_total_cells: int = 6) -> dict:
    """Compute projected quota consumption for the full study from A1 data.

    Input: A1 cell aggregate (sum across all ``len(STUDY_TASKS)`` task runs for the A1 cell).
    Output: projection over all ``len(CELLS)`` cells.

    Projection formula:
        projected_total = a1_total_tokens × n_total_cells
            (A1 is one cell; multiply by total cell count to project full study)
        projected_pct = projected_total / WEEKLY_MAX_TOKENS

    The scale factor is ``n_total_cells`` (default 6 = ``len(CELLS)``), NOT 30, because
    ``a1_total_tokens`` is already the sum of all ``len(STUDY_TASKS)`` task pairs in A1.
    Multiplying by 30 would treat the 5-task aggregate as a per-pair cost, causing a 5×
    overestimate that would make the bail-out fire on every non-trivial run.

    Args:
        a1_total_tokens: Total token count aggregated across all A1 task runs
            (i.e. sum over all ``len(STUDY_TASKS)`` pairs in cell A1).
        n_total_cells: Total number of cells in the study (default ``len(CELLS)`` = 6).

    Returns:
        Dict with keys: a1_tokens, projected_total, weekly_max_tokens, projected_pct,
        bail_threshold_pct, bail_triggered.
    """
    projected_total = a1_total_tokens * n_total_cells
    projected_pct = projected_total / WEEKLY_MAX_TOKENS
    return {
        "a1_tokens": a1_total_tokens,
        "projected_total": projected_total,
        "weekly_max_tokens": WEEKLY_MAX_TOKENS,
        "projected_pct": round(projected_pct * 100, 2),
        "bail_threshold_pct": round(BAIL_THRESHOLD * 100, 2),
        "bail_triggered": projected_pct > BAIL_THRESHOLD,
    }


def _get_current_branch(repo_root: Path) -> str:
    """Return the current git branch name.

    Args:
        repo_root: Repository root path.

    Returns:
        Current branch name string.

    Raises:
        subprocess.CalledProcessError: If git command fails.
    """
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _create_throwaway_branch(
    repo_root: Path, pre_task_commit: str, branch_name: str
) -> None:
    """Create a throwaway branch at the pre-task commit.

    Args:
        repo_root: Repository root path.
        pre_task_commit: Git commit hash to base the throwaway branch on.
        branch_name: Name for the new throwaway branch.

    Raises:
        subprocess.CalledProcessError: If git command fails.
    """
    # Create new branch at the specified commit
    subprocess.run(
        ["git", "checkout", "-b", branch_name, pre_task_commit],
        cwd=repo_root,
        check=True,
    )


def _restore_branch(repo_root: Path, branch_name: str) -> None:
    """Restore (checkout) the named branch.

    Args:
        repo_root: Repository root path.
        branch_name: Name of the branch to restore.

    Raises:
        subprocess.CalledProcessError: If git command fails.
    """
    subprocess.run(
        ["git", "checkout", branch_name],
        cwd=repo_root,
        check=True,
    )


def _delete_throwaway_branch(repo_root: Path, branch_name: str) -> None:
    """Delete a throwaway branch (best-effort; logs but does not raise on failure).

    Args:
        repo_root: Repository root path.
        branch_name: Name of the branch to delete.
    """
    result = subprocess.run(
        ["git", "branch", "-D", branch_name],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(
            f"[run_t06_study] Warning: could not delete branch {branch_name}: "
            f"{result.stderr.strip()}",
            file=sys.stderr,
        )


def _run_auto_implement(
    repo_root: Path,
    invoke_id: str,
    builder_model: str,
    auditor_model: str,
    effort: str,
    timeout: int,
) -> dict:
    """Invoke /auto-implement <task> via the claude CLI subprocess.

    Uses ``AIW_BUILDER_MODEL`` and ``AIW_AUDITOR_MODEL`` environment variables
    (to be read by T07's dispatch helper, once shipped) plus the cell effort level.

    NOTE: T07 dynamic dispatch is not yet shipped at T06 time. The environment
    variables are set here so the harness is forward-compatible; current autopilot
    will use its default model assignments regardless.

    Args:
        repo_root: Repository root path.
        invoke_id: Task identifier string for the /auto-implement command, e.g. "m12 t01".
        builder_model: Builder model slug, e.g. "claude-opus-4-6".
        auditor_model: Auditor model slug, e.g. "claude-sonnet-4-6".
        effort: Effort level string, e.g. "high".
        timeout: Maximum seconds to wait for the subprocess.

    Returns:
        Dict with keys: returncode, stdout_tail, stderr_tail, wall_clock_seconds.
    """
    env = os.environ.copy()
    env["AIW_BUILDER_MODEL"] = builder_model
    env["AIW_AUDITOR_MODEL"] = auditor_model
    env["AIW_EFFORT"] = effort
    env["AIW_AUTONOMY_SANDBOX"] = "1"

    start_ts = time.monotonic()
    try:
        result = subprocess.run(
            [
                "claude",
                "--dangerously-skip-permissions",
                "--print",
                f"/auto-implement {invoke_id}",
            ],
            cwd=repo_root,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        wall_clock = int(time.monotonic() - start_ts)
        return {
            "returncode": result.returncode,
            "stdout_tail": result.stdout[-2000:] if result.stdout else "",
            "stderr_tail": result.stderr[-1000:] if result.stderr else "",
            "wall_clock_seconds": wall_clock,
        }
    except subprocess.TimeoutExpired:
        wall_clock = int(time.monotonic() - start_ts)
        return {
            "returncode": -1,
            "stdout_tail": "[TIMEOUT]",
            "stderr_tail": f"Subprocess timed out after {timeout}s",
            "wall_clock_seconds": wall_clock,
        }
    except FileNotFoundError:
        return {
            "returncode": -2,
            "stdout_tail": "",
            "stderr_tail": "claude CLI not found in PATH",
            "wall_clock_seconds": 0,
        }


def _write_result(cell_dir: Path, result: dict) -> None:
    """Write a cell result dict to ``<cell_dir>/result.json``.

    Args:
        cell_dir: Directory for the cell-task pair.
        result: Result dict to serialise.

    Raises:
        OSError: On write failure.
    """
    cell_dir.mkdir(parents=True, exist_ok=True)
    out_path = cell_dir / "result.json"
    with out_path.open("w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2)
    print(f"[run_t06_study] Result written to {out_path}")


def _write_bail_manifest(projection: dict, a1_summary: dict) -> None:
    """Write a bail-out manifest to ``runs/study_t06/bail_manifest.json``.

    The ``bail_manifest.json`` schema::

        {
          "bail_triggered": true,
          "bail_ts": "<ISO-8601>",
          "reason": "<human-readable string>",
          "quota_projection": { <_compute_quota_projection output> },
          "a1_summary": {
            "a1_task_results": [ <list of run_cell result dicts> ],
            "a1_total_tokens": <int>
          }
        }

    Args:
        projection: Quota projection dict from ``_compute_quota_projection``.
        a1_summary: Dict with keys ``a1_task_results`` (list of run_cell result dicts
            for all tasks in the A1 cell) and ``a1_total_tokens`` (total token count
            accumulated across those task results). Must represent the full A1 cell
            aggregate, NOT a single task result dict.
    """
    STUDY_ROOT.mkdir(parents=True, exist_ok=True)
    manifest = {
        "bail_triggered": True,
        "bail_ts": _now_iso(),
        "reason": (
            f"A1 baseline cell consumed {projection['a1_tokens']} tokens. "
            f"Projected full-study cost: {projection['projected_total']} tokens "
            f"({projection['projected_pct']}% of weekly Max quota). "
            f"Bail threshold: {projection['bail_threshold_pct']}%. "
            "DEFER verdict applies; resume cell-by-cell outside autopilot."
        ),
        "quota_projection": projection,
        "a1_summary": a1_summary,
    }
    out_path = STUDY_ROOT / "bail_manifest.json"
    with out_path.open("w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)
    print(f"[run_t06_study] Bail manifest written to {out_path}")


# ---------------------------------------------------------------------------
# Single-cell runner
# ---------------------------------------------------------------------------

def run_cell(
    cell: str,
    task: dict,
    builder_model: str,
    auditor_model: str,
    effort: str,
    timeout: int,
    repo_root: Path,
    dry_run: bool = False,
) -> dict:
    """Run one cell-task pair and return the result dict.

    Steps:
      1. Identify pre-task commit and create a throwaway branch.
      2. Invoke /auto-implement.
      3. Read T22 telemetry records produced during the run.
      4. Restore the original branch and delete the throwaway branch.
      5. Return the result dict.

    Args:
        cell: Cell ID, e.g. "A1".
        task: Task definition dict from STUDY_TASKS.
        builder_model: Builder model slug.
        auditor_model: Auditor model slug.
        effort: Effort level.
        timeout: Subprocess timeout in seconds.
        repo_root: Repository root path.
        dry_run: If True, skip the actual subprocess invocation (for testing).

    Returns:
        Result dict with keys: cell, task_id, builder_model, auditor_model, effort,
        spawn_ts, complete_ts, wall_clock_seconds, returncode, tokens, stdout_tail,
        stderr_tail.
    """
    cell_dir = _cell_dir(cell, task["task_id"])
    cell_dir.mkdir(parents=True, exist_ok=True)

    # Branch state is only needed for real (non-dry-run) runs.
    if dry_run:
        original_branch = "[DRY-RUN]"
        throwaway_branch = f"t06-study-{cell.lower()}-{task['task_id']}-dry-run"
    else:
        original_branch = _get_current_branch(repo_root)
        throwaway_branch = f"t06-study-{cell.lower()}-{task['task_id']}-{int(time.time())}"

    spawn_ts = _now_iso()
    run_result: dict = {
        "cell": cell,
        "task_id": task["task_id"],
        "task_kind": task["kind"],
        "builder_model": builder_model,
        "auditor_model": auditor_model,
        "effort": effort,
        "spawn_ts": spawn_ts,
        "complete_ts": None,
        "wall_clock_seconds": None,
        "returncode": None,
        "tokens": None,
        "stdout_tail": None,
        "stderr_tail": None,
        "throwaway_branch": throwaway_branch,
        "pre_task_commit": task["pre_task_commit"],
    }

    try:
        if not dry_run:
            # Step 1: Create throwaway branch
            print(
                f"[run_t06_study] Creating throwaway branch {throwaway_branch} "
                f"at commit {task['pre_task_commit']}"
            )
            _create_throwaway_branch(repo_root, task["pre_task_commit"], throwaway_branch)

            # Step 2: Invoke /auto-implement
            print(f"[run_t06_study] Running cell {cell} on task {task['invoke_id']}")
            invoke_result = _run_auto_implement(
                repo_root=repo_root,
                invoke_id=task["invoke_id"],
                builder_model=builder_model,
                auditor_model=auditor_model,
                effort=effort,
                timeout=timeout,
            )
        else:
            print(f"[run_t06_study] DRY RUN: skipping subprocess for {cell}-{task['task_id']}")
            invoke_result = {
                "returncode": 0,
                "stdout_tail": "[DRY RUN]",
                "stderr_tail": "",
                "wall_clock_seconds": 0,
            }

        # Step 3: Read telemetry records from the task run dir
        telemetry_records = _read_telemetry_records(task["task_id"])
        token_sums = _sum_tokens(telemetry_records)

        run_result.update({
            "complete_ts": _now_iso(),
            "wall_clock_seconds": invoke_result["wall_clock_seconds"],
            "returncode": invoke_result["returncode"],
            "tokens": token_sums,
            "stdout_tail": invoke_result["stdout_tail"],
            "stderr_tail": invoke_result["stderr_tail"],
            "telemetry_record_count": len(telemetry_records),
        })

    finally:
        if not dry_run:
            # Step 4: Restore original branch; raise on failure so the outer loop
            # does not continue on a corrupt repo (HEAD may still be on the throwaway
            # branch, in which case _delete_throwaway_branch would also fail).
            try:
                _restore_branch(repo_root, original_branch)
            except subprocess.CalledProcessError as exc:
                print(
                    f"[run_t06_study] FATAL: could not restore branch {original_branch}: {exc}",
                    file=sys.stderr,
                )
                raise
            # Step 5: Delete throwaway branch (only reached if restore succeeded)
            _delete_throwaway_branch(repo_root, throwaway_branch)

    _write_result(cell_dir, run_result)
    return run_result


# ---------------------------------------------------------------------------
# Full-study runner
# ---------------------------------------------------------------------------

def run_full_study(
    repo_root: Path,
    timeout: int = 3600,
    dry_run: bool = False,
) -> int:
    """Run the full 30-cell-task study sequentially with bail-out awareness.

    Runs A1 first (baseline). After A1, computes quota projection and applies
    the L5 bail-out if the projection exceeds BAIL_THRESHOLD. If bail-out fires,
    writes bail_manifest.json and returns exit code 2.

    Cells A2-A6 × all tasks run after A1 if no bail-out.

    Args:
        repo_root: Repository root path.
        timeout: Per-cell subprocess timeout in seconds.
        dry_run: If True, skip actual subprocess invocations.

    Returns:
        0 on success, 1 on hard error, 2 on bail-out.
    """
    print(f"[run_t06_study] Starting full study. Study root: {STUDY_ROOT}")
    STUDY_ROOT.mkdir(parents=True, exist_ok=True)

    study_results: list[dict] = []

    # Run A1 baseline first (all 5 tasks), with an early bail-out check after the
    # very first task pair (A1-m12_t01) per spec L5: "bail if cost exceeds 5%
    # projected to study end."  A single-pair projection uses scale factor 30
    # (6 cells × 5 tasks) to extrapolate one task pair to the full study.
    a1_cell = CELLS["A1"]
    a1_total_tokens = 0
    for i, task in enumerate(STUDY_TASKS):
        result = run_cell(
            cell="A1",
            task=task,
            builder_model=a1_cell["builder_model"],
            auditor_model=a1_cell["auditor_model"],
            effort=a1_cell["effort"],
            timeout=timeout,
            repo_root=repo_root,
            dry_run=dry_run,
        )
        study_results.append(result)
        if result.get("tokens"):
            a1_total_tokens += result["tokens"].get("total_tokens", 0)

        if i == 0:
            # L5 bail-out check: fire after A1-m12_t01 (the first task pair only).
            # The first pair's token count is used directly; scale factor = 30
            # (len(CELLS) × len(STUDY_TASKS)) projects one pair to the full study.
            first_pair_tokens = a1_total_tokens
            pair_scale = len(CELLS) * len(STUDY_TASKS)  # 30
            projected_total = first_pair_tokens * pair_scale
            projected_pct = projected_total / WEEKLY_MAX_TOKENS
            projection = {
                "a1_tokens": first_pair_tokens,
                "projected_total": projected_total,
                "weekly_max_tokens": WEEKLY_MAX_TOKENS,
                "projected_pct": round(projected_pct * 100, 2),
                "bail_threshold_pct": round(BAIL_THRESHOLD * 100, 2),
                "bail_triggered": projected_pct > BAIL_THRESHOLD,
            }
            print(
                f"[run_t06_study] First-pair ({task['task_id']}) tokens: {first_pair_tokens}. "
                f"Projected full-study ({pair_scale} pairs): "
                f"{projection['projected_pct']}% of weekly quota."
            )
            if projection["bail_triggered"]:
                print(
                    f"[run_t06_study] BAIL-OUT triggered after first task pair: projected cost "
                    f"{projection['projected_pct']}% > "
                    f"{projection['bail_threshold_pct']}% threshold.",
                    file=sys.stderr,
                )
                a1_summary = {
                    "a1_task_results": study_results,
                    "a1_total_tokens": a1_total_tokens,
                }
                _write_bail_manifest(projection, a1_summary)
                return 2

    # Full A1 aggregate projection (informational; bail already checked after pair 1)
    projection = _compute_quota_projection(a1_total_tokens)
    print(
        f"[run_t06_study] A1 baseline total tokens: {a1_total_tokens}. "
        f"Projected full-study (× {len(CELLS)} cells): "
        f"{projection['projected_pct']}% of weekly quota."
    )

    # Run remaining cells A2-A6 × all tasks
    remaining_cells = [c for c in CELLS if c != "A1"]
    for cell_id in remaining_cells:
        cell = CELLS[cell_id]
        for task in STUDY_TASKS:
            result = run_cell(
                cell=cell_id,
                task=task,
                builder_model=cell["builder_model"],
                auditor_model=cell["auditor_model"],
                effort=cell["effort"],
                timeout=timeout,
                repo_root=repo_root,
                dry_run=dry_run,
            )
            study_results.append(result)

    # Write full manifest
    manifest_path = STUDY_ROOT / "study_manifest.json"
    with manifest_path.open("w", encoding="utf-8") as fh:
        json.dump(
            {
                "study": "M20 T06 Shadow-Audit empirical study",
                "completed_ts": _now_iso(),
                "total_pairs": len(study_results),
                "results": study_results,
            },
            fh,
            indent=2,
        )
    print(f"[run_t06_study] Full study complete. Manifest: {manifest_path}")
    return 0


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    """Build and return the argument parser for the study harness.

    Returns:
        Configured :class:`argparse.ArgumentParser`.
    """
    parser = argparse.ArgumentParser(
        prog="run_t06_study.py",
        description=(
            "M20 T06 Shadow-Audit harness. Runs one cell-task pair (or the full study) "
            "against a throwaway branch and collects T22 telemetry."
        ),
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path("."),
        help="Repository root (default: current directory).",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=3600,
        help="Per-cell subprocess timeout in seconds (default: 3600).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip actual subprocess invocations (for testing harness logic).",
    )

    sub = parser.add_subparsers(dest="command")

    # Single-cell subcommand
    p_cell = sub.add_parser("cell", help="Run a single cell-task pair.")
    p_cell.add_argument(
        "--cell",
        required=True,
        choices=list(CELLS.keys()),
        help="Cell ID, e.g. A1.",
    )
    p_cell.add_argument(
        "--task",
        required=True,
        choices=[t["task_id"] for t in STUDY_TASKS],
        help="Task ID, e.g. m12_t01.",
    )
    p_cell.add_argument(
        "--builder-model",
        required=False,
        help="Override builder model (default: cell's default).",
    )
    p_cell.add_argument(
        "--auditor-model",
        required=False,
        help="Override auditor model (default: cell's default).",
    )
    p_cell.add_argument(
        "--effort",
        default="high",
        choices=["low", "medium", "high", "xhigh"],
        help="Effort level (default: high).",
    )

    # Full-study subcommand
    sub.add_parser("full-study", help="Run all 30 cell-task pairs sequentially.")

    return parser


def main(argv: list[str] | None = None) -> None:
    """Entry point for the study harness CLI.

    Args:
        argv: Optional argument list (defaults to ``sys.argv[1:]``).
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "cell":
        cell_def = CELLS[args.cell]
        task_def = next(t for t in STUDY_TASKS if t["task_id"] == args.task)
        result = run_cell(
            cell=args.cell,
            task=task_def,
            builder_model=args.builder_model or cell_def["builder_model"],
            auditor_model=args.auditor_model or cell_def["auditor_model"],
            effort=args.effort,
            timeout=args.timeout,
            repo_root=args.repo_root,
            dry_run=args.dry_run,
        )
        tokens = result.get("tokens") or {}
        projection = _compute_quota_projection(tokens.get("total_tokens", 0))
        print(
            f"[run_t06_study] Cell {args.cell} task {args.task} complete. "
            f"Tokens: {tokens.get('total_tokens', 0)}. "
            f"Quota projection if × 30: {projection['projected_pct']}%."
        )
        if projection["bail_triggered"]:
            # Build the same a1_summary aggregate shape the full-study path uses.
            # The single-cell path runs one task only, so the list has one entry.
            a1_summary = {
                "a1_task_results": [result],
                "a1_total_tokens": tokens.get("total_tokens", 0),
            }
            _write_bail_manifest(projection, a1_summary)
            sys.exit(2)

    elif args.command == "full-study":
        exit_code = run_full_study(
            repo_root=args.repo_root,
            timeout=args.timeout,
            dry_run=args.dry_run,
        )
        sys.exit(exit_code)

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
