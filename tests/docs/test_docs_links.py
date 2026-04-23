"""Hermetic link-resolution test for M13 Task 03.

Pins two invariants for every ``*.md`` under the user-facing ``docs/``
tree:

1. Every relative markdown link resolves to a real file on disk.
   Absolute ``http(s)://`` links, bare-fragment ``#section`` links, and
   ``mailto:`` links are skipped. Anchor fragments in relative links
   (``architecture.md#section``) are file-checked, not anchor-checked —
   anchor validation is nice_to_have scope.

2. Any relative link that points into a builder-only tree —
   ``../design_docs/``, ``../CLAUDE.md``, ``../.claude/commands/``, or
   ``../milestone_*/`` — **must** be accompanied by the literal marker
   ``(builder-only, on design branch)`` somewhere on the same markdown
   line. A user who installed the project from PyPI lands on the
   ``main`` branch; those paths do not ship there. The marker is the
   only signal they get that following the link requires a repo clone
   on the ``design`` branch.

Composes over: the ``docs/`` rewrite shipped at M13 T03 (rewrote three
pre-pivot placeholders). Depends on: nothing. Adds zero runtime to the
pytest suite — pure filesystem + regex scan.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DOCS_DIR = REPO_ROOT / "docs"

_LINK_RE = re.compile(r"\[(?P<text>[^\]]+)\]\((?P<target>[^)]+)\)")

_BUILDER_ONLY_PREFIXES: tuple[str, ...] = (
    "../design_docs/",
    "../CLAUDE.md",
    "../.claude/commands/",
)
_BUILDER_ONLY_MILESTONE_RE = re.compile(r"\.\./milestone_\d+")
_BUILDER_ONLY_MARKER = "(builder-only, on design branch)"


def _is_builder_only_target(target: str) -> bool:
    """Return True when ``target`` points into a builder-only tree."""
    if target.startswith(_BUILDER_ONLY_PREFIXES):
        return True
    return bool(_BUILDER_ONLY_MILESTONE_RE.search(target))


def _strip_fragment(target: str) -> str:
    """Drop a trailing ``#anchor`` from a relative link target."""
    return target.split("#", 1)[0]


def _is_external(target: str) -> bool:
    """Return True when ``target`` is an absolute URL or mailto link."""
    return (
        target.startswith(("http://", "https://", "mailto:"))
        or target.startswith("#")
    )


def _display_path(md_path: Path) -> str:
    """Render ``md_path`` relative to the repo root when possible.

    Falls back to the absolute path for files outside the repo — the
    scanner runs against ``tmp_path`` in the unit tests, which are not
    under ``REPO_ROOT``.
    """
    try:
        return str(md_path.relative_to(REPO_ROOT))
    except ValueError:
        return str(md_path)


def _scan_markdown_file(md_path: Path) -> list[str]:
    """Return a list of human-readable violation messages for ``md_path``.

    Empty list means the file is clean. Each violation message names the
    file, the line number, and the failing link target. Fenced code
    blocks (lines inside a ``` ... ``` span) are skipped — ``[text](url)``
    inside a code sample is not a real link.
    """
    violations: list[str] = []
    source = md_path.read_text(encoding="utf-8")
    in_fence = False

    for lineno, line in enumerate(source.splitlines(), start=1):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue

        for match in _LINK_RE.finditer(line):
            target = match.group("target").strip()

            if _is_external(target):
                continue

            target_no_fragment = _strip_fragment(target)
            if not target_no_fragment:
                continue

            resolved = (md_path.parent / target_no_fragment).resolve()
            if not resolved.exists():
                violations.append(
                    f"{_display_path(md_path)}:{lineno} "
                    f"broken relative link: {target!r} "
                    f"(resolved to {resolved})"
                )
                continue

            if _is_builder_only_target(target) and _BUILDER_ONLY_MARKER not in line:
                violations.append(
                    f"{_display_path(md_path)}:{lineno} "
                    f"builder-only link {target!r} missing marker "
                    f"{_BUILDER_ONLY_MARKER!r} on the same line"
                )

    return violations


def test_docs_relative_links_resolve() -> None:
    """Every relative markdown link under ``docs/`` points at a real file.

    Enforces M13 T03 AC-7: the three user-facing docs must ship with
    working cross-references. A broken link on ``main`` is a first-
    impression failure for a PyPI user.
    """
    md_files = sorted(DOCS_DIR.glob("*.md"))
    assert md_files, f"expected at least one *.md under {DOCS_DIR}"

    all_violations: list[str] = []
    for md_path in md_files:
        all_violations.extend(_scan_markdown_file(md_path))

    assert not all_violations, "docs link violations:\n  " + "\n  ".join(all_violations)


def test_scanner_flags_unmarked_builder_only_link(tmp_path: Path) -> None:
    """The scanner reports a violation when a builder-only link lacks the marker.

    Enforces M13 T03 AC-8: the marker-enforcement rule is load-bearing.
    If a future doc edit adds a ``../design_docs/…`` link without the
    ``(builder-only, on design branch)`` suffix, the scanner must catch
    it. This test mutates a temporary ``.md`` file (not the real docs)
    and drives the scanner against it — pure unit test of the scanner
    function, no coupling to the shipped docs.
    """
    fake_doc = tmp_path / "fake.md"
    fake_doc.write_text(
        "# Fake\n"
        "See [the builder doc](../design_docs/architecture.md) for details.\n",
        encoding="utf-8",
    )

    (tmp_path.parent / "design_docs").mkdir(exist_ok=True)
    (tmp_path.parent / "design_docs" / "architecture.md").write_text("stub\n")

    violations = _scan_markdown_file(fake_doc)
    assert len(violations) == 1, f"expected exactly one violation, got {violations}"
    assert "missing marker" in violations[0]
    assert "design_docs/architecture.md" in violations[0]


def test_scanner_accepts_marked_builder_only_link(tmp_path: Path) -> None:
    """The scanner accepts a builder-only link that carries the marker.

    Companion to ``test_scanner_flags_unmarked_builder_only_link``:
    pins that a well-formed builder-only link passes silently. Without
    this, the scanner could drift into over-flagging (e.g. requiring
    the marker on every line regardless of link target) and silently
    block legitimate content.
    """
    (tmp_path.parent / "design_docs").mkdir(exist_ok=True)
    (tmp_path.parent / "design_docs" / "architecture.md").write_text("stub\n")

    fake_doc = tmp_path / "fake.md"
    fake_doc.write_text(
        "# Fake\n"
        "See [the builder doc](../design_docs/architecture.md) "
        "(builder-only, on design branch) for details.\n",
        encoding="utf-8",
    )

    violations = _scan_markdown_file(fake_doc)
    assert violations == [], f"expected no violations, got {violations}"
