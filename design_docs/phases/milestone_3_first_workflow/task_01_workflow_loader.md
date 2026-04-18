# Task 01 — Workflow Loader (Typed)

**Issues:** W-01, W-02, W-03, W-04, R-08, CRIT-01, CRIT-02

## What to Build

Reads `workflow.yaml`, validates against component config schemas, **type-checks step-to-step data flow at load time** (Haystack pattern — CRIT-01), stores workflow directory content hash in SQLite (CRIT-02). Every future workflow depends on this.

## Deliverables

### `ai_workflows/loader.py`

```python
class WorkflowDefinition(BaseModel):
    name: str
    description: str
    inputs: dict[str, str]
    components: dict[str, dict]              # step name → raw config dict
    flow: list[str]                          # step order
    max_run_cost_usd: float | None = 10.00   # default budget cap
    allowed_executables: list[str] = []
    strict_review: bool = False

async def load_workflow(
    workflow_dir: str,
    profile: str | None = None,
) -> tuple[WorkflowDefinition, str]:
    """
    Returns (definition, workflow_dir_hash).

    1. Parse workflow.yaml, validate against WorkflowDefinition schema
    2. For each component in `components`: instantiate the correct ComponentConfig subclass
    3. Resolve all step output/input schemas by importing their Pydantic models
    4. Type-check the `flow:` — each `input_from:` reference must match a producer's output schema
    5. Validate all system prompt templates — no {{var}} substitutions
    6. Import custom_tools.py if it exists
    7. Compute workflow directory hash via compute_workflow_hash()
    8. Return definition + hash
    """
```

### Type Checking (CRIT-01)

Each component declares `input_schema` and `output_schema` (Pydantic classes). The loader reads these from `schemas/*.py` and verifies:

```python
def validate_flow_typing(flow: list[str], components: dict) -> None:
    """For each step with input_from: <prev_step>, verify:
       prev_step.output_schema is compatible with this step's input_schema.
       Raise TypeMismatchError at load time on mismatch."""
```

Compatible means: Pydantic's `model_validate()` succeeds (same fields or strictly-fewer-fields on input). On incompatibility, raise with both schemas' field lists in the error message.

### Workflow Snapshotting (CRIT-02)

At run start, the full workflow directory is snapshotted to `~/.ai-workflows/runs/<run_id>/workflow/`:

```python
async def snapshot_workflow(run_id: str, workflow_dir: str) -> str:
    """Copy entire workflow dir to runs/<run_id>/workflow/.
       Compute and return content hash."""
    hash = compute_workflow_hash(workflow_dir)
    shutil.copytree(workflow_dir, f"~/.ai-workflows/runs/{run_id}/workflow/")
    return hash
```

On `aiw resume`:

1. Fetch stored `workflow_dir_hash` from `runs` row
2. Re-hash the snapshotted dir (proves it wasn't tampered with)
3. Use the snapshotted dir, not the current on-disk dir, to reconstruct the workflow
4. Optionally re-hash the current on-disk dir and warn if different (user may have iterated on prompts between run and resume)

### Custom Tools Discovery

`custom_tools.py` in the workflow dir is imported at load time and any tools it registers via `register_*_tools(registry)` are added to the per-run `ToolRegistry`. The registry is scoped to this run — no global state.

### `flow:` + `after:`/`before:` DAG Merge

`flow:` is the top-level sequential list. If a component has `after:` or `before:` keys, those add implicit edges. At load time we merge into a validated linear order for Pipeline use (M3) or a DAG for Orchestrator use (M4+). In M3: reject any non-linear flow and require a linear merge.

## Acceptance Criteria

- [ ] Valid `workflow.yaml` loads without error
- [ ] Missing required field raises `WorkflowValidationError` naming the field
- [ ] Unknown component `type:` raises `UnknownComponentError`
- [ ] Type mismatch on `input_from:` reference raises at load time
- [ ] System prompt with `{{var}}` raises at load time
- [ ] `custom_tools.py` is imported and its tools available in the run's registry
- [ ] `workflow_dir_hash` is computed and matches `compute_workflow_hash()` directly
- [ ] Snapshot dir created at `~/.ai-workflows/runs/<run_id>/workflow/`

## Dependencies

- All of M2
