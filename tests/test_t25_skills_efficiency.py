"""Tests for M21 Task 25 — Skills efficiency audit.

Verifies:
- AC1: scripts/audit/skills_efficiency.py exists, supports two CI-gated --check flags
  (screenshot-overuse, missing-tool-decl) + all-aggregate, exits non-zero on findings,
  exits zero when clean, <= 200 lines.
- AC2: .claude/commands/audit-skills.md exists and carries the four required ## section
  anchors (Inputs, Procedure, Outputs, Return schema).
- AC2b: Both existing Skills carry 'allowed-tools:' frontmatter.
- AC3: CI workflow wires both audit scripts.
- AC4: This test file (AC4 self-referential).
- AC7: CHANGELOG.md updated under [Unreleased] with ### Added — M21 Task 25 entry.

Synthetic fixtures exercise rule-fires-on-violation for both CI-gated rules.
Live-repo smoke verifies both existing Skills are heuristic-clean.

Relationship to other modules: standalone test; exercises
scripts/audit/skills_efficiency.py via subprocess (mirrors test_t24_md_discoverability.py
pattern). No imports from ai_workflows.
"""

from __future__ import annotations

import re
import subprocess
import sys
import textwrap
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO_ROOT / ".claude" / "skills"
AUDIT_SCRIPT = REPO_ROOT / "scripts" / "audit" / "skills_efficiency.py"
COMMANDS_DIR = REPO_ROOT / ".claude" / "commands"
AUDIT_SKILLS_CMD = COMMANDS_DIR / "audit-skills.md"
CI_YML = REPO_ROOT / ".github" / "workflows" / "ci.yml"
CHANGELOG = REPO_ROOT / "CHANGELOG.md"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_check(
    check_name: str,
    target: Path,
    extra_args: list[str] | None = None,
) -> subprocess.CompletedProcess:
    """Run the audit script with the given check name against target."""
    cmd = [
        sys.executable,
        str(AUDIT_SCRIPT),
        "--check",
        check_name,
        "--target",
        str(target),
    ]
    if extra_args:
        cmd.extend(extra_args)
    return subprocess.run(cmd, capture_output=True, text=True)


# ---------------------------------------------------------------------------
# AC1: Script existence and basic properties
# ---------------------------------------------------------------------------


def test_audit_script_exists() -> None:
    """AC1: scripts/audit/skills_efficiency.py exists."""
    assert AUDIT_SCRIPT.exists(), f"Audit script missing: {AUDIT_SCRIPT}"


def test_audit_script_line_count() -> None:
    """AC1 (smoke step 8): audit script is <= 200 lines."""
    lines = AUDIT_SCRIPT.read_text().splitlines()
    assert len(lines) <= 200, f"Audit script is {len(lines)} lines (limit 200)"


