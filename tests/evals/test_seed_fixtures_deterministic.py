"""Seed-fixture replay tests (M7 Task 05).

Three always-on tests that keep the committed ``evals/`` fixtures honest
for ``planner`` and ``slice_refactor``:

1. ``test_planner_seed_fixtures_replay_green_deterministic`` — loads
   every ``evals/planner/**/*.json`` fixture through
   :func:`ai_workflows.evals.storage.load_suite` and asserts
   :class:`EvalRunner` (deterministic mode) returns ``fail_count == 0``.
2. ``test_slice_refactor_seed_fixtures_replay_green_deterministic`` — same
   for ``slice_refactor``.
3. ``test_all_committed_fixtures_parse_to_eval_case`` — globs
   ``evals/**/*.json`` and asserts each file parses cleanly via
   :meth:`EvalCase.model_validate_json`. Catches a malformed commit
   before the downstream replay reports a less-helpful stub-adapter
   or wiring error.

All three tests run under the default ``uv run pytest`` — no env gate
— which is the M7-T05 AC-4 contract. The replay path is deterministic
(stub adapter, no provider calls), so these tests are hermetic and
cost-free.
"""

from __future__ import annotations

import contextlib
from pathlib import Path

import pytest

from ai_workflows import workflows
from ai_workflows.evals import EvalCase, EvalRunner
from ai_workflows.evals.storage import load_suite
from ai_workflows.workflows.planner import build_planner
from ai_workflows.workflows.slice_refactor import build_slice_refactor

_REPO_EVALS_ROOT = Path(__file__).resolve().parents[2] / "evals"


@pytest.fixture(autouse=True)
def _ensure_workflows_registered() -> None:
    """Guarantee both workflow builders are registered before each case.

    ``tests/cli/test_eval_commands.py`` (T04) uses an autouse fixture
    that clears the registry and re-registers only ``planner`` — the
    fixture has no post-yield teardown, so a later-running test that
    needs ``slice_refactor`` finds an empty slot. We re-register
    idempotently here: :func:`workflows.register` is a no-op when the
    same builder is already registered, and raises loud on a true
    conflict.
    """

    for name, builder in (
        ("planner", build_planner),
        ("slice_refactor", build_slice_refactor),
    ):
        # ValueError fires when a different builder object is already
        # registered under the name — happens when another test module
        # re-imports the module under a fresh registry reset. Trust the
        # current registration in that case.
        with contextlib.suppress(ValueError):
            workflows.register(name, builder)


@pytest.mark.asyncio
async def test_planner_seed_fixtures_replay_green_deterministic() -> None:
    """AC-2: ``aiw eval run planner`` → green on HEAD seed fixtures."""

    suite = load_suite("planner", root=_REPO_EVALS_ROOT)
    assert suite.cases, "planner seed fixture suite is empty"

    runner = EvalRunner(mode="deterministic")
    report = await runner.run(suite)

    assert report.fail_count == 0, "\n".join(report.summary_lines())
    assert report.pass_count == len(suite.cases)


@pytest.mark.asyncio
async def test_slice_refactor_seed_fixtures_replay_green_deterministic() -> None:
    """AC-2: ``aiw eval run slice_refactor`` → green on HEAD seed fixtures.

    Exercises the subgraph-node resolution path in
    :func:`ai_workflows.evals.runner._resolve_node_scope` — the
    ``slice_worker`` + ``slice_worker_validator`` pair lives inside the
    compiled ``slice_branch`` sub-graph, not at the top level of the
    :func:`build_slice_refactor` :class:`StateGraph`.
    """

    suite = load_suite("slice_refactor", root=_REPO_EVALS_ROOT)
    assert suite.cases, "slice_refactor seed fixture suite is empty"

    runner = EvalRunner(mode="deterministic")
    report = await runner.run(suite)

    assert report.fail_count == 0, "\n".join(report.summary_lines())
    assert report.pass_count == len(suite.cases)


def test_all_committed_fixtures_parse_to_eval_case() -> None:
    """AC: every committed fixture is a parseable :class:`EvalCase`."""

    fixture_paths = sorted(_REPO_EVALS_ROOT.rglob("*.json"))
    assert fixture_paths, "no committed eval fixtures found under evals/"

    for path in fixture_paths:
        raw = path.read_text(encoding="utf-8")
        try:
            EvalCase.model_validate_json(raw)
        except Exception as exc:  # noqa: BLE001 — surface offending path
            raise AssertionError(
                f"{path.relative_to(_REPO_EVALS_ROOT.parent)} did not parse "
                f"as EvalCase: {exc}"
            ) from exc
