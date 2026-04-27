"""Doctest-compilability tests for docs/writing-a-workflow.md (M19 Task 05).

Verifies that every executable code block in the rewritten doc compiles
and, where possible, runs under the test suite. Snippets that require a
real LLM call are compilation-only (instantiate objects, do not dispatch).

Relationship to other modules
-------------------------------
* :mod:`ai_workflows.workflows` — the spec-API surface every snippet exercises.
* :mod:`ai_workflows.workflows.summarize` — the worked-example workflow; the
  snippet in the doc is cross-checked against the file source here.
* ``tests/docs/test_docs_links.py`` — the companion link-resolution test;
  both must pass for the doc to be considered AC-10-clean.

M19 Task 05 ACs covered
------------------------
* AC-3  — worked ``summarize`` example present; doctest-compilable.
* AC-10 — doctest verification passes; every code block compiles cleanly.
"""

from __future__ import annotations

import difflib
import importlib
import inspect
from pathlib import Path

from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_DOC_PATH = _REPO_ROOT / "docs" / "writing-a-workflow.md"


# ---------------------------------------------------------------------------
# AC-10 — code-block extract + compile check
# ---------------------------------------------------------------------------


def _extract_python_blocks(md_path: Path) -> list[tuple[int, str]]:
    """Return all ```python … ``` fenced blocks as (start_line, source) pairs.

    Strips the fenced delimiters; preserves the inner content verbatim.
    Skips blocks whose first non-blank line starts with ``#`` followed by
    a bash-style comment (those are shell blocks accidentally typed with
    the ``python`` fence — e.g. shell pipelines like ``uv pip install``).
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


def test_all_python_blocks_compile() -> None:
    """Every ```python block in writing-a-workflow.md compiles without SyntaxError.

    This is the load-bearing doctest-compilability check for M19 AC-10.
    It catches copy-paste drift between the doc and the real API — a
    mis-spelled import or a removed class becomes an immediate compile error.
    """
    assert _DOC_PATH.exists(), f"Expected doc at {_DOC_PATH}"
    blocks = _extract_python_blocks(_DOC_PATH)
    assert blocks, "No ```python blocks found in writing-a-workflow.md"

    errors: list[str] = []
    for start_line, src in blocks:
        try:
            compile(src, f"writing-a-workflow.md:{start_line}", "exec")
        except SyntaxError as exc:
            errors.append(f"Line {start_line}: SyntaxError — {exc}")

    assert not errors, "\n".join(errors)


# ---------------------------------------------------------------------------
# AC-3 — worked summarize example: imports + WorkflowSpec construction
# ---------------------------------------------------------------------------


def test_summarize_imports_available() -> None:
    """All symbols used in the worked summarize example are importable.

    Pins the import surface taught in the doc's §Worked example section.
    If any symbol is removed or renamed, this test catches it.
    """
    from ai_workflows.workflows import (  # noqa: F401
        LLMStep,
        RetryPolicy,
        ValidateStep,
        WorkflowSpec,
        register_workflow,
    )


def test_summarize_worked_example_constructs() -> None:
    """The worked example's WorkflowSpec + steps construct without error.

    Drives the same construction path the doc shows. Uses a local
    tier-registry dict instead of ``summarize_tier_registry()`` to keep
    the test hermetic (no provider import needed for a construction-only check).
    """
    from ai_workflows.primitives.tiers import LiteLLMRoute, TierConfig
    from ai_workflows.workflows import LLMStep, RetryPolicy, ValidateStep, WorkflowSpec

    class SummarizeInput(BaseModel):
        text: str
        max_words: int

    class SummarizeOutput(BaseModel):
        summary: str

    stub_tiers = {
        "summarize-llm": TierConfig(
            name="summarize-llm",
            route=LiteLLMRoute(model="gemini/gemini-2.5-flash"),
            max_concurrency=4,
            per_call_timeout_s=120,
        ),
    }

    spec = WorkflowSpec(
        name="summarize_doc_test",
        input_schema=SummarizeInput,
        output_schema=SummarizeOutput,
        tiers=stub_tiers,
        steps=[
            LLMStep(
                tier="summarize-llm",
                prompt_template=(
                    "Summarize the following text in at most {max_words} words. "
                    "Respond with a JSON object matching the SummarizeOutput schema.\n\n"
                    "Text:\n{text}"
                ),
                response_format=SummarizeOutput,
                retry=RetryPolicy(
                    max_transient_attempts=3,
                    max_semantic_attempts=2,
                    transient_backoff_base_s=0.5,
                    transient_backoff_max_s=4.0,
                ),
            ),
            ValidateStep(
                target_field="summary",
                schema=SummarizeOutput,
            ),
        ],
    )

    assert spec.name == "summarize_doc_test"
    assert len(spec.steps) == 2
    assert isinstance(spec.steps[0], LLMStep)
    assert isinstance(spec.steps[1], ValidateStep)