def test_audit_script_importable() -> None:
    """AC1: audit script is importable as a Python module."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("skills_efficiency", AUDIT_SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    assert callable(getattr(module, "main", None)), "main() must be a callable"


# ---------------------------------------------------------------------------
# AC1: Invalid-target error handling
# ---------------------------------------------------------------------------


def test_invalid_target_exits_2(tmp_path: Path) -> None:
    """AC1: --target pointing to a non-existent dir exits 2."""
    result = _run_check("all", tmp_path / "does_not_exist")
    assert result.returncode == 2, (
        f"Expected exit 2 for invalid target; got {result.returncode}\n{result.stderr}"
    )


# ---------------------------------------------------------------------------
# AC1: Live .claude/skills/ smoke — both checks pass on heuristic-clean Skills
# ---------------------------------------------------------------------------


def test_screenshot_overuse_passes_on_live_skills() -> None:
    """AC1 / smoke step 2: screenshot-overuse exits 0 against live .claude/skills/."""
    result = _run_check("screenshot-overuse", SKILLS_DIR)
    assert result.returncode == 0, (
        f"screenshot-overuse violations on live skills:\n{result.stdout}{result.stderr}"
    )


def test_missing_tool_decl_passes_on_live_skills() -> None:
    """AC1 / smoke step 2: missing-tool-decl exits 0 against live .claude/skills/."""
    result = _run_check("missing-tool-decl", SKILLS_DIR)
    assert result.returncode == 0, (
        f"missing-tool-decl violations on live skills:\n{result.stdout}{result.stderr}"
    )


def test_all_passes_on_live_skills() -> None:
    """AC1 / smoke step 2: --check all exits 0 against live .claude/skills/."""
    result = _run_check("all", SKILLS_DIR)
    assert result.returncode == 0, (
        f"--check all violations on live skills:\n{result.stdout}{result.stderr}"
    )


# ---------------------------------------------------------------------------
# AC1: Synthetic-fixture — rule fires on violation (screenshot-overuse)
# ---------------------------------------------------------------------------


def test_screenshot_overuse_fires_on_violation(tmp_path: Path) -> None:
    """AC1: screenshot-overuse exits 1 when a Skill mentions screenshot without text-extraction."""
    skill_dir = tmp_path / "bad-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        textwrap.dedent(
            """\
            ---
            name: bad-skill
            description: A skill that triggers the screenshot-overuse rule.
            allowed-tools: Bash
            ---
            # bad-skill
            ## Procedure
            Take a screenshot of the page to capture the layout.
            """
        )
    )
    result = _run_check("screenshot-overuse", tmp_path)
    assert result.returncode == 1, (
        f"Expected exit 1 for screenshot-overuse violation; got {result.returncode}\n"
        f"{result.stdout}{result.stderr}"
    )
    assert "Rule 1 FAIL" in result.stdout, f"Expected 'Rule 1 FAIL' in output:\n{result.stdout}"


def test_screenshot_overuse_ok_when_adjacent_text_extraction(tmp_path: Path) -> None:
    """AC1: screenshot-overuse exits 0 when adjacent text-extraction reference is present."""
    skill_dir = tmp_path / "ok-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        textwrap.dedent(
            """\
            ---
            name: ok-skill
            description: Uses screenshot but pairs it with text-extraction.
            allowed-tools: Bash
            ---
            # ok-skill
            ## Procedure
            Take a screenshot then use text-extraction to parse the result.
            """
        )
    )
    result = _run_check("screenshot-overuse", tmp_path)
    assert result.returncode == 0, (
        f"Expected exit 0 for adjacent text-extraction; got {result.returncode}\n"
        f"{result.stdout}{result.stderr}"
    )


# ---------------------------------------------------------------------------
# AC1: Synthetic-fixture — rule fires on violation (missing-tool-decl)
# ---------------------------------------------------------------------------


def test_missing_tool_decl_fires_on_violation(tmp_path: Path) -> None:
    """AC1: missing-tool-decl exits 1 when SKILL.md has no allowed-tools and >= 2 tools."""
    skill_dir = tmp_path / "no-decl-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        textwrap.dedent(
            """\
            ---
            name: no-decl-skill
            description: Missing allowed-tools but uses two tools in fenced blocks.
            ---
            # no-decl-skill
            ## Procedure
            ```bash
            Read /some/file.txt
            Bash uv build
            ```
            """
        )
    )
    result = _run_check("missing-tool-decl", tmp_path)
    assert result.returncode == 1, (
        f"Expected exit 1 for missing-tool-decl violation; got {result.returncode}\n"
        f"{result.stdout}{result.stderr}"
    )
    assert "Rule 2 FAIL" in result.stdout, f"Expected 'Rule 2 FAIL' in output:\n{result.stdout}"


def test_missing_tool_decl_ok_when_allowed_tools_present(tmp_path: Path) -> None:
    """AC1: missing-tool-decl exits 0 when allowed-tools: frontmatter is present."""
    skill_dir = tmp_path / "good-decl-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        textwrap.dedent(
            """\
            ---
            name: good-decl-skill
            description: Has allowed-tools frontmatter.
            allowed-tools: Bash
            ---
            # good-decl-skill
            ## Procedure
            ```bash
            Read /some/file.txt
            Bash uv build
            ```
            """
        )
    )
    result = _run_check("missing-tool-decl", tmp_path)
    assert result.returncode == 0, (
        f"Expected exit 0 with allowed-tools present; got {result.returncode}\n"
        f"{result.stdout}{result.stderr}"
    )


def test_missing_tool_decl_ok_when_only_one_tool(tmp_path: Path) -> None:
    """AC1: missing-tool-decl exits 0 when < 2 distinct tools detected (no false positive)."""
    skill_dir = tmp_path / "one-tool-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        textwrap.dedent(
            """\
            ---
            name: one-tool-skill
            description: Uses only one tool so no declaration required.
            ---
            # one-tool-skill
            ## Procedure
            - Read the spec file for context.
            Read more files as needed.
            """
        )
    )
    result = _run_check("missing-tool-decl", tmp_path)
    assert result.returncode == 0, (
        f"Expected exit 0 for single-tool skill; got {result.returncode}\n"
        f"{result.stdout}{result.stderr}"
    )


# ---------------------------------------------------------------------------
# AC2b: Existing Skills have allowed-tools: frontmatter
# ---------------------------------------------------------------------------


def test_ai_workflows_skill_has_allowed_tools() -> None:
    """AC2b (smoke step 2b): .claude/skills/ai-workflows/SKILL.md has allowed-tools: frontmatter."""
    skill_md = SKILLS_DIR / "ai-workflows" / "SKILL.md"
    content = skill_md.read_text()
    assert re.search(r"^allowed-tools:", content, re.MULTILINE), (
        f"ai-workflows SKILL.md missing 'allowed-tools:' frontmatter: {skill_md}"
    )


def test_dep_audit_skill_has_allowed_tools() -> None:
    """AC2b (smoke step 2b): .claude/skills/dep-audit/SKILL.md has allowed-tools: frontmatter."""
    skill_md = SKILLS_DIR / "dep-audit" / "SKILL.md"
    content = skill_md.read_text()
    assert re.search(r"^allowed-tools:", content, re.MULTILINE), (
        f"dep-audit SKILL.md missing 'allowed-tools:' frontmatter: {skill_md}"
    )


# ---------------------------------------------------------------------------
# AC2: /audit-skills slash command shape
# ---------------------------------------------------------------------------


def test_audit_skills_command_exists() -> None:
    """AC2 (smoke step 1): .claude/commands/audit-skills.md exists."""
    assert AUDIT_SKILLS_CMD.exists(), f"audit-skills.md missing: {AUDIT_SKILLS_CMD}"


def test_audit_skills_command_has_four_section_anchors() -> None:
    """AC2 (smoke step 9): audit-skills.md carries all four required ## section anchors."""
    content = AUDIT_SKILLS_CMD.read_text()
    required = ["## Inputs", "## Procedure", "## Outputs", "## Return schema"]
    missing = [h for h in required if h not in content]
    assert not missing, (
        f"audit-skills.md missing section anchors: {missing}"
    )


