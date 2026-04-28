"""Anti-cargo-cult detection helpers for the Auditor agent.

Task: M20 Task 20 — Carry-over checkbox-cargo-cult catch (extended detection).
Relationship: Orchestration-layer helper (scripts/orchestration/); no dependency on
  ai_workflows/ package.  The Auditor agent prompt (`.claude/agents/auditor.md`)
  describes these inspections in prose; this module provides an equivalent Python
  implementation so `tests/agents/test_auditor_anti_cargo_cult.py` can exercise every
  detection branch hermetically without spawning live agents.

Three failure modes detected (per spec §Mechanism):

1. **Carry-over checkbox-cargo-cult** — a `[x]` checkbox in the spec's carry-over
   section does not correspond to any diff hunk that addresses it.  Emits HIGH.

2. **Cycle-N finding overlap** — ≥ 50% of cycle-N Auditor findings share title
   similarity > threshold (default 0.70) with any cycle-(N-1) finding.  Emits MEDIUM
   "loop may be spinning; recommend human review."  Threshold operator-tunable via
   ``AIW_LOOP_DETECTION_THRESHOLD`` env-var.

3. **Rubber-stamp detection** — Auditor verdict is PASS, diff exceeds 50 lines, and
   zero HIGH+MEDIUM findings were raised.  Emits MEDIUM "verify reasoning on critical
   sweep."
"""

from __future__ import annotations

import difflib
import os
import re
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

DEFAULT_LOOP_DETECTION_THRESHOLD = 0.70
"""Default similarity ratio for cycle-N-vs-cycle-(N-1) finding overlap detection.

Operator-tunable via the ``AIW_LOOP_DETECTION_THRESHOLD`` environment variable.
Value must be a float in [0.0, 1.0].  The default (0.70) means a finding title
must score > 0.70 on ``difflib.SequenceMatcher.ratio()`` against a prior-cycle
finding title to count as an overlap.
"""


def get_loop_detection_threshold() -> float:
    """Return the operator-configured loop-detection threshold.

    Reads ``AIW_LOOP_DETECTION_THRESHOLD`` from the environment.  Falls back to
    ``DEFAULT_LOOP_DETECTION_THRESHOLD`` (0.70) if unset or unparseable.
    """
    raw = os.environ.get("AIW_LOOP_DETECTION_THRESHOLD", "")
    if raw.strip():
        try:
            val = float(raw.strip())
            if 0.0 <= val <= 1.0:
                return val
        except ValueError:
            pass
    return DEFAULT_LOOP_DETECTION_THRESHOLD


@dataclass
class CargoFinding:
    """A single anti-cargo-cult finding emitted by one of the three detectors.

    Attributes:
        severity: ``"HIGH"`` or ``"MEDIUM"``.
        message: Human-readable description of the finding.
        detector: Which detector produced this finding
            (``"checkbox"``, ``"cycle_overlap"``, or ``"rubber_stamp"``).
    """

    severity: str
    message: str
    detector: str


# ---------------------------------------------------------------------------
# Detector 1: carry-over checkbox without diff hunk
# ---------------------------------------------------------------------------

# Matches a checked carry-over checkbox in a markdown spec:
#   - [x] or - [X]  at the start of a line (after optional whitespace)
_CHECKED_BOX_RE = re.compile(r"^\s*-\s+\[[xX]\]\s+(.+)", re.MULTILINE)


def detect_checkbox_without_diff(
    spec_carry_over_text: str,
    diff_text: str,
) -> list[CargoFinding]:
    """Check that every ticked carry-over checkbox has a corresponding diff hunk.

    Args:
        spec_carry_over_text: The raw text of the ``## Carry-over from prior audits``
            section (or the full spec file — only checked checkboxes are extracted).
        diff_text: The full ``git diff`` / ``git log -p`` output for the current
            cycle's commits.

    Returns:
        A list of HIGH ``CargoFinding`` entries — one per ticked item that has no
        matching hunk in the diff.  Empty list means all ticked items appear to be
        covered.
    """
    findings: list[CargoFinding] = []
    checked_items = _CHECKED_BOX_RE.findall(spec_carry_over_text)

    for item_text in checked_items:
        # Build a normalized search key: strip leading issue-ID like "M20-T01-ISS-01 "
        # and severity tags like "(HIGH)" or "(MEDIUM)".
        search_key = _normalize_carry_over_title(item_text)
        if search_key and not _hunk_mentions(search_key, diff_text):
            findings.append(
                CargoFinding(
                    severity="HIGH",
                    message=(
                        f"Carry-over item checked ([x] {item_text.strip()[:80]}) "
                        f"but no corresponding diff hunk found. "
                        f"Verify the change was actually implemented."
                    ),
                    detector="checkbox",
                )
            )

    return findings


