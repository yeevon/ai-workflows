"""Hermetic tests for stable-prefix construction discipline.

Task: M20 Task 23 — Cache-breakpoint discipline.
Relationship: Tests that spawn prompts constructed by the helpers in
  ``tests/orchestrator/_helpers.py`` and manually-constructed prompts
  comply with the stable-prefix rules documented in
  ``.claude/commands/_common/spawn_prompt_template.md``
  §Stable-prefix discipline.

ACs covered:
- AC-6: Constructed spawn prompts have no timestamps, UUIDs, hostname strings
        in the prefix segment.
- AC-6: Stable prefix and dynamic context are separated by ``\\n\\n``.
- AC-6: Per-call values (timestamps, UUIDs, run IDs) appear only after the
        stable prefix boundary.
"""

from __future__ import annotations

import re
import socket
import uuid
from datetime import UTC, datetime

from tests.orchestrator._helpers import (
    build_auditor_spawn_prompt,
    build_builder_spawn_prompt,
    build_reviewer_spawn_prompt,
    build_roadmap_selector_spawn_prompt,
    build_task_analyzer_spawn_prompt,
)

# ---------------------------------------------------------------------------
# Helpers — test utilities
# ---------------------------------------------------------------------------

# Regex patterns for per-request dynamic values that MUST NOT appear in the
# stable prefix segment (the content before the first \n\n boundary).
_ISO_TIMESTAMP_RE = re.compile(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}"
)
_UUID_RE = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
    re.IGNORECASE,
)
_HOSTNAME = socket.gethostname()


def _stable_prefix(prompt: str) -> str:
    """Extract the stable prefix from a spawn prompt.

    The stable prefix is the portion before the first ``\\n\\n`` boundary.
    Returns the whole prompt if no ``\\n\\n`` is found (so the boundary test
    catches it).

    Args:
        prompt: Full spawn prompt string.

    Returns:
        The prefix segment (may be empty if the prompt starts with ``\\n\\n``).
    """
    if "\n\n" in prompt:
        return prompt.split("\n\n", 1)[0]
    return prompt


def _dynamic_context(prompt: str) -> str:
    """Extract the dynamic context from a spawn prompt.

    Returns everything after the first ``\\n\\n`` boundary.  Returns empty
    string if no boundary is present.

    Args:
        prompt: Full spawn prompt string.

    Returns:
        The dynamic context segment (may be empty).
    """
    if "\n\n" in prompt:
        return prompt.split("\n\n", 1)[1]
    return ""


# ---------------------------------------------------------------------------
# Fixtures — canonical project context brief (static, no runtime values)
# ---------------------------------------------------------------------------

_STATIC_BRIEF = (
    "Project: ai-workflows (Python, MIT, published as jmdl-ai-workflows on PyPI)\n"
    "Layer rule: primitives → graph → workflows → surfaces\n"
    "Gate commands: uv run pytest, uv run lint-imports, uv run ruff check\n"
    "Architecture: design_docs/architecture.md\n"
    "Load-bearing KDRs: 002, 003, 004, 006, 008, 009, 013\n"
    "Issue file path: design_docs/phases/milestone_12_foo/issues/task_01_issue.md\n"
    "Status surfaces: per-task spec Status line, milestone README task table row\n"
)

_TASK_SPEC_PATH = "design_docs/phases/milestone_12_foo/task_01_bar.md"
_ISSUE_FILE_PATH = "design_docs/phases/milestone_12_foo/issues/task_01_issue.md"
_MILESTONE_README_PATH = "design_docs/phases/milestone_12_foo/README.md"
_STATIC_DIFF = "--- a/foo.py\n+++ b/foo.py\n@@ -1,1 +1,1 @@\n-old\n+new"


# ---------------------------------------------------------------------------
# Tests — builder spawn prompt
# ---------------------------------------------------------------------------


