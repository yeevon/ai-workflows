"""Tests for the Auditor anti-cargo-cult detection logic.

Task: M20 Task 20 — Carry-over checkbox-cargo-cult catch (extended detection).
Relationship: Exercises ``scripts/orchestration/cargo_cult_detector.py`` and
  validates the structural claims in ``.claude/agents/auditor.md`` Phase 4.

Three detectors under test:

1. ``detect_checkbox_without_diff`` — HIGH when a carry-over ``[x]`` has no
   corresponding diff hunk.
2. ``detect_cycle_overlap`` — MEDIUM when ≥ 50% of cycle-N finding titles
   score > threshold against cycle-(N-1) titles.
3. ``detect_rubber_stamp`` — MEDIUM when verdict is PASS + diff > 50 lines
   + zero HIGH/MEDIUM findings.

Per-AC coverage:
  AC-1  — Phase 4 extensions land in auditor.md (structural grep test).
  AC-2  — M12-T01 carry-over checkbox paragraph present in auditor.md.
  AC-3  — Each detection emits the correct severity (HIGH / MEDIUM).
  AC-4  — True-positive + true-negative for each of the three detectors.
  AC-5  — CHANGELOG entry is present.
  AC-6  — Status surfaces (checked separately at spec/README level).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Import helpers from the detector module under test
# ---------------------------------------------------------------------------

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.orchestration.cargo_cult_detector import (
    DEFAULT_LOOP_DETECTION_THRESHOLD,
    count_diff_lines,
    detect_checkbox_without_diff,
    detect_cycle_overlap,
    detect_rubber_stamp,
    extract_finding_titles,
    get_loop_detection_threshold,
    run_all_detectors,
)

# ---------------------------------------------------------------------------
# Paths to live agent files for structural checks
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).parent.parent.parent
_AUDITOR_MD = _REPO_ROOT / ".claude" / "agents" / "auditor.md"
_CHANGELOG_MD = _REPO_ROOT / "CHANGELOG.md"

# ---------------------------------------------------------------------------
# AC-1 + AC-2: structural grep tests against auditor.md
# ---------------------------------------------------------------------------


def _phase4_block(text: str) -> str:
    """Return the text slice between '## Phase 4' and the next '## Phase' heading."""
    try:
        start = text.index("## Phase 4")
    except ValueError:
        pytest.fail("auditor.md has no '## Phase 4' heading")
    try:
        end = text.index("## Phase", start + 1)
    except ValueError:
        end = len(text)
    return text[start:end]


def test_auditor_phase4_has_cycle_overlap_extension() -> None:
    """Phase 4 in auditor.md contains cycle-N overlap detection language."""
    text = _AUDITOR_MD.read_text()
    phase4 = _phase4_block(text)
    assert "cycle" in phase4.lower() and "overlap" in phase4.lower(), (
        "Phase 4 must contain cycle-N overlap detection language"
    )


def test_auditor_phase4_has_rubber_stamp_detection() -> None:
    """Phase 4 in auditor.md contains rubber-stamp detection language."""
    text = _AUDITOR_MD.read_text()
    phase4 = _phase4_block(text)
    assert "rubber-stamp" in phase4.lower(), (
        "Phase 4 must contain rubber-stamp detection language"
    )


def test_auditor_md_has_carry_over_cargo_cult_paragraph() -> None:
    """auditor.md contains the M12-T01 carry-over checkbox-cargo-cult patch."""
    text = _AUDITOR_MD.read_text()
    assert "Carry-over checkbox-cargo-cult" in text, (
        "auditor.md must contain the 'Carry-over checkbox-cargo-cult' paragraph "
        "(M12-T01 patch)"
    )


def test_auditor_no_new_phase_numbering() -> None:
    """auditor.md must not introduce a Phase 4.5, Phase 7, or Phase 8."""
    text = _AUDITOR_MD.read_text()
    for forbidden in ("Phase 4.5", "Phase 7", "Phase 8"):
        assert forbidden not in text, (
            f"auditor.md must not introduce {forbidden!r} (per audit M14)"
        )


# ---------------------------------------------------------------------------
# AC-5: CHANGELOG entry
# ---------------------------------------------------------------------------


def test_changelog_has_m20_task20_entry() -> None:
    """CHANGELOG.md has the M20 Task 20 Changed entry."""
    text = _CHANGELOG_MD.read_text()
    assert "M20 Task 20" in text, (
        "CHANGELOG.md must have a 'M20 Task 20' entry under [Unreleased]"
    )
    assert "anti-cargo-cult" in text.lower() or "cargo-cult" in text.lower(), (
        "CHANGELOG entry must mention cargo-cult inspections"
    )


# ---------------------------------------------------------------------------
# Detector helpers — unit tests
# ---------------------------------------------------------------------------


def test_get_loop_detection_threshold_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """Default threshold is 0.70 when env-var is unset."""
    monkeypatch.delenv("AIW_LOOP_DETECTION_THRESHOLD", raising=False)
    result = get_loop_detection_threshold()
    assert result == DEFAULT_LOOP_DETECTION_THRESHOLD


def test_get_loop_detection_threshold_env_var_honored(monkeypatch: pytest.MonkeyPatch) -> None:
    """AIW_LOOP_DETECTION_THRESHOLD env-var overrides the default."""
    monkeypatch.setenv("AIW_LOOP_DETECTION_THRESHOLD", "0.85")
    assert get_loop_detection_threshold() == pytest.approx(0.85)


def test_get_loop_detection_threshold_invalid_env_var_falls_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Invalid env-var value falls back to default."""
    monkeypatch.setenv("AIW_LOOP_DETECTION_THRESHOLD", "not-a-float")
    assert get_loop_detection_threshold() == DEFAULT_LOOP_DETECTION_THRESHOLD


