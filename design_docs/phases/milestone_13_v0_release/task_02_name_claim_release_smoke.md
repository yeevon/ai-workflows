# Task 02 — PyPI name claim + clean-venv install smoke + wheel-excludes test

**Status:** 📝 Planned (drafted 2026-04-22 after T01 audit).
**Grounding:** [milestone README](README.md) · [task_01_pyproject_polish.md](task_01_pyproject_polish.md) · [T01 audit issue file](issues/task_01_issue.md) · [CLAUDE.md](../../../CLAUDE.md) · [architecture.md §4.4](../../architecture.md) (the two CLI surfaces the smoke exercises).

## What to Build

Three deliverables. All three close one M13 exit criterion each without touching any `ai_workflows/` runtime code:

1. **Record the PyPI name claim for `ai-workflows`.** A one-off web check + a note in this spec + a `CHANGELOG.md` entry. No `pyproject.toml` change — T01 already set `name = "ai-workflows"`.
2. **Ship the release-gate smoke script.** `scripts/release_smoke.sh` — a bash script that builds the wheel, installs it into a fresh venv outside the repo, runs `aiw` + `aiw-mcp` help, runs `aiw list-runs` against a fresh Storage DB (exercises the migrations-from-wheel path T01 unlocked), and optionally drives a real planner run when `AIW_E2E=1` + `GEMINI_API_KEY` are set. **Not** wired into CI at M13 (live-provider path); invoked manually from T06's runbook before the first `uv publish`.
3. **Extend the wheel-contents test with exclusion assertions.** Append a third test to `tests/test_wheel_contents.py` that asserts `design_docs/`, `CLAUDE.md`, and `.claude/commands/` are absent from the built wheel — closes the other half of milestone README §Exit criteria 2.

## Deliverables

### 1. PyPI name claim

Pre-flight check performed 2026-04-22:

```bash
$ curl -sS -o /dev/null -w '%{http_code}\n' https://pypi.org/pypi/ai-workflows/json
404
```

`ai-workflows` is **available** on PyPI as of 2026-04-22. The `[project].name = "ai-workflows"` stamp from T01 stands. No namespace alternative (`aiw-framework`, `ai-workflows-langgraph`, `<user>-ai-workflows` — the three candidates named in milestone README §Exit criteria 4) is needed.

**No `pyproject.toml` edit at T02.** The claim is passively held by the first successful `uv publish` at T07; PyPI treats the first uploader of a name as the owner. Between now and T07, a race is theoretically possible but not practically worth defending against — the contingency is documented in T07's spec when drafted.

The claim is recorded in:

- This spec (above).
- The `CHANGELOG.md [Unreleased]` entry for T02.
- The T02 audit issue file.

### 2. [scripts/release_smoke.sh](../../../scripts/release_smoke.sh) — manual release-gate smoke

New file at repo root under `scripts/` (sibling of the existing `scripts/spikes/`). Shell script, not Python — it must operate outside a `uv sync`'d venv and prove the wheel is installable on a bare `uv`-only machine.

**Contract.**

- Input: none (uses the current working directory as the repo root; fails loudly if `pyproject.toml` is missing).
- Exit code: 0 on success, non-zero on any failure. Script uses `set -euo pipefail` at the top.
- Side effects: creates a temporary directory via `mktemp -d`, builds the wheel into it, makes a fresh venv inside it, installs the wheel, runs the smokes. Cleans up the temp dir via a `trap` on EXIT.

**Stages, in order.**