class TestBuilderSpawnPromptStablePrefix:
    """Stable-prefix discipline for Builder spawn prompts."""

    def test_no_iso_timestamp_in_prefix(self) -> None:
        """Builder spawn prompt's stable prefix must not contain ISO timestamps."""
        prompt = build_builder_spawn_prompt(
            task_spec_path=_TASK_SPEC_PATH,
            issue_file_path=_ISSUE_FILE_PATH,
            milestone_readme_path=_MILESTONE_README_PATH,
            project_context_brief=_STATIC_BRIEF,
        )
        prefix = _stable_prefix(prompt)
        assert not _ISO_TIMESTAMP_RE.search(prefix), (
            f"ISO timestamp found in stable prefix: {_ISO_TIMESTAMP_RE.search(prefix).group()}"
        )

    def test_no_uuid_in_prefix(self) -> None:
        """Builder spawn prompt's stable prefix must not contain UUIDs."""
        prompt = build_builder_spawn_prompt(
            task_spec_path=_TASK_SPEC_PATH,
            issue_file_path=_ISSUE_FILE_PATH,
            milestone_readme_path=_MILESTONE_README_PATH,
            project_context_brief=_STATIC_BRIEF,
        )
        prefix = _stable_prefix(prompt)
        assert not _UUID_RE.search(prefix), (
            f"UUID found in stable prefix: {_UUID_RE.search(prefix).group()}"
        )

    def test_no_hostname_in_prefix(self) -> None:
        """Builder spawn prompt's stable prefix must not contain the machine hostname."""
        prompt = build_builder_spawn_prompt(
            task_spec_path=_TASK_SPEC_PATH,
            issue_file_path=_ISSUE_FILE_PATH,
            milestone_readme_path=_MILESTONE_README_PATH,
            project_context_brief=_STATIC_BRIEF,
        )
        prefix = _stable_prefix(prompt)
        # Only check if hostname is non-trivial (not "localhost")
        if _HOSTNAME and _HOSTNAME not in ("localhost", ""):
            assert _HOSTNAME not in prefix, (
                f"Hostname '{_HOSTNAME}' found in stable prefix"
            )

    def test_hardcoded_hostname_never_appears_in_builder_prefix(self) -> None:
        """Builder prompt builders must not embed a hardcoded hostname string.

        Verifies the 'no hostname in prefix' rule does not regress when the runtime
        hostname is 'localhost' (common in Docker/CI containers) — by constructing a
        project-context brief that contains a representative hostname literal and
        asserting it does not appear in the stable-prefix segment produced by the
        builder.  The builder must not call ``socket.gethostname()`` nor embed any
        host-derived value before the ``\\n\\n`` boundary.
        """
        # Use a synthetic brief with NO hostname value injected by the caller.
        # The builder itself must not inject one either.
        representative_hostname = "ci-runner-node-42.example.com"
        # Confirm this string is NOT in the static brief (so the builder can't inherit it).
        assert representative_hostname not in _STATIC_BRIEF

        prompt = build_builder_spawn_prompt(
            task_spec_path=_TASK_SPEC_PATH,
            issue_file_path=_ISSUE_FILE_PATH,
            milestone_readme_path=_MILESTONE_README_PATH,
            project_context_brief=_STATIC_BRIEF,
        )
        prefix = _stable_prefix(prompt)
        assert representative_hostname not in prefix, (
            "Builder must not embed a hardcoded hostname in the stable prefix"
        )

    def test_stable_dynamic_separated_by_double_newline(self) -> None:
        """Stable prefix and dynamic context are separated by \\n\\n."""
        prompt = build_builder_spawn_prompt(
            task_spec_path=_TASK_SPEC_PATH,
            issue_file_path=_ISSUE_FILE_PATH,
            milestone_readme_path=_MILESTONE_README_PATH,
            project_context_brief=_STATIC_BRIEF,
        )
        assert "\n\n" in prompt, "Spawn prompt must contain \\n\\n boundary"


# ---------------------------------------------------------------------------
# Tests — auditor spawn prompt
# ---------------------------------------------------------------------------


