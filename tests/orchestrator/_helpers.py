"""Orchestrator test helpers — spawn-prompt sizing, KDR extraction, cycle summaries, iter-shipped.

Task: M20 Task 02 — Sub-agent input prune (orchestrator-side scope discipline).
Task: M20 Task 03 — In-task cycle compaction (cycle_<N>/summary.md per Auditor).
Task: M20 Task 04 — Cross-task iteration compaction (iter_<N>-shipped.md at autopilot
  iteration boundaries).
Relationship: Provides the Python implementations of the spawn-prompt scope rules
  described in `.claude/commands/_common/spawn_prompt_template.md`, and the cycle-summary
  emission + read-only-latest-summary rule described in
  `.claude/commands/_common/cycle_summary_template.md`, and the iter-shipped artifact
  emission + read-only-latest-shipped rule described in
  `.claude/commands/autopilot.md` §Path convention.  The production versions of these
  rules run as markdown-prose logic inside the slash-command orchestrators; this module
  provides equivalent Python implementations so the orchestrator tests can exercise every
  branch without live agent spawns.

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


# ---------------------------------------------------------------------------
# Cycle-summary helpers (M20 Task 03)
# ---------------------------------------------------------------------------

# Required keys that every cycle_<N>/summary.md must contain.
# These are the section headings defined in cycle_summary_template.md.
CYCLE_SUMMARY_REQUIRED_KEYS: tuple[str, ...] = (
    "**Cycle:**",
    "**Date:**",
    "**Builder verdict:**",
    "**Auditor verdict:**",
    "**Files changed this cycle:**",
    "**Gates run this cycle:**",
    "**Open issues at end of cycle:**",
    "**Decisions locked this cycle:**",
    "**Carry-over to next cycle:**",
)


def make_cycle_summary(
    cycle_number: int,
    date: str,
    builder_verdict: str,
    auditor_verdict: str,
    files_changed: list[str],
    gates: list[tuple[str, str, str]],
    open_issues: str,
    decisions_locked: list[str],
    carry_over: list[str],
    task_number: int = 3,
) -> str:
    """Render a cycle_<N>/summary.md string per the canonical template.

    Implements the template from
    `.claude/commands/_common/cycle_summary_template.md`.  Used by test helpers
    to generate synthetic cycle-summary content without live Auditor spawns.

    Args:
        cycle_number: The 1-based cycle index (N).
        date: ISO-8601 date string (e.g. "2026-04-28").
        builder_verdict: One of ``BUILT``, ``BLOCKED``, ``STOP-AND-ASK``.
        auditor_verdict: One of ``PASS``, ``OPEN``, ``BLOCKED``.
        files_changed: List of file paths changed this cycle (empty → "none").
        gates: List of ``(name, command, result)`` tuples for the gate table.
        open_issues: Human-readable summary of open issues (e.g. "none" or
            "2 HIGH (M20-T03-ISS-01, M20-T03-ISS-02)").
        decisions_locked: Bullet items for decisions locked this cycle (empty → "none").
        carry_over: Bullet items for ACs the next Builder cycle must satisfy.
            Must be non-empty when ``auditor_verdict`` is ``OPEN`` (invariant from
            the template).
        task_number: Task number for the header line (default: 3).

    Returns:
        A Markdown string conforming to the cycle_<N>/summary.md template.
    """
    files_str = (
        "\n".join(f"- {f}" for f in files_changed) if files_changed else "none"
    )

    gate_rows = "\n".join(
        f"| {name} | `{command}` | {result} |" for name, command, result in gates
    )
    gate_table = (
        "| Gate | Command | Result |\n"
        "|---|---|---|\n"
        + gate_rows
    )

    decisions_str = (
        "\n".join(f"- {d}" for d in decisions_locked)
        if decisions_locked
        else "none"
    )

    carry_str = (
        "\n".join(f"- {c}" for c in carry_over) if carry_over else "none"
    )

    return (
        f"# Cycle {cycle_number} summary — Task {task_number:02d}\n\n"
        f"**Cycle:** {cycle_number}\n"
        f"**Date:** {date}\n"
        f"**Builder verdict:** {builder_verdict}\n"
        f"**Auditor verdict:** {auditor_verdict}\n"
        f"**Files changed this cycle:** {files_str}\n"
        f"**Gates run this cycle:**\n\n{gate_table}\n\n"
        f"**Open issues at end of cycle:** {open_issues}\n"
        f"**Decisions locked this cycle:** {decisions_str}\n"
        f"**Carry-over to next cycle:** {carry_str}\n"
    )


def build_builder_spawn_prompt_cycle_n(
    task_spec_path: str,
    issue_file_path: str,
    project_context_brief: str,
    latest_cycle_summary: str,
    cycle_summary_path: str,
) -> str:
    """Construct a cycle-N (N ≥ 2) Builder spawn prompt with the latest cycle summary.

    Implements the read-only-latest-summary rule from
    `.claude/commands/_common/cycle_summary_template.md`:
    cycle N (N ≥ 2) replaces the parent milestone README with the most recent
    `cycle_{N-1}/summary.md` content.  No prior Builder reports, no prior Auditor
    chat content, no prior cycle summaries beyond the most recent one.

    Args:
        task_spec_path: Repo-relative path to the task spec.
        issue_file_path: Repo-relative path to the issue file.
        project_context_brief: Verbatim project context brief.
        latest_cycle_summary: Full content of the most recent cycle summary.
        cycle_summary_path: Repo-relative path of the most recent cycle summary
            (e.g. ``"runs/m20_t03/cycle_1/summary.md"``).

    Returns:
        A spawn-prompt string for the Builder on cycle N ≥ 2.
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
        f"Issue file path: {issue_file_path}\n\n"
        f"## Project context brief\n\n{project_context_brief}\n\n"
        f"## Latest cycle summary ({cycle_summary_path})\n\n"
        f"{latest_cycle_summary}\n\n"
        f"## Output budget\n\n{budget_directive}\n\n"
        f"## Return schema\n\n{schema_reminder}\n"
    )


