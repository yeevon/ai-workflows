"""Wheel-contents regression guard for M13 Task 01.

Pins two invariants the published wheel must hold:

1. The repo-root ``migrations/`` directory is bundled under the wheel
   root (the ``tool.hatch.build.targets.wheel.force-include`` hook in
   ``pyproject.toml``) — without this, first-run ``aiw`` /
   ``aiw-mcp`` on a ``uvx`` / ``uv tool install`` install fails
   because ``yoyo-migrations`` reads scripts from an on-disk path the
   wheel never shipped. The primary install contract at M13.
2. The ``ai_workflows/`` source package is still swept as a plain
   Python package (the ``packages = ["ai_workflows"]`` line must not
   silently regress when ``force-include`` is added).

The test runs ``uv build --wheel --out-dir <tmp_path>`` as a
subprocess and inspects the resulting ``.whl`` archive directly. It is
hermetic (no network, no provider call) and runs in the default
``uv run pytest`` suite. Skipped when ``uv`` is not on PATH — CI
always has it; a developer running without ``uv`` sees a loud skip
rather than a false failure.
"""

from __future__ import annotations

import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def _have_uv() -> bool:
    """Return True when the ``uv`` CLI is available on PATH."""
    return shutil.which("uv") is not None


@pytest.fixture(scope="module")
def built_wheel(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Run ``uv build --wheel`` against the repo and return the ``.whl`` path.

    Module-scoped so the two tests below share one build — ``uv build``
    is the expensive step; the assertions are cheap zipfile reads.
    """
    if not _have_uv():
        pytest.skip("uv CLI not available")

    out_dir = tmp_path_factory.mktemp("wheel_out")
    result = subprocess.run(
        ["uv", "build", "--wheel", "--out-dir", str(out_dir)],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, (
        f"uv build failed (exit {result.returncode}):\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )

    wheels = list(out_dir.glob("*.whl"))
    assert len(wheels) == 1, f"expected exactly one wheel, got {wheels}"
    return wheels[0]


def test_built_wheel_includes_migrations(built_wheel: Path) -> None:
    """Wheel archive must contain the repo-root ``migrations/*.sql`` data.

    This is the shipping-blocker fixed by
    ``[tool.hatch.build.targets.wheel.force-include]``. Without the
    hook the wheel only sweeps ``packages = ["ai_workflows"]`` and
    ``migrations/`` is silently omitted — breaking first-run
    ``aiw`` / ``aiw-mcp`` on any ``uvx`` / ``uv tool install``.
    """
    with zipfile.ZipFile(built_wheel) as zf:
        names = set(zf.namelist())

    # M13 T01 task spec names these two explicitly. If future
    # migrations land (e.g. ``003_artifacts.sql`` already exists
    # at repo root), they're also covered by the whole-dir assertion
    # below — shipping the entire ``migrations/`` tree is the invariant.
    assert "migrations/001_initial.sql" in names, sorted(names)
    assert "migrations/002_reconciliation.sql" in names, sorted(names)

    shipped_sql = {n for n in names if n.startswith("migrations/") and n.endswith(".sql")}
    on_disk_sql = {
        f"migrations/{p.name}"
        for p in (REPO_ROOT / "migrations").iterdir()
        if p.suffix == ".sql"
    }
    assert shipped_sql == on_disk_sql, (
        f"wheel migrations set diverges from repo migrations/:\n"
        f"  only in wheel: {shipped_sql - on_disk_sql}\n"
        f"  only on disk:  {on_disk_sql - shipped_sql}"
    )


def test_built_wheel_includes_ai_workflows_package(built_wheel: Path) -> None:
    """Wheel archive must still contain the ``ai_workflows`` source package.

    Sanity guard — adding ``force-include`` must not regress the
    ``packages = ["ai_workflows"]`` sweep. If this fails the package
    body stopped shipping, which would also be a shipping bug.
    """
    with zipfile.ZipFile(built_wheel) as zf:
        names = set(zf.namelist())

    assert "ai_workflows/__init__.py" in names, sorted(names)
    assert "ai_workflows/primitives/storage.py" in names, sorted(names)


def test_built_wheel_excludes_builder_mode_artefacts(built_wheel: Path) -> None:
    """Builder-mode artefacts must not ship in the distributable wheel.

    Per milestone README §Exit criteria 2 + §Branch model:
    ``design_docs/``, ``CLAUDE.md``, and ``.claude/commands/`` are
    builder/auditor-workflow artefacts. They land on the ``design``
    branch only; the ``main`` branch (which publishes to PyPI) drops
    them at M13 T05. Even during the branch-split window where they
    briefly coexist in the source tree, ``packages = ["ai_workflows"]``
    + the ``force-include`` hook must never sweep them. This test
    pins that invariant so a future hatchling-config edit (e.g. a
    ``force-include`` typo that broadens the sweep) cannot silently
    leak builder artefacts into a published wheel.
    """
    with zipfile.ZipFile(built_wheel) as zf:
        names = list(zf.namelist())

    forbidden_prefixes = ("design_docs/", ".claude/commands/")
    for name in names:
        for prefix in forbidden_prefixes:
            assert not name.startswith(prefix), (
                f"wheel leaked builder-mode path: {name} "
                f"(matched forbidden prefix {prefix!r})"
            )
    assert "CLAUDE.md" not in names, (
        f"wheel leaked CLAUDE.md; full list: {sorted(names)}"
    )


def test_built_wheel_excludes_dotenv_and_loose_yaml(built_wheel: Path) -> None:
    """0.1.1 patch — wheel must not ship `.env*` or bare-root `*.yaml`.

    Belt-and-braces against accidental secrets leakage. The current
    ``packages = ["ai_workflows"]`` + targeted ``force-include`` for
    ``migrations/`` makes this invariant hold by construction (repo-root
    `.env` / `docs/tiers.example.yaml` / `pricing.yaml` sit outside the source
    package), but a future ``force-include`` edit that broadens the
    sweep could silently leak them. This test pins the invariant so
    the wheel layer catches the regression directly.
    """
    with zipfile.ZipFile(built_wheel) as zf:
        names = list(zf.namelist())

    dotenv_leaks = [n for n in names if Path(n).name.startswith(".env")]
    assert not dotenv_leaks, (
        f"wheel leaked dotenv-shaped file(s): {dotenv_leaks}"
    )

    root_yaml_leaks = [
        n for n in names
        if n.endswith((".yaml", ".yml"))
        and "/" not in n.rstrip("/")
    ]
    assert not root_yaml_leaks, (
        f"wheel leaked bare-root YAML file(s): {root_yaml_leaks}. "
        f"Repo-root `pricing.yaml` is dev-time only and "
        f"must never ship."
    )
