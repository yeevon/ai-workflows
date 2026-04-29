"""Tests for M21 Task 15 — /ship manual happy-path publish Skill (host-only).

Verifies:
- AC1: SKILL.md exists; frontmatter has name/description/allowed-tools; body <= 5K tokens;
  four required ## anchors (Inputs, Procedure, Outputs, Return schema).
- AC2: runbook.md exists and is T24-rubric conformant.
- AC3 (host-only safety anchor): SKILL.md body contains "host-only" + "autonomy-mode"
  references. The autonomy-mode boundary MUST be explicit.
- AC4: T25 skills_efficiency gate is clean across .claude/skills/.
- AC8: _common/skills_pattern.md Live Skills line lists ship.
- AC9: CHANGELOG.md updated with M21 Task 15 entry under [Unreleased].

Relationship to other modules: standalone test; exercises
scripts/audit/md_discoverability.py and scripts/audit/skills_efficiency.py via
subprocess (mirrors test_t13_triage.py and test_t16_sweep.py patterns).
No imports from ai_workflows.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = REPO_ROOT / ".claude" / "skills" / "ship"
SKILL_MD = SKILL_DIR / "SKILL.md"
RUNBOOK_MD = SKILL_DIR / "runbook.md"
SKILLS_PATTERN_MD = REPO_ROOT / ".claude" / "agents" / "_common" / "skills_pattern.md"
AUDIT_DISCOVERABILITY = REPO_ROOT / "scripts" / "audit" / "md_discoverability.py"
AUDIT_SKILLS_EFF = REPO_ROOT / "scripts" / "audit" / "skills_efficiency.py"
CHANGELOG = REPO_ROOT / "CHANGELOG.md"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_skill_md() -> str:
    """Read ship SKILL.md as UTF-8."""
    return SKILL_MD.read_text(encoding="utf-8")


def _parse_frontmatter(body: str) -> dict:
    """Extract the YAML frontmatter block from body.

    Raises AssertionError when the frontmatter opener / closer is missing
    or malformed.
    """
    assert body.startswith("---\n"), "SKILL.md must open with YAML frontmatter marker"
    _, _, rest = body.partition("---\n")
    fm_block, marker, _ = rest.partition("\n---\n")
    assert marker == "\n---\n", "SKILL.md frontmatter must close with a trailing ---"
    data = yaml.safe_load(fm_block) or {}
    assert isinstance(data, dict), "frontmatter must parse to a mapping"
    return data


def _run_discoverability(
    check: str,
    extra_args: list[str] | None = None,
) -> subprocess.CompletedProcess:
    """Invoke md_discoverability.py with the given check against the ship Skill dir."""
    cmd = [
        sys.executable,
        str(AUDIT_DISCOVERABILITY),
        "--check",
        check,
        "--target",
        str(SKILL_DIR),
    ]
    if extra_args:
        cmd.extend(extra_args)
    return subprocess.run(cmd, capture_output=True, text=True)


# ---------------------------------------------------------------------------
# AC1 — SKILL.md existence and frontmatter
# ---------------------------------------------------------------------------


def test_skill_md_exists() -> None:
    """AC1: .claude/skills/ship/SKILL.md exists and is non-empty."""
    assert SKILL_MD.is_file(), f"expected {SKILL_MD} to exist"
    body = _read_skill_md()
    assert body.strip(), "SKILL.md must not be empty"


def test_skill_md_frontmatter_name() -> None:
    """AC1: frontmatter name == 'ship'."""
    body = _read_skill_md()
    fm = _parse_frontmatter(body)
    assert fm.get("name") == "ship", (
        f"skill name must be 'ship', got {fm.get('name')!r}"
    )


def test_skill_md_frontmatter_description_present() -> None:
    """AC1: frontmatter description is a non-empty string."""
    body = _read_skill_md()
    fm = _parse_frontmatter(body)
    desc = fm.get("description")
    assert isinstance(desc, str) and desc.strip(), (
        "frontmatter must carry a non-empty description string"
    )


def test_skill_md_frontmatter_description_length() -> None:
    """AC1: frontmatter description is <= 200 characters."""
    body = _read_skill_md()
    fm = _parse_frontmatter(body)
    desc = fm.get("description", "")
    assert len(desc) <= 200, (
        f"description is {len(desc)} chars — must be <= 200; got: {desc!r}"
    )


def test_skill_md_frontmatter_allowed_tools() -> None:
    """AC1: frontmatter allowed-tools is present and non-empty."""
    body = _read_skill_md()
    fm = _parse_frontmatter(body)
    allowed = fm.get("allowed-tools")
    assert allowed, (
        "frontmatter must carry a non-empty 'allowed-tools' entry"
    )


def test_skill_md_body_token_budget() -> None:
    """AC1: SKILL.md body word-count * 1.3 <= 5000."""
    body = _read_skill_md()
    word_count = len(body.split())
    token_estimate = word_count * 1.3
    assert token_estimate <= 5000, (
        f"SKILL.md estimated tokens ({token_estimate:.0f}) exceeds 5000; "
        f"word count = {word_count}"
    )


# ---------------------------------------------------------------------------
# AC1 — Required four ## anchors
# ---------------------------------------------------------------------------


def test_skill_md_anchor_inputs() -> None:
    """AC1: SKILL.md has '## Inputs' anchor."""
    body = _read_skill_md()
    assert "## Inputs" in body, "SKILL.md must have '## Inputs' section"


def test_skill_md_anchor_procedure() -> None:
    """AC1: SKILL.md has '## Procedure' anchor."""
    body = _read_skill_md()
    assert "## Procedure" in body, "SKILL.md must have '## Procedure' section"


def test_skill_md_anchor_outputs() -> None:
    """AC1: SKILL.md has '## Outputs' anchor."""
    body = _read_skill_md()
    assert "## Outputs" in body, "SKILL.md must have '## Outputs' section"


def test_skill_md_anchor_return_schema() -> None:
    """AC1: SKILL.md has '## Return schema' anchor."""
    body = _read_skill_md()
    assert "## Return schema" in body, "SKILL.md must have '## Return schema' section"


# ---------------------------------------------------------------------------
# AC1 — runbook.md referenced from SKILL.md body
# ---------------------------------------------------------------------------


def test_skill_md_references_runbook() -> None:
    """AC1: SKILL.md body references 'runbook.md'."""
    body = _read_skill_md()
    assert "runbook.md" in body, (
        "SKILL.md must reference the helper file 'runbook.md'"
    )


# ---------------------------------------------------------------------------
# AC2 — runbook.md existence and T24 rubric
# ---------------------------------------------------------------------------


def test_runbook_md_exists() -> None:
    """AC2: .claude/skills/ship/runbook.md exists and is non-empty."""
    assert RUNBOOK_MD.is_file(), f"expected {RUNBOOK_MD} to exist"
    content = RUNBOOK_MD.read_text(encoding="utf-8")
    assert content.strip(), "runbook.md must not be empty"


def test_runbook_md_t24_summary() -> None:
    """AC2: runbook.md passes T24 rubric --check summary."""
    result = _run_discoverability("summary")
    assert result.returncode == 0, (
        f"T24 summary check failed on ship/:\n{result.stdout}\n{result.stderr}"
    )


def test_runbook_md_t24_section_budget() -> None:
    """AC2: runbook.md passes T24 rubric --check section-budget."""
    result = _run_discoverability("section-budget")
    assert result.returncode == 0, (
        f"T24 section-budget check failed on ship/:\n{result.stdout}\n{result.stderr}"
    )


def test_runbook_md_t24_code_block_len() -> None:
    """AC2: runbook.md passes T24 rubric --check code-block-len (max 20 lines)."""
    result = _run_discoverability("code-block-len", ["--max", "20"])
    assert result.returncode == 0, (
        f"T24 code-block-len check failed on ship/:\n{result.stdout}\n{result.stderr}"
    )


# ---------------------------------------------------------------------------
# AC3 — T15-specific host-only / autonomy-mode safety anchors
# ---------------------------------------------------------------------------


def test_skill_md_host_only_anchor() -> None:
    """AC3 (T15-specific): SKILL.md body contains 'host-only' (case-insensitive).

    The autonomy-mode boundary MUST be explicit; a Skill that publishes without
    this anchor is unacceptable per T15 spec AC3.
    """
    body = _read_skill_md()
    assert "host-only" in body.lower(), (
        "SKILL.md must contain 'host-only' to mark the autonomy-mode boundary"
    )


def test_skill_md_autonomy_mode_anchor() -> None:
    """AC3 (T15-specific): SKILL.md body contains 'autonomy-mode' (case-insensitive)."""
    body = _read_skill_md()
    assert "autonomy-mode" in body.lower(), (
        "SKILL.md must contain 'autonomy-mode' reference to forbid orchestrator invocation"
    )


# ---------------------------------------------------------------------------
# AC4 — T25 skills_efficiency clean
# ---------------------------------------------------------------------------


def test_t25_skills_efficiency_clean() -> None:
    """AC4: skills_efficiency --check all is clean across .claude/skills/ (includes ship)."""
    skills_dir = REPO_ROOT / ".claude" / "skills"
    cmd = [
        sys.executable,
        str(AUDIT_SKILLS_EFF),
        "--check",
        "all",
        "--target",
        str(skills_dir),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode == 0, (
        f"skills_efficiency --check all failed after ship/ added:\n"
        f"{result.stdout}\n{result.stderr}"
    )


# ---------------------------------------------------------------------------
# AC8 — _common/skills_pattern.md live-Skills line
# ---------------------------------------------------------------------------


def test_skills_pattern_md_live_skills_count_line() -> None:
    """AC8: _common/skills_pattern.md has a 'Live Skills:' count line."""
    assert SKILLS_PATTERN_MD.is_file(), (
        f"expected {SKILLS_PATTERN_MD} to exist"
    )
    content = SKILLS_PATTERN_MD.read_text(encoding="utf-8")
    assert "Live Skills:" in content, (
        "_common/skills_pattern.md must contain a 'Live Skills:' count line"
    )


def test_skills_pattern_md_ship_in_count_line() -> None:
    """AC8: the Live Skills count line mentions 'ship'."""
    content = SKILLS_PATTERN_MD.read_text(encoding="utf-8")
    live_line = next(
        (line for line in content.splitlines() if "Live Skills:" in line), None
    )
    assert live_line is not None, "No 'Live Skills:' line found"
    assert "ship" in live_line, (
        f"'Live Skills:' line must mention 'ship'; got: {live_line!r}"
    )


# ---------------------------------------------------------------------------
# AC9 — CHANGELOG entry
# ---------------------------------------------------------------------------


def test_changelog_t15_entry() -> None:
    """AC9: CHANGELOG.md has a M21 Task 15 entry under [Unreleased]."""
    content = CHANGELOG.read_text(encoding="utf-8")
    unreleased_idx = content.find("[Unreleased]")
    first_version_idx = content.find("\n## [0.", unreleased_idx + 1)
    assert unreleased_idx != -1 and "M21 Task 15" in content[unreleased_idx:first_version_idx], (
        "CHANGELOG.md must contain a 'M21 Task 15' entry under [Unreleased]"
    )
