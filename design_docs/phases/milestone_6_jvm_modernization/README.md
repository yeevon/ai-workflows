# Milestone 6 — jvm_modernization Workflow

## Goal

Compose `test_coverage_gap_fill` and `slice_refactor` into the full JVM modernization pipeline. This is the project's target use case — reaching this milestone proves the architecture works.

**Exit criteria:** `aiw run jvm_modernization --slice OrderService --repos.A /a --repos.B /b --repos.C /c` runs the full pipeline: exploration → characterization tests → plan → human review → refactor → validate.

## Scope

- `jvm_modernization` workflow composing the two prior workflows
- Cross-workflow data sharing pattern (W-05: sub-workflow vs. component config import — decide here)
- JVM-specific custom tools: `run_gradle_build`, `run_maven_build`, `openrewrite_apply`
- Router component (if routing by `change_type` is needed — add only if this workflow demands it)

## Key Question to Resolve Here (W-05)

Does `jvm_modernization` call `test_coverage_gap_fill` and `slice_refactor` as sub-workflows, or does it import their component configs directly?

**Sub-workflow:** Each workflow runs as a separate `aiw run` invocation. Clean separation, separate cost tracking, but requires inter-process coordination.

**Component config import:** `jvm_modernization/workflow.yaml` imports component configs from the other two workflow directories. Single run, unified cost tracking, but tighter coupling.

Decide at build time based on what the actual data flow looks like.

## What to Watch For

- Does the HumanGate plan review become unwieldy at jvm_modernization scale? (50-task DAG across 3 repos)
- Do JVM-specific tool failures surface clearly enough to act on?
- Is the escalation path (local_coder → haiku → sonnet → opus) actually used — and does it save cost?

## Tasks (define at build time)

Define tasks when Milestones 4 and 5 are complete. The workflow structure will be clear by then.
