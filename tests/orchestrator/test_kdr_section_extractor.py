"""KDR-section extraction tests — citation parser and compact-pointer builder.

Task: M20 Task 02 — Sub-agent input prune (orchestrator-side scope discipline).

This module verifies the KDR-citation parsing logic and the compact-pointer builder
used when constructing Auditor spawn prompts. The key invariant: the Auditor receives
only the *identifiers* of cited KDRs (a compact pointer to read §9 on-demand), not
the full §9 table inlined.

Per-AC coverage:
  AC-4 — ``test_kdr_section_extractor.py`` passes with positive + edge cases.
"""

from __future__ import annotations

from tests.orchestrator._helpers import (
    build_kdr_compact_pointer,
    extract_cited_kdrs,
    extract_kdr_sections,
)

# ---------------------------------------------------------------------------
# Fixtures: synthetic spec text and architecture.md §9 excerpt
# ---------------------------------------------------------------------------

# A realistic task spec excerpt citing two KDRs in the Grounding line
_SPEC_WITH_TWO_KDRS = """\
# Task 01 — Auditor TierConfigs

**Status:** ✅ Complete.
**Grounding:** [architecture.md §9 KDR-003 / KDR-011](../../architecture.md)

## What to Build

Register two new TierConfig entries: `auditor-sonnet` and `auditor-opus`.
These satisfy KDR-003 (no Anthropic API; OAuth CLI path only) and KDR-011 (tiered audit cascade).
"""

# A spec citing no KDRs
_SPEC_WITH_NO_KDRS = """\
# Task 00 — Scaffold Setup

**Status:** ✅ Complete.

## What to Build

Create the project directory structure. No LLM nodes involved.
"""

# A spec citing one KDR with an unnormalised numeric suffix (single digit)
_SPEC_WITH_SINGLE_DIGIT_KDR = """\
# Task ZZ — Something Simple

Relates to KDR-4 (validator pairing) and grounding in architecture.md §9.
"""

# A spec citing many KDRs including duplicates
_SPEC_WITH_DUPLICATE_KDRS = """\
# Task N — Complex

Needs KDR-002, KDR-003, KDR-013 per the spec.
Also check: KDR-002 again (mentioned twice), KDR-003 (mentioned again).
"""

# Minimal synthetic architecture.md §9 table excerpt
_ARCH_MD_SECTION_9 = """\
## 9. Key design decisions

Referenced by short ID from future specs, tasks, and commits.

| ID | Decision | Source |
| --- | --- | --- |
| KDR-001 | LangGraph replaces hand-rolled DAG orchestrator. | analysis § B |
| KDR-002 | MCP server is the portable inside-out surface. | analysis § C |
| KDR-003 | No Anthropic API. Gemini + Qwen runtime; Claude Code CLI via OAuth. | memory |
| KDR-004 | Validator-node-after-every-LLM-node is mandatory. | analysis § E |
| KDR-006 | Three-bucket retry taxonomy at the TieredNode boundary. | §8.2 |
| KDR-009 | LangGraph SqliteSaver owns checkpoint persistence. | §4.1, §4.2 |
| KDR-011 | Tiered audit cascade. | ADR-0004, §4.2, §4.4 |
| KDR-013 | External workflow module discovery. | ADR-0007, §4.2 |
"""


# ---------------------------------------------------------------------------
# extract_cited_kdrs — positive cases
# ---------------------------------------------------------------------------

