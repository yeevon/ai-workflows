"""Doc-link resolution tests for the M9 T03 skill_install.md.

Pure-filesystem tests: assert the install walk-through lives where the
spec says and that every relative link in it resolves on disk. Guards
against renamed paths in M4 / M8 silently rotting the doc.

Relationship to other modules
-----------------------------
* ``design_docs/phases/milestone_9_skill/skill_install.md`` — the
  walk-through under test (T03 deliverable).
* ``README.md`` — root project README, asserted to link back at the
  walk-through.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DOC_PATH = REPO_ROOT / "design_docs" / "phases" / "milestone_9_skill" / "skill_install.md"
ROOT_README = REPO_ROOT / "README.md"

# Matches markdown-link URL targets: (...). Excludes pure-anchor (#foo)
# and external scheme://… targets; we only check local relative links.
_LINK_PATTERN = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_skill_install_doc_exists() -> None:
    """The install walk-through exists at the spec path."""
    assert DOC_PATH.is_file(), f"expected {DOC_PATH} to exist"
    assert _read(DOC_PATH).strip(), "skill_install.md must not be empty"


def test_skill_install_doc_links_resolve() -> None:
    """Every relative link in the doc resolves to an existing path.

    Anchors within the same file (``#foo``), external schemes
    (``http://…``, ``https://…``, ``mailto:…``), and links stripped of
    their target (``()``) are skipped. Anchored relative links (e.g.
    ``../foo.md#bar``) have the anchor trimmed before resolution.
    """
    body = _read(DOC_PATH)
    unresolved: list[str] = []
    for match in _LINK_PATTERN.finditer(body):
        raw = match.group(1).strip()
        if not raw:
            continue
        if raw.startswith(("#", "http://", "https://", "mailto:")):
            continue
        target = raw.split("#", 1)[0]
        if not target:
            continue
        resolved = (DOC_PATH.parent / target).resolve()
        if not resolved.exists():
            unresolved.append(f"{raw} → {resolved}")
    assert not unresolved, (
        "skill_install.md relative links failed to resolve:\n  - "
        + "\n  - ".join(unresolved)
    )


def test_root_readme_links_skill_install() -> None:
    """Root README contains a link to the install walk-through.

    Matches the spec's single-contextually-appropriate-line requirement;
    the test only asserts the substring presence, not placement.
    """
    body = _read(ROOT_README)
    assert "design_docs/phases/milestone_9_skill/skill_install.md" in body, (
        "root README.md must link to skill_install.md (M9 T03 AC-2)"
    )


def test_skill_install_doc_covers_http_mode() -> None:
    """M14 T01: skill_install.md §5 documents the HTTP transport.

    Pins the §5 heading slug + the three flags that form the public
    surface so the walk-through cannot silently rot. Matches on the
    flag tokens (``--transport http``, ``--cors-origin``, ``--host``)
    rather than exact prose so wording can evolve without a test edit.
    """
    body = _read(DOC_PATH)
    assert "## 5. HTTP mode for external hosts" in body, (
        "skill_install.md must carry the §5 heading 'HTTP mode for external hosts'"
    )

    heading_idx = body.index("## 5. HTTP mode for external hosts")
    next_heading_idx = body.index("\n## 6.", heading_idx)
    section = body[heading_idx:next_heading_idx]

    for token in ("--transport http", "--cors-origin", "--host"):
        assert token in section, (
            f"skill_install.md §5 must reference '{token}' (M14 T01 exit criterion 8)"
        )


def test_skill_install_doc_forbids_anthropic_api() -> None:
    """KDR-003 guardrail on the install doc.

    The doc is the user's install surface — it must never instruct
    anyone to set the banned API key or reach the Anthropic HTTP API.
    """
    body = _read(DOC_PATH)
    assert "ANTHROPIC_API_KEY" not in body, (
        "skill_install.md must never instruct callers to set ANTHROPIC_API_KEY (KDR-003)"
    )
    assert "anthropic.com/api" not in body, (
        "skill_install.md must never reference the Anthropic public HTTP API (KDR-003)"
    )