def test_count_diff_lines_typical() -> None:
    """count_diff_lines counts added/removed lines but not diff headers."""
    diff = (
        "diff --git a/foo.py b/foo.py\n"
        "--- a/foo.py\n"
        "+++ b/foo.py\n"
        "@@ -1,3 +1,4 @@\n"
        " unchanged\n"
        "-removed line\n"
        "+added line 1\n"
        "+added line 2\n"
    )
    assert count_diff_lines(diff) == 3


def test_count_diff_lines_empty() -> None:
    """Empty diff has zero diff lines."""
    assert count_diff_lines("") == 0


def test_extract_finding_titles_standard_format() -> None:
    """extract_finding_titles parses standard HIGH/MEDIUM/LOW headers."""
    issue_text = (
        "## 🔴 HIGH — Gate failed on pytest\n\n"
        "Some detail.\n\n"
        "## 🟡 MEDIUM — Missing docstring on public function\n\n"
        "More detail.\n\n"
        "## 🟢 LOW — Cosmetic whitespace\n"
    )
    titles = extract_finding_titles(issue_text)
    assert "Gate failed on pytest" in titles
    assert "Missing docstring on public function" in titles
    assert "Cosmetic whitespace" in titles


def test_extract_finding_titles_empty_issue_file() -> None:
    """extract_finding_titles returns empty list for PASS issue file with no findings."""
    issue_text = (
        "# Task 20 — Title — Audit Issues\n\n"
        "**Status:** PASS\n\n"
        "## AC grading\n"
        "All ACs met.\n"
    )
    assert extract_finding_titles(issue_text) == []


# ---------------------------------------------------------------------------
# Detector 1: checkbox without diff — true positives
# ---------------------------------------------------------------------------


def test_checkbox_without_diff_fires_high() -> None:
    """Ticked carry-over item without a diff hunk → HIGH finding fires."""
    carry_over = "- [x] Implement retry logic in RetryingEdge (M20-T01-ISS-03)\n"
    diff = "diff --git a/foo.py b/foo.py\n+def unrelated_function(): pass\n"

    findings = detect_checkbox_without_diff(carry_over, diff)

    assert len(findings) >= 1
    assert any(f.severity == "HIGH" for f in findings)
    assert any(f.detector == "checkbox" for f in findings)