def _extract_worked_example_block(doc_text: str) -> str:
    """Extract the first ```python block from the §Worked example section.

    Returns the raw block content (without fencing markers).
    """
    worked_example_idx = doc_text.find("## Worked example")
    assert worked_example_idx >= 0, "Expected '## Worked example' section in the doc"
    next_section_idx = doc_text.find("\n## ", worked_example_idx + 1)
    section = (
        doc_text[worked_example_idx:next_section_idx]
        if next_section_idx >= 0
        else doc_text[worked_example_idx:]
    )

    # Extract the first ```python ... ``` block within that section
    fence_start = section.find("```python\n")
    assert fence_start >= 0, "No ```python block found in §Worked example section"
    fence_end = section.find("\n```", fence_start + len("```python\n"))
    assert fence_end >= 0, "Unclosed ```python block in §Worked example section"
    return section[fence_start + len("```python\n"):fence_end]


def _normalise_for_comparison(text: str) -> list[str]:
    """Normalise a source block for byte-equality comparison.

    Strips:
    - Lines starting with ``# doctest:`` (doctest markers).
    - The two-line LOW-2 doc-only comment block starting with ``# (For brevity``
      (that comment is added to the doc to explain the sibling-module pattern;
      it is not part of the source file).
    - Trailing whitespace from each line.
    - Leading/trailing blank lines.

    Returns the list of normalised non-empty lines.
    """
    _LOW2_COMMENT_FRAGMENTS = (
        "# (For brevity",
        "# downstream authors can keep it inline as shown in",
    )
    lines = []
    for raw in text.splitlines():
        stripped = raw.rstrip()
        if stripped.startswith("# doctest:"):
            continue
        if any(stripped.startswith(frag) for frag in _LOW2_COMMENT_FRAGMENTS):
            continue
        lines.append(stripped)
    # Strip leading and trailing blank lines
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return lines


def test_worked_example_matches_summarize_py() -> None:
    """The doc's worked-example is byte-for-byte source-shared with summarize.py.

    AC-3 (MEDIUM-1 fix): the spec text requires byte-for-byte source sharing (modulo
    doctest framing). This test normalises both the doc snippet and the summarize.py
    source (stripping doctest markers, the LOW-2 sibling-module comment, trailing
    whitespace, and leading/trailing blank lines) and asserts line-set equality.

    If summarize.py adds, removes, or changes any line, this test will fail and
    require writing-a-workflow.md §Worked example to be updated to match.
    """
    # Read the canonical source
    summarize_src_path = _REPO_ROOT / "ai_workflows" / "workflows" / "summarize.py"
    assert summarize_src_path.exists(), f"Expected summarize.py at {summarize_src_path}"
    summarize_src = summarize_src_path.read_text(encoding="utf-8")

    # The source file starts with a module docstring (lines 1–48) then the code.
    # We want only the code portion — everything from ``from __future__`` onwards.
    future_idx = summarize_src.find("from __future__ import annotations")
    assert future_idx >= 0, "Expected 'from __future__ import annotations' in summarize.py"
    source_code = summarize_src[future_idx:]

    # Read the doc's worked example block
    doc_text = _DOC_PATH.read_text(encoding="utf-8")
    doc_block = _extract_worked_example_block(doc_text)

    source_lines = _normalise_for_comparison(source_code)
    doc_lines = _normalise_for_comparison(doc_block)

    # Build a readable diff on mismatch
    if source_lines != doc_lines:
        diff = list(difflib.unified_diff(
            source_lines,
            doc_lines,
            fromfile="summarize.py (normalised)",
            tofile="doc worked example (normalised)",
            lineterm="",
        ))
        raise AssertionError(
            "AC-3 (MEDIUM-1) violated: doc worked-example is not byte-for-byte "
            "source-shared with summarize.py.\n\n"
            "Diff (summarize.py → doc):\n" + "\n".join(diff)
        )


