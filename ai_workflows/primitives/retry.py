"""Three-bucket retry taxonomy (M1 Task 07 — KDR-006, [architecture.md §8.2]).

Exposes the classifier + policy object M2's `RetryingEdge` and
`ValidatorNode` will consume. This module is **classification only** —
it does not run a retry loop. The execution layer (self-looping edges,
exponential backoff) lands in the `graph/` layer in M2 per
[architecture.md §4.2](../../design_docs/architecture.md) and
KDR-001.

Why three buckets (see [architecture.md §8.2](../../design_docs/architecture.md)):

* **`RetryableTransient`** — network blip, 429, 5xx, stream interruption.
  Safe to retry the same call. LiteLLM retries within a single call
  first; if exhausted, the exception bubbles up and `RetryingEdge`
  self-loops at the node level with exponential backoff per
  `RetryPolicy`.
* **`RetryableSemantic`** — output parsed but violated schema /
  business rule. Re-invoke the LLM with a revision hint. Raised
  explicitly by M2's `ValidatorNode` after catching pydantic
  `ValidationError` (KDR-004). This module does **not** auto-classify
  `ValidationError` — the validator is the one that decides whether a
  payload is a retryable schema miss or a non-retryable logic error.
* **`NonRetryable`** — auth failure, invalid model, logic error, budget
  exceeded. Node fails; graph-level policy decides (abort run vs.
  continue independent siblings). Two distinct non-retryable failures
  in the same run trigger the double-failure hard-stop (§8.2).

Relationship to sibling modules
-------------------------------
* `primitives/tiers.py` — post-M1 Task 06 tier retries ride under
  LiteLLM (KDR-007). The per-tier transient budget lives here, on
  `RetryPolicy.max_transient_attempts`, not on the tier config.
* `primitives/cost.py` — M1 Task 08 raises `NonRetryable("budget
  exceeded")` from `CostTracker.check_budget` per §8.5.
* `graph/` (M2) — `RetryingEdge` reads `RetryPolicy` and consumes
  `classify()` at the edge between an LLM node and its `ValidatorNode`.
  Retry-prompt wiring is LangGraph's job, not ours.

Classification keys off LiteLLM exception types and stdlib
`subprocess` errors — the pre-pivot provider SDKs (KDR-003, KDR-005)
are no longer imported anywhere in this module.
"""

from __future__ import annotations

import subprocess

import litellm
import structlog
from pydantic import BaseModel, Field

_LOG = structlog.get_logger(__name__)

# 0.1.3 patch: stderr captured from a Claude Code CLI subprocess
# (CalledProcessError) can be a crucial debugging signal (CLI version
# mismatch, OAuth expiry, transient auth refresh). Cap the logged
# length so a runaway error does not flood logs.
_STDERR_LOG_CAP = 2_000

__all__ = [
    "AuditFailure",
    "NonRetryable",
    "RetryPolicy",
    "RetryableSemantic",
    "RetryableTransient",
    "classify",
]


class RetryableTransient(Exception):
    """Network blip, 429, 5xx, stream interruption. Safe to retry the same call.

    LiteLLM retries once internally; a raised `RetryableTransient`
    means that internal budget is exhausted and the edge layer should
    self-loop per `RetryPolicy.max_transient_attempts` with
    exponential backoff bounded by `transient_backoff_max_s`.
    """


class RetryableSemantic(Exception):
    """Output parsed but violated schema / business rule.

    Raised by M2's `ValidatorNode` after catching a pydantic
    `ValidationError` or a business-rule mismatch. Carries a plain-text
    `reason` for the log line and a `revision_hint` that LangGraph
    feeds back to the model as the next-turn prompt so it can
    course-correct (KDR-004).
    """

    def __init__(self, reason: str, revision_hint: str) -> None:
        super().__init__(reason)
        self.reason = reason
        self.revision_hint = revision_hint


class NonRetryable(Exception):
    """Auth failure, invalid model, logic error, budget exceeded.

    Surfaces directly to the caller. The graph-level policy decides
    whether to abort the whole run or let independent siblings
    continue (§8.2). Two of these in the same run trigger the
    double-failure hard-stop.
    """


def _render_audit_feedback(
    *,
    primary_original: str,
    failure_reasons: list[str],
    suggested_approach: str | None,
    primary_context: str,
) -> str:
    """Render the audit-feedback re-prompt template (KDR-011, exit criterion 3).

    Exact shape pinned by ``tests/primitives/test_audit_feedback_template.py``:

        <primary_original>

        <audit-feedback>
        Reasons:
        - <reason 1>
        - <reason 2>
        Suggested approach: <suggested_approach or "(none)">
        </audit-feedback>

        <primary_context>

    Trailing newline omitted. The reasons block always renders (empty list
    → ``"Reasons:\\n- (none)"``); suggested_approach renders ``"(none)"`` when
    the auditor returned None. Module-private — not exported via ``__all__``
    and not imported by ``audit_cascade.py`` or any other module. Single
    ownership site: ``AuditFailure`` constructs the hint at ``__init__`` time.
    """
    reasons_block = "\n".join(f"- {r}" for r in failure_reasons) or "- (none)"
    suggested = suggested_approach or "(none)"
    return (
        f"{primary_original}\n\n"
        f"<audit-feedback>\n"
        f"Reasons:\n{reasons_block}\n"
        f"Suggested approach: {suggested}\n"
        f"</audit-feedback>\n\n"
        f"{primary_context}"
    )


