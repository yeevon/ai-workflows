"""Tests for the audit-feedback re-prompt template (M12 Task 02 — KDR-011).

Pins the exact rendered shape of the ``_render_audit_feedback`` helper and the
:class:`AuditFailure` exception's ``revision_hint`` against the literal expected
string from the spec.  The template is part of the cascade's behavioural surface;
any silent drift in whitespace or section markers would corrupt the re-prompt
sent to the primary LLM on the next retry turn.

The ``_render_audit_feedback`` helper is module-private (leading underscore,
not in ``__all__``); tests do not import it directly.  Instead, test #4 pins the
exception's emitted ``revision_hint`` so that template ownership stays inside
``AuditFailure`` while the contract remains testable.

Test #1 does import ``_render_audit_feedback`` directly for the full-shape
contract test, consistent with the spec's "exact string asserted" requirement
(see §Tests — test #1 body).
"""

from __future__ import annotations

from ai_workflows.primitives.retry import (
    AuditFailure,
    RetryableSemantic,
    _render_audit_feedback,  # type: ignore[attr-defined]
    classify,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_EXPECTED_FULL = (
    "<orig>\n"
    "\n"
    "<audit-feedback>\n"
    "Reasons:\n"
    "- r1\n"
    "- r2\n"
    "Suggested approach: try X\n"
    "</audit-feedback>\n"
    "\n"
    "<ctx>"
)


# ---------------------------------------------------------------------------
# Test 1: full shape — exact whitespace + section markers
# ---------------------------------------------------------------------------


def test_audit_feedback_template_full_shape() -> None:
    """AC: _render_audit_feedback produces the exact spec-pinned string (test #1)."""
    result = _render_audit_feedback(
        primary_original="<orig>",
        failure_reasons=["r1", "r2"],
        suggested_approach="try X",
        primary_context="<ctx>",
    )
    assert result == _EXPECTED_FULL


# ---------------------------------------------------------------------------
# Test 2: empty reasons → "- (none)" under Reasons:
# ---------------------------------------------------------------------------


def test_audit_feedback_template_empty_reasons() -> None:
    """AC: empty failure_reasons renders '- (none)' under the Reasons: header."""
    result = _render_audit_feedback(
        primary_original="P",
        failure_reasons=[],
        suggested_approach="try Z",
        primary_context="C",
    )
    assert "Reasons:\n- (none)\n" in result


# ---------------------------------------------------------------------------
# Test 3: no suggested_approach → "(none)"
# ---------------------------------------------------------------------------


def test_audit_feedback_template_no_suggested_approach() -> None:
    """AC: suggested_approach=None renders 'Suggested approach: (none)'."""
    result = _render_audit_feedback(
        primary_original="P",
        failure_reasons=["r1"],
        suggested_approach=None,
        primary_context="C",
    )
    assert "Suggested approach: (none)\n" in result


# ---------------------------------------------------------------------------
# Test 4: AuditFailure.revision_hint byte-equal to expected template
# ---------------------------------------------------------------------------


def test_audit_failure_revision_hint_byte_equal_to_expected_template() -> None:
    """AC: AuditFailure.revision_hint matches the spec-pinned literal exactly (test #4).

    This test pins the exception's emitted hint — not the helper's return value —
    so the template ownership stays inside AuditFailure and is not testable only
    via the module-private helper import.
    """
    exc = AuditFailure(
        failure_reasons=["r1", "r2"],
        suggested_approach="try X",
        primary_original="<orig>",
        primary_context="<ctx>",
    )
    assert exc.revision_hint == _EXPECTED_FULL


# ---------------------------------------------------------------------------
# Test 5: AuditFailure is a RetryableSemantic subclass (bucket classification)
# ---------------------------------------------------------------------------


def test_audit_failure_is_retryable_semantic() -> None:
    """AC: issubclass(AuditFailure, RetryableSemantic) and classify() returns RetryableSemantic.

    KDR-006: AuditFailure rides the existing RetryableSemantic bucket without
    any edit to classify().
    """
    assert issubclass(AuditFailure, RetryableSemantic)

    exc = AuditFailure(
        failure_reasons=["r1"],
        suggested_approach=None,
        primary_original="P",
        primary_context="C",
    )
    assert classify(exc) is RetryableSemantic
