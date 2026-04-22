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
        "docs/writing-a-graph-primitive.md",
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
    """The post-pivot architectural contracts must be present.

    M1 Task 12 replaced the pre-pivot three-contract set (which named
    ``components``) with a four-layer contract per
    [architecture.md §3](../design_docs/architecture.md); M7 Task 01
    extended the set with the evals-layer contract (M7 Task 03
    amendment relaxed its wording from "depends on graph +
    primitives only" to "cannot import surfaces" — see M7-T01-ISS-03
    / the pyproject.toml inline comment):

    1. primitives cannot import graph, workflows, or surfaces
    2. graph cannot import workflows or surfaces
    3. workflows cannot import surfaces
    4. evals cannot import surfaces

    Substring matching keeps the test resilient to wording tweaks
    while pinning the layer vocabulary.
    """
    import tomllib

    with (REPO_ROOT / "pyproject.toml").open("rb") as fh:
        pyproject = tomllib.load(fh)
    contracts = pyproject["tool"]["importlinter"]["contracts"]
    names = {c["name"] for c in contracts}
    assert len(contracts) == 4, f"expected exactly 4 contracts, got {len(contracts)}: {names}"
    assert any("primitives cannot import" in n for n in names)
    assert any("graph cannot import" in n for n in names)
    assert any("workflows cannot import surfaces" in n for n in names)
    assert any("evals cannot import surfaces" in n for n in names)


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
    ``secret-scan`` job and returns the quoted pattern. Parsing at
    test time keeps this test and CI in lock-step even if the regex
    is narrowed.
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
    time so a CI-side narrowing either still passes or visibly breaks
    here.
    """
    import re

    PATTERN = _extract_ci_secret_scan_regex()
    assert re.search(PATTERN, "key=sk-ant-abcDEF_123"), "pattern must match a valid key"
    assert not re.search(PATTERN, "nothing here"), "pattern must not match plain text"
    assert not re.search(PATTERN, "sk-openai-abc123"), "pattern must not match other providers"


def test_secret_scan_regex_is_extracted_from_ci_yml() -> None:
    """Ensure the extractor found a non-trivial regex."""
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


# ---------------------------------------------------------------------------
# M1 close-out (Task 13)
# ---------------------------------------------------------------------------
#
# Tests below pin the milestone-1 exit criteria asserted by M1 Task 13
# (milestone close-out). They verify that documentation state (README,
# roadmap, CHANGELOG), the scripts/ tree, the primitives source tree,
# and the dependency set all reflect the ✅ close. Future accidental
# reversion of any artefact visibly fails here.


def test_milestone_1_readme_marked_complete() -> None:
    """M1 Task 13 AC-6: milestone README status line reads ✅ Complete."""
    readme = (
        REPO_ROOT
        / "design_docs"
        / "phases"
        / "milestone_1_reconciliation"
        / "README.md"
    )
    text = readme.read_text(encoding="utf-8")
    assert "**Status:** ✅ Complete" in text, (
        "M1 README Status must be '✅ Complete (<date>)' after T13 close-out"
    )
    assert "## Outcome" in text, (
        "M1 README must carry an Outcome section summarising the milestone"
    )


def test_roadmap_m1_row_marked_complete() -> None:
    """M1 Task 13 AC-6: roadmap M1 row reads ✅ complete."""
    roadmap = REPO_ROOT / "design_docs" / "roadmap.md"
    text = roadmap.read_text(encoding="utf-8")
    assert "✅ complete" in text, (
        "design_docs/roadmap.md must mark M1 as '✅ complete (<date>)'"
    )


def test_changelog_has_m1_reconciliation_dated_section() -> None:
    """M1 Task 13 AC-5: CHANGELOG promotes M1 entries into a dated section."""
    changelog = REPO_ROOT / "CHANGELOG.md"
    text = changelog.read_text(encoding="utf-8")
    assert "## [M1 Reconciliation]" in text, (
        "CHANGELOG.md must have a '## [M1 Reconciliation] - <date>' section "
        "promoting the M1 task entries out of [Unreleased]"
    )
    assert "### Changed — M1 Task 13: Milestone Close-out" in text, (
        "CHANGELOG.md must carry a T13 close-out entry"
    )


def test_scripts_m1_smoke_removed_per_m1_t06_iss_04_and_m1_t10_iss_01() -> None:
    """M1 Task 13: resolves M1-T06-ISS-04 + M1-T10-ISS-01.

    Carry-over from [task_06_issue.md § M1-T06-ISS-04] and
    [task_10_issue.md § M1-T10-ISS-01]: ``scripts/m1_smoke.py`` imported
    six symbols removed during M1 (``pydantic_ai``,
    ``llm.model_factory``, ``WorkflowDeps``, ``load_tiers``,
    ``BudgetExceeded``, ``compute_workflow_hash``) and could not be
    executed. T13 chose the delete branch; M3 owns any post-pivot smoke
    script. Pin the absence so a future restore is visibly blocked.
    """
    smoke_path = REPO_ROOT / "scripts" / "m1_smoke.py"
    assert not smoke_path.exists(), (
        "scripts/m1_smoke.py must stay deleted per T13 close-out; "
        "a post-pivot smoke script belongs in M3 once a workflow is runnable."
    )


def test_primitives_source_tree_has_no_pydantic_ai_imports() -> None:
    """M1 Task 13 AC-3: zero ``pydantic_ai`` references in ``ai_workflows/``.

    The task-spec grep ``grep -r pydantic_ai ai_workflows/ tests/`` also
    matches the three regression-guard tests under
    ``tests/primitives/test_{cost,logging,retry}.py`` whose job is
    literally to *pin the absence* of ``pydantic_ai`` — this is the same
    convention T03's audit validated. Tightening AC-3 to the
    ``ai_workflows/`` source tree (the stricter spec intent) is
    unambiguous.
    """
    source_root = REPO_ROOT / "ai_workflows"
    offenders: list[str] = []
    for py_file in source_root.rglob("*.py"):
        text = py_file.read_text(encoding="utf-8")
        if "pydantic_ai" in text:
            offenders.append(str(py_file.relative_to(REPO_ROOT)))
    assert not offenders, (
        f"pydantic_ai references leaked into ai_workflows/: {offenders}"
    )


def test_no_nice_to_have_dependencies_adopted() -> None:
    """M1 Task 13 pre-close checklist: no silent nice_to_have.md adoption.

    Scans ``pyproject.toml`` + ``ai_workflows/`` for the seven deferred
    items ([nice_to_have.md §1/§3/§4/§8]): ``langfuse``, ``langsmith``,
    ``instructor``, ``docker-compose``, ``mkdocs``, ``deepagents``,
    ``opentelemetry``. Adoption requires an ADR + a new KDR per
    [CLAUDE.md](../CLAUDE.md) — not a task.
    """
    import re

    forbidden = (
        "langfuse",
        "langsmith",
        "instructor",
        "docker-compose",
        "mkdocs",
        "deepagents",
        "opentelemetry",
    )
    pattern = re.compile("|".join(re.escape(tok) for tok in forbidden))

    offenders: list[str] = []

    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    if pattern.search(pyproject):
        offenders.append("pyproject.toml")

    source_root = REPO_ROOT / "ai_workflows"
    for py_file in source_root.rglob("*.py"):
        text = py_file.read_text(encoding="utf-8")
        if pattern.search(text):
            offenders.append(str(py_file.relative_to(REPO_ROOT)))

    assert not offenders, (
        f"nice_to_have.md dependency leaked without ADR: {offenders}"
    )


# Ensure the repo root is importable when pytest is invoked from elsewhere.
# (pytest already adds the rootdir, but this makes the test usable from any
# cwd without pytest discovery quirks.)
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
