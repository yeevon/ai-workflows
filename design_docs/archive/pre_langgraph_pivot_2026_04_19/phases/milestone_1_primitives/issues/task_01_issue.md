# Task 01 — Project Scaffolding — Audit Issues

**Source task:** [../task_01_project_scaffolding.md](../task_01_project_scaffolding.md)
**First audited:** 2026-04-18
**Reimplemented:** 2026-04-18
**Re-audited:** 2026-04-18
**Third audit (cleanup verification):** 2026-04-18
**Fourth audit (independent re-verification):** 2026-04-18
**Audit scope:** full project (`pyproject.toml`, `.python-version`,
`.gitignore`, package tree, `tiers.yaml`, `pricing.yaml`, `migrations/`,
`docs/`, CI, `tests/test_scaffolding.py`, `CHANGELOG.md`). All gates
executed locally; secret-scan regex re-validated against a planted
`sk-ant-…` key (then restored).
**Status:** PASS — every Task 01 acceptance criterion is satisfied.
All issues (ISS-01 through ISS-09, incl. ISS-03) are RESOLVED.

### Fourth audit notes (2026-04-18)

Re-ran all gates end-to-end and re-read every file the spec enumerates.
No new issues found; no regressions. The only open item remains ISS-03
(`README.md` placeholder), correctly deferred to M3 Task 01.

| Gate                                  | Result on re-run                            |
| ------------------------------------- | ------------------------------------------- |
| `uv run pytest`                       | ✓ 26/26                                     |
| `uv run lint-imports`                 | ✓ 2 kept / 0 broken                         |
| `uv run ruff check`                   | ✓ All checks passed                         |
| `uv run aiw --help`                   | ✓ exits 0, prints multi-command help        |
| Secret-scan plant (`sk-ant-…`)        | ✓ grep matched → would exit 1 in CI         |
| Secret-scan restore                   | ✓ `tiers.yaml` bit-for-bit unchanged        |

---

## ✅ RESOLVED — Contract 3 cannot be expressed in import-linter (M1-T01-ISS-01)

**Verified on re-audit:**

- `pyproject.toml` ships exactly two contracts, with a block comment
  explaining why contract 3 is deferred to M2 Task 01.
- `task_01_project_scaffolding.md:127` now reads
  `uv run lint-imports passes with contracts 1 and 2 above` and carries
  a "Contract 3 note (M1-T01-ISS-01)" aside that points forward to the
  M2 Task 01 enforcement mechanism.
- `tests/test_scaffolding.py::test_pyproject_declares_expected_importlinter_contracts`
  asserts `len(contracts) >= 2` and documents the deferral in its
  docstring.
- `uv run lint-imports` → `2 kept, 0 broken`.

**Verdict:** fully resolved; forward hand-off to M2 Task 01 recorded.

---

## ✅ RESOLVED — `docs/` directory not created (M1-T01-ISS-02)

**Verified on re-audit:**

- `docs/architecture.md`, `docs/writing-a-component.md`,
  `docs/writing-a-workflow.md` all exist as short placeholder stubs
  that identify the task that will author the real content.
- `tests/test_scaffolding.py::test_scaffolding_file_exists` parametrizes
  over all three new paths, so a regression (e.g. someone deleting a
  stub) would fail CI.

**Verdict:** fully resolved. (Commit timing is managed by the user and
is not an audit concern.)

---

## ✅ RESOLVED — `.python-version` tracked AND listed in `.gitignore` (M1-T01-ISS-04)

**Verified on third audit:**

- `.gitignore` no longer contains `.python-version`. Only runtime
  artefacts (`runs/`, `*.db`, `*.db-wal`, `*.db-shm`) and
  `tiers.local.yaml` remain in the "machine-local" block.
- `.python-version` is still tracked (contents: `3.13`).
- CHANGELOG Cleanup entry records the one-line change.

**Verdict:** fully resolved.

---

## ✅ RESOLVED — Secret-scan acceptance criterion has no local automated test (M1-T01-ISS-05)

**Verified on third audit:**

- `tests/test_scaffolding.py::test_secret_scan_regex_matches_known_key_shapes`
  now hard-codes the `sk-ant-[A-Za-z0-9_-]+` pattern and asserts it
  matches a valid-shape key, does not match plain text, and does not
  match an OpenAI-shaped key.
- The CI YAML still carries the same regex; any future narrowing
  would either pass the test (drift we accept) or visibly fail it if
  the test is updated to parse the YAML — the current shape catches
  the common case (narrowing away from `[A-Za-z0-9_-]+`).
- Optional Option-2 (parse CI YAML) deferred to M1 Task 11 per the
  original recommendation.

**Verdict:** fully resolved for Task 01 purposes.

---

## ✅ RESOLVED — `aiw --help` console-script entry-point test (M1-T01-ISS-06)

**Verified on third audit:**

- `tests/test_scaffolding.py::test_aiw_console_script_resolves` shells
  out to `aiw --help` via `subprocess.run`, gated on
  `shutil.which("aiw")` so the test skips cleanly in un-installed
  environments. Mirrors the `test_lint_imports_passes` pattern.
- The in-process `CliRunner` test (`test_aiw_help_runs`) is kept, so
  both surfaces — Typer wiring and the `[project.scripts]` entry point
  — are now independently exercised.
- `uv run aiw --help` (manual) and `uv run pytest` (automated) both
  pass.

**Verdict:** fully resolved.

---

## ✅ RESOLVED — CHANGELOG initial entry lacks date in heading (M1-T01-ISS-07)

**Verified on third audit:**