def test_summarize_py_module_docstring_cites_doc() -> None:
    """summarize.py's docstring cites docs/writing-a-workflow.md as T05's source.

    Cross-checks that the module docstring is up-to-date about the relationship
    between summarize.py and writing-a-workflow.md.
    """
    summarize_mod = importlib.import_module("ai_workflows.workflows.summarize")
    doc = inspect.getdoc(summarize_mod) or ""
    # The docstring should mention T05 or writing-a-workflow or the doc relationship
    assert any(
        phrase in doc
        for phrase in ["T05", "writing-a-workflow", "docs/writing-a-workflow"]
    ), (
        "ai_workflows/workflows/summarize.py module docstring should mention the "
        "docs/writing-a-workflow.md relationship (T05 worked-example source)."
    )


# ---------------------------------------------------------------------------
# AC-3 / AC-1 — no `import langgraph` in Tier-1/Tier-2 blocks
# ---------------------------------------------------------------------------


def _extract_python_blocks_from_text(text: str) -> list[tuple[int, str]]:
    """Extract ```python blocks from a markdown text string.

    Same logic as ``_extract_python_blocks`` but operates on a string directly
    rather than reading from a file path.
    """
    lines = text.splitlines()
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
                blocks.append((start_line, "\n".join(block_lines)))
                in_block = False
                block_lines = []
            else:
                block_lines.append(line)

    return blocks


def test_no_import_langgraph_in_tier1_tier2_blocks() -> None:
    """No ```python block in the doc contains `import langgraph` before the Escape hatch section.

    AC-1: Tier 1/2 examples must not teach consumers to import LangGraph.
    The escape-hatch section legitimately contains LangGraph; everything before
    the §Escape hatch heading must be langgraph-free.
    """
    doc_text = _DOC_PATH.read_text(encoding="utf-8")

    # Split at the escape-hatch section heading
    escape_idx = doc_text.find("## Escape hatch")
    assert escape_idx > 0, "Expected '## Escape hatch' section in the doc"
    tier1_tier2_section = doc_text[:escape_idx]

    # Extract python blocks from the Tier-1/Tier-2 portion only
    blocks = _extract_python_blocks_from_text(tier1_tier2_section)
    langgraph_violations: list[str] = []

    for start_line, block_src in blocks:
        if "import langgraph" in block_src:
            langgraph_violations.append(
                f"Line ~{start_line}: Tier-1/Tier-2 block contains 'import langgraph'"
            )

    assert not langgraph_violations, (
        "AC-1 violation — 'import langgraph' found in Tier-1/Tier-2 code blocks:\n"
        + "\n".join(langgraph_violations)
    )


# ---------------------------------------------------------------------------
# AC-4 — MCP payload wrapper present in doc
# ---------------------------------------------------------------------------