class TestExtractCitedKdrs:
    """Tests for :func:`extract_cited_kdrs`."""

    def test_two_kdrs_extracted_correctly(self) -> None:
        """Spec citing KDR-003 and KDR-011 → both extracted."""
        result = extract_cited_kdrs(_SPEC_WITH_TWO_KDRS)
        assert result == ["KDR-003", "KDR-011"]

    def test_no_kdrs_returns_empty_list(self) -> None:
        """Spec with no KDR citations → empty list."""
        result = extract_cited_kdrs(_SPEC_WITH_NO_KDRS)
        assert result == []

    def test_single_digit_kdr_normalised(self) -> None:
        """KDR-4 (single digit) is normalised to KDR-004."""
        result = extract_cited_kdrs(_SPEC_WITH_SINGLE_DIGIT_KDR)
        assert result == ["KDR-004"]

    def test_duplicate_kdrs_deduplicated(self) -> None:
        """KDR-002 and KDR-003 mentioned twice each → deduplicated."""
        result = extract_cited_kdrs(_SPEC_WITH_DUPLICATE_KDRS)
        assert result == ["KDR-002", "KDR-003", "KDR-013"]

    def test_result_is_sorted(self) -> None:
        """Extracted KDR identifiers are sorted."""
        spec = "References KDR-013 first, then KDR-003, then KDR-006."
        result = extract_cited_kdrs(spec)
        assert result == sorted(result)

    def test_empty_string_returns_empty(self) -> None:
        """Empty string → empty list."""
        assert extract_cited_kdrs("") == []

    def test_kdr_in_code_block_extracted(self) -> None:
        """KDR citation inside a code block is still extracted."""
        spec = "```\n# satisfies KDR-009\n```"
        result = extract_cited_kdrs(spec)
        assert "KDR-009" in result

    def test_not_matched_on_partial_word(self) -> None:
        """'KDR-' followed by non-digit is not matched."""
        spec = "See KDR-ABC for details."
        result = extract_cited_kdrs(spec)
        assert result == []


# ---------------------------------------------------------------------------
# build_kdr_compact_pointer — positive + edge cases
# ---------------------------------------------------------------------------

class TestBuildKdrCompactPointer:
    """Tests for :func:`build_kdr_compact_pointer`."""

    def test_two_kdrs_compact_pointer(self) -> None:
        """Two cited KDRs → compact one-liner with both IDs."""
        result = build_kdr_compact_pointer(["KDR-003", "KDR-011"])
        assert "KDR-003" in result
        assert "KDR-011" in result
        assert "read §9 of design_docs/architecture.md on-demand" in result

    def test_no_kdrs_yields_grid_header(self) -> None:
        """No cited KDRs → §9 grid header only (compact pointer)."""
        result = build_kdr_compact_pointer([])
        assert "| ID | Decision | Source |" in result
        assert "read §9 of design_docs/architecture.md on-demand" in result

    def test_single_kdr_compact_pointer(self) -> None:
        """Single cited KDR → compact one-liner."""
        result = build_kdr_compact_pointer(["KDR-003"])
        assert "KDR-003" in result
        assert "read §9" in result

    def test_compact_pointer_is_short(self) -> None:
        """Compact pointer is much shorter than a full §9 table inline.

        A full §9 table has ~14 rows × ~100 chars each = ~1400 chars.
        The compact pointer for 2 KDRs should be well under 200 chars.
        """
        result = build_kdr_compact_pointer(["KDR-003", "KDR-011"])
        # One-liner with two IDs + instructions should be well under 200 chars
        assert len(result) < 200, (
            f"Compact pointer is longer than expected ({len(result)} chars): {result!r}"
        )


# ---------------------------------------------------------------------------
# extract_kdr_sections — positive + edge cases
# ---------------------------------------------------------------------------