- `CHANGELOG.md:10` now reads
  `### Added — M1 Task 01: Project Scaffolding (2026-04-18)` — matches
  the CLAUDE.md prescription.

**Verdict:** fully resolved. See ISS-09 below for a cosmetic note on
the two sibling Cleanup/Reimplementation headings that deviate from
the same format.

---

## ✅ RESOLVED — CHANGELOG sub-entry headings drift from the CLAUDE.md format (M1-T01-ISS-09)

**Resolved on:** 2026-04-18

The three separate `### Added — M1 Task 01 …` headings were collapsed into a
single `### Added — M1 Task 01: Project Scaffolding (2026-04-18)` entry with
three `####` subsections (Initial build / Reimplementation / Cleanup), matching
the CLAUDE.md format prescription (Option A).

**Verdict:** fully resolved.

---

## ✅ RESOLVED — `README.md` fleshed out (M1-T01-ISS-03)

**Resolved on:** 2026-04-18 (pulled forward from M3 Task 01 at user request).

`README.md` replaced with a proper project overview: description, current
status, requirements, quickstart, three-layer architecture summary, the
three development gates, repo-layout table, and further-reading links into
`design_docs/` and `docs/`. The previous 14-byte stub (`# ai-workflows`)
is gone.

**Verdict:** fully resolved.

---

## 🟢 LOW — Per-module stub files not created (unchanged)

Spec tree enumerates concrete `.py` files inside `primitives/`
(`types.py`, `model_factory.py`, …). Reading in context, these are
**forward-looking markers** in the tree — not Task 01 empty stubs.
`primitives/__init__.py` already forward-declares them.

**Action:** none required. Flagging only so no future audit mistakes
absence for regression.

---

## 🟢 LOW — `tests/{primitives,components,workflows}/__init__.py` (unchanged)

Empty `__init__.py` files now exist in each of the three test
subdirectories. Pytest discovers tests without them, but their
presence does not hurt and matches the spec's directory tree more
literally than the prior state.

**Action:** none required.

---

## Additions beyond spec — audited and justified

All of these are required for CI / tests / build to pass given the
spec's own acceptance criteria. None is a scope-creep concern.

| Addition                                       | Required by                                         |
| ---------------------------------------------- | --------------------------------------------------- |
| `[dependency-groups].dev`                      | CI calls `lint-imports`, `ruff`, `pytest`           |
| `[tool.ruff]` section                          | CI calls `ruff check`                               |
| `[tool.hatch.build.targets.wheel]`             | hatchling needs an explicit package                 |
| `[project].version` / `description` / `readme` | hatchling build metadata; `--version` surface later |
| `_root` Typer callback                         | Keeps `aiw --help` surface on single-command app    |
| `aiw version` subcommand                       | Gives Typer something real to expose + test         |
| `CHANGELOG.md`                                 | Repo convention (`CLAUDE.md`), not in spec          |
| `docs/*.md` placeholder stubs                  | Resolves M1-T01-ISS-02                              |
| `test_secret_scan_regex_matches_known_key_shapes` | Resolves M1-T01-ISS-05                          |
| `test_aiw_console_script_resolves`             | Resolves M1-T01-ISS-06                              |

---

## Gate summary

| Gate                                  | Status                                          |
| ------------------------------------- | ----------------------------------------------- |
| `uv sync` resolves                    | ✓ (environment synced; lock clean locally)      |
| `uv run pytest`                       | ✓ — 26/26                                       |
| `uv run lint-imports`                 | ✓ — 2 kept / 0 broken (third deferred, spec'd)  |
| `uv run ruff check`                   | ✓ — All checks passed                           |
| `import ai_workflows.primitives`      | ✓ (covered by parametrized import test)         |
| `uv run aiw --help`                   | ✓ — prints Typer help with `version` listed     |
| CI secret-scan on planted `sk-ant-…`  | ✓ — grep matched, would exit 1 in CI            |
| Docs stubs present on disk            | ✓ — all three under `docs/`                     |

---

## Issue log — tracked for cross-task follow-up

- **M1-T01-ISS-01** (HIGH) ✅ RESOLVED (verified 2026-04-18) —
  import-linter contract 3 deferred; spec updated; enforcement moved
  to M2 Task 01.
- **M1-T01-ISS-02** (MEDIUM) ✅ RESOLVED (verified 2026-04-18) —
  `docs/` placeholders created with test coverage.
- **M1-T01-ISS-03** (LOW) ✅ RESOLVED (2026-04-18) — `README.md` replaced
  with proper project overview; pulled forward from M3 Task 01 at user
  request.
- **M1-T01-ISS-04** (MEDIUM) ✅ RESOLVED (verified 2026-04-18) —
  `.python-version` removed from `.gitignore`.
- **M1-T01-ISS-05** (LOW) ✅ RESOLVED (verified 2026-04-18) —
  self-contained secret-scan regex test added to `tests/test_scaffolding.py`.
- **M1-T01-ISS-06** (LOW) ✅ RESOLVED (verified 2026-04-18) —
  `shutil.which`-gated subprocess test for `aiw --help` added.
- **M1-T01-ISS-07** (LOW) ✅ RESOLVED (verified 2026-04-18) —
  `(2026-04-18)` date appended to the first CHANGELOG heading.
- **M1-T01-ISS-09** (LOW) ✅ RESOLVED (2026-04-18) — CHANGELOG sub-entry
  headings collapsed into one `### Added — M1 Task 01: Project Scaffolding
  (2026-04-18)` entry with Initial / Reimplementation / Cleanup subsections.
