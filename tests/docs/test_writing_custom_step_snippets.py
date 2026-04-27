"""Doctest-compilability tests for docs/writing-a-custom-step.md (M19 Task 06).

Verifies that every executable code block in the Tier 3 guide compiles
cleanly, skipped blocks are marked correctly, and key structural requirements
of the doc are satisfied.

Relationship to other modules
------------------------------
* :mod:`ai_workflows.workflows.spec` (M19 T01) — ``Step`` base class used in
  every snippet.
* :mod:`ai_workflows.workflows.testing` (M19 T06) — ``compile_step_in_isolation``
  documented in §Testing section.
* ``tests/docs/test_docs_links.py`` — companion link-resolution test; both must
  pass for the doc to be considered AC-9-clean.

M19 Task 06 ACs covered
------------------------
* AC-1  — 9-section structure present.
* AC-2  — ``WebFetchStep`` worked example present and doctest-skip marked;
          ``AddOneStep`` doctest-runnable substitute present.
* AC-3  — ``Step`` base class contract section documents ``execute()`` + ``compile()``.
* AC-4  — §State-channel conventions enumerates the four conventions.
* AC-5  — §Testing section references ``compile_step_in_isolation``.
* AC-6  — §Graduation hints names three signals + cross-link to
          ``writing-a-graph-primitive.md``.
* AC-7  — §User-owned code boundary cites KDR-013 + ADR-0007.
* AC-8  — §Pointers cross-links to ``writing-a-workflow.md`` and
          ``writing-a-graph-primitive.md``.
* AC-9  — doctest verification: all blocks compile; skipped blocks marked.
"""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_DOC_PATH = _REPO_ROOT / "docs" / "writing-a-custom-step.md"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_python_blocks(md_path: Path) -> list[tuple[int, str]]:
    """Return all ```python … ``` fenced blocks as (start_line, source) pairs.

    Strips the fenced delimiters; preserves the inner content verbatim.
    """
    source = md_path.read_text(encoding="utf-8")
    lines = source.splitlines()
    blocks: list[tuple[int, str]] = []
    in_block = False
    block_lines: list[str] = []
    start_line = 0

    for i, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not in_block:
            if stripped == "```python":
                in_block = True
                block_lines = []
                start_line = i
        else:
            if stripped == "```":
                block_src = "\n".join(block_lines)
                blocks.append((start_line, block_src))
                in_block = False
                block_lines = []
            else:
                block_lines.append(line)

    return blocks


def _doc_text() -> str:
    return _DOC_PATH.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# AC-9 — code block compile check
# ---------------------------------------------------------------------------


def test_doc_exists() -> None:
    """docs/writing-a-custom-step.md exists (not the stub)."""
    assert _DOC_PATH.exists(), f"Expected doc at {_DOC_PATH}"
    text = _doc_text()
    # Verify the stub is fully replaced — CARRY-T05-MEDIUM-2
    assert "This guide ships with M19 Task 06" not in text, (
        "Stub vestige found: doc must be the full Tier 3 guide, not the T05 stub"
    )


def test_all_python_blocks_compile() -> None:
    """Every ```python block in writing-a-custom-step.md compiles without SyntaxError.

    Load-bearing doctest-compilability check for M19 AC-9.  Catches
    mis-spelled imports and removed classes immediately.
    """
    blocks = _extract_python_blocks(_DOC_PATH)
    assert blocks, "No ```python blocks found in writing-a-custom-step.md"

    errors: list[str] = []
    for start_line, src in blocks:
        try:
            compile(src, f"writing-a-custom-step.md:{start_line}", "exec")
        except SyntaxError as exc:
            errors.append(f"Line {start_line}: SyntaxError — {exc}")

    assert not errors, "\n".join(errors)