def parse_cycle_summary(summary_text: str) -> dict[str, str]:
    """Parse a cycle_<N>/summary.md into a key→value mapping.

    Extracts each ``**Key:**`` field from the summary text.  Multi-line values
    (e.g. gate tables, bullet lists) are captured up to the next ``**Key:**``
    marker.  This is test-infrastructure parsing; it is not designed to be
    exhaustive against adversarial input.

    Args:
        summary_text: Full text of a ``cycle_<N>/summary.md`` file.

    Returns:
        A dict mapping each ``**Key:**`` label (without the ``**`` delimiters or
        trailing ``:``) to its value string (stripped).
    """
    result: dict[str, str] = {}
    # Match lines like "**Key:** value" or "**Key:**" (possibly multi-line value)
    key_re = re.compile(r"^\*\*(.+?):\*\*\s*(.*)", re.MULTILINE)
    matches = list(key_re.finditer(summary_text))
    for i, match in enumerate(matches):
        key = match.group(1).strip()
        # Value is the rest of this line plus lines until the next key match
        inline_value = match.group(2).strip()
        if i + 1 < len(matches):
            between = summary_text[match.end():matches[i + 1].start()]
        else:
            between = summary_text[match.end():]
        extra = between.strip()
        value = (inline_value + ("\n" + extra if extra else "")).strip()
        result[key] = value
    return result


# ---------------------------------------------------------------------------
# Iter-shipped artifact helpers (M20 Task 04)
# ---------------------------------------------------------------------------

# Required keys that every autopilot-<run-ts>-iter<N>-shipped.md must contain.
# These are the section headings defined in autopilot.md §Iteration-shipped artifact structure.
ITER_SHIPPED_REQUIRED_KEYS: tuple[str, ...] = (
    "**Run timestamp:**",
    "**Iteration:**",
    "**Date:**",
    "**Verdict from queue-pick:**",
)

# Section headers that must appear in a PROCEED iter-shipped artifact.
ITER_SHIPPED_PROCEED_SECTIONS: tuple[str, ...] = (
    "## Task shipped (if PROCEED)",
    "## Carry-over to next iteration",
    "## Telemetry summary",
)