class TestAuditorSpawnPromptStablePrefix:
    """Stable-prefix discipline for Auditor spawn prompts."""

    def test_no_iso_timestamp_in_prefix(self) -> None:
        """Auditor spawn prompt's stable prefix must not contain ISO timestamps."""
        prompt = build_auditor_spawn_prompt(
            task_spec_path=_TASK_SPEC_PATH,
            issue_file_path=_ISSUE_FILE_PATH,
            milestone_readme_path=_MILESTONE_README_PATH,
            project_context_brief=_STATIC_BRIEF,
            git_diff=_STATIC_DIFF,
            cited_kdrs=["KDR-003", "KDR-013"],
        )
        prefix = _stable_prefix(prompt)
        assert not _ISO_TIMESTAMP_RE.search(prefix)

    def test_no_uuid_in_prefix(self) -> None:
        """Auditor spawn prompt's stable prefix must not contain UUIDs."""
        prompt = build_auditor_spawn_prompt(
            task_spec_path=_TASK_SPEC_PATH,
            issue_file_path=_ISSUE_FILE_PATH,
            milestone_readme_path=_MILESTONE_README_PATH,
            project_context_brief=_STATIC_BRIEF,
            git_diff=_STATIC_DIFF,
            cited_kdrs=["KDR-003"],
        )
        prefix = _stable_prefix(prompt)
        assert not _UUID_RE.search(prefix)

    def test_has_double_newline_boundary(self) -> None:
        """Auditor prompt contains \\n\\n boundary between prefix and dynamic context."""
        prompt = build_auditor_spawn_prompt(
            task_spec_path=_TASK_SPEC_PATH,
            issue_file_path=_ISSUE_FILE_PATH,
            milestone_readme_path=_MILESTONE_README_PATH,
            project_context_brief=_STATIC_BRIEF,
            git_diff=_STATIC_DIFF,
            cited_kdrs=[],
        )
        assert "\n\n" in prompt


# ---------------------------------------------------------------------------
# Tests — reviewer spawn prompts (sr-dev / sr-sdet / security-reviewer)
# ---------------------------------------------------------------------------


class TestReviewerSpawnPromptStablePrefix:
    """Stable-prefix discipline for reviewer spawn prompts."""

    def test_no_iso_timestamp_in_prefix(self) -> None:
        prompt = build_reviewer_spawn_prompt(
            task_spec_path=_TASK_SPEC_PATH,
            issue_file_path=_ISSUE_FILE_PATH,
            project_context_brief=_STATIC_BRIEF,
            git_diff=_STATIC_DIFF,
            files_touched=["scripts/orchestration/cache_verify.py"],
            agent_name="sr-dev",
        )
        prefix = _stable_prefix(prompt)
        assert not _ISO_TIMESTAMP_RE.search(prefix)

    def test_no_uuid_in_prefix(self) -> None:
        prompt = build_reviewer_spawn_prompt(
            task_spec_path=_TASK_SPEC_PATH,
            issue_file_path=_ISSUE_FILE_PATH,
            project_context_brief=_STATIC_BRIEF,
            git_diff=_STATIC_DIFF,
            files_touched=["scripts/orchestration/cache_verify.py"],
            agent_name="sr-sdet",
        )
        prefix = _stable_prefix(prompt)
        assert not _UUID_RE.search(prefix)

    def test_has_double_newline_boundary(self) -> None:
        prompt = build_reviewer_spawn_prompt(
            task_spec_path=_TASK_SPEC_PATH,
            issue_file_path=_ISSUE_FILE_PATH,
            project_context_brief=_STATIC_BRIEF,
            git_diff=_STATIC_DIFF,
            files_touched=[],
            agent_name="security-reviewer",
        )
        assert "\n\n" in prompt


# ---------------------------------------------------------------------------
# Tests — per-call values must not leak into a well-formed prompt's prefix
# ---------------------------------------------------------------------------


