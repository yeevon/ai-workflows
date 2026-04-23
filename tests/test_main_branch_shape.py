"""Branch-shape invariant — M13 Task 05.

Pins the two-branch model:

* ``main`` (release branch): must NOT contain ``design_docs/``,
  ``CLAUDE.md``, ``.claude/commands/``, ``tests/skill/``, or
  ``scripts/spikes/``. These are builder-only surfaces that live on
  ``design_branch`` exclusively.
* ``design_branch`` (builder branch): must contain ``design_docs/``.
  The test environment signals the current branch via the
  ``AIW_BRANCH=design`` env var so a single test file covers both
  branches without duplication.

``.github/CONTRIBUTING.md`` is asserted unconditionally — it ships on
both branches as the one-paragraph pointer PyPI users follow to reach
the builder workflow.

The inversion mechanism (env-var-gated) mirrors the pattern used by
``tests/e2e_mcp/test_cli_smoke.py``'s ``AIW_E2E=1`` gating — a single
test suite, branch-conditional assertions, no per-branch file forks.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
_BRANCH = os.environ.get("AIW_BRANCH", "main").lower()
_ON_DESIGN = _BRANCH == "design"

_BUILDER_ONLY_PATHS: tuple[str, ...] = (
    "design_docs",
    "CLAUDE.md",
    ".claude/commands",
    "tests/skill",
    "scripts/spikes",
)


@pytest.mark.skipif(_ON_DESIGN, reason="runs on main only")
def test_design_docs_absence_on_main() -> None:
    """``main`` must not contain any builder-only surface.

    Enforces M13 T05 AC-1. Each path is a ``git rm``-ed builder
    artefact; re-appearance on ``main`` is a merge-direction violation
    (builder content flowing back to the release branch).
    """
    present = [p for p in _BUILDER_ONLY_PATHS if (REPO_ROOT / p).exists()]
    assert not present, (
        f"main branch must not carry builder-only paths, found: {present}. "
        f"Merge direction is design_branch → main only; these indicate a "
        f"backflow. Delete them from main and investigate the merge source."
    )


@pytest.mark.skipif(not _ON_DESIGN, reason="runs on design_branch only")
def test_design_docs_presence_on_design_branch() -> None:
    """``design_branch`` must contain ``design_docs/``.

    Enforces M13 T05 AC-4 inverse. Catches accidental deletion of the
    builder tree on the branch that owns it. Invoked via
    ``AIW_BRANCH=design uv run pytest tests/test_main_branch_shape.py``.
    """
    design_docs = REPO_ROOT / "design_docs"
    assert design_docs.is_dir(), (
        f"design_branch must carry the design_docs/ tree at {design_docs}; "
        f"missing directory indicates an accidental deletion on the builder branch."
    )

    claude_md = REPO_ROOT / "CLAUDE.md"
    assert claude_md.is_file(), (
        f"design_branch must carry CLAUDE.md at {claude_md}; missing file "
        f"indicates an accidental deletion of Builder/Auditor conventions."
    )


def test_contributing_md_exists_everywhere() -> None:
    """``.github/CONTRIBUTING.md`` must exist on both branches.

    Enforces M13 T05 AC-3. The one-paragraph pointer at design_branch
    is the public entry point for contributors landing on GitHub; it
    ships unchanged on both branches so the PyPI-hosted repo link +
    the clone-from-``main`` path both surface the same guidance.
    """
    contributing = REPO_ROOT / ".github" / "CONTRIBUTING.md"
    assert contributing.is_file(), (
        f"expected {contributing} on both main + design_branch"
    )
    body = contributing.read_text(encoding="utf-8")
    assert body.strip(), f"{contributing} must not be empty"
    assert "design_branch" in body, (
        f"{contributing} must reference the design_branch explicitly so "
        f"contributors know which branch to clone for the builder workflow"
    )
