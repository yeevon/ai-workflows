# M13 Release Runbook — builder-only

**Scope:** Manual gate for every `uv publish` of `ai-workflows`. Landed at M13 T02; invoked from M13 T07 before the first 0.1.0 upload and from every subsequent patch-release thereafter.

**Branch residence:** `design` branch only. M13 T05 prunes this file from `main` — a PyPI user landing on the `main` branch should not see builder-mode runbooks.

**Grounding:** [task_02 spec](task_02_name_claim_release_smoke.md) · [task_01 spec](task_01_pyproject_polish.md) (the `force-include` hook the smoke depends on) · [milestone README §Branch model](README.md) · [scripts/release_smoke.sh](../../../scripts/release_smoke.sh).

---

## 1. When to run this

Run `bash scripts/release_smoke.sh` from the repo root immediately before every `uv publish` — no exceptions. The script is the only gate that proves the built wheel is installable + runnable by a first-time user on a clean venv. The `tests/test_wheel_contents.py` hermetic suite confirms the wheel *archive* is shaped correctly, but it does not install the wheel into a venv separate from the repo's `.venv` — the release smoke does.

Trigger list:

- **First upload** (T07 — `0.1.0` to PyPI).
- **Every subsequent patch or minor release** (`0.1.x`, `0.2.0`, etc.). Even if pyproject.toml diff looks trivial, run the smoke.
- **After any `[tool.hatch.build.targets.wheel]` edit.** The wheel-contents test catches regressions in the *names* of files shipped; the smoke catches regressions in *how they install and run*.

When in doubt: run it.

## 2. Pre-flight check

Run these four checks before invoking the smoke script:

1. **Release branch.** `git rev-parse --abbrev-ref HEAD` reports `main`. Post-T05 the `main` branch is what publishes; running the smoke from `design` builds a wheel that includes `design_docs/` + `CLAUDE.md` + `.claude/commands/` paths that would fail `test_built_wheel_excludes_builder_mode_artefacts` — and more importantly, would ship builder-mode artefacts to PyPI. Pre-T05 there is no `design` branch yet; run from `main` regardless.
2. **Working tree clean.** `git status --short` is empty. An uncommitted edit can change the built wheel in ways the smoke does not advertise.
3. **Last commit is the intended release SHA.** `git log -1 --oneline` matches the commit you intend to publish. The smoke builds the wheel from the current tree.
4. **`uv` on PATH.** `which uv` resolves. The script uses `uv build`, `uv venv`, `uv pip install` — all via `uv`.

## 3. Run the smoke

Default hermetic pass:

```bash
bash scripts/release_smoke.sh
```

Expected output: six `[N/6]` stage headers followed by `=== OK — release smoke passed ===`. Total runtime on a warm laptop: ~10–20 seconds.

Stage-by-stage failure guide:

| Stage | What it exercises | If it fails | First thing to check |
| --- | --- | --- | --- |
| 1. Build wheel | `uv build --wheel` against the current tree | Build error | `uv build` directly, read the traceback. Usually a `pyproject.toml` syntax error or a hatchling-config mistake. |
| 2. Fresh venv | `uv venv` outside the repo | Unlikely (uv bug / disk full) | `df -h /tmp`, `uv venv --version`. |
| 3. Install wheel | `uv pip install <wheel>` into the fresh venv | Dependency resolution or wheel-contents issue | `uv pip install -vv <wheel>` manually against the fresh venv; read the resolver trace. |
| 4. Help-smoke CLIs | `aiw --help` + `aiw-mcp --help` | `[project.scripts]` entry point broken | Check `pyproject.toml` scripts; verify the target function is importable in the freshly-installed wheel's Python. |
| 5. Migrations-from-wheel | `aiw list-runs` — applies migrations | **Most likely regression site.** yoyo "no migration scripts found" means T01's `force-include` hook was lost. | `unzip -l <wheel> \| grep migrations/` — if empty, re-check `[tool.hatch.build.targets.wheel.force-include]`. |
| 6. Real planner (optional) | Gated by `AIW_E2E=1 + GEMINI_API_KEY` | Provider outage or schema drift | Skip this stage (unset the env vars) unless you intentionally want to pay for a real Gemini call as part of the release gate. |

If any hermetic stage (1–5) fails, **do not proceed to `uv publish`.** Fix the regression on the release branch, re-commit, re-run the smoke.

## 4. Optional live-provider pass

Run when you want an end-to-end proof that the wheel actually drives a real planner run, not just that the migrations apply:

```bash
AIW_E2E=1 GEMINI_API_KEY=<your-key> bash scripts/release_smoke.sh
```

What this adds over the default pass:

- Drives `aiw run planner --goal 'wheel-smoke' --run-id wheel-smoke-<timestamp>` against real Gemini Flash.
- 60-second timeout. Accepts "paused at gate" as success (the planner's first HumanGate is the expected stopping point for a single-shot invocation with no `--approve`).

What this costs:

- One real Gemini Flash call's worth of tokens (fractions of a cent at current pricing — checked against `total_cost_usd` in the smoke's Storage DB before cleanup). Still, not a thing to run casually on every PR — that is why it stays off the default path.

What this does **not** exercise:

- The Claude Code OAuth subprocess driver (planner's synth phase). A two-phase planner run that touches Opus would add cost and latency; the smoke deliberately stops at the first gate to keep the live pass cheap.
- The MCP surface. `aiw-mcp` is help-smoked at stage 4 but not driven by a real client. The T07 post-publish validation (`uvx --from ai-workflows==0.1.0 aiw version`) is where end-to-end PyPI reachability is proven, not here.

Never set `AIW_E2E=1` without `GEMINI_API_KEY` — the script checks both; the absence of either skips the stage cleanly without failing the smoke.

## 5. Release smoke invocation log

A rolling log of every pre-publish smoke run. Keep chronological — most recent at the bottom. Each entry has: date, SHA, branch, stages pass/fail, any notable observations.

### 2026-04-22 — M13 T06 pre-publish smoke

- **SHA:** `8f1fd8e` (main HEAD, post-T05 branch-split commit).
- **Branch:** main.
- **Result:** ✅ PASS. All six stage headers emitted; tail line `=== OK — release smoke passed ===`. Stage 6 (real-provider planner) cleanly skipped — `AIW_E2E=1` intentionally unset per T06 spec (T07 owns the post-publish live round-trip).
- **Notes:** First pre-publish smoke after the T05 branch split. `main`-only test invariants held: `tests/test_main_branch_shape.py::test_design_docs_absence_on_main` passes because no `design_docs/`, `CLAUDE.md`, `.claude/commands/`, `tests/skill/`, or `scripts/spikes/` path resolves on `main`. Wheel build included the bundled `migrations/001_initial.sql` + `migrations/002_reconciliation.sql` via the T01 `[tool.hatch.build.targets.wheel.force-include]` hook; stage 5 `aiw list-runs` against a fresh `AIW_STORAGE_DB` applied them without error. Built wheel artefact: `ai_workflows-0.1.0-py3-none-any.whl` (discarded after the smoke's tempdir cleanup — T07 will rebuild from the same `main` HEAD for the actual `uv publish`). No regressions; T07 is unblocked.
