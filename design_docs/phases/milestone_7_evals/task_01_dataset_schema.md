# Task 01 — Eval Dataset Schema + Storage Layout

**Status:** 📝 Planned.
**Grounding:** [milestone README §Exit criteria](README.md) · [architecture.md §7](../../architecture.md) · [KDR-004](../../architecture.md) · [KDR-010 / ADR-0002](../../adr/0002_bare_typed_response_format_schemas.md).

## What to Build

Create the `ai_workflows.evals` package and land the two pydantic schemas the rest of M7 composes over: `EvalCase` (a single input→expected-output fixture for a single LLM node) and `EvalSuite` (a grouping of cases under one workflow + node). Define the on-disk JSON layout that T02's capture helper writes and T03's replay runner reads.

No capture logic, no replay logic, no CLI. This task is the primitive substrate — the shape everything else relies on.

## Deliverables

### [ai_workflows/evals/__init__.py](../../../ai_workflows/evals/__init__.py)

New package. Module docstring cites this task and names the downstream consumers (T02 capture, T03 replay, T04 CLI). Exports `EvalCase`, `EvalSuite`, `load_suite`, `save_case`.

### [ai_workflows/evals/schemas.py](../../../ai_workflows/evals/schemas.py)

Two pydantic models:

```python
class EvalCase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: str  # e.g. "planner-happy-path-01"
    workflow_id: str  # e.g. "planner"
    node_name: str  # e.g. "explorer" / "planner" / "slice_worker"
    inputs: dict[str, Any]  # the TieredNode input state (serialized)
    expected_output: Any  # raw output; structure depends on node's output_schema
    output_schema_fqn: str | None  # "ai_workflows.workflows.planner.ExplorerReport" etc.
    tolerance: EvalTolerance = EvalTolerance()
    captured_at: datetime
    captured_from_run_id: str | None  # link back to runs.run_id of the source run
    metadata: dict[str, str] = Field(default_factory=dict)


class EvalTolerance(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    mode: Literal["strict_json", "substring", "regex"] = "strict_json"
    # "strict_json" — exact round-trip equality after parsing through output_schema
    # "substring"   — each configured field must contain expected as a substring (case-insensitive)
    # "regex"       — each configured field must match expected as a regex
    field_overrides: dict[str, Literal["strict_json", "substring", "regex"]] = Field(
        default_factory=dict
    )


class EvalSuite(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    workflow_id: str
    cases: tuple[EvalCase, ...]
```

All **bare-typed per KDR-010** — no `Field(min_length/max_length/...)`.

### [ai_workflows/evals/storage.py](../../../ai_workflows/evals/storage.py)

Filesystem layout + serialization helpers:

```python
EVALS_ROOT = Path("evals")  # repo-root sibling; override via AIW_EVALS_ROOT env var

def fixture_path(root: Path, workflow_id: str, node_name: str, case_id: str) -> Path:
    return root / workflow_id / node_name / f"{case_id}.json"

def save_case(case: EvalCase, root: Path = EVALS_ROOT) -> Path:
    """Write one case to its canonical path. Refuses to overwrite unless overwrite=True."""

def load_suite(workflow_id: str, root: Path = EVALS_ROOT) -> EvalSuite:
    """Load every case under <root>/<workflow_id>/**/*.json into one suite."""

def load_case(path: Path) -> EvalCase:
    """Load a single case JSON."""
```

JSON uses `EvalCase.model_dump_json(indent=2)` so fixtures diff cleanly in PRs.

### Layer contract update

Add a fourth import-linter contract under [pyproject.toml](../../../pyproject.toml):

```toml
[[tool.importlinter.contracts]]
name = "evals depends on graph + primitives only"
type = "forbidden"
source_modules = ["ai_workflows.evals"]
forbidden_modules = ["ai_workflows.workflows", "ai_workflows.cli", "ai_workflows.mcp"]
```

`evals/` sits **below** workflows + surfaces in the layer order so the CLI in T04 can safely import it. Confirm the full contract set still kept by `uv run lint-imports`: existing 3 + new 1 = 4 total.

### Tests

[tests/evals/test_schemas.py](../../../tests/evals/test_schemas.py) (new directory):

- `test_eval_case_rejects_extra_fields` — `extra="forbid"` honoured.
- `test_eval_case_serialization_round_trip` — `model_dump_json` → `model_validate_json` preserves every field including `EvalTolerance.field_overrides`.
- `test_eval_suite_empty_cases_allowed` — empty tuple is valid.
- `test_eval_suite_rejects_mismatched_workflow_id` — a case with `workflow_id="planner"` cannot land in a suite keyed `slice_refactor`.

[tests/evals/test_storage.py](../../../tests/evals/test_storage.py):

- `test_save_case_writes_canonical_path` — under `tmp_path`, `save_case(case, tmp_path)` writes to `<root>/<workflow>/<node>/<case_id>.json`.
- `test_save_case_refuses_overwrite_by_default` — second `save_case` with same path raises; `overwrite=True` allows it.
- `test_load_suite_aggregates_nested_cases` — three cases across two node directories load into one `EvalSuite`.
- `test_load_suite_ignores_non_json_files` — stray `README.md` under the fixture dir does not break the load.

### Scaffolding

- [ai_workflows/evals/py.typed](../../../ai_workflows/evals/py.typed) — marker file.
- [tests/evals/__init__.py](../../../tests/evals/__init__.py) — empty.
- [evals/.gitkeep](../../../evals/.gitkeep) — make the fixture directory root exist.

## Acceptance Criteria

- [ ] `ai_workflows.evals` imports clean; `from ai_workflows.evals import EvalCase, EvalSuite, save_case, load_suite` works.
- [ ] `EvalCase` + `EvalSuite` + `EvalTolerance` are pydantic `v2` models with `extra="forbid"` and `frozen=True`, bare-typed per KDR-010.
- [ ] `save_case` / `load_suite` round-trip is lossless for every field.
- [ ] Import-linter contract set: **4 kept, 0 broken** (`uv run lint-imports`).
- [ ] Every listed test passes under `uv run pytest tests/evals/`.
- [ ] `uv run ruff check` clean.
- [ ] No `ai_workflows.evals` import inside `ai_workflows/graph/` or `ai_workflows/workflows/` (verified by the new import-linter contract).

## Dependencies

- M6 close-out (layer-linter contract set is currently 3; this task extends it to 4).
- No prior-milestone carry-overs.

## Out of scope (explicit)

- Any capture logic. (T02.)
- Any replay logic. (T03.)
- Any CLI surface. (T04.)
- Seed fixtures for `planner` / `slice_refactor`. (T05 landing via capture path.)
