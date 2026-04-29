"""Tests for scripts/orchestration/telemetry.py — spawn/complete subcommands.

Task: M20 Task 22 — Per-cycle token telemetry per agent.
Relationship: Hermetic tests for the telemetry wrapper CLI.  Exercises the
  spawn + complete round-trip, atomic-write semantics, path convention, and
  error cases.  No live agent spawns; all I/O is inside tmp_path.

ACs verified here:
- AC-1: scripts/orchestration/telemetry.py exists with spawn + complete subcommands.
- AC-2: per-cycle JSON records land at runs/<task>/cycle_<N>/<agent>.usage.json
         with all captured fields.
- AC-5: tests/orchestrator/test_telemetry_record.py passes.
"""

from __future__ import annotations

import importlib.util
import json
import threading
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
    # tests/orchestrator/ → tests/ → repo_root
    return Path(__file__).parent.parent.parent


@pytest.fixture
def telemetry(repo_root):
    """Load the telemetry module."""
    return _load_telemetry_module(repo_root)


@pytest.fixture
def runs_dir(tmp_path) -> Path:
    """Return a temporary runs/ directory and cd into it for the test."""
    runs = tmp_path / "runs"
    runs.mkdir()
    return tmp_path  # return parent so paths under runs/ can be built


# ---------------------------------------------------------------------------
# Spawn subcommand tests
# ---------------------------------------------------------------------------

class TestSpawnSubcommand:
    """Tests for the ``spawn`` subcommand."""

    def test_spawn_creates_directory_and_record(self, telemetry, runs_dir, monkeypatch):
        """spawn creates the cycle directory and a valid JSON record."""
        monkeypatch.chdir(runs_dir)
        telemetry.main([
            "spawn",
            "--task", "m20_t22",
            "--cycle", "1",
            "--agent", "auditor",
            "--model", "claude-opus-4-7",
            "--effort", "high",
        ])

        record_path = runs_dir / "runs" / "m20_t22" / "cycle_1" / "auditor.usage.json"
        assert record_path.exists(), "Record file should be created by spawn"

        with record_path.open() as fh:
            rec = json.load(fh)

        assert rec["task"] == "m20_t22"
        assert rec["cycle"] == 1
        assert rec["agent"] == "auditor"
        assert rec["model"] == "claude-opus-4-7"
        assert rec["effort"] == "high"
        assert rec["spawn_ts"] is not None
        assert rec["complete_ts"] is None
        assert rec["wall_clock_seconds"] is None

    def test_spawn_null_fills_completion_fields(self, telemetry, runs_dir, monkeypatch):
        """spawn nulls out all completion fields."""
        monkeypatch.chdir(runs_dir)
        telemetry.main([
            "spawn",
            "--task", "m20_t22",
            "--cycle", "1",
            "--agent", "builder",
            "--model", "claude-sonnet-4-6",
            "--effort", "medium",
        ])
        record_path = runs_dir / "runs" / "m20_t22" / "cycle_1" / "builder.usage.json"
        with record_path.open() as fh:
            rec = json.load(fh)

        for field in (
            "input_tokens", "output_tokens",
            "cache_creation_input_tokens", "cache_read_input_tokens",
            "verdict", "fragment_path", "section",
        ):
            assert rec[field] is None, f"{field} should be null after spawn-only"

    def test_spawn_creates_nested_cycle_dirs(self, telemetry, runs_dir, monkeypatch):
        """spawn creates nested cycle directories that don't exist yet."""
        monkeypatch.chdir(runs_dir)
        telemetry.main([
            "spawn",
            "--task", "m99_t01",
            "--cycle", "3",
            "--agent", "sr-dev",
            "--model", "claude-opus-4-7",
            "--effort", "high",
        ])
        assert (runs_dir / "runs" / "m99_t01" / "cycle_3").is_dir()

    def test_spawn_path_convention_zero_padded(self, telemetry, runs_dir, monkeypatch):
        """Record path uses m<MM>_t<NN> zero-padded convention."""
        monkeypatch.chdir(runs_dir)
        telemetry.main([
            "spawn",
            "--task", "m05_t02",
            "--cycle", "1",
            "--agent", "auditor",
            "--model", "claude-opus-4-7",
            "--effort", "high",
        ])
        expected = runs_dir / "runs" / "m05_t02" / "cycle_1" / "auditor.usage.json"
        assert expected.exists()

    def test_spawn_missing_required_arg_exits_nonzero(self, telemetry, runs_dir, monkeypatch):
        """spawn exits non-zero when a required argument is missing."""
        monkeypatch.chdir(runs_dir)
        with pytest.raises(SystemExit) as exc_info:
            telemetry.main([
                "spawn",
                "--task", "m20_t22",
                # --cycle omitted
                "--agent", "auditor",
                "--model", "claude-opus-4-7",
                "--effort", "high",
            ])
        assert exc_info.value.code != 0

    def test_spawn_invalid_effort_exits_nonzero(self, telemetry, runs_dir, monkeypatch):
        """spawn exits non-zero when effort value is not in the allowed set."""
        monkeypatch.chdir(runs_dir)
        with pytest.raises(SystemExit) as exc_info:
            telemetry.main([
                "spawn",
                "--task", "m20_t22",
                "--cycle", "1",
                "--agent", "auditor",
                "--model", "claude-opus-4-7",
                "--effort", "turbo",  # invalid
            ])
        assert exc_info.value.code != 0


