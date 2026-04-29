"""Tests for M21 Task 24 — MD-file discoverability audit.

Verifies:
- AC1: All 11 audited MD files satisfy rules 1-4 (smoke steps 1-4 exit zero).
- AC3: T10 invariant held (9/9 agents reference _common/non_negotiables.md).
- AC4: T11 invariant held (4/4 drift-check agents carry the KDR table).
- AC5: scripts/audit/md_discoverability.py exists, runnable, ≤ 200 lines, supports 4 checks.
- AC6: issues/task_24_issue.md exists with Per-file rubric baseline table.
- AC7: CHANGELOG.md updated with M21 Task 24 entry under [Unreleased].

Relationship to other modules: standalone test; exercises scripts/audit/md_discoverability.py
against the live .claude/agents/ directory.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
AGENTS_DIR = REPO_ROOT / ".claude" / "agents"
AUDIT_SCRIPT = REPO_ROOT / "scripts" / "audit" / "md_discoverability.py"
ISSUE_FILE = (
    REPO_ROOT
    / "design_docs"
    / "phases"
    / "milestone_21_autonomy_loop_continuation"
    / "issues"
    / "task_24_issue.md"
)
CHANGELOG = REPO_ROOT / "CHANGELOG.md"


# ---------------------------------------------------------------------------
# AC5: Script existence, line count, and importability
# ---------------------------------------------------------------------------


def test_audit_script_exists() -> None:
    """AC5: scripts/audit/md_discoverability.py exists."""
    assert AUDIT_SCRIPT.exists(), f"Audit script missing: {AUDIT_SCRIPT}"


def test_audit_script_line_count() -> None:
    """AC5: audit script is ≤ 200 lines."""
    lines = AUDIT_SCRIPT.read_text().splitlines()
    assert len(lines) <= 200, f"Audit script is {len(lines)} lines (limit 200)"


def test_audit_script_importable() -> None:
    """AC5: audit script is importable as a Python module."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("md_discoverability", AUDIT_SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    assert hasattr(module, "main"), "main() function must be present"


# ---------------------------------------------------------------------------
# AC1: All 11 files pass rules 1-4 (smoke steps 1-4)
# ---------------------------------------------------------------------------


def _run_check(check_name: str, extra_args: list[str] | None = None) -> subprocess.CompletedProcess:
    """Run the audit script with the given check name."""
    cmd = [
        sys.executable,
        str(AUDIT_SCRIPT),
        "--check",
        check_name,
        "--target",
        str(AGENTS_DIR),
    ]
    if extra_args:
        cmd.extend(extra_args)
    return subprocess.run(cmd, capture_output=True, text=True)


def test_rule1_summary_check_passes() -> None:
    """AC1 / smoke step 1: all 11 files have a 3-line summary before first ## heading."""
    result = _run_check("summary")
    assert result.returncode == 0, (
        f"Rule 1 (summary) violations:\n{result.stdout}{result.stderr}"
    )


def test_rule2_section_count_passes() -> None:
    """AC1 / smoke step 4: all 11 files have >= 2 ## headings."""
    result = _run_check("section-count", ["--min", "2"])
    assert result.returncode == 0, (
        f"Rule 2 (section-count) violations:\n{result.stdout}{result.stderr}"
    )


def test_rule3_section_budget_passes() -> None:
    """AC1 / smoke step 2: no ## section exceeds 384 words (500 tokens)."""
    result = _run_check("section-budget")
    assert result.returncode == 0, (
        f"Rule 3 (section-budget) violations:\n{result.stdout}{result.stderr}"
    )


def test_rule4_code_block_len_passes() -> None:
    """AC1 / smoke step 3: no inline code block exceeds 20 lines."""
    result = _run_check("code-block-len", ["--max", "20"])
    assert result.returncode == 0, (
        f"Rule 4 (code-block-len) violations:\n{result.stdout}{result.stderr}"
    )


# ---------------------------------------------------------------------------
# AC3: T10 invariant — all 9 agents reference _common/non_negotiables.md
# ---------------------------------------------------------------------------

_NINE_AGENT_FILES = [
    "architect.md",
    "auditor.md",
    "builder.md",
    "dependency-auditor.md",
    "roadmap-selector.md",
    "security-reviewer.md",
    "sr-dev.md",
    "sr-sdet.md",
    "task-analyzer.md",
]


def test_t10_invariant_all_9_agents_reference_non_negotiables() -> None:
    """AC3: T10 invariant — all 9 agent prompts reference _common/non_negotiables.md."""
    missing = []
    for fname in _NINE_AGENT_FILES:
        fpath = AGENTS_DIR / fname
        content = fpath.read_text()
        if "_common/non_negotiables.md" not in content:
            missing.append(fname)
    assert not missing, (
        f"T10 invariant broken — {len(missing)} agent(s) missing reference: {missing}"
    )


# ---------------------------------------------------------------------------
# AC4: T11 invariant — 4 drift-check agents carry the KDR table
# ---------------------------------------------------------------------------

_FOUR_DRIFT_CHECK_AGENTS = [
    "auditor.md",
    "task-analyzer.md",
    "architect.md",
    "dependency-auditor.md",
]


def test_t11_invariant_4_drift_check_agents_carry_kdr_table() -> None:
    """AC4: T11 invariant — 4 agents carry '## Load-bearing KDRs' section."""
    missing = []
    for fname in _FOUR_DRIFT_CHECK_AGENTS:
        fpath = AGENTS_DIR / fname
        content = fpath.read_text()
        if "## Load-bearing KDRs" not in content:
            missing.append(fname)
    assert not missing, (
        f"T11 invariant broken — {len(missing)} agent(s) missing KDR table: {missing}"
    )


# ---------------------------------------------------------------------------
# AC6: Issue file exists with Per-file rubric baseline table
# ---------------------------------------------------------------------------


def test_issue_file_exists() -> None:
    """AC6: issues/task_24_issue.md exists."""
    assert ISSUE_FILE.exists(), f"Issue file missing: {ISSUE_FILE}"


def test_issue_file_has_baseline_table() -> None:
    """AC6: issue file contains 'Per-file rubric baseline' section."""
    content = ISSUE_FILE.read_text()
    assert "Per-file rubric baseline" in content, (
        "Issue file missing '## Per-file rubric baseline' section"
    )


# ---------------------------------------------------------------------------
# AC7: CHANGELOG entry exists
# ---------------------------------------------------------------------------


def test_changelog_has_t24_entry() -> None:
    """AC7: CHANGELOG.md has a M21 Task 24 entry under [Unreleased]."""
    content = CHANGELOG.read_text()
    # Tightened per TA-LOW-01: match section anchor pattern
    import re
    pattern = re.compile(r"^### (Added|Changed) — M21 Task 24:", re.MULTILINE)
    assert pattern.search(content), (
        "CHANGELOG missing '### (Added|Changed) — M21 Task 24:' entry under [Unreleased]"
    )
