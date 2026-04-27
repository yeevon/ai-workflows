# Task 05 — Rewrite `docs/writing-a-workflow.md` declarative-first (Tier 1 + Tier 2)

**Status:** ✅ Done (implemented 2026-04-26).
**Grounding:** [milestone README](README.md) · [ADR-0008 §Documentation surface (the tier-by-tier doc disposition table)](../../adr/0008_declarative_authoring_surface.md) · [KDR-013 (the existing discovery surface preserved)](../../architecture.md) · [Task 01](task_01_workflow_spec.md) (the spec API the doc teaches) · [Task 02](task_02_compiler.md) (the compiler the doc references) · [Task 03](task_03_result_shape.md) (the renamed `artifact` field referenced in the doc's "what to read from the response" sub-section) · [`docs/writing-a-workflow.md`](../../../docs/writing-a-workflow.md) (the existing doc — 181 lines as of M16; rewrites under this task).

## What to Build

Rewrite `docs/writing-a-workflow.md` declarative-first. The existing doc teaches the LangGraph-builder authoring shape (the heavy path that ADR-0008 repositions as the "escape hatch"). The new doc teaches the spec API (Tier 1 — compose built-in steps + Tier 2 — parameterise them) as the happy path, with brief mentions of Tier 3 (custom step types) and Tier 4 (escape hatch) and strong cross-links to their dedicated guides ([T06's `writing-a-custom-step.md`](task_06_writing_custom_step.md) for Tier 3; the existing [`writing-a-graph-primitive.md`](../../../docs/writing-a-graph-primitive.md) realigned in [T07](task_07_extension_model_propagation.md) for Tier 4).

Identity-level promise the doc delivers (per ADR-0008 §Documentation surface): a downstream consumer with no LangGraph experience writes a working workflow end-to-end from this doc alone. They never `import langgraph`.

## Deliverables

### 1. Rewrite `docs/writing-a-workflow.md`

Section structure (replaces the existing 181-line doc top to bottom):

#### Title + intro
- "Writing a Workflow" — unchanged title.
- Intro: 2-3 sentence framing — a workflow is a `WorkflowSpec` that names inputs, outputs, and ordered steps; the framework synthesizes the LangGraph runtime; you never `import langgraph`.
- Pointer to the [extension model in `architecture.md`](../design_docs/architecture.md) (T07 lands the architecture section) for the full four-tier framing.

#### §Prerequisites
- `ai-workflows` installed (`uv tool install jmdl-ai-workflows`).
- Provider keys (`GEMINI_API_KEY` etc.) — only if the workflow uses tier-routed LLMs.
- `claude` CLI on PATH if the workflow uses Claude Code subprocess tier.

Same content as the current §Prerequisites — preserved verbatim.

#### §The `WorkflowSpec` shape (Tier 1)
A workflow is a pydantic data object. Required fields:
- `name: str` — the registry key.
- `input_schema: type[BaseModel]` — pydantic input model.
- `output_schema: type[BaseModel]` — pydantic output model. The first field is the workflow's terminal artefact and surfaces as `RunWorkflowOutput.artifact`.
- `steps: list[Step]` — ordered list of step instances.

Required (per locked Q3 — the spec is self-contained at registration; no legacy fallback for spec-authored workflows):
- `tiers: dict[str, TierConfig]` — workflow-local tier registry. Empty dict acceptable for no-LLM workflows; for LLM-using workflows, every `LLMStep.tier` value must appear as a key here. Typo'd tier names raise at registration time with a clear message ("got `'planner-syth'`; available tiers: `{'planner-explorer', 'planner-synth'}`").

Show a minimum viable spec: a one-step `ValidateStep`-only workflow. Then upgrade to a one-step `LLMStep` workflow (the `summarize` example from ADR-0008 §Decision).

#### §Built-in step types (Tier 1 + Tier 2)
Each of the five step types: `LLMStep`, `ValidateStep`, `GateStep`, `TransformStep`, `FanOutStep`. Per type:
- One-line role.
- Constructor signature with field types.
- One worked example (3-5 lines).
- The "Tier 2 hooks" sub-line: which fields parameterise behaviour (e.g. `LLMStep.retry`, `LLMStep.tier`, `GateStep.on_reject`).

For `LLMStep` specifically, document **both prompt-source surfaces** with explicit framing on which to pick:
- `prompt_template: str` — Tier 1 sugar. **Only `str.format()`-style substitution is supported** — no Jinja, no f-string evaluation, no callbacks. State fields named in the template are filled in via `state.format(**state)` at call time. Use this when your prompt is a static string with simple `{field_name}` placeholders.
- `prompt_fn: Callable[[dict], tuple[str | None, list[dict]]]` — advanced. The function reads the workflow state and returns `(system_prompt, messages)`. Use this when the prompt is state-derived (multi-turn, context-dependent, builds messages list dynamically). The in-tree planner workflow uses `prompt_fn` because its explorer/synth prompts read multiple state fields and produce structured message lists; a `str.format()` template cannot reproduce them.
- Cross-field invariant: **exactly one** of `prompt_template` or `prompt_fn` must be set. Both set → registration-time `ValidationError` with `"cannot set both"`. Neither set → `"must set exactly one of `prompt_fn` (callable) or `prompt_template` (str.format string)"`.

Total: ~5 sub-sections; each ≤ 20 lines. Doc reader skims the table to find the step they want.

#### §Worked example — the `summarize` workflow
A 2-step example showing composition: `LLMStep(summarize)` + `ValidateStep`. Demonstrates Tier 1 (compose) + Tier 2 (`response_format` validator pairing happens automatically; `retry=RetryPolicy(...)` parameterises the retry budget).

**Source-shared with the in-tree workflow.** The code below is **the literal source** of [`ai_workflows/workflows/summarize.py`](../ai_workflows/workflows/summarize.py) — T04 ships the file; this doc cites it. When the workflow changes, this doc changes; the doctest harness asserts the snippet matches the file byte-for-byte (modulo doctest framing).

```python
from ai_workflows.workflows import register_workflow, WorkflowSpec, LLMStep, ValidateStep, RetryPolicy
from pydantic import BaseModel


class SummarizeInput(BaseModel):
    text: str
    max_words: int


class SummarizeOutput(BaseModel):
    summary: str


register_workflow(WorkflowSpec(
    name="summarize",
    input_schema=SummarizeInput,
    output_schema=SummarizeOutput,
    tiers=summarize_tier_registry(),   # required non-None per locked Q3
    steps=[
        LLMStep(
            tier="summarize-llm",
            prompt_template="Summarize in at most {max_words} words:\n\n{text}",
            response_format=SummarizeOutput,
            retry=RetryPolicy(max_semantic_attempts=2),   # primitives' RetryPolicy field name per locked Q1
        ),
        ValidateStep(target_field="summary", schema=SummarizeOutput),
    ],
))
```

#### §Running your workflow
- CLI: `aiw run summarize --text "..." --max-words 100 --run-id sm-1`.
- MCP: `run_workflow(payload={"workflow_id": "summarize", "inputs": {...}})` over both stdio and HTTP transports. **Document the `payload` wrapper explicitly** — FastMCP convention; was undocumented pre-M19 and tripped up CS-300's pre-flight smoke.
- Reading the response: `result.artifact` is the workflow's terminal artefact; `result.plan` is a deprecated alias preserved for backward compatibility through the 0.2.x line; removal target 1.0.

#### §When you need more — pointers to deeper tiers

Brief one-paragraph framing per deeper tier:

- **Tier 3 — Custom step types** (when no built-in covers your need). Subclass `Step`, implement `execute(state) -> dict` for the typical path, and slot into your spec like a built-in. **Upgrade path within Tier 3:** if your custom step needs to fan out, compose a sub-graph, or emit conditional edges, override `compile(state_class, step_id) -> CompiledStep` directly instead of `execute()` — that gives you the full bespoke-topology surface the built-ins use. See [`docs/writing-a-custom-step.md`](writing-a-custom-step.md) for the full guide including the `compile()` upgrade-path worked example.
- **Tier 4 — Escape to LangGraph directly** (when even Tier 3's custom-step `compile()` override can't express your topology — typically genuinely non-standard control flow patterns the linear step list cannot describe). The existing `register(name, build_fn)` API is preserved for this. See [`docs/writing-a-graph-primitive.md`](writing-a-graph-primitive.md) and the §Escape hatch sub-section below.

#### §External workflows from a downstream consumer

Existing M16 content preserved. Updates:
- The minimum-module-shape example switches from a builder to a `WorkflowSpec`.
- Discovery surface (`AIW_EXTRA_WORKFLOW_MODULES` env + `--workflow-module` CLI flag) — unchanged from M16. Cross-link [ADR-0007](../design_docs/adr/0007_user_owned_code_contract.md) for the discovery decision and [ADR-0008](../design_docs/adr/0008_declarative_authoring_surface.md) for the authoring shape.
- Remove the existing line-90 `return graph.compile()` example — replace with the spec-API minimum shape (which has no compile concern).
- Remove the existing reference to `get_run_status` MCP tool (line 118 — the tool doesn't exist; was the M18 inventory's DOC-CONTRADICTION-1).
- Clarify the `<workflow>_tier_registry()` naming convention (the prefix must literally match the workflow name) — was the M18 inventory's DOC-CONTRADICTION-2.

#### §Escape hatch — when the spec API isn't enough

Brief sub-section. The current `register(name, build_fn)` API is preserved; consumers with non-standard topologies use it. Pointer to `writing-a-graph-primitive.md` for graph-layer extension. Honest note: most workflows do not need the escape hatch; if you reach for it, ask whether the pattern can be expressed as a custom step type first.

#### §Testing your workflow

Same content as current §Testing — uses `StubLLMAdapter` to inject deterministic LLM responses without provider calls. Updated to mention the framework provides spec-compilation fixtures (T06's territory — `compile_step_in_isolation` ships in T06's `ai_workflows/workflows/testing.py`; this doc just points at them).

### 2. Doctest-compilable code snippets

Every executable code block in the doc must compile under `uv run pytest --doctest-modules` if the doc is included in the doctest-modules path. Implementation: either (a) wrap the snippets as docstring examples in a sentinel module under `tests/docs/`, or (b) add explicit pytest markers that exclude untestable snippets (e.g. snippets that depend on a real LLM call). The Auditor verifies at audit time that the worked examples actually run.

### 3. Cross-references audited

Every internal link in the doc is verified at implement time:
- `[architecture overview](../design_docs/architecture.md)` — exists; the link target should point at the new §"Extension model" subsection T07 lands.
- `[writing-a-custom-step.md](writing-a-custom-step.md)` — T06 lands this; T05 cross-links to it forward-anchored.
- `[writing-a-graph-primitive.md](writing-a-graph-primitive.md)` — exists; T07 realigns its content but the link is stable.
- `[ADR-0008](../design_docs/adr/0008_declarative_authoring_surface.md)` — exists.
- `[ADR-0007](../design_docs/adr/0007_user_owned_code_contract.md)` — exists.

Cross-reference rot from the M18 inventory ("(builder-only, on design branch)" annotations) — every annotation in the rewritten doc is audited; outdated annotations removed; genuine design-only references retained with a clearer note.

### 4. Smoke verification (Auditor runs)

```bash
# Doctest-compile every code block (if a doctest harness is configured):
uv run pytest --doctest-modules docs/writing-a-workflow.md

# Lint markdown for broken links:
test -f docs/writing-a-workflow.md
grep -E '^\[.*\]\([^)]+\)' docs/writing-a-workflow.md | while read line; do
  # extract the path; verify it exists relative to docs/
  ...
done

# Manual read-through: the doc opens with the spec API, never imports
# langgraph in any Tier-1 / Tier-2 example, and points at Tier 3 + Tier 4
# guides for deeper extension.
```

The doctest pass is the load-bearing smoke. Manual read-through verifies the framing.

### 5. CHANGELOG

Under `[Unreleased]` on both branches:

```markdown
### Changed — M19 Task 05: docs/writing-a-workflow.md rewritten declarative-first (YYYY-MM-DD)
- Doc now teaches the M19 spec API (Tier 1 — compose built-in steps + Tier 2 — parameterise them) as the happy path. Existing LangGraph-builder content moved under §"Escape hatch — when the spec API isn't enough" with cross-link to docs/writing-a-graph-primitive.md.
- §"External workflows from a downstream consumer" updated: minimum module shape uses `WorkflowSpec`, MCP `payload` wire shape documented, references to non-existent `get_run_status` tool removed, tier-registry naming convention clarified.
- Cross-references audited; outdated "(builder-only, on design branch)" annotations cleared.
```

## Acceptance Criteria

- [x] **AC-1:** `docs/writing-a-workflow.md` rewritten declarative-first. Tier 1 (compose built-in steps) + Tier 2 (parameterise) coverage with worked examples. No `import langgraph` in any Tier-1 or Tier-2 code block.
- [x] **AC-2:** Section structure matches Deliverable 1 (intro / Prerequisites / WorkflowSpec shape / Built-in step types / Worked example / Running / Pointers to deeper tiers / External workflows / Escape hatch / Testing).
- [x] **AC-3:** Worked `summarize` example present (or equivalent generic Tier 1+2 example) with full pydantic models + `register_workflow` call. Doctest-compilable.
- [x] **AC-4:** §"Running your workflow" documents the MCP `{"payload": {...}}` wire wrapping convention with a worked client snippet (resolves M18 DOC-DG4).
- [x] **AC-5:** §"Running your workflow" documents `result.artifact` as the canonical artefact field; `result.plan` mentioned as deprecated alias (composes with T03).
- [x] **AC-6:** §"When you need more" cross-links to `writing-a-custom-step.md` (T06) for Tier 3 and `writing-a-graph-primitive.md` (T07-aligned) for Tier 4. Tier 3 framing includes the `execute()` typical path AND the `compile()` upgrade path for fan-out / sub-graph / conditional cases (per locked Q4 refinement). Every cross-reference link verified resolvable at implement time.
- [x] **AC-7:** §"External workflows from a downstream consumer" updated — minimum module shape uses `WorkflowSpec`, references to non-existent `get_run_status` tool removed, tier-registry naming convention stated explicitly. Resolves M18 DOC-CONTRADICTION-1 + DOC-CONTRADICTION-2.
- [x] **AC-8:** §"Escape hatch" sub-section exists; honest framing that most workflows don't need it; cross-link to `writing-a-graph-primitive.md`.
- [x] **AC-9:** Cross-reference rot cleared. No outdated "(builder-only, on design branch)" annotations on items now in the main tree (e.g. ADR-0007, ADR-0008).
- [x] **AC-10:** Doctest verification (Deliverable 4) passes. Every code block in the doc compiles cleanly.
- [x] **AC-11:** No regression in the doc's existing pedagogical strength — the Auditor's read-through confirms the doc opens with the simplest case and progresses to more complex.
- [x] **AC-12:** CHANGELOG entry under `[Unreleased]` per Deliverable 5.
- [x] **AC-13:** Gates green on both branches. `uv run pytest`, `uv run lint-imports`, `uv run ruff check` (the doc rewrite shouldn't affect these but the audit reruns them).

## Dependencies

- **Task 01 (`WorkflowSpec` + step taxonomy)** — precondition. The doc references the step types T01 ships.
- **Task 02 (compiler)** — soft precondition. The doc references the compiler indirectly (via the worked examples that round-trip through dispatch); doctest assumes T02's compiler is wired.
- **Task 03 (artifact bug fix)** — precondition for §"Running your workflow"'s `result.artifact` reference.
- **T04 ships the `summarize` workflow as the in-tree spec-API proof point.** T05's worked-doc example shares source with `ai_workflows/workflows/summarize.py` — both must ship in the same release. (planner + slice_refactor ports both deferred per locked H2 + Q5 — no T05-equivalent precondition.)
- **Forward-anchors T06** (the doc cross-links to `writing-a-custom-step.md` which T06 creates). T06 must land before this doc ships in the same release; otherwise the cross-link is broken.

## Out of scope (explicit)

- **No `docs/writing-a-custom-step.md` work.** That's T06.
- **No `docs/writing-a-graph-primitive.md` rewrite.** That's T07 (alignment with the four-tier framing).
- **No architecture.md or README.md changes.** That's T07.
- **No deprecation-warning campaigns.** Per M19 README Q3.
- **No ADR work.** ADR-0008 is the load-bearing decision; this doc executes it.
- **No MCP schema changes.** Documented `payload` wrapping is the existing FastMCP convention; the doc surfaces it without changing the wire.

## Carry-over from prior milestones

- **M18 doc-inventory findings** — every doc-relevant item from the M18 hostile re-read inventory (DOC-DC1, DOC-DC2, DOC-DG1, DOC-DG4, R1, R2 — see ADR-0008 §Context for the full list) is resolved in this doc rewrite.

## Carry-over from task analysis

- [x] **TA-LOW-01 — Deprecation-timeline framing consistency** (severity: LOW, source: task_analysis.md round 1)
      Use one phrasing across all M19 specs and the actual CHANGELOG entry: *"deprecated alias preserved for backward compatibility through the 0.2.x line; removal target 1.0."* Verify `result.plan` framing in §"Running your workflow" matches T03's CHANGELOG entry.

- [x] **TA-LOW-06 — Cross-spec consistency on `compile_step_in_isolation` reference** (severity: LOW, source: task_analysis.md round 1)
      §"Testing your workflow" references "framework provides spec-compilation fixtures (T06's territory)." Verify T06 ships `compile_step_in_isolation` (per locked M4) and that this doc's pointer matches the actual fixture name.
