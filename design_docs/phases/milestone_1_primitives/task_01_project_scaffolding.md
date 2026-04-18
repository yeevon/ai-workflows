# Task 01 — Project Scaffolding

**Issues:** R-01, R-02, R-03, R-04, R-05, R-06, R-07, X-06

## What to Build

Set up the repo so every subsequent task builds into a consistent, lint-enforced structure from the first commit.

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
  "anthropic>=0.40",
  "httpx>=0.27",
  "pydantic>=2.0",
  "pyyaml>=6.0",
  "structlog>=24.0",
  "typer>=0.12",
  "networkx>=3.0",
]

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
```

### Directory structure
```
ai-workflows/
├── pyproject.toml
├── tiers.yaml
├── pricing.yaml
├── .python-version          # 3.13
├── .gitignore
├── ai_workflows/
│   ├── __init__.py
│   ├── cli.py               # typer app, stubs for now
│   ├── primitives/
│   │   ├── __init__.py
│   │   ├── llm/
│   │   │   ├── __init__.py
│   │   │   ├── base.py
│   │   │   ├── anthropic.py
│   │   │   ├── ollama.py
│   │   │   └── openai_compat.py
│   │   ├── tools/
│   │   │   ├── __init__.py
│   │   │   ├── registry.py
│   │   │   ├── sanitizer.py
│   │   │   ├── fs.py
│   │   │   ├── shell.py
│   │   │   ├── http.py
│   │   │   └── git.py
│   │   ├── tiers.py
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

### `.gitignore`
```
.venv/
__pycache__/
*.pyc
.env
.env.*
~/.ai-workflows/
runs/
*.db
dist/
.coverage
```

### `.github/workflows/ci.yml`
Minimal CI: `uv run pytest`, `uv run lint-imports`, `uv run ruff check`.

## Acceptance Criteria

- [ ] `uv run pytest` passes (empty test suite is fine)
- [ ] `uv run lint-imports` passes with the two contracts above
- [ ] `import ai_workflows.primitives` works
- [ ] `import ai_workflows.components` works
- [ ] `aiw --help` prints the typer help text

## Dependencies

None — this is the first task.