# ---------------------------------------------------------------------------
# Complete subcommand tests
# ---------------------------------------------------------------------------

class TestCompleteSubcommand:
    """Tests for the ``complete`` subcommand."""

    def _do_spawn(self, telemetry, runs_dir, task="m20_t22", cycle=1, agent="auditor"):
        telemetry.main([
            "spawn",
            "--task", task,
            "--cycle", str(cycle),
            "--agent", agent,
            "--model", "claude-opus-4-7",
            "--effort", "high",
        ])

    def test_complete_updates_record_with_all_fields(self, telemetry, runs_dir, monkeypatch):
        """complete merges completion metrics into the spawn record."""
        monkeypatch.chdir(runs_dir)
        self._do_spawn(telemetry, runs_dir)
        telemetry.main([
            "complete",
            "--task", "m20_t22",
            "--cycle", "1",
            "--agent", "auditor",
            "--input-tokens", "12450",
            "--output-tokens", "387",
            "--cache-creation", "8200",
            "--cache-read", "4250",
            "--verdict", "PASS",
            "--fragment-path", "runs/m20_t22/cycle_1/audit_issue.md",
            "--section", "—",
        ])
        record_path = runs_dir / "runs" / "m20_t22" / "cycle_1" / "auditor.usage.json"
        with record_path.open() as fh:
            rec = json.load(fh)

        assert rec["input_tokens"] == 12450
        assert rec["output_tokens"] == 387
        assert rec["cache_creation_input_tokens"] == 8200
        assert rec["cache_read_input_tokens"] == 4250
        assert rec["verdict"] == "PASS"
        assert rec["fragment_path"] == "runs/m20_t22/cycle_1/audit_issue.md"
        assert rec["section"] == "—"
        assert rec["complete_ts"] is not None
        # Wall-clock should be a non-negative integer
        assert isinstance(rec["wall_clock_seconds"], int)
        assert rec["wall_clock_seconds"] >= 0

    def test_complete_preserves_spawn_fields(self, telemetry, runs_dir, monkeypatch):
        """complete does not overwrite spawn_ts, model, or effort."""
        monkeypatch.chdir(runs_dir)
        self._do_spawn(telemetry, runs_dir)

        record_path = runs_dir / "runs" / "m20_t22" / "cycle_1" / "auditor.usage.json"
        with record_path.open() as fh:
            spawn_rec = json.load(fh)
        original_spawn_ts = spawn_rec["spawn_ts"]

        telemetry.main([
            "complete",
            "--task", "m20_t22",
            "--cycle", "1",
            "--agent", "auditor",
            "--input-tokens", "100",
            "--output-tokens", "50",
            "--verdict", "PASS",
        ])
        with record_path.open() as fh:
            rec = json.load(fh)

        assert rec["spawn_ts"] == original_spawn_ts
        assert rec["model"] == "claude-opus-4-7"
        assert rec["effort"] == "high"

    def test_complete_null_cache_fields_when_not_provided(self, telemetry, runs_dir, monkeypatch):
        """complete records null cache fields when --cache-creation/read are omitted."""
        monkeypatch.chdir(runs_dir)
        self._do_spawn(telemetry, runs_dir)
        telemetry.main([
            "complete",
            "--task", "m20_t22",
            "--cycle", "1",
            "--agent", "auditor",
            "--input-tokens", "100",
            "--output-tokens", "50",
            "--verdict", "PASS",
        ])
        record_path = runs_dir / "runs" / "m20_t22" / "cycle_1" / "auditor.usage.json"
        with record_path.open() as fh:
            rec = json.load(fh)

        assert rec["cache_creation_input_tokens"] is None
        assert rec["cache_read_input_tokens"] is None

    def test_complete_without_prior_spawn_creates_record(self, telemetry, runs_dir, monkeypatch):
        """complete creates a new record if no spawn record exists (warn on stderr)."""
        monkeypatch.chdir(runs_dir)
        # No spawn — complete directly
        telemetry.main([
            "complete",
            "--task", "m20_t99",
            "--cycle", "1",
            "--agent", "builder",
            "--input-tokens", "500",
            "--output-tokens", "200",
            "--verdict", "BUILT",
        ])
        record_path = runs_dir / "runs" / "m20_t99" / "cycle_1" / "builder.usage.json"
        assert record_path.exists()
        with record_path.open() as fh:
            rec = json.load(fh)
        assert rec["input_tokens"] == 500
        assert rec["spawn_ts"] is None  # No spawn happened

    def test_complete_missing_required_arg_exits_nonzero(self, telemetry, runs_dir, monkeypatch):
        """complete exits non-zero when input-tokens is missing."""
        monkeypatch.chdir(runs_dir)
        with pytest.raises(SystemExit) as exc_info:
            telemetry.main([
                "complete",
                "--task", "m20_t22",
                "--cycle", "1",
                "--agent", "auditor",
                # --input-tokens omitted
                "--output-tokens", "50",
                "--verdict", "PASS",
            ])
        assert exc_info.value.code != 0