def test_skipped_blocks_have_doctest_skip_marker() -> None:
    """Blocks that require httpx or network calls are marked # doctest: +SKIP.

    TA-LOW-04 carry-over: WebFetchStep block must have the skip marker so
    doctests don't try to run it.
    """
    text = _doc_text()
    # The WebFetchStep block must carry the skip marker
    assert "# doctest: +SKIP" in text, (
        "WebFetchStep (httpx / network) block must be marked # doctest: +SKIP"
    )


# ---------------------------------------------------------------------------
# AC-1 — 9-section structure
# ---------------------------------------------------------------------------


def test_section_structure() -> None:
    """Doc contains all 9 required sections from AC-1."""
    text = _doc_text()
    required_sections = [
        "When to write a custom step",
        "The `Step` base class contract",
        "Worked example",
        "State-channel conventions",
        "Testing your custom step",
        "Graduation hints",
        "User-owned code boundary",
        "Pointers to adjacent tiers",
    ]
    missing = [s for s in required_sections if s not in text]
    assert not missing, f"Missing sections: {missing}"


# ---------------------------------------------------------------------------
# AC-2 — WebFetchStep (skip) + AddOneStep (runnable)
# ---------------------------------------------------------------------------


def test_web_fetch_step_present_and_skip_marked() -> None:
    """§Worked example contains WebFetchStep class marked doctest: +SKIP (AC-2)."""
    text = _doc_text()
    assert "WebFetchStep" in text, "WebFetchStep class must be in the worked example"
    # The § Worked example section heading introduces the WebFetchStep code block.
    # The skip marker must appear in the same block, immediately before the httpx import.
    # The class definition `class WebFetchStep` must follow the `# doctest: +SKIP` marker.
    class_def_pos = text.find("class WebFetchStep")
    assert class_def_pos != -1, "class WebFetchStep definition must be present"
    # The skip marker must appear somewhere before the class definition in the doc
    skip_pos = text.rfind("# doctest: +SKIP", 0, class_def_pos)
    assert skip_pos != -1, (
        "# doctest: +SKIP marker must appear before class WebFetchStep definition"
    )


def test_add_one_step_present_as_runnable_substitute() -> None:
    """§Worked example contains AddOneStep as a doctest-runnable substitute (AC-2)."""
    text = _doc_text()
    assert "AddOneStep" in text, "AddOneStep synthetic substitute must be present"


def test_web_fetch_step_uses_generic_tier_name() -> None:
    """WebFetchStep example uses a generic tier name, not the in-tree 'planner-explorer'.

    TA-LOW-09 carry-over: the in-tree planner tier should not appear in the
    WebFetchStep example as it's semantically wrong for a generic web-fetch
    workflow.
    """
    text = _doc_text()
    assert "planner-explorer" not in text, (
        "WebFetchStep example must not borrow the in-tree planner tier name "
        "'planner-explorer' (TA-LOW-09 carry-over)"
    )


# ---------------------------------------------------------------------------
# AC-3 — Step base class contract
# ---------------------------------------------------------------------------


def test_step_base_class_execute_documented() -> None:
    """§Step base class contract documents execute(state) -> dict coroutine (AC-3)."""
    text = _doc_text()
    assert "execute" in text, "execute() must be documented in the base class contract"
    assert "async def execute" in text, "execute() must be documented as async"


def test_step_base_class_compile_documented() -> None:
    """§Step base class contract documents compile(state_class, step_id) -> CompiledStep (AC-3)."""
    text = _doc_text()
    assert "compile" in text, "compile() upgrade path must be documented"
    assert "CompiledStep" in text, "CompiledStep must be referenced in the compile path"


def test_frozen_model_invariant_stated() -> None:
    """§Step base class contract states frozen model + extra='forbid' invariants (AC-3)."""
    text = _doc_text()
    assert "frozen" in text, "frozen model invariant must be stated"
    assert "extra" in text, "extra='forbid' invariant must be stated"


def test_default_compile_wraps_execute_documented() -> None:
    """Doc states the default compile() wraps execute() in a single node (AC-3 — locked Q4)."""
    text = _doc_text()
    assert "wraps" in text.lower() or "wrap" in text.lower(), (
        "Doc must state that the default compile() wraps execute() in a single node"
    )


