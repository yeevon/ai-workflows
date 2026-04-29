"""Hermetic tests for scripts/orchestration/run_t06_study.py.

Task: M20 Task 06 — Shadow-Audit empirical study (cycles 4-5 harness-bug fixes).
Relationship: Tests the quota-projection formula, bail-manifest content, and
  dry-run path of the study harness.  No network, no claude subprocess, no git
  operations.  All I/O is inside tmp_path fixtures.

ACs verified here (cycle 4 FIX-1 sr-sdet):
- test_compute_quota_projection_uses_correct_scale_factor: verifies BLOCK-1 fix
  (formula uses × n_total_cells = 6, not × 30).
- test_bail_manifest_contains_aggregate_not_last_task_result: verifies BLOCK-2/
  FIX-1 fix (a1_summary dict shape, not stale single-task result).
- test_run_cell_dry_run_completes_without_subprocess: verifies run_cell dry_run=True
  writes result.json without invoking any subprocess.

ACs verified here (cycle 5 sr-sdet FIX-A + FIX-B):
- test_run_full_study_dry_run_completes_without_bail: verifies run_full_study
  dry_run=True completes (rc=0), writes study_manifest.json with total_pairs==30,
  and does NOT write bail_manifest.json (i==0 guard does not spuriously fire on
  zero tokens).
- test_single_cell_bail_manifest_shape: verifies the single-cell CLI bail path
  builds an a1_summary aggregate dict (fixes LOW-9 call-site bug).
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Module loader
# ---------------------------------------------------------------------------

def _load_harness(repo_root: Path):
    """Load scripts/orchestration/run_t06_study.py as an importable module."""
    mod_path = repo_root / "scripts" / "orchestration" / "run_t06_study.py"
    spec = importlib.util.spec_from_file_location("run_t06_study", mod_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def repo_root() -> Path:
    """Return the repository root (two levels above tests/)."""
    return Path(__file__).parent.parent.parent


@pytest.fixture(scope="module")
def harness(repo_root: Path):
    """Return the loaded run_t06_study module."""
    return _load_harness(repo_root)


# ---------------------------------------------------------------------------
# BLOCK-1 fix: _compute_quota_projection scale factor
# ---------------------------------------------------------------------------

class TestComputeQuotaProjection:
    """Verify that _compute_quota_projection scales by len(CELLS) = 6, not 30."""

    def test_compute_quota_projection_uses_correct_scale_factor(self, harness):
        """Scale factor must be n_total_cells (6) applied to the 5-task aggregate.

        With a1_total_tokens=300_000 (sum of 5 A1 tasks) and n_total_cells=6:
          projected_total = 300_000 × 6 = 1_800_000
          projected_pct   = 1_800_000 / 3_150_000 ≈ 57.14%
          bail_triggered  = True  (57.14% > 5%)

        The old formula (× 30) would give 9_000_000 tokens — a 5× overestimate.
        """
        fn = harness._compute_quota_projection
        result = fn(a1_total_tokens=300_000, n_total_cells=6)

        assert result["a1_tokens"] == 300_000
        assert result["projected_total"] == 1_800_000  # 300_000 × 6
        assert result["weekly_max_tokens"] == harness.WEEKLY_MAX_TOKENS
        # projected_pct ≈ 57.14%
        expected_pct = round(1_800_000 / harness.WEEKLY_MAX_TOKENS * 100, 2)
        assert abs(result["projected_pct"] - expected_pct) < 0.01
        assert result["bail_triggered"] is True

    def test_compute_quota_projection_default_n_total_cells_is_6(self, harness):
        """Default n_total_cells must be 6 (len(CELLS)), not 29 or 30.

        Verifies the arithmetic independently: 100_000 × 6 = 600_000.
        """
        fn = harness._compute_quota_projection
        result_default = fn(a1_total_tokens=100_000)
        assert result_default["projected_total"] == 600_000

    def test_compute_quota_projection_no_bail_when_low_tokens(self, harness):
        """Bail must NOT fire when projected cost is below 5% weekly budget."""
        fn = harness._compute_quota_projection
        # 5% of 3_150_000 = 157_500; input that keeps projection well below threshold
        # a1_total_tokens = 1_000 → projected = 6_000 → pct ≈ 0.19%
        result = fn(a1_total_tokens=1_000, n_total_cells=6)
        assert result["bail_triggered"] is False
        assert result["projected_total"] == 6_000


# ---------------------------------------------------------------------------
# BLOCK-2 / FIX-1 fix: _write_bail_manifest receives aggregate not last task
# ---------------------------------------------------------------------------

class TestBailManifestShape:
    """Verify the bail_manifest.json schema matches the updated _write_bail_manifest."""

    def test_bail_manifest_contains_aggregate_not_last_task_result(
        self, harness, tmp_path, monkeypatch
    ):
        """bail_manifest.json must contain a1_summary with a list of task results.

        The old code passed a single run_cell result dict (the last loop variable).
        The fix constructs an a1_summary dict:
          {"a1_task_results": [...], "a1_total_tokens": <int>}
        """
        # Redirect STUDY_ROOT to tmp_path so the manifest lands in a clean dir
        monkeypatch.setattr(harness, "STUDY_ROOT", tmp_path)

        fake_projection = {
            "a1_tokens": 50_000,
            "projected_total": 300_000,
            "weekly_max_tokens": harness.WEEKLY_MAX_TOKENS,
            "projected_pct": 9.52,
            "bail_threshold_pct": 5.0,
            "bail_triggered": True,
        }
        fake_task_results = [
            {"cell": "A1", "task_id": "m12_t01", "tokens": {"total_tokens": 20_000}},
            {"cell": "A1", "task_id": "m12_t02", "tokens": {"total_tokens": 30_000}},
        ]
        a1_summary = {
            "a1_task_results": fake_task_results,
            "a1_total_tokens": 50_000,
        }

        harness._write_bail_manifest(fake_projection, a1_summary)

        manifest_path = tmp_path / "bail_manifest.json"
        assert manifest_path.exists(), "bail_manifest.json was not created"

        with manifest_path.open() as fh:
            manifest = json.load(fh)

        # Must have a1_summary key (not a1_result)
        assert "a1_summary" in manifest, "manifest must have 'a1_summary' key, not 'a1_result'"
        assert "a1_result" not in manifest, "old 'a1_result' key must not be present"

        # a1_summary must be the aggregate dict shape
        assert isinstance(manifest["a1_summary"], dict)
        assert "a1_task_results" in manifest["a1_summary"]
        assert isinstance(manifest["a1_summary"]["a1_task_results"], list)
        assert manifest["a1_summary"]["a1_total_tokens"] == 50_000
        assert len(manifest["a1_summary"]["a1_task_results"]) == 2

        # Standard fields must be present
        assert manifest["bail_triggered"] is True
        assert "quota_projection" in manifest
        assert "bail_ts" in manifest
        assert "reason" in manifest


# ---------------------------------------------------------------------------
# FIX-1 sr-sdet: dry-run path completes without subprocess
# ---------------------------------------------------------------------------

class TestRunCellDryRun:
    """Verify run_cell with dry_run=True writes result.json and calls no subprocess."""

    def test_run_cell_dry_run_completes_without_subprocess(
        self, harness, tmp_path, monkeypatch
    ):
        """run_cell(dry_run=True) must write result.json without invoking claude or git.

        Monkeypatches STUDY_ROOT so output goes to tmp_path.
        Monkeypatches _get_current_branch (git call) to raise if called — ensures the
        dry_run path truly skips all subprocess invocations.
        """
        monkeypatch.setattr(harness, "STUDY_ROOT", tmp_path)

        # Any git call in dry_run mode means the code is NOT honouring dry_run
        def _fail_if_called(*_args, **_kwargs):
            raise AssertionError("_get_current_branch must not be called in dry_run mode")

        monkeypatch.setattr(harness, "_get_current_branch", _fail_if_called)

        task = harness.STUDY_TASKS[0]  # m12_t01
        cell_def = harness.CELLS["A1"]

        result = harness.run_cell(
            cell="A1",
            task=task,
            builder_model=cell_def["builder_model"],
            auditor_model=cell_def["auditor_model"],
            effort=cell_def["effort"],
            timeout=60,
            repo_root=tmp_path,
            dry_run=True,
        )

        # result dict must be returned with expected shape
        assert result["cell"] == "A1"
        assert result["task_id"] == task["task_id"]
        assert result["returncode"] == 0
        assert result["stdout_tail"] == "[DRY RUN]"

        # result.json must be written
        result_path = tmp_path / "A1-m12_t01" / "result.json"
        assert result_path.exists(), f"result.json not written at {result_path}"

        with result_path.open() as fh:
            written = json.load(fh)
        assert written["returncode"] == 0
        assert written["cell"] == "A1"


# ---------------------------------------------------------------------------
# FIX-A (cycle 5 sr-sdet): run_full_study dry-run end-to-end path
# ---------------------------------------------------------------------------

class TestRunFullStudyDryRun:
    """Verify run_full_study with dry_run=True completes without bail (FIX-A)."""

    def test_run_full_study_dry_run_completes_without_bail(
        self, harness, tmp_path, monkeypatch
    ):
        """run_full_study(dry_run=True) must return 0 and write study_manifest.json.

        The i==0 bail-out guard must NOT fire on dry_run because token sums are zero,
        which keeps projected_pct at 0% — well below the 5% bail threshold.
        No bail_manifest.json should be created.
        """
        monkeypatch.setattr(harness, "STUDY_ROOT", tmp_path / "study")

        rc = harness.run_full_study(repo_root=tmp_path, timeout=60, dry_run=True)

        assert rc == 0, f"run_full_study returned non-zero: {rc}"

        bail_manifest = tmp_path / "study" / "bail_manifest.json"
        assert not bail_manifest.exists(), (
            "bail_manifest.json must NOT exist in a dry_run with zero tokens"
        )

        manifest_path = tmp_path / "study" / "study_manifest.json"
        assert manifest_path.exists(), "study_manifest.json must be written on success"

        manifest = json.loads(manifest_path.read_text())
        assert manifest["total_pairs"] == 30, (
            f"Expected 30 pairs (6 cells × 5 tasks), got {manifest['total_pairs']}"
        )


# ---------------------------------------------------------------------------
# FIX-B (cycle 5 sr-sdet / closes LOW-9): single-cell CLI bail a1_summary shape
# ---------------------------------------------------------------------------

class TestSingleCellBailManifestShape:
    """Verify the single-cell CLI bail path writes a correctly-shaped a1_summary (FIX-B)."""

    def test_single_cell_bail_manifest_shape(self, harness, tmp_path, monkeypatch):
        """main(['--dry-run', 'cell', '--cell', 'A1', '--task', 'm12_t01']) with a
        monkeypatched _compute_quota_projection that returns bail_triggered=True must
        write bail_manifest.json with a1_summary containing a1_task_results (list) and
        a1_total_tokens (int).

        This pins the LOW-9 call-site fix: the cell subcommand must pass an aggregate
        a1_summary dict, not a raw run_cell result dict, to _write_bail_manifest.
        """
        monkeypatch.setattr(harness, "STUDY_ROOT", tmp_path / "study")

        def _fake_projection(a1_total_tokens: int, n_total_cells: int = 6) -> dict:
            return {
                "a1_tokens": a1_total_tokens,
                "projected_total": 999_999,
                "weekly_max_tokens": harness.WEEKLY_MAX_TOKENS,
                "projected_pct": 99.9,
                "bail_threshold_pct": 5.0,
                "bail_triggered": True,
            }

        monkeypatch.setattr(harness, "_compute_quota_projection", _fake_projection)

        # main() calls sys.exit(2) on bail — catch it
        with pytest.raises(SystemExit) as exc_info:
            harness.main(["--dry-run", "cell", "--cell", "A1", "--task", "m12_t01"])
        assert exc_info.value.code == 2

        bail = tmp_path / "study" / "bail_manifest.json"
        assert bail.exists(), "bail_manifest.json must be written on single-cell bail"

        manifest = json.loads(bail.read_text())
        assert "a1_summary" in manifest, "manifest must have 'a1_summary' key"
        assert isinstance(manifest["a1_summary"]["a1_task_results"], list), (
            "a1_task_results must be a list"
        )
        assert isinstance(manifest["a1_summary"]["a1_total_tokens"], int), (
            "a1_total_tokens must be an int"
        )
