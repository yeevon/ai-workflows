# Task 02 — PyPI name claim + clean-venv install smoke + wheel-excludes test — Audit Issues

**Source task:** [../task_02_name_claim_release_smoke.md](../task_02_name_claim_release_smoke.md)
**Audited on:** 2026-04-22
**Audit scope:** T02 spec, milestone README (§Exit criteria 2 + 3 + 4, §Branch model, §Task order), T01 issue file (sibling context + `built_wheel` reuse), T01 spec (force-include hook the smoke depends on), architecture.md §3 (four-layer contract), §4.4 (CLI + MCP surfaces exercised by smoke), §6 (no new deps), §9 (KDR grid), scripts/release_smoke.sh (new), design_docs/phases/milestone_13_v0_release/release_runbook.md (new), tests/test_wheel_contents.py (one test appended), CHANGELOG.md [Unreleased] T02 block, manual bash scripts/release_smoke.sh run (stages 1-5 green; stage 6 skipped cleanly), manual grep of .github/workflows/ci.yml for `release_smoke`, manual inspection of built wheel archive, git diff HEAD -- ai_workflows/.
**Status:** ✅ PASS (Cycle 1) — all 12 ACs met, zero HIGH / MEDIUM / LOW, three gates green (615 passed / 5 skipped, 4 import-linter contracts kept, ruff clean), release smoke stages 1-5 green on current tip.

---

## Design-drift check