def _normalize_carry_over_title(text: str) -> str:
    """Strip issue-ID prefix, severity tags, and leading/trailing noise."""
    # Remove issue-ID prefix: M<N>-T<NN>-ISS-<NN>
    text = re.sub(r"^M\d+-T\d+-ISS-\d+\s*[:\-–]?\s*", "", text, flags=re.IGNORECASE)
    # Remove severity tags
    text = re.sub(r"\(HIGH\)|\(MEDIUM\)|\(LOW\)", "", text, flags=re.IGNORECASE)
    # Collapse whitespace
    text = " ".join(text.split())
    return text.strip()


def _hunk_mentions(search_key: str, diff_text: str) -> bool:
    """Return True if the diff references any significant keyword from search_key.

    Splits the search key into words (length ≥ 4), removes common English stop words,
    and checks whether ANY of the remaining keywords appears in the diff (case-insensitive).
    This avoids false negatives from case differences, camelCase vs snake_case, or
    minor rephrasing while still catching cases where the diff is completely unrelated.

    A True result means the diff plausibly addresses the carry-over item; False means
    no significant keyword from the item title appears anywhere in the diff.
    """
    if not search_key or not diff_text:
        return False

    _STOP_WORDS = frozenset(
        {
            "add", "added", "adds", "the", "this", "that", "with", "from", "into",
            "for", "and", "not", "when", "does", "without", "have", "missing",
            "each", "every", "must", "should", "will", "also", "then", "than",
        }
    )

    diff_lower = diff_text.lower()
    # Extract significant keywords: len >= 4, not a stop word
    keywords = [
        w.lower()
        for w in re.findall(r"[A-Za-z][A-Za-z0-9_]{3,}", search_key)
        if w.lower() not in _STOP_WORDS
    ]

    if not keywords:
        # No significant keywords — cannot falsify, treat as unverifiable (no finding)
        return True

    return any(kw in diff_lower for kw in keywords)


# ---------------------------------------------------------------------------
# Detector 2: cycle-N finding overlap with cycle-(N-1)
# ---------------------------------------------------------------------------

# Matches finding titles from issue-file sections like:
#   ## 🔴 HIGH — some finding title
#   ## 🟡 MEDIUM — another finding title
_FINDING_TITLE_RE = re.compile(
    r"^##\s+(?:🔴|🟡|🟢)?\s*(?:HIGH|MEDIUM|LOW)\s+[—–-]+\s*(.+)",
    re.MULTILINE | re.IGNORECASE,
)


def extract_finding_titles(issue_file_text: str) -> list[str]:
    """Extract finding titles from an Auditor issue file.

    Parses lines matching the canonical issue-file format::

        ## 🔴 HIGH — <title>
        ## 🟡 MEDIUM — <title>
        ## 🟢 LOW — <title>

    Args:
        issue_file_text: Full text of the issue file.

    Returns:
        List of stripped finding titles (may be empty for a PASS issue file with no
        findings).
    """
    return [m.strip() for m in _FINDING_TITLE_RE.findall(issue_file_text)]


def detect_cycle_overlap(
    current_titles: list[str],
    prior_titles: list[str],
    threshold: float | None = None,
) -> list[CargoFinding]:
    """Detect when cycle-N findings substantially overlap cycle-(N-1) findings.

    For each title in ``current_titles``, compute the maximum
    ``difflib.SequenceMatcher.ratio()`` against every title in ``prior_titles``.
    If ≥ 50% of current titles score above ``threshold``, emit a MEDIUM finding.

    Args:
        current_titles: Finding titles from the current cycle's issue file.
        prior_titles: Finding titles from the previous cycle's issue file.
        threshold: Similarity ratio cutoff (0.0–1.0).  Defaults to
            ``get_loop_detection_threshold()``.

    Returns:
        A list with zero or one MEDIUM ``CargoFinding``.  Zero findings means no
        suspicious overlap detected.
    """
    if threshold is None:
        threshold = get_loop_detection_threshold()

    if not current_titles or not prior_titles:
        return []

    overlap_count = 0
    for title_n in current_titles:
        best_ratio = max(
            difflib.SequenceMatcher(None, title_n, title_prev).ratio()
            for title_prev in prior_titles
        )
        if best_ratio > threshold:
            overlap_count += 1

    overlap_fraction = overlap_count / len(current_titles)

    if overlap_fraction >= 0.50:
        return [
            CargoFinding(
                severity="MEDIUM",
                message=(
                    f"cycle-N findings substantially overlap cycle-(N-1) "
                    f"({overlap_count}/{len(current_titles)} findings score "
                    f"> {threshold:.0%} similarity) — loop may be spinning; "
                    f"recommend human review."
                ),
                detector="cycle_overlap",
            )
        ]
    return []


