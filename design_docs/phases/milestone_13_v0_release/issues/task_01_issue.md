# Task 01 — `pyproject.toml` polish + wheel contents fix — Audit Issues

**Source task:** [../task_01_pyproject_polish.md](../task_01_pyproject_polish.md)
**Audited on:** 2026-04-22
**Audit scope:** pyproject.toml diff, tests/test_wheel_contents.py (new), CHANGELOG.md [Unreleased] entry, architecture.md §3 / §6 / KDR grid, sibling task files (none at M13 beyond T01), milestone README exit criteria, manual `uv build` + `unzip -l` wheel inspection.
**Status:** ✅ PASS (Cycle 1) — all 9 ACs met, zero HIGH / MEDIUM / LOW, three gates green (614 passed / 5 skipped, 4 import-linter contracts kept, ruff clean).

---

## Design-drift check

| Axis | Evidence | Verdict |
| --- | --- | --- |
| New dependency? | Zero. `dependencies = [...]` block untouched; dev group untouched. No `optional-dependencies`. | ✅ Clean. |
| New module or layer? | Zero. Diff is 2× `pyproject.toml` blocks + 1× new `tests/test_wheel_contents.py` + `CHANGELOG.md`. No `ai_workflows/` diff. Four-layer import contract unaffected — `uv run lint-imports` reports 4 kept, 0 broken. | ✅ Clean. |
| LLM call added? | None. | ✅ Clean. |
| Checkpoint / resume logic? | None. | ✅ Clean. |
| Retry logic? | None. | ✅ Clean. |
| Observability? | None. | ✅ Clean. |
| `anthropic` SDK / `ANTHROPIC_API_KEY`? | Grep over diff — no matches. KDR-003 preserved. | ✅ Clean. |
| `nice_to_have.md` scope creep? | Task spec §Out of scope explicitly excludes PyPI upload, README install section, skill uvx option, CHANGELOG `[0.1.0]` release section, version bump, `[project.optional-dependencies]`, and new CI jobs. None of these appear in the diff. | ✅ Clean. |
| architecture.md §6 alignment | `hatchling` build backend already declared at `[build-system].requires`; `force-include` is a hatchling-native hook, not a new dependency. | ✅ Clean. |

**No design drift. No KDR violation. No architectural §X contradiction.**

---

## AC grading

