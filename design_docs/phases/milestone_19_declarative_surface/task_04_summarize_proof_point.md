# Task 04 — Ship `summarize` workflow as in-tree spec-API proof point + wire-level e2e verification

**Status:** ✅ Done (implemented 2026-04-26).
**Grounding:** [milestone README](README.md) · [ADR-0008 §Consequences (in-tree workflows must port as M19 proof points; revised after analyzer round 2 — H2 lock)](../../adr/0008_declarative_authoring_surface.md) · [KDR-002 (MCP-as-substrate — the e2e verification rides through the MCP wire)](../../architecture.md) · [KDR-004 (validator pairing — exercised by the `summarize` workflow's `LLMStep` + `ValidateStep` composition)](../../architecture.md) · [Task 01](task_01_workflow_spec.md) (consumes the spec data model) · [Task 02](task_02_compiler.md) (consumes the compiler) · [Task 03](task_03_result_shape.md) (composes — `summarize`'s `FINAL_STATE_KEY = "summary"` round-trips through `RunWorkflowOutput.artifact`) · [Task 05](task_05_writing_workflow_rewrite.md) (the doc whose worked example shares source with this task's `summarize.py`) · [`ai_workflows/workflows/__init__.py`](../../../ai_workflows/workflows/__init__.py) (the registry surface the new workflow registers through) · [`ai_workflows/evals/_stub_adapter.py`](../../../ai_workflows/evals/_stub_adapter.py) (the LLM-stubbing surface the hermetic tests use).

## What to Build

Ship a new in-tree workflow `ai_workflows/workflows/summarize.py` as the M19 spec-API proof point. The workflow uses **only** T01's built-in step types (`LLMStep` + `ValidateStep`); its only purpose is to validate that the spec API compiles, dispatches, checkpoints, and surfaces results end-to-end through both `aiw run` and `aiw-mcp run_workflow`. The same `summarize.py` code is the literal source of T05's worked-doc example (T05 cites the file by path so the doc and the workflow stay in lockstep — when one changes, the other does).

**Why a new in-tree workflow instead of porting `planner`:** analyzer round 2 surfaced that `planner.py:455-682` uses the M8/M10 fault-tolerance overlay (`wrap_with_error_handler`, `build_ollama_fallback_gate`, `CircuitOpen`-aware conditional routing, `planner_hard_stop` terminal node, post-gate artifact storage-write) — the same overlay that drove the locked Q5 deferral of slice_refactor's port. T01's five built-in step types cannot express conditional routing or distinct terminal nodes within a linear `steps: list[Step]`. Porting planner under the original T04 framing would hit the same taxonomy gap; the behavioural-equivalence acceptance criterion would be unsatisfiable. Per H2 lock (2026-04-26), planner stays on its existing `register("planner", build_planner)` registration through 0.3.x — same escape-hatch posture as slice_refactor.

The H2 framing: M19 ships a new in-tree workflow that demonstrates the simplest realistic shape (single LLM call + validator), proves the spec API end-to-end through both surfaces, and preserves the existing complex workflows on the documented escape hatch until external mileage tells us which extensions to add. The `summarize` workflow is genuinely useful (not a toy `echo` placeholder), so the "framework dogfoods its own spec API" claim is real — just smaller-scope than planner.

## Deliverables

### 1. New module `ai_workflows/workflows/summarize.py`

Lives in the workflows layer alongside `planner.py`, `slice_refactor.py`, `_compiler.py`, `spec.py`, etc. Imports stdlib + `pydantic` + `ai_workflows.workflows` (for the spec types) only. **No graph imports** — the workflow is pure-spec; the compiler owns all LangGraph wiring.

```python
"""summarize — the M19 spec-API proof-point workflow.

Authored at M19 T04 to (a) prove the declarative spec API compiles +
dispatches + checkpoints + surfaces results end-to-end through both
``aiw run`` and ``aiw-mcp run_workflow``, and (b) provide a worked
example downstream consumers copy-paste from. The same code is the
literal source of ``docs/writing-a-workflow.md`` §Worked example
(T05); when one changes, the other does.

Shape: single tier-routed LLM call (LLMStep) + a ValidateStep against
the output schema. Uses the simplest realistic spec — no GateStep, no
TransformStep, no FanOutStep — so an external author reading this
module sees the smallest viable spec rather than a large reference.

Per ADR-0008 + locked H2 (2026-04-26): this is the only in-tree
workflow on the spec API at 0.3.0. The legacy ``planner`` and
``slice_refactor`` workflows remain on the existing
``register(name, build_fn)`` escape hatch through 0.3.x; their
ports are forward-deferred per locked Q5 + H2 + the re-open
trigger captured in nice_to_have.md.
"""
from __future__ import annotations

from pydantic import BaseModel

from ai_workflows.workflows import (
    LLMStep,
    RetryPolicy,        # re-exported from ai_workflows.primitives.retry per locked Q1
    ValidateStep,
    WorkflowSpec,
    register_workflow,
)
from ai_workflows.workflows.summarize_tiers import summarize_tier_registry


class SummarizeInput(BaseModel):
    """Input schema — the user's text + how aggressively to summarise."""
    text: str
    max_words: int


class SummarizeOutput(BaseModel):
    """Output schema — the LLM's summary. First field is the workflow's terminal artefact (FINAL_STATE_KEY)."""
    summary: str


_SPEC = WorkflowSpec(
    name="summarize",
    input_schema=SummarizeInput,
    output_schema=SummarizeOutput,
    tiers=summarize_tier_registry(),
    steps=[
        LLMStep(
            tier="summarize-llm",
            prompt_template=(
                "Summarize the following text in at most {max_words} words. "
                "Respond with a JSON object matching the SummarizeOutput schema.\n\n"
                "Text:\n{text}"
            ),
            response_format=SummarizeOutput,
            retry=RetryPolicy(
                max_transient_attempts=3,
                max_semantic_attempts=2,
                transient_backoff_base_s=0.5,
                transient_backoff_max_s=4.0,
            ),
        ),
        ValidateStep(
            target_field="summary",
            schema=SummarizeOutput,
        ),
    ],
)


register_workflow(_SPEC)
```

Field-level details:

- `prompt_template` (Tier 1 sugar — `str.format()`-only per locked Q2). The summarize prompt is straightforward enough to express as a template; advanced state-derived prompt construction is not needed. This deliberately exercises the `prompt_template` path (T04's planner-port draft would have exercised `prompt_fn`; the synthetic workflow flips the prompt-source choice so the spec API gets coverage on both shapes once T05's doc uses both).
- `response_format=SummarizeOutput` — the validator pairing is automatic (KDR-004 by construction per T01 + T02). The `ValidateStep` after the `LLMStep` is illustrative; in this exact configuration where its `schema` matches the upstream `LLMStep.response_format`, it is a runtime no-op (the LLMStep's paired validator already validated). The composition is shown for syntactic illustration only.
- `retry=RetryPolicy(...)` — uses the primitives' `RetryPolicy` field names (`max_transient_attempts` / `max_semantic_attempts` / backoff fields) per locked Q1. Defaults match the existing `RetryingEdge` defaults; no behavioural surprise.
- `tiers=summarize_tier_registry()` — required non-None per locked Q3.

### 2. New module `ai_workflows/workflows/summarize_tiers.py`

```python
"""summarize_tier_registry — the tier registry for summarize.py.

Lives in a separate module from ``summarize.py`` so the spec module
itself stays pure-pydantic + spec-import. This mirrors the planner /
slice_refactor pattern (each ships an `<workflow>_tier_registry()`
helper) but the spec-API workflow uses ``WorkflowSpec.tiers=`` rather
than the legacy `<workflow>_tier_registry()` getattr fallback.
"""
from __future__ import annotations

from ai_workflows.primitives.tiers import LiteLLMRoute, TierConfig


def summarize_tier_registry() -> dict[str, TierConfig]:
    """Return the tier registry for the summarize workflow.
    
    Single tier — ``summarize-llm`` — routes to Gemini Flash via LiteLLM
    (KDR-007 — LiteLLM unified for Gemini). Cheaper than Claude Code OAuth
    paths; faster than Ollama-routed tiers.
    """
    return {
        "summarize-llm": TierConfig(
            name="summarize-llm",
            route=LiteLLMRoute(model="gemini/gemini-2.5-flash"),
            max_concurrency=4,
            per_call_timeout_s=120,
        ),
    }
```

`LiteLLMRoute` lives at `ai_workflows/primitives/tiers.py` (not a sub-module under `primitives/providers/`); both `LiteLLMRoute` and `TierConfig` import from the same module. The route carries `kind` + `model` + `api_base` only — temperature / max_tokens / sampling-config concerns are LiteLLM-driver-level kwargs handled by the adapter, not fields on `LiteLLMRoute` itself. `TierConfig` requires `name=` (matching the registry key) and accepts optional `per_call_timeout_s`. Use `gemini/gemini-2.5-flash` (the project's canonical Gemini route per existing tier configs); verify the model name at implement time against the live planner / slice_refactor tier configs.

### 3. Hermetic test — `tests/workflows/test_summarize.py`

Exercises the spec → compile → dispatch → response chain end-to-end against `StubLLMAdapter` (no provider call).

- `test_summarize_registers_via_spec_api` — assert `'summarize' in workflows.list_workflows()` after importing `ai_workflows.workflows.summarize`.
- `test_summarize_compiles_to_runnable_state_graph` — call the registered builder; assert the result is a `StateGraph`; compile with the in-memory checkpointer and invoke against a hand-built initial state. Stub LLM returns a valid `SummarizeOutput`. Assert the final state has `summary` populated.
- `test_summarize_round_trips_through_dispatch` — drive `_dispatch.run_workflow` directly with `workflow="summarize"` + `inputs={"text": "...", "max_words": 50}` against `StubLLMAdapter`. Assert the response has `status="completed"` and `artifact == {"summary": "<stub value>"}`. **Composes with T03** — `summarize`'s `FINAL_STATE_KEY = "summary"` (the first field of `SummarizeOutput`); the response surfaces it through the `artifact` field per T03's bug fix. Also assert `result.plan == result.artifact` (the deprecated alias from T03 stays in lockstep).
- `test_summarize_validator_step_runs` — variant of the round-trip test where the stub LLM returns a malformed `SummarizeOutput`. Assert the workflow errors out via the validator (or retries per `RetryPolicy(max_semantic_attempts=2)` then errors). Pins the `ValidateStep` step-type contribution.
- `test_summarize_retry_policy_on_transient_failure` — variant where the stub LLM raises a transient error twice then returns a valid response. Assert retry budget consumed; workflow completes. Pins the `RetryPolicy` parameterisation.

Hermetic; combined runtime <2s wall-clock.

### 4. Extend `aiw run` to accept arbitrary input shapes via `--input KEY=VALUE` (per locked H1 — α-1)

**The CLI gap closure for the spec API.** The existing `aiw run` (`ai_workflows/cli.py:185-227`) hardcodes planner-shape input flags: `--goal`, `--context`, `--max-steps`. Per locked H1 (analyzer round 3), this prevents `aiw run summarize --text "..." --max-words 50` from parsing — the spec API would be MCP-only without this fix. Without the CLI extension, M19 ships an architectural regression from M16's surface-parity claim (KDR-002 says MCP is the substrate; CLI is the second public surface, not the only-substrate). Three options surfaced (α drop the CLI proof, β reframe to planner-shape, γ extend the CLI); user locked **α-1 with refinements** — extend additively, preserve planner flags byte-identically.

**Add to `ai_workflows/cli.py`:**

- New `--input KEY=VALUE` Typer option on `aiw run` — repeatable. Coexists with existing `--goal`/`--context`/`--max-steps`/`--budget`/`--run-id`/`--tier-override` flags. New canonical path for spec-API workflows; existing planner flags continue to work for `aiw run planner ...` invocations byte-identically (no deprecation, no warning — purely additive per refinement #1).
- Parser: the dispatch code merges `--goal`/`--context`/`--max-steps` (when provided) with `--input KEY=VALUE` (when provided) into a single `inputs: dict[str, Any]` before calling `_dispatch.run_workflow`. **On conflict** between a planner flag and an `--input` entry naming the same key, **raise `typer.BadParameter`** with an explicit message (refinement #1 — raise on conflict; loud-failure default matches the framework's existing posture). Conflict scenario: `aiw run planner --goal "x" --input goal="y"` → `BadParameter("conflicting input 'goal': set via both --goal flag and --input goal=...; choose one")`.
- Type coercion: pass the parsed string-string `dict[str, str]` from `--input KEY=VALUE` straight into `workflow_module.initial_state(run_id, inputs_dict)`, which already calls `input_schema(**inputs_dict)` per T02's compiler. Pydantic v2 coerces `"50"` → `int 50` for int-typed fields, `"true"` → `bool True`, etc. (refinement #2). What's free: scalar coercion, bool parsing, enum string→value lookup. What's not: lists, nested dicts, dates without ISO format. Document in T05 as a CLI limitation — complex inputs go via MCP.
- Validation errors as `typer.BadParameter`: when pydantic raises `ValidationError` on bad input, wrap it via the existing `_parse_tier_overrides` pattern (`cli.py:_parse_tier_overrides` — find the helper at implement time; it already handles validation-error wrapping for `--tier-override`). Mirror that shape so the user sees `Error: input 'max_words' must be int (got 'fifty')` rather than a stack trace (refinement #3).
- Help text discoverability: `aiw run <workflow> --help` should list the workflow's `input_schema` fields. Typer can't auto-generate flags for an arbitrary schema, but the help callback can render an `Inputs (pass via --input KEY=VALUE):` section with `- text (str)`, `- max_words (int, optional, default 100)` lines derived from `workflow_module.initial_state.__annotations__` or `input_schema.model_fields`. ~10 lines of help-rendering code (refinement #4). Test that the help output mentions every `input_schema` field by name (refinement watch-point #3).

**Concrete shape (sketch — Builder refines at implement time):**

```python
# ai_workflows/cli.py — additive extension

def _parse_inputs(input_kvs: list[str]) -> dict[str, str]:
    """Parse `key=value` strings into a dict; raise typer.BadParameter on malformed."""
    parsed: dict[str, str] = {}
    for kv in input_kvs:
        if "=" not in kv:
            raise typer.BadParameter(f"--input must be KEY=VALUE, got: {kv!r}")
        key, value = kv.split("=", 1)
        if not key:
            raise typer.BadParameter(f"--input KEY cannot be empty, got: {kv!r}")
        parsed[key] = value
    return parsed


@app.command()
def run(
    workflow: str,
    goal: str | None = typer.Option(None, "--goal", help="..."),
    context: str | None = typer.Option(None, "--context", help="..."),
    max_steps: int | None = typer.Option(None, "--max-steps", help="..."),
    input_kvs: list[str] = typer.Option(
        [],
        "--input",
        help="Generic input as KEY=VALUE (repeatable). Workflow's input_schema receives the merged dict; "
             "pydantic v2 coerces string values to int/bool/enum types as declared. Use for spec-API "
             "workflows whose inputs don't fit the planner-shape --goal/--context/--max-steps flags. "
             "Complex inputs (lists, nested dicts) go via MCP.",
    ),
    # ... existing --budget, --run-id, --tier-override flags unchanged ...
) -> None:
    """..."""
    # Build the inputs dict by merging planner flags + --input KVs:
    inputs: dict[str, Any] = {}
    planner_flags = {"goal": goal, "context": context, "max_steps": max_steps}
    for key, value in planner_flags.items():
        if value is not None:
            inputs[key] = value
    extra_inputs = _parse_inputs(input_kvs)
    for key, value in extra_inputs.items():
        if key in inputs:
            raise typer.BadParameter(
                f"conflicting input {key!r}: set via both --{key.replace('_', '-')} flag "
                f"and --input {key}=...; choose one"
            )
        inputs[key] = value
    # ... existing dispatch path unchanged: pass `inputs` to _run_workflow.
```

**Help-text rendering (refinement #4)** — add a separate `--show-inputs <workflow>` subcommand or a custom callback on `aiw run --help <workflow>` that introspects the workflow's `input_schema.model_fields` and renders the field list. Builder picks the exact UX at implement time; the test (refinement #5) just asserts every input field name appears in `--help` output.

**Existing-test migration:** `tests/cli/test_run.py:261-264` `test_run_missing_goal_exits_two` asserts that omitting `--goal` exits with code 2 (typer's `BadParameter` for missing required option). Once H1 makes `--goal` optional (so non-planner workflows like `summarize` don't need it), this test's assertion shifts: `aiw run planner` (with no `--goal` and no `--input goal=...`) no longer fails at typer-parse time — it fails at dispatch-layer pydantic validation when `PlannerInput(goal=None)` raises (because planner's input schema declares `goal: str` as required). Builder updates the test to assert the new failure path: same exit code (still 2 if BadParameter wraps the pydantic error per refinement #3, or whatever the dispatch-error wrapping converges on); error message contains `'goal'` and `'required'`. AC-9's "byte-identical" claim covers the **success** path (`aiw run planner --goal "x"` continues to work unchanged); the **failure** path migration is documented here and the test update lands as part of T04.

### 5. Wire-level integration test — `tests/integration/test_spec_api_e2e.py`

**The load-bearing wire-level proof.** Drives `summarize` through both surfaces using their actual entry-points; this is what proves "the spec API works end-to-end through `aiw run` and `aiw-mcp run_workflow`," which no unit test alone can prove (per the H2 lock framing — α was rejected because shipping a brand-new authoring surface with no wire-level proof = first external user becomes the integration test). Per locked H1 + refinement #5: the integration test explicitly covers both paths and asserts the response artefact is identical from both surfaces.

- `test_aiw_run_summarize_via_input_kvs` — uses `typer.testing.CliRunner` to invoke `aiw run summarize --input text="The quick brown fox..." --input max_words=50 --run-id smry-1` against `StubLLMAdapter`. Asserts exit code 0; stdout contains the run-id + the artefact. Exercises the locked-H1 `--input KEY=VALUE` shape end-to-end. Pydantic coerces `"50"` → `int 50` for `SummarizeInput.max_words` automatically.
- `test_aiw_run_summarize_help_lists_input_fields` — uses `CliRunner` to invoke `aiw run summarize --help` (or whatever the locked-H1 help-rendering UX shape lands as). Asserts the help output mentions both `text` and `max_words` field names from `SummarizeInput.model_fields`. Pins refinement #4 (help text discoverability).
- `test_aiw_run_planner_flag_input_conflict_raises` — uses `CliRunner` to invoke `aiw run planner --goal "x" --input goal="y"` (a deliberate conflict between the planner-shape `--goal` flag and the new `--input` mechanism). Asserts exit code 2 (Typer's BadParameter exit code) + stderr contains `conflicting input 'goal'`. Pins refinement #1 (raise on conflict).
- `test_aiw_mcp_run_workflow_summarize_via_fastmcp_client` — uses `fastmcp.Client` to invoke `run_workflow(payload={"workflow_id": "summarize", "inputs": {"text": "...", "max_words": 50}})` over the in-process MCP server. Asserts `result.data.artifact == {"summary": "<stub value>"}` and `result.data.status == "completed"`. **Resolves M18 inventory DOC-DG4** — the `payload` wire-shape wrapper is exercised live in M19's own test surface.
- `test_summarize_artefact_identical_across_surfaces` — uses both `CliRunner` and `fastmcp.Client` to drive the same `summarize` workflow against the same `StubLLMAdapter` (same stub response). Asserts the resulting artefacts are byte-identical (`{"summary": "<stub value>"}` from both surfaces). Pins refinement #5 (load-bearing wire-level proof — both surfaces produce the same result).
- Tests share a fixture that registers `StubLLMAdapter` as the LLM provider for the `summarize-llm` tier so no Gemini call fires.

This test file is **new** (`tests/integration/` may need to be created if absent — the existing `tests/cli/`, `tests/mcp/`, `tests/workflows/` already exist; placing this under `tests/integration/` makes the wire-level intent explicit).

### 6. Documentation alignment with T05

T05 (`docs/writing-a-workflow.md` rewrite) cites `ai_workflows/workflows/summarize.py` as the source of its worked example. T04 ships the file; T05 uses it. The doc and the workflow share source — when one changes, the other does. T05's AC includes "the worked-example code matches `summarize.py` byte-for-byte (modulo doctest framing)."

T04 itself does not edit T05. The cross-reference is documented in T05's grounding section + AC.

### 7. CHANGELOG

Under `[Unreleased]` on both branches:

```markdown
### Added — M19 Task 04: summarize workflow as in-tree spec-API proof point + aiw run --input extension (YYYY-MM-DD)
- `ai_workflows/workflows/summarize.py` — new in-tree workflow authored against the M19 declarative spec API per ADR-0008 + locked H2. WorkflowSpec instance composing `LLMStep` (single tier-routed LLM call with `prompt_template` Tier 1 sugar) + `ValidateStep` (redundant schema check exercising the step type). Sole purpose: prove the spec API compiles + dispatches + checkpoints + surfaces results end-to-end through both `aiw run` and `aiw-mcp run_workflow`. Doubles as the worked-doc example T05 cites.
- `ai_workflows/workflows/summarize_tiers.py` — `summarize_tier_registry()` helper. Single tier `summarize-llm` routed to Gemini Flash via LiteLLM (KDR-007).
- `aiw run --input KEY=VALUE` (repeatable) — new CLI flag for spec-API workflows whose inputs don't fit the planner-shape `--goal`/`--context`/`--max-steps` flags. Coexists with the existing planner flags; raises `BadParameter` on conflict between a planner flag and an `--input` entry naming the same key. Pydantic v2 coerces string values to declared types. Per locked H1.
- `tests/workflows/test_summarize.py` — 5 hermetic tests against `StubLLMAdapter`.
- `tests/integration/test_spec_api_e2e.py` — wire-level tests (CLI via CliRunner + MCP via fastmcp.Client + cross-surface artefact identity). The load-bearing e2e proof for the M19 spec API.
```

(The H2 deferral framing — "planner port deferred per locked H2" — is recorded in the README §Decisions item 7 + T08 outcome record per design_branch's audit trail; not duplicated as a `### Changed` CHANGELOG entry per M6 fix from analyzer round 3 — `planner.py` is unchanged, so the user has no observable difference to surface.)

## Acceptance Criteria

- [x] **AC-1:** `ai_workflows/workflows/summarize.py` exists with the structure from Deliverable 1: `SummarizeInput` + `SummarizeOutput` pydantic models, `_SPEC` constant defined as a `WorkflowSpec` composing `LLMStep` (with `prompt_template` Tier 1 sugar) + `ValidateStep`, `register_workflow(_SPEC)` at module top level. No `import langgraph` anywhere in the module.
- [x] **AC-2:** `ai_workflows/workflows/summarize_tiers.py` exists with `summarize_tier_registry()` helper returning a `dict[str, TierConfig]` with the `summarize-llm` tier routed to Gemini Flash via LiteLLM.
- [x] **AC-3:** Module docstring on `summarize.py` cites M19 T04, ADR-0008, locked H2 (2026-04-26), and the dual purpose (in-tree proof point + worked-doc-example source).
- [x] **AC-4:** `tests/workflows/test_summarize.py` exists with the 5 tests from Deliverable 3. All green; hermetic; combined runtime <2s wall-clock.
- [x] **AC-5:** `aiw run` extended to accept `--input KEY=VALUE` (repeatable) per locked H1 + Deliverable 4. Existing planner flags (`--goal`, `--context`, `--max-steps`) preserved byte-identically; conflict between a planner flag and an `--input` entry naming the same key raises `BadParameter`; pydantic v2 type coercion on the merged inputs dict; help text mentions every `input_schema` field by name. ~30-50 lines added to `cli.py` per Deliverable 4's sketch; no diff to other CLI commands (`resume`, `list-runs`, `cancel`, `eval`).
- [x] **AC-6:** `tests/integration/test_spec_api_e2e.py` exists with the 5 wire-level tests from Deliverable 5 (CLI via `--input`, CLI help-rendering, CLI conflict-raising, MCP via `fastmcp.Client`, cross-surface artefact identity). All green. Resolves M18 inventory DOC-DG4 (FastMCP `payload` wire shape) by exercising it live; resolves locked H1's CLI gap by exercising the `--input` flag end-to-end.
- [x] **AC-7:** `summarize`'s `FINAL_STATE_KEY = "summary"` (first field of `SummarizeOutput`) round-trips correctly through `RunWorkflowOutput.artifact` per T03's bug fix. The integration test's MCP assertion explicitly checks `result.data.artifact["summary"]` (not `result.data.plan["summary"]`); both fields are populated and equal.
- [x] **AC-8:** No port of `planner` or `slice_refactor`. Both stay on the existing `register(name, build_fn)` registration unchanged. T04's diff to `planner.py` and `slice_refactor.py` is **zero lines**. The H2 lock + Q5 lock are documented in the README §Decisions item 7 + T08's Outcome record.
- [x] **AC-9:** Existing tests stay green or migrate per Deliverable 4. The `summarize` workflow is purely additive; no existing dispatch path or workflow is modified. The `aiw run planner --goal "x" --max-steps 5` **success** path continues to work byte-identically (preserved by Deliverable 4's additive shape). The **failure** path for `aiw run planner` with no `--goal` migrates from typer-parser (exit 2 from BadParameter) to dispatch-layer pydantic validation (exit 2 wrapped via the `_parse_inputs` validation helper); `tests/cli/test_run.py:261-264` (`test_run_missing_goal_exits_two`) updates per Deliverable 4 §"Existing-test migration." Failure error message still contains `'goal'` + `'required'`. No other CLI tests modified.
- [x] **AC-10:** Layer rule preserved — `uv run lint-imports` reports 4 contracts kept, 0 broken. `summarize.py` imports `ai_workflows.workflows` (spec types) + `pydantic` only; `summarize_tiers.py` imports `ai_workflows.primitives.tiers` only (both `LiteLLMRoute` and `TierConfig` from the same module). `cli.py` extension imports stay within the existing surfaces layer.
- [x] **AC-11:** Gates green on both branches. `uv run pytest`, `uv run lint-imports`, `uv run ruff check`.
- [x] **AC-12:** CHANGELOG entry (Added) under `[Unreleased]` per Deliverable 7. The H2 deferral framing is recorded in the README §Decisions item 7 + T08's Outcome record per design_branch's audit trail; not duplicated as a `### Changed` CHANGELOG entry (planner.py is unchanged, so the user has no observable difference to surface).
- [x] **AC-13:** No new step types added to T01's taxonomy. If implementing `summarize` surfaces a needed step type the taxonomy doesn't have, **stop and ask the user** — H2 explicitly rejected option γ (extending the taxonomy now). The `summarize` workflow is designed to fit inside the five built-ins as-is.

## Dependencies

- **Task 01 (`WorkflowSpec` + step taxonomy)** — precondition.
- **Task 02 (compiler)** — precondition. T04 dispatches through the compiled spec end-to-end.
- **Task 03 (artifact bug fix)** — precondition. T04 AC-6 explicitly verifies the round-trip through `RunWorkflowOutput.artifact`; without T03's fix the assertion would fail (the artefact would silently drop).
- **Forward-anchors T05** (T05's worked-doc example cites `summarize.py` — both must ship in the same release).
- **Forward-anchors T08** (T08's pre-publish gates include the `summarize` test sweep + the live-smoke from `/tmp` against real Gemini).

## Out of scope (explicit)

- **No port of `planner`.** Deferred per locked H2 (2026-04-26). planner stays on `register("planner", build_planner)` through 0.3.x. Re-open trigger captured in T07's `nice_to_have.md` entry alongside slice_refactor's.
- **No port of `slice_refactor`.** Deferred per locked Q5 (2026-04-26).
- **No new step types beyond T01's five built-ins.** `summarize` is designed to fit inside `LLMStep` + `ValidateStep`; if implementation surfaces a need for a new step type, stop and ask the user.
- **No edits to existing in-tree workflows.** `planner.py` and `slice_refactor.py` are unchanged.
- **No documentation work.** T05 + T06 + T07 own docs; T04 ships only the workflow + tests + CHANGELOG entry.
- **No MCP schema changes.** `summarize` rides on the existing MCP surface; the `payload` wrapper is the existing FastMCP convention; M18-DOC-DG4 is resolved by *exercising* the wrapper, not changing it. **The CLI surface IS extended in this task** (per locked H1 + Deliverable 4 — `aiw run --input KEY=VALUE` is new in M19); only the MCP schema is out-of-scope.
- **No live-Gemini integration test.** The wire-level proof in `tests/integration/test_spec_api_e2e.py` uses `StubLLMAdapter`. The live-Gemini smoke against real provider lives in T08's release ceremony (post-publish, from `/tmp`).
- **No new cost surface.** `summarize`'s tests assert workflow completion + artefact round-trip only; cost assertions (if any) use `>= 0` per the surface-review guardrail (Claude Code Opus reports notional costs; Gemini reports real costs). Per the M19 README's locked T01 §Out-of-scope: M19 inherits `runs.total_cost_usd` and stops.

## Carry-over from prior milestones

*None.* Builds on M16-shipped surface + M19 T01 + T02 + T03.

## Carry-over from task analysis

- [x] **TA-LOW-02 — Module-restructuring fallback threshold** (severity: LOW, source: task_analysis.md round 1)
      The `summarize_tiers.py` split mirrors the planner / slice_refactor pattern; if circular imports surface between the spec module and the tier-registry module, fall back to inlined tiers in `summarize.py`. Builder discretion at implement time.

- [x] **TA-LOW-10 — Straggler `_run_workflow` reference in Python comment at line 214** (severity: LOW, source: task_analysis.md round 5)
      The Python comment in Deliverable 4's `cli.py` sketch — `# ... existing dispatch path unchanged: pass `inputs` to _run_workflow.` — still uses the leading-underscore form. The actual exported function is `_dispatch.run_workflow` (no leading underscore on the function; the underscore is on the module name). Builder self-corrects against the canonical references elsewhere in this spec; mechanical edit at implement time updates the comment to match.
