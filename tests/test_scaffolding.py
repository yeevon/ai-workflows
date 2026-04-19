"""Acceptance tests for M1 Task 01 — Project Scaffolding.

These tests validate the structural deliverables of Task 01 only:

* the three top-level layers (`primitives`, `components`, `workflows`)
  import cleanly
* the `aiw` Typer app exposes `--help`
* the import-linter contracts in `pyproject.toml` pass
* the scaffolding files referenced by later tasks exist on disk

Behavioural tests (LLM calls, tool execution, storage round-trips, …) live
under `tests/primitives/`, `tests/components/`, and `tests/workflows/` and
are added by the corresponding implementation tasks.
"""

from __future__ import annotations

import importlib
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

REPO_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Layered package imports
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "module_name",
    [
        "ai_workflows",
        "ai_workflows.primitives",
        "ai_workflows.components",
        "ai_workflows.workflows",
        "ai_workflows.cli",
    ],
)
def test_layered_packages_import(module_name: str) -> None:
    """Every layer (and the CLI) must import without side-effect failures.

    Task 01 acceptance criterion: ``import ai_workflows.primitives`` works.
    We extend that to every package we created so a typo in any
    ``__init__.py`` is caught immediately.
    """
    module = importlib.import_module(module_name)
    assert module is not None


def test_package_exposes_version() -> None:
    """The top-level package advertises a ``__version__`` string."""
    import ai_workflows

    assert isinstance(ai_workflows.__version__, str)
    assert ai_workflows.__version__  # non-empty


# ---------------------------------------------------------------------------
# CLI smoke test
# ---------------------------------------------------------------------------


def test_aiw_help_runs() -> None:
    """``aiw --help`` should print Typer help text and exit 0.

    We invoke the Typer app in-process via ``CliRunner`` rather than
    shelling out, because a subprocess invocation depends on the console
    script being installed via ``uv sync`` which we cannot guarantee at
    test time.
    """
    from ai_workflows.cli import app

    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0, result.output
    assert "aiw" in result.output.lower()


def test_aiw_version_command() -> None:
    """``aiw version`` prints the package version."""
    from ai_workflows import __version__
    from ai_workflows.cli import app

    runner = CliRunner()
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0, result.output
    assert __version__ in result.output


# ---------------------------------------------------------------------------
# Scaffolding files
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "relative_path",
    [
        "pyproject.toml",
        "tiers.yaml",
        "pricing.yaml",
        ".gitignore",
        "migrations/001_initial.sql",
        ".github/workflows/ci.yml",
        "CHANGELOG.md",
        "docs/architecture.md",
        "docs/writing-a-component.md",
        "docs/writing-a-workflow.md",
    ],
)
def test_scaffolding_file_exists(relative_path: str) -> None:
    """Files declared by Task 01's directory tree must be on disk."""
    path = REPO_ROOT / relative_path
    assert path.is_file(), f"missing scaffolding file: {relative_path}"


def test_pyproject_declares_required_dependencies() -> None:
    """Every dependency listed in the Task 01 spec must appear in pyproject."""
    # Python 3.11+ ships tomllib in the stdlib.
    import tomllib

    with (REPO_ROOT / "pyproject.toml").open("rb") as fh:
        pyproject = tomllib.load(fh)

    required = {
        "langgraph",
        "langgraph-checkpoint-sqlite",
        "litellm",
        "fastmcp",
        "httpx",
        "pydantic",
        "pyyaml",
        "structlog",
        "typer",
        "yoyo-migrations",
    }
    declared = {
        # `uv` accepts both `pkg>=X` and `pkg==X`; split on the first
        # non-name character to extract the bare distribution name.
        _split_dep_name(spec) for spec in pyproject["project"]["dependencies"]
    }
    missing = required - declared
    assert not missing, f"missing dependencies in pyproject.toml: {sorted(missing)}"


def test_pyproject_registers_aiw_script() -> None:
    """The ``aiw`` console script must point at ``ai_workflows.cli:app``."""
    import tomllib

    with (REPO_ROOT / "pyproject.toml").open("rb") as fh:
        pyproject = tomllib.load(fh)
    scripts = pyproject["project"].get("scripts", {})
    assert scripts.get("aiw") == "ai_workflows.cli:app"