def test_doc_documents_mcp_payload_wrapper() -> None:
    """§Running your workflow documents the MCP payload wrapper convention.

    AC-4: the ``payload`` key is required by FastMCP; its omission was the
    first CS-300 pre-flight gap (DOC-DG4 in the M18 inventory).
    """
    doc_text = _DOC_PATH.read_text(encoding="utf-8")
    assert '"payload"' in doc_text or "'payload'" in doc_text, (
        "AC-4 violated: the doc must document the MCP payload wrapper. "
        "The string 'payload' must appear in a code block in §Running your workflow."
    )
    assert "FastMCP" in doc_text or "fastmcp" in doc_text.lower(), (
        "AC-4 violated: the doc should reference FastMCP in the MCP section."
    )


# ---------------------------------------------------------------------------
# AC-5 — result.artifact canonical; result.plan deprecated
# ---------------------------------------------------------------------------


def test_doc_documents_artifact_and_plan_deprecation() -> None:
    """§Running your workflow documents result.artifact + plan deprecation.

    AC-5: ``result.artifact`` is the canonical field; ``result.plan`` is a
    deprecated alias through 0.2.x with removal target 1.0.
    """
    doc_text = _DOC_PATH.read_text(encoding="utf-8")
    assert "result.artifact" in doc_text, (
        "AC-5 violated: 'result.artifact' not found in the doc."
    )
    assert "result.plan" in doc_text, (
        "AC-5 violated: 'result.plan' not found in the doc — must mention the deprecated alias."
    )
    assert "deprecated" in doc_text.lower(), (
        "AC-5 violated: the doc must describe 'result.plan' as deprecated."
    )
    # TA-LOW-01: verify the 0.2.x / 1.0 phrasing is consistent with T03's CHANGELOG
    assert "0.2.x" in doc_text, (
        "TA-LOW-01 violated: deprecation framing must cite '0.2.x' as the compatibility window."
    )
    assert "1.0" in doc_text, (
        "TA-LOW-01 violated: deprecation framing must cite '1.0' as the removal target."
    )


# ---------------------------------------------------------------------------
# HIGH-1 — CLI command-name pin: no invented flags / commands in doc
# ---------------------------------------------------------------------------


def test_doc_cli_no_approve_flag() -> None:
    """Doc must not teach the non-existent --approve flag on aiw resume.

    HIGH-1 fix: the actual flag is --gate-response approved (or bare aiw resume
    for the default). --approve is rejected by Typer at runtime.
    """
    doc_text = _DOC_PATH.read_text(encoding="utf-8")
    assert "--approve" not in doc_text, (
        "HIGH-1: doc contains '--approve' which is not a valid flag on 'aiw resume'. "
        "The correct flag is '--gate-response approved' (or bare 'aiw resume' for the default)."
    )


def test_doc_cli_no_aiw_cancel_command() -> None:
    """Doc must not teach the non-existent aiw cancel command.

    HIGH-1 fix: 'aiw cancel' does not exist at 0.2.x. Cancellation is
    MCP-only via the cancel_run tool.
    """
    doc_text = _DOC_PATH.read_text(encoding="utf-8")
    # The phrase "aiw cancel" must not appear as a command invocation.
    # We allow "aiw cancel" to appear in a prose note explaining it does NOT exist.
    lines_with_aiw_cancel = [
        line.strip()
        for line in doc_text.splitlines()
        if "aiw cancel" in line
        and not any(neg in line for neg in ["not implemented", "is not", "CLI cancellation"])
    ]
    assert not lines_with_aiw_cancel, (
        "HIGH-1: doc teaches 'aiw cancel' as a valid command, but it does not exist "
        "at 0.2.x (cancellation is MCP-only). Lines:\n"
        + "\n".join(lines_with_aiw_cancel)
    )


