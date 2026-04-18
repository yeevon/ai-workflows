# ai-workflows

Composable AI workflow framework built on the
[`pydantic-ai`](https://ai.pydantic.dev/) ecosystem. Primitives wrap the
`pydantic-ai` `Agent` / `Model` surface with tier routing, cost tracking,
budget caps, retry policy, multi-breakpoint prompt caching, and
workflow-aware SQLite storage. Components (`Worker`, `Validator`,
`Pipeline`, `AgentLoop`, …) compose those primitives into reusable
building blocks. Workflows wire components together for specific tasks
(JVM modernization, doc generation, code review, …).

## Status

Early development. Milestone 1 (Primitives) is in progress:

- ✅ **M1 Task 01 — Project Scaffolding** (2026-04-18) — repo layout, CI,
  `import-linter` contracts, Typer CLI shell. See
  [`CHANGELOG.md`](CHANGELOG.md) for details.
- ⬜ M1 Tasks 02–12 — shared types, model factory, prompt caching, tool
  registry, stdlib tools, tiers loader, storage, cost tracker, retry,
  logging, CLI primitives.

No runtime behaviour yet; the `aiw` CLI currently exposes only `--help`
and a `version` subcommand.

## Requirements

- Python **3.12+** (runtime target: 3.13, pinned in `.python-version`)
- [`uv`](https://docs.astral.sh/uv/) for dependency and venv management

## Quickstart

```bash
# Install all runtime + dev dependencies into a local .venv
uv sync

# Typer CLI (expands over M1 Task 12)
uv run aiw --help
uv run aiw version

# Run the test suite
uv run pytest
```

## Architecture

Three strictly layered sub-packages, enforced at lint time by
`import-linter` contracts declared in `pyproject.toml`:

```
ai_workflows/
├── primitives/    # LLM client factory, tool registry, storage, retry, …
├── components/    # Worker, Validator, Pipeline, AgentLoop, …
└── workflows/     # Concrete workflow definitions
```

Rules (see `pyproject.toml` for the machine-enforced version):

1. `primitives` must not import from `components` or `workflows`.
2. `components` must not import from `workflows`.
3. *(Deferred to M2 Task 01)* components must not touch each other's
   underscore-prefixed private modules.

## Development gates

Every change must pass these before merge (wired into
[`.github/workflows/ci.yml`](.github/workflows/ci.yml)):

```bash
uv run pytest           # test suite
uv run lint-imports     # architectural contracts
uv run ruff check       # linting
```

A separate CI job greps `tiers.yaml` and `pricing.yaml` for
`sk-ant-…` patterns and fails the build if any are found — API keys live
in environment variables, never in committed config.

## Repository layout

| Path                                        | Purpose                                                       |
| ------------------------------------------- | ------------------------------------------------------------- |
| [`ai_workflows/`](ai_workflows/)            | Package source — primitives, components, workflows            |
| [`tests/`](tests/)                          | pytest suite; mirrors the package structure                   |
| [`docs/`](docs/)                            | User-facing docs (placeholders until authored)                |
| [`design_docs/`](design_docs/)              | Canonical design; milestone/task breakdowns                   |
| [`migrations/`](migrations/)                | `yoyo-migrations` SQL scripts                                 |
| [`tiers.yaml`](tiers.yaml)                  | Model tier configuration (populated in M1 Task 07)            |
| [`pricing.yaml`](pricing.yaml)              | Per-model pricing for the cost tracker (M1 Task 09)           |
| [`CHANGELOG.md`](CHANGELOG.md)              | Keep-a-Changelog entries, milestone/task-scoped               |
| [`CLAUDE.md`](CLAUDE.md)                    | Builder / Auditor workflow instructions for Claude Code       |

## Further reading

- [`design_docs/phases/milestone_1_primitives/`](design_docs/phases/milestone_1_primitives/)
  — full task breakdown for M1.
- [`docs/architecture.md`](docs/architecture.md) — architecture overview
  (to be authored by M1 Task 11).
- [`docs/writing-a-component.md`](docs/writing-a-component.md) —
  component authoring guide (M2 Task 01).
- [`docs/writing-a-workflow.md`](docs/writing-a-workflow.md) — workflow
  authoring guide (M3 Task 01).
