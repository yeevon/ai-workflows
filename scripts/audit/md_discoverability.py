"""MD-file discoverability audit script — M21 Task 24.

Checks .claude/agents/*.md files against the T24 discoverability rubric (rules 1-4).
Rule 5 (one topic per file) is human-judged; this script does not encode it.
Standalone utility; no imports from ai_workflows. Reusable for T26 agent_docs/ audit.

Spec-API: --check {summary|section-budget|code-block-len|section-count}
          --target <dir>  --max <int>  --min <int>
Exits non-zero on violations.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

MAX_SECTION_WORDS = 384  # 500 tokens / 1.3


def _strip_frontmatter(text: str) -> str:
    """Return text after YAML frontmatter (--- ... ---), or the full text if none."""
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].rstrip() != "---":
        return text
    for i, line in enumerate(lines[1:], start=1):
        if line.rstrip() == "---":
            return "".join(lines[i + 1 :])
    return text


def _get_md_files(target: Path) -> list[Path]:
    """Return .md files under target, including _common/ subdirectory."""
    files = sorted(target.glob("*.md"))
    common = target / "_common"
    if common.is_dir():
        files += sorted(common.glob("*.md"))
    return files


def _parse_sections(text: str) -> list[tuple[str, str]]:
    """Return (heading, body) pairs for each ## section in text."""
    parts = re.split(r"^(## .+)", text, flags=re.MULTILINE)
    return [
        (parts[i].strip(), parts[i + 1] if i + 1 < len(parts) else "")
        for i in range(1, len(parts), 2)
    ]


def check_summary(files: list[Path]) -> list[str]:
    """Rule 1: ≥3 non-empty non-heading prose lines before first ## heading."""
    errors = []
    for fpath in files:
        after_fm = _strip_frontmatter(fpath.read_text(encoding="utf-8"))
        count = 0
        for ln in after_fm.lstrip("\n").splitlines():
            if ln.startswith("## "):
                break
            if ln.strip() and not ln.startswith("#"):
                count += 1
        if count < 3:
            errors.append(
                f"{fpath}: Rule 1 FAIL — {count} prose line(s) before ## (need 3)"
            )
    return errors


def check_section_budget(files: list[Path]) -> list[str]:
    """Rule 3: no ## section exceeds MAX_SECTION_WORDS words (excl. code blocks)."""
    errors = []
    for fpath in files:
        after_fm = _strip_frontmatter(fpath.read_text(encoding="utf-8"))
        for heading, body in _parse_sections(after_fm):
            no_code = re.sub(r"```.*?```", "", body, flags=re.DOTALL)
            words = len(no_code.split())
            if words > MAX_SECTION_WORDS:
                errors.append(
                    f"{fpath}: Rule 3 FAIL — '{heading}' "
                    f"has {words} words (limit {MAX_SECTION_WORDS})"
                )
    return errors


def check_code_block_len(files: list[Path], max_lines: int = 20) -> list[str]:
    """Rule 4: no fenced code block exceeds max_lines lines."""
    errors = []
    pat = re.compile(r"^```.*?\n(.*?)```", re.DOTALL | re.MULTILINE)
    for fpath in files:
        blocks = pat.findall(fpath.read_text(encoding="utf-8"))
        for i, block in enumerate(blocks, start=1):
            n = len(block.splitlines())
            if n > max_lines:
                errors.append(
                    f"{fpath}: Rule 4 FAIL — code block #{i} has {n} lines"
                    f" (limit {max_lines})"
                )
    return errors


def check_section_count(files: list[Path], min_sections: int = 2) -> list[str]:
    """Rule 2: each file has at least min_sections ## headings."""
    errors = []
    for fpath in files:
        after_fm = _strip_frontmatter(fpath.read_text(encoding="utf-8"))
        n = len(_parse_sections(after_fm))
        if n < min_sections:
            errors.append(f"{fpath}: Rule 2 FAIL — {n} ## section(s) (minimum {min_sections})")
    return errors


def main(argv: list[str] | None = None) -> int:
    """Entry point for the discoverability audit script."""
    parser = argparse.ArgumentParser(description="Audit agent MD files against the T24 rubric.")
    parser.add_argument("--check", required=True,
        choices=["summary", "section-budget", "code-block-len", "section-count"])
    parser.add_argument("--target", required=True, type=Path)
    parser.add_argument("--max", type=int, default=20)
    parser.add_argument("--min", type=int, default=2)
    args = parser.parse_args(argv)

    if not args.target.is_dir():
        print(f"ERROR: target '{args.target}' is not a directory", file=sys.stderr)
        return 2

    files = _get_md_files(args.target)
    if not files:
        print(f"WARNING: no .md files found under '{args.target}'", file=sys.stderr)
        return 0

    dispatch = {
        "summary": lambda: check_summary(files),
        "section-budget": lambda: check_section_budget(files),
        "code-block-len": lambda: check_code_block_len(files, max_lines=args.max),
        "section-count": lambda: check_section_count(files, min_sections=args.min),
    }
    errors = dispatch[args.check]()

    if errors:
        for err in errors:
            print(err)
        return 1

    print(f"OK: {args.check} — all {len(files)} file(s) pass")
    return 0


if __name__ == "__main__":
    sys.exit(main())
