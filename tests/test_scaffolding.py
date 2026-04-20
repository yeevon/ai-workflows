"""Acceptance tests for M1 Task 01 — Project Scaffolding.

These tests validate the structural deliverables of Task 01 only:

* the four top-level layers (`primitives`, `graph`, `workflows`, and
  the surfaces `cli` + `mcp`) import cleanly per the post-pivot
  [architecture.md §3](../design_docs/architecture.md) four-layer
  contract installed by M1 Task 12.
* the `aiw` Typer app exposes `--help`
* the import-linter contracts in `pyproject.toml` pass
* the scaffolding files referenced by later tasks exist on disk

Behavioural tests (LLM calls, storage round-trips, …) live under
``tests/primitives/``, ``tests/graph/``, ``tests/workflows/``, and
``tests/mcp/`` and are added by the corresponding implementation
tasks (M2 onward).
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
        "ai_workflows.graph",
        "ai_workflows.workflows",
        "ai_workflows.cli",
        "ai_workflows.mcp",
    ],
)
def test_layered_packages_import(module_name: str) -> None:
    """Every layer (and the CLI + MCP surfaces) must import without side-effect failures.

    M1 Task 12 flipped the package tree to the four-layer
    primitives → graph → workflows → surfaces shape. Task 01's
    acceptance criterion ("``import ai_workflows.primitives`` works")
    is extended to every package on that list so a typo in any
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


def test_workflow_hash_module_is_retired_per_adr_0001() -> None:
    """M1 Task 10 / ADR-0001: the pre-pivot ``workflow_hash`` primitive is gone.

    Pins three artefacts at once — the module, the test file, and the
    ADR — so a future restore of any of the first two visibly collides
    with the decision recorded in the third.
    """
    module_path = REPO_ROOT / "ai_workflows" / "primitives" / "workflow_hash.py"
    assert not module_path.exists(), (
        "workflow_hash.py must stay deleted per ADR-0001; "
        "resurrecting it requires a new ADR superseding 0001."
    )

    test_path = REPO_ROOT / "tests" / "primitives" / "test_workflow_hash.py"
    assert not test_path.exists(), (
        "tests/primitives/test_workflow_hash.py must stay deleted per ADR-0001."
    )

    adr_path = REPO_ROOT / "design_docs" / "adr" / "0001_workflow_hash.md"
    assert adr_path.is_file(), "ADR-0001 must exist at design_docs/adr/0001_workflow_hash.md."
    adr_text = adr_path.read_text(encoding="utf-8")
    assert "Accepted" in adr_text, "ADR-0001 must declare its status."
    assert "Option B" in adr_text, "ADR-0001 must name the Remove outcome."
    assert "KDR-009" in adr_text, "ADR-0001 must cite KDR-009 per the task spec."

    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("ai_workflows.primitives.workflow_hash")


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
    """The four-layer architectural contracts from M1 Task 12 must be present.

    M1 Task 12 replaced the pre-pivot three-contract set (which named
    ``components``) with the post-pivot four-layer contract per
    [architecture.md §3](../design_docs/architecture.md):

    1. primitives cannot import graph, workflows, or surfaces
    2. graph cannot import workflows or surfaces
    3. workflows cannot import surfaces

    Substring matching keeps the test resilient to wording tweaks
    while pinning the layer vocabulary.
    """
    import tomllib

    with (REPO_ROOT / "pyproject.toml").open("rb") as fh:
        pyproject = tomllib.load(fh)
    contracts = pyproject["tool"]["importlinter"]["contracts"]
    names = {c["name"] for c in contracts}
    assert len(contracts) == 3, f"expected exactly 3 contracts, got {len(contracts)}: {names}"
    assert any("primitives cannot import" in n for n in names)
    assert any("graph cannot import" in n for n in names)
    assert any("workflows cannot import surfaces" in n for n in names)


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