# ---------------------------------------------------------------------------
# Detector 3: rubber-stamp detection
# ---------------------------------------------------------------------------

_DIFF_LINE_RE = re.compile(r"^[+\-](?![+\-])", re.MULTILINE)


def count_diff_lines(diff_text: str) -> int:
    """Count the number of added/removed lines in a unified diff.

    Only lines that start with ``+`` or ``-`` (but not ``+++`` / ``---`` header
    lines) are counted.

    Args:
        diff_text: Unified diff text (e.g. output of ``git diff``).

    Returns:
        Total count of added + removed lines.
    """
    return len(_DIFF_LINE_RE.findall(diff_text))


def detect_rubber_stamp(
    verdict: str,
    diff_text: str,
    high_count: int,
    medium_count: int,
    diff_line_threshold: int = 50,
) -> list[CargoFinding]:
    """Detect the rubber-stamp pattern: PASS + big diff + zero HIGH/MEDIUM findings.

    Args:
        verdict: Auditor verdict string (e.g. ``"PASS"``, ``"OPEN"``).
        diff_text: Full unified diff for the cycle.
        high_count: Number of HIGH findings in the issue file.
        medium_count: Number of MEDIUM findings in the issue file.
        diff_line_threshold: Minimum diff-line count to trigger the check.
            Default 50 (per spec §Mechanism step 3).

    Returns:
        A list with zero or one MEDIUM ``CargoFinding``.
    """
    if verdict.upper() != "PASS":
        return []
    if high_count > 0 or medium_count > 0:
        return []

    diff_lines = count_diff_lines(diff_text)
    if diff_lines <= diff_line_threshold:
        return []

    return [
        CargoFinding(
            severity="MEDIUM",
            message=(
                f"Auditor verdict PASS with substantial diff ({diff_lines} lines) "
                f"and no findings — verify reasoning on critical sweep."
            ),
            detector="rubber_stamp",
        )
    ]


# ---------------------------------------------------------------------------
# Convenience: run all three detectors at once
# ---------------------------------------------------------------------------


def run_all_detectors(
    spec_carry_over_text: str,
    diff_text: str,
    current_issue_text: str,
    prior_issue_text: str | None,
    verdict: str,
    high_count: int,
    medium_count: int,
    loop_threshold: float | None = None,
) -> list[CargoFinding]:
    """Run all three anti-cargo-cult detectors and return combined findings.

    Args:
        spec_carry_over_text: Text of the spec's carry-over section.
        diff_text: Full unified diff for the current cycle.
        current_issue_text: Text of the current cycle's issue file.
        prior_issue_text: Text of the previous cycle's issue file, or ``None`` if
            this is cycle 1.
        verdict: Auditor verdict (``"PASS"`` / ``"OPEN"`` / ``"BLOCKED"``).
        high_count: Number of HIGH findings in the current issue file.
        medium_count: Number of MEDIUM findings in the current issue file.
        loop_threshold: Override for cycle-overlap threshold.  ``None`` uses the
            env-var / default.

    Returns:
        Combined list of all ``CargoFinding`` entries from all three detectors.
    """
    findings: list[CargoFinding] = []

    findings.extend(detect_checkbox_without_diff(spec_carry_over_text, diff_text))

    if prior_issue_text:
        current_titles = extract_finding_titles(current_issue_text)
        prior_titles = extract_finding_titles(prior_issue_text)
        findings.extend(
            detect_cycle_overlap(current_titles, prior_titles, threshold=loop_threshold)
        )

    findings.extend(
        detect_rubber_stamp(verdict, diff_text, high_count, medium_count)
    )

    return findings
