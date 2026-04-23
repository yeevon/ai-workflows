# Milestone 17 — `scaffold_workflow` Meta-Workflow

**Status:** 📝 Planned (drafted 2026-04-23).
**Grounding:** [architecture.md §4.2 + §4.3](../../architecture.md) · [roadmap.md](../../roadmap.md) · [analysis/post_0.1.2_audit_disposition.md](../../analysis/post_0.1.2_audit_disposition.md) · [M15 README](../milestone_15_tier_overlay/README.md) (tier overlay — precondition) · [M16 README](../milestone_16_external_workflows/README.md) (external load path — precondition) · [M11 README](../milestone_11_gate_review/README.md) (gate-pause projection — M17 uses `HumanGate` with reviewable state).

## Why this milestone exists

M15 gave users a way to **rebind** tiers for existing workflows. M16 gave users a way to **drop in** their own workflow Python file. Both are power-user surfaces: editing a `.py` file is the entry cost. A first-time user with a goal (*"generate exam questions from textbook chapters"*, *"refactor this Django app's auth middleware"*, *"summarise meeting transcripts into action items"*) still faces a blank `.py` and has to learn the `register(name, builder)` pattern, the `TieredNode` / `ValidatorNode` / `HumanGate` primitives, the LangGraph `StateGraph` API, and the tier-name conventions — before they write a single line of workflow code.

M17 closes that gap with a **meta-workflow** — a shipped workflow whose job is to generate other workflows. The user invokes `aiw run scaffold_workflow --goal "generate exam questions …" --target ~/my-workflows/question_gen.py`, reviews the generated code at a `HumanGate` that surfaces the full file contents, and on approval the scaffold writes the file to disk. The user then runs it via M16's `AIW_WORKFLOWS_PATH`:

```bash
aiw run scaffold_workflow \
  --goal 'generate exam questions from a textbook chapter' \
  --target ~/my-workflows/question_gen.py
# ... reviews generated code at HumanGate ... approves ...

export AIW_WORKFLOWS_PATH=~/my-workflows
aiw inspect question_gen     # M16's inspection surface
aiw run question_gen --input chapter_1.txt
```

This is the **"help them build it"** piece the operator called out during the M15 design review (2026-04-23). It's the concrete entry point that makes ai-workflows usable for CS300 and beyond: CS300's authors use the scaffold to produce their `question_generation` workflow, review the emitted code, drop it in, iterate.

## Risk-ownership boundary (load-bearing)

**Generated code is owned by the user, not by ai-workflows.** The scaffold writes `.py` files; from that moment on, the files are the user's. ai-workflows does not lint, test, or certify user-generated code — those are the user's decisions with the user's risk.

Concretely:

- The scaffold's LLM → code-gen path emits a file. The paired validator only confirms *"the output parses as Python and contains the expected `register(...)` call shape"* — a workflow-internal schema check, not a safety certificate. **No `pytest`, no `ruff`, no `import-linter`** on the generated artefact before handing it to the user.
- The `HumanGate` at the end of the scaffold surfaces the generated code as a **preview for the user to review**, not as a gate where ai-workflows has pre-certified safety. The gate message is *"here's what I'll write to disk — approve to save or reject to retry with different guidance."*
- Once written to disk, the file lives in the user's `$AIW_WORKFLOWS_PATH`. M16's load path surfaces import errors at startup (so the user sees their own broken code's stack trace), but ai-workflows does not try to fix or sandbox it.
- The scaffold never writes to `ai_workflows/` inside the installed package. Target paths must be user-writable locations; attempting to target a package-relative path fails fast with a clear error.

This framing shapes T01's deliverables and is recorded in **ADR-0007** (M16 T03) + **ADR-0008** (this milestone's T03).

## What M17 ships

