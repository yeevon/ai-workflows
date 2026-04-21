# Task 05 — CI Hookup + Seed Fixtures for `planner` + `slice_refactor`

**Status:** 📝 Planned.
**Grounding:** [milestone README §Exit criteria 4 + 5](README.md) · [.github/workflows/ci.yml](../../../.github/workflows/ci.yml).

## What to Build

Two inseparable deliverables:

1. **Seed fixtures.** Capture representative cases for both shipped workflows (`planner` + `slice_refactor`) so M7's harness has something concrete to guard from day one. Captured via the T04 `aiw eval capture` CLI against real-provider runs performed once in a Builder session.

2. **CI wiring.** A new GitHub Actions job that runs `aiw eval run planner` + `aiw eval run slice_refactor` in **deterministic mode** on every PR that touches `ai_workflows/workflows/**`, `ai_workflows/graph/**`, or `evals/**`. Live-mode replay is **not** wired into CI — it stays manual / scheduled.

## Deliverables

### Seed fixtures

Committed under `evals/`:

- `evals/planner/explorer/happy-path-01.json` — captured from a real `planner` run with goal `"Write a release checklist for version 1.2.0"`. `output_schema_fqn = "ai_workflows.workflows.planner.ExplorerReport"`. Tolerance: `strict_json` with `field_overrides={"notes": "substring"}` (free-text field).
- `evals/planner/synth/happy-path-01.json` — same run, the synth (`planner-synth`) phase. `output_schema_fqn = "ai_workflows.workflows.planner.PlannerPlan"`. Tolerance: `strict_json` with `field_overrides={"summary": "substring"}`.
- `evals/slice_refactor/slice_worker/happy-path-01.json` — captured from a real `slice_refactor` run with a 3-step plan. `output_schema_fqn = "ai_workflows.workflows.slice_refactor.SliceResult"`. Tolerance: `strict_json`.

Target **minimum 3 cases total**, covering both workflows. More cases welcome but not required at M7 — T06 close-out audit will flag coverage holes as forward-deferred to future tasks.

Fixture files are **plain JSON pretty-printed** (not YAML, not gzipped) so PR diffs are reviewable.

### Fixture capture procedure (record in CHANGELOG for reproducibility)

Performed once by the T05 Builder against live providers:

```bash
# 1. Run a planner capture
export AIW_CAPTURE_EVALS=planner-seed
export GEMINI_API_KEY=...
aiw run planner --goal "Write a release checklist for version 1.2.0" --run-id eval-seed-planner
aiw resume eval-seed-planner --approve
aiw eval capture --run-id eval-seed-planner --dataset planner

# 2. Run a slice_refactor capture
export AIW_CAPTURE_EVALS=slice-seed
aiw run slice_refactor --goal "Write three one-line unit tests for an add(a, b) function." --run-id eval-seed-slice
aiw resume eval-seed-slice --approve  # planner gate
aiw resume eval-seed-slice --approve  # strict-review gate
aiw eval capture --run-id eval-seed-slice --dataset slice_refactor

# 3. Verify deterministic replay passes immediately
aiw eval run planner
aiw eval run slice_refactor
```

The Builder commits the captured JSON fixtures verbatim. Minor post-capture edits allowed: trimming noisy metadata fields, widening a tolerance mode for a legitimately non-deterministic free-text summary. Edits are called out in the CHANGELOG.

### CI wiring

[.github/workflows/ci.yml](../../../.github/workflows/ci.yml) — add one new job after the existing `test` / `lint` jobs:

```yaml
  eval-replay:
    name: Eval replay (deterministic)
    runs-on: ubuntu-latest
    needs: test
    if: |
      contains(github.event.pull_request.changed_files, 'ai_workflows/workflows/') ||
      contains(github.event.pull_request.changed_files, 'ai_workflows/graph/') ||
      contains(github.event.pull_request.changed_files, 'evals/')
    steps:
      - uses: actions/checkout@v4
      - name: Set up uv
        uses: astral-sh/setup-uv@v5
      - name: Install
        run: uv sync --dev
      - name: Run evals
        run: |
          uv run aiw eval run planner
          uv run aiw eval run slice_refactor
```

Note on the `if:` condition: GitHub Actions doesn't expose `changed_files` directly — the Builder will need to resolve this via `dorny/paths-filter@v3` or an equivalent path-filter action. The pseudocode above states intent; the Builder lands the actual syntax.

**CI scope boundary:** live-mode replay stays out of PR CI. Live replay is a separate manual workflow file (optional T05 add, or forward-deferred to a future task) gated by a workflow_dispatch trigger. Running live on every PR would burn provider quota and introduce flakes from model-side drift — M7's PR-gate job catches code-side drift deterministically, which is the promise.

### Tests

[tests/evals/test_seed_fixtures_deterministic.py](../../../tests/evals/test_seed_fixtures_deterministic.py):

- `test_planner_seed_fixtures_replay_green_deterministic` — loads `evals/planner/...`, runs `EvalRunner(mode="deterministic")`, asserts `report.fail_count == 0`. Always runs; no env gate.
- `test_slice_refactor_seed_fixtures_replay_green_deterministic` — same for `slice_refactor`.
- `test_all_committed_fixtures_parse_to_eval_case` — globs every `evals/**/*.json`, asserts each parses cleanly through `EvalCase.model_validate_json`. Catches a malformed commit before the replay fails with a less-clear error.

## Acceptance Criteria

- [ ] At least **3 seed fixtures** committed under `evals/` spanning both `planner` and `slice_refactor` — minimum one case per LLM node (`planner-explorer`, `planner-synth`, `slice-worker`).
- [ ] `aiw eval run planner` and `aiw eval run slice_refactor` both green on HEAD.
- [ ] New `eval-replay` CI job in `.github/workflows/ci.yml` — triggered on any PR touching `workflows/`, `graph/`, or `evals/`; runs both eval suites in deterministic mode.
- [ ] `uv run pytest tests/evals/test_seed_fixtures_deterministic.py` green under the default `uv run pytest` (no env gates).
- [ ] CHANGELOG entry records the capture procedure, the live-provider run_ids used, and any post-capture fixture edits.
- [ ] Full gate: `uv run pytest && uv run lint-imports && uv run ruff check` green.

## Dependencies

- [Task 01](task_01_dataset_schema.md) — schemas.
- [Task 02](task_02_capture_callback.md) — capture callback.
- [Task 03](task_03_replay_runner.md) — `EvalRunner`.
- [Task 04](task_04_cli_surface.md) — `aiw eval` commands drive capture + replay.
- Live providers: `GEMINI_API_KEY` + `ollama` with `qwen2.5-coder:32b` + `claude` CLI authenticated (same prereqs as the M5 / M6 manual smokes).

## Out of scope (explicit)

- Live-mode replay in CI.
- Coverage of every permutation of every workflow — M7 is the guard for *existence and correctness*; depth of coverage is a future-task concern.
- Scheduled nightly live-replay. (Candidate for a follow-up task or `nice_to_have.md` promotion.)
- Eval-driven pre-commit hooks.