# ---------------------------------------------------------------------------
# Atomic write tests
# ---------------------------------------------------------------------------

class TestAtomicWrite:
    """Tests for atomic-write semantics under simulated concurrency."""

    def test_concurrent_spawns_for_different_agents_create_distinct_records(
        self, telemetry, runs_dir, monkeypatch
    ):
        """Concurrent spawn invocations for different agents create distinct records.

        This test covers directory-creation safety under concurrent access: eight
        threads share the same cycle directory but write to separate agent files.
        ``mkdir(parents=True, exist_ok=True)`` is thread-safe, so no locking is
        needed at the directory level.  All eight per-agent records must exist and
        contain the correct agent name after all threads join.

        NOTE: This test does NOT exercise same-file write contention — that case is
        covered by ``test_concurrent_completes_for_same_triple_are_atomic``.
        """
        monkeypatch.chdir(runs_dir)
        errors: list[Exception] = []

        def do_spawn(agent: str) -> None:
            try:
                telemetry.main([
                    "spawn",
                    "--task", "m20_t22_concurrent",
                    "--cycle", "1",
                    "--agent", agent,
                    "--model", "claude-opus-4-7",
                    "--effort", "high",
                ])
            except Exception as exc:
                errors.append(exc)

        agents = [f"agent_{i}" for i in range(8)]
        threads = [threading.Thread(target=do_spawn, args=(a,)) for a in agents]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Concurrent spawns raised: {errors}"

        for agent in agents:
            record_path = (
                runs_dir / "runs" / "m20_t22_concurrent" / "cycle_1" / f"{agent}.usage.json"
            )
            assert record_path.exists(), f"Record for {agent} should exist"
            with record_path.open() as fh:
                rec = json.load(fh)
            assert rec["agent"] == agent

    def test_concurrent_completes_for_same_triple_are_atomic(
        self, telemetry, runs_dir, monkeypatch
    ):
        """Concurrent ``complete`` calls on the SAME (task, cycle, agent) triple are atomic.

        Eight threads each call ``complete`` on the same
        ``(task="m20_t22_atomic", cycle=1, agent="auditor")`` triple with distinct
        ``--input-tokens`` values (0, 100, 200, …, 700).  After all threads join:

        - Exactly one parseable JSON record exists at the expected path.
        - ``record["input_tokens"]`` is one of the expected per-thread values (last
          writer wins — no truncation, interleaving, or corruption).

        Discriminating-positive: if ``_write_record_atomic`` were replaced with a
        bare ``open(path, "w"); json.dump(record, fh)`` sequence, concurrent writes
        to the same path would intermittently produce a truncated or interleaved file,
        causing ``json.load()`` to raise ``JSONDecodeError`` or producing a record
        whose ``input_tokens`` is neither of the expected values.  The atomic
        ``NamedTemporaryFile + Path.replace()`` pattern (POSIX ``rename(2)``) prevents
        this: the destination is swapped atomically, so any reader sees either the
        old complete file or the new complete file, never a partial write.
        """
        monkeypatch.chdir(runs_dir)

        N = 8
        expected_input_tokens = [i * 100 for i in range(N)]

        # Spawn once so a base record exists (complete merges into it).
        telemetry.main([
            "spawn",
            "--task", "m20_t22_atomic",
            "--cycle", "1",
            "--agent", "auditor",
            "--model", "claude-opus-4-7",
            "--effort", "high",
        ])

        errors: list[Exception] = []

        def do_complete(input_tokens: int) -> None:
            try:
                telemetry.main([
                    "complete",
                    "--task", "m20_t22_atomic",
                    "--cycle", "1",
                    "--agent", "auditor",
                    "--input-tokens", str(input_tokens),
                    "--output-tokens", "50",
                    "--verdict", "PASS",
                ])
            except Exception as exc:
                errors.append(exc)

        threads = [
            threading.Thread(target=do_complete, args=(tok,))
            for tok in expected_input_tokens
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Concurrent completes raised: {errors}"

        record_path = (
            runs_dir / "runs" / "m20_t22_atomic" / "cycle_1" / "auditor.usage.json"
        )
        assert record_path.exists(), "Record file must exist after concurrent completes"

        # Must parse as valid JSON (no truncation / interleaving).
        with record_path.open() as fh:
            rec = json.load(fh)

        # Last writer wins — the value must be one of the expected per-thread values.
        assert rec["input_tokens"] in expected_input_tokens, (
            f"input_tokens={rec['input_tokens']!r} is not one of the expected "
            f"per-thread values {expected_input_tokens}; likely write-corruption."
        )

    def test_complete_is_idempotent_on_retry(self, telemetry, runs_dir, monkeypatch):
        """Calling complete twice writes the second call's values, no corruption."""
        monkeypatch.chdir(runs_dir)
        # spawn first
        telemetry.main([
            "spawn",
            "--task", "m20_t22_idem",
            "--cycle", "1",
            "--agent", "auditor",
            "--model", "claude-opus-4-7",
            "--effort", "high",
        ])
        # first complete
        telemetry.main([
            "complete",
            "--task", "m20_t22_idem",
            "--cycle", "1",
            "--agent", "auditor",
            "--input-tokens", "100",
            "--output-tokens", "50",
            "--verdict", "PASS",
        ])
        # second complete (retry with different values)
        telemetry.main([
            "complete",
            "--task", "m20_t22_idem",
            "--cycle", "1",
            "--agent", "auditor",
            "--input-tokens", "200",
            "--output-tokens", "75",
            "--verdict", "PASS",
        ])
        record_path = runs_dir / "runs" / "m20_t22_idem" / "cycle_1" / "auditor.usage.json"
        with record_path.open() as fh:
            rec = json.load(fh)
        assert rec["input_tokens"] == 200  # second call wins
        assert rec["output_tokens"] == 75


# ---------------------------------------------------------------------------
# Smoke test (from spec lines 134-155)
# ---------------------------------------------------------------------------

class TestSmokeFlow:
    """End-to-end spawn-then-complete flow matching the spec's smoke test."""

    def test_spec_smoke_test_round_trip(self, telemetry, runs_dir, monkeypatch):
        """Full spawn → complete round-trip per spec smoke test."""
        monkeypatch.chdir(runs_dir)

        telemetry.main([
            "spawn",
            "--task", "m20_t22_smoke",
            "--cycle", "1",
            "--agent", "auditor",
            "--model", "claude-opus-4-7",
            "--effort", "high",
        ])
        telemetry.main([
            "complete",
            "--task", "m20_t22_smoke",
            "--cycle", "1",
            "--agent", "auditor",
            "--input-tokens", "100",
            "--output-tokens", "50",
            "--cache-creation", "80",
            "--cache-read", "20",
            "--verdict", "PASS",
            "--fragment-path", "/tmp/x",
        ])

        record_path = runs_dir / "runs" / "m20_t22_smoke" / "cycle_1" / "auditor.usage.json"
        assert record_path.exists(), "record should land at the expected path"

        with record_path.open() as fh:
            d = json.load(fh)

        assert d["agent"] == "auditor"
        assert d["input_tokens"] == 100
        assert d["verdict"] == "PASS"
        # No quota_consumption_proxy — that is T06's analysis-layer scope
        assert "quota_consumption_proxy" not in d