1. **`scaffold_workflow` LangGraph `StateGraph`** — shipping in `ai_workflows/workflows/scaffold_workflow.py`. Uses the same graph primitives as `planner` and `slice_refactor`: a `TieredNode` that emits workflow-source as structured output, a `ValidatorNode` that schema-checks the output, a `HumanGate` for the file-preview-and-approve step, and a final write-to-disk node that commits the approved source. Tier defaults: **Claude Opus for the synthesis step** (matches `planner-synth` convention — reasoning-heavy task), **Qwen via Ollama** not used here (the scaffold is single-tier + validator + gate + write).
2. **Output schema.** A pydantic model `ScaffoldedWorkflow` with the fields the scaffold must emit: `name: str`, `source_python: str` (the full `.py` file contents), `description: str`, `declared_tiers: dict[str, TierConfig]`, `requires_human_gate: bool`, `reasoning: str` (why the scaffold chose this structure). The validator asserts `source_python` parses as Python AST + contains at least one `register(...)` call that names the `name` field.
3. **`HumanGate` preview format.** Gate surfaces the full generated `source_python`, the declared tier registry, and a diff-friendly preview of what will be written. M11's gate-pause projection rides through unchanged — the MCP surface (`RunWorkflowOutput.gate_context`) carries the scaffold review content for the operator or an MCP-host reviewer.
4. **Write-to-disk node.** On gate approval, writes `source_python` to the user-supplied `target_path`. Fails fast if the path is inside `ai_workflows/` (package-safety guard), if the file already exists and `--force` was not passed, or if the parent directory is not writable.
5. **Prompt + schema design.** The scaffold prompt is a load-bearing artefact — it teaches the LLM the graph primitives, tier-naming conventions, validator pairing (KDR-004), and the `register()` contract. Shipped as a structured prompt template with slots for the user's goal + any tier preferences. Prompt lives in `ai_workflows/workflows/scaffold_workflow_prompt.py` so it's easy to iterate.
6. **MCP exposure.** `run_workflow(workflow="scaffold_workflow", ...)` + gate-review + resume — identical surface to the shipped workflows. MCP consumers (including CS300 via HTTP) can drive the scaffold from a browser / agent / another workflow.
7. **Skill-install walkthrough.** [`design_docs/phases/milestone_9_skill/skill_install.md`](../milestone_9_skill/skill_install.md) gains a new **§Generating your own workflow** section with the end-to-end flow: `aiw run scaffold_workflow` → review at gate → approve → drop in `AIW_WORKFLOWS_PATH` → run.
8. **ADR-0008 — user-owned generated code.** Records the risk-ownership framing, the validator-scope decision (schema-only, not safety), the write-target safety rules (no in-package writes), and the rejected alternatives (lint/test the generated code before handing it over, sandbox the scaffold runtime, keep generated code inside the package).
9. **Test coverage.** Unit tests for the validator (parseable Python + `register()` shape), the write-to-disk safety guards, the prompt-template rendering, and an integration test via the stub adapter that round-trips a goal → fake-generated source → validator-pass → gate → write. A live-mode test (gated by `AIW_EVAL_LIVE=1` + real Claude Code CLI) exercises the end-to-end path.

## Goal

A user invokes the scaffold and gets a working workflow file:

```bash
aiw run scaffold_workflow \
  --goal 'generate exam questions from a textbook chapter' \
  --target ~/my-workflows/question_gen.py \
  --run-id scaffold-qg-1

# ... scaffold runs; LLM synthesises a StateGraph skeleton ...
# ... validator confirms output parses + has register("question_gen", ...) ...
# ... HumanGate surfaces the full .py contents for review ...

aiw resume scaffold-qg-1 --approve   # or --reject to retry

# On approve: file is written to ~/my-workflows/question_gen.py.
# User inspects, edits if desired, runs via M16's AIW_WORKFLOWS_PATH:
export AIW_WORKFLOWS_PATH=~/my-workflows
aiw list-workflows   # shows question_gen alongside planner + slice_refactor
aiw run question_gen --input chapter_1.txt --run-id qg-smoke
```

