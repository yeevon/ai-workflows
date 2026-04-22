# Task 01 — MCP gate-pause projection

**Status:** 📝 Planned (drafted 2026-04-21; amended 2026-04-22 after T01 pre-implementation evaluation fixed five source-drift inaccuracies and absorbed two scope gaps).
**Grounding:** [milestone README](README.md) · [architecture.md §4.4](../../architecture.md) · [M9 T04 issue file — ISS-02](../milestone_9_skill/issues/task_04_issue.md) · [schemas.py:79-122](../../../ai_workflows/mcp/schemas.py#L79-L122) · [workflows/_dispatch.py:567-937](../../../ai_workflows/workflows/_dispatch.py#L567-L937) · [graph/human_gate.py](../../../ai_workflows/graph/human_gate.py).

## What to Build

At a `HumanGate` pause, the MCP `run_workflow` / `resume_run` tools must return the **in-flight draft plan** and a minimum **gate-context projection** so the operator (or the Claude Code skill on their behalf) has something reviewable before they `resume_run`.

The defect today: [`schemas.py:86-89`](../../../ai_workflows/mcp/schemas.py#L86-L89) documents and implements `plan` as "populated only on `'completed'`". Net effect per the M9 T04 live smoke: at gate pause the operator sees `{status: "pending", awaiting: "gate", plan: null, ...}` and has no artefact to review. The skill text then truthfully reports "nothing to check" — faithful to the MCP surface, unhelpful to the human.

The fix is **additive** at the MCP surface. No checkpoint format change (KDR-009), no new tool, no new resource, no workflow change. The existing output models grow their `plan` population rule to include gate pauses and gate-rejected terminals, gain a new `gate_context` forward-compat projection field, and (pre-existing schema-literal bug) grow their `status` Literal to accept `"aborted"`.

### Source-drift fixes folded into this task (from 2026-04-22 evaluation)

| # | What the pre-2026-04-22 spec said | What is actually in source | Resolution in this spec |
| --- | --- | --- | --- |
| **A** | Projection code lives in `ai_workflows/mcp/_dispatch.py`. | That file does not exist. Dispatch is `ai_workflows/workflows/_dispatch.py`; `server.py` just wraps it and calls `RunWorkflowOutput(**result)` / `ResumeRunOutput(**result)`. | Target [`workflows/_dispatch.py`](../../../ai_workflows/workflows/_dispatch.py). Specifically the `_build_result_from_final` (L567) and `_build_resume_result_from_final` (L802) helpers — both already own the interrupt branch where the projection needs to land. |
| **B** | `HumanGate` "stamps a `_gate_prompt` key into state"; read it from `state["_gate_prompt"]`. | `HumanGate` does not write to any state channel for the prompt. It calls `storage.record_gate(...)` and emits the prompt via `interrupt(payload)` — the payload surfaces in `final["__interrupt__"][0].value` as `{gate_id, prompt, strict_review, timeout_s, default_response_on_timeout}`. Pattern already exercised by [test_slice_refactor_strict_gate.py:448](../../../tests/workflows/test_slice_refactor_strict_gate.py#L448). | Projection reads `final["__interrupt__"][0].value` and pulls `prompt` + `gate_id` from that dict. Zero new storage surface; zero new state channel. |
| **C** | (Pre-existing latent bug, not previously surfaced in M11 spec.) | `RunWorkflowOutput.status: Literal["pending", "completed", "errored"]` ([schemas.py:93](../../../ai_workflows/mcp/schemas.py#L93)), but dispatch returns `"aborted"` on two paths: ollama-fallback abort ([_dispatch.py:625-635](../../../ai_workflows/workflows/_dispatch.py#L625-L635)) and double-failure hard-stop ([_dispatch.py:646-657](../../../ai_workflows/workflows/_dispatch.py#L646-L657)). Any real `"aborted"` return would raise a pydantic validation error at the MCP boundary before the client ever sees the status. Same bug on `ResumeRunOutput.status` ([schemas.py:119](../../../ai_workflows/mcp/schemas.py#L119)) for the resume-side ollama abort ([_dispatch.py:867-876](../../../ai_workflows/workflows/_dispatch.py#L867-L876)). | Add `"aborted"` to both `RunWorkflowOutput.status` and `ResumeRunOutput.status` Literal unions. Document the two dispatch triggers. One new hermetic MCP test asserts the `aborted` shape round-trips through the schema without a pydantic error. |
| **D** | Exit criterion 4 of the milestone README names `"gate_rejected"` as a plan-populated status on both output models. | Only `ResumeRunOutput` has `"gate_rejected"` in its Literal. `RunWorkflowOutput` cannot emit `gate_rejected` — a fresh `run_workflow` only ever yields `pending` (gate) / `completed` / `aborted` / `errored`. `gate_rejected` is strictly a resume-side terminal. | Split the docstrings: `RunWorkflowOutput.plan` is populated on `status="pending", awaiting="gate"` (in-flight draft) and `status="completed"` (terminal). `ResumeRunOutput.plan` is populated on `status="pending"` (another gate fired; gate_context also populated), `status="completed"` (terminal), and `status="gate_rejected"` (last-draft-before-rejection, for audit). |
| **E** | `gate_context.checkpoint_ts` needs a value; no source specified. | — | `checkpoint_ts = datetime.now(UTC).isoformat()` stamped at projection time (matches the pattern the surrounding helpers already use for `finished_at`). The value is the time the MCP client received the projection, not the time the graph checkpointed — good enough for operator triage; documented as such in the field description so it is not mistaken for the checkpoint's own recorded timestamp (which LangGraph owns and is not part of this surface). |

### Gaps absorbed (from the same evaluation)

- **Gap 1 — plan at `status="gate_rejected"`.** Milestone README exit criterion 4 calls for last-draft plan availability at rejected terminals (for audit). `_build_resume_result_from_final`'s rejected branch ([_dispatch.py:889-903](../../../ai_workflows/workflows/_dispatch.py#L889-L903)) currently returns `plan=None`. With the projection in place, this branch must dump `final.get("plan")` the same way the `completed` branch does. `gate_context` stays `None` at `gate_rejected` — the gate transition has already happened, so there is no pending prompt to surface.
- **Gap 2 — skill-shape test.** `tests/skill/` has frontmatter + doc-link tests today. A new hermetic assertion that `.claude/skills/ai-workflows/SKILL.md` names both `plan` and `gate_context.gate_prompt` in its pending-flow section keeps the skill text honest against the new MCP surface. Landing spot: extend [`tests/skill/test_skill_frontmatter.py`](../../../tests/skill/test_skill_frontmatter.py) with one new test, or create `tests/skill/test_skill_gate_review.py` — Builder's call based on file length.

## Deliverables

### [ai_workflows/mcp/schemas.py](../../../ai_workflows/mcp/schemas.py) — output models

- **`RunWorkflowOutput`.**
  - Extend `status` Literal from `["pending", "completed", "errored"]` to `["pending", "completed", "aborted", "errored"]`. (Issue C.)
  - Rewrite the class docstring. Remove `"plan is populated only on 'completed'"`. Add: `plan` is populated on `status="completed"` (terminal artefact) and on `status="pending"` when `awaiting="gate"` (in-flight draft); `None` on `"aborted"` and `"errored"`.
  - Document `"aborted"` as the status dispatch returns when the ollama-fallback gate resolved to ABORT or the double-failure hard-stop fired; `error` carries the distinguishing message.
  - Add a new field:

    ```python
    gate_context: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Populated iff status='pending' and awaiting='gate'. Keys "
            "at M11: 'gate_prompt' (str, the prompt the HumanGate "
            "recorded), 'gate_id' (str, the gate identifier), "
            "'workflow_id' (str), 'checkpoint_ts' (str, ISO-8601 "
            "stamp at projection time — not the checkpointer's own "
            "timestamp). Forward-compat: M12 will extend this dict "
            "with cascade-transcript keys (audit_verdict, "
            "audit_reasons, suggested_approach) without a schema "
            "break."
        ),
    )
    ```

- **`ResumeRunOutput`.**
  - Extend `status` Literal from `["pending", "completed", "gate_rejected", "errored"]` to `["pending", "completed", "gate_rejected", "aborted", "errored"]`. (Issue C.)
  - Add `awaiting: Literal["gate"] | None = None` field (mirrors `RunWorkflowOutput.awaiting`). This closes a pre-existing asymmetry — resume can return `status="pending"` when another gate fires, and the caller should be able to tell what is being awaited by the same key as on the run-side. Populated iff `status="pending"`; `None` on every other terminal. (Issue D fallout.)
  - Rewrite the class docstring. `plan` is populated on `status="completed"` (terminal artefact), `status="pending"` (re-gated draft, alongside `gate_context`), and `status="gate_rejected"` (last-draft-before-rejection, for audit; `gate_context` is `None` because the gate has already resolved).
  - Add the same `gate_context` field with identical shape and population rule as on `RunWorkflowOutput`.
- **No change to `RunWorkflowInput` / `ResumeRunInput` / `RunSummary` / `ListRunsInput` / `CancelRunInput` / `CancelRunOutput`.** Input shapes and the other surfaces are unaffected.

### [ai_workflows/workflows/_dispatch.py](../../../ai_workflows/workflows/_dispatch.py) — projection helpers

Two helpers grow the projection. No new function signature; no new collaborator on either helper's parameter list.

#### `_build_result_from_final` ([_dispatch.py:567-691](../../../ai_workflows/workflows/_dispatch.py#L567-L691))

- **Interrupt branch ([L601-610](../../../ai_workflows/workflows/_dispatch.py#L601-L610)).** Today returns `{plan: None, ...}`. Change:
  1. Extract the interrupt payload: `interrupts = final["__interrupt__"]; payload = interrupts[0].value if interrupts else {}`. Defensive `.get(...)` everywhere — if the tuple is unexpectedly empty or the payload key is missing, fall back to `"<gate prompt not recorded>"` and log a `structlog` warning but do not raise.
  2. Dump `final.get("plan")` via the same `model_dump() if hasattr(plan, "model_dump") else (dict(plan) if plan else None)` pattern the completed branch already uses ([L661-664](../../../ai_workflows/workflows/_dispatch.py#L661-L664)). Factor the five-line dump into a private module-level `_dump_plan(plan) -> dict | None` helper so both this branch, the completed branch, the resume interrupt branch, the resume completed branch, and the new resume gate_rejected branch all share one implementation.
  3. Build `gate_context = {"gate_prompt": payload.get("prompt", "<gate prompt not recorded>"), "gate_id": payload.get("gate_id", "<unknown>"), "workflow_id": <workflow arg>, "checkpoint_ts": datetime.now(UTC).isoformat()}`. The `workflow` string is not currently a parameter of `_build_result_from_final` — thread it through: add `workflow: str` to the helper signature; call sites ([L556-562](../../../ai_workflows/workflows/_dispatch.py#L556-L562) and the resume variant) pass `workflow=workflow` from the enclosing scope.
  4. Return the new dict with `plan=_dump_plan(final.get("plan"))`, `awaiting="gate"`, `gate_context=<as above>`, `total_cost_usd=total`, `error=None`, `status="pending"`, `run_id=run_id`.
- **`ollama_fallback_aborted` branch ([L612-635](../../../ai_workflows/workflows/_dispatch.py#L612-L635)) and `hard_stop_failing_slice_ids` branch ([L637-657](../../../ai_workflows/workflows/_dispatch.py#L637-L657)).** Shape unchanged — still `plan=None`. Add `gate_context=None` to both return dicts (keyword-parity with the new field).
- **Completed branch ([L659-672](../../../ai_workflows/workflows/_dispatch.py#L659-L672)).** Replace the inline plan-dump with `plan=_dump_plan(final.get("plan"))`. Add `gate_context=None` to the return dict.
- **Errored branches ([L674-691](../../../ai_workflows/workflows/_dispatch.py#L674-L691)).** Add `gate_context=None` to both return dicts.
- **Dispatch-level exception branch ([L546-554](../../../ai_workflows/workflows/_dispatch.py#L546-L554)).** Add `gate_context=None` to the return dict. (This path lives in `run_workflow`, not in `_build_result_from_final`; edit it directly.)

#### `_build_resume_result_from_final` ([_dispatch.py:802-937](../../../ai_workflows/workflows/_dispatch.py#L802-L937))

Same structural shape as the run-side helper.

- **Interrupt branch ([L845-853](../../../ai_workflows/workflows/_dispatch.py#L845-L853)).** Extract `payload` from `final["__interrupt__"][0].value`. Dump the plan via `_dump_plan`. Build `gate_context` identical to the run-side version. Return with `awaiting="gate"` (new field on ResumeRunOutput), `plan=_dump_plan(final.get("plan"))`, `gate_context=<built above>`. Thread `workflow: str` through this helper too; call site ([L789-794](../../../ai_workflows/workflows/_dispatch.py#L789-L794)) already has `workflow` in scope.
- **`ollama_fallback_aborted` branch ([L855-876](../../../ai_workflows/workflows/_dispatch.py#L855-L876)).** Add `gate_context=None` and `awaiting=None` to the return dict.
- **Rejected branch ([L889-903](../../../ai_workflows/workflows/_dispatch.py#L889-L903)).** (Gap 1.) Change `plan: None` to `plan=_dump_plan(final.get("plan"))` — surface the last-draft plan for audit. Keep `gate_context=None` (gate has resolved, no pending prompt). Add `awaiting=None`.
- **Completed branch ([L905-920](../../../ai_workflows/workflows/_dispatch.py#L905-L920)).** Replace inline plan-dump with `_dump_plan(final.get("plan"))`. Add `gate_context=None`, `awaiting=None`.
- **Errored branches ([L922-937](../../../ai_workflows/workflows/_dispatch.py#L922-L937)).** Add `gate_context=None`, `awaiting=None` to both return dicts.

#### Shared helper

Add at module scope, above `_build_result_from_final`:

```python
def _dump_plan(plan: Any) -> dict[str, Any] | None:
    """Serialise an in-flight or terminal plan for transport.

    Accepts a pydantic model (``.model_dump()``), a mapping
    (``dict(plan)``), or ``None``. Returns ``None`` when the plan is
    unset so the MCP output field stays strictly-optional. Shared
    between the run and resume helpers so the pending/completed/
    gate_rejected branches cannot drift in what they emit.
    """
    if plan is None:
        return None
    if hasattr(plan, "model_dump"):
        return plan.model_dump()
    return dict(plan)
```

### Symmetry guard — `server.py` unaffected

[`ai_workflows/mcp/server.py`](../../../ai_workflows/mcp/server.py) does nothing more than `RunWorkflowOutput(**result)` / `ResumeRunOutput(**result)` at the tool-function boundary. Once `_dispatch` returns the new keys, the server-side wrap picks them up automatically — **no edit to `server.py`**. Confirmed against [server.py:163](../../../ai_workflows/mcp/server.py#L163) and [server.py:184](../../../ai_workflows/mcp/server.py#L184).

### [.claude/skills/ai-workflows/SKILL.md](../../../.claude/skills/ai-workflows/SKILL.md)

Update the "When the MCP tool returns `status='pending'`" section. Current wording (post-M9): *"Surface the pending status to the user and ask how to resume."* New wording: *"Read the `plan` and `gate_context.gate_prompt` from the response. Surface the **plan body** to the user verbatim, quote the gate prompt, and ask for `approved` or `rejected`. Pass their choice as `gate_response` to `resume_run`."*

### [design_docs/phases/milestone_9_skill/skill_install.md §4 Smoke](../milestone_9_skill/skill_install.md) — smoke update

The `§4 Smoke` walkthrough's expected output at step 3 ("gate pause") currently shows `plan: null`. Update the expected-output snippet to show a non-null plan and a populated `gate_context`. Doc-accuracy fix — `tests/skill/test_doc_links.py::test_skill_install_doc_links_resolve` covers link resolution; the new tests below cover the output-shape contract + skill-text contract.

### Tests

#### [tests/mcp/test_gate_pause_projection.py](../../../tests/mcp/test_gate_pause_projection.py) — new

Fixtures mirror `tests/mcp/test_run_workflow.py` / `test_resume_run.py` patterns — autouse `_redirect_default_paths` for tmp storage + checkpoint; same stub tier adapter pattern as those tests.

Four hermetic tests:

1. **`test_run_workflow_gate_pause_projects_plan_and_gate_context`** — drive `run_workflow(planner, goal='x')` with a stub adapter that produces a valid `PlannerPlan`. Assert `RunWorkflowOutput`:
   - `status == "pending"`
   - `awaiting == "gate"`
   - `plan` is a non-null dict with key `steps` (the top-level `PlannerPlan` schema key)
   - `gate_context` is a non-null dict with keys `gate_prompt` (str, non-empty), `gate_id` (str == `"plan_review"`), `workflow_id` (str == `"planner"`), `checkpoint_ts` (str, parseable as ISO-8601).
2. **`test_resume_run_regate_projects_plan_and_gate_context`** — use `slice_refactor` (has two gates — `planner_review` + `slice_refactor_review`). `run_workflow` pauses at gate 1; `resume_run(approved)` pauses at gate 2. Assert `ResumeRunOutput`:
   - `status == "pending"`, `awaiting == "gate"`
   - `plan` non-null, `gate_context` non-null with `gate_id == "slice_refactor_review"`.
3. **`test_completed_status_has_null_gate_context_and_matches_m4_plan_shape`** — drive a workflow to completion (approve every gate); assert:
   - `status == "completed"`, `awaiting is None`, `gate_context is None`
   - `plan` shape is byte-identical to the M4-era shape (regression guard). Compare against a golden dict (stub produces a deterministic plan).
4. **`test_gate_rejected_preserves_last_draft_plan`** — run + resume with `gate_response="rejected"` on the terminal gate; assert `ResumeRunOutput`:
   - `status == "gate_rejected"`, `plan` is non-null (last-draft), `gate_context is None`, `awaiting is None`.

#### [tests/mcp/test_aborted_status_roundtrip.py](../../../tests/mcp/test_aborted_status_roundtrip.py) — new (Issue C)

One hermetic test:

- **`test_aborted_status_does_not_raise_validation_error`** — construct a raw dispatch-return dict with `status="aborted"`, `plan=None`, `gate_context=None`, `error="ollama_fallback: operator aborted run at the circuit-breaker gate"` and any other required fields; assert `RunWorkflowOutput(**raw)` and `ResumeRunOutput(**raw_resume)` both instantiate without `pydantic.ValidationError`. Pre-M11 this would have raised; the test locks the fix.

A fuller integration test that actually drives the ollama-fallback abort through the full dispatch path is unnecessary — the pydantic validation is what the schema enforces, and the existing `tests/workflows/test_*_ollama_fallback.py` suite already exercises the dispatch triggers.

#### Skill-text contract test (Gap 2)

Extend [`tests/skill/test_skill_frontmatter.py`](../../../tests/skill/test_skill_frontmatter.py) (or add a new `tests/skill/test_skill_gate_review.py` if the frontmatter file is already long). One new test:

- **`test_skill_names_plan_and_gate_prompt_in_pending_flow`** — load `.claude/skills/ai-workflows/SKILL.md`, locate the pending-status section (grep for a known header the section uses — e.g. `"pending"` or `"gate_response"`), assert the section text contains both `plan` and `gate_context.gate_prompt`. Non-pinning on exact wording; just enforces that the fields are named.

### [CHANGELOG.md](../../../CHANGELOG.md)

Under `## [Unreleased]`, add a `### Changed — M11 Task 01: MCP gate-pause projection (YYYY-MM-DD)` entry. List files touched, ACs satisfied, and name ISS-02 as the driver (back-link to M9 T04 issue file). Explicitly note the `status="aborted"` schema fix as a pre-existing latent bug that the task absorbed (Issue C).

## Acceptance Criteria

- [ ] `RunWorkflowOutput.status` Literal includes `"aborted"`. `ResumeRunOutput.status` Literal includes `"aborted"`. Regression test (`test_aborted_status_does_not_raise_validation_error`) green.
- [ ] `ResumeRunOutput.awaiting: Literal["gate"] | None = None` added, mirrors `RunWorkflowOutput.awaiting`. Populated iff `status="pending"`; `None` elsewhere.
- [ ] `RunWorkflowOutput.plan` is non-null on `status="pending", awaiting="gate"` for the `planner` workflow. `gate_context` is a dict with `gate_prompt` (str, non-empty), `gate_id` (str), `workflow_id` (str), `checkpoint_ts` (ISO-8601 str).
- [ ] `ResumeRunOutput.plan` and `.gate_context` mirror the above on re-gate resume (tested against `slice_refactor`, which has two gates).
- [ ] `ResumeRunOutput.plan` is non-null on `status="gate_rejected"` (last-draft for audit). `gate_context` is `None` on that path.
- [ ] Schema docstrings on both output models rewritten. Zero `"only on completed"` text. Describe: `plan` population rule per-status; `gate_context` forward-compat shape; `aborted` meaning.
- [ ] Non-gate paths unchanged in shape for the existing clients: `status="completed"` returns `plan` byte-identical to the M4-era dump (golden-value regression test), `gate_context=None`, `awaiting=None`; `status="errored"` returns `plan=None, gate_context=None`; `status="aborted"` returns `plan=None, gate_context=None`.
- [ ] `_dump_plan` helper added to `workflows/_dispatch.py` at module scope; all five branches (two interrupt, two completed, one rejected) route through it.
- [ ] `workflow: str` threaded through both `_build_*_from_final` helpers.
- [ ] `.claude/skills/ai-workflows/SKILL.md` updated to name `plan` and `gate_context.gate_prompt` in the pending-flow section. Skill-text test green.
- [ ] `skill_install.md §4 Smoke` expected-output snippet refreshed; existing link tests stay green.
- [ ] Five new tests land and pass (four in `tests/mcp/test_gate_pause_projection.py`, one in `tests/mcp/test_aborted_status_roundtrip.py`, plus one skill-text test under `tests/skill/`).
- [ ] `uv run pytest` + `uv run lint-imports` (4 contracts kept — no new layer contract) + `uv run ruff check` all clean.
- [ ] CHANGELOG entry under `[Unreleased]` lists files + ACs + ISS-02 driver + the `status="aborted"` latent-bug absorption note.
- [ ] [M9 T04 issue file ISS-02](../milestone_9_skill/issues/task_04_issue.md) flipped `OPEN` → `RESOLVED (M11 T01 <sha>)` with back-link; propagation footer updated.

## Dependencies

- **M9 T04 ISS-02** (this task is the closure).
- No workflow code change; the existing `planner` / `slice_refactor` already stamp `plan` into state at the gate pause, and `HumanGate` already emits the prompt via the LangGraph interrupt payload. M11 reads; does not write.

## Out of scope (explicit)

- **No new MCP tool or resource.** Projection fits inside the existing output models.
- **No workflow change.** `planner` / `slice_refactor` source unchanged.
- **No checkpoint format change.** Projection reads existing state channels + interrupt payload (KDR-009).
- **No gate-timeout change.** `strict_review` semantics (KDR-008) unchanged.
- **No M12 cascade work.** Cascade transcript keys in `gate_context` are an M12 additive change against the forward-compat field this task lands.
- **No new Storage method.** Prompt is read from the LangGraph interrupt payload, not via a new `storage.get_gate(run_id)` surface. A storage-side read would duplicate the write `record_gate` already performs with zero new reader value — the payload is already in `final`.
- **No CLI-surface change.** `aiw run` / `aiw resume` do not currently surface the draft plan at gate pause either, but the CLI has always been a lower-fidelity surface than the MCP one (its gate-pause output is a human-readable line, not a structured dict). The M9 T04 issue was specifically about the MCP + skill surface; CLI parity is forward-deferrable.

## Propagation status

Filled in at audit time. ISS-02 resolution back-propagates to the M9 T04 issue file at close-out; no forward carry-over expected unless the audit surfaces a second trigger for a generic state-projection surface (at which point either `nice_to_have.md` or M13+).