| Axis | Evidence | Verdict |
| --- | --- | --- |
| New dependency? | Zero. `pyproject.toml` untouched at T02 (T01 landed all packaging metadata; T02 §Out of scope explicitly excludes any `pyproject.toml` edit). New bash script + new markdown runbook + one appended Python test. | ✅ Clean. |
| New module or layer? | Zero. T02 adds no Python source file. Only test append + shell script + doc. Four-layer contract untouched — `uv run lint-imports` reports 4 kept, 0 broken. | ✅ Clean. |
| LLM call added? | None in the hermetic default path. Stage 6 (optional real-provider) drives `aiw run planner` via the existing `TieredNode` → LiteLLM/Gemini path — already-audited surface from M1–M8, gated behind `AIW_E2E=1 + GEMINI_API_KEY`. KDR-004 (ValidatorNode pairing) preserved via existing planner graph. | ✅ Clean. |
| Checkpoint / resume logic? | None. Smoke exercises `SqliteSaver` indirectly via `aiw list-runs` but does not add new checkpoint code. KDR-009 preserved. | ✅ Clean. |
| Retry logic? | None. | ✅ Clean. |
| Observability? | None. `configure_logging` not called from the bash script (it's invoked by the `aiw` CLI entry point, which already uses `StructuredLogger`). No external backend adoption. | ✅ Clean. |
| `anthropic` SDK / `ANTHROPIC_API_KEY`? | Grep over T02 diff — no matches. Smoke script references only `GEMINI_API_KEY` (KDR-003 preserved). | ✅ Clean. |
| `nice_to_have.md` scope creep? | T02 §Out of scope excludes `uv publish`, CI wiring for the smoke, `--no-wait` CLI flag, shell-surface provider stub, `pyproject.toml` edit, README install section, branch split. None appear in the diff. CI-gated publish-on-tag stays a `nice_to_have.md` candidate per milestone README §Propagation status. | ✅ Clean. |
| architecture.md §6 alignment | `uv` / `bash` / `zipfile` / `subprocess` already declared or stdlib; no new runtime dep. Hatchling `force-include` T01 installed is the only build-system surface the smoke depends on. | ✅ Clean. |
| architecture.md §3 alignment | Four-layer contract unaffected by packaging-only task. Import-linter 4-contract sweep KEPT. | ✅ Clean. |
| KDR-002 (portable surface) | Smoke script actively *validates* KDR-002: builds the wheel, installs it in a venv outside the repo, proves both CLI entry points resolve, proves migrations apply from the `site-packages/` layout. Directly strengthens the invariant T01 put in place. | ✅ Clean. |
| KDR-008 (MCP schema contract) | `aiw-mcp --help` help-smoked at stage 4; does not invoke any MCP tool (that would be the T07 post-publish gate). No schema drift possible from T02. | ✅ Clean. |

**No design drift. No KDR violation. No architectural §X contradiction.** T02 is packaging-validation scope — it does not add code to `ai_workflows/`; it pins the *shape* of the distributable.

---

## AC grading

Graded individually against [task_02_name_claim_release_smoke.md:115-127](../task_02_name_claim_release_smoke.md#L115-L127).

| # | Acceptance criterion | Evidence | Verdict |
| --- | --- | --- | --- |
| AC-1 | PyPI name `ai-workflows` confirmed available (404 on `pypi.org/pypi/ai-workflows/json`); outcome recorded in spec + CHANGELOG T02 entry + T02 audit issue file. **No `pyproject.toml` change.** | `curl -sS -o /dev/null -w '%{http_code}\n' https://pypi.org/pypi/ai-workflows/json` → `404` (2026-04-22). Recorded in [task_02 spec §Deliverables 1](../task_02_name_claim_release_smoke.md#L18-L25); [CHANGELOG.md:16-20](../../../../CHANGELOG.md#L16-L20); this issue file (below, §Name claim record). `git diff --stat HEAD -- pyproject.toml` reports 29 insertions — all from T01's metadata landing, none from T02. T02 spec explicitly forbids pyproject edit; inspection of the pyproject.toml diff shows zero T02-attributable lines (the name claim is passive until T07's `uv publish`). | ✅ PASS |
| AC-2 | `scripts/release_smoke.sh` exists, is executable (`chmod +x`), uses `set -euo pipefail`, and cleans up its temp dir via `trap`. | [`ls -la`](..) reports `-rwxrwxr-x` at `/home/papa-jochy/prj/ai-workflows/scripts/release_smoke.sh` (user+group execute bits set). [scripts/release_smoke.sh:19](../../../../scripts/release_smoke.sh#L19) `set -euo pipefail` at top. [scripts/release_smoke.sh:29-33](../../../../scripts/release_smoke.sh#L29-L33) `TMP_DIR="$(mktemp -d ...)"` + `cleanup() { rm -rf "$TMP_DIR"; }` + `trap cleanup EXIT`. | ✅ PASS |
| AC-3 | Smoke script's stages 1–5 (hermetic) run green on current `main` tip: `uv build --wheel` produces exactly one wheel; `uv venv` creates fresh venv; `uv pip install` installs wheel; `aiw --help` + `aiw-mcp --help` exit 0; `aiw list-runs` against fresh `AIW_STORAGE_DB` exits 0 (migrations applied). | Manual run of `bash scripts/release_smoke.sh` (2026-04-22) produces literal output: `[1/6] uv build --wheel ... built: ai_workflows-0.1.0-py3-none-any.whl` → `[2/6] uv venv (fresh, outside repo) ...` → `[3/6] uv pip install <wheel> ...` → `[4/6] aiw --help + aiw-mcp --help ...` → `[5/6] aiw list-runs against fresh AIW_STORAGE_DB (migrations apply) ...` → `=== OK — release smoke passed ===`. Exit code 0. Stage 5's `AIW_STORAGE_DB` assertion at [scripts/release_smoke.sh:113-116](../../../../scripts/release_smoke.sh#L113-L116) confirms the DB file lands on disk (yoyo applied migrations successfully). | ✅ PASS |
| AC-4 | Stage 6 (real-provider run) is gated by both `AIW_E2E=1` and `GEMINI_API_KEY` present. When either is missing, script prints a skip line and continues without error. **Not run in audit** — gated by operator invocation. | [scripts/release_smoke.sh:125](../../../../scripts/release_smoke.sh#L125) `if [[ "${AIW_E2E:-0}" == "1" && -n "${GEMINI_API_KEY:-}" ]]; then` — double-gate via short-circuit AND. Manual audit run (both env vars unset) produced `[6/6] real-provider planner run (optional) ... skip — set AIW_E2E=1 and GEMINI_API_KEY to exercise this stage` followed by `=== OK — release smoke passed ===` and exit 0. | ✅ PASS |
| AC-5 | `scripts/release_smoke.sh` is **not** referenced from `.github/workflows/ci.yml`. | `grep -n release_smoke .github/workflows/ci.yml` returns zero matches; audit fallback `echo` prints `(not in CI — AC-5 verified)`. CI stays hermetic; the live-provider stage would cost tokens per PR and the hermetic stages 1-5 duplicate `tests/test_wheel_contents.py`. Matches spec §Deliverables 2 "Not added to CI" paragraph. | ✅ PASS |
| AC-6 | `design_docs/phases/milestone_13_v0_release/release_runbook.md` exists, ≤ 100 lines, covers the four sections named in §Deliverables 3. Runbook stays on `design` branch (will be pruned from `main` at T05). | `wc -l` reports **77 lines** (≤ 100 cap). Four top-level sections present at [release_runbook.md:11](../release_runbook.md#L11) `## 1. When to run this`, [release_runbook.md:23](../release_runbook.md#L23) `## 2. Pre-flight check`, [release_runbook.md:32](../release_runbook.md#L32) `## 3. Run the smoke`, [release_runbook.md:55](../release_runbook.md#L55) `## 4. Optional live-provider pass`. Header line 5: `**Branch residence:** \`design\` branch only. M13 T05 prunes this file from \`main\`...`. | ✅ PASS |
| AC-7 | `tests/test_wheel_contents.py` gains `test_built_wheel_excludes_builder_mode_artefacts` covering absence of `design_docs/`, `CLAUDE.md`, `.claude/commands/`. Shares the `built_wheel` fixture with the two T01 tests — no new fixture. Passes. | [tests/test_wheel_contents.py:115-141](../../../../tests/test_wheel_contents.py#L115-L141) — third test `test_built_wheel_excludes_builder_mode_artefacts(built_wheel: Path)` taking the module-scoped fixture by name. Asserts `forbidden_prefixes = ("design_docs/", ".claude/commands/")` against every archive entry (`not name.startswith(prefix)`) + discrete `assert "CLAUDE.md" not in names`. Green in full pytest run: `tests/test_wheel_contents.py ...` (three dots — two from T01, one new). No new fixture; no duplicated `uv build` subprocess call. | ✅ PASS |
| AC-8 | `uv run pytest` green (614 existing + 1 new = 615 tests). | `uv run pytest` → `615 passed, 5 skipped, 2 warnings in 25.62s`. 0 failures. Baseline 614 + 1 new exclusion test = 615. The 5 skipped are the pre-existing live-mode e2e smokes (4) + live eval replay (1) — unchanged from T01's baseline. | ✅ PASS |
| AC-9 | `uv run lint-imports` reports 4 contracts kept, 0 broken. | `uv run lint-imports` → `Contracts: 4 kept, 0 broken.` All four contracts KEPT: `primitives cannot import graph, workflows, or surfaces`; `graph cannot import workflows or surfaces`; `workflows cannot import surfaces`; `evals cannot import surfaces`. M13 T02 adds no layer contract. | ✅ PASS |
| AC-10 | `uv run ruff check` clean. Script-only edits (bash) outside ruff's scope; one new Python test block lints clean. | `uv run ruff check` → `All checks passed!`. The new test appends to an existing Python file without changing imports or adding unused names. Bash + markdown files are out of ruff's scope (confirmed by `pyproject.toml [tool.ruff] include` settings — Python-only). | ✅ PASS |
| AC-11 | CHANGELOG `[Unreleased]` entry lists files + ACs + deviation note (smoke substitutes `list-runs` for `run --no-wait` in hermetic default path). | [CHANGELOG.md:10-82](../../../../CHANGELOG.md#L10-L82) — `### Changed — M13 Task 02: PyPI name claim + release smoke + wheel excludes (2026-04-22)` block. Files touched enumerated at [:64-72](../../../../CHANGELOG.md#L64-L72) (scripts/release_smoke.sh new, release_runbook.md new, test_wheel_contents.py one test appended, task_02 spec new, CHANGELOG itself). 12 ACs enumerated at [:73-82](../../../../CHANGELOG.md#L73-L82). Deviation block at [:48-62](../../../../CHANGELOG.md#L48-L62) — explicit wording: *"Milestone README §Exit criteria 3 + task_02 spec §Deliverables 2 called for the smoke to run `aiw run planner --goal 'wheel-smoke' --run-id wheel-smoke --no-wait` against a stubbed provider. Two gaps prevented a literal implementation … The shipped script substitutes `aiw list-runs` for `aiw run` in the hermetic default path …"*. | ✅ PASS |
| AC-12 | Zero diff under `ai_workflows/`. T02, like T01, is packaging-only — no runtime code change. | `git diff --name-only HEAD -- 'ai_workflows/'` returns empty (zero output before the `head -20` pipeline). `git status --short` shows `CHANGELOG.md` + `pyproject.toml` modified (both from T01's prior uncommitted work plus T02's CHANGELOG append) plus untracked: `design_docs/phases/milestone_13_v0_release/issues/`, `release_runbook.md`, `task_02_name_claim_release_smoke.md`, `scripts/release_smoke.sh`, `tests/test_wheel_contents.py` (T01's create, plus T02's append). Zero `ai_workflows/` paths modified or untracked. | ✅ PASS |

---

## 🔴 HIGH

_None._

## 🟡 MEDIUM

_None._

## 🟢 LOW

_None._

---

## Additions / deviations beyond spec — audited and justified

### 1. Spec deviation: `aiw list-runs` substitutes for `aiw run --no-wait` in the hermetic default path

**Spec.** Milestone README §Exit criteria 3 + T02 spec §Deliverables 2 both prescribed the hermetic smoke run `aiw run planner --goal 'wheel-smoke' --run-id wheel-smoke --no-wait` against a stubbed provider.

**Shipped behaviour.** Stage 5 runs `aiw list-runs` against a fresh `AIW_STORAGE_DB` instead.

**Justification** (§Deliverables 2 spec deviation block + CHANGELOG [:48-62](../../../../CHANGELOG.md#L48-L62)):

- `aiw run` has no `--no-wait` flag today. `grep -rn no-wait ai_workflows/cli.py` returns zero matches. Adding one is fundamental graph-surface scope (return `run_id` before the first `HumanGate` fires rather than blocking) — out-of-scope for a packaging-only task.
- No shell-surface provider stub exists. `StubLLMAdapter` is a Python test helper under `ai_workflows/evals/_stub_adapter.py`, not an `AIW_*`-env-configurable runtime swap.
- `aiw list-runs` exercises the same `SQLiteStorage.open()` + migrations-apply code path that `aiw run` would open first — which is the *actual* thing the smoke is meant to gate (T01's `force-include` hook is the regression surface).
- The real-provider `aiw run` path lives in stage 6 behind the standard `AIW_E2E=1 + GEMINI_API_KEY` double-gate used by `tests/e2e/` today — matching the README's own "or against real Gemini Flash if `GEMINI_API_KEY` + `AIW_E2E=1` are set" clause verbatim.

**Verdict.** Kept. The deviation strengthens hermetic-ness (zero provider dependency in the default path) without weakening the headline gate (migrations-from-wheel regression still detected). Recorded in spec + CHANGELOG + this issue file. Not a forward-deferral — the `--no-wait` flag and shell-surface stub are genuine packaging/surface gaps, but neither is a T02 blocker; both belong to post-v0.1.0 triggers if they ever surface.

### 2. Stage-failure diagnostic table in the release runbook

**Spec.** §Deliverables 3 prescribed four sections; did not specify a per-stage failure-interpretation table.

**Shipped.** [release_runbook.md §3](../release_runbook.md#L32) contains a five-row table mapping each hermetic stage to "What it exercises / If it fails / First thing to check". Row 5 (migrations-from-wheel) explicitly names the yoyo "no migration scripts found" error signature plus the `unzip -l <wheel> | grep migrations/` recovery check — the failure mode T01's `force-include` regression would produce.

**Justification.** The runbook is "builder-only" — its audience is future-me returning to the release gate after a long gap. Without a stage-failure map, the first live failure would require reconstruction of context. Cost of adding: 15 lines of markdown. Cost of omitting: at least one wasted debug cycle per release failure. Kept.

### 3. T02 spec file landed as part of the implementation, not pre-existing

**Convention.** Milestone README §Task order line 96 says *"Per-task spec files land as each predecessor closes (same convention as M10 / M11 / M12)."* T02's spec (`task_02_name_claim_release_smoke.md`) was drafted at T02 kickoff (2026-04-22, immediately after T01 closed clean), not before. Listed among "files touched" in the CHANGELOG T02 block.

**Verdict.** Convention-compliant. Spec authored **before** implementation (read from [task_02 spec:1-146](../task_02_name_claim_release_smoke.md) during implement phase); implementation strictly against the spec. No retroactive spec-drafting.

---

## Name claim record

- **Date:** 2026-04-22
- **Command:** `curl -sS -o /dev/null -w '%{http_code}\n' https://pypi.org/pypi/ai-workflows/json`
- **Response:** `404`
- **Interpretation:** `ai-workflows` is available on PyPI. No namespace alternative (`aiw-framework`, `ai-workflows-langgraph`, `<user>-ai-workflows`) needed.
- **Held by:** Passive — the claim is owned by whoever first uploads `ai-workflows==<version>` to PyPI. T07 is the first upload; until then the name is theoretically available to anyone.
- **Contingency:** If a race occurs (someone else uploads `ai-workflows` before T07), T07's spec (drafted at T06 close) will document the fallback — re-check at T07 kickoff, namespace via one of the three candidates, update `[project].name` + every doc that quotes the name. CLI script names (`aiw`, `aiw-mcp`) stay stable regardless.

---

## Gate summary

| Gate | Command | Result |
| --- | --- | --- |
| pytest | `uv run pytest` | **615 passed, 5 skipped, 0 failed** (5 skipped = 4 live-mode e2e smokes + live eval replay; 615 = 614 baseline + 1 new exclusion test) |
| import-linter | `uv run lint-imports` | **4 kept, 0 broken** (primitives / graph / workflows / evals contracts all KEPT) |
| ruff | `uv run ruff check` | **All checks passed!** |
| release smoke stages 1-5 (manual) | `bash scripts/release_smoke.sh` | **OK — release smoke passed** (build → venv → install → help-smoke → migrations-from-wheel → stage 6 skipped cleanly) |
| CI reference check | `grep -n release_smoke .github/workflows/ci.yml` | **No matches** — smoke not in CI (AC-5) |

---

## Issue log — cross-task follow-up

_None._ T02 is self-contained. No cross-task forward-deferrals.

Reference forward-looking items (surfaced for context, not open):

- **M13 T07** will re-run the smoke script as a mandatory pre-`uv publish` gate; the runbook's §2 pre-flight checklist is the operator's checklist.
- **M13 T05** will delete `design_docs/phases/milestone_13_v0_release/release_runbook.md` from the `main` branch (it stays on `design`). Deletion is T05's scope, not a T02 issue.
- **M13 T07** may surface a `--no-wait` CLI flag need if the release smoke's stage 6 proves too slow for interactive use. Not a T02 issue — documented as "out of scope" in T02 spec §Out of scope and the deviation block.

---

## Deferred to nice_to_have

_None._ T02 adopts nothing from `nice_to_have.md`. The CI-gated publish-on-tag candidate stays parked in `nice_to_have.md §17+` per milestone README §Propagation status; T02 did not revive it.

---

## Propagation status

**No forward-deferrals.** No carry-over written to any sibling task file. No `nice_to_have.md` entry added. T02's `built_wheel` fixture reuse pattern inherited naturally from T01's issue file (ISS-none; just the module-scoped fixture convention). No cross-file propagation required at T02 close.
