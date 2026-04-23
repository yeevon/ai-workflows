"""0.1.2 patch — pin the single-source-of-truth version invariant.

0.1.1 shipped with a stale ``ai_workflows.__version__ = "0.1.0"`` while
``pyproject.toml`` said ``version = "0.1.1"`` — the hardcoded literals
drifted. The published 0.1.1 wheel was functionally correct (dotenv
auto-load worked) but ``aiw version`` from a 0.1.1 install reported
``0.1.0``, a real regression.

0.1.2 fixes the root cause:

* ``ai_workflows/__init__.py:__version__`` is now the single source of
  truth.
* ``pyproject.toml`` declares ``dynamic = ["version"]`` and points
  ``[tool.hatch.version]`` at the Python module — hatchling parses the
  dunder at build time and stamps it into the wheel metadata.

This test pins the post-install invariant: whatever
``importlib.metadata`` reads from the installed wheel's metadata
(which is what ``pip show``, ``uv tool list``, and ``uvx`` display)
must match the Python dunder. A divergence here means either the
build missed the dunder or someone edited the dunder after install
without re-syncing — both are regressions.

Relationship to other tests
---------------------------
* :mod:`tests.test_wheel_contents` exercises the build itself via
  ``uv build``. A wheel whose metadata mismatches its bundled
  ``__version__`` would be a ``[tool.hatch.version]`` config bug, and
  the test below catches it at install time.
* :mod:`tests.test_dotenv_autoload` pins the other 0.1.1 patch
  behaviour (``.env`` auto-load). Orthogonal.
"""

from __future__ import annotations

import re
from importlib.metadata import version as metadata_version

import ai_workflows

_DIST_NAME = "jmdl-ai-workflows"
_SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+([-.][\w.]+)?$")


def test_dunder_version_matches_installed_metadata() -> None:
    """``ai_workflows.__version__`` must equal the wheel's metadata version.

    Reads both sides and compares: the Python dunder (source of truth
    at build time) and the installed wheel's metadata (what PyPI and
    `uv` see). They cannot diverge when
    ``[tool.hatch.version] path = "ai_workflows/__init__.py"`` is wired
    correctly.

    A failure here typically means either (a) the pyproject version
    config is stale (someone re-added a literal ``version = "..."``
    next to ``dynamic = ["version"]``), or (b) someone edited the
    dunder after install without a re-sync. Both are 0.1.2 regressions.
    """
    dunder = ai_workflows.__version__
    installed = metadata_version(_DIST_NAME)
    assert dunder == installed, (
        f"version drift: ai_workflows.__version__ = {dunder!r}, "
        f"importlib.metadata.version({_DIST_NAME!r}) = {installed!r}. "
        f"Single-source-of-truth invariant broken — check "
        f"pyproject.toml [tool.hatch.version] config and the "
        f"__version__ assignment in ai_workflows/__init__.py."
    )


def test_dunder_version_is_well_formed_semver() -> None:
    """``__version__`` must parse as a SemVer 2.0 string.

    Guard against typos or accidental non-release tags (``dev``,
    ``wip``) sneaking into the dunder. Accepts ``MAJOR.MINOR.PATCH``
    with optional suffix (``0.1.2`` / ``0.1.2rc1`` / ``0.2.0.post1``).
    """
    dunder = ai_workflows.__version__
    assert _SEMVER_RE.match(dunder), (
        f"ai_workflows.__version__ = {dunder!r} is not well-formed "
        f"SemVer (expected MAJOR.MINOR.PATCH[-suffix])."
    )
