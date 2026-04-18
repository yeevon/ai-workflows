# Task 04 — Evaluation Harness (NEW)

**Issues:** IMP-01, IMP-07

## What to Build

Evaluation harness using `pydantic-evals`. The single most important addition over the original design — without it, every prompt change is a blind experiment.

## Why This Matters

After running `test_coverage_gap_fill` on 3 repos, you'll make prompt changes. Without evals, you cannot answer: "did my new exploration prompt regress quality on the repos where it used to work?"

`pydantic-evals` gives you:

- `Case` — a named input + expected behavior
- `Dataset` — a collection of cases
- `LLMJudge` — semantic evaluators (reuses your semantic Validator shape)
- Custom evaluators — deterministic checks (did this test actually run?)
- Span-based evaluators — assertions over OTel spans emitted during the run

## Deliverables

### `pydantic-evals` Integration

Add `evals/` directory inside each workflow directory:

```text
ai_workflows/workflows/test_coverage_gap_fill/
├── ... (workflow files)
└── evals/
    ├── cases.py              # Python definition of cases + dataset
    └── fixtures/             # small test codebases used as inputs
        ├── tiny_auth/
        ├── simple_calculator/
        └── state_machine/
```

### `evals/cases.py` Shape

```python
from pydantic_evals import Case, Dataset
from pydantic_evals.evaluators import LLMJudge, Equals, Contains

class TestCoverageCase(BaseModel):
    repo_path: str
    slice_name: str
    expected_function_count_min: int

dataset = Dataset[TestCoverageCase, GeneratedTests, dict](
    cases=[
        Case(
            name="tiny_auth_basic",
            inputs=TestCoverageCase(repo_path="evals/fixtures/tiny_auth", slice_name="AuthModule", expected_function_count_min=3),
            expected_output=...,                     # structural expectations
            evaluators=[
                LLMJudge(
                    rubric="The generated tests must have at least one assert per test function.",
                    model="anthropic:claude-haiku-4-5",
                ),
                Contains(field="test_code", substring="assert"),
            ],
        ),
        # ... 9 more cases covering edge cases
    ],
)
```

### `aiw eval <workflow>` Command

```text
aiw eval test_coverage_gap_fill

Running 10 cases against test_coverage_gap_fill...
  tiny_auth_basic          PASS  (haiku $0.02, 14s)
  simple_calculator        PASS  (haiku $0.02, 12s)
  state_machine_complex    FAIL  (haiku $0.03, 18s)
    LLMJudge: "Tests do not cover the transition from STARTED to COMPLETED"
  ...

Pass rate: 9/10 (90%)
Mean cost per case: $0.02
Total cost: $0.21

Comparison with last run (2026-04-15):
  +1 new pass (state_machine_simple was failing)
  -0 regressions
  +$0.01 mean cost change
```

Eval results are written to SQLite in a new `evals` table:

```sql
CREATE TABLE evals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workflow_id TEXT NOT NULL,
    case_name TEXT NOT NULL,
    run_id TEXT,                       -- nullable if eval was standalone
    passed INTEGER NOT NULL,
    cost_usd REAL,
    duration_ms INTEGER,
    failure_reason TEXT,
    evaluated_at TEXT NOT NULL
);
```

### `test_coverage_gap_fill` Pass/Fail Metric (IMP-07)

Before writing the workflow prompts, define the metric:

> A generated test file "passes" for a given function when:
>
> 1. It is syntactically valid Python (parses with `ast.parse`)
> 2. It contains at least one `assert` statement per `def test_*` function
> 3. An LLMJudge rates it "covers the target function's primary behavior"
>
> The workflow "passes" on a codebase when ≥ 80% of generated test files pass individually.

This metric is what the eval harness checks. Without this metric defined, you can't iterate on the prompt.

### Migration: Add Evals Table

New migration `migrations/002_evals.sql` to add the `evals` table. yoyo-migrations handles this automatically.

## Acceptance Criteria

- [ ] `evals/cases.py` with 10 cases for `test_coverage_gap_fill`
- [ ] `aiw eval test_coverage_gap_fill` runs all cases and reports pass/fail
- [ ] Eval results written to `evals` table
- [ ] Second run of `aiw eval` compares against previous run (regression detection)
- [ ] Each case's cost is tracked in `llm_calls` and rolled up to `evals.cost_usd`
- [ ] Pass/fail metric for test_coverage_gap_fill is documented in workflow README

## Dependencies

- Task 03 (workflow)
- M1 Task 08 (storage — migration system in place)