def make_iter_shipped(
    run_timestamp: str,
    iteration: int,
    date: str,
    verdict: str,
    task_shipped: str | None = None,
    cycles: int | None = None,
    commit_sha: str | None = None,
    files_touched: list[str] | None = None,
    auditor_verdict: str | None = None,
    reviewer_verdicts: dict[str, str] | None = None,
    kdr_additions: str | None = None,
    clean_tasks_milestone: str | None = None,
    clean_tasks_rounds: int | None = None,
    clean_tasks_stop: str | None = None,
    specs_hardened: list[str] | None = None,
    halt_reason: str | None = None,
    state_preserved: list[str] | None = None,
    user_questions: list[str] | None = None,
    carry_over: str = "",
) -> str:
    """Render an autopilot-<run-ts>-iter<N>-shipped.md string per the canonical template.

    Implements the template from ``.claude/commands/autopilot.md``
    §Iteration-shipped artifact structure.  Used by test helpers to generate
    synthetic iter-shipped content without live autopilot runs.

    Args:
        run_timestamp: The run timestamp string (e.g. "20260427T152243Z").
        iteration: The 1-based iteration index (N).
        date: ISO-8601 date string (e.g. "2026-04-28").
        verdict: One of ``PROCEED``, ``NEEDS-CLEAN-TASKS``, ``HALT-AND-ASK``.
        task_shipped: Task spec filename (for PROCEED verdict).
        cycles: Number of Builder→Auditor cycles run (for PROCEED verdict).
        commit_sha: Final commit SHA on design_branch (for PROCEED verdict).
        files_touched: List of files touched (for PROCEED verdict).
        auditor_verdict: Auditor's final verdict (for PROCEED verdict).
        reviewer_verdicts: Dict of reviewer name → verdict (for PROCEED verdict).
        kdr_additions: KDR additions string (for PROCEED verdict).
        clean_tasks_milestone: Milestone hardened (for NEEDS-CLEAN-TASKS verdict).
        clean_tasks_rounds: Number of clean-tasks rounds (for NEEDS-CLEAN-TASKS verdict).
        clean_tasks_stop: Final stop verdict (for NEEDS-CLEAN-TASKS verdict).
        specs_hardened: List of spec filenames hardened (for NEEDS-CLEAN-TASKS verdict).
        halt_reason: Halt reason paragraph (for HALT-AND-ASK verdict).
        state_preserved: Uncommitted files list (for HALT-AND-ASK verdict).
        user_questions: Bullet list of user-arbitration questions (for HALT-AND-ASK verdict).
        carry_over: Carry-over to next iteration (empty string = "none").

    Returns:
        A Markdown string conforming to the iter-shipped template in autopilot.md.
    """
    lines: list[str] = [
        f"# Autopilot iter {iteration} — shipped",
        "",
        f"**Run timestamp:** {run_timestamp}",
        f"**Iteration:** {iteration}",
        f"**Date:** {date}",
        f"**Verdict from queue-pick:** {verdict}",
    ]

    if verdict == "PROCEED":
        lines.append("")
        lines.append("## Task shipped (if PROCEED)")
        lines.append(f"- **Task:** {task_shipped or 'unknown'}")
        lines.append(f"- **Cycles:** {cycles if cycles is not None else 1}")
        lines.append(f"- **Final commit:** {commit_sha or 'unknown'} on `design_branch`")
        files_str = ", ".join(files_touched) if files_touched else "none"
        lines.append(f"- **Files touched:** {files_str}")
        lines.append(f"- **Auditor verdict:** {auditor_verdict or 'PASS'}")
        rv = reviewer_verdicts or {}
        sr_dev = rv.get("sr-dev", "SHIP")
        sr_sdet = rv.get("sr-sdet", "SHIP")
        security = rv.get("security", "SHIP")
        dependency = rv.get("dependency", "SHIP")
        lines.append(
            f"- **Reviewer verdicts:** sr-dev={sr_dev}, sr-sdet={sr_sdet}, "
            f"security={security}, dependency={dependency}"
        )
        lines.append(f"- **KDR additions (if any):** {kdr_additions or 'none'}")

    elif verdict == "NEEDS-CLEAN-TASKS":
        lines.append("")
        lines.append("## Milestone work (if NEEDS-CLEAN-TASKS)")
        lines.append(f"- **Milestone:** {clean_tasks_milestone or 'unknown'}")
        rounds_val = clean_tasks_rounds if clean_tasks_rounds is not None else 1
        lines.append(f"- **/clean-tasks rounds:** {rounds_val}")
        lines.append(f"- **Final stop verdict:** {clean_tasks_stop or 'LOW-ONLY'}")
        specs_str = ", ".join(specs_hardened) if specs_hardened else "none"
        lines.append(f"- **Specs hardened:** {specs_str}")

    elif verdict == "HALT-AND-ASK":
        lines.append("")
        lines.append("## Halt (if HALT-AND-ASK)")
        lines.append(f"- **Halt reason:** {halt_reason or 'unspecified'}")
        state_str = ", ".join(state_preserved) if state_preserved else "none"
        lines.append(f"- **State preserved:** {state_str}")
        if user_questions:
            q_str = "\n".join(f"  - {q}" for q in user_questions)
            lines.append(f"- **User-arbitration question(s):**\n{q_str}")
        else:
            lines.append("- **User-arbitration question(s):** none")

    lines.append("")
    lines.append("## Carry-over to next iteration")
    lines.append(carry_over if carry_over else "*(none)*")

    lines.append("")
    lines.append("## Telemetry summary")
    lines.append("*(retrofitted by T22 when it lands; empty at T04 land time)*")

    return "\n".join(lines) + "\n"


