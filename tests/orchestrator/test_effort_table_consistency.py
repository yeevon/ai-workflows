"""Hermetic test: effort_table.md assignments match every frontmatter declaration.

Task: M20 Task 21 — Adaptive-thinking migration.
Relationship: Reads `.claude/commands/_common/effort_table.md` and each agent /
  slash-command frontmatter; asserts that the effort value declared in the table
  matches what each file's frontmatter declares. This is the enforcement layer that
  prevents the table from drifting out of sync with the actual frontmatters.

Hermetic: no live agent spawns, no network, no LLM calls.
"""

from __future__ import annotations

import re
from pathlib import Path

# ---------------------------------------------------------------------------
# Repo paths
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[2]
_COMMANDS_DIR = _REPO_ROOT / ".claude" / "commands"
_AGENTS_DIR = _REPO_ROOT / ".claude" / "agents"
_EFFORT_TABLE_PATH = _COMMANDS_DIR / "_common" / "effort_table.md"

# ---------------------------------------------------------------------------
# Expected mappings (canonical source: effort_table.md)
# These must match the table rows exactly; the test also validates by parsing
# the table file directly so this dict serves as a double-check.
# ---------------------------------------------------------------------------

# Keys: filenames (basename only). Values: expected effort level.
EXPECTED_COMMAND_EFFORTS: dict[str, str] = {
    "auto-implement.md": "high",
    "audit.md": "high",
    "clean-tasks.md": "high",
    "clean-implement.md": "high",
    "queue-pick.md": "medium",
    "autopilot.md": "high",
    "implement.md": "high",
}

EXPECTED_AGENT_EFFORTS: dict[str, str] = {
    "builder.md": "high",
    "auditor.md": "high",
    "security-reviewer.md": "high",
    "dependency-auditor.md": "medium",
    "architect.md": "high",
    "sr-dev.md": "high",
    "sr-sdet.md": "high",
    "task-analyzer.md": "high",
    "roadmap-selector.md": "medium",
}

# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

# Matches a table row containing a filename and effort value.
# Table row format: `| `filename` | ... | `effort` | ... |`
# We match the filename (with .md) and the effort value from the same row.
_TABLE_ROW_RE = re.compile(
    r"^\|\s*`([^`]+\.md)`\s*\|[^|]*\|\s*`(high|medium|low|max|xhigh)`\s*\|",
    re.MULTILINE,
)

# Matches `effort: <value>` in frontmatter.
_EFFORT_FRONTMATTER_RE = re.compile(
    r"^effort:\s*(high|medium|low|max|xhigh)\s*$",
    re.MULTILINE,
)


def _parse_effort_table(table_text: str) -> dict[str, str]:
    """Parse effort assignments from the effort_table.md markdown file.

    Extracts every row that contains a backtick-quoted `.md` filename and a
    backtick-quoted effort level in the third column.

    Args:
        table_text: Full text of `_common/effort_table.md`.

    Returns:
        A dict mapping filename (basename) to effort level.
    """
    result: dict[str, str] = {}
    for match in _TABLE_ROW_RE.finditer(table_text):
        filename = match.group(1)
        effort = match.group(2)
        result[filename] = effort
    return result


def _get_frontmatter_effort(path: Path) -> str | None:
    """Extract the `effort:` value from a file's frontmatter.

    Args:
        path: Path to a markdown file with YAML frontmatter.

    Returns:
        The effort value string, or ``None`` if not found.
    """
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    match = _EFFORT_FRONTMATTER_RE.search(text)
    return match.group(1) if match else None


# ---------------------------------------------------------------------------
# AC5: effort_table.md exists and lists every agent + slash command
# ---------------------------------------------------------------------------

def test_effort_table_exists() -> None:
    """AC5: .claude/commands/_common/effort_table.md exists."""
    assert _EFFORT_TABLE_PATH.exists(), (
        f"effort_table.md not found at {_EFFORT_TABLE_PATH.relative_to(_REPO_ROOT)}"
    )


def test_effort_table_lists_all_commands() -> None:
    """AC5: effort_table.md lists all 7 slash commands."""
    table_text = _EFFORT_TABLE_PATH.read_text(encoding="utf-8")
    table_assignments = _parse_effort_table(table_text)
    missing = [f for f in EXPECTED_COMMAND_EFFORTS if f not in table_assignments]
    assert not missing, (
        f"effort_table.md is missing entries for {len(missing)} slash command(s):\n"
        + "\n".join(f"  {f}" for f in missing)
    )


def test_effort_table_lists_all_agents() -> None:
    """AC5: effort_table.md lists all 9 agents."""
    table_text = _EFFORT_TABLE_PATH.read_text(encoding="utf-8")
    table_assignments = _parse_effort_table(table_text)
    missing = [f for f in EXPECTED_AGENT_EFFORTS if f not in table_assignments]
    assert not missing, (
        f"effort_table.md is missing entries for {len(missing)} agent(s):\n"
        + "\n".join(f"  {f}" for f in missing)
    )


# ---------------------------------------------------------------------------
# Consistency: table values match frontmatter values (slash commands)
# ---------------------------------------------------------------------------

def test_command_frontmatter_matches_table() -> None:
    """Each slash command's frontmatter effort matches the effort_table.md assignment."""
    table_text = _EFFORT_TABLE_PATH.read_text(encoding="utf-8")
    table_assignments = _parse_effort_table(table_text)

    mismatches: list[str] = []
    for filename, expected_effort in EXPECTED_COMMAND_EFFORTS.items():
        path = _COMMANDS_DIR / filename
        actual_effort = _get_frontmatter_effort(path)
        table_effort = table_assignments.get(filename)

        if actual_effort is None:
            mismatches.append(f"{filename}: frontmatter has no `effort:` line")
        elif actual_effort != expected_effort:
            mismatches.append(
                f"{filename}: frontmatter has `effort: {actual_effort}`, "
                f"expected `effort: {expected_effort}`"
            )
        if table_effort is not None and table_effort != expected_effort:
            mismatches.append(
                f"{filename}: effort_table.md has `{table_effort}`, "
                f"expected `{expected_effort}`"
            )

    assert not mismatches, (
        f"{len(mismatches)} slash command effort mismatch(es):\n"
        + "\n".join(f"  {m}" for m in mismatches)
    )


# ---------------------------------------------------------------------------
# Consistency: table values match frontmatter values (agents)
# ---------------------------------------------------------------------------

def test_agent_frontmatter_matches_table() -> None:
    """Each agent's frontmatter effort matches the effort_table.md assignment."""
    table_text = _EFFORT_TABLE_PATH.read_text(encoding="utf-8")
    table_assignments = _parse_effort_table(table_text)

    mismatches: list[str] = []
    for filename, expected_effort in EXPECTED_AGENT_EFFORTS.items():
        path = _AGENTS_DIR / filename
        actual_effort = _get_frontmatter_effort(path)
        table_effort = table_assignments.get(filename)

        if actual_effort is None:
            mismatches.append(f"{filename}: frontmatter has no `effort:` line")
        elif actual_effort != expected_effort:
            mismatches.append(
                f"{filename}: frontmatter has `effort: {actual_effort}`, "
                f"expected `effort: {expected_effort}`"
            )
        if table_effort is not None and table_effort != expected_effort:
            mismatches.append(
                f"{filename}: effort_table.md has `{table_effort}`, "
                f"expected `{expected_effort}`"
            )

    assert not mismatches, (
        f"{len(mismatches)} agent effort mismatch(es):\n"
        + "\n".join(f"  {m}" for m in mismatches)
    )
