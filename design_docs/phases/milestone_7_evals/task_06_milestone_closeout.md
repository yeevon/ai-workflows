# Task 06 — Milestone Close-out

**Status:** 📝 Planned.
**Grounding:** [milestone README](README.md) · [CLAUDE.md](../../../CLAUDE.md) close-out conventions · [M6 T09](../milestone_6_slice_refactor/task_09_milestone_closeout.md) (pattern to mirror).

## What to Build

Close M7. Confirm every exit criterion from the [milestone README](README.md). Update [CHANGELOG.md](../../../CHANGELOG.md), flip M7 complete in [roadmap.md](../../roadmap.md), and refresh the root [README.md](../../../README.md). No code change beyond docs — any code finding surfaced during close-out becomes a forward-deferred carry-over on the appropriate M8 task or a new nice_to_have.md entry, never a drive-by fix.

Mirrors [M6 Task 09](../milestone_6_slice_refactor/task_09_milestone_closeout.md) so reviewers get identical close-out muscle memory.

## Deliverables

### [README.md](README.md) (milestone)

- Flip **Status** from `📝 Planned` to `✅ Complete (<YYYY-MM-DD>)`.
- Append an **Outcome** section summarising:
  - Schema substrate ([task 01](task_01_dataset_schema.md)) — `ai_workflows.evals` package landed with `EvalCase`, `EvalSuite`, `EvalTolerance` bare-typed pydantic v2 models; on-disk JSON layout under `evals/<workflow>/<node>/<case_id>.json`; fourth import-linter contract (`evals` below workflows + surfaces, above nothing).
  - Capture callback ([task 02](task_02_capture_callback.md)) — `CaptureCallback` emits one fixture per LLM-node call when `AIW_CAPTURE_EVALS=<name>` is set; default path byte-identical when unset.
  - Replay runner ([task 03](task_03_replay_runner.md)) — deterministic single-node replay graph with stub adapter; live mode double-gated on `AIW_E2E=1` + `AIW_EVAL_LIVE=1`; schema-aware diff output.
  - CLI surface ([task 04](task_04_cli_surface.md)) — `aiw eval capture` reconstructs fixtures from checkpoint channels (or `CaptureCallback` fallback); `aiw eval run <workflow> [--live]` exits 0 all-pass / 1 any-fail.
  - CI wiring + seed fixtures ([task 05](task_05_ci_hookup_seed_fixtures.md)) — `eval-replay` job path-filtered to `workflows/`, `graph/`, `evals/`; ≥3 seed fixtures across `planner` explorer + synth and `slice_refactor` slice_worker.
  - Manual verification: live capture procedure rerun once to confirm fresh-clone reproducibility; `aiw eval run planner --live` + `aiw eval run slice_refactor --live` recorded at close-out time as a model-side drift baseline.
  - Green-gate snapshot: `uv run pytest`, `uv run lint-imports` (**4 contracts kept** — evals contract added at T01), `uv run ruff check`.
- Keep the **Carry-over from prior milestones** section intact (currently: *None*).

### [roadmap.md](../../roadmap.md)

Flip M7 row `Status` from `planned` to `✅ complete (<YYYY-MM-DD>)`.

### [CHANGELOG.md](../../../CHANGELOG.md)

Promote accumulated `[Unreleased]` entries from M7 tasks into a dated section `## [M7 Eval Harness] - <YYYY-MM-DD>`. Keep the top-of-file `[Unreleased]` section intact. Add a T06 close-out entry at the top of the new dated section — mirror M6 T09's shape. Record in this entry:

- The live-capture `run_id`s used at T05 (already in the T05 CHANGELOG line; promote the citation here for the milestone-level record).
- The close-out-time `AIW_E2E=1 AIW_EVAL_LIVE=1 uv run aiw eval run planner --live` + `... slice_refactor --live` runs — commit sha baseline + pass/fail counts + any tolerance decisions made.
- The `uv run lint-imports` 4-contract snapshot confirming the new `evals` contract is among them.
- The capture-mechanism choice locked at T04 (checkpoint-channel reconstruction **or** `CaptureCallback` re-run fallback) — so future Builders know which path is live.

### Root [README.md](../../../README.md)

Update to M7-closed state, matching the M6 close-out shape:

- **Status table** — M7 row → `✅ Complete (<YYYY-MM-DD>)`.
- **Narrative** — append a post-M7 paragraph covering:
  - The deterministic/live split and why (KDR-004: prompting is a contract; model-side vs. code-side drift diagnostic).
  - The `AIW_CAPTURE_EVALS` opt-in capture pattern paired with `aiw eval capture` for post-hoc snapshot.
  - The CI `eval-replay` job behaviour (path-filtered, deterministic, PR-gate; live stays manual).
  - The four-contract import-linter state (evals under workflows + surfaces).
- **What runs today** — add an `aiw eval` CLI bullet citing `capture` + `run` subcommands; add a `evals/` fixture tree bullet; cite the `CaptureCallback` as a graph-layer sibling to `CostTrackingCallback`.
- **Next** pointer — flip `→ M7 eval harness` to `→ M8 Ollama infrastructure` (or the next planned milestone as of close-out date).

Section-heading rename: `post-M6` → `post-M7`.

### Audit-before-close check

The close-out Builder opens **every** M7 task issue file (`design_docs/phases/milestone_7_evals/issues/task_0[1-5]_issue.md`) and confirms:

- No OPEN `🔴 HIGH` or `🟡 MEDIUM` entries.
- Every `DEFERRED` entry has a matching carry-over in its target task spec (propagation discipline, CLAUDE.md *Forward-deferral propagation*).
- Every nice_to_have.md deferral has a §N reference recorded.

Any hole found is the close-out's to fix in-audit (doc maintenance only, not code). If a gap can't be closed with a doc edit, stop and ask the user.

## Acceptance Criteria

- [ ] Every exit criterion in the milestone [README](README.md) has a concrete verification (paths / test names / issue-file links).
- [ ] `uv run pytest && uv run lint-imports && uv run ruff check` green on a fresh clone; `lint-imports` reports **4 contracts kept** (the new `evals` contract plus the three pre-existing).
- [ ] Close-out CHANGELOG entry records the live-replay runs for both `planner` and `slice_refactor` at close-out time (commit sha + pass/fail counts).
- [ ] Close-out CHANGELOG entry records the capture-mechanism choice locked at T04.
- [ ] M7 milestone README **and** roadmap reflect `✅ Complete (<YYYY-MM-DD>)`.
- [ ] CHANGELOG has a dated `## [M7 Eval Harness] - <YYYY-MM-DD>` section; `[Unreleased]` preserved at the top.
- [ ] Root README updated: status table, post-M7 narrative, What-runs-today, Next → M8.
- [ ] All M7 task issue files audited for propagation holes; any gap closed or escalated.

## Dependencies

- [Task 01](task_01_dataset_schema.md) through [Task 05](task_05_ci_hookup_seed_fixtures.md).

## Out of scope (explicit)

- Any code change. Close-out is docs-only; findings flow to M8+ carry-over or nice_to_have.md.
- Promotion of LLM-as-judge, Langfuse, LangSmith, or embedding tolerance (see [nice_to_have.md §1 / §3](../../nice_to_have.md)).
- Retrofitting eval coverage for future workflows (M8 eval cases get captured under M8 T0x, not back-filled here).