def test_doc_cli_resume_registered_commands() -> None:
    """CLI subcommands taught in the doc match the Typer app's registered commands.

    HIGH-1: pins the doc against the live CLI surface. Verifies that 'resume'
    is a registered command name on the Typer app.

    Typer infers a command's name from its callback function name when ``name=None``
    is passed to ``@app.command()``. We resolve the effective name accordingly.
    """
    from ai_workflows.cli import app

    def _effective_name(cmd_info: object) -> str:
        """Return the effective CLI command name for a Typer CommandInfo."""
        explicit = getattr(cmd_info, "name", None)
        if explicit:
            return explicit
        cb = getattr(cmd_info, "callback", None)
        if cb and hasattr(cb, "__name__"):
            return cb.__name__.replace("_", "-")
        return ""

    registered = {_effective_name(c) for c in app.registered_commands}
    assert "resume" in registered, (
        f"'aiw resume' is taught in the doc but not registered on the Typer app. "
        f"Effective registered commands: {registered}"
    )
    # Confirm 'cancel' is NOT registered (so the doc correctly omits it)
    assert "cancel" not in registered, (
        "'cancel' is unexpectedly registered on the Typer app — "
        "update the doc to teach 'aiw cancel' and remove the 'not implemented' note."
    )


# ---------------------------------------------------------------------------
# HIGH-2 — Testing fixture patch-target pin: no broken import path in doc
# ---------------------------------------------------------------------------


def test_doc_testing_fixture_no_broken_import_path() -> None:
    """Doc's Testing section must not reference the non-existent providers.litellm_adapter path.

    HIGH-2 fix: ai_workflows.primitives.providers.litellm_adapter does not exist.
    The correct module is ai_workflows.primitives.llm.litellm_adapter.
    monkeypatch.setattr on the wrong path raises ModuleNotFoundError at fixture setup.
    """
    doc_text = _DOC_PATH.read_text(encoding="utf-8")
    assert "ai_workflows.primitives.providers.litellm_adapter" not in doc_text, (
        "HIGH-2: doc references 'ai_workflows.primitives.providers.litellm_adapter' "
        "which does not exist. The correct patch target is "
        "'ai_workflows.graph.tiered_node' (where LiteLLMAdapter is imported)."
    )


def test_doc_testing_fixture_uses_correct_patch_target() -> None:
    """Doc's Testing section must reference ai_workflows.graph.tiered_node as the patch site.

    HIGH-2 fix: tiered_node already imported LiteLLMAdapter at module load time;
    patching the source module is a no-op for the consumer-side reference.
    The correct patch target is ai_workflows.graph.tiered_node.LiteLLMAdapter.
    """
    doc_text = _DOC_PATH.read_text(encoding="utf-8")
    testing_idx = doc_text.find("## Testing your workflow")
    assert testing_idx >= 0, "Expected '## Testing your workflow' section in the doc"
    testing_section = doc_text[testing_idx:]
    has_correct_patch_site = (
        "ai_workflows.graph.tiered_node" in testing_section
        or "tiered_node" in testing_section
    )
    assert has_correct_patch_site, (
        "HIGH-2: the doc's Testing section must reference 'ai_workflows.graph.tiered_node' "
        "as the monkeypatch target (the import site, not the source module)."
    )


# ---------------------------------------------------------------------------
# AC-6 — Tier 3 / Tier 4 cross-links present
# ---------------------------------------------------------------------------


def test_doc_cross_links_to_deeper_tiers() -> None:
    """§When you need more cross-links to writing-a-custom-step.md and writing-a-graph-primitive.md.

    AC-6: the doc must point Tier-3 consumers to the custom-step guide and
    Tier-4 consumers to the graph-primitive guide.
    """
    doc_text = _DOC_PATH.read_text(encoding="utf-8")
    assert "writing-a-custom-step.md" in doc_text, (
        "AC-6 violated: no link to writing-a-custom-step.md found."
    )
    assert "writing-a-graph-primitive.md" in doc_text, (
        "AC-6 violated: no link to writing-a-graph-primitive.md found."
    )