The scaffold workflow itself is a legitimate consumer of the same infrastructure (TieredNode + ValidatorNode + HumanGate + register) that the workflows it generates will use. Dogfooding — not new substrate.

## Exit criteria

1. **`scaffold_workflow` ships in `ai_workflows/workflows/scaffold_workflow.py`.** Registered via the same `register("scaffold_workflow", build_scaffold_workflow)` call the shipped workflows use. Declares its own tier registry (`scaffold_workflow_tier_registry()`) with a single tier name (e.g. `scaffold-synth`) routing to Claude Opus. M15's overlay can rebind the tier to Sonnet or an external model without editing the scaffold.
2. **Pydantic output schema.** `ScaffoldedWorkflow` model with the six fields named above. Imported from `ai_workflows/workflows/scaffold_workflow.py` or a sibling schemas module.
3. **Validator enforces "parseable Python + `register()` shape."** The validator parses `source_python` via `ast.parse()`; if parsing raises, the validator rejects. If parsing succeeds, the validator walks the AST looking for a top-level `Call` node whose `func` resolves to the name `register` and whose first arg is a string literal matching the output's `name` field. Anything beyond that — whether the workflow actually works, whether its prompts are sensible, whether its tier registry is coherent — is **not checked**. Risk is the user's.
4. **`HumanGate` preview.** The gate emits `source_python` + a structured `summary` field showing the declared tiers, validators, and write target. M11's projection carries the summary into `RunWorkflowOutput.gate_context` so MCP consumers see the preview.
5. **Write-to-disk safety guards.**
   - Target path must not be inside `ai_workflows/` (compare against the installed package's `__file__` parent). Fails with `TargetInsideInstalledPackageError`.
   - Parent directory must exist + be writable. Fails with `TargetDirectoryNotWritableError` carrying the attempted path.
   - If the file already exists and `--force` was not passed (CLI flag) / `force=False` in the MCP input, fails with `TargetExistsError`.
   - Writes are atomic (write to a temp file + `os.replace`) so a partial write on approval cannot corrupt a previous good file.
6. **Prompt template.** A structured prompt at `ai_workflows/workflows/scaffold_workflow_prompt.py` (module-level constant or pydantic-model-driven). Fields: goal, tier_preferences (optional), target_path, existing_workflow_context (optional — if the user wants the scaffold to mimic an existing workflow's shape). The prompt teaches the LLM the `TieredNode` / `ValidatorNode` / `HumanGate` / `RetryingEdge` primitives + the four-layer contract + the `register()` convention. Prompt engineering is the load-bearing work of T01; the validator is the safety net.
7. **MCP exposure.** `run_workflow(workflow="scaffold_workflow", goal=..., target_path=..., force=False)` works identically on stdio + HTTP. Gate-pause projection (M11) carries the preview content. Resume via `resume_run(run_id=..., approved=True)` writes the file; `approved=False` rejects + retries with different LLM guidance (via the `RetryingEdge` path, up to the budget).
8. **CLI surface.** `aiw run scaffold_workflow --goal ... --target ~/path/file.py [--force]` — the `--target` flag is required; `--force` defaults to False. CLI exit codes: 0 on successful write, non-zero on validator rejection, safety-guard failure, or gate rejection past retry budget.
9. **Skill-install doc extension.** New `§Generating your own workflow` section in [`skill_install.md`](../milestone_9_skill/skill_install.md) covers: invocation, review-at-gate, approve/reject, write path, `AIW_WORKFLOWS_PATH` handoff, where to iterate (edit the generated file, re-register via process restart or `aiw list-workflows` to confirm).
10. **ADR-0008 added** under `design_docs/adr/0008_user_owned_generated_code.md`. Full text drafted at T03.
11. **CS300 dogfood smoke.** A non-blocking smoke path: the operator runs the scaffold against a CS300-shaped goal (question generation from a chapter of text), approves, drops the generated file in a CS300 `AIW_WORKFLOWS_PATH` directory, runs it end-to-end through the MCP HTTP transport. Documented in the close-out CHANGELOG entry; not automated. If this smoke surfaces prompt-engineering deficiencies or validator-edge-cases, they fold into T01 / T02 before close-out.
12. **Hermetic tests.** New `tests/workflows/test_scaffold_workflow.py` covering:
    - Validator: parseable Python passes; unparseable Python rejects; missing `register()` call rejects; `register()` with wrong name rejects; `register()` with matching name passes.
    - Write safety: target inside `ai_workflows/` rejects; nonexistent parent rejects; existing file without `--force` rejects; existing file with `--force` overwrites.
    - Stub-adapter round-trip: goal → scripted LLM output → validator pass → gate trigger → resume with approve → file written.
    - HumanGate projection: M11's gate_context carries the preview content over HTTP.
    New `tests/e2e/test_scaffold_workflow_live.py` (double-gated by `AIW_EVAL_LIVE=1 + AIW_E2E=1`): end-to-end with real Claude Code CLI.
13. **Gates green on both branches.** `uv run pytest` + `uv run lint-imports` (4 kept — scaffold workflow lives in `workflows/` layer alongside `planner` + `slice_refactor`) + `uv run ruff check`.

## Non-goals

- **No lint / test / import-linter on generated code.** The validator checks "parseable + `register()` call" only. Anything more is user territory — the user owns the code from the moment it's written (ADR-0008).
- **No in-package scaffolding.** Target paths inside `ai_workflows/` are rejected. The scaffold is for user-owned code; shipped workflows stay under source control + review.
- **No sandboxing of scaffolded code at runtime.** M16's load path runs user code with full process privileges. M17 just helps write that code; the runtime trust model is owned by M16 + ADR-0007.
- **No automatic re-registration.** After the scaffold writes a file, the user has to restart `aiw` / `aiw-mcp` (or trigger M16's load at a natural lifecycle boundary) for the new workflow to appear in the registry. Hot-reload is a forward option.
- **No version-pinning of generated code to the ai-workflows version.** Generated code may target a specific API shape (e.g. `TieredNode` signature). If ai-workflows evolves the primitive surface, old generated code may break — that's the user's to maintain. M17 does not emit compatibility shims.
- **No code-gen for primitives.** T01 scaffolds workflows only. If a user needs a custom primitive, they write it hand (M16's `AIW_PRIMITIVES_PATH` is the surface). A `scaffold_primitive` workflow is a forward option once the workflow-scaffold shape has shipped and proven out.
- **No multi-file scaffolds.** One invocation = one `.py` file. Workflows that naturally span multiple files (e.g. a large `StateGraph` with dedicated modules) are written hand or generated by multiple scaffold invocations. T01 keeps the unit of generation atomic.
- **No Anthropic API (KDR-003).** The scaffold's LLM tier routes via Claude Code CLI subprocess (default Opus). M15's overlay can rebind to any LiteLLM-supported model; the default stays OAuth-subprocess.
- **No schema discoverability tooling beyond `aiw inspect`.** Users wanting to see available graph primitives read `docs/writing-a-graph-primitive.md`. The scaffold's prompt template does not embed the full primitive inventory — it points at the docs.

## Key decisions in effect

| Decision | Reference |
|---|---|
| Generated code is user-owned; scaffold validates schema only, not safety | ADR-0008 (T03) |
| Validator scope: parseable Python + expected `register()` shape | ADR-0008 |
| No writes inside `ai_workflows/`; atomic writes; existing files need `--force` | ADR-0008 |
| Scaffold is itself a LangGraph workflow — dogfooding, not new substrate | architecture.md §4.2 |
| KDR-004 compliance: LLM node paired with ValidatorNode (schema check only) | KDR-004 |
| M11 gate-pause projection carries the code preview over MCP | KDR-008 + M11 |
| Default tier = Claude Opus via OAuth subprocess; overridable via M15 overlay | KDR-003 + KDR-007 + M15 |

## Task order

| # | Task | Kind |
|---|---|---|
| 01 | [`scaffold_workflow` graph + validator + write-safety + CLI/MCP wiring](task_01_scaffold_workflow.md) | code + test |
| 02 | Prompt template iteration + live-mode smoke + CS300 dogfood | prompt + test |
| 03 | ADR-0008 + skill-install §Generating-your-own-workflow + `docs/writing-a-workflow.md` §Scaffolding | doc |
| 04 | Milestone close-out | doc |

Per-task specs land as each predecessor closes.

## Dependencies

- **M15 landed** (tier overlay + fallback). Scaffold's default tier can be rebound by M15 overlay without regenerating the scaffold itself.
- **M16 landed** (external workflows load path). Without M16, the scaffold's output has nowhere to go — it would write to a file nobody can load. M16 is a hard precondition.
- **M13 (v0.1.0) + M14 (HTTP) + M11 (gate projection)** — shipped. M17 rides on all three.
- **`.claude/skills/ai-workflows/SKILL.md`** — M9's skill packaging extends to cover the scaffold flow at T03 (doc-only; no code change in the skill itself).

## Ships as 0.4.0

M15 → 0.2.0. M16 → 0.3.0. M17 → 0.4.0. Each is an additive minor release; no API breakage.

## Open questions (resolve before T01 kickoff)

- **Prompt template vs. inline string.** Prompt engineering is iterative; the template should be easy to edit without touching the graph wiring. Current plan: module-level constant `SCAFFOLD_PROMPT_TEMPLATE` in `scaffold_workflow_prompt.py`, rendered via `.format()` or pydantic interpolation.
- **Validator falling back to a second attempt.** If the first LLM emit fails schema validation, `RetryingEdge` retries the LLM call (per the `classify()` taxonomy). The validator's failure message is re-rendered into the next prompt attempt to guide the model. If 3 attempts fail, surface the failure at the gate with the last attempt + error — let the user decide whether to abandon or modify the goal.
- **`target_path` normalisation.** `~/path/file.py` vs. `/home/user/path/file.py` vs. relative paths. Current plan: accept any string, resolve via `Path(target).expanduser().resolve()` at input-validation time. Reject relative paths (ambiguous against the user's cwd vs. the server's cwd).
- **Write-target naming convention.** Should the scaffold infer the filename from the workflow name, or does the user pass both? Current plan: user supplies the full target path; the workflow name is inferred from the file stem. Reduces ambiguity + gives the user full control over the on-disk layout.

## Carry-over from prior milestones

- *None at M17 kickoff.* M15 and M16 absorb every pre-M17 finding.

## Propagation status

Filled in at audit time. Anticipated forward-deferrals:

- **Multi-file scaffolds.** `nice_to_have.md` candidate — trigger: a user workflow naturally needs more than one file (e.g. shared constants + graph wiring + adapter overrides). Current scope is one-file-per-invocation.
- **`scaffold_primitive` meta-workflow.** `nice_to_have.md` candidate — trigger: a user needs a custom primitive (e.g. a role-tagged validator) and the hand-written path is painful. Composes over M17's existing scaffold pattern.
- **Template-based scaffolds.** `nice_to_have.md` candidate — trigger: users repeatedly generate scaffolds with similar shapes (e.g. "text-in → structured-out → write file" is a common pattern). Templates would short-circuit the prompt.
- **Lint-the-generated-code toggle.** Explicit non-goal per ADR-0008 + project memory on risk ownership. Not a `nice_to_have.md` entry; deferral is architectural, not operational.

## Issues

Land under [issues/](issues/) after each task's first audit.
