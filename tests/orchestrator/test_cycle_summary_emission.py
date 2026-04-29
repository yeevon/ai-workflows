"""Cycle-summary emission tests — 3-cycle simulation.

Task: M20 Task 03 — In-task cycle compaction (cycle_<N>/summary.md per Auditor).

This module verifies:
- After each cycle, the Auditor emits ``cycle_<N>/summary.md`` at the *nested*
  directory path ``runs/<task>/cycle_<N>/summary.md`` (NOT the flat form
  ``cycle_<N>_summary.md`` — nested form is authoritative per audit M11).
- Each summary file parses to the expected structure (all required keys present).
- Earlier summaries are unchanged after later cycles write their own.
- The ``Carry-over to next cycle:`` field is non-empty when the Auditor verdict is OPEN.

Per-AC coverage:
  AC-1 — Auditor Phase 5 extension: cycle-summary emitted per cycle (simulated here
          with ``make_cycle_summary``; Auditor agent text updated in auditor.md).
  AC-2 — Template structure validated: all required keys present in each summary.
  AC-3 — read-only-latest-summary rule described in auto-implement.md / clean-implement.md
          (prose change verified by smoke test grep; structural rule tested in
          ``test_cycle_context_constant.py``).
  AC-4 — ``runs/<task>/`` directory convention: nested ``cycle_<N>/summary.md`` form.
  AC-5 — ``test_cycle_summary_emission.py`` passes.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.orchestrator._helpers import (
    CYCLE_SUMMARY_REQUIRED_KEYS,
    make_cycle_summary,
    parse_cycle_summary,
)

# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

_TASK_SHORTHAND = "m12_t03"
_DATE = "2026-04-28"
_GATE_ROWS = [
    ("pytest", "uv run pytest", "PASS"),
    ("lint-imports", "uv run lint-imports", "PASS"),
    ("ruff", "uv run ruff check", "PASS"),
]


# ---------------------------------------------------------------------------
# Helper: stub Auditor that writes a cycle summary to tmp_path
# ---------------------------------------------------------------------------

def _stub_auditor_emit_summary(
    runs_dir: Path,
    cycle_number: int,
    auditor_verdict: str,
    files_changed: list[str],
    carry_over: list[str],
) -> Path:
    """Simulate the Auditor's Phase 5b: emit cycle_<N>/summary.md.

    Creates the per-cycle directory and writes the summary file, mirroring
    what the Auditor does in production after Phase 5a (issue-file write).

    The nested form ``cycle_<N>/summary.md`` is authoritative per audit M11.
    The flat form ``cycle_<N>_summary.md`` is NOT used and must NOT appear.

    Args:
        runs_dir: Base ``runs/<task-shorthand>/`` directory under tmp_path.
        cycle_number: 1-based cycle index.
        auditor_verdict: ``PASS`` | ``OPEN`` | ``BLOCKED``.
        files_changed: Files changed in this cycle.
        carry_over: ACs for next Builder cycle (must be non-empty if OPEN).

    Returns:
        The ``Path`` to the written ``cycle_<N>/summary.md`` file.
    """
    open_issues = "none" if auditor_verdict == "PASS" else "1 MEDIUM (simulated)"
    decisions: list[str] = []
    if auditor_verdict == "PASS" and cycle_number > 1:
        decisions = ["Locked: smoke test path approved (loop-controller + Auditor concur)"]

    summary_text = make_cycle_summary(
        cycle_number=cycle_number,
        date=_DATE,
        builder_verdict="BUILT",
        auditor_verdict=auditor_verdict,
        files_changed=files_changed,
        gates=_GATE_ROWS,
        open_issues=open_issues,
        decisions_locked=decisions,
        carry_over=carry_over,
        task_number=3,
    )

    cycle_dir = runs_dir / f"cycle_{cycle_number}"
    cycle_dir.mkdir(parents=True, exist_ok=True)

    summary_path = cycle_dir / "summary.md"
    summary_path.write_text(summary_text)
    return summary_path


# ---------------------------------------------------------------------------
# Test class: 3-cycle simulation
# ---------------------------------------------------------------------------

class TestCycleSummaryEmission:
    """3-cycle Builder→Auditor loop simulation; validates summary emission."""

    @pytest.fixture()
    def runs_dir(self, tmp_path: Path) -> Path:
        """Create ``runs/<task-shorthand>/`` under tmp_path."""
        d = tmp_path / "runs" / _TASK_SHORTHAND
        d.mkdir(parents=True)
        return d

    # ------------------------------------------------------------------
    # Cycle 1: auditor verdict OPEN
    # ------------------------------------------------------------------

    def test_cycle_1_summary_exists(self, runs_dir: Path) -> None:
        """After cycle 1 the Auditor emits cycle_1/summary.md (nested form)."""
        summary_path = _stub_auditor_emit_summary(
            runs_dir=runs_dir,
            cycle_number=1,
            auditor_verdict="OPEN",
            files_changed=[
                "ai_workflows/workflows/audit_cascade.py",
                "tests/workflows/test_audit_cascade.py",
                "CHANGELOG.md",
            ],
            carry_over=["AC-3: add wire-level MCP round-trip smoke test"],
        )

        # Nested form: cycle_1/summary.md
        assert summary_path == runs_dir / "cycle_1" / "summary.md"
        assert summary_path.exists()

        # Flat form must NOT exist
        flat = runs_dir / "cycle_1_summary.md"
        assert not flat.exists(), (
            "Flat form 'cycle_1_summary.md' must not exist — "
            "nested form 'cycle_1/summary.md' is authoritative per audit M11."
        )

    def test_cycle_1_summary_structure(self, runs_dir: Path) -> None:
        """cycle_1/summary.md contains all required keys."""
        summary_path = _stub_auditor_emit_summary(
            runs_dir=runs_dir,
            cycle_number=1,
            auditor_verdict="OPEN",
            files_changed=["ai_workflows/workflows/audit_cascade.py"],
            carry_over=["AC-3: add wire-level smoke test"],
        )

        text = summary_path.read_text()
        parsed = parse_cycle_summary(text)

        for required_key in CYCLE_SUMMARY_REQUIRED_KEYS:
            # Strip ** delimiters from the constant to get the bare key name
            key = required_key.strip("*").rstrip(":")
            assert key in parsed, (
                f"Required key {required_key!r} missing from cycle_1/summary.md. "
                f"Present keys: {list(parsed.keys())}"
            )

    def test_cycle_1_open_carry_over_populated(self, runs_dir: Path) -> None:
        """cycle_1/summary.md with OPEN verdict has non-empty Carry-over field."""
        carry_over_item = "AC-3: add wire-level MCP round-trip smoke test"
        summary_path = _stub_auditor_emit_summary(
            runs_dir=runs_dir,
            cycle_number=1,
            auditor_verdict="OPEN",
            files_changed=[],
            carry_over=[carry_over_item],
        )

        text = summary_path.read_text()
        assert "OPEN" in text
        assert carry_over_item in text, (
            "Carry-over field must be non-empty when Auditor verdict is OPEN — "
            "the next Builder cycle must know which ACs remain unmet."
        )

    # ------------------------------------------------------------------
    # Cycle 2: auditor verdict still OPEN
    # ------------------------------------------------------------------

    def test_cycle_2_summary_exists(self, runs_dir: Path) -> None:
        """After cycle 2 the Auditor emits cycle_2/summary.md (nested form)."""
        # Emit cycle 1 first (prerequisite for a realistic 3-cycle scenario)
        _stub_auditor_emit_summary(
            runs_dir=runs_dir,
            cycle_number=1,
            auditor_verdict="OPEN",
            files_changed=["ai_workflows/workflows/audit_cascade.py"],
            carry_over=["AC-3: add smoke test"],
        )

        summary_path = _stub_auditor_emit_summary(
            runs_dir=runs_dir,
            cycle_number=2,
            auditor_verdict="OPEN",
            files_changed=["tests/integration/test_audit_cascade_mcp_e2e.py"],
            carry_over=["AC-3: smoke test present but not wire-level yet"],
        )

        # Nested form: cycle_2/summary.md
        assert summary_path == runs_dir / "cycle_2" / "summary.md"
        assert summary_path.exists()

        # Flat form must NOT exist
        flat = runs_dir / "cycle_2_summary.md"
        assert not flat.exists(), (
            "Flat form 'cycle_2_summary.md' must not exist — "
            "nested form 'cycle_2/summary.md' is authoritative per audit M11."
        )

    def test_cycle_1_unchanged_after_cycle_2(self, runs_dir: Path) -> None:
        """cycle_1/summary.md is not modified when cycle_2/summary.md is written."""
        carry_over_1 = ["AC-3: add smoke test"]
        _stub_auditor_emit_summary(
            runs_dir=runs_dir,
            cycle_number=1,
            auditor_verdict="OPEN",
            files_changed=["ai_workflows/workflows/audit_cascade.py"],
            carry_over=carry_over_1,
        )
        cycle_1_path = runs_dir / "cycle_1" / "summary.md"
        original_text = cycle_1_path.read_text()
        original_mtime = cycle_1_path.stat().st_mtime

        _stub_auditor_emit_summary(
            runs_dir=runs_dir,
            cycle_number=2,
            auditor_verdict="OPEN",
            files_changed=["tests/integration/test_mcp_e2e.py"],
            carry_over=["AC-3: wire-level smoke test still missing"],
        )

        # cycle_1/summary.md must be byte-for-byte unchanged
        assert cycle_1_path.read_text() == original_text
        assert cycle_1_path.stat().st_mtime == original_mtime

    # ------------------------------------------------------------------
    # Cycle 3: auditor verdict PASS
    # ------------------------------------------------------------------

    def test_cycle_3_summary_exists(self, runs_dir: Path) -> None:
        """After cycle 3 the Auditor emits cycle_3/summary.md (nested form)."""
        for cycle in range(1, 3):
            _stub_auditor_emit_summary(
                runs_dir=runs_dir,
                cycle_number=cycle,
                auditor_verdict="OPEN",
                files_changed=[f"file_cycle_{cycle}.py"],
                carry_over=[f"AC-3 still open (cycle {cycle})"],
            )

        summary_path = _stub_auditor_emit_summary(
            runs_dir=runs_dir,
            cycle_number=3,
            auditor_verdict="PASS",
            files_changed=["tests/integration/test_audit_cascade_mcp_e2e.py"],
            carry_over=[],
        )

        # Nested form: cycle_3/summary.md
        assert summary_path == runs_dir / "cycle_3" / "summary.md"
        assert summary_path.exists()

        # Flat form must NOT exist
        flat = runs_dir / "cycle_3_summary.md"
        assert not flat.exists(), (
            "Flat form 'cycle_3_summary.md' must not exist — "
            "nested form 'cycle_3/summary.md' is authoritative per audit M11."
        )

    def test_cycle_3_pass_carry_over_empty(self, runs_dir: Path) -> None:
        """cycle_3/summary.md with PASS verdict has 'none' in Carry-over field."""
        summary_path = _stub_auditor_emit_summary(
            runs_dir=runs_dir,
            cycle_number=3,
            auditor_verdict="PASS",
            files_changed=["tests/integration/test_audit_cascade_mcp_e2e.py"],
            carry_over=[],
        )

        text = summary_path.read_text()
        assert "PASS" in text
        # When verdict is PASS, carry-over should be "none"
        parsed = parse_cycle_summary(text)
        assert parsed.get("Carry-over to next cycle", "").strip() == "none", (
            "Carry-over to next cycle must be 'none' when Auditor verdict is PASS — "
            "there are no open ACs for the next Builder cycle to address."
        )

    def test_all_three_cycles_coexist(self, runs_dir: Path) -> None:
        """All three cycle_N/summary.md files exist independently after the 3-cycle loop."""
        verdicts = ["OPEN", "OPEN", "PASS"]
        for i, verdict in enumerate(verdicts, start=1):
            carry_over = [f"AC-3 open (cycle {i})"] if verdict == "OPEN" else []
            _stub_auditor_emit_summary(
                runs_dir=runs_dir,
                cycle_number=i,
                auditor_verdict=verdict,
                files_changed=[f"changed_in_cycle_{i}.py"],
                carry_over=carry_over,
            )

        for cycle_n in range(1, 4):
            nested_path = runs_dir / f"cycle_{cycle_n}" / "summary.md"
            assert nested_path.exists(), (
                f"cycle_{cycle_n}/summary.md should exist after the 3-cycle loop."
            )
            # Flat form must never exist
            flat_path = runs_dir / f"cycle_{cycle_n}_summary.md"
            assert not flat_path.exists(), (
                f"Flat form cycle_{cycle_n}_summary.md must not be created — "
                "nested form is authoritative per audit M11."
            )

    # ------------------------------------------------------------------
    # Structural validation
    # ------------------------------------------------------------------

    def test_summary_header_format(self, runs_dir: Path) -> None:
        """Summary file begins with '# Cycle N summary — Task NN' header."""
        summary_path = _stub_auditor_emit_summary(
            runs_dir=runs_dir,
            cycle_number=2,
            auditor_verdict="OPEN",
            files_changed=["some_file.py"],
            carry_over=["AC-X still open"],
        )
        text = summary_path.read_text()
        assert text.startswith("# Cycle 2 summary — Task 03"), (
            f"Summary must start with '# Cycle N summary — Task NN'. "
            f"Actual start: {text[:60]!r}"
        )

    def test_gate_table_present(self, runs_dir: Path) -> None:
        """Summary file contains the gate table with pytest, lint-imports, ruff rows."""
        summary_path = _stub_auditor_emit_summary(
            runs_dir=runs_dir,
            cycle_number=1,
            auditor_verdict="PASS",
            files_changed=[],
            carry_over=[],
        )
        text = summary_path.read_text()
        assert "pytest" in text
        assert "lint-imports" in text
        assert "ruff" in text
        assert "| Gate | Command | Result |" in text

    def test_builder_verdict_recorded(self, runs_dir: Path) -> None:
        """Summary file records the Builder verdict (BUILT / BLOCKED / STOP-AND-ASK)."""
        summary_path = _stub_auditor_emit_summary(
            runs_dir=runs_dir,
            cycle_number=1,
            auditor_verdict="PASS",
            files_changed=[],
            carry_over=[],
        )
        text = summary_path.read_text()
        assert "BUILT" in text, "Builder verdict 'BUILT' must appear in the summary."