class TestExtractKdrSections:
    """Tests for :func:`extract_kdr_sections`."""

    def test_cited_kdrs_extracted_from_table(self) -> None:
        """Citing KDR-003 and KDR-011 → only those two rows returned."""
        result = extract_kdr_sections(_ARCH_MD_SECTION_9, ["KDR-003", "KDR-011"])
        assert "KDR-003" in result
        assert "KDR-011" in result
        # Non-cited KDRs should NOT appear as table rows (header "ID" column is OK)
        # We verify specific non-cited rows are absent
        assert "No Anthropic API" in result   # KDR-003 text
        assert "Tiered audit cascade" in result  # KDR-011 text
        # KDR-001 text should not appear
        assert "LangGraph replaces hand-rolled DAG" not in result

    def test_no_kdrs_yields_compact_pointer(self) -> None:
        """No cited KDRs → §9 grid header / compact pointer returned."""
        result = extract_kdr_sections(_ARCH_MD_SECTION_9, [])
        assert "| ID | Decision | Source |" in result
        # Actual KDR rows should not be present
        assert "No Anthropic API" not in result

    def test_cited_kdr_not_in_table_returns_compact_pointer(self) -> None:
        """Cited KDR not in the table → compact pointer (graceful fallback)."""
        result = extract_kdr_sections(_ARCH_MD_SECTION_9, ["KDR-099"])
        # KDR-099 doesn't exist in the table; should get compact pointer
        assert "read §9 of design_docs/architecture.md on-demand" in result

    def test_header_always_present_when_rows_match(self) -> None:
        """When rows match, the table header is always included."""
        result = extract_kdr_sections(_ARCH_MD_SECTION_9, ["KDR-003"])
        assert "| ID | Decision | Source |" in result
        assert "| --- | --- | --- |" in result

    def test_extracted_content_much_smaller_than_full_section(self) -> None:
        """Extracted sections for 2 KDRs is significantly smaller than full §9 content.

        This is the core invariant: the KDR pre-load rule saves tokens by
        extracting only what's cited rather than inlining the full §9 table.
        """
        full_size = len(_ARCH_MD_SECTION_9)
        extracted = extract_kdr_sections(_ARCH_MD_SECTION_9, ["KDR-003", "KDR-011"])
        extracted_size = len(extracted)

        # Extracted (2 rows) should be much smaller than the full table (8 rows + header)
        assert extracted_size < full_size * 0.5, (
            f"Extracted sections ({extracted_size} chars) should be < 50% of "
            f"full §9 ({full_size} chars). KDR extraction is not saving enough."
        )

    def test_unnormalised_kdr_id_still_produces_rows(self) -> None:
        """Passing unnormalised IDs directly to extract_kdr_sections still matches rows.

        ``extract_kdr_sections`` normalises caller-supplied IDs internally, so
        callers who skip ``extract_cited_kdrs`` (which pre-normalises) do not
        get a silent empty result.

        Regression guard for the normalisation added in cycle 2 (FIX-SDET-3).
        """
        # Pass the short-form "KDR-3" (no zero-padding) directly, bypassing
        # extract_cited_kdrs(), which would have normalised it to "KDR-003".
        result = extract_kdr_sections(_ARCH_MD_SECTION_9, ["KDR-3"])

        # The KDR-003 row (No Anthropic API) must appear — normalisation fixed the mismatch.
        assert "No Anthropic API" in result, (
            "extract_kdr_sections should normalise 'KDR-3' to 'KDR-003' and "
            f"return the matching row. Got: {result!r}"
        )
        assert "KDR-003" in result


# ---------------------------------------------------------------------------
# Integration: extract_cited_kdrs → build_kdr_compact_pointer (end-to-end)
# ---------------------------------------------------------------------------

class TestKdrExtractionPipeline:
    """End-to-end tests of the extract → build_pointer pipeline."""

    def test_spec_citing_two_kdrs_end_to_end(self) -> None:
        """Full pipeline: spec text → cited list → compact pointer."""
        cited = extract_cited_kdrs(_SPEC_WITH_TWO_KDRS)
        pointer = build_kdr_compact_pointer(cited)

        # Cited list is correct
        assert cited == ["KDR-003", "KDR-011"]

        # Compact pointer is short and names the cited KDRs
        assert "KDR-003" in pointer
        assert "KDR-011" in pointer
        assert "read §9" in pointer

    def test_spec_with_no_kdrs_end_to_end(self) -> None:
        """Full pipeline: spec with no KDRs → empty list → grid header."""
        cited = extract_cited_kdrs(_SPEC_WITH_NO_KDRS)
        pointer = build_kdr_compact_pointer(cited)

        assert cited == []
        assert "| ID | Decision | Source |" in pointer
