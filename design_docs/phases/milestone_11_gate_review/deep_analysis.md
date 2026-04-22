# Milestone 11 — Post-T01 deep analysis

**Performed on:** 2026-04-22.
**Scope:** M11 T01 implementation review — design drift against [architecture.md](../../architecture.md) + cited KDRs, alignment with M1–M9, forward-compat surface for M12, [nice_to_have.md](../../nice_to_have.md) trigger sweep. T02 (milestone close-out) is still pending per the [M11 README task-order](README.md) — the full milestone deep-analysis runs at T02 close-out. This pass covers the landed T01 surface only.
**Inputs:** [task_01_gate_pause_projection.md](task_01_gate_pause_projection.md) + [issues/task_01_issue.md](issues/task_01_issue.md); [ai_workflows/mcp/schemas.py](../../../ai_workflows/mcp/schemas.py); [ai_workflows/workflows/_dispatch.py](../../../ai_workflows/workflows/_dispatch.py); [ai_workflows/graph/human_gate.py](../../../ai_workflows/graph/human_gate.py); [.claude/skills/ai-workflows/SKILL.md](../../../.claude/skills/ai-workflows/SKILL.md); [skill_install.md](../milestone_9_skill/skill_install.md); [CHANGELOG.md](../../../CHANGELOG.md); every M11-cited KDR (KDR-001, KDR-002, KDR-003, KDR-004, KDR-008, KDR-009); [architecture.md §4.4 / §7 / §9](../../architecture.md); [M9 T04 issue file](../milestone_9_skill/issues/task_04_issue.md); [M9 deep analysis](../milestone_9_skill/deep_analysis.md); [M12 README](../milestone_12_audit_cascade/README.md); [ADR-0004](../../adr/0004_tiered_audit_cascade.md); [nice_to_have.md](../../nice_to_have.md); [roadmap.md](../../roadmap.md).

This pass mirrors the [M9 post-close-out deep-analysis](../milestone_9_skill/deep_analysis.md) pattern — a synthesis step run after the `/clean-implement` loop closes, whose job is to surface drift and alignment concerns the mechanical AC-grading audit would not catch. T01 is a code-touching task (schemas + dispatch + tests + doc), so this pass runs at T01 close rather than waiting for the full milestone close-out.

## TL;DR