def test_checkbox_without_diff_message_includes_item_text() -> None:
    """HIGH finding message includes (part of) the checked item text."""
    carry_over = "- [x] Add timeout to subprocess call\n"
    diff = ""

    findings = detect_checkbox_without_diff(carry_over, diff)
    assert len(findings) == 1
    assert "timeout" in findings[0].message.lower() or "subprocess" in findings[0].message.lower()


# ---------------------------------------------------------------------------
# Detector 1: checkbox without diff — true negatives (no false positives)
# ---------------------------------------------------------------------------


def test_checkbox_with_matching_diff_does_not_fire() -> None:
    """Ticked item whose keyword appears in the diff → no finding."""
    carry_over = "- [x] Add retry logic to RetryingEdge\n"
    diff = (
        "diff --git a/ai_workflows/graph/retry_edge.py b/...\n"
        "+def retry_logic(): ...\n"
    )

    findings = detect_checkbox_without_diff(carry_over, diff)
    assert findings == []


def test_unchecked_carry_over_does_not_fire() -> None:
    """Unchecked carry-over item ([ ]) does not produce a finding."""
    carry_over = "- [ ] Implement caching for TieredNode results\n"
    diff = ""

    findings = detect_checkbox_without_diff(carry_over, diff)
    assert findings == []


def test_empty_carry_over_does_not_fire() -> None:
    """Empty carry-over section → no findings."""
    findings = detect_checkbox_without_diff("", "diff text here")
    assert findings == []


# ---------------------------------------------------------------------------
# Detector 2: cycle overlap — true positives
# ---------------------------------------------------------------------------


def test_cycle_overlap_80_percent_fires_medium() -> None:
    """80% similar titles → MEDIUM 'loop may be spinning' finding fires."""
    current = [
        "Missing docstring on TieredNode",
        "RetryingEdge does not handle timeout",
        "ValidatorNode schema not enforced",
        "Gate fails on lint-imports",
        "CHANGELOG entry missing",
    ]
    # Prior cycle titles are almost identical (mirroring 80%)
    prior = [
        "Missing docstring on TieredNode",           # identical → ratio 1.0
        "RetryingEdge does not handle timeout",       # identical → ratio 1.0
        "ValidatorNode schema not enforced",          # identical → ratio 1.0
        "Gate fails on lint-imports",                 # identical → ratio 1.0
        "Completely different unrelated finding",     # low ratio
    ]

    findings = detect_cycle_overlap(current, prior, threshold=0.70)

    assert len(findings) == 1
    assert findings[0].severity == "MEDIUM"
    assert "loop may be spinning" in findings[0].message
    assert findings[0].detector == "cycle_overlap"


def test_cycle_overlap_uses_env_threshold(monkeypatch: pytest.MonkeyPatch) -> None:
    """Overlap detection honours AIW_LOOP_DETECTION_THRESHOLD env-var."""
    current = [
        "Gate fails on pytest",
        "Missing CHANGELOG entry",
    ]
    # 50% identical titles — fires at threshold 0.40
    prior = [
        "Gate fails on pytest",    # identical → 1.0
        "Completely different",    # low
    ]

    monkeypatch.setenv("AIW_LOOP_DETECTION_THRESHOLD", "0.40")
    findings_low_thresh = detect_cycle_overlap(current, prior)

    # With threshold=0.40, the identical title scores 1.0 > 0.40 → 50% overlap
    # → fires (50% ≥ 50%)
    assert len(findings_low_thresh) == 1

    # With threshold=0.95, the identical title (1.0 > 0.95 → 50% overlap) still
    # fires at 50% because even 1/2 = 50% meets the ≥ 50% criterion.
    # Use an explicit high threshold that requires >50% of titles to overlap.
    three_current = ["Gate fails on pytest", "Missing CHANGELOG", "Novel finding X"]
    three_prior = ["Gate fails on pytest", "Some old finding", "Another old finding"]
    findings_high_thresh = detect_cycle_overlap(three_current, three_prior, threshold=0.95)
    # Only 1/3 = 33% overlap at threshold 0.95 → should NOT fire
    assert findings_high_thresh == []


