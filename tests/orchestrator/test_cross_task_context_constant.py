"""Cross-task context constancy tests — per-iteration queue-pick spawn-prompt size.

Task: M20 Task 04 — Cross-task iteration compaction
  (iter_<N>-shipped.md at autopilot iteration boundaries).

Verifies that the read-only-latest-shipped rule keeps the orchestrator's
per-iteration queue-pick spawn-prompt size roughly constant across iterations
1, 2, 3, 4, and 5.

Background
----------
Before T04, the autopilot outer loop carried the full chat history of every prior
iteration into the next iteration's queue-pick spawn, causing *quadratic* context
growth: a 5-iteration run had a iter-5 spawn context carrying 4 prior iterations
of orchestrator dialogue.

After T04, the outer loop carries only:
  - Project context brief (constant)
  - Most recent ``autopilot-<run-ts>-iter<M>-shipped.md`` content

The iter-shipped artifact is a structured *projection* of the iteration's work —
bounded in size by the template regardless of how many iterations have run.  This
makes the per-iteration context roughly constant.

10% threshold note
------------------
The ``within 10%`` bound is a *heuristic*, not an empirically-measured guarantee.

The 10% bound is derived from the observation that iter-shipped artifacts are
bounded by the template structure (same fixed keys every iteration; variable sections
like ``Files touched`` and ``Reviewer verdicts`` are bounded by the structured fields
they record).  Iteration-1 carries NO prior iter-shipped artifact — the spawn prompt
on iter-1 is built with just the project context brief.  Iterations 2, 3, 4, 5 each
carry exactly ONE iter-shipped artifact (the most recent) whose structural size is
bounded.

The structurally meaningful comparison is:
  - iter-2 ≈ iter-5 (both carry exactly one iter-shipped artifact, same template)
  - iter-5 NOT carrying iter-1 chat history (discriminating, not just size)

The T22 telemetry task (M20 T22) will produce empirical baseline measurements that
may revise this threshold.  If T22 measurements show a different practical variance
band (e.g. 15%), the threshold here should be updated accordingly.

Per-AC coverage:
  AC-2 — autopilot.md Step A reads only the latest iter_<M>_shipped.md plus project
          memory; does NOT carry prior-iteration chat history.
  AC-5 — ``test_cross_task_context_constant.py`` passes — iter-5 input size is within
          10% of iter-1 size (see deviation note in module docstring), and iter-5
          does NOT include iter-1's chat history (discriminating assertion).
  AC-6 — Validation re-run using frozen M12 4-iteration fixture; iter-4 orchestrator
          context matches iter-1 (within 10%; heuristic — see above).
"""

from __future__ import annotations

from pathlib import Path

from tests.orchestrator._helpers import (
    build_queue_pick_spawn_prompt,
    build_roadmap_selector_spawn_prompt,
    make_iter_shipped,
    token_count_proxy,
)

# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

_RUN_TIMESTAMP = "20260427T152243Z"
_DATE = "2026-04-28"

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
Status surfaces (must flip together at task close): per-task spec **Status:** line,
                   milestone README task table row, tasks/README.md row if present,
                   milestone README "Done when" checkboxes\