class TestPerCallValueIsolation:
    """Verify that injecting per-call values into the dynamic context (not the prefix)
    keeps the prefix byte-stable between spawns."""

    def _build_prompt_with_dynamic_context(
        self, stable_prefix: str, dynamic_context: str
    ) -> str:
        """Construct a spawn prompt by joining prefix + dynamic context with \\n\\n.

        This is the canonical construction pattern per §Stable-prefix discipline.
        """
        return stable_prefix + "\n\n" + dynamic_context

    def test_timestamp_in_dynamic_context_does_not_affect_prefix(self) -> None:
        """Timestamps appended after \\n\\n do not appear in the prefix segment."""
        stable = "Agent system prompt\nNon-negotiables block\nTool list"
        now = datetime.now(UTC).isoformat()
        dynamic = f"## Current time\n{now}\n\n## Task\ndo something"
        prompt = self._build_prompt_with_dynamic_context(stable, dynamic)

        prefix = _stable_prefix(prompt)
        assert not _ISO_TIMESTAMP_RE.search(prefix), (
            "Timestamp leaked into stable prefix"
        )
        # Dynamic context should contain the timestamp
        ctx = _dynamic_context(prompt)
        assert now in ctx

    def test_uuid_in_dynamic_context_does_not_affect_prefix(self) -> None:
        """UUIDs appended after \\n\\n do not appear in the prefix segment."""
        stable = "Agent system prompt\nNon-negotiables block"
        run_id = str(uuid.uuid4())
        dynamic = f"## Run ID\n{run_id}\n\n## Task diff\n+added line"
        prompt = self._build_prompt_with_dynamic_context(stable, dynamic)

        prefix = _stable_prefix(prompt)
        assert not _UUID_RE.search(prefix)
        ctx = _dynamic_context(prompt)
        assert run_id in ctx

    def test_two_prompts_with_same_stable_prefix_are_byte_identical_in_prefix(self) -> None:
        """Two spawns with the same stable prefix produce byte-identical prefix segments
        regardless of differing dynamic contexts."""
        stable = "Agent system prompt\nNon-negotiables block\nTool list"
        dynamic1 = "## Diff\n+line added in cycle 1"
        dynamic2 = "## Diff\n+line added in cycle 2"

        prompt1 = self._build_prompt_with_dynamic_context(stable, dynamic1)
        prompt2 = self._build_prompt_with_dynamic_context(stable, dynamic2)

        assert _stable_prefix(prompt1) == _stable_prefix(prompt2), (
            "Stable prefixes must be byte-identical across spawns"
        )
        assert _dynamic_context(prompt1) != _dynamic_context(prompt2), (
            "Dynamic contexts should differ (otherwise test is vacuous)"
        )

    def test_real_builder_prefix_is_byte_identical_across_two_calls(self) -> None:
        """Real ``build_builder_spawn_prompt`` produces byte-identical stable prefixes
        on two calls with identical arguments — pins the actual byte-stability property
        the cache discipline depends on."""
        prompt1 = build_builder_spawn_prompt(
            task_spec_path=_TASK_SPEC_PATH,
            issue_file_path=_ISSUE_FILE_PATH,
            milestone_readme_path=_MILESTONE_README_PATH,
            project_context_brief=_STATIC_BRIEF,
        )
        prompt2 = build_builder_spawn_prompt(
            task_spec_path=_TASK_SPEC_PATH,
            issue_file_path=_ISSUE_FILE_PATH,
            milestone_readme_path=_MILESTONE_README_PATH,
            project_context_brief=_STATIC_BRIEF,
        )
        assert _stable_prefix(prompt1) == _stable_prefix(prompt2), (
            "build_builder_spawn_prompt must produce byte-identical stable prefixes "
            "across calls with the same arguments"
        )

    def test_real_auditor_prefix_is_byte_identical_across_two_calls(self) -> None:
        """Real ``build_auditor_spawn_prompt`` produces byte-identical stable prefixes
        on two calls with identical arguments — pins the cache discipline for auditor."""
        prompt1 = build_auditor_spawn_prompt(
            task_spec_path=_TASK_SPEC_PATH,
            issue_file_path=_ISSUE_FILE_PATH,
            milestone_readme_path=_MILESTONE_README_PATH,
            project_context_brief=_STATIC_BRIEF,
            git_diff=_STATIC_DIFF,
            cited_kdrs=["KDR-003", "KDR-013"],
        )
        prompt2 = build_auditor_spawn_prompt(
            task_spec_path=_TASK_SPEC_PATH,
            issue_file_path=_ISSUE_FILE_PATH,
            milestone_readme_path=_MILESTONE_README_PATH,
            project_context_brief=_STATIC_BRIEF,
            git_diff=_STATIC_DIFF,
            cited_kdrs=["KDR-003", "KDR-013"],
        )
        assert _stable_prefix(prompt1) == _stable_prefix(prompt2), (
            "build_auditor_spawn_prompt must produce byte-identical stable prefixes "
            "across calls with the same arguments"
        )

    def test_prefix_boundary_is_first_double_newline(self) -> None:
        """The \\n\\n boundary is the first one in the prompt — prefix ends there."""
        stable = "line1\nline2"
        dynamic = "section1\n\nsection2"  # Dynamic has its own \n\n
        prompt = stable + "\n\n" + dynamic
        prefix = _stable_prefix(prompt)
        assert prefix == stable


# ---------------------------------------------------------------------------
# Tests — stable-prefix discipline rules from spawn_prompt_template.md §T23
# ---------------------------------------------------------------------------


