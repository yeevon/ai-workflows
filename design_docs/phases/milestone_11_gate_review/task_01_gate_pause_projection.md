# Task 01 — MCP gate-pause projection

**Status:** 📝 Planned (drafted 2026-04-21).
**Grounding:** [milestone README](README.md) · [architecture.md §4.4](../../architecture.md) · [M9 T04 issue file — ISS-02](../milestone_9_skill/issues/task_04_issue.md) · [schemas.py:79-98](../../../ai_workflows/mcp/schemas.py#L79-L98).

## What to Build

At a HumanGate pause, the MCP `run_workflow` / `resume_run` tools must return the **in-flight draft plan** and a minimum **gate-context projection** so the operator (or the Claude Code skill on their behalf) has something reviewable before they `resume_run`.

The defect today: [`ai_workflows/mcp/schemas.py:86-89`](../../../ai_workflows/mcp/schemas.py#L86-L89) documents and implements `plan` as "populated only on `'completed'`". Net effect per the M9 T04 live smoke: at gate pause the operator sees `{status: "pending", awaiting: "gate", plan: null, ...}` and has no artefact to review. The skill text then truthfully reports "nothing to check" — faithful to the MCP surface, unhelpful to the human.

The fix is **additive** at the MCP surface. No checkpoint format change (KDR-009), no new tool, no new resource, no workflow change. The existing output models grow their `plan` population rule to include gate pauses, and gain a new `gate_context` forward-compat projection field.

## Deliverables

### [ai_workflows/mcp/schemas.py](../../../ai_workflows/mcp/schemas.py) — output models

- **`RunWorkflowOutput`.** Update the docstring: replace *"`plan` is populated only on `'completed'`"* with the new rule — *"`plan` is populated on `'completed'` (terminal artefact) and on `'pending'` when `awaiting='gate'` (in-flight draft); `None` on `'errored'`."*. Add a new field `gate_context: dict[str, Any] | None = Field(default=None, description="…")`. Populated iff `status="pending"` and `awaiting="gate"`; structurally a dict with at minimum the keys `gate_prompt` (str), `workflow_id` (str), `checkpoint_ts` (str ISO-8601). Field is documented as forward-compat — M12 will extend it with cascade-transcript keys (`audit_verdict`, `audit_reasons`, `suggested_approach`) without a schema break.
- **`ResumeRunOutput`.** Mirror the same two changes. The `status` literal set (`pending` / `completed` / `gate_rejected` / `errored`) is unchanged. `plan` docstring rewritten to match (`pending` case added). `gate_context` field added with the same shape and population rule.
- **No change to `RunWorkflowInput` / `ResumeRunInput`.** Input shape is unaffected.
- **No change to the literal sets on `status` or `awaiting`.** The semantic shift is *what `plan` means at `status="pending"`*, not a new status value.

### [ai_workflows/mcp/server.py](../../../ai_workflows/mcp/server.py) + [ai_workflows/mcp/_dispatch.py](../../../ai_workflows/mcp/_dispatch.py) — projection

Locate the code paths that construct `RunWorkflowOutput(...)` and `ResumeRunOutput(...)` on a gate-interrupt return. M4 T02 / T03 landed them in `ai_workflows.mcp._dispatch` (the `_build_result_from_gate` / `_build_resume_result_from_gate` helpers). On gate-interrupt return:

1. Read the current checkpointed state via LangGraph's checkpointer (`SqliteSaver.aget(cfg)` or equivalent — the dispatch layer already holds the `thread_id`). This is a **read**; no persistence change.
2. If `state["plan"]` is present, project it into the output's `plan` field. If absent (unknown workflow shape), leave `plan=None` — no error.
3. Construct `gate_context` = `{gate_prompt: state.get("_gate_prompt", "<gate prompt not recorded>"), workflow_id: <workflow>, checkpoint_ts: <ISO-8601 stamp>}`. The `_gate_prompt` key is the one the `HumanGate` graph primitive already stamps (see `ai_workflows.graph.human_gate`). If the helper's actual key differs, use the real key — the spec is: *whatever channel the existing HumanGate writes the prompt to*.

Keep the **non-gate** paths untouched: `status="completed"` still projects `plan` the same way it did at M4 (`_build_result_from_final` / `_build_resume_result_from_final`), with `gate_context=None`. `status="errored"` returns `plan=None, gate_context=None`.

No new import between layers. `_dispatch` already imports `primitives.storage` and the compiled workflow graph; the additional state-read is over the objects it already holds.

### [.claude/skills/ai-workflows/SKILL.md](../../../.claude/skills/ai-workflows/SKILL.md)

Update the "When the MCP tool returns `status='pending'`" section. Current wording (post-M9): *"Surface the pending status to the user and ask how to resume."* New wording: *"Read the `plan` and `gate_context.gate_prompt` from the response. Surface the **plan body** to the user verbatim, quote the gate prompt, and ask for `approved` or `rejected`. Pass their choice as `gate_response` to `resume_run`."*

### [design_docs/phases/milestone_9_skill/skill_install.md §4 Smoke](../milestone_9_skill/skill_install.md) — smoke update

The `§4 Smoke` walkthrough's expected output at step 3 ("gate pause") currently shows `plan: null`. Update the expected-output snippet to show a non-null plan and a populated `gate_context`. This is a doc-accuracy fix — `tests/skill/test_doc_links.py::test_skill_install_doc_links_resolve` covers link resolution; a matching hermetic test (below) covers the output-shape contract.

### Tests — [tests/mcp/](../../../tests/mcp/)

Three hermetic tests (no real provider, stub adapter) under `tests/mcp/test_gate_pause_projection.py`:

1. `test_run_workflow_gate_pause_projects_plan_and_gate_context` — compile a minimal `planner`-shaped graph with a stub `TieredNode` that returns a fixed `PlannerPlan`, dispatch via `_dispatch.run_workflow`, assert the `RunWorkflowOutput` has `status="pending"`, `awaiting="gate"`, `plan` is a dict with `steps` key, `gate_context` is a dict with `gate_prompt`, `workflow_id`, `checkpoint_ts` keys.
2. `test_resume_run_regate_projects_plan_and_gate_context` — resume with `gate_response="approved"` on a workflow that re-gates; assert `ResumeRunOutput` carries the same projection.
3. `test_completed_status_has_null_gate_context` — run a workflow that completes without pausing (stub plan passes first-try); assert `gate_context=None` on `status="completed"`. Assert the existing `plan` projection on completed is byte-identical to the M4-era shape (no regression).

Fixtures mirror `tests/mcp/test_run_workflow.py` / `test_resume_run.py` patterns — autouse `_redirect_default_paths` for tmp storage + checkpoint.

### [CHANGELOG.md](../../../CHANGELOG.md)

Under `## [Unreleased]`, add a `### Changed — M11 Task 01: MCP gate-pause projection (YYYY-MM-DD)` entry. List files touched, ACs satisfied, and name ISS-02 as the driver (back-link to M9 T04 issue file).

## Acceptance Criteria

- [ ] `RunWorkflowOutput.plan` is non-null on `status="pending", awaiting="gate"` for the `planner` workflow; `gate_context` is a dict with `gate_prompt`, `workflow_id`, `checkpoint_ts`.
- [ ] `ResumeRunOutput.plan` and `.gate_context` mirror the above on re-gate resume.
- [ ] Schema docstrings on both output models rewritten to name the three `plan`-populated statuses (`pending`+`gate`, `completed`, `gate_rejected` terminal draft) and zero the `"only on completed"` text.
- [ ] Non-gate paths unchanged: `status="completed"` returns `plan` per M4 shape (regression test), `gate_context=None`; `status="errored"` returns both `None`.
- [ ] `.claude/skills/ai-workflows/SKILL.md` updated to read the new fields and surface the plan to the operator.
- [ ] `skill_install.md §4 Smoke` expected-output snippet refreshed; existing link tests stay green.
- [ ] Three hermetic MCP tests above land and pass.
- [ ] `uv run pytest` + `uv run lint-imports` (4 contracts kept — no new layer contract) + `uv run ruff check` all clean.
- [ ] CHANGELOG entry under `[Unreleased]` lists files + ACs + ISS-02 driver.
- [ ] [M9 T04 issue file ISS-02](../milestone_9_skill/issues/task_04_issue.md) flipped `OPEN` → `RESOLVED (M11 T01 <sha>)` with back-link; propagation footer updated.

## Dependencies

- **M9 T04 ISS-02** (this task is the closure).
- No workflow code change; the existing `planner` / `slice_refactor` already stamp `plan` into state at the gate pause. M11 reads; does not write.

## Out of scope (explicit)

- **No new MCP tool or resource.** Projection fits inside the existing output models.
- **No workflow change.** `planner` / `slice_refactor` source unchanged.
- **No checkpoint format change.** Projection reads existing state channels (KDR-009).
- **No gate-timeout change.** `strict_review` semantics (KDR-008) unchanged.
- **No M12 cascade work.** Cascade transcript keys in `gate_context` are an M12 additive change against the forward-compat field this task lands.

## Propagation status

Filled in at audit time. ISS-02 resolution back-propagates to the M9 T04 issue file at close-out; no forward carry-over expected unless the audit surfaces a second trigger for a generic state-projection surface (at which point either `nice_to_have.md` or M13+).