class AuditFailure(RetryableSemantic):
    """Auditor verdict was passed=False — the primary's output failed semantic review.

    Carries the structured verdict payload + the rendered revision-guidance
    template the primary node will pick up on its next re-fire. Bucketed
    ``RetryableSemantic`` per KDR-006 so the existing ``RetryingEdge`` routes
    it back to the primary without taxonomy edits.

    Introduced by M12 Task 02 (KDR-011 foundation row 2). The ``revision_hint``
    is built by the module-private ``_render_audit_feedback`` helper; callers
    read it via ``exc.revision_hint`` — they never call the helper directly.
    """

    def __init__(
        self,
        *,
        failure_reasons: list[str],
        suggested_approach: str | None,
        primary_original: str,
        primary_context: str,
    ) -> None:
        revision_hint = _render_audit_feedback(
            primary_original=primary_original,
            failure_reasons=failure_reasons,
            suggested_approach=suggested_approach,
            primary_context=primary_context,
        )
        super().__init__(
            reason=f"audit_failed: {len(failure_reasons)} reason(s)",
            revision_hint=revision_hint,
        )
        self.failure_reasons = failure_reasons
        self.suggested_approach = suggested_approach


class RetryPolicy(BaseModel):
    """Per-tier retry budget + backoff shape.

    Consumed by M2's `RetryingEdge`. `max_transient_attempts` and
    `max_semantic_attempts` match the §8.2 defaults; the backoff
    fields cap the transient-retry sleep window so a misbehaving
    provider cannot lock a run up indefinitely.
    """

    max_transient_attempts: int = Field(default=3, ge=1)
    max_semantic_attempts: int = Field(default=3, ge=1)
    transient_backoff_base_s: float = Field(default=1.0, gt=0.0)
    transient_backoff_max_s: float = Field(default=30.0, gt=0.0)


_LITELLM_TRANSIENT: tuple[type[BaseException], ...] = (
    litellm.Timeout,
    litellm.APIConnectionError,
    litellm.RateLimitError,
    litellm.ServiceUnavailableError,
)

_LITELLM_NON_RETRYABLE: tuple[type[BaseException], ...] = (
    litellm.BadRequestError,
    litellm.AuthenticationError,
    litellm.NotFoundError,
    litellm.ContextWindowExceededError,
)


def classify(
    exc: BaseException,
) -> type[RetryableTransient | RetryableSemantic | NonRetryable]:
    """Map an exception to one of the three retry buckets.

    Returns the taxonomy **class** (not an instance) so callers can
    raise a fresh bucket-tagged exception or dispatch by `is` /
    `issubclass`. The mapping is intentionally narrow — anything not
    explicitly listed is `NonRetryable` so a misclassified error fails
    loudly instead of retrying into oblivion.

    Rules
    -----
    * LiteLLM `Timeout` / `APIConnectionError` / `RateLimitError` /
      `ServiceUnavailableError` → `RetryableTransient`.
    * LiteLLM `BadRequestError` / `AuthenticationError` /
      `NotFoundError` / `ContextWindowExceededError` → `NonRetryable`.
    * `subprocess.TimeoutExpired` → `RetryableTransient` (covers the
      Claude Code CLI subprocess tier; a timed-out wrapper is safe to
      rerun).
    * `subprocess.CalledProcessError` → `NonRetryable`. Stderr-pattern
      recovery (e.g. transient auth refresh) is flagged for M2
      refinement; at M1 we default to the safe bucket.
    * Anything else → `NonRetryable`.

    Pydantic `ValidationError` is **not** auto-classified. M2's
    `ValidatorNode` catches it and raises `RetryableSemantic`
    explicitly with a `revision_hint` so the validator owns the
    decision (KDR-004).
    """
    if isinstance(exc, _LITELLM_TRANSIENT):
        return RetryableTransient
    if isinstance(exc, _LITELLM_NON_RETRYABLE):
        return NonRetryable
    if isinstance(exc, subprocess.TimeoutExpired):
        return RetryableTransient
    if isinstance(exc, subprocess.CalledProcessError):
        # 0.1.3 patch: surface the CLI's own stderr before classifying.
        # Without this, auth-expiry / version-mismatch signals from the
        # `claude` subprocess are silently dropped once the exception is
        # reclassified. Truncate to cap log volume.
        stderr = _extract_stderr(exc)
        if stderr:
            _LOG.warning(
                "subprocess_called_process_error_stderr",
                cmd=_stringify_cmd(exc.cmd),
                returncode=exc.returncode,
                stderr_excerpt=stderr[:_STDERR_LOG_CAP],
                stderr_truncated=len(stderr) > _STDERR_LOG_CAP,
            )
        return NonRetryable
    # M12 T02: bucket instances already carry their classification as their type.
    # AuditFailure is a RetryableSemantic subclass; passing a pre-classified
    # bucket exception to classify() returns the correct bucket class without a
    # taxonomy change.  This also covers RetryableSemantic instances raised by
    # ValidatorNode that are forwarded to classify() by an outer catch block.
    if isinstance(exc, RetryableSemantic):
        return RetryableSemantic
    if isinstance(exc, RetryableTransient):
        return RetryableTransient
    return NonRetryable


def _extract_stderr(exc: subprocess.CalledProcessError) -> str:
    """Decode ``exc.stderr`` into a short string; return ``""`` when unusable."""
    stderr = exc.stderr
    if stderr is None:
        return ""
    if isinstance(stderr, bytes):
        try:
            return stderr.decode("utf-8", errors="replace").strip()
        except Exception:  # noqa: BLE001 — never raise from a log site
            return ""
    if isinstance(stderr, str):
        return stderr.strip()
    return ""


def _stringify_cmd(cmd: object) -> str:
    """Render ``exc.cmd`` (list[str] | str | None) as a one-line string."""
    if cmd is None:
        return ""
    if isinstance(cmd, (list, tuple)):
        return " ".join(str(part) for part in cmd)
    return str(cmd)