class TestSpawnPromptTemplateRules:
    """Rule-coverage tests mapping to the four rules in §Stable-prefix discipline."""

    def test_rule1_no_per_request_strings_in_builder_prefix(self) -> None:
        """Rule 1: the builder's own stable prefix is free of ISO timestamps and UUIDs.

        Calls ``build_builder_spawn_prompt`` directly and inspects ``_stable_prefix``
        on the raw builder output — no appended dynamic section.  This proves that
        the builder itself does not emit per-request values before its first ``\\n\\n``.
        """
        prompt = build_builder_spawn_prompt(
            task_spec_path=_TASK_SPEC_PATH,
            issue_file_path=_ISSUE_FILE_PATH,
            milestone_readme_path=_MILESTONE_README_PATH,
            project_context_brief=_STATIC_BRIEF,
        )
        prefix = _stable_prefix(prompt)
        assert not _ISO_TIMESTAMP_RE.search(prefix), (
            f"ISO timestamp found in builder stable prefix: "
            f"{_ISO_TIMESTAMP_RE.search(prefix).group()}"
        )
        assert not _UUID_RE.search(prefix), (
            f"UUID found in builder stable prefix: {_UUID_RE.search(prefix).group()}"
        )

    def test_rule1_no_per_request_strings_in_task_analyzer_prefix(self) -> None:
        """Rule 1 on task-analyzer: stable prefix must not contain timestamps or UUIDs."""
        prompt = build_task_analyzer_spawn_prompt(
            milestone_dir_path="design_docs/phases/m12/",
            analysis_output_path="task_analysis.md",
            project_context_brief=_STATIC_BRIEF,
            round_number=1,
            spec_filenames=["task_01_bar.md"],
        )
        prefix = _stable_prefix(prompt)
        assert not _ISO_TIMESTAMP_RE.search(prefix), (
            f"ISO timestamp found in task-analyzer stable prefix: "
            f"{_ISO_TIMESTAMP_RE.search(prefix).group()}"
        )
        assert not _UUID_RE.search(prefix), (
            f"UUID found in task-analyzer stable prefix: {_UUID_RE.search(prefix).group()}"
        )

    def test_rule1_no_per_request_strings_in_roadmap_selector_prefix(self) -> None:
        """Rule 1 on roadmap-selector: stable prefix must not contain timestamps or UUIDs."""
        prompt = build_roadmap_selector_spawn_prompt(
            recommendation_file_path="runs/recommendation.md",
            project_context_brief=_STATIC_BRIEF,
            milestone_scope="m12",
        )
        prefix = _stable_prefix(prompt)
        assert not _ISO_TIMESTAMP_RE.search(prefix), (
            f"ISO timestamp found in roadmap-selector stable prefix: "
            f"{_ISO_TIMESTAMP_RE.search(prefix).group()}"
        )
        assert not _UUID_RE.search(prefix), (
            f"UUID found in roadmap-selector stable prefix: {_UUID_RE.search(prefix).group()}"
        )

    def test_rule4_double_newline_boundary_present_in_all_prompt_builders(self) -> None:
        """Rule 4: every prompt builder produces a prompt containing \\n\\n."""
        prompts = [
            build_builder_spawn_prompt(
                _TASK_SPEC_PATH, _ISSUE_FILE_PATH, _MILESTONE_README_PATH, _STATIC_BRIEF
            ),
            build_auditor_spawn_prompt(
                _TASK_SPEC_PATH, _ISSUE_FILE_PATH, _MILESTONE_README_PATH,
                _STATIC_BRIEF, _STATIC_DIFF, ["KDR-003"]
            ),
            build_reviewer_spawn_prompt(
                _TASK_SPEC_PATH, _ISSUE_FILE_PATH, _STATIC_BRIEF,
                _STATIC_DIFF, [], "sr-dev"
            ),
            build_task_analyzer_spawn_prompt(
                "design_docs/phases/m12/", "task_analysis.md",
                _STATIC_BRIEF, 1, ["task_01_bar.md"]
            ),
            build_roadmap_selector_spawn_prompt(
                "runs/recommendation.md", _STATIC_BRIEF, "m12"
            ),
        ]
        for prompt in prompts:
            assert "\n\n" in prompt, (
                "Every spawn prompt must contain \\n\\n boundary between "
                "stable prefix and dynamic context."
            )