# ---------------------------------------------------------------------------
# Detector 2: cycle overlap — true negatives
# ---------------------------------------------------------------------------


def test_cycle_overlap_novel_findings_no_false_positive() -> None:
    """Novel findings with < 50% overlap → no false positive."""
    current = [
        "New issue with cache invalidation in SqliteSaver",
        "Missing smoke test for declarative workflow dispatch",
        "ValidatorNode not paired with TieredNode in new graph",
    ]
    prior = [
        "RetryingEdge timeout handling missing",
        "CHANGELOG entry not updated for M20 T01",
    ]

    findings = detect_cycle_overlap(current, prior, threshold=0.70)
    assert findings == []


def test_cycle_overlap_empty_current_no_finding() -> None:
    """Empty current-cycle titles (PASS with no findings) → no overlap finding."""
    findings = detect_cycle_overlap([], ["some prior finding"], threshold=0.70)
    assert findings == []


def test_cycle_overlap_no_prior_no_finding() -> None:
    """No prior-cycle titles (cycle 1) → no overlap finding."""
    findings = detect_cycle_overlap(["Gate fails"], [], threshold=0.70)
    assert findings == []


# ---------------------------------------------------------------------------
# Detector 3: rubber stamp — true positives
# ---------------------------------------------------------------------------

_BIG_DIFF = (
    "diff --git a/foo.py b/foo.py\n"
    "--- a/foo.py\n"
    "+++ b/foo.py\n"
    "@@ -1,60 +1,60 @@\n"
    + "".join(f"-old line {i}\n+new line {i}\n" for i in range(1, 56))
)


def test_rubber_stamp_pass_big_diff_no_findings_fires_medium() -> None:
    """PASS + 100-line diff + zero findings → MEDIUM 'verify reasoning' fires."""
    findings = detect_rubber_stamp(
        verdict="PASS",
        diff_text=_BIG_DIFF,
        high_count=0,
        medium_count=0,
    )

    assert len(findings) == 1
    assert findings[0].severity == "MEDIUM"
    assert "verify reasoning" in findings[0].message
    assert findings[0].detector == "rubber_stamp"


def test_rubber_stamp_uses_existing_medium_tier_not_advisory() -> None:
    """Rubber-stamp finding severity is MEDIUM (not a new ADVISORY tier)."""
    findings = detect_rubber_stamp(
        verdict="PASS",
        diff_text=_BIG_DIFF,
        high_count=0,
        medium_count=0,
    )

    assert findings[0].severity == "MEDIUM"
    assert "ADVISORY" not in findings[0].severity


# ---------------------------------------------------------------------------
# Detector 3: rubber stamp — true negatives
# ---------------------------------------------------------------------------


def test_rubber_stamp_open_verdict_does_not_fire() -> None:
    """OPEN verdict with big diff and no findings → no rubber-stamp finding."""
    findings = detect_rubber_stamp(
        verdict="OPEN",
        diff_text=_BIG_DIFF,
        high_count=0,
        medium_count=0,
    )
    assert findings == []


def test_rubber_stamp_pass_with_high_finding_does_not_fire() -> None:
    """PASS with a HIGH finding → no rubber-stamp (findings are present)."""
    findings = detect_rubber_stamp(
        verdict="PASS",
        diff_text=_BIG_DIFF,
        high_count=1,
        medium_count=0,
    )
    assert findings == []


def test_rubber_stamp_pass_with_medium_finding_does_not_fire() -> None:
    """PASS with a MEDIUM finding → no rubber-stamp (findings are present)."""
    findings = detect_rubber_stamp(
        verdict="PASS",
        diff_text=_BIG_DIFF,
        high_count=0,
        medium_count=1,
    )
    assert findings == []


def test_rubber_stamp_small_diff_does_not_fire() -> None:
    """PASS + small diff (≤ 50 lines) + no findings → no rubber-stamp."""
    small_diff = (
        "diff --git a/foo.py b/foo.py\n"
        "+added one line\n"
        "-removed one line\n"
    )
    findings = detect_rubber_stamp(
        verdict="PASS",
        diff_text=small_diff,
        high_count=0,
        medium_count=0,
    )
    assert findings == []


