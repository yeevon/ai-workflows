"""Hermetic test: zero deprecated thinking directives in .claude/.

Task: M20 Task 21 — Adaptive-thinking migration.
Relationship: Verifies that all `.claude/agents/*.md` and `.claude/commands/*.md`
  (including subdirectories) have been migrated away from deprecated
  `thinking: <literal>` shorthand and `budget_tokens` directives, and that every
  slash command and agent frontmatter contains `thinking:\\n  type: adaptive` plus
  a matching `effort:` line.

This test is intentionally hermetic (no live agent spawns, no network, no LLM
calls). It scans the filesystem directly. Pass/fail reflects the current on-disk
state of the `.claude/` directory.
"""

from __future__ import annotations

import re
from pathlib import Path

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CLAUDE_DIR = _REPO_ROOT / ".claude"
_COMMANDS_DIR = _CLAUDE_DIR / "commands"
_AGENTS_DIR = _CLAUDE_DIR / "agents"

# The 7 slash command files that must have adaptive thinking.
SLASH_COMMAND_FILES = [
    "auto-implement.md",
    "audit.md",
    "clean-tasks.md",
    "clean-implement.md",
    "queue-pick.md",
    "autopilot.md",
    "implement.md",
]

# The 9 agent files that must have adaptive thinking.
AGENT_FILES = [
    "builder.md",
    "auditor.md",
    "security-reviewer.md",
    "dependency-auditor.md",
    "architect.md",
    "sr-dev.md",
    "sr-sdet.md",
    "task-analyzer.md",
    "roadmap-selector.md",
]

# Pattern: `thinking: <literal>` (any shorthand variant — max/high/medium/low/xhigh).
# This matches YAML-inline shorthand like `thinking: max` on a single line.
# It does NOT match `thinking:` followed by a newline (block-scalar form used for adaptive).
_THINKING_SHORTHAND_RE = re.compile(
    r"^thinking:\s*(max|high|medium|low|xhigh)\s*$",
    re.MULTILINE,
)

# Pattern: `budget_tokens` anywhere in the file.
_BUDGET_TOKENS_RE = re.compile(r"budget_tokens")

# Pattern: `thinking:\n  type: adaptive` (block-scalar adaptive form).
# We check for `type: adaptive` within 5 lines after a `thinking:` line.
_THINKING_ADAPTIVE_RE = re.compile(
    r"^thinking:\s*\n\s+type:\s*adaptive\s*$",
    re.MULTILINE,
)

# Pattern: `effort:` line.
_EFFORT_RE = re.compile(r"^effort:\s*(high|medium|low|max|xhigh)\s*$", re.MULTILINE)


def _collect_all_claude_md_files() -> list[Path]:
    """Collect every .md file under .claude/ recursively."""
    return list(_CLAUDE_DIR.rglob("*.md"))


def _read(path: Path) -> str:
    """Read file text; return empty string if file does not exist."""
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


# ---------------------------------------------------------------------------
# AC1: Zero `thinking: <literal>` shorthand directives across .claude/
# ---------------------------------------------------------------------------

def test_no_thinking_shorthand_in_claude_dir() -> None:
    """AC1: zero `thinking: <literal>` shorthand in any .claude/ markdown file.

    Covers all shorthand variants: max, high, medium, low, xhigh.
    `thinking: high` in the old implement.md is the same deprecated dial as
    `thinking: max` per research brief §Lens 3.3.
    """
    hits: list[str] = []
    for path in _collect_all_claude_md_files():
        text = path.read_text(encoding="utf-8")
        for match in _THINKING_SHORTHAND_RE.finditer(text):
            hits.append(f"{path.relative_to(_REPO_ROOT)}:{match.group(0)!r}")

    assert not hits, (
        f"Found {len(hits)} deprecated `thinking: <literal>` shorthand directive(s):\n"
        + "\n".join(f"  {h}" for h in hits)
    )


# ---------------------------------------------------------------------------
# AC2: Zero `budget_tokens` literals across .claude/
# ---------------------------------------------------------------------------

def test_no_budget_tokens_in_claude_dir() -> None:
    """AC2: zero `budget_tokens` literals in any .claude/ markdown file.

    `budget_tokens` is the deprecated manual-budget form rejected on Opus 4.7.
    """
    hits: list[str] = []
    for path in _collect_all_claude_md_files():
        text = path.read_text(encoding="utf-8")
        for _match in _BUDGET_TOKENS_RE.finditer(text):
            hits.append(f"{path.relative_to(_REPO_ROOT)}")

    # Deduplicate (file may have multiple hits but we report per-file).
    unique_hits = sorted(set(hits))
    assert not unique_hits, (
        f"Found `budget_tokens` in {len(unique_hits)} file(s):\n"
        + "\n".join(f"  {h}" for h in unique_hits)
    )


# ---------------------------------------------------------------------------
# AC3: All 7 slash commands have `thinking: { type: adaptive }` + `effort:`
# ---------------------------------------------------------------------------

def test_slash_commands_have_adaptive_thinking() -> None:
    """AC3: each slash command frontmatter has `thinking:\\n  type: adaptive`."""
    missing: list[str] = []
    for filename in SLASH_COMMAND_FILES:
        path = _COMMANDS_DIR / filename
        text = _read(path)
        if not _THINKING_ADAPTIVE_RE.search(text):
            missing.append(filename)

    assert not missing, (
        f"{len(missing)} slash command(s) missing `thinking:\\n  type: adaptive`:\n"
        + "\n".join(f"  {f}" for f in missing)
    )


def test_slash_commands_have_effort() -> None:
    """AC3: each slash command frontmatter has an `effort:` line."""
    missing: list[str] = []
    for filename in SLASH_COMMAND_FILES:
        path = _COMMANDS_DIR / filename
        text = _read(path)
        if not _EFFORT_RE.search(text):
            missing.append(filename)

    assert not missing, (
        f"{len(missing)} slash command(s) missing `effort:` line:\n"
        + "\n".join(f"  {f}" for f in missing)
    )


# ---------------------------------------------------------------------------
# AC4: All 9 agents have `thinking: { type: adaptive }` + `effort:`
# ---------------------------------------------------------------------------

def test_agents_have_adaptive_thinking() -> None:
    """AC4: each agent frontmatter has `thinking:\\n  type: adaptive`."""
    missing: list[str] = []
    for filename in AGENT_FILES:
        path = _AGENTS_DIR / filename
        text = _read(path)
        if not _THINKING_ADAPTIVE_RE.search(text):
            missing.append(filename)

    assert not missing, (
        f"{len(missing)} agent(s) missing `thinking:\\n  type: adaptive`:\n"
        + "\n".join(f"  {f}" for f in missing)
    )


def test_agents_have_effort() -> None:
    """AC4: each agent frontmatter has an `effort:` line."""
    missing: list[str] = []
    for filename in AGENT_FILES:
        path = _AGENTS_DIR / filename
        text = _read(path)
        if not _EFFORT_RE.search(text):
            missing.append(filename)

    assert not missing, (
        f"{len(missing)} agent(s) missing `effort:` line:\n"
        + "\n".join(f"  {f}" for f in missing)
    )