# ---------------------------------------------------------------------------
# AC3: CI workflow wires both audit scripts
# ---------------------------------------------------------------------------


def test_ci_wires_md_discoverability() -> None:
    """AC3 (smoke step 3): ci.yml references scripts/audit/md_discoverability.py."""
    content = CI_YML.read_text()
    assert "scripts/audit/md_discoverability.py" in content, (
        "ci.yml does not reference scripts/audit/md_discoverability.py"
    )


def test_ci_wires_skills_efficiency() -> None:
    """AC3 (smoke step 3): ci.yml references scripts/audit/skills_efficiency.py."""
    content = CI_YML.read_text()
    assert "scripts/audit/skills_efficiency.py" in content, (
        "ci.yml does not reference scripts/audit/skills_efficiency.py"
    )


# ---------------------------------------------------------------------------
# AC7: CHANGELOG entry
# ---------------------------------------------------------------------------


def test_changelog_has_t25_entry() -> None:
    """AC7: CHANGELOG.md has a M21 Task 25 entry under [Unreleased]."""
    content = CHANGELOG.read_text()
    pattern = re.compile(r"^### (Added|Changed) — M21 Task 25:", re.MULTILINE)
    assert pattern.search(content), (
        "CHANGELOG missing '### (Added|Changed) — M21 Task 25:' entry under [Unreleased]"
    )
