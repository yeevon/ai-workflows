# Milestone 11 — MCP Gate-Review Surface

**Status:** 📝 Planned (drafted 2026-04-21).
**Grounding:** [architecture.md §4.4](../../architecture.md) · [roadmap.md](../../roadmap.md) · [M9 T04 issue file (ISS-02)](../milestone_9_skill/issues/task_04_issue.md) · [ADR-0004](../../adr/0004_tiered_audit_cascade.md) (M12 precondition).

## Why this milestone exists

The M9 T04 close-out live smoke (2026-04-21) fired the first end-to-end flow through the `.claude/skills/ai-workflows/` skill against a fresh Claude Code session. Round-trip worked mechanically (`run_workflow(planner) → pending/gate → resume_run approved → completed`), but the operator's verbatim observation at the gate pause was: *"paused for human gate review but there is nothing for me to check"*.

Root cause is structural, not skill-level. At gate pause the MCP `RunWorkflowOutput` / `ResumeRunOutput` carry `plan: null` by design — [`ai_workflows/mcp/schemas.py:87-90`](../../../ai_workflows/mcp/schemas.py#L87-L90) pins this explicitly: *"`plan` is populated only on `'completed'`"*. There are no sibling `@mcp.resource()` endpoints that could project the in-flight plan either — grep of `ai_workflows/mcp/server.py` returns only four `@mcp.tool()`s. Net effect: the skill hands the operator a gate pause with no artefact. Approving blind completes the round-trip but defeats the KDR-001 *informed* human-review semantic the gate exists for.

M9 is faithful to KDR-002 (packaging-only); the defect sits upstream in the M4 MCP surface and has been there since M4 shipped. M9's live smoke was the first time anyone exercised the full human-facing flow end-to-end, so this is the first milestone that can propagate the fix. M11 closes the gap.

M11 sits after M10 in roadmap order. M10 is independent (Ollama hardening, code-touching in `ai_workflows/workflows/` + `ai_workflows/primitives/`); M11 is a pure `ai_workflows/mcp/` + skill-text surface diff. Either can land first without blocking the other.

M11 is a **precondition for M12** (tiered audit cascade). M12's cascade-failure escalation path routes to a strict `HumanGate` that carries the auditor's rejection reasons + suggested fix + full cascade transcript. That escalation has no user value unless the operator can actually see the transcript at gate pause — which is what M11 fixes.

## Goal

At any MCP-surfaced gate pause (`status="pending"`, `awaiting="gate"` — see [schemas.py:93-94](../../../ai_workflows/mcp/schemas.py#L93-L94)), the caller receives the gate-relevant subset of the graph's current state — minimally the **in-flight draft plan** for the `planner` / `slice_refactor` workflows, plus the **gate prompt text** the `HumanGate` recorded, plus any **cascade transcript** keys the graph state is carrying (M12 forward-compat). Projection is read-only — the checkpointer remains LangGraph-owned; the fix is projection over the checkpointed state, not a new persistence path.

No new MCP tool. No new resource. The existing `RunWorkflowOutput` / `ResumeRunOutput` grow their `plan` field (and any added gate-context field) to be populated at gate pause, not only on terminal completion. Schema docstring is rewritten to reflect the new semantics. Backwards-compat is preserved: on terminal `status="completed"`, `plan` keeps its current shape; the change is strictly additive at `status="pending", awaiting="gate"`.

## Exit criteria

1. `RunWorkflowOutput.plan` and `ResumeRunOutput.plan` are **non-null** whenever `status="pending"` and `awaiting="gate"`, for any workflow whose checkpointed state carries a `plan` channel at the gate pause. Today this applies to `planner` (gate pauses after plan synthesis) and `slice_refactor` (gate pauses after per-slice aggregation with the plan still in state).
2. The MCP output model grows a `gate_context: dict[str, Any] | None = None` field. Populated at `status="pending", awaiting="gate"` with the minimum reviewable subset: `{gate_prompt: str, workflow_id: str, checkpoint_ts: str}` at M11 landing. Field is documented as a forward-compat projection surface — M12 will extend it with cascade-transcript keys. Absent / null on non-gate status.
3. `ai_workflows/mcp/server.py` — the code paths that construct `RunWorkflowOutput` / `ResumeRunOutput` on gate interrupt read the checkpointed state via LangGraph's checkpointer (no new persistence, no new table). Projection is a pure read over `state["plan"]` + the gate-recorded prompt; if the key is absent the projection returns `None` and the output field is `None`.
4. Schema docstrings rewritten. Old text (*"`plan` is populated only on `'completed'`"*) removed. New text names the three populated statuses: `"awaiting"` (gate pause, in-flight draft), `"completed"` (terminal, final artefact), `"gate_rejected"` (terminal — last draft before rejection, for audit).
5. `.claude/skills/ai-workflows/SKILL.md` — the "pending → `resume_run`" flow documented to surface the **draft plan** to the user and quote the gate prompt, not the null projection. Matching smoke text for `skill_install.md §4` (*Smoke*).
6. Hermetic tests under `tests/mcp/` assert:
   (a) A `run_workflow(planner, goal='x')` that hits the gate returns `RunWorkflowOutput` with `status="pending"`, `awaiting="gate"`, and `plan` as a non-null dict with the schema-expected top-level keys.
   (b) `resume_run(run_id, gate_response="approved")` on a run that re-gates (e.g. a multi-gate workflow) returns a `ResumeRunOutput` with `plan` and `gate_context` populated identically.
   (c) A `run_workflow` that hits a *non*-gate status (e.g. `completed` after immediate success, or `errored`) returns `gate_context: None`.
7. End-to-end live-smoke re-run of the M9 T04 scenario (fresh Claude Code session → skill → `run_workflow(planner, goal='Write a release checklist')` → gate pause → operator sees the draft plan inline → approve → completed). Pass/fail recorded in the M11 T02 CHANGELOG close-out block with commit sha baseline.
8. M9 T04 issue file flipped: ISS-02 `OPEN → RESOLVED (M11 T01 sha)` with a back-link.
9. Gates green: `uv run pytest` + `uv run lint-imports` (4 contracts kept — no new layer contract at M11) + `uv run ruff check`.

## Non-goals

- **No new MCP tool / resource.** The projection fits inside the existing `RunWorkflowOutput` / `ResumeRunOutput` shape. A new `get_run_state` tool or `aiw://runs/<id>/state` resource is a larger surface addition whose trigger has not fired — the gate-pause case is the concrete need; a generic state-projection surface can be promoted later (`nice_to_have.md` entry if M12 or M13 shows a second trigger).
- **No checkpoint-format change.** LangGraph owns checkpoint persistence (KDR-009). The projection reads the existing state channel; no new field is persisted.
- **No workflow change.** `planner` / `slice_refactor` already write their plan into a state key that the checkpointer captures; M11 is purely about surfacing that key through the MCP boundary.
- **No cascade work.** `AuditCascadeNode`, auditor tiers, `run_audit_cascade` MCP tool, and the per-workflow `audit_cascade_enabled` opt-in all land at M12. M11 adds the `gate_context` field in a forward-compat shape so M12 can extend it without a schema break, nothing more.
- **No gate-timeout change.** `strict_review` semantics (KDR-008.3) unchanged.

## Key decisions in effect

| Decision | Reference |
| --- | --- |
| MCP tool schemas are the public contract; additive changes (new fields) are non-breaking | architecture.md §7 + KDR-008 |
| Checkpoint format is LangGraph-owned; projection over it is read-only | KDR-009 |
| Skill is packaging-only over the MCP surface | KDR-002 |
| No new KDR at M11 | CLAUDE.md non-negotiables |

## Task order

| # | Task | Kind |
| --- | --- | --- |
| 01 | [MCP gate-pause projection — schemas + server + tests + skill text](task_01_gate_pause_projection.md) | code + test + doc |
| 02 | [Milestone close-out](task_02_milestone_closeout.md) | doc |

Per-task spec files land when the milestone is promoted from `📝 Planned` to active. T01 is spec'd below; T02 is written at T01's close-out so the scope stays calibrated against landed surface.

## Carry-over from prior milestones

- **[M9 T04 ISS-02 🔴 HIGH](../milestone_9_skill/issues/task_04_issue.md)** — propagated here as the driver of T01. When T01 lands, the M9 T04 issue file flips ISS-02 → `RESOLVED (M11 T01 sha)` with a back-link.

## Propagation status

Filled in at audit time. The only forward-deferral candidate is a generic state-projection surface (new tool or resource) if a second trigger fires post-M11 — at that point either a `nice_to_have.md` entry or an M13+ milestone, not an M11-internal deliverable.

## Issues

Land under [issues/](issues/) after each task's first audit.
