# Task 01 — BaseComponent ABC

**Issues:** C-01, C-02, C-03, C-04, C-05

## What to Build

The abstract base class every component inherits from. Provides shared: structured logging bound with component context, cost tagging hook, run_id threading, and the standard `run()` interface.

## Deliverables

### `components/__init__.py` / `components/base.py`

```python
from abc import ABC, abstractmethod
from pydantic import BaseModel

class ComponentConfig(BaseModel):
    """Base config all component configs extend."""
    pass

class ComponentResult(BaseModel):
    """Base result all component results extend."""
    status: str  # completed, failed, incomplete
    component: str
    run_id: str

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

    def _log(self) -> BoundLogger:
        """Returns structlog logger bound with run_id, workflow_id, component."""
        ...
```

**Prompt template rendering** (lives here, used by all components):
```python
def render_prompt(template_path: str, variables: dict[str, str]) -> str:
    """Load prompt file, substitute {{variable}} patterns."""
    ...
```

## Acceptance Criteria

- [ ] `BaseComponent` is abstract — cannot be instantiated directly
- [ ] `render_prompt()` substitutes all `{{var}}` patterns correctly
- [ ] `render_prompt()` raises `MissingPromptVariable` if a `{{var}}` in the template has no value in `variables`
- [ ] `render_prompt()` raises `UnknownVariable` if `variables` contains a key not in the template (prevents silent typos)
- [ ] Logger returned by `_log()` has `run_id`, `workflow_id`, `component` bound

## Dependencies

- All of Milestone 1
