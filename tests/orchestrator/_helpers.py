"""Orchestrator test helpers — spawn-prompt sizing and KDR extraction.

Task: M20 Task 02 — Sub-agent input prune (orchestrator-side scope discipline).
Relationship: Provides the Python implementations of the spawn-prompt scope rules
  described in `.claude/commands/_common/spawn_prompt_template.md`.  The production
  versions of these rules run as markdown-prose logic inside the slash-command
  orchestrators; this module provides equivalent Python implementations so
  `tests/orchestrator/test_spawn_prompt_size.py` and
  `tests/orchestrator/test_kdr_section_extractor.py` can exercise every branch
  without live agent spawns.

This module intentionally lives under `tests/` (not `ai_workflows/`) because
it is test infrastructure for the autonomy orchestration layer (`.claude/`).
Adding it to `ai_workflows/` would create a subpackage with no runtime caller,
violating the layer discipline (`primitives → graph → workflows → surfaces`)
enforced by `uv run lint-imports`.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Token-count proxy
# ---------------------------------------------------------------------------

def token_count_proxy(text: str) -> float:
    """Approximate token count using a whitespace-word proxy.

    Uses ``len(re.findall(r'\\S+', text)) * 1.3`` — the canonical proxy defined
    at T01/T02 (L8, round 1, 2026-04-27) and reused by T22/T23 for consistency.
    Accuracy is not load-bearing; magnitude is.  No ``tiktoken`` dependency.

    Args:
        text: Any string — typically an orchestrator spawn prompt.

    Returns:
        An approximate floating-point token count.
    """
    return len(re.findall(r"\S+", text)) * 1.3


# ---------------------------------------------------------------------------
# Per-agent spawn-prompt token ceilings
# ---------------------------------------------------------------------------

# Ceilings from `.claude/commands/_common/spawn_prompt_template.md` §Token ceilings.
# Values are in approximate tokens (via the regex proxy above).
AGENT_SPAWN_CEILINGS: dict[str, int] = {
    "builder": 8_000,
    "auditor": 6_000,
    "sr-dev": 4_000,
    "sr-sdet": 4_000,
    "security-reviewer": 4_000,
    "dependency-auditor": 4_000,
    "task-analyzer": 6_000,
    "roadmap-selector": 4_000,
}


# ---------------------------------------------------------------------------
# KDR-section extraction logic
# ---------------------------------------------------------------------------

# Regex that matches a KDR citation anywhere in a markdown text block.
# Matches "KDR-NNN" where NNN is 1–3 digits.
_KDR_CITE_RE = re.compile(r"\bKDR-(\d{1,3})\b")

# Regex that matches a single KDR row in the §9 table of architecture.md.
# The table has rows like: "| KDR-003 | <decision text> | <source> |"
_KDR_ROW_RE = re.compile(
    r"^\|\s*(KDR-\d{1,3})\s*\|(.+?)\|(.+?)\|?\s*$",
    re.MULTILINE,
)

# The §9 grid header — returned when no KDRs are cited (compact pointer).
_KDR_GRID_HEADER = (
    "| ID | Decision | Source |\n"
    "| --- | --- | --- |\n"
    "(read §9 of design_docs/architecture.md on-demand for the full table)"
)


def extract_cited_kdrs(spec_text: str) -> list[str]:
    """Parse KDR identifiers cited anywhere in a task spec.

    Finds every ``KDR-NNN`` token in ``spec_text`` and returns a deduplicated,
    sorted list of normalised identifiers (e.g. ``["KDR-003", "KDR-013"]``).

    Args:
        spec_text: The full text of a task spec markdown file.

    Returns:
        Deduplicated, sorted list of KDR identifiers cited (e.g.
        ``["KDR-003", "KDR-013"]``).  Empty list if none are cited.
    """
    matches = _KDR_CITE_RE.findall(spec_text)
    # Normalise to zero-padded 3-digit form to match architecture.md format
    ids = {f"KDR-{m.zfill(3)}" for m in matches}
    return sorted(ids)


def build_kdr_compact_pointer(cited_kdrs: list[str]) -> str:
    """Build the compact KDR pointer string for an Auditor spawn prompt.

    When KDRs are cited, returns a one-line list of the cited identifiers
    with an instruction to read §9 on-demand.  When no KDRs are cited,
    returns the §9 grid header only (as a compact pointer for the Auditor
    to expand on-demand).

    This is the value the orchestrator places under "Relevant KDRs:" in the
    Auditor's spawn prompt — it replaces the full §9 table content inline.

    Args:
        cited_kdrs: Output of :func:`extract_cited_kdrs`.

    Returns:
        A compact string: either a one-liner with cited IDs or the grid header.
    """
    if not cited_kdrs:
        return _KDR_GRID_HEADER
    ids_str = ", ".join(cited_kdrs)
    return (
        f"Relevant KDRs: {ids_str} — "
        "read §9 of design_docs/architecture.md on-demand for full text."
    )


def extract_kdr_sections(
    architecture_text: str,
    cited_kdrs: list[str],
) -> str:
    """Extract only the §9 table rows for the cited KDRs from architecture.md.

    Parses the §9 markdown table in ``architecture_text`` and returns only the
    rows whose ``KDR-NNN`` identifier appears in ``cited_kdrs``.  When
    ``cited_kdrs`` is empty, returns the §9 grid header only (compact pointer).

    This is the *content* form of the KDR pre-load rule — useful when the
    orchestrator wants to inline the relevant rows rather than just identifiers.
    For the *compact-pointer* form (preferred by the spawn-prompt template),
    use :func:`build_kdr_compact_pointer`.

    Args:
        architecture_text: Full text of ``design_docs/architecture.md``.
        cited_kdrs: Identifiers to extract (from :func:`extract_cited_kdrs`).

    Returns:
        Markdown table header + matching rows, or the compact pointer if no
        KDRs are cited.
    """
    if not cited_kdrs:
        return _KDR_GRID_HEADER

    # Normalise caller-supplied IDs to zero-padded form (e.g. "KDR-3" → "KDR-003")
    # so that callers who skip extract_cited_kdrs() still get correct row matches.
    # IDs without a "-" separator are kept as-is (they won't match any table row,
    # which is the safe-fail behaviour rather than a silent incorrect match).
    cited_set = {
        f"KDR-{c.split('-', 1)[1].zfill(3)}" if c.startswith("KDR-") and "-" in c else c
        for c in cited_kdrs
    }
    header = "| ID | Decision | Source |\n| --- | --- | --- |\n"
    matched_rows: list[str] = []

    for match in _KDR_ROW_RE.finditer(architecture_text):
        kdr_id = match.group(1).strip()
        # Normalise to zero-padded form
        parts = kdr_id.split("-")
        if len(parts) == 2:
            kdr_id = f"KDR-{parts[1].zfill(3)}"
        if kdr_id in cited_set:
            matched_rows.append(match.group(0).strip())

    if not matched_rows:
        # None of the cited KDRs were found in the table — return compact pointer
        return build_kdr_compact_pointer(cited_kdrs)

    return header + "\n".join(matched_rows)


# ---------------------------------------------------------------------------
# Spawn-prompt builder utilities (for test fixture construction)
# ---------------------------------------------------------------------------

def build_builder_spawn_prompt(
    task_spec_path: str,
    issue_file_path: str,
    milestone_readme_path: str,
    project_context_brief: str,
) -> str:
    """Construct a minimal Builder spawn prompt per the scope discipline rules.

    Implements the Builder minimal pre-load set from
    `.claude/commands/_common/spawn_prompt_template.md`.

    Args:
        task_spec_path: Repo-relative path to the task spec.
        issue_file_path: Repo-relative path to the issue file (may not exist).
        milestone_readme_path: Repo-relative path to the milestone README.
        project_context_brief: Verbatim project context brief.

    Returns:
        A spawn-prompt string whose token count should be ≤ the Builder ceiling.
    """
    budget_directive = (
        "Output budget: 4K tokens. Durable findings live in the file you write;\n"
        "the return is the 3-line schema only — "
        "see .claude/commands/_common/agent_return_schema.md"
    )
    schema_reminder = (
        "Return per .claude/commands/_common/agent_return_schema.md — exactly 3 lines:\n"
        "verdict: <token>\n"
        "file: <path or —>\n"
        "section: <## header or —>\n"
        "No prose, no preamble, no chat body outside those three lines."
    )
    return (
        f"Task spec path: {task_spec_path}\n"
        f"Issue file path: {issue_file_path}\n"
        f"Parent milestone README path: {milestone_readme_path}\n\n"
        f"## Project context brief\n\n{project_context_brief}\n\n"
        f"## Output budget\n\n{budget_directive}\n\n"
        f"## Return schema\n\n{schema_reminder}\n"
    )


def build_auditor_spawn_prompt(
    task_spec_path: str,
    issue_file_path: str,
    milestone_readme_path: str,
    project_context_brief: str,
    git_diff: str,
    cited_kdrs: list[str],
) -> str:
    """Construct a minimal Auditor spawn prompt per the scope discipline rules.

    Implements the Auditor minimal pre-load set from
    `.claude/commands/_common/spawn_prompt_template.md`.  Path references are
    passed; full document content is NOT inlined.

    Args:
        task_spec_path: Repo-relative path to the task spec.
        issue_file_path: Repo-relative path to the issue file.
        milestone_readme_path: Repo-relative path to the milestone README.
        project_context_brief: Verbatim project context brief.
        git_diff: Current ``git diff`` output.
        cited_kdrs: KDR identifiers cited in the task spec
            (from :func:`extract_cited_kdrs`).

    Returns:
        A spawn-prompt string whose token count should be ≤ the Auditor ceiling.
    """
    kdr_pointer = build_kdr_compact_pointer(cited_kdrs)
    budget_directive = (
        "Output budget: 1-2K tokens. Durable findings live in the issue file you write;\n"
        "the return is the 3-line schema only — "
        "see .claude/commands/_common/agent_return_schema.md"
    )
    schema_reminder = (
        "Return per .claude/commands/_common/agent_return_schema.md — exactly 3 lines:\n"
        "verdict: <token>\n"
        "file: <path or —>\n"
        "section: <## header or —>\n"
        "No prose, no preamble, no chat body outside those three lines."
    )
    return (
        f"Task spec path: {task_spec_path}\n"
        f"Issue file path: {issue_file_path}\n"
        f"Parent milestone README path: {milestone_readme_path}\n\n"
        f"## Project context brief\n\n{project_context_brief}\n\n"
        f"## Relevant KDRs\n\n{kdr_pointer}\n\n"
        f"## Current diff\n\n```diff\n{git_diff}\n```\n\n"
        f"## Output budget\n\n{budget_directive}\n\n"
        f"## Return schema\n\n{schema_reminder}\n"
    )


def build_reviewer_spawn_prompt(
    task_spec_path: str,
    issue_file_path: str,
    project_context_brief: str,
    git_diff: str,
    files_touched: list[str],
    agent_name: str = "reviewer",
) -> str:
    """Construct a minimal reviewer spawn prompt per the scope discipline rules.

    Implements the reviewer (sr-dev, sr-sdet, security-reviewer) minimal
    pre-load set from `.claude/commands/_common/spawn_prompt_template.md`.

    Args:
        task_spec_path: Repo-relative path to the task spec.
        issue_file_path: Repo-relative path to the issue file.
        project_context_brief: Verbatim project context brief.
        git_diff: Current ``git diff`` output.
        files_touched: Aggregated list of files touched across all Builder reports.
        agent_name: Agent name for the output budget label.

    Returns:
        A spawn-prompt string whose token count should be ≤ the reviewer ceiling.
    """
    files_str = "\n".join(f"- {f}" for f in files_touched)
    budget_directive = (
        "Output budget: 1-2K tokens. Durable findings live in the issue file you append;\n"
        "the return is the 3-line schema only — "
        "see .claude/commands/_common/agent_return_schema.md"
    )
    schema_reminder = (
        "Return per .claude/commands/_common/agent_return_schema.md — exactly 3 lines:\n"
        "verdict: <token>\n"
        "file: <path or —>\n"
        "section: <## header or —>\n"
        "No prose, no preamble, no chat body outside those three lines."
    )
    return (
        f"Task spec path: {task_spec_path}\n"
        f"Issue file path: {issue_file_path}\n\n"
        f"## Project context brief\n\n{project_context_brief}\n\n"
        f"## Files touched\n\n{files_str}\n\n"
        f"## Current diff\n\n```diff\n{git_diff}\n```\n\n"
        f"## Output budget\n\n{budget_directive}\n\n"
        f"## Return schema\n\n{schema_reminder}\n"
    )


def build_task_analyzer_spawn_prompt(
    milestone_dir_path: str,
    analysis_output_path: str,
    project_context_brief: str,
    round_number: int,
    spec_filenames: list[str],
) -> str:
    """Construct a minimal task-analyzer spawn prompt per the scope discipline rules.

    Implements the task-analyzer minimal pre-load set from
    `.claude/commands/_common/spawn_prompt_template.md`.

    Args:
        milestone_dir_path: Repo-relative path to the milestone directory.
        analysis_output_path: Repo-relative path to the analysis output file.
        project_context_brief: Verbatim project context brief.
        round_number: Current analysis round number.
        spec_filenames: List of task spec filenames to analyze.

    Returns:
        A spawn-prompt string whose token count should be ≤ the task-analyzer ceiling.
    """
    specs_str = "\n".join(f"- {f}" for f in spec_filenames)
    budget_directive = (
        "Output budget: 1-2K tokens. Durable findings live in the task_analysis.md "
        "file you write;\n"
        "the return is the 3-line schema only — "
        "see .claude/commands/_common/agent_return_schema.md"
    )
    schema_reminder = (
        "Return per .claude/commands/_common/agent_return_schema.md — exactly 3 lines:\n"
        "verdict: <token>\n"
        "file: <path or —>\n"
        "section: <## header or —>\n"
        "No prose, no preamble, no chat body outside those three lines."
    )
    return (
        f"Milestone directory path: {milestone_dir_path}\n"
        f"Analysis output file: {analysis_output_path}\n"
        f"Round number: {round_number}\n\n"
        f"## Project context brief\n\n{project_context_brief}\n\n"
        f"## Task spec filenames to analyze\n\n{specs_str}\n\n"
        f"## Output budget\n\n{budget_directive}\n\n"
        f"## Return schema\n\n{schema_reminder}\n"
    )


def build_roadmap_selector_spawn_prompt(
    recommendation_file_path: str,
    project_context_brief: str,
    milestone_scope: str,
) -> str:
    """Construct a minimal roadmap-selector spawn prompt per the scope discipline rules.

    Implements the roadmap-selector minimal pre-load set from
    `.claude/commands/_common/spawn_prompt_template.md`.

    Args:
        recommendation_file_path: Path where the agent should write its recommendation.
        project_context_brief: Verbatim project context brief.
        milestone_scope: Milestone scope string (from $ARGUMENTS, or "all open").

    Returns:
        A spawn-prompt string whose token count should be ≤ the roadmap-selector ceiling.
    """
    budget_directive = (
        "Output budget: 1-2K tokens. Durable findings live in the recommendation "
        "file you write;\n"
        "the return is the 3-line schema only — "
        "see .claude/commands/_common/agent_return_schema.md"
    )
    schema_reminder = (
        "Return per .claude/commands/_common/agent_return_schema.md — exactly 3 lines:\n"
        "verdict: <token>\n"
        "file: <path or —>\n"
        "section: <## header or —>\n"
        "No prose, no preamble, no chat body outside those three lines."
    )
    return (
        f"Recommendation file path: {recommendation_file_path}\n"
        f"Milestone scope: {milestone_scope}\n\n"
        f"## Project context brief\n\n{project_context_brief}\n\n"
        f"## Output budget\n\n{budget_directive}\n\n"
        f"## Return schema\n\n{schema_reminder}\n"
    )
