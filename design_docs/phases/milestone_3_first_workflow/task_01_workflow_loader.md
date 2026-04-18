# Task 01 — Workflow Loader

**Issues:** W-01, W-02, W-03, W-04, R-08

## What to Build

The engine that reads a `workflow.yaml`, validates it against component config schemas, instantiates components, and wires data flow. Every future workflow depends on this.

## Deliverables

### `ai_workflows/loader.py`

**`WorkflowDefinition` (Pydantic model):**
```python
class WorkflowDefinition(BaseModel):
    name: str
    description: str
    inputs: dict[str, str]            # name -> type hint string
    components: dict[str, dict]       # component name -> raw config dict
    flow: list[str]                   # top-level execution order
    allowed_executables: list[str] = []
    strict_review: bool = False
```

**`load_workflow(workflow_dir: str, profile: str | None) -> WorkflowDefinition`:**
1. Reads `workflow.yaml` from `workflow_dir`
2. Validates against `WorkflowDefinition`
3. For each component entry: instantiates the correct `ComponentConfig` subclass based on `type:` field
4. Imports `custom_tools.py` from `workflow_dir` if it exists (auto-discovery)
5. Returns the validated definition

**`build_run_context(definition: WorkflowDefinition, run_id: str, inputs: dict) -> RunContext`:**
- Creates the `RunContext` with `run_id`, `workflow_id`, `allowed_executables`, `strict_review`
- Snapshots `workflow.yaml` into `~/.ai-workflows/runs/<run_id>/workflow.yaml`
- Creates `runs/<run_id>/` directory structure

**`flow:` + `after:`/`before:` DAG merge:**
- `flow:` provides the top-level ordering constraint
- `after:`/`before:` on individual steps add fine-grained edges
- Merge into a single DAG at load time
- Validate: no circular dependencies, no references to unknown component names

## Acceptance Criteria

- [ ] Valid `workflow.yaml` loads without error
- [ ] Missing required field raises `WorkflowValidationError` with the field name
- [ ] Unknown component `type:` raises `UnknownComponentError`
- [ ] Circular dependency in flow raises `CyclicDependencyError`
- [ ] `custom_tools.py` is imported and its tools registered into the workflow's `ToolRegistry`
- [ ] `workflow.yaml` is snapshotted into run dir before any component runs

## Dependencies

- All of Milestone 2