def test_pyproject_declares_expected_importlinter_contracts() -> None:
    """The architectural contracts from Task 01 must be present.

    Task 01 ships two statically-enforceable contracts:

    1. primitives cannot import components or workflows
    2. components cannot import workflows

    A third contract ("components cannot peek at each other's private
    state") is documented in the spec but cannot be expressed in
    ``import-linter`` today — its wildcard syntax only allows ``*`` to
    replace a whole module segment, so ``components.*._*`` is rejected.
    It is re-added in M2 Task 01 when components exist and private
    modules can be enumerated.
    """
    import tomllib

    with (REPO_ROOT / "pyproject.toml").open("rb") as fh:
        pyproject = tomllib.load(fh)
    contracts = pyproject["tool"]["importlinter"]["contracts"]
    names = {c["name"] for c in contracts}
    assert len(contracts) >= 2
    # Substring matching keeps the test resilient to minor wording tweaks.
    assert any("primitives" in n for n in names)
    assert any("components cannot import workflows" in n for n in names)


# ---------------------------------------------------------------------------
# import-linter contract enforcement
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    shutil.which("lint-imports") is None,
    reason="import-linter not installed in this environment",
)
def test_lint_imports_passes() -> None:
    """The committed code must satisfy every import-linter contract.

    This is the Task 01 acceptance criterion ``uv run lint-imports passes``
    expressed as a unit test so it runs alongside everything else.
    """
    result = subprocess.run(
        ["lint-imports"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"lint-imports failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )


# ---------------------------------------------------------------------------
# Secret-scan regex
# ---------------------------------------------------------------------------


def _extract_ci_secret_scan_regex() -> str:
    """Return the Anthropic key regex from ``.github/workflows/ci.yml``.

    Scans for the ``grep -E '<regex>'`` invocation used by the
    ``secret-scan`` job and returns the quoted pattern. M1-T01-ISS-08:
    parsing at test time keeps this test and CI in lock-step even if
    the regex is narrowed.
    """
    import re as _re

    ci_path = REPO_ROOT / ".github" / "workflows" / "ci.yml"
    content = ci_path.read_text(encoding="utf-8")
    match = _re.search(r"grep\s+-E\s+'([^']+)'", content)
    assert match, f"could not locate `grep -E '<regex>'` in {ci_path}"
    return match.group(1)


def test_secret_scan_regex_matches_known_key_shapes() -> None:
    """The CI secret-scan grep pattern must match real Anthropic key shapes.

    Parses the live regex out of ``.github/workflows/ci.yml`` at test
    time (M1-T01-ISS-08) so a CI-side narrowing either still passes or
    visibly breaks here. ISS-05 / ISS-08.
    """
    import re

    PATTERN = _extract_ci_secret_scan_regex()
    assert re.search(PATTERN, "key=sk-ant-abcDEF_123"), "pattern must match a valid key"
    assert not re.search(PATTERN, "nothing here"), "pattern must not match plain text"
    assert not re.search(PATTERN, "sk-openai-abc123"), "pattern must not match other providers"


def test_secret_scan_regex_is_extracted_from_ci_yml() -> None:
    """M1-T01-ISS-08: ensure the extractor found a non-trivial regex."""
    pattern = _extract_ci_secret_scan_regex()
    assert pattern.startswith("sk-ant-"), (
        f"expected an Anthropic-shaped pattern, got: {pattern!r}"
    )


# ---------------------------------------------------------------------------
# Console-script entry-point
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    shutil.which("aiw") is None,
    reason="aiw console script not installed (run `uv sync`)",
)
def test_aiw_console_script_resolves() -> None:
    """The installed ``aiw`` console script must resolve and exit 0.

    Complements ``test_aiw_help_runs`` (in-process CliRunner) by proving
    that the ``[project.scripts]`` entry point in ``pyproject.toml`` is
    wired correctly.  A broken entry point would pass the CliRunner test
    but fail here.  ISS-06.
    """
    result = subprocess.run(["aiw", "--help"], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "aiw" in result.stdout.lower()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _split_dep_name(spec: str) -> str:
    """Return the distribution name from a PEP 508 requirement string.

    e.g. ``pydantic-ai>=1.0`` → ``pydantic-ai``.
    """
    for sep in ("[", ">", "<", "=", "!", "~", ";", " "):
        idx = spec.find(sep)
        if idx != -1:
            return spec[:idx].strip()
    return spec.strip()


# Ensure the repo root is importable when pytest is invoked from elsewhere.
# (pytest already adds the rootdir, but this makes the test usable from any
# cwd without pytest discovery quirks.)
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
