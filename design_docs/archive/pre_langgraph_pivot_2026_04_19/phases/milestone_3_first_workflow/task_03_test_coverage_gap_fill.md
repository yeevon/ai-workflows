# Task 03 — Workflow: test_coverage_gap_fill (Cloud-Default)

## Goal

Generate characterization tests for a codebase slice. **Cloud-default** — Haiku for both exploration and generation in M1-M3. Ollama swap-in lands in M4 alongside Ollama's operational wrapping.

## Directory Structure

```text
ai_workflows/workflows/test_coverage_gap_fill/
├── workflow.yaml
├── prompts/
│   ├── explore_module_system.txt     # STATIC — no {{var}}
│   ├── explore_module_user.txt       # per-call vars OK
│   ├── generate_test_system.txt
│   ├── generate_test_user.txt
│   └── validate_test_system.txt      # STATIC criteria
├── schemas/
│   ├── inputs.py                     # TestCoverageInput
│   ├── exploration.py                # ModuleSummary
│   └── test_file.py                  # GeneratedTestFile
├── run.py                            # thin CLI entry point
└── evals/                            # added in Task 04
    ├── cases.py
    └── dataset.json
```

## `workflow.yaml`

```yaml
name: test_coverage_gap_fill
description: Generate characterization tests for a codebase slice

max_run_cost_usd: 5.00
allowed_executables: []
strict_review: false

inputs:
  repo: path
  slice: str

components:
  explore:
    type: worker
    tier: haiku                      # cloud-default in M1-M3 (was local_coder)
    system_prompt_file: prompts/explore_module_system.txt
    user_prompt_file: prompts/explore_module_user.txt
    input_schema: schemas/inputs.py:TestCoverageInput
    output_schema: schemas/exploration.py:ModuleSummary
    tools: [read_file, list_dir, grep]
    max_output_chars: 15000

  generate_tests:
    type: fanout
    input_from: explore              # ModuleSummary.functions as items
    worker_config:
      tier: haiku
      system_prompt_file: prompts/generate_test_system.txt
      user_prompt_file: prompts/generate_test_user.txt
      input_schema: schemas/exploration.py:FunctionSignature
      output_schema: schemas/test_file.py:GeneratedTestFile
      tools: [read_file]
      max_output_chars: 10000
    validator_config:
      steps:
        - type: semantic
          tier: haiku
          criteria_prompt: prompts/validate_test_system.txt
    concurrency: 5

flow:
  - explore
  - generate_tests
```

## Key Design Details

### Static System Prompts

Every `*_system.txt` file is static — no `{{var}}` substitutions. The loader's `validate_system_prompt_template()` check enforces this. Prompt caching requires it.

### Per-Call User Prompts

`explore_module_user.txt` can use `{{repo}}`, `{{slice}}`. The Worker renders with `input` fields at runtime.

### Schema Wiring (CRIT-01)

`explore` produces `ModuleSummary` which contains `functions: list[FunctionSignature]`. The Fanout component's `input_from: explore` takes `ModuleSummary.functions` as its item list. The loader type-checks this at load time — if `FunctionSignature` in the Fanout's `input_schema` doesn't match `functions`'s item type, it raises before any LLM call.

## Acceptance Criteria

- [ ] Workflow runs end-to-end on a small Python module
- [ ] Haiku exploration produces a `ModuleSummary` with function signatures
- [ ] Haiku fanout generates a runnable pytest file per function
- [ ] Semantic validator correctly rejects a test file with no asserts
- [ ] `aiw inspect` shows correct breakdown (all haiku, no local_coder)
- [ ] `aiw resume` after interruption skips completed test generations
- [ ] Total cost under $1 on a 10-function module

## Dependencies

- Task 01 (loader)
- Task 02 (aiw run)