def parse_iter_shipped(artifact_text: str) -> dict[str, str]:
    """Parse an iter-shipped artifact Markdown string into a key→value mapping.

    Extracts each ``**Key:**`` field from the artifact text.  Values are captured
    up to the next ``**Key:**`` marker or the next ``##`` section header, whichever
    comes first.  This is test-infrastructure parsing; it is not designed to be
    exhaustive against adversarial input.

    Args:
        artifact_text: Full text of an iter-shipped artifact Markdown file.

    Returns:
        A dict mapping each ``**Key:**`` label (without ``**`` delimiters or
        trailing ``:``) to its value string (stripped).  Section headers
        (``##`` lines) and ``-`` bullet prefixes under each key are NOT included
        as separate keys — only ``**Key:**`` pairs.
    """
    result: dict[str, str] = {}
    # Match **Key:** lines only at the top level (not inside bullet lists that start with -)
    key_re = re.compile(r"^\*\*(.+?):\*\*\s*(.*)", re.MULTILINE)
    # Section headers act as value boundaries (stop value capture at ## lines)
    section_re = re.compile(r"^##\s", re.MULTILINE)

    matches = list(key_re.finditer(artifact_text))
    section_starts = [m.start() for m in section_re.finditer(artifact_text)]

    def _next_boundary(after_pos: int, next_key_start: int | None) -> int:
        """Return the position of the earliest boundary after ``after_pos``."""
        candidates = [s for s in section_starts if s > after_pos]
        candidates_key = [next_key_start] if next_key_start is not None else []
        all_candidates = candidates + candidates_key
        if not all_candidates:
            return len(artifact_text)
        return min(all_candidates)

    for i, match in enumerate(matches):
        key = match.group(1).strip()
        inline_value = match.group(2).strip()
        next_key_start = matches[i + 1].start() if i + 1 < len(matches) else None
        boundary = _next_boundary(match.end(), next_key_start)
        between = artifact_text[match.end():boundary]
        extra = between.strip()
        value = (inline_value + ("\n" + extra if extra else "")).strip()
        result[key] = value
    return result


def build_queue_pick_spawn_prompt(
    recommendation_file_path: str,
    project_context_brief: str,
    latest_iter_shipped: str,
    latest_iter_shipped_path: str,
) -> str:
    """Construct an iter-N (N ≥ 2) queue-pick spawn prompt with the latest iter-shipped artifact.

    Implements the read-only-latest-shipped rule from ``.claude/commands/autopilot.md``
    §Step A: iteration N+1's queue-pick spawn reads the most recent
    ``iter_<M>-shipped.md`` for context on what the prior iteration delivered.
    No prior iteration's chat history is carried.

    This is the cross-task analogue of :func:`build_builder_spawn_prompt_cycle_n`
    (T03's in-task rule).  The production rule runs as markdown-prose logic inside
    autopilot.md; this Python implementation lets tests exercise it without live
    agent spawns.

    Args:
        recommendation_file_path: Path where the queue-pick agent should write
            its recommendation.
        project_context_brief: Verbatim project context brief.
        latest_iter_shipped: Full content of the most recent iter-shipped artifact.
        latest_iter_shipped_path: Repo-relative path of the most recent iter-shipped
            artifact (e.g. ``"runs/autopilot-20260427T152243Z-iter1-shipped.md"``).

    Returns:
        A spawn-prompt string for the roadmap-selector on iteration N ≥ 2.
        Its token count should be bounded (O(1) with respect to iteration count)
        because the iter-shipped artifact is a structured projection of the prior
        iteration's work — not a verbatim replay of the orchestrator's chat history.
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
        f"Recommendation file path: {recommendation_file_path}\n\n"
        f"## Project context brief\n\n{project_context_brief}\n\n"
        f"## Prior iteration summary ({latest_iter_shipped_path})\n\n"
        f"(Read-only-latest-shipped rule: only the most recent iter-shipped artifact is "
        f"provided; prior iterations' chat history is NOT carried forward.)\n\n"
        f"{latest_iter_shipped}\n\n"
        f"## Output budget\n\n{budget_directive}\n\n"
        f"## Return schema\n\n{schema_reminder}\n"
    )