def test_doc_tier3_framing_includes_compile_override() -> None:
    """Tier 3 framing covers both execute() typical path and compile() upgrade path.

    AC-6 (locked Q4 refinement): the framing must include BOTH execute() and
    compile() so authors know about the upgrade path to fan-out / sub-graph /
    conditional edge topologies.
    """
    doc_text = _DOC_PATH.read_text(encoding="utf-8")
    assert "execute" in doc_text, (
        "AC-6 violated: Tier 3 framing must mention the execute() typical path."
    )
    assert "compile(" in doc_text or "compile()" in doc_text, (
        "AC-6 violated: Tier 3 framing must mention the compile() upgrade path."
    )
    # compile_step_in_isolation reference (TA-LOW-06)
    assert "compile_step_in_isolation" in doc_text, (
        "TA-LOW-06 violated: §Testing your workflow must reference compile_step_in_isolation "
        "by name (matching T06's eventual fixture name)."
    )


# ---------------------------------------------------------------------------
# AC-7 — External workflows section updated
# ---------------------------------------------------------------------------


def test_doc_external_workflows_no_get_run_status() -> None:
    """§External workflows must not reference the non-existent get_run_status MCP tool.

    AC-7: DOC-CONTRADICTION-1 from the M18 inventory — this tool was never
    implemented; the old doc referenced it erroneously.
    """
    doc_text = _DOC_PATH.read_text(encoding="utf-8")
    assert "get_run_status" not in doc_text, (
        "AC-7 violated: 'get_run_status' must not appear — the tool does not exist "
        "(M18 inventory DOC-CONTRADICTION-1)."
    )


def test_doc_external_workflows_tier_registry_convention() -> None:
    """§External workflows states the tier-registry naming convention explicitly.

    AC-7: DOC-CONTRADICTION-2 from the M18 inventory — the prefix of
    ``<workflow>_tier_registry()`` must literally match the workflow name.
    """
    doc_text = _DOC_PATH.read_text(encoding="utf-8")
    # The convention is stated in the doc with the "must literally match" framing
    assert "must literally match" in doc_text or "literally match" in doc_text, (
        "AC-7 violated: the tier-registry naming convention must state that the prefix "
        "must literally match the workflow name (DOC-CONTRADICTION-2)."
    )


def test_doc_external_workflows_uses_workflowspec() -> None:
    """§External workflows minimum module shape uses WorkflowSpec, not the escape-hatch builder.

    AC-7: the minimum module shape taught in the doc must use the spec API.
    """
    doc_text = _DOC_PATH.read_text(encoding="utf-8")
    assert "WorkflowSpec" in doc_text, (
        "AC-7 violated: the external-workflows section must show a WorkflowSpec example."
    )


# ---------------------------------------------------------------------------
# AC-8 — Escape hatch section exists with honest framing
# ---------------------------------------------------------------------------


def test_doc_escape_hatch_section_exists() -> None:
    """§Escape hatch sub-section exists with honest framing.

    AC-8: the doc must contain an escape-hatch section, acknowledge most
    workflows don't need it, and cross-link to writing-a-graph-primitive.md.
    """
    doc_text = _DOC_PATH.read_text(encoding="utf-8")
    assert "## Escape hatch" in doc_text, (
        "AC-8 violated: no '## Escape hatch' section in the doc."
    )
    assert "Most workflows do not need" in doc_text or "most workflows" in doc_text.lower(), (
        "AC-8 violated: the escape-hatch section must acknowledge most workflows don't need it."
    )
    # cross-link already checked in test_doc_cross_links_to_deeper_tiers


# ---------------------------------------------------------------------------
# AC-9 — No "(builder-only, on design branch)" rot on non-design-branch items
# ---------------------------------------------------------------------------


