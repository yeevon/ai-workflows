# evals/ — captured cases + golden suites

This tree holds two kinds of artefacts: hand-authored seed fixtures used as
golden cases, and capture-callback-emitted fixtures from real workflow runs
(opt-in via `AIW_CAPTURE_EVALS=<dataset>`). The replay engine lives in
`ai_workflows.evals` (see `evals/runner.py`).

## Layout reference

Two shapes coexist in `evals/`:

- **Hand-written / seed fixtures** (M7 T05) — `evals/<workflow>/<node>/<case>.json`.
  Authored directly via `save_case()` or committed by hand. The `EvalRunner`
  finds them via `load_suite(workflow_id)`. Examples on disk:
  `evals/planner/explorer/happy-path-01.json`,
  `evals/slice_refactor/slice_worker/happy-path-01.json`.
- **Capture-callback-emitted fixtures** (M7 T02) — `evals/<dataset>/<workflow>/<node>/<case>.json`.
  Written when a workflow run sets `AIW_CAPTURE_EVALS=<dataset>` (or a future
  surface threads `--capture-evals <dataset>`). The `<dataset>` segment
  disambiguates capture batches.

The cascade fixture convention below is a sub-shape of the second layout.

## Cascade fixture convention (M12 T06)

When the audit cascade is enabled for a workflow (`AIW_AUDIT_CASCADE_PLANNER=1`,
`AIW_AUDIT_CASCADE_SLICE_REFACTOR=1`, or the global `AIW_AUDIT_CASCADE=1` —
see ADR-0009 / KDR-014), each cascade pair writes two independent fixtures
when `AIW_CAPTURE_EVALS=<dataset>` is also set:

```
evals/<dataset>/<workflow>/<cascade_name>_primary/<case_id>.json    # role="author"
evals/<dataset>/<workflow>/<cascade_name>_auditor/<case_id>.json    # role="auditor"
```

`<cascade_name>` is the `name=` kwarg passed to `audit_cascade_node()` in the
workflow's compile function. For in-tree workflows:

| Workflow | `<cascade_name>` | Primary path | Auditor path |
|---|---|---|---|
| `planner` | `planner_explorer_audit` (`planner.py:570`) | `evals/<dataset>/planner/planner_explorer_audit_primary/` | `evals/<dataset>/planner/planner_explorer_audit_auditor/` |
| `slice_refactor` | `slice_worker_audit` (`slice_refactor.py:1053`) | `evals/<dataset>/slice_refactor/slice_worker_audit_primary/` | `evals/<dataset>/slice_refactor/slice_worker_audit_auditor/` |

Each captured fixture is independently loadable via
`ai_workflows.evals.storage.load_case(path)` (or
`EvalCase.model_validate_json(path.read_text())`); operators can spot-check
or hand-edit one side of a cascade pair without touching the other.

The cascade verdict node (`<cascade_name>_verdict`) is a pure parse step
(no LLM call); no fixture is written for it.

**Full-suite replay through `EvalRunner` is a follow-up.** Cascade nodes do
not match the engine's `<node>_validator` pair-lookup convention (KDR-004) —
`runner.py:_resolve_node_scope` looks for `<cascade_name>_primary_validator` /
`<cascade_name>_auditor_validator`, but the cascade graph only registers
`<cascade_name>_validator` (single underscore segment). T06 therefore scopes
replay verification to direct `load_case` loading. A future task may extend
`EvalRunner` to recognise cascade-internal node-name conventions.

Per-fixture telemetry: each captured `EvalCase` is paired with a
`TokenUsage` ledger entry stamped via `usage.role` at `tiered_node` factory
time (closure-bound — see `audit_cascade.py:313, 349`). The role tag is
NOT read from graph state, so retried/re-fired cascade attempts inherit the
correct role on every record. `state['cascade_role']` exists as a debug
surface for in-flight inspection of which sub-node last ran, but
`TokenUsage.role` is the persistent telemetry field. Aggregate via
`CostTracker.by_role(run_id)`.
