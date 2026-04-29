"""Tests for M21 Task 16 — /sweep ad-hoc reviewer Skill.

Verifies:
- AC1: SKILL.md exists; frontmatter has name/description/allowed-tools; body <= 5K tokens;
  four required ## anchors (Inputs, Procedure, Outputs, Return schema).
- AC2: runbook.md exists and is T24-rubric conformant.
- AC3: T25 skills_efficiency gate is clean against the new Skill.
- AC4: T10 invariant (9/9 agents reference _common/non_negotiables.md) preserved.
- AC5: T24 invariant held on .claude/agents/.
- AC6: This test file (self-referential — six cases per spec).
- AC7: _common/skills_pattern.md has 'sweep' in Live Skills line.
- AC8: CHANGELOG.md updated with M21 Task 16 entry under [Unreleased].

Relationship to other modules: standalone test; exercises
scripts/audit/md_discoverability.py and scripts/audit/skills_efficiency.py via
subprocess (mirrors test_t13_triage.py and test_t14_check.py pattern). No imports
from ai_workflows.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = REPO_ROOT / ".claude" / "skills" / "sweep"
SKILL_MD = SKILL_DIR / "SKILL.md"
RUNBOOK_MD = SKILL_DIR / "runbook.md"
SKILLS_PATTERN_MD = REPO_ROOT / ".claude" / "agents" / "_common" / "skills_pattern.md"
AGENTS_DIR = REPO_ROOT / ".claude" / "agents"
AUDIT_DISCOVERABILITY = REPO_ROOT / "scripts" / "audit" / "md_discoverability.py"
AUDIT_SKILLS_EFF = REPO_ROOT / "scripts" / "audit" / "skills_efficiency.py"
CHANGELOG = REPO_ROOT / "CHANGELOG.md"

_REQUIRED_AGENTS = [
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_skill_md() -> str:
    """Read sweep SKILL.md as UTF-8."""
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
    target: Path | None = None,
) -> subprocess.CompletedProcess:
    """Invoke md_discoverability.py with the given check against a target directory."""
    tgt = target if target is not None else SKILL_DIR
    cmd = [
        sys.executable,
        str(AUDIT_DISCOVERABILITY),
        "--check",
        check,
        "--target",
        str(tgt),
    ]
    if extra_args:
        cmd.extend(extra_args)
    return subprocess.run(cmd, capture_output=True, text=True)


# ---------------------------------------------------------------------------
# Case 1 — SKILL.md frontmatter parses (YAML-loadable; name, description, allowed-tools)
# ---------------------------------------------------------------------------


def test_skill_md_exists() -> None:
    """AC1: .claude/skills/sweep/SKILL.md exists and is non-empty."""
    assert SKILL_MD.is_file(), f"expected {SKILL_MD} to exist"
    body = _read_skill_md()
    assert body.strip(), "SKILL.md must not be empty"


def test_skill_md_frontmatter_fields() -> None:
    """AC1: frontmatter YAML-loadable; name=='sweep'; desc<=200 chars; allowed-tools present."""
    body = _read_skill_md()
    fm = _parse_frontmatter(body)
    assert fm.get("name") == "sweep", (
        f"skill name must be 'sweep', got {fm.get('name')!r}"
    )
    desc = fm.get("description", "")
    assert isinstance(desc, str) and desc.strip(), (
        "frontmatter must carry a non-empty description string"
    )
    assert len(desc) <= 200, (
        f"description is {len(desc)} chars — must be <= 200; got: {desc!r}"
    )
    allowed = fm.get("allowed-tools")
    assert allowed, "frontmatter must carry a non-empty 'allowed-tools' entry"


# ---------------------------------------------------------------------------
# Case 2 — SKILL.md body token budget and four required ## anchors
# ---------------------------------------------------------------------------


def test_skill_md_body_token_budget_and_anchors() -> None:
    """AC1: body word-count * 1.3 <= 5000; four ## anchors present; runbook.md referenced."""
    body = _read_skill_md()
    word_count = len(body.split())
    token_estimate = word_count * 1.3
    assert token_estimate <= 5000, (
        f"SKILL.md estimated tokens ({token_estimate:.0f}) exceeds 5000; "
        f"word count = {word_count}"
    )
    for anchor in ("## Inputs", "## Procedure", "## Outputs", "## Return schema"):
        assert anchor in body, f"SKILL.md must have '{anchor}' section"
    assert "runbook.md" in body, "SKILL.md must reference the helper file 'runbook.md'"


# ---------------------------------------------------------------------------
# Case 3 — runbook.md existence and T24 rubric
# ---------------------------------------------------------------------------


def test_runbook_md_t24_rubric() -> None:
    """AC2: runbook.md exists; passes T24 rubric summary / section-budget / code-block-len."""
    assert RUNBOOK_MD.is_file(), f"expected {RUNBOOK_MD} to exist"
    content = RUNBOOK_MD.read_text(encoding="utf-8")
    assert content.strip(), "runbook.md must not be empty"

    for check, extra in [
        ("summary", None),
        ("section-budget", None),
        ("code-block-len", ["--max", "20"]),
    ]:
        result = _run_discoverability(check, extra)
        assert result.returncode == 0, (
            f"T24 {check} check failed on sweep/:\n{result.stdout}\n{result.stderr}"
        )


# ---------------------------------------------------------------------------
# Case 4 — T25 skills_efficiency clean
# ---------------------------------------------------------------------------


def test_t25_skills_efficiency_clean() -> None:
    """AC3: skills_efficiency --check all is clean across .claude/skills/ (includes sweep)."""
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
        f"skills_efficiency --check all failed after sweep/ added:\n"
        f"{result.stdout}\n{result.stderr}"
    )


# ---------------------------------------------------------------------------
# Case 5 — T10 invariant (9/9 agents reference _common/non_negotiables.md)
# ---------------------------------------------------------------------------


def test_t10_invariant_nine_of_nine() -> None:
    """AC4: all 9 agents reference _common/non_negotiables.md (T10 invariant)."""
    needle = "_common/non_negotiables.md"
    missing = []
    for agent_name in _REQUIRED_AGENTS:
        agent_path = AGENTS_DIR / agent_name
        assert agent_path.is_file(), f"agent file missing: {agent_path}"
        content = agent_path.read_text(encoding="utf-8")
        if needle not in content:
            missing.append(agent_name)
    assert not missing, (
        f"T10 invariant violated: these agents do not reference {needle!r}: {missing}"
    )


# ---------------------------------------------------------------------------
# Case 6 — _common/skills_pattern.md and CHANGELOG
# ---------------------------------------------------------------------------


def test_skills_pattern_and_changelog() -> None:
    """AC7+AC8: Live Skills line lists 'sweep'; CHANGELOG has M21 Task 16 entry."""
    assert SKILLS_PATTERN_MD.is_file(), f"expected {SKILLS_PATTERN_MD} to exist"
    content = SKILLS_PATTERN_MD.read_text(encoding="utf-8")
    live_line = next(
        (line for line in content.splitlines() if "Live Skills:" in line), None
    )
    assert live_line is not None, "No 'Live Skills:' line found in skills_pattern.md"
    assert "sweep" in live_line, (
        f"'Live Skills:' line must mention 'sweep'; got: {live_line!r}"
    )

    changelog_content = CHANGELOG.read_text(encoding="utf-8")
    assert "M21 Task 16" in changelog_content, (
        "CHANGELOG.md must contain a 'M21 Task 16' entry under [Unreleased]"
    )