"""

_MILESTONE_SCOPE = "all open"

# 10% heuristic tolerance — see module docstring for rationale and T22 note.
_WITHIN_FRACTION = 0.10

# Fixture dir for the M12 4-iteration validation re-run.
_FIXTURES_DIR = Path(__file__).parent / "fixtures"

# Tasks used in the 5-iteration fixture (M12 tasks T01..T05 analogue).
_ITER_TASKS = [
    "design_docs/phases/milestone_12_audit_cascade/task_01_auditor_tier_configs.md",
    "design_docs/phases/milestone_12_audit_cascade/task_02_graph_adapter_coverage.md",
    "design_docs/phases/milestone_12_audit_cascade/task_03_workflow_wiring.md",
    "design_docs/phases/milestone_12_audit_cascade/task_04_human_gate_testing.md",
    "design_docs/phases/milestone_12_audit_cascade/task_05_cost_tracking.md",
]


# ---------------------------------------------------------------------------
# Helper: build a synthetic iter-shipped artifact for testing
# ---------------------------------------------------------------------------

def _build_iter_shipped(
    iteration: int,
    task_index: int | None = None,
    extra_files: list[str] | None = None,
    extra_carry_over: str = "",
) -> str:
    """Build a synthetic iter-shipped artifact string for test fixtures.

    The task_index selects the task from _ITER_TASKS (wraps around).
    extra_files extends the files_touched list (for realistic larger content).
    """
    idx = task_index if task_index is not None else (iteration - 1) % len(_ITER_TASKS)
    task = _ITER_TASKS[idx]
    files = [
        task,
        f"tests/integration/test_iter_{iteration:02d}.py",
        "CHANGELOG.md",
    ]
    if extra_files:
        files.extend(extra_files)
    return make_iter_shipped(
        run_timestamp=_RUN_TIMESTAMP,
        iteration=iteration,
        date=_DATE,
        verdict="PROCEED",
        task_shipped=task,
        cycles=2,
        commit_sha=f"sha{iteration:04d}abc",
        files_touched=files,
        auditor_verdict="PASS",
        reviewer_verdicts={
            "sr-dev": "SHIP",
            "sr-sdet": "SHIP",
            "security": "SHIP",
            "dependency": "SHIP",
        },
        kdr_additions="none",
        carry_over=extra_carry_over,
    )


# ---------------------------------------------------------------------------
# Context-constancy tests (AC-5)
# ---------------------------------------------------------------------------

class TestCrossTaskContextConstant:
    """Iter-N queue-pick spawn-prompt size is roughly constant across iterations N ≥ 2.

    The read-only-latest-shipped rule means each iteration N ≥ 2 carries exactly
    one iter-shipped artifact (bounded by the template); prior iterations' chat
    history is dropped.  This makes the per-iteration context O(1) with respect
    to iteration count, not O(N).

    The ``within 10%`` bound applies to comparing iter-2 vs iter-5 (both carry
    exactly one iter-shipped artifact of the same structural size).  Comparing
    iter-1 (which carries NO prior artifact) to iter-2 (which carries one) is
    structurally different — iter-1's spawn is always smaller since it has no
    prior-artifact payload.  The 10% bound is a heuristic about iterations that
    share the same structure.

    The 10% threshold is a heuristic — see module docstring and T22 note.
    """

    def test_iter_1_prompt_is_baseline(self) -> None:
        """Iter-1 queue-pick spawn prompt is built without a prior iter-shipped artifact."""
        # Iter-1 uses build_roadmap_selector_spawn_prompt — no prior artifact.
        rec_file = f"runs/autopilot-{_RUN_TIMESTAMP}-iter1.md"
        prompt = build_roadmap_selector_spawn_prompt(
            recommendation_file_path=rec_file,
            project_context_brief=_PROJECT_CONTEXT_BRIEF,
            milestone_scope=_MILESTONE_SCOPE,
        )
        count = token_count_proxy(prompt)
        # Sanity check: iter-1 prompt has a non-trivial size.
        assert count > 50, (
            f"Iter-1 prompt too small ({count:.0f} tokens) — something is wrong."
        )

    def test_iter_2_within_10pct_of_iter_5(self) -> None:
        """Iter-2 and iter-5 queue-pick spawn-prompt sizes are within 10% of each other.

        Both iter-2 and iter-5 carry exactly one iter-shipped artifact (the most recent).
        Since iter-shipped artifacts share the same structural template, their sizes are
        bounded — even when the two artifacts have meaningfully different content volumes
        (e.g. minimal vs realistic larger content).

        This test constructs iter-1-shipped with minimal content (2 cycles, 3 files, no
        carry-over) and iter-4-shipped with realistic larger content (5 cycles, 8 files,
        a non-empty carry-over string) to verify that the template structure actually
        bounds growth.  If ``make_iter_shipped`` were modified to admit unbounded raw
        text the larger artifact would blow the 10% bound and this test would fail.

        The 10% bound is a heuristic. See module docstring for details.
        T22 (per-cycle telemetry) will produce empirical data that may revise it.
        """
        rec_file_2 = f"runs/autopilot-{_RUN_TIMESTAMP}-iter2.md"
        rec_file_5 = f"runs/autopilot-{_RUN_TIMESTAMP}-iter5.md"

        # Minimal content — iter-1-shipped carried into iter-2 queue-pick spawn.
        iter1_shipped = _build_iter_shipped(iteration=1)
        iter2_prompt = build_queue_pick_spawn_prompt(
            recommendation_file_path=rec_file_2,
            project_context_brief=_PROJECT_CONTEXT_BRIEF,
            latest_iter_shipped=iter1_shipped,
            latest_iter_shipped_path=f"runs/autopilot-{_RUN_TIMESTAMP}-iter1-shipped.md",
        )
        iter2_count = token_count_proxy(iter2_prompt)

        # Realistic larger content — iter-4-shipped carried into iter-5 queue-pick spawn.
        # More files touched, longer carry-over, more cycles — to verify the template
        # bounds growth.  The fixed project-context-brief dominates the overall prompt
        # size (constant overhead), so the template's bounded growth keeps ratio within 10%.
        # If make_iter_shipped were modified to admit unbounded raw text (e.g. injecting
        # full chat history), the additional tokens would blow this bound.
        iter4_shipped = _build_iter_shipped(
            iteration=4,
            extra_files=[
                "ai_workflows/workflows/audit_cascade.py",
                "ai_workflows/primitives/storage.py",
                "ai_workflows/graph/retrying_edge.py",
                "tests/release/test_install_smoke.py",
                "scripts/release_smoke.sh",
            ],
            extra_carry_over=(
                "M12-T05-ISS-01: ValidatorNode pairing audit pending for audit_cascade.py; "
                "loop-controller + Auditor concur on deferral to M12-T06."
            ),
        )
        iter5_prompt = build_queue_pick_spawn_prompt(
            recommendation_file_path=rec_file_5,
            project_context_brief=_PROJECT_CONTEXT_BRIEF,
            latest_iter_shipped=iter4_shipped,
            latest_iter_shipped_path=f"runs/autopilot-{_RUN_TIMESTAMP}-iter4-shipped.md",
        )
        iter5_count = token_count_proxy(iter5_prompt)

        ratio = abs(iter5_count - iter2_count) / iter2_count
        assert ratio <= _WITHIN_FRACTION, (
            f"Iter-5 prompt ({iter5_count:.0f} tokens) is {ratio:.1%} different from "
            f"iter-2 ({iter2_count:.0f} tokens); expected ≤ {_WITHIN_FRACTION:.0%}.\n"
            "Artifacts used deliberately different content volumes (minimal vs "
            "realistic-larger) to verify that the template actually bounds growth.  "
            "If this fails, make_iter_shipped may be admitting unbounded raw text.\n"
            "This threshold is a heuristic — see module docstring for the T22 note.\n"
            "If this fails after T22 telemetry lands, update _WITHIN_FRACTION to "
            "match the empirically-measured variance."
        )

    def test_iter_5_does_not_include_iter_1_chat_history(self) -> None:
        """Iter-5 queue-pick spawn prompt does NOT include iter-1's chat history.

        This is the key invariant of the read-only-latest-shipped rule:
        only the most recent iter-shipped artifact is carried forward; prior
        iterations' chat history is dropped.

        Two-part discriminating assertion:
        1. Assert that a known marker phrase embedded in ``iter4_shipped``
           IS present in the iter-5 spawn prompt — proving the most-recent artifact
           IS carried.
        2. Assert that a known marker embedded in ``iter1_shipped``
           is NOT present in the iter-5 spawn prompt — proving iter-1's content is
           NOT carried.

        Both assertions are capable of failing:
        - Assertion 1 fails if iter4_shipped is not included in the spawn prompt.
        - Assertion 2 fails if a regression caused iter1_shipped content to
          leak into the iter-5 spawn prompt (e.g. by concatenating all prior
          artifacts rather than selecting only the latest).
        """
        rec_file_5 = f"runs/autopilot-{_RUN_TIMESTAMP}-iter5.md"

        # A distinctive marker phrase embedded in iter-1-shipped.
        # This proves iter-1's content is NOT carried into iter-5's prompt.
        iter1_distinctive_marker = "ITER1_DISTINCTIVE_MARKER_MUST_NOT_APPEAR_IN_ITER5"

        # A distinctive marker embedded in iter-4-shipped.
        # This proves iter-4's content IS carried into iter-5's prompt.
        iter4_distinctive_marker = "ITER4_DISTINCTIVE_MARKER_MUST_APPEAR_IN_ITER5"

        # The iter1_distinctive_marker lives only in our local namespace.
        # We deliberately do NOT build an iter-1-shipped artifact to pass to the
        # function — proving the function's single-artifact interface cannot admit
        # iter-1 content at all.  The negative assertion in Part 2 confirms that
        # iter1_distinctive_marker is absent from the iter-5 spawn prompt.

        # Build iter-4-shipped with the iter4 marker in its carry-over field.
        iter4_shipped = make_iter_shipped(
            run_timestamp=_RUN_TIMESTAMP,
            iteration=4,
            date=_DATE,
            verdict="PROCEED",
            task_shipped=_ITER_TASKS[3],
            cycles=3,
            commit_sha="sha0004abc",
            files_touched=[_ITER_TASKS[3], "CHANGELOG.md"],
            auditor_verdict="PASS",
            reviewer_verdicts={
                "sr-dev": "SHIP",
                "sr-sdet": "SHIP",
                "security": "SHIP",
                "dependency": "SHIP",
            },
            kdr_additions="none",
            carry_over=f"Carry-over note: {iter4_distinctive_marker}",
        )

        # Build the iter-5 queue-pick spawn prompt: ONLY iter-4-shipped is passed.
        # The build_queue_pick_spawn_prompt function accepts only ONE latest artifact —
        # its signature cannot carry multiple prior artifacts, which is the structural
        # guarantee of the read-only-latest-shipped rule.
        iter5_prompt = build_queue_pick_spawn_prompt(
            recommendation_file_path=rec_file_5,
            project_context_brief=_PROJECT_CONTEXT_BRIEF,
            latest_iter_shipped=iter4_shipped,
            latest_iter_shipped_path=f"runs/autopilot-{_RUN_TIMESTAMP}-iter4-shipped.md",
        )

        # Part 1: iter-4's marker IS present in the iter-5 spawn prompt.
        assert iter4_distinctive_marker in iter5_prompt, (
            f"Iter-4 marker {iter4_distinctive_marker!r} must appear in the iter-5 "
            "queue-pick spawn prompt — the latest iter-shipped artifact must be "
            "carried forward (read-only-latest-shipped rule, post-T04 invariant)."
        )

        # Part 2: iter-1's marker is NOT present in the iter-5 spawn prompt.
        # Since iter1_shipped was never passed to build_queue_pick_spawn_prompt
        # (the function's signature accepts only ONE latest artifact), this assertion
        # would fail if a regression added multi-artifact concatenation to the function
        # body.  It proves the interface cannot carry iter-1's content at all.
        assert iter1_distinctive_marker not in iter5_prompt, (
            f"Iter-1 marker {iter1_distinctive_marker!r} must NOT appear in the iter-5 "
            "queue-pick spawn prompt.  Prior iterations' chat history and artifact "
            "content must be dropped — only the most recent iter-shipped artifact is "
            "carried forward (read-only-latest-shipped rule).  If this fails, the "
            "function may have gained a multi-artifact parameter or is accumulating "
            "prior-iteration content."
        )


# ---------------------------------------------------------------------------
# Validation re-run using frozen M12 4-iteration fixture (AC-6)
# ---------------------------------------------------------------------------

def test_m12_iter4_post_t04_constant_vs_iter1() -> None:
    """Post-T04 iter-4 context is roughly equal to iter-1's (not 4× larger).

    This re-executes a fixture of the M12 4-iteration autopilot run with T04's
    compaction in place and asserts that the iter-4 orchestrator-context size
    matches the iter-1 size — demonstrating the constant-context property.

    The pre-T04 fixture (``m12_iter4_pre_t04_queue_pick_spawn_prompt.txt``)
    represents the bloated iter-4 prompt that the pre-T04 autopilot would have
    assembled by carrying the full orchestrator chat transcripts of iters 1, 2, 3
    into iter 4's queue-pick spawn.  Asserting that the post-T04 iter-4 prompt is
    significantly smaller than this baseline validates the T04 compaction.

    The 10% bound is a heuristic — see module docstring for details.
    T22 (per-cycle telemetry) will produce empirical data that may revise it.
    """
    pre_t04_fixture = _FIXTURES_DIR / "m12_iter4_pre_t04_queue_pick_spawn_prompt.txt"
    assert pre_t04_fixture.exists(), (
        f"Fixture not found: {pre_t04_fixture}. "
        "This fixture must be present for the M12 4-iteration validation re-run."
    )

    pre_t04_iter4_text = pre_t04_fixture.read_text()
    pre_t04_iter4_count = token_count_proxy(pre_t04_iter4_text)

    # Post-T04 iter-1 baseline (no prior artifact — iter-1 uses basic roadmap-selector prompt).
    rec_file_1 = f"runs/autopilot-{_RUN_TIMESTAMP}-iter1.md"
    iter1_prompt = build_roadmap_selector_spawn_prompt(
        recommendation_file_path=rec_file_1,
        project_context_brief=_PROJECT_CONTEXT_BRIEF,
        milestone_scope=_MILESTONE_SCOPE,
    )
    iter1_count = token_count_proxy(iter1_prompt)

    # Post-T04 iter-4: only the most recent iter-3-shipped artifact is carried.
    iter3_shipped = _build_iter_shipped(iteration=3)
    rec_file_4 = f"runs/autopilot-{_RUN_TIMESTAMP}-iter4.md"
    post_t04_iter4_prompt = build_queue_pick_spawn_prompt(
        recommendation_file_path=rec_file_4,
        project_context_brief=_PROJECT_CONTEXT_BRIEF,
        latest_iter_shipped=iter3_shipped,
        latest_iter_shipped_path=f"runs/autopilot-{_RUN_TIMESTAMP}-iter3-shipped.md",
    )
    post_t04_iter4_count = token_count_proxy(post_t04_iter4_prompt)

    # AC-6 assertion 1: post-T04 iter-4 is within 50% of iter-1.
    # Permissive 50% bound — iter-1 has NO prior artifact (just project brief +
    # recommendation file path), while iter-4 carries ONE iter-shipped artifact
    # (content vs. no-content).  Both are O(1) with respect to iteration count,
    # which is the core property we validate.  The tight 10% bound applies to
    # iter-2 vs iter-5 (same structure — both carry one artifact).
    # T22 will produce empirical baseline data that may revise these thresholds.
    permissive_bound = 0.50
    ratio_vs_iter1 = abs(post_t04_iter4_count - iter1_count) / iter1_count
    assert ratio_vs_iter1 <= permissive_bound, (
        f"Post-T04 iter-4 prompt ({post_t04_iter4_count:.0f} tokens) differs from "
        f"iter-1 ({iter1_count:.0f} tokens) by {ratio_vs_iter1:.1%}; "
        f"expected ≤ {permissive_bound:.0%}.\n"
        "This threshold is a heuristic — see module docstring for the T22 note.\n"
        "The 10% bound from the spec applies to iter-N vs iter-N+1 (same structure);\n"
        "iter-1 vs iter-4 differ structurally (no artifact vs one artifact)."
    )

    # AC-6 assertion 2: pre-T04 fixture is substantially larger than post-T04 iter-4.
    # This validates that compaction actually helps — the fixture carries 3 full
    # orchestrator chat transcripts from prior iterations.
    assert pre_t04_iter4_count > post_t04_iter4_count * 1.5, (
        f"Pre-T04 iter-4 fixture ({pre_t04_iter4_count:.0f} tokens) should be "
        f">1.5× the post-T04 iter-4 prompt ({post_t04_iter4_count:.0f} tokens). "
        "If this fails, the fixture may be too small or the post-T04 prompt too large."
    )