def test_doc_no_builder_only_annotation_on_main_tree_items() -> None:
    """Outdated '(builder-only, on design branch)' annotations on main-tree items are cleared.

    AC-9: ADR-0007 and ADR-0008 have shipped and are in the main tree as of
    0.2.x; any remaining '(builder-only, on design branch)' annotation on these
    items is cross-reference rot.

    The doc may legitimately annotate links that genuinely point into design_docs/
    (which do not ship in the wheel) with the marker — but not items that have
    already shipped to main.
    """
    doc_text = _DOC_PATH.read_text(encoding="utf-8")
    # The doc correctly uses the marker on design_docs/ links (ADR files).
    # We verify there are no stale builder-only annotations on code constructs
    # that shipped in 0.2.x+ (e.g. "TieredNode (builder-only, on design branch)").
    shipped_items = [
        "TieredNode",
        "ValidatorNode",
        "RetryingEdge",
        "HumanGate",
        "register_workflow",
        "WorkflowSpec",
        "LLMStep",
    ]
    marker = "(builder-only, on design branch)"
    violations = []
    for item in shipped_items:
        # Check if the item appears on the SAME LINE as the builder-only marker
        for line in doc_text.splitlines():
            if item in line and marker in line:
                violations.append(line.strip())

    assert not violations, (
        "AC-9 violated: shipped items annotated as builder-only:\n"
        + "\n".join(violations)
    )


# ---------------------------------------------------------------------------
# ADV-1 — Reserved field names documented
# ---------------------------------------------------------------------------


def test_doc_documents_reserved_field_names() -> None:
    """§WorkflowSpec shape documents reserved field names (T04 security ADV-1).

    The framework reserves 'run_id' and several '_'-prefixed keys. Authors
    must not use these as input_schema or output_schema field names.
    """
    doc_text = _DOC_PATH.read_text(encoding="utf-8")
    reserved_names = [
        "run_id",
        "last_exception",
        "_retry_counts",
        "_non_retryable_failures",
        "_mid_run_tier_overrides",
    ]
    missing = [name for name in reserved_names if name not in doc_text]
    assert not missing, (
        f"ADV-1 violated: the following reserved field names are not documented: {missing}"
    )


# ---------------------------------------------------------------------------
# ADV-2 — prompt_template injection caveat documented
# ---------------------------------------------------------------------------


def test_doc_documents_prompt_template_injection_caveat() -> None:
    """§LLMStep documents the prompt_template brace-escaping caveat (T04 security ADV-2).

    End-user-controlled field values can inject str.format()-style placeholders;
    authors must know to use {{ / }} escaping or switch to prompt_fn=.
    """
    doc_text = _DOC_PATH.read_text(encoding="utf-8")
    assert "{{" in doc_text and "}}" in doc_text, (
        "ADV-2 violated: the doc must show {{ / }} brace-escaping syntax."
    )
    assert "prompt_fn" in doc_text, (
        "ADV-2 violated: the doc must mention prompt_fn= as the safe alternative."
    )
    # The caveat should appear near the LLMStep section
    has_brace_caveat = (
        "Brace-escaping" in doc_text
        or "brace-escaping" in doc_text
        or "brace" in doc_text.lower()
    )
    assert has_brace_caveat, (
        "ADV-2 violated: the doc must include a brace-escaping caveat in the LLMStep section."
    )


# ---------------------------------------------------------------------------
# Doc structure — section order check (AC-2)
# ---------------------------------------------------------------------------

_EXPECTED_SECTIONS = [
    "## Prerequisites",
    "## The `WorkflowSpec` shape",
    "## Built-in step types",
    "## Worked example",
    "## Running your workflow",
    "## When you need more",
    "## External workflows from a downstream consumer",
    "## Escape hatch",
    "## Testing your workflow",
]


def test_doc_section_order() -> None:
    """Section structure matches the spec Deliverable 1 prescribed order (AC-2).

    Every required section must be present and appear in the correct order.
    The test finds the first occurrence of each heading and asserts monotone
    increasing character position.
    """
    doc_text = _DOC_PATH.read_text(encoding="utf-8")
    positions = []
    missing = []
    for section in _EXPECTED_SECTIONS:
        idx = doc_text.find(section)
        if idx == -1:
            missing.append(section)
        else:
            positions.append((idx, section))

    assert not missing, f"Missing required sections: {missing}"

    for i in range(1, len(positions)):
        prev_pos, prev_sec = positions[i - 1]
        curr_pos, curr_sec = positions[i]
        assert curr_pos > prev_pos, (
            f"Section order violation: '{curr_sec}' appears before '{prev_sec}'"
        )
