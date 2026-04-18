# Task 01 — Project Scaffolding

**Issues:** R-01, R-02, R-03, R-04, R-05, R-06, R-07, X-06, CRIT-10, SD-04

## What to Build

Set up the repo with `pydantic-ai` substrate, `yoyo-migrations`, import-linter for 3-layer enforcement, and logfire for OTel observability (wired later in M3).

## Deliverables

### `pyproject.toml`

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "ai-workflows"
requires-python = ">=3.12"
dependencies = [
  "pydantic-ai>=1.0",
  "pydantic-graph>=1.0",
  "pydantic-evals>=1.0",
  "logfire>=2.0",
  "anthropic>=0.40",
  "httpx>=0.27",
  "pydantic>=2.0",
  "pyyaml>=6.0",
  "structlog>=24.0",
  "typer>=0.12",
  "yoyo-migrations>=9.0",
]

[project.optional-dependencies]
dag = ["networkx>=3.0"]   # installed in M4 when DAG Orchestrator lands

[project.scripts]
aiw = "ai_workflows.cli:app"

[tool.pytest.ini_options]
asyncio_mode = "auto"

[tool.importlinter]
root_package = "ai_workflows"

[[tool.importlinter.contracts]]
name = "primitives cannot import components or workflows"
type = "forbidden"
source_modules = ["ai_workflows.primitives"]
forbidden_modules = ["ai_workflows.components", "ai_workflows.workflows"]

[[tool.importlinter.contracts]]
name = "components cannot import workflows"
type = "forbidden"
source_modules = ["ai_workflows.components"]
forbidden_modules = ["ai_workflows.workflows"]

[[tool.importlinter.contracts]]
name = "components cannot peek at each other's private state"
type = "forbidden"
source_modules = ["ai_workflows.components.*"]
forbidden_modules = ["ai_workflows.components.*._*"]
```

### Directory Structure

```text
ai-workflows/
├── pyproject.toml
├── tiers.yaml
├── pricing.yaml
├── .python-version
├── .gitignore
├── migrations/                   # yoyo-migrations SQL scripts
│   └── 001_initial.sql
├── ai_workflows/
│   ├── __init__.py
│   ├── cli.py
│   ├── primitives/
│   │   ├── __init__.py
│   │   ├── llm/
│   │   │   ├── __init__.py
│   │   │   ├── types.py          # ContentBlock, Message, Response, ClientCapabilities
│   │   │   ├── model_factory.py  # tier → pydantic-ai Model
│   │   │   └── caching.py        # multi-breakpoint Anthropic cache
│   │   ├── tools/
│   │   │   ├── __init__.py
│   │   │   ├── registry.py
│   │   │   ├── forensic_logger.py  # renamed from sanitizer; LOGGING only
│   │   │   ├── fs.py
│   │   │   ├── shell.py
│   │   │   ├── http.py
│   │   │   └── git.py
│   │   ├── tiers.py
│   │   ├── workflow_hash.py      # content hash of workflow directory
│   │   ├── storage.py
│   │   ├── cost.py
│   │   ├── retry.py
│   │   └── logging.py
│   ├── components/
│   │   └── __init__.py
│   └── workflows/
│       └── __init__.py
├── tests/
│   ├── primitives/
│   ├── components/
│   └── workflows/
└── docs/
    ├── architecture.md
    ├── writing-a-component.md
    └── writing-a-workflow.md
```

### `.github/workflows/ci.yml`

Minimal CI: `uv run pytest`, `uv run lint-imports`, `uv run ruff check`. Add a second job that scans `tiers.yaml` and `pricing.yaml` for API key patterns and fails if found.

### `migrations/001_initial.sql`

Initial schema stub (details in task_08). yoyo-migrations tracks applied migrations in `_yoyo_migration` table automatically.

## Acceptance Criteria

- [ ] `uv sync` installs `pydantic-ai`, `logfire`, `yoyo-migrations` without conflicts
- [ ] `uv run pytest` passes (empty suite)
- [ ] `uv run lint-imports` passes with all three contracts above
- [ ] `import ai_workflows.primitives` works
- [ ] `aiw --help` prints the typer help text
- [ ] CI secret-scan fails when a test `sk-ant-xxx` is added to `tiers.yaml`

## Dependencies

None — first task.
