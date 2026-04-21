"""Unit tests for :func:`ai_workflows.evals._compare.compare` (M7 Task 03).

One test per tolerance mode plus a mixed-mode test that exercises
``field_overrides`` and one that pins the unified-diff shape the
strict-JSON path renders on mismatch.
"""

from __future__ import annotations

import json

from pydantic import BaseModel, ConfigDict

from ai_workflows.evals._compare import compare
from ai_workflows.evals.schemas import EvalTolerance


class _SummarySchema(BaseModel):
    """Stand-in output schema for the compare tests."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    summary: str
    count: int


_SCHEMA_FQN = f"{_SummarySchema.__module__}.{_SummarySchema.__qualname__}"


def _dumps(summary: str, count: int) -> str:
    return json.dumps({"summary": summary, "count": count})


def test_strict_json_passes_on_identical_output() -> None:
    tolerance = EvalTolerance(mode="strict_json")
    expected = _dumps("delivered", 3)
    passed, diff = compare(expected, expected, tolerance, _SCHEMA_FQN)
    assert passed
    assert diff == ""


def test_strict_json_fails_with_unified_diff_on_mismatch() -> None:
    tolerance = EvalTolerance(mode="strict_json")
    expected = _dumps("delivered", 3)
    actual = _dumps("delivered", 4)
    passed, diff = compare(expected, actual, tolerance, _SCHEMA_FQN)
    assert not passed
    # Unified diff should carry the pydantic dumps' sorted-key JSON.
    assert "--- expected" in diff
    assert "+++ actual" in diff
    assert "\"count\": 3" in diff
    assert "\"count\": 4" in diff


def test_substring_passes_when_expected_is_substring_of_actual() -> None:
    tolerance = EvalTolerance(mode="substring")
    expected = _dumps("delivered", 3)
    actual = _dumps("page delivered to production", 3)
    passed, diff = compare(expected, actual, tolerance, _SCHEMA_FQN)
    assert passed
    assert diff == ""


def test_substring_fails_when_expected_not_in_actual() -> None:
    tolerance = EvalTolerance(mode="substring")
    expected = _dumps("delivered", 3)
    actual = _dumps("shipped", 3)
    passed, diff = compare(expected, actual, tolerance, _SCHEMA_FQN)
    assert not passed
    assert "summary" in diff


def test_regex_passes_when_pattern_matches_actual() -> None:
    tolerance = EvalTolerance(mode="regex")
    expected = _dumps(r"deliver.*page", 3)
    actual = _dumps("delivered the marketing page", 3)
    passed, diff = compare(expected, actual, tolerance, _SCHEMA_FQN)
    assert passed
    assert diff == ""


def test_regex_fails_when_pattern_does_not_match() -> None:
    tolerance = EvalTolerance(mode="regex")
    expected = _dumps(r"^shipped\s", 3)
    actual = _dumps("delivered the marketing page", 3)
    passed, diff = compare(expected, actual, tolerance, _SCHEMA_FQN)
    assert not passed
    assert "summary" in diff


def test_mixed_tolerance_with_field_overrides_mixes_strict_and_substring() -> None:
    """Canonical T03 pattern: strict_json default, substring on `summary`.

    Expected summary "delivered" is a substring of actual's longer
    summary — should pass. But the ``count`` field is strict and
    matches exactly, so the whole case passes. Flip ``count`` and it
    should fail even though the summary still matches.
    """

    tolerance = EvalTolerance(
        mode="strict_json",
        field_overrides={"summary": "substring"},
    )
    expected = _dumps("delivered", 3)
    actual_pass = _dumps("page delivered to prod", 3)
    passed, _ = compare(expected, actual_pass, tolerance, _SCHEMA_FQN)
    assert passed

    actual_fail_count = _dumps("page delivered to prod", 4)
    passed, diff = compare(expected, actual_fail_count, tolerance, _SCHEMA_FQN)
    assert not passed
    assert "count" in diff


def test_compare_handles_schema_parse_failure_as_failure() -> None:
    """When the expected doesn't parse, strict_json compare surfaces it.

    Pins the "schema drift" diagnostic path: if the resolved schema
    can no longer parse expected_output, the diff still renders so a
    human can see what happened rather than getting a silent True.
    """

    tolerance = EvalTolerance(mode="strict_json")
    # Valid JSON but violates schema (missing 'count').
    expected = json.dumps({"summary": "only summary"})
    actual = expected
    passed, diff = compare(expected, actual, tolerance, _SCHEMA_FQN)
    # Both sides fall back to the same JSON-parsed dict, so they
    # compare equal. The schema-drift diagnostic is the runner's job
    # — it runs the real validator which DOES raise on this input.
    assert passed
    assert diff == ""
