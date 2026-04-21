# Task 06 — Milestone Close-out

**Status:** ✅ Complete (2026-04-21).
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

- [x] Every exit criterion in the milestone [README](README.md) has a concrete verification (paths / test names / issue-file links).
- [x] `uv run pytest && uv run lint-imports && uv run ruff check` green on a fresh clone; `lint-imports` reports **4 contracts kept** (the new `evals` contract plus the three pre-existing).
- [x] Close-out CHANGELOG entry records the live-replay runs for both `planner` and `slice_refactor` at close-out time (commit sha + pass/fail counts).
- [x] Close-out CHANGELOG entry records the capture-mechanism choice locked at T04.
- [x] M7 milestone README **and** roadmap reflect `✅ Complete (2026-04-21)`.
- [x] CHANGELOG has a dated `## [M7 Eval Harness] - 2026-04-21` section; `[Unreleased]` preserved at the top.
- [x] Root README updated: status table, post-M7 narrative, What-runs-today, Next → M8.
- [x] All M7 task issue files audited for propagation holes; any gap closed or escalated.

## Dependencies

- [Task 01](task_01_dataset_schema.md) through [Task 05](task_05_ci_hookup_seed_fixtures.md).

## Out of scope (explicit)

- Any code change. Close-out is docs-only; findings flow to M8+ carry-over or nice_to_have.md.
- Promotion of LLM-as-judge, Langfuse, LangSmith, or embedding tolerance (see [nice_to_have.md §1 / §3](../../nice_to_have.md)).
- Retrofitting eval coverage for future workflows (M8 eval cases get captured under M8 T0x, not back-filled here).

## Carry-over from prior audits

- [x] **M7-T01-ISS-01** (🟢 LOW) — **RESOLVED 2026-04-21.** `architecture.md` §3 updated with a peer-of-graph ASCII diagram + expanded six-edge import-contract rules; new §4.5 Evals layer subsection documents `EvalCase` / `EvalSuite` / `EvalTolerance`, `CaptureCallback`, `EvalRunner` + `_compare` + `_resolve_node_scope`, and the `eval-replay` CI surface. Back-link: [issues/task_01_issue.md#m7-t01-iss-01-architecturemd-§3--§4-does-not-yet-document-the-evals-layer](issues/task_01_issue.md).
- [x] **M7-T05-ISS-01** (🟡 MEDIUM) — **RESOLVED 2026-04-21.** `tests/cli/test_eval_commands.py`'s autouse `_reensure_planner_registered` fixture now snapshots `ai_workflows.workflows._REGISTRY`, resets + seeds `planner` for the test, yields, then restores the full snapshot (preferred "snapshot as a whole" path from the audit recommendation — future workflow registrations survive without fixture edits). The T04 band-aid in `tests/evals/test_seed_fixtures_deterministic.py` remains as defence-in-depth. Back-link: [issues/task_05_issue.md#m7-t05-iss-01-testsclitest_eval_commandspy-autouse-fixture-leaves-session-wide-registry-pollution](issues/task_05_issue.md).
- [x] **M7-T05-ISS-04** (🟢 LOW, doc-maintenance) — **RESOLVED 2026-04-21.** `task_05_ci_hookup_seed_fixtures.md` amended in place: explorer fixture tolerance text corrected to `field_overrides={"summary": "substring"}` with an inline "(Amended 2026-04-21 at T06 close-out: `ExplorerReport` has no `notes` field…)" note; planner-synth node_name corrected to `"planner"`. Audit trail preserved by the amendment note. Back-link: [issues/task_05_issue.md#m7-t05-iss-04-spec-deviation-explorer-tolerance-field_overridesnotes-substring--summary-substring](issues/task_05_issue.md).
- [x] **M7-T05-ISS-06** (🟢 LOW, forward-looking) — **DEFERRED TO [nice_to_have.md §13](../../nice_to_have.md).** New nice_to_have entry captures two implementation options (register pydantic models with LangGraph's msgpack type registry, or switch checkpoint writes to JSON-mode before serializer handoff) + explicit triggers (LangGraph release that escalates to a hard error; noticeable capture-path slowdown; unexplained replay failure traced to serializer drift). No in-milestone fix — the warnings are advisory under current LangGraph and do not affect capture-callback correctness. Back-link: [issues/task_05_issue.md#m7-t05-iss-06-deserialization-warnings-during-slice_refactor-capture-path](issues/task_05_issue.md).