def test_rubber_stamp_legitimate_clean_code_no_false_positive() -> None:
    """Genuinely clean code with low diff → no false positive."""
    tiny_diff = "diff --git a/CHANGELOG.md b/CHANGELOG.md\n+### Added — M20 T20\n"
    findings = detect_rubber_stamp(
        verdict="PASS",
        diff_text=tiny_diff,
        high_count=0,
        medium_count=0,
    )
    assert findings == []


# ---------------------------------------------------------------------------
# Detector 3: rubber stamp — boundary tests (F-2 fix)
# ---------------------------------------------------------------------------

# Build a diff with exactly N added/removed lines (no +++ / --- headers that
# would be excluded by count_diff_lines).
def _make_diff_with_n_lines(n: int) -> str:
    """Return a minimal unified diff string with exactly n added lines."""
    lines = ["diff --git a/foo.py b/foo.py\n"]
    for i in range(n):
        lines.append(f"+added line {i}\n")
    return "".join(lines)


def test_rubber_stamp_50_lines_does_not_fire() -> None:
    """Exactly 50 diff lines must NOT fire (threshold is 'exceeds 50')."""
    diff_50 = _make_diff_with_n_lines(50)
    findings = detect_rubber_stamp(
        verdict="PASS",
        diff_text=diff_50,
        high_count=0,
        medium_count=0,
    )
    assert findings == [], (
        "detect_rubber_stamp must not fire when diff_lines == 50 "
        "(fires only when diff_lines > 50)"
    )


def test_rubber_stamp_51_lines_fires() -> None:
    """Exactly 51 diff lines MUST fire a MEDIUM finding."""
    diff_51 = _make_diff_with_n_lines(51)
    findings = detect_rubber_stamp(
        verdict="PASS",
        diff_text=diff_51,
        high_count=0,
        medium_count=0,
    )
    assert len(findings) == 1, (
        "detect_rubber_stamp must fire exactly once when diff_lines == 51"
    )
    assert findings[0].severity == "MEDIUM"


# ---------------------------------------------------------------------------
# run_all_detectors integration test
# ---------------------------------------------------------------------------


def test_run_all_detectors_combines_findings() -> None:
    """run_all_detectors returns combined findings from all three detectors."""
    carry_over = "- [x] Add retry logic to RetryingEdge\n"
    diff = ""  # no diff → checkbox fires
    current_issue = ""  # no current findings → no cycle overlap
    prior_issue = ""

    # PASS + no diff → rubber-stamp does not fire (diff too small)
    # Checkbox fires HIGH because diff is empty
    findings = run_all_detectors(
        spec_carry_over_text=carry_over,
        diff_text=diff,
        current_issue_text=current_issue,
        prior_issue_text=prior_issue,
        verdict="PASS",
        high_count=0,
        medium_count=0,
    )

    severities = {f.severity for f in findings}
    detectors = {f.detector for f in findings}
    assert "HIGH" in severities
    assert "checkbox" in detectors


def test_run_all_detectors_no_prior_issue_skips_cycle_overlap() -> None:
    """When prior_issue_text is None, cycle-overlap detector is skipped."""
    findings = run_all_detectors(
        spec_carry_over_text="",
        diff_text="",
        current_issue_text="## 🔴 HIGH — Some finding\n",
        prior_issue_text=None,  # cycle 1
        verdict="OPEN",
        high_count=1,
        medium_count=0,
    )
    # No checkbox or rubber-stamp or cycle-overlap findings expected
    assert all(f.detector != "cycle_overlap" for f in findings)


def test_run_all_detectors_all_clear() -> None:
    """Clean cycle (matched checkboxes, novel findings, small diff) → no findings."""
    carry_over = "- [ ] Future work item\n"  # unchecked
    diff = "+one line added\n"
    findings = run_all_detectors(
        spec_carry_over_text=carry_over,
        diff_text=diff,
        current_issue_text="",
        prior_issue_text="",
        verdict="OPEN",
        high_count=1,
        medium_count=0,
    )
    assert findings == []
