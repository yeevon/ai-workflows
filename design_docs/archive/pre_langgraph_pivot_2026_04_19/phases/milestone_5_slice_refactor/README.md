# Milestone 5 — Second Workflow: slice_refactor

## Goal

Port Pipeline 2 to use the orchestration components built in Milestone 4. This is the second forcing function — two workflows sharing the same components reveals shared patterns and tightens APIs.

**Exit criteria:** `aiw run slice_refactor --repos.A /path/a --repos.B /path/b --slice OrderService` plans and executes a cross-repo refactor with a HumanGate review before execution.

## Scope

- `slice_refactor` workflow: YAML, prompts, schemas, custom tools
- Any component API fixes revealed by this workflow
- Comparison against `test_coverage_gap_fill` to identify true shared patterns

## Key Features of this Workflow

- Multi-repo inputs (A, B, C with cross-repo dependency awareness)
- Two-phase Planner: Qwen explores all repos, Opus plans the cross-repo refactor DAG
- HumanGate between planning and execution (`strict_review: false` for personal use, can enable for work)
- Sonnet Workers for refactor tasks (multi-turn, full file content)
- Structural Validator: build command must pass after each file change
- Parallel branches within repos, sequential between dependent repos

## What to Watch For

This is where cross-workflow patterns emerge. After building this workflow, look at what's duplicated between `test_coverage_gap_fill` and `slice_refactor`:
- If exploration prompt is nearly identical → extract to a shared `prompts/explore_module.txt` in stdlib
- If validation logic is duplicated → consider a shared validator config
- If schema shapes overlap → extract to a shared `schemas/` location

The extraction rule: only if a **third** workflow would need it. Don't extract based on two.

## Workflow Structure (sketch)

```
ai_workflows/workflows/slice_refactor/
├── workflow.yaml
├── prompts/
│   ├── explore_repo.txt
│   ├── plan_refactor.txt
│   ├── refactor_file.txt
│   └── validate_refactor.txt
├── schemas/
│   ├── repo_summary.py
│   ├── refactor_plan.py
│   └── refactor_result.py
├── custom_tools.py              # run_gradle_build, run_maven_build, etc. — registered on demand
└── run.py
```

## Tasks (define at build time)

Tasks for this milestone are defined when you start building it — after Milestone 4 is complete and you know what the component APIs actually look like. Do not speculate now.