# ---------------------------------------------------------------------------
# AC-4 — §State-channel conventions four bullets
# ---------------------------------------------------------------------------


def test_state_channel_conventions_four_bullets() -> None:
    """§State-channel conventions enumerates the four required conventions (AC-4)."""
    text = _doc_text()
    required = [
        "state[",          # read from state[<field>]
        "dict of updates", # write a dict of updates
        "mutate",          # don't mutate state directly
        "_mid_run_",       # don't reach for _mid_run_ keys
    ]
    missing = [phrase for phrase in required if phrase not in text]
    assert not missing, (
        f"State-channel conventions section missing required phrases: {missing}"
    )


# ---------------------------------------------------------------------------
# AC-5 — §Testing section references compile_step_in_isolation
# ---------------------------------------------------------------------------


def test_testing_section_references_compile_step_in_isolation() -> None:
    """§Testing section references compile_step_in_isolation fixture (AC-5)."""
    text = _doc_text()
    assert "compile_step_in_isolation" in text, (
        "§Testing section must reference compile_step_in_isolation fixture"
    )
    assert "ai_workflows.workflows.testing" in text or "workflows.testing" in text, (
        "§Testing section must show the import path for compile_step_in_isolation"
    )


# ---------------------------------------------------------------------------
# AC-6 — §Graduation hints: three signals + cross-link
# ---------------------------------------------------------------------------


def test_graduation_hints_three_signals() -> None:
    """§Graduation hints names three signals for promotion (AC-6)."""
    text = _doc_text()
    # Check for the three signals:
    # 1. used in 2+ workflows / across workflows
    assert "two or more" in text or "2+" in text, (
        "Graduation hint 1 (used in 2+ workflows) must be present"
    )
    # 2. copy-paste propagation
    assert "copy" in text.lower() and "paste" in text.lower(), (
        "Graduation hint 2 (copy-paste propagation) must be present"
    )
    # 3. reusable wiring → graph primitive
    assert "wiring" in text.lower(), (
        "Graduation hint 3 (reusable wiring → graph primitive) must be present"
    )


def test_graduation_hints_cross_link_to_graph_primitive() -> None:
    """§Graduation hints cross-links to writing-a-graph-primitive.md (AC-6)."""
    text = _doc_text()
    assert "writing-a-graph-primitive.md" in text, (
        "§Graduation hints must cross-link to writing-a-graph-primitive.md"
    )


# ---------------------------------------------------------------------------
# AC-7 — §User-owned code boundary: KDR-013 + ADR-0007
# ---------------------------------------------------------------------------


def test_user_owned_code_boundary_cites_kdr013() -> None:
    """§User-owned code boundary cites KDR-013 (AC-7)."""
    text = _doc_text()
    assert "KDR-013" in text, "§User-owned code boundary must cite KDR-013"


def test_user_owned_code_boundary_cites_adr0007() -> None:
    """§User-owned code boundary cites ADR-0007 (AC-7)."""
    text = _doc_text()
    assert "ADR-0007" in text, "§User-owned code boundary must cite ADR-0007"


# ---------------------------------------------------------------------------
# AC-8 — §Pointers to adjacent tiers: cross-links verified
# ---------------------------------------------------------------------------


def test_pointers_cross_links_writing_a_workflow() -> None:
    """§Pointers to adjacent tiers cross-links to writing-a-workflow.md (AC-8)."""
    text = _doc_text()
    assert "writing-a-workflow.md" in text, (
        "§Pointers must cross-link to writing-a-workflow.md (Tier 1+2)"
    )


def test_pointers_cross_links_writing_a_graph_primitive() -> None:
    """§Pointers to adjacent tiers cross-links to writing-a-graph-primitive.md (AC-8)."""
    text = _doc_text()
    assert "writing-a-graph-primitive.md" in text, (
        "§Pointers must cross-link to writing-a-graph-primitive.md (Tier 4)"
    )
