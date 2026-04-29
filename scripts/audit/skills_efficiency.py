"""Skills efficiency audit script — M21 Task 25.

Checks .claude/skills/*/SKILL.md (and helper files) for two CI-gated
failure-mode heuristics (Nate Jones / Nicholas Rhodes "automated task bloat"):

  screenshot-overuse  — flag mentions of 'screenshot'/'image' without an
                        adjacent text-extraction reference. Uses generalized
                        regex (text-extraction|parse|extract|read.*text) rather
                        than the Anthropic Computer Use tool name 'get_page_text'
                        verbatim — ai-workflows is a CLI/MCP project (TA-LOW-03).

  missing-tool-decl   — flag SKILL.md files without 'allowed-tools:' frontmatter
                        when >= 2 distinct tool names appear in fenced code blocks
                        or at list-bullet starts. Mid-prose occurrences excluded
                        to avoid false positives against documentation prose.

Operator-only heuristics (tool-roundtrips, file-rereads) are slash-command-prose
only (TA-LOW-02 — judgement-rich, not mechanically reliable).

Spec-API: --check {screenshot-overuse|missing-tool-decl|all} --target <dir>
Exit 1 on findings; exit 0 on clean; exit 2 on bad invocation.
Relationship: standalone utility; no imports from ai_workflows. Finding shape
matches T24's md_discoverability.py ("Rule N FAIL — <skill>: <reason>").
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

_TOOL_NAMES = [
    "Read", "Write", "Edit", "Bash", "ToolSearch",
    "WebFetch", "Screenshot", "run_workflow", "resume_run",
    "list_runs", "cancel_run",
]

_BULLET_TOOL_RE = re.compile(
    r"(?m)^[ \t]*[-*\d]+\.?\s+(" + "|".join(re.escape(t) for t in _TOOL_NAMES) + r")\b"
)
_FENCED_BLOCK_RE = re.compile(r"```.*?```", re.DOTALL)
_TEXT_EXTRACT_RE = re.compile(
    r"text[\-_]?extraction|parse|extract|read[\s\-_]?text", re.IGNORECASE
)
_SCREENSHOT_IMG_RE = re.compile(r"\bscreenshot\b|\bimage\b", re.IGNORECASE)


def _tools_in_fenced_blocks(text: str) -> set[str]:
    """Return tool names found inside fenced code blocks."""
    found: set[str] = set()
    for block in _FENCED_BLOCK_RE.findall(text):
        for tool in _TOOL_NAMES:
            if re.search(r"\b" + re.escape(tool) + r"\b", block):
                found.add(tool)
    return found


def _tools_in_bullet_starts(text: str) -> set[str]:
    """Return tool names found at the start of list bullets."""
    return {m.group(1) for m in _BULLET_TOOL_RE.finditer(text)}


def _has_allowed_tools_frontmatter(text: str) -> bool:
    """Return True if the file has an 'allowed-tools:' key in its YAML frontmatter."""
    lines = text.splitlines()
    if not lines or lines[0].rstrip() != "---":
        return False
    for line in lines[1:]:
        if line.rstrip() == "---":
            break
        if re.match(r"^allowed-tools\s*:", line):
            return True
    return False


def _get_skill_files(target: Path) -> list[Path]:
    """Return all .md files under target/*/ (SKILL.md + helpers per Skill dir)."""
    if not target.is_dir():
        return []
    files: list[Path] = []
    for skill_dir in sorted(target.iterdir()):
        if skill_dir.is_dir():
            files.extend(sorted(skill_dir.glob("*.md")))
    return files


def _screenshot_has_adjacent_text_extraction(text: str, match: re.Match) -> bool:
    """Return True if there is a text-extraction ref within 120 chars of the match."""
    start = max(0, match.start() - 120)
    end = min(len(text), match.end() + 120)
    return bool(_TEXT_EXTRACT_RE.search(text[start:end]))


def check_screenshot_overuse(files: list[Path]) -> list[str]:
    """Rule 1: flag Skill files mentioning screenshot/image without text-extraction ref."""
    errors: list[str] = []
    for fpath in files:
        text = fpath.read_text(encoding="utf-8")
        for m in _SCREENSHOT_IMG_RE.finditer(text):
            if not _screenshot_has_adjacent_text_extraction(text, m):
                errors.append(
                    f"Rule 1 FAIL — {fpath}: mentions '{m.group()}' without"
                    f" adjacent text-extraction reference"
                )
                break
    return errors


def check_missing_tool_decl(files: list[Path]) -> list[str]:
    """Rule 2: flag SKILL.md without 'allowed-tools:' when >= 2 distinct tools detected."""
    errors: list[str] = []
    for fpath in (f for f in files if f.name == "SKILL.md"):
        text = fpath.read_text(encoding="utf-8")
        if _has_allowed_tools_frontmatter(text):
            continue
        tools = _tools_in_fenced_blocks(text) | _tools_in_bullet_starts(text)
        if len(tools) >= 2:
            errors.append(
                f"Rule 2 FAIL — {fpath}: no 'allowed-tools:' frontmatter but"
                f" {len(tools)} distinct tool(s) detected ({', '.join(sorted(tools))})"
            )
    return errors


def main(argv: list[str] | None = None) -> int:
    """Entry point for the skills efficiency audit script."""
    parser = argparse.ArgumentParser(
        description="Audit .claude/skills/ for token-waste heuristics (T25)."
    )
    parser.add_argument(
        "--check",
        required=True,
        choices=["screenshot-overuse", "missing-tool-decl", "all"],
    )
    parser.add_argument("--target", required=True, type=Path)
    args = parser.parse_args(argv)

    if not args.target.is_dir():
        print(f"ERROR: target '{args.target}' is not a directory", file=sys.stderr)
        return 2

    files = _get_skill_files(args.target)
    if not files:
        print(f"WARNING: no .md files found under '{args.target}'", file=sys.stderr)
        return 0

    errors: list[str] = []
    if args.check in ("screenshot-overuse", "all"):
        errors.extend(check_screenshot_overuse(files))
    if args.check in ("missing-tool-decl", "all"):
        errors.extend(check_missing_tool_decl(files))

    if errors:
        for err in errors:
            print(err)
        return 1

    print(f"OK: {args.check} — all {len(files)} skill file(s) pass")
    return 0


if __name__ == "__main__":
    sys.exit(main())