1. **Build wheel.** `uv build --wheel --out-dir "$TMP_DIR/dist"` — same command the T01 hermetic test runs. Asserts exactly one `.whl` landed in `$TMP_DIR/dist/`.
2. **Create clean venv outside the repo.** `uv venv "$TMP_DIR/venv"` — fresh, empty, no `uv sync` of the repo. Importantly this venv is **not** the repo's `.venv` — the smoke must prove the wheel's self-sufficiency.
3. **Install the built wheel.** `uv pip install --python "$TMP_DIR/venv/bin/python" "$TMP_DIR/dist/ai_workflows-"*.whl`.
4. **Help-smoke both CLI entry points.** `"$TMP_DIR/venv/bin/aiw" --help` and `"$TMP_DIR/venv/bin/aiw-mcp" --help`. Both must exit 0. Proves the `[project.scripts]` entry points resolve against the installed wheel.
5. **Migrations-from-wheel smoke** (the headline gate). Set `AIW_STORAGE_DB="$TMP_DIR/storage.db"` and run `"$TMP_DIR/venv/bin/aiw" list-runs`. This command opens `SQLiteStorage.open(...)`, which applies all migrations from the wheel-bundled `migrations/` directory (the path `ai_workflows/primitives/storage.py`'s walk-up resolves to under `site-packages/migrations/` — exactly the install layout T01 produced via `force-include`). An empty output with exit 0 proves: (a) the wheel ships `migrations/`; (b) the Storage walk-up finds them at the `site-packages/` layer; (c) yoyo applies them successfully; (d) the run registry is queryable. If T01's `force-include` hook ever regresses, this stage fails loudly.
6. **Optional: real-provider planner run.** Gated by `AIW_E2E=1` + `GEMINI_API_KEY` both set. Runs `aiw run planner --goal 'wheel-smoke' --run-id wheel-smoke` with a 60-second timeout; accepts "paused at gate" as success (exit code 0 on the HumanGate path). When either env var is missing, prints a skip line and continues. Not run by default — the hermetic stages 1-5 are the release-gate bar.
7. **Cleanup.** `trap cleanup EXIT` removes `$TMP_DIR`.

**Spec deviation called out up-front.** The milestone README §Exit criteria 3 prescribes *"runs `aiw run planner --goal 'wheel-smoke' --run-id wheel-smoke --no-wait` against a stubbed provider"*. Two drift points vs. the shipped script:

1. There is no `--no-wait` flag on `aiw run` today ([cli.py](../../../ai_workflows/cli.py) grep confirms). Adding one is fundamental graph-surface scope (return run_id before HumanGate fires) — out of scope for T02's packaging focus.
2. There is no shell-level "stubbed provider" surface. `StubLLMAdapter` is a Python test helper under `ai_workflows/evals/_stub_adapter.py`, not a `AIW_*`-env-configurable runtime swap.

The shipped script substitutes `aiw list-runs` for `aiw run` in the hermetic path. `list-runs` exercises the same `SQLiteStorage.open()` + migrations-apply code path that `aiw run` opens first — which is the *actual* thing the smoke is meant to gate (the wheel must ship migrations, and the Storage walk-up must find them). It adds **zero** provider-dependency to the hermetic default path. The real-provider `aiw run` path lives behind the same `AIW_E2E=1` + `GEMINI_API_KEY` double-gate that [tests/e2e/](../../../tests/e2e/) uses today — matching the README's own "or against real Gemini Flash if `GEMINI_API_KEY` + `AIW_E2E=1` are set" clause. This deviation is **recorded in CHANGELOG T02** and **in the T02 audit issue file under "additions / deviations beyond spec — audited and justified"**.

**Not added to CI.** The script stays manual. Any CI invocation would either (a) be hermetic and duplicate `tests/test_wheel_contents.py` or (b) be live-provider and cost real money per PR. T13 could revisit if a trigger fires — not here.

### 3. [design_docs/phases/milestone_13_v0_release/release_runbook.md](release_runbook.md) — builder-only runbook

New file in this milestone directory (stays on `design` branch — deleted from `main` at T05 branch-split per milestone README §Branch model). Short — four sections, ≤ 100 lines:

1. **When to run this.** Before every `uv publish` (T07 kickoff). Never skip — the script is the only gate that proves the wheel works for a first-time user.
2. **Pre-flight check.** Ensure the repo is on the `main` branch (release branch per milestone README §Branch model; T07 publishes from `main`), working tree clean, last commit is the intended release SHA.
3. **Run the smoke.** `bash scripts/release_smoke.sh` — expected output, how to interpret failures (stage-by-stage).
4. **Optional live-provider pass.** `AIW_E2E=1 GEMINI_API_KEY=<...> bash scripts/release_smoke.sh` — when to run it, what it proves, what it costs.

### 4. [tests/test_wheel_contents.py](../../../tests/test_wheel_contents.py) — third test: builder-mode exclusions

Append one test to the existing file (reuse the `built_wheel` module-scoped fixture from T01):

```python
def test_built_wheel_excludes_builder_mode_artefacts(built_wheel: Path) -> None:
    """Builder-mode artefacts must not ship in the distributable wheel.

    Per milestone README §Exit criteria 2 + §Branch model: ``design_docs/``,
    ``CLAUDE.md``, and ``.claude/commands/`` are builder/auditor-workflow
    artefacts. They land on the ``design`` branch only; the ``main``
    branch (which publishes to PyPI) drops them at T05. Even during the
    branch-split window where they briefly coexist in the source tree,
    ``packages = ["ai_workflows"]`` + the ``force-include`` hook must
    never sweep them. This test pins that invariant.
    """
    with zipfile.ZipFile(built_wheel) as zf:
        names = list(zf.namelist())

    forbidden_prefixes = ("design_docs/", ".claude/commands/")
    for name in names:
        for prefix in forbidden_prefixes:
            assert not name.startswith(prefix), (
                f"wheel leaked builder-mode path: {name} "
                f"(matched forbidden prefix {prefix!r})"
            )
    assert "CLAUDE.md" not in names, f"wheel leaked CLAUDE.md; full list: {sorted(names)}"
```

Hermetic — same `uv build` subprocess fixture as T01, no network, no provider call, runs in the default `uv run pytest` suite.

### 5. [CHANGELOG.md](../../../CHANGELOG.md)

Under `## [Unreleased]`, append a new `### Changed — M13 Task 02: PyPI name claim + release smoke + wheel excludes (YYYY-MM-DD)` block covering:

- PyPI name check outcome (404 on `pypi.org/pypi/ai-workflows/json` as of 2026-04-22 — available).
- Files touched: `scripts/release_smoke.sh` (new), `design_docs/phases/milestone_13_v0_release/release_runbook.md` (new — builder-only), `tests/test_wheel_contents.py` (one test appended).
- ACs satisfied.
- Deviation from spec: the release-smoke script substitutes `aiw list-runs` for `aiw run --no-wait` in the hermetic default path; the real-provider `aiw run` stage is gated behind `AIW_E2E=1` + `GEMINI_API_KEY`. Reason: `--no-wait` does not exist as a CLI flag today and there is no shell-surface provider stub. Adding either would be out-of-scope runtime work. Recorded verbatim in the T02 audit issue file.

## Acceptance Criteria

- [ ] AC-1: PyPI name `ai-workflows` confirmed available (404 on `pypi.org/pypi/ai-workflows/json`); outcome recorded in this spec + CHANGELOG T02 entry + T02 audit issue file. **No `pyproject.toml` change.**
- [ ] AC-2: `scripts/release_smoke.sh` exists, is executable (`chmod +x`), uses `set -euo pipefail`, and cleans up its temp dir via `trap`.
- [ ] AC-3: The smoke script's stages 1–5 (hermetic) run green on the current `main` tip: `uv build --wheel` produces exactly one wheel; `uv venv` creates a fresh venv; `uv pip install` installs the wheel; `aiw --help` + `aiw-mcp --help` exit 0; `aiw list-runs` against a fresh `AIW_STORAGE_DB` exits 0 (migrations applied).
- [ ] AC-4: Stage 6 (real-provider run) is gated by both `AIW_E2E=1` and `GEMINI_API_KEY` present. When either is missing, the script prints a skip line and continues without error. **Not run in the audit** — gated by operator invocation.
- [ ] AC-5: `scripts/release_smoke.sh` is **not** referenced from `.github/workflows/ci.yml`. Audit greps CI config to confirm.
- [ ] AC-6: `design_docs/phases/milestone_13_v0_release/release_runbook.md` exists, ≤ 100 lines, covers the four sections named above. Runbook stays on `design` branch (will be pruned from `main` at T05 branch-split).
- [ ] AC-7: `tests/test_wheel_contents.py` gains `test_built_wheel_excludes_builder_mode_artefacts` covering absence of `design_docs/`, `CLAUDE.md`, and `.claude/commands/`. Test shares the `built_wheel` fixture with the two T01 tests — no new fixture. Passes.
- [ ] AC-8: `uv run pytest` green (614 existing + 1 new = 615 tests).
- [ ] AC-9: `uv run lint-imports` reports 4 contracts kept, 0 broken (no new layer contract at T02).
- [ ] AC-10: `uv run ruff check` clean. Script-only edits (bash) are outside ruff's scope; the one new Python test block lints clean.
- [ ] AC-11: CHANGELOG `[Unreleased]` entry lists files + ACs + the deviation note (smoke substitutes `list-runs` for `run --no-wait` in the hermetic default path).
- [ ] AC-12: Zero diff under `ai_workflows/`. T02, like T01, is packaging-only — no runtime code change.

## Dependencies

- **T01 complete and clean** (✅ landed 2026-04-22, Cycle 1 of `/clean-implement`). T02 reuses the `built_wheel` fixture + the `force-include` layout T01 put in place.
- No external dependency. The PyPI name check is a GET request; the smoke script is offline by default.

## Out of scope (explicit)

- **No `uv publish`.** The first upload is T07's scope; T02 only *prepares* the gate script.
- **No CI wiring for the smoke.** Live-provider gate; stays manual.
- **No `--no-wait` CLI flag.** Out-of-scope for a packaging task; see §Deliverables 2 for the deviation rationale.
- **No shell-surface provider stub.** Same reason.
- **No `pyproject.toml` edit.** T01 landed the name + metadata; T02 only records the name-availability check outcome.
- **No README install section.** Lands at T04.
- **No branch split.** Lands at T05; this task stays on `design`.

## Propagation status

Filled in at audit time. Anticipated forward-deferrals: none — T02 is narrow. The `--no-wait` / shell-provider-stub gaps are called out as spec deviations (audited + justified); they do not become carry-over.
