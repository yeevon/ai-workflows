# Task 01 — BaseComponent ABC

**Issues:** C-01, C-02, C-03, C-04, C-05

## What to Build

The ABC every component inherits from. Responsible for:

- Logging bound with component context
- Prompt template rendering with `{{var}}` substitution + system-prompt variable validation
- Wiring to `CostTracker`, `StorageBackend`, `ToolRegistry`
- Generating `WorkflowDeps` for every LLM call through pydantic-ai

## Deliverables

### `components/base.py`

```python
from abc import ABC, abstractmethod
from pydantic import BaseModel
from ai_workflows.primitives.llm.types import WorkflowDeps

class ComponentConfig(BaseModel):
    """Base config all component configs extend."""
    pass

class ComponentResult(BaseModel):
    status: Literal["completed", "failed", "incomplete"]
    component: str
    run_id: str
    output: dict | None = None
    failure_reason: str | None = None

class BaseComponent(ABC):
    def __init__(
        self,
        config: ComponentConfig,
        storage: StorageBackend,
        cost_tracker: CostTracker,
        tool_registry: ToolRegistry,
    ): ...

    @abstractmethod
    async def run(
        self,
        input: BaseModel,
        *,
        run_id: str,
        workflow_id: str,
        task_id: str,
    ) -> ComponentResult: ...

    def _make_deps(self, run_id: str, workflow_id: str, task_id: str, tier: str) -> WorkflowDeps:
        """Construct WorkflowDeps for passing to pydantic-ai Agent.run()."""

    def _log(self) -> BoundLogger:
        """Structlog logger bound with run_id, workflow_id, component."""
```

### Prompt Template Rendering

```python
def render_prompt(template_path: str, variables: dict[str, str]) -> str:
    """Load prompt, substitute {{var}} patterns. Raises on missing or extra vars."""

def validate_system_prompt_template(path: str) -> None:
    """
    Raise if the system prompt template contains {{var}} substitutions.

    Per CRIT-07: variables in system prompts break prompt caching because
    the hash differs every call. System prompts must be static.
    """
```

Called at workflow load time for every Worker/Planner config. Workflow load fails with a clear error if a system prompt has variables.

## Acceptance Criteria

- [ ] `BaseComponent` is abstract (cannot instantiate)
- [ ] `render_prompt()` substitutes all `{{var}}` patterns
- [ ] `render_prompt()` raises `MissingPromptVariable` on template var not in dict
- [ ] `render_prompt()` raises `UnknownVariable` on dict key not in template
- [ ] `validate_system_prompt_template()` raises on `{{var}}` in system prompt
- [ ] `_make_deps()` returns a `WorkflowDeps` usable as `deps` in `Agent.run()`

## Dependencies

- All of Milestone 1
