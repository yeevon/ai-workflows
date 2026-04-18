# Changelog

All notable changes to ai-workflows are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added — M1 Task 01: Project Scaffolding (2026-04-18)

Initial project skeleton built on the `pydantic-ai` ecosystem. Establishes
the three-layer architecture (primitives → components → workflows) and the
tooling that enforces it. No runtime behaviour yet — that lands in M1
Tasks 02–12.

#### Initial build

- **`pyproject.toml`**
  - Runtime deps: `pydantic-ai`, `pydantic-graph`, `pydantic-evals`,
    `logfire`, `anthropic`, `httpx`, `pydantic`, `pyyaml`, `structlog`,
    `typer`, `yoyo-migrations`.
  - Optional `dag` extra for `networkx` (installed in M4).
  - Dev group: `import-linter`, `pytest`, `pytest-asyncio`, `ruff`.
  - Console script: `aiw = ai_workflows.cli:app`.
  - Two `import-linter` contracts encoding the layer rules:
    1. primitives cannot import components or workflows
    2. components cannot import workflows

    A third contract ("components cannot peek at each other's private
    state") is documented in the Task 01 spec but is **deferred**:
    `import-linter`'s wildcard syntax only allows `*` to replace a whole
    module segment, so `components.*._*` is rejected at load time.
    The rule comes back in M2 Task 01 when components exist and their
    private modules can be enumerated.
  - `ruff` defaults: line length 100, py312 target, rule set
    `E,F,I,UP,B,SIM`.
  - `pytest-asyncio` set to `auto` mode.
- **Package layout** (`ai_workflows/`)
  - `ai_workflows/__init__.py` — exposes `__version__` and documents the
    layering rule.
  - `ai_workflows/cli.py` — minimal Typer app with `--help` and a
    `version` subcommand. Subcommand groups land in M1 Task 12.
  - `ai_workflows/primitives/__init__.py` plus `llm/` and `tools/`
    subpackages (empty modules, filled in by Tasks 02–11).
  - `ai_workflows/components/__init__.py` (filled by M2 + M4).
  - `ai_workflows/workflows/__init__.py` (filled by M3, M5, M6).
- **Configuration stubs**
  - `tiers.yaml` — empty `tiers: {}` map; real schema lands in Task 07.
  - `pricing.yaml` — empty `models: {}` map; populated by Task 09.
- **Migrations**
  - `migrations/001_initial.sql` — bootstrap migration so `yoyo apply` has
    a tracked history on day one. Task 08 lands the real schema as 002+.
- **CI** (`.github/workflows/ci.yml`)
  - `test` job: `uv sync`, `uv run pytest`, `uv run lint-imports`,
    `uv run ruff check`.
  - `secret-scan` job: greps committed config for `sk-ant-…` patterns and
    fails the build if any are found.
- **Tests** (`tests/test_scaffolding.py`) — acceptance tests for Task 01:
  - All three layers + the CLI module import cleanly.
  - `aiw --help` and `aiw version` succeed via `typer.testing.CliRunner`.
  - Required scaffolding files exist on disk.
  - `pyproject.toml` declares every dependency from the Task 01 spec, the
    `aiw` console script, and the three `import-linter` contracts.
  - `lint-imports` exits 0 (skipped when `import-linter` is not
    installed).

#### Reimplementation

Addresses open issues from the Task 01 audit (M1-T01-ISS-01, M1-T01-ISS-02):

- **`docs/architecture.md`** — placeholder stub; to be authored by M1 Task 11.
- **`docs/writing-a-component.md`** — placeholder stub; to be authored by M2 Task 01.
- **`docs/writing-a-workflow.md`** — placeholder stub; to be authored by M3 Task 01.
- **`tests/test_scaffolding.py`** — extended parametrized file-existence test to cover
  the three new `docs/` placeholders. Test count: 21 → 24.
- **`design_docs/phases/milestone_1_primitives/task_01_project_scaffolding.md`** —
  acceptance criterion for `lint-imports` updated to say "contracts 1 and 2" (not
  "all three"), with a note documenting the Contract 3 deferral to M2 Task 01
  (M1-T01-ISS-01).
- **`pyproject.toml`** — removed accidental duplicate `pytest` entry from
  `[project.dependencies]`; it belongs only in `[dependency-groups].dev`.

#### Cleanup

Addresses open issues from the Task 01 re-audit (ISS-04, ISS-05, ISS-06, ISS-07, ISS-09):

- **`.gitignore`** — drop `.python-version` entry; file is the canonical 3.13 pin (ISS-04).
- **`tests/test_scaffolding.py`** — add `test_secret_scan_regex_matches_known_key_shapes`
  (ISS-05): self-contained pattern test that will break if the CI grep is ever narrowed.
- **`tests/test_scaffolding.py`** — add `test_aiw_console_script_resolves` (ISS-06):
  subprocess-based `aiw --help` gated on `shutil.which("aiw")`; proves the
  `[project.scripts]` entry point resolves beyond what `CliRunner` can verify.
- **`CHANGELOG.md`** — collapsed three Task 01 sub-entries into one
  `### Added — M1 Task 01: Project Scaffolding (2026-04-18)` heading with subsections,
  matching the CLAUDE.md format prescription (ISS-09).

#### Completion marking & README (2026-04-18)

Marks Task 01 as complete in the design docs and replaces the placeholder
`README.md` (closes the last open issue, ISS-03).

- **`design_docs/phases/milestone_1_primitives/task_01_project_scaffolding.md`** — ticked all
  seven acceptance-criteria checkboxes and added a top-of-file `Status: ✅ Complete (2026-04-18)`
  line pointing to the audit log.
- **`design_docs/phases/milestone_1_primitives/README.md`** — appended
  `— ✅ **Complete** (2026-04-18)` to the Task 01 entry in the task order list.
- **`README.md`** — replaced 14-byte stub with a proper project README: description, current
  status (M1 Task 01 done, 02–12 pending), requirements, quickstart, three-layer architecture
  summary with contract rules, the three development gates, repo layout table, and further-reading
  links into `design_docs/` and `docs/`. Resolves ISS-03 (previously deferred to M3 Task 01).
- **`design_docs/phases/milestone_1_primitives/issues/task_01_issue.md`** — flipped ISS-03
  from LOW/open to ✅ RESOLVED and updated the issue-log footer to reflect that every
  Task 01 issue is now closed.

### Notes

- `.python-version` pins to 3.13 (target runtime); `pyproject.toml`
  declares `>=3.12` so the project still builds on the user's laptop where
  3.12 is installed.
- `.gitignore` already excludes `runs/`, `*.db*`, `tiers.local.yaml`, and
  `.env*` — left untouched by this task.
