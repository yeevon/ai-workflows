"""Hermetic tests for the cache-breakpoint verification harness.

Task: M20 Task 23 — Cache-breakpoint discipline.
Relationship: Tests ``scripts/orchestration/cache_verify.py`` — specifically the
  core :func:`verify_cache_discipline` logic and the ``run_dry_run`` CLI path.
  No real ``claude`` subprocess is invoked; all inputs are synthetic telemetry
  record fixtures.

ACs covered:
- AC-4: Synthetic spawn-1 + spawn-2 with byte-identical prefix → verification PASS.
- AC-4: Synthetic spawn-1 + spawn-2 with per-call timestamp in prefix → FAIL
        (cache_read = 0 on spawn 2).
- AC-4: Synthetic spawn-1 outside cache TTL (> 5 min gap) → SKIP.
- AC-4: ``run_dry_run`` writes ``cache_verification.txt`` and returns correct exit code.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

# ---------------------------------------------------------------------------
# Load the module under test via importlib (scripts/ is not a package).
# ---------------------------------------------------------------------------

def _load_cache_verify():
    """Load scripts/orchestration/cache_verify.py as a module."""
    mod_path = (
        Path(__file__).parent.parent.parent
        / "scripts"
        / "orchestration"
        / "cache_verify.py"
    )
    spec = importlib.util.spec_from_file_location("cache_verify", mod_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_cv = _load_cache_verify()
CACHE_HIT_THRESHOLD = _cv.CACHE_HIT_THRESHOLD
verify_cache_discipline = _cv.verify_cache_discipline
run_dry_run = _cv.run_dry_run

# ---------------------------------------------------------------------------
# Fixtures — synthetic telemetry records
# ---------------------------------------------------------------------------

# A "good" spawn-1 record: cache was created with a 10 000-token stable prefix.
_SPAWN1_GOOD = {
    "task": "m12_t01",
    "cycle": 1,
    "agent": "auditor",
    "spawn_ts": "2026-04-28T14:00:00Z",
    "complete_ts": "2026-04-28T14:01:00Z",
    "wall_clock_seconds": 60,
    "model": "claude-opus-4-7",
    "effort": "high",
    "input_tokens": 12000,
    "output_tokens": 400,
    "cache_creation_input_tokens": 10000,
    "cache_read_input_tokens": 0,
    "verdict": "PASS",
    "fragment_path": None,
    "section": None,
}

# A "good" spawn-2 record: cache was read, >80% of stable prefix tokens.
_SPAWN2_GOOD = {
    "task": "m12_t01",
    "cycle": 2,
    "agent": "auditor",
    "spawn_ts": "2026-04-28T14:02:00Z",   # 1 minute after spawn-1 complete — within TTL
    "complete_ts": "2026-04-28T14:03:00Z",
    "wall_clock_seconds": 60,
    "model": "claude-opus-4-7",
    "effort": "high",
    "input_tokens": 2000,
    "output_tokens": 350,
    "cache_creation_input_tokens": 0,
    "cache_read_input_tokens": 9500,       # 9500 / 10000 = 95% — well above 80%
    "verdict": "PASS",
    "fragment_path": None,
    "section": None,
}

# Spawn-2 with broken cache: per-call timestamp invalidated the prefix.
_SPAWN2_BROKEN_CACHE = {
    **_SPAWN2_GOOD,
    "cache_read_input_tokens": 0,          # Cache miss — breakpoint is wrong
    "input_tokens": 12000,                 # Full re-cache; same input_tokens as spawn 1
}

# Spawn-2 outside the 5-minute cache TTL (> 5 min after spawn-1 complete).
_SPAWN2_OUTSIDE_TTL = {
    **_SPAWN2_GOOD,
    "spawn_ts": "2026-04-28T14:10:00Z",    # 9 minutes after spawn-1 complete
    "cache_read_input_tokens": 0,          # TTL expired; 0 is expected/indeterminate
}

# Spawn-1 with zero cache_creation (no stable prefix was written).
_SPAWN1_NO_CREATION = {
    **_SPAWN1_GOOD,
    "cache_creation_input_tokens": 0,
    "cache_read_input_tokens": 0,
}

# Spawn-1 with None cache_creation (field was not captured by T22).
_SPAWN1_NONE_CREATION = {
    **_SPAWN1_GOOD,
    "cache_creation_input_tokens": None,
}


# ---------------------------------------------------------------------------
# Tests — verify_cache_discipline
# ---------------------------------------------------------------------------


class TestVerifyCacheDiscipline:
    """Tests for the core verification logic."""

    def test_pass_when_spawn2_reads_above_threshold(self) -> None:
        """Byte-identical prefix → spawn 2 reads ≥80% of stable prefix → PASS."""
        result = verify_cache_discipline(_SPAWN1_GOOD, _SPAWN2_GOOD)
        assert result.status == "PASS"
        assert "correctly placed" in result.message
        assert result.spawn2_cache_read == 9500
        assert result.stable_prefix_tokens == 10000

    def test_fail_when_spawn2_reads_zero(self) -> None:
        """Per-call timestamp invalidated prefix → cache_read=0 on spawn 2 → FAIL."""
        result = verify_cache_discipline(_SPAWN1_GOOD, _SPAWN2_BROKEN_CACHE)
        assert result.status == "FAIL"
        assert "regression" in result.message.lower() or "breakpoint" in result.message.lower()
        assert result.spawn2_cache_read == 0
        assert result.stable_prefix_tokens == 10000

    def test_fail_message_contains_high_finding_marker(self) -> None:
        """FAIL result message contains the 🚧 marker for HIGH surface."""
        result = verify_cache_discipline(_SPAWN1_GOOD, _SPAWN2_BROKEN_CACHE)
        assert result.status == "FAIL"
        assert "🚧" in result.message

    def test_fail_message_references_stable_prefix_discipline(self) -> None:
        """FAIL message guides operator to the stable-prefix discipline doc."""
        result = verify_cache_discipline(_SPAWN1_GOOD, _SPAWN2_BROKEN_CACHE)
        assert "spawn_prompt_template.md" in result.message or "per-request" in result.message

    def test_skip_when_elapsed_exceeds_ttl(self) -> None:
        """Spawn 2 arrives > 5 min after spawn 1 → TTL expired → SKIP."""
        result = verify_cache_discipline(_SPAWN1_GOOD, _SPAWN2_OUTSIDE_TTL)
        assert result.status == "SKIP"
        assert "ttl" in result.message.lower() or "expired" in result.message.lower()

    def test_skip_ttl_boundary_exactly_at_limit(self) -> None:
        """Elapsed time exactly equal to TTL → SKIP (inclusive ge boundary: elapsed == TTL → SKIP).

        The ``>=`` operator in cache_verify.py means equality at the TTL limit is SKIP.
        """
        spawn2_at_boundary = {
            **_SPAWN2_GOOD,
            # spawn_ts exactly CACHE_TTL_SECONDS after spawn1's complete_ts
            "spawn_ts": "2026-04-28T14:06:00Z",  # 14:01:00 + 300s = 14:06:00
            "cache_read_input_tokens": 0,
        }
        result = verify_cache_discipline(_SPAWN1_GOOD, spawn2_at_boundary)
        assert result.status == "SKIP"

    def test_error_when_spawn1_has_no_cache_creation(self) -> None:
        """Spawn 1 cache_creation=0 (first run / not captured) → ERROR."""
        result = verify_cache_discipline(_SPAWN1_NO_CREATION, _SPAWN2_GOOD)
        assert result.status == "ERROR"
        assert "cache_creation" in result.message.lower()

    def test_error_when_spawn1_cache_creation_is_none(self) -> None:
        """Spawn 1 cache_creation=None (T22 did not capture it) → ERROR."""
        result = verify_cache_discipline(_SPAWN1_NONE_CREATION, _SPAWN2_GOOD)
        assert result.status == "ERROR"

    def test_pass_at_exactly_80_percent(self) -> None:
        """Spawn 2 reads exactly 80% of stable tokens → PASS (threshold is ≥)."""
        spawn2_exact = {**_SPAWN2_GOOD, "cache_read_input_tokens": 8000}  # 8000/10000 = 80%
        result = verify_cache_discipline(_SPAWN1_GOOD, spawn2_exact)
        assert result.status == "PASS"

    def test_fail_just_below_80_percent(self) -> None:
        """Spawn 2 reads 79.9% of stable tokens → FAIL."""
        spawn2_low = {**_SPAWN2_GOOD, "cache_read_input_tokens": 7999}  # 7999/10000 < 80%
        result = verify_cache_discipline(_SPAWN1_GOOD, spawn2_low)
        assert result.status == "FAIL"

    def test_result_carries_threshold_constant(self) -> None:
        """Result object always exposes the correct threshold value."""
        result = verify_cache_discipline(_SPAWN1_GOOD, _SPAWN2_GOOD)
        assert result.threshold == CACHE_HIT_THRESHOLD

    def test_elapsed_seconds_in_result(self) -> None:
        """Elapsed seconds between spawn 1 complete and spawn 2 start is captured."""
        result = verify_cache_discipline(_SPAWN1_GOOD, _SPAWN2_GOOD)
        # spawn1 complete_ts = 14:01:00, spawn2 spawn_ts = 14:02:00 → 60s
        assert result.elapsed_seconds is not None
        assert abs(result.elapsed_seconds - 60.0) < 1.0

    def test_none_timestamps_do_not_cause_skip(self) -> None:
        """Missing timestamps → elapsed=None → no TTL check → proceeds to step 2/3."""
        record1_no_ts = {**_SPAWN1_GOOD, "complete_ts": None}
        record2_no_ts = {**_SPAWN2_GOOD, "spawn_ts": None}
        result = verify_cache_discipline(record1_no_ts, record2_no_ts)
        # No TTL check; stable_prefix is 10000; spawn2 read = 9500 → PASS
        assert result.status == "PASS"

    def test_spawn2_missing_cache_read_input_tokens_key_returns_error(self) -> None:
        """Key 'cache_read_input_tokens' entirely absent from spawn-2 record → ERROR.

        Distinguishes a T22 schema mismatch / partial capture (key absent) from a
        genuine cache miss (key present with value 0).  A missing key must not
        silently coerce to a FAIL with misleading ratio output.
        """
        spawn2_missing_key = {
            k: v for k, v in _SPAWN2_GOOD.items() if k != "cache_read_input_tokens"
        }
        result = verify_cache_discipline(_SPAWN1_GOOD, spawn2_missing_key)
        assert result.status == "ERROR", (
            "Missing 'cache_read_input_tokens' key must return ERROR, not FAIL"
        )
        assert "missing" in result.message.lower() or "absent" in result.message.lower(), (
            "ERROR message should describe the missing field"
        )


# ---------------------------------------------------------------------------
# Tests — to_text report rendering
# ---------------------------------------------------------------------------


class TestVerificationResultToText:
    """Tests for the report rendering method."""

    def test_pass_report_contains_status(self) -> None:
        result = verify_cache_discipline(_SPAWN1_GOOD, _SPAWN2_GOOD)
        report = result.to_text("auditor", "m12_t01")
        assert "PASS" in report

    def test_fail_report_contains_status(self) -> None:
        result = verify_cache_discipline(_SPAWN1_GOOD, _SPAWN2_BROKEN_CACHE)
        report = result.to_text("auditor", "m12_t01")
        assert "FAIL" in report

    def test_report_contains_agent_and_task(self) -> None:
        result = verify_cache_discipline(_SPAWN1_GOOD, _SPAWN2_GOOD)
        report = result.to_text("auditor", "m12_t01")
        assert "auditor" in report
        assert "m12_t01" in report

    def test_report_contains_telemetry_values(self) -> None:
        result = verify_cache_discipline(_SPAWN1_GOOD, _SPAWN2_GOOD)
        report = result.to_text("auditor", "m12_t01")
        assert "10000" in report  # stable_prefix_tokens
        assert "9500" in report   # spawn2_cache_read


# ---------------------------------------------------------------------------
# Tests — run_dry_run CLI helper
# ---------------------------------------------------------------------------


class TestRunDryRun:
    """Tests for the run_dry_run function using tmp record files."""

    def _write_record(self, path: Path, record: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(record), encoding="utf-8")

    def test_dry_run_pass_exits_0(self, tmp_path: Path) -> None:
        """Good records → PASS → exit code 0."""
        spawn1 = tmp_path / "cycle_1" / "auditor.usage.json"
        spawn2 = tmp_path / "cycle_2" / "auditor.usage.json"
        self._write_record(spawn1, _SPAWN1_GOOD)
        self._write_record(spawn2, _SPAWN2_GOOD)
        code = run_dry_run("auditor", "m12_t01", spawn1, spawn2, tmp_path)
        assert code == 0

    def test_dry_run_fail_exits_2(self, tmp_path: Path) -> None:
        """Broken cache → FAIL → exit code 2."""
        spawn1 = tmp_path / "cycle_1" / "auditor.usage.json"
        spawn2 = tmp_path / "cycle_2" / "auditor.usage.json"
        self._write_record(spawn1, _SPAWN1_GOOD)
        self._write_record(spawn2, _SPAWN2_BROKEN_CACHE)
        code = run_dry_run("auditor", "m12_t01", spawn1, spawn2, tmp_path)
        assert code == 2

    def test_dry_run_skip_exits_1(self, tmp_path: Path) -> None:
        """TTL expired → SKIP → exit code 1."""
        spawn1 = tmp_path / "cycle_1" / "auditor.usage.json"
        spawn2 = tmp_path / "cycle_2" / "auditor.usage.json"
        self._write_record(spawn1, _SPAWN1_GOOD)
        self._write_record(spawn2, _SPAWN2_OUTSIDE_TTL)
        code = run_dry_run("auditor", "m12_t01", spawn1, spawn2, tmp_path)
        assert code == 1

    def test_dry_run_error_exits_3_on_missing_file(self, tmp_path: Path) -> None:
        """Missing record file → exit code 3."""
        spawn1 = tmp_path / "cycle_1" / "auditor.usage.json"
        spawn2 = tmp_path / "cycle_2" / "auditor.usage.json"
        # Only write spawn1; spawn2 is missing
        self._write_record(spawn1, _SPAWN1_GOOD)
        code = run_dry_run("auditor", "m12_t01", spawn1, spawn2, tmp_path)
        assert code == 3

    def test_dry_run_writes_output_file(self, tmp_path: Path) -> None:
        """run_dry_run writes cache_verification.txt to the output dir."""
        spawn1 = tmp_path / "cycle_1" / "auditor.usage.json"
        spawn2 = tmp_path / "cycle_2" / "auditor.usage.json"
        self._write_record(spawn1, _SPAWN1_GOOD)
        self._write_record(spawn2, _SPAWN2_GOOD)
        out_dir = tmp_path / "output"
        run_dry_run("auditor", "m12_t01", spawn1, spawn2, out_dir)
        assert (out_dir / "cache_verification.txt").exists()

    def test_dry_run_output_contains_pass_status(self, tmp_path: Path) -> None:
        """cache_verification.txt contains PASS on a good run."""
        spawn1 = tmp_path / "cycle_1" / "auditor.usage.json"
        spawn2 = tmp_path / "cycle_2" / "auditor.usage.json"
        self._write_record(spawn1, _SPAWN1_GOOD)
        self._write_record(spawn2, _SPAWN2_GOOD)
        out_dir = tmp_path / "output"
        run_dry_run("auditor", "m12_t01", spawn1, spawn2, out_dir)
        text = (out_dir / "cache_verification.txt").read_text()
        assert "PASS" in text

    def test_dry_run_output_contains_fail_status_and_high_marker(self, tmp_path: Path) -> None:
        """cache_verification.txt contains FAIL and 🚧 on a broken-cache run."""
        spawn1 = tmp_path / "cycle_1" / "auditor.usage.json"
        spawn2 = tmp_path / "cycle_2" / "auditor.usage.json"
        self._write_record(spawn1, _SPAWN1_GOOD)
        self._write_record(spawn2, _SPAWN2_BROKEN_CACHE)
        out_dir = tmp_path / "output"
        run_dry_run("auditor", "m12_t01", spawn1, spawn2, out_dir)
        text = (out_dir / "cache_verification.txt").read_text()
        assert "FAIL" in text
        assert "🚧" in text
