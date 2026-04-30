"""Tests for M15 Task 03 — ``aiw list-tiers`` CLI command.

Covers AC-1 through AC-4 from
``design_docs/phases/milestone_15_tier_overlay/task_03_aiw_list_tiers_and_circuit_open_cascade.md``:

* AC-1: ``aiw list-tiers`` runs without error; ``--help`` exits 0.
* AC-2: Tier table output includes workflow name, tier name, route kind,
  model/flag, concurrency, timeout, fallback column.
* AC-3: ``--workflow`` filter shows only the named workflow's tiers;
  unknown workflow name exits with exactly code 2.
* AC-4: Imperative workflows (no ``WorkflowSpec``) appear as a single
  row with ``"(no tier registry exported)"``.

Plus two additional tests added in cycle 2 per Auditor decisions:

* Decision 1 (MED-01): bare ``aiw list-tiers`` discovers in-package
  workflows via ``_eager_import_in_package_workflows()`` — planner tiers
  appear in output without any pre-registration.
* Decision 2 (LOW-01): imperative-workflow ``"(no tier registry exported)"``
  code path is covered by a test (AC-4 test coverage gap).

No LLM is involved — ``list-tiers`` is a pure read.

Relationship to other modules
-----------------------------
* :mod:`ai_workflows.cli` — entry point under test.
* :mod:`ai_workflows.workflows` — registry; synthetic specs are
  registered in each test and cleared by the ``_clean_registry``
  autouse fixture (inside ``TestListTiersIsolated`` class).
* :mod:`ai_workflows.primitives.tiers` — ``LiteLLMRoute``,
  ``ClaudeCodeRoute``, ``TierConfig`` — used to build synthetic specs.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel
from typer.testing import CliRunner

from ai_workflows import workflows
from ai_workflows.cli import app
from ai_workflows.primitives.tiers import LiteLLMRoute, TierConfig
from ai_workflows.workflows.spec import LLMStep, WorkflowSpec, register_workflow

_RUNNER = CliRunner()


# ---------------------------------------------------------------------------
# Shared test models
# ---------------------------------------------------------------------------


class _TierInput(BaseModel):
    goal: str


class _TierOutput(BaseModel):
    result: str


# ---------------------------------------------------------------------------
# Decision 1 (MED-01) — eager-import shows planner tiers on bare invocation
#
# This test lives OUTSIDE the TestListTiersIsolated class so the registry
# is NOT reset before invocation.  ``_eager_import_in_package_workflows()``
# inside ``list_tiers()`` auto-imports the sibling workflow modules so their
# top-level ``register``/``register_workflow`` calls fire and the registry is
# populated at the point the output is rendered.
# ---------------------------------------------------------------------------


def test_list_tiers_shows_planner_tiers_on_bare_invocation() -> None:
    """MED-01 fix: bare ``aiw list-tiers`` discovers and prints the planner workflow's tiers.

    ``_eager_import_in_package_workflows()`` inside ``list_tiers()`` imports
    every sibling module in the ``ai_workflows.workflows`` package and — for
    modules that were already imported but whose registration was cleared (e.g.
    after ``_reset_for_tests()``) — re-triggers their registration by scanning
    module globals for :class:`WorkflowSpec` instances and ``build_<name>``
    callables.

    This test does not pre-register anything.  It does not reset or evict
    modules.  It relies entirely on ``_eager_import_in_package_workflows()``
    to handle both the "fresh import" and the "already loaded, registry cleared"
    cases.

    Asserts:
    - exit code is 0
    - ``"planner"`` appears in stdout (workflow column)
    - at least one in-package workflow is listed (sentinel not present)
    """
    result = _RUNNER.invoke(app, ["list-tiers"])

    assert result.exit_code == 0, f"unexpected exit {result.exit_code}: {result.output}"
    assert "planner" in result.output, (
        f"expected 'planner' in output, got:\n{result.output}"
    )
    # The planner registers at least one tier; the output must not be the
    # empty-registry sentinel.
    assert "(no workflows registered)" not in result.output


# ---------------------------------------------------------------------------
# TestListTiersIsolated — tests that need a clean registry
#
# The ``_clean_registry`` fixture is autouse=True within this class only,
# so the MED-01 test above is unaffected.
# ---------------------------------------------------------------------------


class TestListTiersIsolated:
    """Isolated tests for ``aiw list-tiers``.

    The class-scoped ``_clean_registry`` autouse fixture clears the workflow
    registry before and after each test in this class.  All synthetic specs
    registered here are therefore invisible to tests outside the class.

    AC-1/AC-2/AC-3/AC-4 (original 4 tests) + Decision 2 (LOW-01) live here.
    """

    @pytest.fixture(autouse=True)
    def _clean_registry(self) -> None:
        """Clear the workflow registry before and after each test.

        Prevents synthetic specs registered in one test leaking into another.
        Pattern mirrors tests/mcp/test_http_transport.py:117-121.
        """
        workflows._reset_for_tests()
        yield  # type: ignore[misc]
        workflows._reset_for_tests()

    # -----------------------------------------------------------------------
    # AC-1 / AC-2 — basic tier table output
    # -----------------------------------------------------------------------

    def test_list_tiers_shows_spec_workflow_tiers(self) -> None:
        """AC-1 + AC-2: register a spec workflow with one LiteLLM tier; ``aiw list-tiers``
        prints the tier name and model string.

        Asserts:
        - exit code is 0
        - ``"gemini/test"`` appears in stdout (model/flag column)
        - tier name ``"primary"`` appears in stdout
        - workflow name appears in stdout
        """
        spec = WorkflowSpec(
            name="tier_test_simple",
            input_schema=_TierInput,
            output_schema=_TierOutput,
            steps=[
                LLMStep(
                    tier="primary",
                    response_format=_TierOutput,
                    prompt_template="goal: {goal}",
                )
            ],
            tiers={
                "primary": TierConfig(
                    name="primary",
                    route=LiteLLMRoute(model="gemini/test"),
                    max_concurrency=2,
                    per_call_timeout_s=60,
                )
            },
        )
        register_workflow(spec)

        result = _RUNNER.invoke(app, ["list-tiers"])

        assert result.exit_code == 0, f"unexpected exit {result.exit_code}: {result.output}"
        assert "gemini/test" in result.output
        assert "primary" in result.output
        assert "tier_test_simple" in result.output

    # -----------------------------------------------------------------------
    # AC-2 — fallback chain rendered
    # -----------------------------------------------------------------------

    def test_list_tiers_fallback_chain_rendered(self) -> None:
        """AC-2: fallback column shows fallback model when a fallback route is set.

        Asserts:
        - exit code is 0
        - ``"gemini/fallback"`` appears in stdout (fallback column)
        """
        spec = WorkflowSpec(
            name="tier_test_fallback",
            input_schema=_TierInput,
            output_schema=_TierOutput,
            steps=[
                LLMStep(
                    tier="primary",
                    response_format=_TierOutput,
                    prompt_template="goal: {goal}",
                )
            ],
            tiers={
                "primary": TierConfig(
                    name="primary",
                    route=LiteLLMRoute(model="gemini/primary"),
                    fallback=[LiteLLMRoute(model="gemini/fallback")],
                )
            },
        )
        register_workflow(spec)

        result = _RUNNER.invoke(app, ["list-tiers"])

        assert result.exit_code == 0, f"unexpected exit {result.exit_code}: {result.output}"
        assert "gemini/fallback" in result.output

    # -----------------------------------------------------------------------
    # AC-3 — --workflow filter
    # -----------------------------------------------------------------------

    def test_list_tiers_workflow_filter(self) -> None:
        """AC-3: ``--workflow <name>`` shows only the named workflow's tiers.

        Registers two synthetic workflows; runs with ``--workflow name1``;
        asserts only name1 appears in stdout and name2 is absent.
        """
        spec_a = WorkflowSpec(
            name="filter_wf_a",
            input_schema=_TierInput,
            output_schema=_TierOutput,
            steps=[
                LLMStep(
                    tier="alpha",
                    response_format=_TierOutput,
                    prompt_template="goal: {goal}",
                )
            ],
            tiers={
                "alpha": TierConfig(
                    name="alpha",
                    route=LiteLLMRoute(model="gemini/alpha"),
                )
            },
        )
        spec_b = WorkflowSpec(
            name="filter_wf_b",
            input_schema=_TierInput,
            output_schema=_TierOutput,
            steps=[
                LLMStep(
                    tier="beta",
                    response_format=_TierOutput,
                    prompt_template="goal: {goal}",
                )
            ],
            tiers={
                "beta": TierConfig(
                    name="beta",
                    route=LiteLLMRoute(model="gemini/beta"),
                )
            },
        )
        register_workflow(spec_a)
        register_workflow(spec_b)

        result = _RUNNER.invoke(app, ["list-tiers", "--workflow", "filter_wf_a"])

        assert result.exit_code == 0, f"unexpected exit {result.exit_code}: {result.output}"
        assert "filter_wf_a" in result.output
        assert "filter_wf_b" not in result.output
        assert "gemini/alpha" in result.output
        assert "gemini/beta" not in result.output

    # -----------------------------------------------------------------------
    # AC-3 — unknown workflow exits with code 2
    # -----------------------------------------------------------------------

    def test_list_tiers_unknown_workflow_exits_2(self) -> None:
        """AC-3: ``--workflow nonexistent`` exits with exactly code 2.

        ``typer.BadParameter`` produces exit code 2 (same as Typer's own
        handling of invalid option values).
        """
        result = _RUNNER.invoke(app, ["list-tiers", "--workflow", "nonexistent"])

        assert result.exit_code == 2, (
            f"expected exit code 2 for unknown workflow, got {result.exit_code}: {result.output}"
        )

    # -----------------------------------------------------------------------
    # Decision 2 (LOW-01) — imperative workflow shows no-tier-registry row
    # -----------------------------------------------------------------------

    def test_list_tiers_imperative_workflow_shows_no_tier_registry(self) -> None:
        """LOW-01 fix: imperative workflows appear with ``"(no tier registry exported)"`` row.

        Inside the ``_clean_registry`` autouse scope (registry cleared before
        and after), register an imperative workflow via ``workflows.register``
        (no ``WorkflowSpec``), invoke ``aiw list-tiers``, and assert the
        sentinel string appears in stdout.

        Asserts:
        - exit code is 0
        - ``"(no tier registry exported)"`` in stdout
        - ``"imp_test"`` (the registered name) in stdout
        """
        workflows.register("imp_test", lambda: object())

        result = _RUNNER.invoke(app, ["list-tiers"])

        assert result.exit_code == 0, f"unexpected exit {result.exit_code}: {result.output}"
        assert "(no tier registry exported)" in result.output, (
            f"expected '(no tier registry exported)' in output, got:\n{result.output}"
        )
        assert "imp_test" in result.output
