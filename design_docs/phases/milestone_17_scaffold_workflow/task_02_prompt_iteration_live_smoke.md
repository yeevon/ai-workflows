# Task 02 — Prompt template iteration + live-mode smoke + CS300 dogfood

**Status:** 📝 Planned.
**Grounding:** [milestone README](README.md) · [task_01_scaffold_workflow.md](task_01_scaffold_workflow.md) (T01 built the graph + validator; this task hardens the prompt) · [ai_workflows/workflows/scaffold_workflow_prompt.py](../../../ai_workflows/workflows/scaffold_workflow_prompt.py) (prompt template to iterate) · [ai_workflows/workflows/spec.py:329-404](../../../ai_workflows/workflows/spec.py#L329-L404) (`WorkflowSpec` + `register_workflow` — the API the generated code must call) · [ai_workflows/workflows/summarize.py](../../../ai_workflows/workflows/summarize.py) (canonical WorkflowSpec-based workflow — the shape the prompt teaches).

## What to Build

Harden the scaffold prompt template so a real Claude Opus run reliably emits a syntactically valid `WorkflowSpec` + `register_workflow(spec)` workflow file. The deliverables fall into three groups: (1) iterate the `SCAFFOLD_PROMPT_TEMPLATE` constant in `scaffold_workflow_prompt.py` against live runs until the validator passes on first try for the canonical CS300 goal, (2) land a live-mode smoke test file gated behind `AIW_E2E=1`, and (3) document an operator-run CS300 dogfood in CHANGELOG.

Also closes four carry-over items from T01 audits: LOW-2 (CLI alias test), LOW-3 (brace-escape regression test), ADV-1 (inner import hoisting), ADV-2 (docstring fix).

## Deliverables

### 1. Updated `ai_workflows/workflows/scaffold_workflow_prompt.py`

Iterate the `SCAFFOLD_PROMPT_TEMPLATE` constant until:
- The prompt includes: the `WorkflowSpec` field inventory (`name`, `input_schema`, `output_schema`, `steps`, `tiers`), the `register_workflow(spec)` calling convention, the four-layer contract (generated code lives in a user-owned module outside `ai_workflows/`), and at least one canonical example step referencing the tier name.
- A live run with `goal="generate exam questions from a textbook chapter"` against Claude Opus produces `spec_python` that passes `validate_scaffold_output()` on first attempt (no retry).
- The brace-escape fix from T01 cycle 2 is intact (no regression; see AC-4).

### 2. Live-mode smoke test `tests/release/test_scaffold_live_smoke.py`

Gated with `@pytest.mark.skipif(not os.getenv("AIW_E2E"), reason="AIW_E2E not set")`. Invokes the scaffold workflow via the `build_scaffold_workflow()` graph with the real `ClaudeCodeRoute(cli_model_flag="opus")` tier (no stub adapter). The test:
- Mirrors `tests/workflows/test_scaffold_workflow.py::test_scaffold_end_to_end_with_stub_adapter` (same checkpointer + config + initial-state pattern), but the stub adapter is replaced by the real `ClaudeCodeRoute(cli_model_flag="opus")` tier (no `_StubLiteLLMAdapter.script` injection). The initial state is built inline as `{"run_id": run_id, "input": ScaffoldWorkflowInput(goal="generate exam questions from a textbook chapter", target_path=tmp_path / "question_gen.py")}` and invoked via `await app.ainvoke(initial, config=cfg, durability="sync")`.
- Asserts the graph pauses at the `preview_gate` HumanGate (use `await app.aget_state(cfg)` and check that `state.next` contains the gate node name — equivalent to the existing test's `assert not target.exists()` pattern).
- Asserts the paused graph state's `scaffolded` field has non-empty `spec_python` content.
- Asserts `validate_scaffold_output(state.values["scaffolded"])` does not raise.
- Does NOT resume with approval — the test halts at the gate (no disk write).

Requires Claude Code CLI auth in the sandbox environment. Not included in the standard `uv run pytest` run (guarded by `AIW_E2E`).

### 3. CS300 dogfood (operator-run, documented in CHANGELOG)

The operator runs:
```bash
aiw run scaffold_workflow \
  --goal 'generate exam questions from a textbook chapter' \
  --target ~/tmp/question_gen_smoke.py \
  --run-id scaffold-cs300-smoke-1

aiw resume scaffold-cs300-smoke-1 --gate-response approved

PYTHONPATH=~/tmp AIW_EXTRA_WORKFLOW_MODULES=question_gen_smoke \
  aiw run question_gen_smoke --input "First chapter text here..." --run-id qg-smoke-1
```
Documents: any deficiencies found in the prompt (missing fields, unclear step syntax, hallucinated primitives) and any changes made to the prompt template as a result. Non-automated; results in CHANGELOG under `[Unreleased] ### Added`.

### 4. Carry-over items from T01 audits

**LOW-2** (T01 cycle 1, M17-T01-ISS-02) — CLI alias test:
Add `tests/cli/test_run_scaffold_alias.py` testing `aiw run-scaffold` flag parsing via `typer.testing.CliRunner`. Cover: `--goal`, `--target`, `--force`, `--tier-override` flags parsed and forwarded correctly. Use the existing stub adapter (no live LLM needed).

**LOW-3** (T01 cycle 2, M17-T01-ISS-03) — Brace-escape regression test:
Add to `tests/workflows/test_scaffold_workflow.py`:
```python
def test_render_scaffold_prompt_brace_escaping():
    result = render_scaffold_prompt(
        goal="generate {x}",
        target_path="/tmp/{name}.py",
        existing_workflow_context="def f(): return {'a': 1}",
    )
    assert "{x}" in result
    assert "{'a': 1}" in result
```

**ADV-1** (T01 sr-dev) — Hoist inner import:
Move `from ai_workflows.primitives.retry import NonRetryable, RetryableSemantic` from inside `_make_scaffold_validator_node` factory to the module-level import block in `scaffold_workflow.py`.

**ADV-2** (T01 sr-dev) — Docstring fix:
Update `atomic_write` docstring in `_scaffold_write_safety.py`: replace "`tempfile.NamedTemporaryFile(dir=target.parent)`" with "`tempfile.mkstemp(dir=target.parent)`".

## Tests

| Test | File | Kind | Gate |
|---|---|---|---|
| `test_render_scaffold_prompt_brace_escaping` | `tests/workflows/test_scaffold_workflow.py` | unit | `uv run pytest` |
| `test_run_scaffold_alias_*` | `tests/cli/test_run_scaffold_alias.py` | unit | `uv run pytest` |
| `test_scaffold_live_smoke` | `tests/release/test_scaffold_live_smoke.py` | E2E | `AIW_E2E=1 uv run pytest` |
| CS300 dogfood | operator-run | manual smoke | documented in CHANGELOG |

## Acceptance Criteria

- **AC-1 — Prompt template iterated.** `SCAFFOLD_PROMPT_TEMPLATE` teaches `WorkflowSpec` fields, `register_workflow(spec)` convention, four-layer contract. A live CS300-goal run passes `validate_scaffold_output()` on first attempt.
- **AC-2 — Live-mode smoke file lands.** `tests/release/test_scaffold_live_smoke.py` exists; `AIW_E2E=1` gated; invokes real Opus tier (no stub); reaches gate interrupt; asserts non-empty `spec_python` passes validator.
- **AC-3 — CS300 dogfood documented.** CHANGELOG has a note under `[Unreleased]` describing the operator-run CS300 smoke, findings, and any prompt changes made as a result.
- **AC-4 — Brace-escape regression test lands.** `test_render_scaffold_prompt_brace_escaping` in `tests/workflows/test_scaffold_workflow.py` exercises brace-containing inputs in `goal`, `target_path`, and `existing_workflow_context` (closes LOW-3 / M17-T01-ISS-03).
- **AC-5 — CLI alias test lands.** `tests/cli/test_run_scaffold_alias.py` covers `--goal`, `--target`, `--force`, `--tier-override` flag parsing via `typer.testing.CliRunner` (closes LOW-2 / M17-T01-ISS-02).
- **AC-6 — ADV-1 fixed.** Inner import hoisted to module-level in `scaffold_workflow.py` (closes sr-dev ADV-1).
- **AC-7 — ADV-2 fixed.** `atomic_write` docstring updated to reference `tempfile.mkstemp` (closes sr-dev ADV-2).
- **AC-8 — Gates green.** `uv run pytest` (1504+ passed, 0 failed), `uv run lint-imports` (5 kept, 0 broken), `uv run ruff check` (all checks passed).
- **AC-9 — CHANGELOG updated.** `[Unreleased]` has an entry for M17 Task 02 deliverables.

## Dependencies

- T01 ✅ (scaffold_workflow graph + validator + write-safety + CLI/MCP wiring shipped 2026-04-30).
- For AC-2 (live-mode smoke): Claude Code CLI auth required in the sandbox. The hermetic tests (AC-4, AC-5, AC-8) do NOT require live auth.

## Out of scope

- Prompt auto-evaluation (running multiple goals, scoring output quality). T02 is one-pass iteration + one canonical live smoke.
- Validator rule additions beyond the 80-char + `ast.parse` + `register_workflow()` check already in T01.
- ADR-0010 full text. T03.
- Skill-install doc. T03.
- Version bump. T04.

## Carry-over from prior audits

- [ ] **LOW-2** (T01 cycle 1, M17-T01-ISS-02) — `aiw run-scaffold` CLI alias test via `typer.testing.CliRunner`. See AC-5.
- [ ] **LOW-3** (T01 cycle 2, M17-T01-ISS-03) — `render_scaffold_prompt` brace-escape regression test. See AC-4.
- [ ] **ADV-1** (T01 sr-dev) — hoist inner import in `_make_scaffold_validator_node` to module-level. See AC-6.
- [ ] **ADV-2** (T01 sr-dev) — update `atomic_write` docstring: `NamedTemporaryFile` → `mkstemp`. See AC-7.

## Carry-over to T03

- ADR-0010 full text (`design_docs/adr/0010_user_owned_generated_code.md`).
- Skill-install doc §Generating-your-own-workflow (`design_docs/phases/milestone_9_skill/skill_install.md`).
- `docs/writing-a-workflow.md` §Scaffolding section.
