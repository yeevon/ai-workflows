"""Hermetic shape guard for the repo-root ``README.md`` — M13 Task 04.

Pins three invariants on the user-facing README:

1. **Line count cap.** The README is ≤ 150 lines. The pre-T04 README
   was 235 lines — a dense builder-facing narrative. Post-trim it is a
   thin user-facing intro, and the cap blocks silent re-growth back
   toward the builder form.

2. **User-facing section headings.** Three literal headings must be
   present exactly once each: ``## Install``, ``## Contributing /
   from source``, ``## Development``. These are the sections a PyPI
   user needs to reach from a fresh clone or ``uvx`` invocation, and
   pinning the exact heading form blocks silent rename drift that
   would break the test's readability guarantee.

3. **Exactly one ``design_docs/`` reference.** The T05 branch split
   deletes ``design_docs/`` from the ``main`` branch. After T05, any
   ``design_docs/…`` reference in the README is a broken link for
   PyPI users. The one surviving reference is the ``design_docs/
   roadmap.md`` pointer in the ``## Next`` section, which carries the
   ``(builder-only, on design branch)`` marker from T03. Any second
   ``design_docs/`` mention is a T04 shape violation.

Sibling to [tests/docs/test_docs_links.py](test_docs_links.py) — that
file scans ``docs/*.md``; this file scans the repo-root README. Kept
separate because the two roots have different shape contracts.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
README_PATH = REPO_ROOT / "README.md"

_LINE_CAP = 150
_REQUIRED_HEADINGS: tuple[str, ...] = (
    "## Install",
    "## Contributing / from source",
    "## Development",
)
_BUILDER_ONLY_MARKER = "(builder-only, on design branch)"


def _read_readme_lines() -> list[str]:
    """Return README content split by newline, no trailing blank."""
    return README_PATH.read_text(encoding="utf-8").splitlines()


def test_readme_line_count_under_cap() -> None:
    """README line count must stay ≤ 150.

    Enforces M13 T04 AC-1. The pre-T04 README was 235 lines of builder
    narrative; the trim target is ≤ 150. Failure message includes the
    actual line count so the operator can see how far over.
    """
    lines = _read_readme_lines()
    assert len(lines) <= _LINE_CAP, (
        f"README.md is {len(lines)} lines, cap is {_LINE_CAP}. "
        f"Trim or extract content to docs/ before re-running."
    )


def test_readme_has_user_facing_sections() -> None:
    """README must contain the three user-facing section headings.

    Enforces M13 T04 AC-2. Each required heading must appear exactly
    once — zero matches is missing, two+ is accidental duplication.
    """
    lines = _read_readme_lines()
    for heading in _REQUIRED_HEADINGS:
        matches = [i for i, line in enumerate(lines, start=1) if line == heading]
        assert len(matches) == 1, (
            f"README.md must contain exactly one line matching {heading!r}; "
            f"found {len(matches)} occurrences at lines {matches}."
        )


def test_readme_has_exactly_one_design_docs_link() -> None:
    """README must mention ``design_docs/`` exactly once, with the marker.

    Enforces M13 T04 AC-5. Post-T05 branch split, ``design_docs/`` does
    not ship on ``main``; the one allowed reference is the roadmap
    pointer in ``## Next``, which carries the builder-only marker so
    PyPI users understand the link requires a repo clone on the
    ``design`` branch. Every other match is a shape violation and is
    reported with file path + line number + line content.
    """
    lines = _read_readme_lines()
    matches = [
        (lineno, line)
        for lineno, line in enumerate(lines, start=1)
        if "design_docs/" in line
    ]

    assert len(matches) == 1, (
        f"README.md must contain exactly one line referencing 'design_docs/'; "
        f"found {len(matches)}:\n"
        + "\n".join(f"  README.md:{lineno}  {line}" for lineno, line in matches)
    )

    (only_lineno, only_line) = matches[0]
    assert _BUILDER_ONLY_MARKER in only_line, (
        f"README.md:{only_lineno} references 'design_docs/' but is missing "
        f"the marker {_BUILDER_ONLY_MARKER!r}. Line content:\n  {only_line}"
    )
