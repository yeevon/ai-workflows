# Task 03 — Workflow: test_coverage_gap_fill

## Goal

Generate characterization tests for a target slice of a codebase. Uses Qwen for exploration reads, Haiku/Qwen for test generation, Sonnet for complex cases requiring full file context.

## Directory Structure

```
ai_workflows/workflows/test_coverage_gap_fill/
├── workflow.yaml
├── prompts/
│   ├── explore_module.txt        # Qwen: read module, extract signatures
│   ├── generate_test.txt         # Haiku: generate test for one function
│   └── validate_test.txt         # Semantic validator criteria
├── schemas/
│   ├── module_summary.py         # Pydantic: Qwen exploration output
│   └── test_file.py              # Pydantic: generated test output
└── run.py                        # thin: parse args, call aiw runner
```

## `workflow.yaml` Sketch

```yaml
name: test_coverage_gap_fill
description: Generate characterization tests for a codebase slice

inputs:
  repo: path
  slice: str

allowed_executables: []         # no shell commands needed for this workflow
strict_review: false

components:
  explore:
    type: worker
    tier: local_coder            # Qwen for exploration
    prompt: prompts/explore_module.txt
    output_schema: schemas/module_summary.py:ModuleSummary
    tools: [read_file, list_dir, grep]
    max_output_chars: 15000

  generate_tests:
    type: fanout
    worker_config:
      tier: haiku
      prompt: prompts/generate_test.txt
      output_schema: schemas/test_file.py:TestFile
      tools: [read_file]
      max_output_chars: 10000
    validator_config:
      steps:
        - type: semantic
          tier: haiku
          criteria: prompts/validate_test.txt
    concurrency: 5

flow:
  - explore
  - generate_tests
```

## Prompts (outline, not final)

**`explore_module.txt`:** Instructs Qwen to read the target slice, list all public functions/classes with signatures, inputs, outputs, and any notable dependencies. Output must match `ModuleSummary` schema.

**`generate_test.txt`:** Instructs Haiku to write a pytest characterization test for one function given its signature and usage context. Output must be a valid Python test file.

**`validate_test.txt`:** Criteria for semantic validator: "Does this test actually test the described function? Does it have at least one assert? Is it syntactically valid Python?"

## Acceptance Criteria

- [ ] Workflow runs end-to-end on a small Python module (< 10 functions)
- [ ] Qwen exploration produces a `ModuleSummary` with all public function signatures
- [ ] Haiku generates a runnable pytest file for at least one function
- [ ] Semantic validator correctly rejects a test file with no asserts
- [ ] `aiw inspect` shows correct cost breakdown (local_coder=$0.00, haiku=$X)
- [ ] Re-running with `aiw resume` after interruption skips completed test generations

## What to Watch For (Forcing Function)

This workflow will break things in the components layer. Document each break and fix it:
- Pydantic schemas too strict for LLM output → add retry or loosen
- Prompt variables that don't exist in the template → improve error message
- Tool output too large for Haiku's context → tune `max_output_chars`
- Fanout failure reason not actionable → improve Validator output

## Dependencies

- Tasks 01 and 02 (loader + aiw run)
