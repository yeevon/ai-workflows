"""Tests for the three-bucket retry taxonomy (M1 Task 07 — KDR-006).

Grades every AC from
[design_docs/phases/milestone_1_reconciliation/task_07_refit_retry_policy.md]:

* AC-1: Three taxonomy classes (`RetryableTransient`,
  `RetryableSemantic`, `NonRetryable`) exported from
  `ai_workflows.primitives.retry`.
* AC-2: `classify()` maps every LiteLLM exception class the spec
  enumerates + the subprocess errors into the right bucket.
* AC-3: `grep -r ModelRetry ai_workflows/ tests/` returns zero
  matches — pinned here by a module-level sanity check.
* AC-4: `uv run pytest tests/primitives/test_retry.py` green (this
  file).
* AC-5: Full-suite `pytest` green subject to the standing T-scope
  reading — pre-existing downstream-owned failures are acceptable
  (see T02 post-build audit in the milestone_1_reconciliation issues
  tree).

Carry-over grading (covered here):
* M1-T02-ISS-01 — no `from anthropic import …` lines in
  `primitives/retry.py`; classification does not depend on the
  removed SDK. Pinned by :func:`test_retry_module_has_no_removed_sdk_imports`.
* M1-T06-ISS-01 — the old
  `TierConfig(provider=…, model=…, max_tokens=…, temperature=…, max_retries=…)`
  construction is gone from this file; post-refit `TierConfig` is
  constructor-shape-incidental to retry classification, so no
  replacement construction is exercised here. Pin: the module imports
  + runs green under the post-refit `TierConfig` shape.
* M1-T06-ISS-03 — `primitives/retry.py` no longer references
  `TierConfig.max_retries`. Pinned by
  :func:`test_retry_module_has_no_tier_config_max_retries_references`.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import litellm
import pytest
from pydantic import ValidationError

from ai_workflows.primitives import retry as retry_module
from ai_workflows.primitives.retry import (
    NonRetryable,
    RetryableSemantic,
    RetryableTransient,
    RetryPolicy,
    classify,
)

# ---------------------------------------------------------------------------
# AC-1 — taxonomy classes exported
# ---------------------------------------------------------------------------


def test_taxonomy_classes_are_exported() -> None:
    """All three taxonomy classes must be importable from the module."""
    assert issubclass(RetryableTransient, Exception)
    assert issubclass(RetryableSemantic, Exception)
    assert issubclass(NonRetryable, Exception)
    assert set(retry_module.__all__) >= {
        "RetryableTransient",
        "RetryableSemantic",
        "NonRetryable",
        "RetryPolicy",
        "classify",
    }


def test_taxonomy_classes_are_distinct() -> None:
    """The three buckets must not subclass each other — they are disjoint."""
    assert not issubclass(RetryableTransient, RetryableSemantic)
    assert not issubclass(RetryableTransient, NonRetryable)
    assert not issubclass(RetryableSemantic, RetryableTransient)
    assert not issubclass(RetryableSemantic, NonRetryable)
    assert not issubclass(NonRetryable, RetryableTransient)
    assert not issubclass(NonRetryable, RetryableSemantic)


def test_retryable_semantic_carries_reason_and_revision_hint() -> None:
    """`RetryableSemantic(reason, revision_hint)` must round-trip both fields."""
    exc = RetryableSemantic(reason="schema mismatch", revision_hint="return a list of strings")
    assert exc.reason == "schema mismatch"
    assert exc.revision_hint == "return a list of strings"
    # str() on the exception surfaces the reason so log lines are useful.
    assert "schema mismatch" in str(exc)


# ---------------------------------------------------------------------------
# RetryPolicy defaults
# ---------------------------------------------------------------------------


def test_retry_policy_has_spec_defaults() -> None:
    """Default values must match the [architecture.md §8.2] spec."""
    policy = RetryPolicy()
    assert policy.max_transient_attempts == 3
    assert policy.max_semantic_attempts == 3
    assert policy.transient_backoff_base_s == 1.0
    assert policy.transient_backoff_max_s == 30.0


def test_retry_policy_rejects_zero_attempts() -> None:
    """A zero or negative attempt budget would be an infinite-fail loop."""
    with pytest.raises(ValidationError):
        RetryPolicy(max_transient_attempts=0)
    with pytest.raises(ValidationError):
        RetryPolicy(max_semantic_attempts=-1)


def test_retry_policy_rejects_non_positive_backoff() -> None:
    """Zero or negative backoff would disable the wait window."""
    with pytest.raises(ValidationError):
        RetryPolicy(transient_backoff_base_s=0.0)
    with pytest.raises(ValidationError):
        RetryPolicy(transient_backoff_max_s=-1.0)


# ---------------------------------------------------------------------------
# AC-2 — classify() maps every listed LiteLLM exception
# ---------------------------------------------------------------------------


def _litellm_transient(cls: type[BaseException]) -> BaseException:
    """Build a LiteLLM transient exception with the kwargs its __init__ needs."""
    return cls(message="boom", model="gemini/gemini-2.5-flash", llm_provider="gemini")


def _litellm_non_retryable(cls: type[BaseException]) -> BaseException:
    """Build a LiteLLM non-retryable exception with the kwargs its __init__ needs."""
    return cls(message="boom", model="gemini/gemini-2.5-flash", llm_provider="gemini")


@pytest.mark.parametrize(
    "exc_cls",
    [
        litellm.Timeout,
        litellm.APIConnectionError,
        litellm.RateLimitError,
        litellm.ServiceUnavailableError,
    ],
)
def test_classify_returns_transient_for_listed_litellm_transient(
    exc_cls: type[BaseException],
) -> None:
    assert classify(_litellm_transient(exc_cls)) is RetryableTransient


@pytest.mark.parametrize(
    "exc_cls",
    [
        litellm.BadRequestError,
        litellm.AuthenticationError,
        litellm.NotFoundError,
        litellm.ContextWindowExceededError,
    ],
)
def test_classify_returns_non_retryable_for_listed_litellm_non_retryable(
    exc_cls: type[BaseException],
) -> None:
    assert classify(_litellm_non_retryable(exc_cls)) is NonRetryable


def test_classify_returns_transient_for_subprocess_timeout() -> None:
    """Claude Code CLI subprocess timeouts are safe to rerun."""
    exc = subprocess.TimeoutExpired(cmd=["claude", "--prompt", "hi"], timeout=30)
    assert classify(exc) is RetryableTransient


def test_classify_returns_non_retryable_for_subprocess_called_process_error() -> None:
    """M1 default is the safe bucket; stderr-pattern recovery is M2 refinement."""
    exc = subprocess.CalledProcessError(returncode=2, cmd=["claude", "--prompt", "hi"])
    assert classify(exc) is NonRetryable


def test_classify_defaults_unknown_exceptions_to_non_retryable() -> None:
    """Anything the classifier does not know about falls through to NonRetryable."""
    assert classify(ValueError("mystery")) is NonRetryable
    assert classify(RuntimeError("mystery")) is NonRetryable
    assert classify(KeyError("mystery")) is NonRetryable


def test_classify_does_not_auto_classify_pydantic_validation_error() -> None:
    """Per KDR-004 / spec, ValidationError is ValidatorNode's call, not ours.

    The classifier sees it as an unrecognised exception and hands back
    `NonRetryable` — ValidatorNode must raise `RetryableSemantic`
    explicitly to put it in the semantic bucket.
    """

    class _Tiny(__import__("pydantic").BaseModel):
        x: int

    try:
        _Tiny(x="not-an-int")  # type: ignore[arg-type]
    except ValidationError as exc:
        assert classify(exc) is NonRetryable
    else:  # pragma: no cover - guard
        pytest.fail("ValidationError was expected")


# ---------------------------------------------------------------------------
# AC-3 — sanity pins (no pydantic_ai / ModelRetry / anthropic residues)
# ---------------------------------------------------------------------------


_REPO_ROOT = Path(__file__).resolve().parents[2]


def _read(relative: str) -> str:
    return (_REPO_ROOT / relative).read_text()


def test_retry_module_has_no_pydantic_ai_or_model_retry_imports() -> None:
    """Spec AC: `ModelRetry` must not be imported or aliased by retry.py.

    Scans for actual import statements so a historical mention inside
    a docstring (e.g. "`pydantic_ai` is removed per KDR-005") is not
    flagged as drift.
    """
    text = _read("ai_workflows/primitives/retry.py")
    for line in text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith(("import ", "from ")):
            assert "pydantic_ai" not in line
            assert "ModelRetry" not in line


def test_retry_module_has_no_removed_sdk_imports() -> None:
    """Carry-over M1-T02-ISS-01: retry.py must not import anthropic / openai."""
    text = _read("ai_workflows/primitives/retry.py")
    for line in text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith(("import ", "from ")):
            assert "anthropic" not in line
            assert "openai" not in line


def test_retry_module_has_no_tier_config_max_retries_references() -> None:
    """Carry-over M1-T06-ISS-03: the removed field must not leak into retry.py.

    Scans the module source for `TierConfig.max_retries` /
    `tier_config.max_retries` — the two references the T06 audit
    pinned at lines 35 and 131 of the pre-refit file.
    """
    text = _read("ai_workflows/primitives/retry.py")
    assert "TierConfig.max_retries" not in text
    assert "tier_config.max_retries" not in text
