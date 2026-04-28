"""Tests for telemetry aggregation — T04 iter-shipped retrofit.

Task: M20 Task 22 — Per-cycle token telemetry per agent.
Relationship: Hermetic tests for the aggregation helpers in
  scripts/orchestration/telemetry.py.  Verifies 3-cycle × 5-agent fixture
  → 15 rows; cache-hit % computed correctly; Telemetry summary section emitted
  in the iter-shipped table format.

ACs verified here:
- AC-4: T04's aggregation hook reads telemetry records into iter_<N>_shipped.md.
- AC-6: tests/orchestrator/test_telemetry_aggregation.py passes.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


def _load_telemetry_module(repo_root: Path):
    """Load scripts/orchestration/telemetry.py as a module."""
    mod_path = repo_root / "scripts" / "orchestration" / "telemetry.py"
    spec = importlib.util.spec_from_file_location("telemetry", mod_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def repo_root() -> Path:
    """Return the repository root path."""
    return Path(__file__).parent.parent.parent


@pytest.fixture
def telemetry(repo_root):
    """Load the telemetry module."""
    return _load_telemetry_module(repo_root)


# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------

AGENTS = ["builder", "auditor", "sr-dev", "sr-sdet", "security-reviewer"]


def _make_record(
    task: str,
    cycle: int,
    agent: str,
    input_tokens: int = 1000,
    output_tokens: int = 200,
    cache_creation: int | None = 600,
    cache_read: int | None = 400,
    verdict: str = "PASS",
    model: str = "claude-sonnet-4-6",
    effort: str = "high",
) -> dict:
    """Build a minimal telemetry record dict for fixture construction."""
    return {
        "task": task,
        "cycle": cycle,
        "agent": agent,
        "spawn_ts": "2026-04-28T10:00:00Z",
        "complete_ts": "2026-04-28T10:02:00Z",
        "wall_clock_seconds": 120,
        "model": model,
        "effort": effort,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cache_creation_input_tokens": cache_creation,
        "cache_read_input_tokens": cache_read,
        "verdict": verdict,
        "fragment_path": f"runs/{task}/cycle_{cycle}/{agent}_output.md",
        "section": "—",
    }


def _write_records(tmp_path: Path, task: str, cycles: int, agents: list[str]) -> list[dict]:
    """Write telemetry records for all cycles × agents to tmp_path/runs/."""
    records = []
    for cycle in range(1, cycles + 1):
        cycle_dir = tmp_path / "runs" / task / f"cycle_{cycle}"
        cycle_dir.mkdir(parents=True, exist_ok=True)
        for agent in agents:
            rec = _make_record(task=task, cycle=cycle, agent=agent)
            record_path = cycle_dir / f"{agent}.usage.json"
            record_path.write_text(json.dumps(rec, indent=2), encoding="utf-8")
            records.append(rec)
    return records


# ---------------------------------------------------------------------------
# aggregate_cycle_records tests
# ---------------------------------------------------------------------------

class TestAggregateCycleRecords:
    """Tests for telemetry.aggregate_cycle_records()."""

    def test_3x5_fixture_returns_15_records(self, telemetry, tmp_path, monkeypatch):
        """3-cycle × 5-agent fixture returns 15 records total across 3 calls."""
        monkeypatch.chdir(tmp_path)
        _write_records(tmp_path, "m20_t22_agg", cycles=3, agents=AGENTS)

        total = 0
        for cycle in range(1, 4):
            records = telemetry.aggregate_cycle_records("m20_t22_agg", cycle)
            assert len(records) == 5, f"cycle {cycle} should have 5 agent records"
            total += len(records)

        assert total == 15, "3 cycles × 5 agents = 15 records"

    def test_records_sorted_by_agent_name(self, telemetry, tmp_path, monkeypatch):
        """aggregate_cycle_records returns records sorted by agent name."""
        monkeypatch.chdir(tmp_path)
        _write_records(tmp_path, "m20_t22_sort", cycles=1, agents=AGENTS)

        records = telemetry.aggregate_cycle_records("m20_t22_sort", 1)
        agent_names = [r["agent"] for r in records]
        assert agent_names == sorted(agent_names)

    def test_missing_directory_returns_empty_list(self, telemetry, tmp_path, monkeypatch):
        """aggregate_cycle_records returns [] when cycle directory does not exist."""
        monkeypatch.chdir(tmp_path)
        records = telemetry.aggregate_cycle_records("m20_t22_missing", 1)
        assert records == []

    def test_corrupt_json_file_skipped(self, telemetry, tmp_path, monkeypatch):
        """Corrupt JSON files are skipped silently; valid records are returned."""
        monkeypatch.chdir(tmp_path)
        cycle_dir = tmp_path / "runs" / "m20_t22_corrupt" / "cycle_1"
        cycle_dir.mkdir(parents=True, exist_ok=True)

        # Write one valid record
        valid_rec = _make_record("m20_t22_corrupt", 1, "builder")
        (cycle_dir / "builder.usage.json").write_text(
            json.dumps(valid_rec), encoding="utf-8"
        )
        # Write one corrupt record
        (cycle_dir / "zz_corrupt.usage.json").write_text(
            "{ not valid json", encoding="utf-8"
        )

        records = telemetry.aggregate_cycle_records("m20_t22_corrupt", 1)
        assert len(records) == 1
        assert records[0]["agent"] == "builder"


# ---------------------------------------------------------------------------
# format_telemetry_table tests
# ---------------------------------------------------------------------------

class TestFormatTelemetryTable:
    """Tests for telemetry.format_telemetry_table()."""

    def test_cache_hit_pct_computed_correctly(self, telemetry):
        """Cache-hit % = cache_read / (cache_read + cache_creation) × 100."""
        # cache_read=400, cache_creation=600 → hit% = 400/1000 = 40.0%
        records = [_make_record("m20_t22", 1, "auditor", cache_creation=600, cache_read=400)]
        table = telemetry.format_telemetry_table(records)
        assert "40.0%" in table

    def test_cache_hit_pct_100_percent(self, telemetry):
        """100% cache hit when cache_creation=0."""
        records = [_make_record("m20_t22", 1, "auditor", cache_creation=0, cache_read=500)]
        table = telemetry.format_telemetry_table(records)
        assert "100.0%" in table

    def test_cache_hit_pct_zero_percent(self, telemetry):
        """0% cache hit when cache_read=0."""
        records = [_make_record("m20_t22", 1, "auditor", cache_creation=800, cache_read=0)]
        table = telemetry.format_telemetry_table(records)
        assert "0.0%" in table

    def test_cache_hit_pct_when_both_cache_fields_zero(self, telemetry):
        """Cache-hit % shows 0.0% when both cache_creation and cache_read are integer 0.

        This exercises the ``else: cache_pct_str = "0.0%"`` divide-by-zero guard at
        ``telemetry.py:303-304``.  With ``cache_creation=0`` and ``cache_read=0``,
        ``total_cache = 0``, so the ``if total_cache > 0`` branch is skipped and the
        else fallback must fire.

        Discriminating-positive: if the ``else: cache_pct_str = "0.0%"`` branch at
        ``telemetry.py:303-304`` were removed (or the condition were inverted), this
        test would raise ``ZeroDivisionError`` (or produce a ``KeyError`` / ``"—"``
        instead of ``"0.0%"``) because ``total_cache == 0`` with no fallback.  The
        existing ``test_cache_hit_pct_zero_percent`` uses ``cache_creation=800`` so
        ``total_cache=800 > 0`` — it never reaches the else branch and therefore does
        NOT cover this regression.
        """
        records = [
            _make_record("m20_t22", 1, "auditor", cache_creation=0, cache_read=0)
        ]
        table = telemetry.format_telemetry_table(records)
        assert "0.0%" in table, (
            "Both cache fields are integer 0; expected the divide-by-zero guard "
            "to return '0.0%', not crash or show '—'."
        )

    def test_cache_hit_pct_dash_when_null(self, telemetry):
        """Cache-hit % shows — when both cache fields are null."""
        records = [
            _make_record("m20_t22", 1, "auditor", cache_creation=None, cache_read=None)
        ]
        table = telemetry.format_telemetry_table(records)
        # The — symbol should appear in the cache-hit column
        assert "—" in table

    def test_table_has_header_row(self, telemetry):
        """Output table contains the required header columns."""
        records = [_make_record("m20_t22", 1, "auditor")]
        table = telemetry.format_telemetry_table(records)
        assert "Cycle" in table
        assert "Agent" in table
        assert "Model" in table
        assert "Effort" in table
        assert "Input tokens" in table
        assert "Output tokens" in table
        assert "Cache hit %" in table
        assert "Verdict" in table

    def test_empty_records_returns_empty_string(self, telemetry):
        """format_telemetry_table returns empty string for empty input."""
        assert telemetry.format_telemetry_table([]) == ""

    def test_15_records_produce_15_data_rows(self, telemetry):
        """3-cycle × 5-agent (15 records) produces 15 data rows in the table."""
        records = []
        for cycle in range(1, 4):
            for agent in AGENTS:
                records.append(_make_record("m20_t22", cycle, agent))
        table = telemetry.format_telemetry_table(records)
        # Each row line starts with | — count data rows (not header/separator)
        lines = table.strip().split("\n")
        # Lines: header row, separator row, then N data rows
        data_rows = [
            row for row in lines
            if row.startswith("|") and "---" not in row and "Cycle" not in row
        ]
        assert len(data_rows) == 15

    def test_no_quota_proxy_column(self, telemetry):
        """Table does NOT include a quota_consumption_proxy column (T06 scope)."""
        records = [_make_record("m20_t22", 1, "auditor")]
        table = telemetry.format_telemetry_table(records)
        assert "quota" not in table.lower()
        assert "proxy" not in table.lower()


# ---------------------------------------------------------------------------
# Telemetry section in iter-shipped fixture (T04 retrofit)
# ---------------------------------------------------------------------------

class TestIterShippedTelemetrySection:
    """Tests that the iter-shipped artifact template includes the Telemetry summary section."""

    def test_helpers_make_iter_shipped_includes_telemetry_section(self, repo_root):
        """_helpers.make_iter_shipped() includes a ## Telemetry summary section."""
        # Import _helpers from tests/orchestrator/
        helpers_path = repo_root / "tests" / "orchestrator" / "_helpers.py"
        spec = importlib.util.spec_from_file_location("_helpers", helpers_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        artifact = mod.make_iter_shipped(
            run_timestamp="20260428T100000Z",
            iteration=1,
            date="2026-04-28",
            verdict="PROCEED",
            task_shipped="task_22_per_cycle_telemetry.md",
            cycles=1,
            commit_sha="abc1234",
            files_touched=["scripts/orchestration/telemetry.py"],
            auditor_verdict="PASS",
        )

        assert "## Telemetry summary" in artifact

    def test_iter_shipped_required_sections_include_telemetry(self, repo_root):
        """ITER_SHIPPED_PROCEED_SECTIONS includes '## Telemetry summary'."""
        helpers_path = repo_root / "tests" / "orchestrator" / "_helpers.py"
        spec = importlib.util.spec_from_file_location("_helpers", helpers_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        assert "## Telemetry summary" in mod.ITER_SHIPPED_PROCEED_SECTIONS
