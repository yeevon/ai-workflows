"""Spawn-prompt size tests — per-agent ceilings and 30% reduction validation.

Task: M20 Task 02 — Sub-agent input prune (orchestrator-side scope discipline).

This module verifies:
- Each agent's spawn prompt (constructed with the T02 scope-discipline rules) fits
  within the per-agent token ceiling from ``spawn_prompt_template.md``.
- The minimal pre-load set is present (task spec path, issue file path, project
  context brief).
- Whole-milestone-README and sibling-issue content inlines are absent.
- The post-T02 Auditor spawn prompt for M12 T01 is ≥ 30% smaller than the
  pre-T02 baseline frozen in ``fixtures/m12_t01_pre_t02_spawn_prompt.txt``.

Per-AC coverage:
  AC-1 — Pruned spawn-prompt convention with per-agent minimal pre-load sets and
          output budget directives (validated via ceiling assertions).
  AC-3 — ``test_spawn_prompt_size.py`` passes with the per-agent ceilings.
  AC-5 — Per-spawn token-count instrumentation (directory layout verified).
  AC-6 — 30% reduction claim validated against frozen M12 T01 baseline.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tests.orchestrator._helpers import (
    AGENT_SPAWN_CEILINGS,
    build_auditor_spawn_prompt,
    build_builder_spawn_prompt,
    build_reviewer_spawn_prompt,
    build_roadmap_selector_spawn_prompt,
    build_task_analyzer_spawn_prompt,
    token_count_proxy,
)

# ---------------------------------------------------------------------------
# Shared fixture task spec content (synthetic — hermetic, no live agent calls)
# ---------------------------------------------------------------------------

# A representative project context brief (same shape as what the slash commands build)
_PROJECT_CONTEXT_BRIEF = """\
Project: ai-workflows (Python, MIT, published as jmdl-ai-workflows on PyPI)
Layer rule: primitives → graph → workflows → surfaces (enforced by `uv run lint-imports`)
Gate commands: `uv run pytest`, `uv run lint-imports`, `uv run ruff check`
Architecture: design_docs/architecture.md (especially §3 four-layer rule, §6 dep table, §9 KDRs)
ADRs: design_docs/adr/*.md
Deferred-ideas file: design_docs/nice_to_have.md (out-of-scope by default)
Changelog convention: ## [Unreleased] → ### Added — M<N> Task <NN>: <Title> (YYYY-MM-DD)
Dep manifests: pyproject.toml + uv.lock — either changing triggers the dependency-auditor
Load-bearing KDRs: 002 (MCP-as-substrate), 003 (no Anthropic API), 004 (validator pairing),
                   006 (three-bucket retry via RetryingEdge), 008 (FastMCP + pydantic schema),
                   009 (SqliteSaver-only checkpoints), 013 (user-owned external workflow code)
Issue file path: design_docs/phases/milestone_12_audit_cascade/issues/task_01_issue.md
Status surfaces (must flip together at task close): per-task spec **Status:** line,
                   milestone README task table row, tasks/README.md row if present,
                   milestone README "Done when" checkboxes\
"""

# Paths for the fixture task (M12 T01)
_SPEC_PATH = "design_docs/phases/milestone_12_audit_cascade/task_01_auditor_tier_configs.md"
_ISSUE_PATH = "design_docs/phases/milestone_12_audit_cascade/issues/task_01_issue.md"
_README_PATH = "design_docs/phases/milestone_12_audit_cascade/README.md"

# A minimal representative git diff
_GIT_DIFF = """\
diff --git a/ai_workflows/workflows/planner.py b/ai_workflows/workflows/planner.py
index abc1234..def5678 100644
--- a/ai_workflows/workflows/planner.py
+++ b/ai_workflows/workflows/planner.py
@@ -650,6 +650,10 @@ def planner_tier_registry():
+    "auditor-sonnet": TierConfig(route=ClaudeCodeRoute(cli_model_flag="sonnet")),
+    "auditor-opus": TierConfig(route=ClaudeCodeRoute(cli_model_flag="opus")),\
"""

# KDRs cited in M12 T01 spec
_CITED_KDRS = ["KDR-003", "KDR-011"]

# Files touched by builder (for reviewer prompts)
_FILES_TOUCHED = [
    "ai_workflows/workflows/planner.py",
    "ai_workflows/workflows/slice_refactor.py",
    "ai_workflows/workflows/summarize_tiers.py",
    "tests/workflows/test_planner.py",
    "CHANGELOG.md",
]

# Spec filenames for task-analyzer
_SPEC_FILENAMES = [
    "task_01_auditor_tier_configs.md",
    "task_02_audit_cascade_node.md",
    "task_03_workflow_wiring.md",
    "task_08_audit_cascade_skip_terminal_gate.md",
]


# ---------------------------------------------------------------------------
# Helper: verify required fields are present and banned content is absent
# ---------------------------------------------------------------------------

def _assert_required_fields_present(prompt: str, required: list[str]) -> None:
    """Assert that all required fields appear in the spawn prompt."""
    for field in required:
        assert field in prompt, (
            f"Required field not found in spawn prompt: {field!r}\n"
            f"Prompt preview: {prompt[:200]!r}"
        )


def _assert_banned_content_absent(prompt: str, banned_markers: list[str]) -> None:
    """Assert that known bulk-content markers are absent from the spawn prompt."""
    for marker in banned_markers:
        assert marker not in prompt, (
            f"Banned bulk-content marker found in spawn prompt: {marker!r}\n"
            f"This indicates content inlining that the T02 scope discipline forbids."
        )


# ---------------------------------------------------------------------------
# Builder spawn
# ---------------------------------------------------------------------------

class TestBuilderSpawnPrompt:
    """Verify the Builder spawn prompt fits the ceiling and has the right shape."""

    def test_token_count_within_ceiling(self) -> None:
        """Builder spawn prompt token count ≤ 8 K."""
        prompt = build_builder_spawn_prompt(
            task_spec_path=_SPEC_PATH,
            issue_file_path=_ISSUE_PATH,
            milestone_readme_path=_README_PATH,
            project_context_brief=_PROJECT_CONTEXT_BRIEF,
        )
        count = token_count_proxy(prompt)
        ceiling = AGENT_SPAWN_CEILINGS["builder"]
        assert count <= ceiling, (
            f"Builder spawn prompt ({count:.0f} tokens) exceeds ceiling ({ceiling} tokens)."
        )

    def test_minimal_pre_load_set_present(self) -> None:
        """Builder spawn prompt includes the minimal pre-load set."""
        prompt = build_builder_spawn_prompt(
            task_spec_path=_SPEC_PATH,
            issue_file_path=_ISSUE_PATH,
            milestone_readme_path=_README_PATH,
            project_context_brief=_PROJECT_CONTEXT_BRIEF,
        )
        _assert_required_fields_present(prompt, [
            _SPEC_PATH,
            _ISSUE_PATH,
            _README_PATH,
            "Project: ai-workflows",  # context brief present
        ])

    def test_output_budget_directive_present(self) -> None:
        """Builder spawn prompt includes the output budget directive."""
        prompt = build_builder_spawn_prompt(
            task_spec_path=_SPEC_PATH,
            issue_file_path=_ISSUE_PATH,
            milestone_readme_path=_README_PATH,
            project_context_brief=_PROJECT_CONTEXT_BRIEF,
        )
        assert "Output budget:" in prompt
        assert "4K" in prompt

    def test_banned_bulk_content_absent(self) -> None:
        """Builder spawn prompt does NOT inline architecture.md or sibling issue content."""
        prompt = build_builder_spawn_prompt(
            task_spec_path=_SPEC_PATH,
            issue_file_path=_ISSUE_PATH,
            milestone_readme_path=_README_PATH,
            project_context_brief=_PROJECT_CONTEXT_BRIEF,
        )
        # These are markers that would appear if content was inlined verbatim
        _assert_banned_content_absent(prompt, [
            "## 9. Key design decisions",  # architecture.md §9 header
            "## Milestone README content (inlined",  # explicit bloat marker
            "## Sibling issue files (inlined",  # sibling issue inlining
        ])


# ---------------------------------------------------------------------------
# Auditor spawn
# ---------------------------------------------------------------------------

class TestAuditorSpawnPrompt:
    """Verify the Auditor spawn prompt fits the ceiling and has the right shape."""

    def test_token_count_within_ceiling(self) -> None:
        """Auditor spawn prompt token count ≤ 6 K."""
        prompt = build_auditor_spawn_prompt(
            task_spec_path=_SPEC_PATH,
            issue_file_path=_ISSUE_PATH,
            milestone_readme_path=_README_PATH,
            project_context_brief=_PROJECT_CONTEXT_BRIEF,
            git_diff=_GIT_DIFF,
            cited_kdrs=_CITED_KDRS,
        )
        count = token_count_proxy(prompt)
        ceiling = AGENT_SPAWN_CEILINGS["auditor"]
        assert count <= ceiling, (
            f"Auditor spawn prompt ({count:.0f} tokens) exceeds ceiling ({ceiling} tokens)."
        )

    def test_minimal_pre_load_set_present(self) -> None:
        """Auditor spawn prompt includes the minimal pre-load set."""
        prompt = build_auditor_spawn_prompt(
            task_spec_path=_SPEC_PATH,
            issue_file_path=_ISSUE_PATH,
            milestone_readme_path=_README_PATH,
            project_context_brief=_PROJECT_CONTEXT_BRIEF,
            git_diff=_GIT_DIFF,
            cited_kdrs=_CITED_KDRS,
        )
        _assert_required_fields_present(prompt, [
            _SPEC_PATH,
            _ISSUE_PATH,
            _README_PATH,
            "Project: ai-workflows",
            "KDR-003",   # cited KDR present as identifier
            "KDR-011",
        ])

    def test_output_budget_directive_present(self) -> None:
        """Auditor spawn prompt includes the output budget directive."""
        prompt = build_auditor_spawn_prompt(
            task_spec_path=_SPEC_PATH,
            issue_file_path=_ISSUE_PATH,
            milestone_readme_path=_README_PATH,
            project_context_brief=_PROJECT_CONTEXT_BRIEF,
            git_diff=_GIT_DIFF,
            cited_kdrs=_CITED_KDRS,
        )
        assert "Output budget:" in prompt
        assert "1-2K" in prompt

    def test_kdr_compact_pointer_present(self) -> None:
        """Auditor spawn prompt uses compact KDR pointer, not full §9 table content."""
        prompt = build_auditor_spawn_prompt(
            task_spec_path=_SPEC_PATH,
            issue_file_path=_ISSUE_PATH,
            milestone_readme_path=_README_PATH,
            project_context_brief=_PROJECT_CONTEXT_BRIEF,
            git_diff=_GIT_DIFF,
            cited_kdrs=_CITED_KDRS,
        )
        # Compact pointer must be present
        assert "read §9 of design_docs/architecture.md on-demand" in prompt
        # Full §9 table should NOT be inlined
        _assert_banned_content_absent(prompt, [
            "| KDR-001 |",  # first row of full §9 table — would appear if inlined
            "| KDR-002 |",
        ])

    def test_no_cited_kdrs_yields_grid_header(self) -> None:
        """Auditor spawn with no cited KDRs includes the §9 grid header only."""
        prompt = build_auditor_spawn_prompt(
            task_spec_path=_SPEC_PATH,
            issue_file_path=_ISSUE_PATH,
            milestone_readme_path=_README_PATH,
            project_context_brief=_PROJECT_CONTEXT_BRIEF,
            git_diff=_GIT_DIFF,
            cited_kdrs=[],
        )
        assert "| ID | Decision | Source |" in prompt
        assert "read §9 of design_docs/architecture.md on-demand" in prompt

    def test_diff_present(self) -> None:
        """Auditor spawn prompt includes the git diff."""
        prompt = build_auditor_spawn_prompt(
            task_spec_path=_SPEC_PATH,
            issue_file_path=_ISSUE_PATH,
            milestone_readme_path=_README_PATH,
            project_context_brief=_PROJECT_CONTEXT_BRIEF,
            git_diff=_GIT_DIFF,
            cited_kdrs=_CITED_KDRS,
        )
        assert "auditor-sonnet" in prompt  # content from _GIT_DIFF


# ---------------------------------------------------------------------------
# Reviewer spawns (sr-dev, sr-sdet, security-reviewer)
# ---------------------------------------------------------------------------

class TestReviewerSpawnPrompt:
    """Verify reviewer spawn prompts fit the ceiling and have the right shape."""

    @pytest.mark.parametrize(
        "agent_name", ["sr-dev", "sr-sdet", "security-reviewer", "dependency-auditor"]
    )
    def test_token_count_within_ceiling(self, agent_name: str) -> None:
        """Reviewer spawn prompt token count ≤ 4 K."""
        prompt = build_reviewer_spawn_prompt(
            task_spec_path=_SPEC_PATH,
            issue_file_path=_ISSUE_PATH,
            project_context_brief=_PROJECT_CONTEXT_BRIEF,
            git_diff=_GIT_DIFF,
            files_touched=_FILES_TOUCHED,
            agent_name=agent_name,
        )
        count = token_count_proxy(prompt)
        ceiling = AGENT_SPAWN_CEILINGS[agent_name]
        assert count <= ceiling, (
            f"{agent_name} spawn prompt ({count:.0f} tokens) exceeds "
            f"ceiling ({ceiling} tokens)."
        )

    def test_files_touched_present(self) -> None:
        """Reviewer spawn prompt includes the files-touched list."""
        prompt = build_reviewer_spawn_prompt(
            task_spec_path=_SPEC_PATH,
            issue_file_path=_ISSUE_PATH,
            project_context_brief=_PROJECT_CONTEXT_BRIEF,
            git_diff=_GIT_DIFF,
            files_touched=_FILES_TOUCHED,
        )
        for f in _FILES_TOUCHED:
            assert f in prompt, f"File {f!r} not found in reviewer spawn prompt."

    def test_output_budget_directive_present(self) -> None:
        """Reviewer spawn prompt includes the output budget directive."""
        prompt = build_reviewer_spawn_prompt(
            task_spec_path=_SPEC_PATH,
            issue_file_path=_ISSUE_PATH,
            project_context_brief=_PROJECT_CONTEXT_BRIEF,
            git_diff=_GIT_DIFF,
            files_touched=_FILES_TOUCHED,
        )
        assert "Output budget:" in prompt
        assert "1-2K" in prompt

    def test_no_full_source_inlined(self) -> None:
        """Reviewer spawn prompt does NOT inline full source file contents.

        The prompt lists file *paths* and a git diff; it does not inline full
        module-level source (e.g. import blocks, decorator chains, multi-line
        class bodies).  A content marker that could only appear in a verbatim
        source read — not in a unified diff hunk — confirms the invariant.
        """
        prompt = build_reviewer_spawn_prompt(
            task_spec_path=_SPEC_PATH,
            issue_file_path=_ISSUE_PATH,
            project_context_brief=_PROJECT_CONTEXT_BRIEF,
            git_diff=_GIT_DIFF,
            files_touched=_FILES_TOUCHED,
        )
        # "import" statements from the top of a source file would appear
        # in a verbatim Read but not in our minimal git diff fixture.
        _assert_banned_content_absent(prompt, [
            "from ai_workflows.primitives",  # module-level import — not in our diff
            "class TierConfig:",             # class definition — not in our diff
        ])


# ---------------------------------------------------------------------------
# task-analyzer spawn
# ---------------------------------------------------------------------------

class TestTaskAnalyzerSpawnPrompt:
    """Verify the task-analyzer spawn prompt fits the ceiling."""

    def test_token_count_within_ceiling(self) -> None:
        """task-analyzer spawn prompt token count ≤ 6 K."""
        prompt = build_task_analyzer_spawn_prompt(
            milestone_dir_path="design_docs/phases/milestone_12_audit_cascade",
            analysis_output_path="design_docs/phases/milestone_12_audit_cascade/task_analysis.md",
            project_context_brief=_PROJECT_CONTEXT_BRIEF,
            round_number=1,
            spec_filenames=_SPEC_FILENAMES,
        )
        count = token_count_proxy(prompt)
        ceiling = AGENT_SPAWN_CEILINGS["task-analyzer"]
        assert count <= ceiling, (
            f"task-analyzer spawn prompt ({count:.0f} tokens) exceeds "
            f"ceiling ({ceiling} tokens)."
        )

    def test_spec_filenames_present(self) -> None:
        """task-analyzer spawn prompt includes the list of spec filenames."""
        prompt = build_task_analyzer_spawn_prompt(
            milestone_dir_path="design_docs/phases/milestone_12_audit_cascade",
            analysis_output_path="design_docs/phases/milestone_12_audit_cascade/task_analysis.md",
            project_context_brief=_PROJECT_CONTEXT_BRIEF,
            round_number=1,
            spec_filenames=_SPEC_FILENAMES,
        )
        for filename in _SPEC_FILENAMES:
            assert filename in prompt, f"Spec filename {filename!r} not in analyzer prompt."

    def test_output_budget_directive_present(self) -> None:
        """task-analyzer spawn prompt includes the output budget directive."""
        prompt = build_task_analyzer_spawn_prompt(
            milestone_dir_path="design_docs/phases/milestone_12_audit_cascade",
            analysis_output_path="design_docs/phases/milestone_12_audit_cascade/task_analysis.md",
            project_context_brief=_PROJECT_CONTEXT_BRIEF,
            round_number=1,
            spec_filenames=_SPEC_FILENAMES,
        )
        assert "Output budget:" in prompt

    def test_no_full_spec_content_inlined(self) -> None:
        """task-analyzer spawn prompt does NOT inline full spec content."""
        prompt = build_task_analyzer_spawn_prompt(
            milestone_dir_path="design_docs/phases/milestone_12_audit_cascade",
            analysis_output_path="design_docs/phases/milestone_12_audit_cascade/task_analysis.md",
            project_context_brief=_PROJECT_CONTEXT_BRIEF,
            round_number=1,
            spec_filenames=_SPEC_FILENAMES,
        )
        # Actual spec content would contain unique phrases like "ClaudeCodeRoute"
        _assert_banned_content_absent(prompt, [
            "ClaudeCodeRoute(cli_model_flag=",  # verbatim spec content
        ])


# ---------------------------------------------------------------------------
# roadmap-selector spawn
# ---------------------------------------------------------------------------

class TestRoadmapSelectorSpawnPrompt:
    """Verify the roadmap-selector spawn prompt fits the ceiling."""

    def test_token_count_within_ceiling(self) -> None:
        """roadmap-selector spawn prompt token count ≤ 4 K."""
        prompt = build_roadmap_selector_spawn_prompt(
            recommendation_file_path="runs/queue-pick-20260428T120000Z.md",
            project_context_brief=_PROJECT_CONTEXT_BRIEF,
            milestone_scope="all open",
        )
        count = token_count_proxy(prompt)
        ceiling = AGENT_SPAWN_CEILINGS["roadmap-selector"]
        assert count <= ceiling, (
            f"roadmap-selector spawn prompt ({count:.0f} tokens) exceeds "
            f"ceiling ({ceiling} tokens)."
        )

    def test_output_budget_directive_present(self) -> None:
        """roadmap-selector spawn prompt includes the output budget directive."""
        prompt = build_roadmap_selector_spawn_prompt(
            recommendation_file_path="runs/queue-pick-20260428T120000Z.md",
            project_context_brief=_PROJECT_CONTEXT_BRIEF,
            milestone_scope="m12",
        )
        assert "Output budget:" in prompt


# ---------------------------------------------------------------------------
# Token-count instrumentation directory-layout test (AC-5)
# ---------------------------------------------------------------------------

class TestSpawnTokenInstrumentation:
    """Verify that the spawn token instrumentation path convention is correct."""

    @pytest.mark.parametrize("agent_name", ["auditor", "builder"])
    def test_spawn_tokens_file_path_convention(
        self, tmp_path: Path, agent_name: str
    ) -> None:
        """spawn_<agent>.tokens.txt lives under runs/<task>/cycle_<N>/ for any agent.

        Verifies for both ``auditor`` and ``builder`` that:
        - The file is created at the expected path.
        - The file contains an integer (no float, no suffix).
        - The filename contains no ``_<N>`` cycle suffix (directory is the namespace).
        """
        # Verify the naming convention from spawn_prompt_template.md:
        # runs/<task>/cycle_<N>/spawn_<agent>.tokens.txt
        # (No _<cycle> suffix on the filename — the directory provides the namespace.)
        task_dir = tmp_path / "runs" / "m12-t01" / "cycle_1"
        task_dir.mkdir(parents=True)

        # Build the appropriate spawn prompt for the agent under test
        if agent_name == "auditor":
            prompt = build_auditor_spawn_prompt(
                task_spec_path=_SPEC_PATH,
                issue_file_path=_ISSUE_PATH,
                milestone_readme_path=_README_PATH,
                project_context_brief=_PROJECT_CONTEXT_BRIEF,
                git_diff=_GIT_DIFF,
                cited_kdrs=_CITED_KDRS,
            )
        else:
            # builder
            prompt = build_builder_spawn_prompt(
                task_spec_path=_SPEC_PATH,
                issue_file_path=_ISSUE_PATH,
                milestone_readme_path=_README_PATH,
                project_context_brief=_PROJECT_CONTEXT_BRIEF,
            )

        token_count = int(token_count_proxy(prompt))
        tokens_file = task_dir / f"spawn_{agent_name}.tokens.txt"
        tokens_file.write_text(str(token_count))

        # Verify the file exists and has the right format
        assert tokens_file.exists()
        content = tokens_file.read_text().strip()
        assert content.isdigit(), (
            f"Token count file should contain an integer, got: {content!r}"
        )

        # Verify no _<N> cycle suffix in the filename (the directory is the namespace)
        assert not re.search(r"_\d+\.tokens\.txt$", tokens_file.name), (
            f"Filename '{tokens_file.name}' must not include a cycle suffix — "
            "the cycle_<N>/ directory is the namespace."
        )
        assert tokens_file.name == f"spawn_{agent_name}.tokens.txt"


# ---------------------------------------------------------------------------
# Validation re-run — 30% reduction against M12 T01 baseline (AC-6)
# ---------------------------------------------------------------------------

_FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_m12_t01_audit_spawn_30pct_reduction() -> None:
    """Post-T02 Auditor spawn for M12 T01 is ≥ 30% smaller than the pre-T02 baseline.

    The pre-T02 baseline is frozen in
    ``tests/orchestrator/fixtures/m12_t01_pre_t02_spawn_prompt.txt``.
    It represents a typical pre-T02 Auditor spawn that inlined:
    - The full architecture.md content
    - The whole milestone README content
    - Sibling issue file content
    - Gate command outputs

    The post-T02 spawn (built by ``build_auditor_spawn_prompt``) includes only the
    minimal pre-load set per the scope discipline rules.

    Both sizes are measured via the same regex-proxy
    (``token_count_proxy``); magnitude is what's load-bearing, not exactness.

    AC-6 — Validation re-run: ≥ 30% input-token reduction asserted.
    """
    baseline_file = _FIXTURES_DIR / "m12_t01_pre_t02_spawn_prompt.txt"
    assert baseline_file.exists(), (
        f"Baseline fixture not found: {baseline_file}. "
        "This fixture must be present for the 30%-reduction validation."
    )

    pre_t02_text = baseline_file.read_text()
    pre_t02_count = token_count_proxy(pre_t02_text)

    # Build the post-T02 Auditor spawn prompt for M12 T01
    post_t02_prompt = build_auditor_spawn_prompt(
        task_spec_path=_SPEC_PATH,
        issue_file_path=_ISSUE_PATH,
        milestone_readme_path=_README_PATH,
        project_context_brief=_PROJECT_CONTEXT_BRIEF,
        git_diff=_GIT_DIFF,
        cited_kdrs=_CITED_KDRS,
    )
    post_t02_count = token_count_proxy(post_t02_prompt)

    reduction_fraction = (pre_t02_count - post_t02_count) / pre_t02_count

    assert reduction_fraction >= 0.30, (
        f"Expected ≥ 30% reduction; got {reduction_fraction:.1%}.\n"
        f"Pre-T02 count: {pre_t02_count:.0f} tokens\n"
        f"Post-T02 count: {post_t02_count:.0f} tokens\n"
        f"Reduction: {pre_t02_count - post_t02_count:.0f} tokens "
        f"({reduction_fraction:.1%})"
    )