M11 T01 is **architecturally clean** and **forward-compatible with M12**. All 15 ACs met (see [Cycle 2 audit verdict](issues/task_01_issue.md)). Every canonical drift probe comes back clean — no new dependency, no new module, no layer change, no checkpoint-format change, no new observability backend, KDR-003 preserved, KDR-008 additive-only contract honoured, KDR-009 checkpointer left LangGraph-owned. **One LOW doc-drift finding** against [architecture.md §4.4 line 106](../../architecture.md#L106): the line was drafted during M9 T04's forward-deferral (2026-04-21) using `status="awaiting"`, but the landed schema uses `status="pending"` + `awaiting="gate"` (two separate fields). A one-word doc fix closes it. No `nice_to_have.md` trigger fired. No new carry-over to M12 beyond what's already pinned in the M12 README.

## 1. Drift check

Cross-reference against [architecture.md](../../architecture.md) (§3 layer contract, §4.4 MCP surface, §6 dependencies, §7 boundaries, §9 KDRs) and every KDR T01 cites.

| Concern | Finding |
| --- | --- |
| New dependency | None. `pyproject.toml` diff against `main` is empty. The structlog import added in Cycle 2 uses an already-declared dep ([`pyproject.toml:21`](../../../pyproject.toml#L21) `structlog>=24.0`). |
| New `ai_workflows.*` module | None. Code edits confined to two existing files — `ai_workflows/mcp/schemas.py` (output model field additions, docstring rewrites) and `ai_workflows/workflows/_dispatch.py` (two new private module-scope helpers, `_dump_plan` + `_extract_gate_context`; signature extension on both `_build_*_from_final` helpers). |
| New layer / contract | None. `uv run lint-imports` reports 4 contracts kept, 0 broken. No new cross-file dependency that would warrant a fifth contract — the new helpers are module-private and both callers live in the same file. |
| LLM call added | None. M11 T01 is pure projection over state already written by `TieredNode` / `HumanGate`. No new `TieredNode` or `ValidatorNode` invocation ⇒ KDR-004 not engaged. |
| Checkpoint / resume logic added | None. The projection reads `final["__interrupt__"][0].value` — LangGraph's native interrupt-payload surface (cross-verified against [`ai_workflows/graph/human_gate.py:99-115`](../../../ai_workflows/graph/human_gate.py#L99-L115)). Zero hand-rolled checkpoint writes. KDR-009 preserved. |
| Retry logic | None. `wrap_with_error_handler` + `NonRetryable` machinery untouched. |
| Observability backend added | None. The structlog warnings (Cycle 2 ISS-03 fix — `mcp_gate_context_malformed_payload` + `mcp_gate_context_missing_interrupt`) emit through the existing in-project `StructuredLogger` frame per KDR-004 / §8.1. No Langfuse / OTel / LangSmith dependency pulled in. Never-fires-in-practice defensive path — no test asserts the warning. |
| KDR-002 (packaging-only skill) | Honoured. `.claude/skills/ai-workflows/SKILL.md` edits describe the new wire shape verbatim; the skill stays recipe-card-only with every action resolving to an MCP tool call. |
| KDR-003 (no Anthropic API) | Preserved. `grep -rn 'ANTHROPIC_API_KEY\|import anthropic\|anthropic.com/api'` over `ai_workflows/**/*.py` returns zero matches. Pre-existing guardrail tests (`test_mcp_server_module_does_not_read_provider_secrets` + skill-text shape tests) stay green. |
| KDR-008 (MCP schemas = public contract, additive = non-breaking) | Honoured. `gate_context` is a new optional field with default `None`; `awaiting` on `ResumeRunOutput` is new optional default `None`; `"aborted"` on both `status` Literals is an additive Literal member. A pre-M11 caller that ignored the new fields keeps working; an M11-aware caller reads the gate-review payload. The only semantic tightening is `plan` on `status="pending"` — previously always `None`, now populated — which is a *fix* to a null projection no caller could have relied on (the M9 T04 live smoke was the first exercise of that path). |
| KDR-009 (LangGraph-owned checkpointer) | Preserved. No new state channel written. No new table. No hand-rolled persistence. The projection is a pure read over `final["__interrupt__"][0].value` + `final.get("plan")` — both already in LangGraph state at gate pause. |
| Four-layer contract | Preserved. `mcp/schemas.py` stays in the `mcp` surface; `workflows/_dispatch.py` stays in the workflow surface layer; no primitive-layer leakage. |

No HIGH drift. No MEDIUM drift. One LOW doc-accuracy drift — see §3 below.

## 2. Implementation alignment with M1–M9

| Milestone | M11 T01's relationship | Verdict |
| --- | --- | --- |
| M1 (primitives baseline) | No primitive-layer change. M11 reads through the existing `SQLiteStorage` via `_dispatch` helpers — no new storage surface. | Aligned. |
| M2 (graph-layer adapters) | M11 reads from `HumanGate`'s interrupt payload (M2 surface) without modifying the gate. The payload shape (`{gate_id, prompt, strict_review, timeout_s, default_response_on_timeout}`) is documented in [`human_gate.py:99-115`](../../../ai_workflows/graph/human_gate.py#L99-L115) and M11 reads two keys (`gate_id`, `prompt`) via `dict.get(...)` with documented defaults. | Aligned. |
| M3 (planner workflow) | `planner` already stamps `plan: PlannerPlan` into state at the gate pause; M11 surfaces that state key through the MCP wire. No planner workflow change. The hermetic `test_run_workflow_gate_pause_projects_plan_and_gate_context` test in [`tests/mcp/test_gate_pause_projection.py`](../../../tests/mcp/test_gate_pause_projection.py) drives the planner end-to-end via `run_workflow` and asserts the projection. | Aligned. |
| M4 (MCP surface) | **M11 T01 sits directly on M4.** `RunWorkflowOutput` / `ResumeRunOutput` grew their `plan` and `gate_context` rules additively. Every existing M4 test stays green (13 collateral test edits were pure contract propagation — workflow kwarg + `plan is None` → `plan is not None` on interrupt / rejected branches; zero drive-by scope). | Aligned (with doc-accuracy note — see §3). |
| M5 (multi-tier planner) | No workflow change. The multi-tier explorer → planner sub-graph still pauses once at `planner_review` and the plan dump is unchanged on `status="completed"` (byte-identical golden-value regression test). `tier_overrides` untouched. | Aligned. |
| M6 (slice_refactor DAG) | `slice_refactor` already writes the plan into state; M11 surfaces it at the `planner_review` pause AND at the strict-review `slice_refactor_review` pause (verified by `test_resume_run_regate_projects_plan_and_gate_context`). The double-failure hard-stop and in-flight `cancel_run` paths are untouched — the new `"aborted"` literal on `status` absorbs the pre-existing M6/M8 abort path that `RunWorkflowOutput` / `ResumeRunOutput` already emitted at the wire level. | Aligned. |
| M7 (evals) | M7 `EvalRunner` / `CaptureCallback` paths unchanged. The schema field growth flows through pydantic `model_dump()` without reshaping captured fixtures. | Aligned. |
| M8 (Ollama circuit breaker + fallback gate) | The Ollama fallback gate now surfaces a populated `plan` + `gate_context` at its pause (it's a `HumanGate` internally). The skill text in [`SKILL.md:103-122`](../../../.claude/skills/ai-workflows/SKILL.md) retained M9's fallback-gate paragraph, which now accurately describes the wire shape the operator will see. | Aligned. |
| M9 (skill packaging) | **M11 T01 is the closure for M9 T04 ISS-02.** The skill text was rewritten to surface `plan` + `gate_context.gate_prompt` verbatim in the pending-flow section, closing the *"paused for human gate review but there is nothing for me to check"* operator observation. [M9 T04 issue file](../milestone_9_skill/issues/task_04_issue.md) ISS-02 flipped `DEFERRED → RESOLVED (M11 T01 f3b3a6a)` on all five pointers (status line, subsection heading, detail block, Issue-log row, Propagation-status footer). | Aligned. |

No alignment breaks. M11 T01 is a faithful additive projection.

## 3. Spec drift surfaced during M11 T01 (recap + one new finding)

### 3.1 Recap — in-task deviations closed in Cycle 2

The `/clean-implement` loop ran two cycles and closed three issues in Cycle 2; a fourth was CLOSED as Builder-discretion in Cycle 1. Full AC grading and per-issue narrative lives in [issues/task_01_issue.md](issues/task_01_issue.md). One-line recap per issue:

| ID | Severity | Final status | Summary |
| --- | --- | --- | --- |
| M11-T01-ISS-01 | 🟡 MEDIUM (book-keeping) | ✅ RESOLVED (Cycle 2) | M9 T04 ISS-02 `RESOLVED` flip + propagation footer update landed; five-pointer edit with literal `<sha>` placeholder (commit-making turn substitutes actual SHA). |
| M11-T01-ISS-02 | 🟢 LOW | ✅ RESOLVED (Cycle 2) | Spec AC-12 bullet `"Five new tests"` → `"Six new tests"` — matches the 4 + 1 + 1 itemisation. |
| M11-T01-ISS-03 | 🟢 LOW | ✅ RESOLVED (Cycle 2) | `_extract_gate_context` defensive branches now emit `_LOG.warning(...)` per spec; `structlog` import + module-level `_LOG` binding added. Never-fires-in-practice; no test asserts the warning. |
| M11-T01-ISS-04 | 🟢 LOW (Builder discretion) | CLOSED (note only) | Gap-2 skill-text test landed in `tests/skill/test_skill_md_shape.py` instead of spec-named `test_skill_frontmatter.py` / `test_skill_gate_review.py`. Reasonable landing-spot choice; no action. |

All four are in-task; none forward-deferred to a future milestone.

### 3.2 New finding — [architecture.md §4.4 line 106](../../architecture.md#L106) doc-accuracy drift

**Severity:** 🟢 LOW (doc-only; no functional impact).

**Finding.** The M11 projection bullet added to [architecture.md §4.4](../../architecture.md) during the M9 T04 forward-deferral (2026-04-21) reads:

> *(Gate-review projection, M11)* — `RunWorkflowOutput.plan` / `ResumeRunOutput.plan` carry the in-flight draft plan at `status="awaiting", awaiting="gate"`, not only on `status="completed"`.

The landed schema uses `status="pending"` (not `"awaiting"`) with `awaiting="gate"` as a separate `Literal["gate"] | None` field. Verified against [`ai_workflows/mcp/schemas.py:108-109`](../../../ai_workflows/mcp/schemas.py#L108-L109) + [`:171-172`](../../../ai_workflows/mcp/schemas.py#L171-L172):

```python
status: Literal["pending", "completed", "aborted", "errored"]
awaiting: Literal["gate"] | None = None
```

The architecture.md line was drafted *before* T01 started and the pre-existing M4-era `status` Literal (`"pending"`, not `"awaiting"`) was the wire shape both then and now. The drafting typo has no functional consequence — the schema contract lives in `schemas.py`, and both the task spec + the Cycle 2 audit verified the landed shape — but the architecture grounding doc should match the implementation. A future Builder reading §4.4 for grounding would be mildly misled.

**Action / Recommendation.** One-word doc fix to [architecture.md:106](../../architecture.md#L106): replace `status="awaiting"` with `status="pending"`. The `awaiting="gate"` text after it is already correct. No other edits to §4.4 needed.

**Why LOW, not MEDIUM.** (a) Doc-only; landed implementation is correct. (b) The schema docstring in `schemas.py` (the actual public contract per KDR-008) enumerates the correct `status` Literal explicitly. (c) The task spec + every landed test uses the correct `status="pending"`. (d) No caller could be misled into writing broken code against `status="awaiting"` — pydantic would reject it at schema validation time. The finding is pure grounding-doc hygiene.

## 4. Unresolved issue disposition

Every M11 T01 audit issue carries a RESOLVED or CLOSED status per §3.1 above. [M9 T04 ISS-02](../milestone_9_skill/issues/task_04_issue.md) flipped `DEFERRED → RESOLVED (M11 T01 f3b3a6a)` on all five pointers in the Cycle 2 Builder pass (stamped at commit `f3b3a6a` per the spec AC-15 shape).

**No open HIGH/MEDIUM. No forward-deferrals from M11 T01 to any future milestone.** The architecture.md drift finding in §3.2 is a one-word edit that should ride the same commit as T01's landing; it does not warrant a new issue file entry (the audit loop is closed, and the deep-analysis pass is the appropriate surface).

## 5. Forward-compat surface for M12

M11 T01's `gate_context` dict was deliberately shaped for additive extension per KDR-008. M12's audit-cascade transcript (see [ADR-0004](../../adr/0004_tiered_audit_cascade.md) + [M12 README T04 exit criterion](../milestone_12_audit_cascade/README.md)) needs to surface `{audit_verdict, audit_reasons, suggested_approach}` at the strict `HumanGate` that fires on cascade-retry exhaustion. Current M11 `gate_context` keys: `{gate_prompt, gate_id, workflow_id, checkpoint_ts}`. M12 can extend the dict with the cascade keys without a schema break — the field is typed `dict[str, Any] | None`, so new keys pass pydantic validation trivially, and an M12-aware caller reading the cascade keys coexists with an M11-era caller reading only the four M11 keys.

Both [M11 T01 schema docstrings](../../../ai_workflows/mcp/schemas.py) explicitly name the M12 forward-compat clause:

> *"Forward-compat: M12 will extend this dict with cascade-transcript keys (audit_verdict, audit_reasons, suggested_approach) without a schema break."*

The [M12 README line 29](../milestone_12_audit_cascade/README.md#L29) reciprocally names M11 as its precondition for the operator-visible cascade transcript. Round-trip verified — no design mismatch.

## 6. [nice_to_have.md](../../nice_to_have.md) trigger sweep

Every nice_to_have entry re-read against the M11 T01 delivered surface. Only entries whose scope brushes against the M11 diff are itemised; the rest were read and untriggered (§§1, 2, 3, 4, 5, 6, 7, 13, 14, 15 — all unchanged by M11).

| § | Entry | Trigger fired by M11 T01? | Action |
| --- | --- | --- | --- |
| 9 | `aiw cost-report <run_id>` — per-run cost breakdown | No. M11 T01 does not touch billing; `total_cost_usd` scalar in the output models remained identical. | None. |
| 10 | OpenTelemetry exporter | No. Structlog warnings stayed on the in-project `StructuredLogger` frame. No backend added. | None. |
| 11 | Prune `CostTracker.by_tier` / `by_model` / `sub_models` | No. M11 T01 added no `CostTracker` consumer; the §11 "why not now" rationale (M12 `by_role` adding a sibling consumer of the rollup idiom) still holds unchanged. | None. |
| 12 | Promote read-only MCP tools to `_dispatch` | **Weak trigger — reconsidered.** M11 T01 added two module-private helpers (`_dump_plan`, `_extract_gate_context`) inside `_dispatch.py` that are now shared between `_build_result_from_final` and `_build_resume_result_from_final`. This is a *workflow-dispatch* helper, not a `list_runs` / `cancel_run` promotion, so it does not directly fire §12's trigger. But it does demonstrate that the `_dispatch.py` module is the right home for cross-surface projection helpers — which is §12's underlying thesis. The trigger for §12 itself (a third surface, or stateful concerns on `list_runs` / `cancel_run`, or CLI/MCP divergence) has **not** fired. | None. The M11 helpers stay scoped to `_dispatch`; no promotion of the read-only tools warranted by this milestone alone. |
| 16 | Centralise env-var documentation | No. M11 T01 added no new env-var. | None. |

**No entry triggered strongly enough to promote. No minor-wording updates warranted by M11 T01 alone** — the §11 + §16 wording updates from the M9 deep analysis still stand; M11 T01 adds no new signal to either.

## 7. Recommendations

Concrete edits. All minor; none warrant a new milestone or task.

1. **[architecture.md:106](../../architecture.md#L106)** — replace `status="awaiting"` with `status="pending"` (see §3.2). One-word edit. Land in the same commit as the M11 T01 deep-analysis / README update so the grounding doc and the implementation land in lockstep.
2. **[README.md](../../../README.md)** — add an M11 T01 landing paragraph to the post-M9 narrative (M11 is still "Planned" at the milestone level until T02 closes, but T01 is a user-visible surface change). Status table: M11 row stays "Planned" — T02 close-out is the promotion point, not T01.
3. **No action** on the CHANGELOG. The existing `[Unreleased]` T01 entry plus its Cycle 2 block is comprehensive; the typical Keep-a-Changelog promotion from `[Unreleased]` to a dated `[M11 ...]` section happens at T02 close-out.
4. **No new milestone or task.** M11 T02 (milestone close-out, already spec'd-to-be-spec'd in the [M11 README task-order](README.md)) owns the live-smoke re-run + milestone-level promotion.
5. **No new `nice_to_have.md` entry.** No structural gap surfaced by M11 T01 maps to a deferred-item shape.

## 8. What this analysis does *not* propose

- **No change to KDR-008** — M11 T01's schema growth is exactly the additive pattern KDR-008 authorises. No re-interpretation needed.
- **No change to KDR-009** — M11 T01 left the checkpointer LangGraph-owned; the projection is read-only over the existing interrupt payload.
- **No `_v2` of the M11 T01 issue file.** All audit updates stayed in-place per CLAUDE.md.
- **No retrospective re-audit of M9 T04.** The ISS-02 flip landed in Cycle 2 of M11 T01's audit loop with back-links in both directions; the M9 T04 audit is closed.
- **No promotion of §12** ([nice_to_have.md](../../nice_to_have.md) — read-only MCP tools to `_dispatch`) — see §6. The M11 helpers are workflow-projection helpers, not `list_runs` / `cancel_run` consolidations.

## 9. Propagation footer

- **[architecture.md §4.4 line 106](../../architecture.md#L106)** — one-word doc fix (§3.2 / §7.1). Lands with this deep-analysis commit.
- **[README.md](../../../README.md)** — post-M9 narrative + M11 row update. Lands with this deep-analysis commit. M11 row stays "Planned" until T02 close-out.
- **[M9 T04 issue file](../milestone_9_skill/issues/task_04_issue.md)** — ISS-02 ✅ RESOLVED via M11 T01 (commit `f3b3a6a`). All five pointers stamped.
- **[M11 T01 issue file](issues/task_01_issue.md)** — closed ✅ PASS Cycle 2/10, CLEAN. No further updates.
- **[M12 README](../milestone_12_audit_cascade/README.md)** — no carry-over from this analysis. M12's dependency on M11 is already captured; the M11 T01 `gate_context` dict shape satisfies M12's forward-compat needs (§5).
- **[M11 T02 spec file]** — not yet authored (per the [M11 README task-order](README.md), T02 is written at T01's close-out). When authored, T02 should carry the live-smoke re-run from the [M11 README exit-criterion 7](README.md#L35) and the milestone-level README + roadmap promotion.

End of analysis.