Graded individually against [task_01_pyproject_polish.md:82-91](../task_01_pyproject_polish.md#L82-L91).

| # | Acceptance criterion | Evidence | Verdict |
| --- | --- | --- | --- |
| AC-1 | `pyproject.toml [project]` contains `authors`, `urls.Homepage`, `urls.Repository`, `urls.Issues`, `keywords`, `classifiers` per spec. | [pyproject.toml:13](../../../../pyproject.toml#L13) `authors = [{name = "Jose de Lima", email = "delimajm@gmail.com"}]`; [pyproject.toml:14](../../../../pyproject.toml#L14) `keywords = ["langgraph", "mcp", "claude-code", "ai-workflow", "litellm", "ollama"]`; [pyproject.toml:15-23](../../../../pyproject.toml#L15-L23) classifiers include all seven spec entries (Development Status :: 3 - Alpha, Intended Audience :: Developers, License :: OSI Approved :: MIT License, OS Independent, Python :: 3, Python :: 3.12, Topic :: Software Development :: Libraries); [pyproject.toml:37-40](../../../../pyproject.toml#L37-L40) `[project.urls]` with Homepage / Repository / Issues pointing at `github.com/yeevon/ai-workflows`. Existing keys not reordered. | ✅ PASS |
| AC-2 | `[tool.hatch.build.targets.wheel.force-include]` maps `"migrations"` → `"migrations"`. | [pyproject.toml:71-72](../../../../pyproject.toml#L71-L72) contains the exact block. Preceded by an explanatory comment at [pyproject.toml:61-70](../../../../pyproject.toml#L61-L70) naming the shipping-bug and why `migrations/` stays at repo root rather than moving under `ai_workflows/`. | ✅ PASS |
| AC-3 | `uv build --wheel` produces a wheel whose archive includes `migrations/001_initial.sql` and `migrations/002_reconciliation.sql`. | Manual `uv build --wheel` produces `ai_workflows-0.1.0-py3-none-any.whl` (50 files, 470973 bytes). `unzip -l` confirms `migrations/001_initial.sql` (2858 bytes) + `migrations/002_reconciliation.sql` (1458 bytes) + `migrations/003_artifacts.sql` (938 bytes) + all three `*.rollback.sql` peers. No `design_docs/`, `CLAUDE.md`, or `.claude/` entries in wheel (hatchling sweeps only what `packages` + `force-include` declare). | ✅ PASS |
| AC-4 | Storage layer resolves `migrations/` correctly under a wheel install. | No code change needed. Existing `_default_migrations_dir()` at [ai_workflows/primitives/storage.py:206-212](../../../../ai_workflows/primitives/storage.py#L206-L212) walks `Path(__file__).resolve().parent.parent.parent / "migrations"`. From a wheel install that lands at `site-packages/ai_workflows/primitives/storage.py`, the walk-up resolves to `site-packages/migrations/` — which is exactly where `force-include "migrations" = "migrations"` places the directory. Matches option 1 in the task spec (§Storage layer). End-to-end install + run validation is T02's release-smoke script scope, not T01's. | ✅ PASS |
| AC-5 | `tests/test_wheel_contents.py` lands with both tests green. | [tests/test_wheel_contents.py](../../../../tests/test_wheel_contents.py) ships `test_built_wheel_includes_migrations` + `test_built_wheel_includes_ai_workflows_package` sharing a module-scoped `built_wheel` fixture. Both green: `tests/test_wheel_contents.py::test_built_wheel_includes_migrations PASSED` and `::test_built_wheel_includes_ai_workflows_package PASSED`. Skip gate for missing `uv` CLI in place. | ✅ PASS |
| AC-6 | No dependency change. No version bump. `[project].version` stays `0.1.0`. | [pyproject.toml:7](../../../../pyproject.toml#L7) `version = "0.1.0"` unchanged. `dependencies` list byte-identical to pre-T01 — confirmed by inspection. No new `[project.optional-dependencies]` block. | ✅ PASS |
| AC-7 | No diff under `ai_workflows/workflows/`, `ai_workflows/mcp/`, `ai_workflows/graph/`. | `git diff --name-only` returns `CHANGELOG.md` + `pyproject.toml`. `git ls-files --others --exclude-standard` returns `tests/test_wheel_contents.py`. Zero paths under `ai_workflows/`. | ✅ PASS |
| AC-8 | `uv run pytest` + `uv run lint-imports` (4 contracts kept) + `uv run ruff check` all clean. | `uv run pytest` → 614 passed, 5 skipped (the four e2e smokes + live-mode eval replay), 0 failed (+2 from M13 T01's new tests — previous baseline 612). `uv run lint-imports` → 4 kept, 0 broken. `uv run ruff check` → All checks passed!. | ✅ PASS |
| AC-9 | CHANGELOG entry under `[Unreleased]` lists files + ACs + "no runtime behaviour change" note. | [CHANGELOG.md:10-68](../../../../CHANGELOG.md#L10-L68) — `### Changed — M13 Task 01: pyproject polish + wheel migrations bundle (2026-04-22)`. Opens with the "no runtime behaviour change" note verbatim. Lists all three files touched (`pyproject.toml`, `tests/test_wheel_contents.py`, `CHANGELOG.md`) plus the explicit "not touched" call-out for `ai_workflows/primitives/storage.py` with the reason (existing walk-up resolves correctly). ACs 1-9 enumerated. | ✅ PASS |

---

## 🔴 HIGH

_None._

## 🟡 MEDIUM

_None._

## 🟢 LOW

_None._

---

## Additions beyond spec — audited and justified

### 1. Whole-set equality assertion between shipped and on-disk `migrations/*.sql`

The task spec (§tests/test_wheel_contents.py item 1) prescribes: *"assert `migrations/001_initial.sql` and `migrations/002_reconciliation.sql` are both present as archive entries."* The shipped test contains both spec-named assertions **plus** a whole-set equality check between the shipped `migrations/*.sql` entries and the repo's `migrations/*.sql` files on disk.

**Justification.** When the spec was drafted (2026-04-21) the repo had two migrations. It now has three — `003_artifacts.sql` landed at M6. Without the set-equality check, the spec-named assertions would pass even if `003_artifacts.sql` (or any future migration) was silently dropped from the wheel — which is exactly the shipping-bug class this task exists to close. The addition is a test-quality reinforcement of the stated AC-3 intent ("wheel must ship the migrations data"), not new scope. No new dependency, no new layer, no new test file. Kept.

### 2. `003_artifacts.sql` covered implicitly

Same test, same justification — the `003_artifacts.sql` migration is not named in the spec but is caught by the set-equality assertion. Kept.

### 3. Explanatory comment block above `[tool.hatch.build.targets.wheel.force-include]`

Ten-line comment at [pyproject.toml:61-70](../../../../pyproject.toml#L61-L70) explaining (a) why `force-include` is needed, (b) how the Storage walk-up resolves against the resulting wheel layout, (c) why `migrations/` stays at repo root rather than moving under `ai_workflows/` (four-layer contract). No functional effect; serves future-maintainer context. Matches the repo's convention of commenting non-obvious `pyproject.toml` blocks (see existing comments at `[tool.ruff]`, `[tool.importlinter]`). Kept.

---

## Gate summary

| Gate | Command | Result |
| --- | --- | --- |
| pytest | `uv run pytest -q` | **614 passed, 5 skipped, 0 failed** (5 skipped = 4 e2e smokes + live eval replay; +2 vs. post-M14 baseline of 612) |
| import-linter | `uv run lint-imports` | **4 kept, 0 broken** (primitives / graph / workflows / evals contracts all KEPT) |
| ruff | `uv run ruff check` | **All checks passed!** |
| wheel build (manual) | `uv build --wheel` | Produces 50-file wheel; `migrations/*.sql` present, `ai_workflows/` swept, zero builder-mode artefacts in archive |

---

## Issue log — cross-task follow-up

_None._ T01 is self-contained. T02 picks up the wheel-excludes test (`design_docs/` / `CLAUDE.md` absence assertions) per milestone README §Task order line 88; the inclusion test landed here gives T02 a natural pattern to compose over.

---

## Deferred to nice_to_have

_None._ T01 adopts nothing from `nice_to_have.md`.

---

## Propagation status

**No forward-deferrals.** No carry-over written to any sibling task file. No `nice_to_have.md` entry added. M13 T02 spec will be drafted next; it inherits the `built_wheel` fixture pattern naturally (same test file, add assertions for absence of builder-mode paths). No cross-file propagation required at T01 close.
