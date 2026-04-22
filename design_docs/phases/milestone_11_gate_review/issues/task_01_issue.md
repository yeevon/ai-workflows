# Task 01 — MCP Gate-Pause Projection — Audit Issues

**Source task:** [../task_01_gate_pause_projection.md](../task_01_gate_pause_projection.md)
**Audited on:** 2026-04-22 (Cycle 1), re-audited 2026-04-22 (Cycle 2)
**Audit scope:** `ai_workflows/mcp/schemas.py` (output models); `ai_workflows/workflows/_dispatch.py` (projection helpers `_dump_plan` + `_extract_gate_context`; both `_build_*_from_final` helpers + the two dispatch-level exception branches); `ai_workflows/graph/human_gate.py` (interrupt-payload shape cross-check); `.claude/skills/ai-workflows/SKILL.md` (pending-flow narrative + example); `design_docs/phases/milestone_9_skill/skill_install.md` (§4 smoke snippets); `CHANGELOG.md` (`[Unreleased]` M11 T01 entry); `tests/mcp/test_gate_pause_projection.py` (4 new tests); `tests/mcp/test_aborted_status_roundtrip.py` (1 new test); `tests/skill/test_skill_md_shape.py` (new Gap-2 test); collateral test edits (`tests/mcp/test_run_workflow.py`, `tests/mcp/test_resume_run.py`, `tests/workflows/test_slice_refactor_apply.py`, `tests/workflows/test_slice_refactor_hard_stop.py`, `tests/workflows/test_slice_refactor_strict_gate.py`, `tests/workflows/test_slice_refactor_e2e.py`); `design_docs/architecture.md` + every cited KDR (KDR-001, KDR-002, KDR-003, KDR-004, KDR-008, KDR-009); `pyproject.toml`; `.github/workflows/ci.yml`; the M11 README; the M9 T04 issue file (ISS-02 — driver). **Cycle 2 delta:** re-loaded `ai_workflows/workflows/_dispatch.py` (structlog import + module-level `_LOG` + two defensive-branch warnings in `_extract_gate_context`); the spec's AC-12 bullet (typo fix); the M9 T04 issue file (five-pointer ISS-02 RESOLVED flip); the CHANGELOG Cycle 2 block.
**Status:** ✅ PASS — Cycle 2/10, CLEAN. All three Cycle 1 OPEN issues resolved by Cycle 2 Builder; ISS-04 was already CLOSED (Builder-discretion note). No new drift; all 15 ACs green; gates re-run clean (pytest 602 passed / 5 skipped, lint-imports 4 kept, ruff clean). The `<sha>` placeholders in the M9 T04 issue file + the CHANGELOG are the expected stamp-on-commit shape per spec AC-15; the commit-making turn substitutes the actual SHA.

## Design-drift check

Cross-checked against [architecture.md](../../../architecture.md) + every KDR the task cites. All five canonical drift probes below came back clean.

| Concern | Finding |
| --- | --- |
| **New dependency** | None. `pyproject.toml` diff against `main` is empty — only `stdlib` (`datetime`), `typing`, and already-imported `pydantic.Field` used. |
| **New `ai_workflows.*` module** | None. Edits confined to two existing files (`mcp/schemas.py`, `workflows/_dispatch.py`); one new helper (`_dump_plan`) and one new helper (`_extract_gate_context`) at module scope inside the existing file. |
| **New layer / contract** | None. `uv run lint-imports` reports **4 contracts kept, 0 broken** — primitives / graph / workflows / evals boundaries preserved. |
| **LLM call added** | None. Pure projection over state already written by `TieredNode` / `HumanGate`. No `TieredNode` / `ValidatorNode` invocation added ⇒ KDR-004 not engaged. |
| **Checkpoint / resume logic added** | None. Projection **reads** `final["__interrupt__"][0].value` (LangGraph's native interrupt-payload surface — verified against [`ai_workflows/graph/human_gate.py:99-115`](../../../../ai_workflows/graph/human_gate.py#L99-L115)) — no hand-rolled checkpoint write, no new state channel written. KDR-009 preserved. |
| **Retry logic added** | None. `wrap_with_error_handler` / `NonRetryable` machinery untouched. |
| **Observability backend added** | None. No Langfuse / OTel / LangSmith dependency added. *(See LOW-02 below — the spec called for a `structlog` warning in the defensive fallback path; implementation omitted it. Non-drift — `StructuredLogger` is in-project, not an external backend.)* |
| **KDR-002 (packaging-only) fidelity** | Not applicable to M11 — M11 is a code-touching milestone by design (the M11 README explicitly unblocks this). |
| **KDR-003 (no Anthropic API)** | No `anthropic` import, no `ANTHROPIC_API_KEY` read anywhere in the diff. `mcp/server.py` still clean (already test-guarded by `test_run_workflow.py::test_mcp_server_module_does_not_read_provider_secrets`). |
| **KDR-008 (MCP schemas = public contract, additive changes non-breaking)** | **Honoured.** `gate_context`, `awaiting` (on `ResumeRunOutput`), and `"aborted"` on both `status` Literals are all additive. A pre-M11 caller that ignored `gate_context` / `awaiting` keeps working; an M11-aware caller gets the new payload. The only status that changes meaning is `"pending"` — `plan` is now non-null there instead of null, which tightens the contract for the better (no caller can have relied on the `None` since the M9 T04 live smoke was the first exercise of that path). |

No HIGH drift. No MEDIUM drift.

## Acceptance criteria grading

| # | Criterion | Verdict |
| --- | --- | --- |
| 1 | `RunWorkflowOutput.status` Literal includes `"aborted"`; `ResumeRunOutput.status` Literal includes `"aborted"`; regression test green | ✅ [schemas.py:108](../../../../ai_workflows/mcp/schemas.py#L108) + [schemas.py:171](../../../../ai_workflows/mcp/schemas.py#L171). `test_aborted_status_does_not_raise_validation_error` green under `pytest tests/mcp/test_aborted_status_roundtrip.py`. |
| 2 | `ResumeRunOutput.awaiting: Literal["gate"] \| None = None` added, mirrors `RunWorkflowOutput.awaiting`; populated iff `status="pending"`; `None` elsewhere | ✅ [schemas.py:172](../../../../ai_workflows/mcp/schemas.py#L172). Every non-pending branch in `_build_resume_result_from_final` sets `"awaiting": None` explicitly (interrupt → `"gate"`, every terminal branch → `None`). |
| 3 | `RunWorkflowOutput.plan` non-null on `status="pending", awaiting="gate"` (planner); `gate_context` dict carries `gate_prompt` (non-empty str), `gate_id` (str), `workflow_id` (str), `checkpoint_ts` (ISO-8601 str) | ✅ [_dispatch.py:673-683](../../../../ai_workflows/workflows/_dispatch.py#L673-L683). `test_run_workflow_gate_pause_projects_plan_and_gate_context` exercises the planner path and pins every required key including `gate_prompt.strip()` non-empty + `datetime.fromisoformat(checkpoint_ts).tzinfo is not None`. |
| 4 | `ResumeRunOutput.plan` and `.gate_context` mirror the run-side shape on re-gate resume (slice_refactor, two gates) | ✅ [_dispatch.py:929-939](../../../../ai_workflows/workflows/_dispatch.py#L929-L939). `test_resume_run_regate_projects_plan_and_gate_context` drives slice_refactor through `planner_review` → resume → `slice_refactor_review` and asserts `gate_id == "slice_refactor_review"`, `workflow_id == "slice_refactor"`. |
| 5 | `ResumeRunOutput.plan` non-null on `status="gate_rejected"` (last draft for audit); `gate_context` is `None` on that path | ✅ [_dispatch.py:977-996](../../../../ai_workflows/workflows/_dispatch.py#L977-L996). Rejected branch calls `_dump_plan(final.get("plan"))` (Gap 1 absorption). `test_gate_rejected_preserves_last_draft_plan` green; collateral `test_resume_run::test_resume_run_rejected_flips_row_and_returns_gate_rejected` flipped from `plan is None` → `plan is not None` with an M11-Gap-1 inline comment. |
| 6 | Schema docstrings on both output models rewritten; zero `"only on completed"` text; describe per-status `plan` population, `gate_context` forward-compat, `"aborted"` meaning | ✅ [schemas.py:80-126](../../../../ai_workflows/mcp/schemas.py#L80-L126) + [schemas.py:136-189](../../../../ai_workflows/mcp/schemas.py#L136-L189). `grep -n 'only on ' ai_workflows/mcp/schemas.py` → no match. Both docstrings enumerate `"pending"` / `"completed"` / `"aborted"` / `"errored"` (plus `"gate_rejected"` on `ResumeRunOutput`) and name the forward-compat M12 cascade-transcript keys. |
| 7 | Non-gate paths byte-identical to M4-era dump: `completed` → `plan` matches, `gate_context=None`, `awaiting=None`; `errored` + `aborted` → `plan=None`, `gate_context=None` | ✅ `test_completed_status_has_null_gate_context_and_matches_m4_plan_shape` compares `result.plan` against a golden `expected_plan` dict (byte-identical). Every non-interrupt branch in both helpers sets `gate_context=None` explicitly (grep confirms 9 `"gate_context": None,` lines across the two helpers + the two dispatch-level exception branches). |
| 8 | `_dump_plan` helper added at module scope; all five branches (two interrupt, two completed, one rejected) route through it | ✅ [_dispatch.py:576-592](../../../../ai_workflows/workflows/_dispatch.py#L576-L592). `grep -n "_dump_plan(" ai_workflows/workflows/_dispatch.py` returns exactly 5 call sites: run-interrupt (L679), run-completed (L739), resume-interrupt (L935), resume-rejected (L992), resume-completed (L1006). |
| 9 | `workflow: str` threaded through both `_build_*_from_final` helpers | ✅ [_dispatch.py:637](../../../../ai_workflows/workflows/_dispatch.py#L637) + [_dispatch.py:882](../../../../ai_workflows/workflows/_dispatch.py#L882). Call sites in `run_workflow` + `resume_run` pass `workflow=workflow` from the enclosing scope. |
| 10 | `.claude/skills/ai-workflows/SKILL.md` names `plan` + `gate_context.gate_prompt` in the pending-flow section; skill-text test green | ✅ [SKILL.md:45-65](../../../../.claude/skills/ai-workflows/SKILL.md) shows a populated-`plan` + `gate_context` example and the narrative instructs *"Read the `plan` and `gate_context.gate_prompt` from the response. Surface the plan body to the user verbatim, quote the gate prompt, ..."*. `test_skill_names_plan_and_gate_prompt_in_pending_flow` green. |
| 11 | `skill_install.md §4 Smoke` expected-output snippet refreshed; existing link tests stay green | ✅ [skill_install.md:86-101](../../skill_install.md) (gate-pause snippet) + [skill_install.md:108-119](../../skill_install.md) (completed snippet) — both snippets now show non-null `plan` + `gate_context` at pause, and `gate_context: null` on `completed`. `test_skill_install_doc_links_resolve` green in the full suite run. |
| 12 | Five (itemised as 4 + 1 + 1 = 6) new tests land and pass | ✅ `tests/mcp/test_gate_pause_projection.py` → 4 tests; `tests/mcp/test_aborted_status_roundtrip.py` → 1 test; `tests/skill/test_skill_md_shape.py::test_skill_names_plan_and_gate_prompt_in_pending_flow` → 1 test. 6 total, all green. *(Spec header says "Five new tests" but itemises 4+1+1=6 — the itemisation is authoritative; see LOW-01 below for the scoreboard mismatch.)* |
| 13 | `uv run pytest` + `uv run lint-imports` (4 contracts kept) + `uv run ruff check` all clean | ✅ Re-run locally at audit time: **pytest 602 passed, 5 skipped, 2 pre-existing yoyo warnings, 18.41s**; **lint-imports 4 contracts kept, 0 broken**; **ruff clean**. |
| 14 | CHANGELOG entry under `[Unreleased]` lists files + ACs + ISS-02 driver + `"aborted"` latent-bug absorption note | ✅ [CHANGELOG.md:10-86](../../../../CHANGELOG.md#L10-L86). Dated `2026-04-22`. Names the Issue C absorption verbatim ("pre-existing latent bug, absorbed into this task as Issue C"); names ISS-02 as driver with back-link; itemises every file touched; explicitly notes the final AC (ISS-02 flip) lands at audit close. |
| 15 | M9 T04 issue file ISS-02 flipped `OPEN` → `RESOLVED (M11 T01 <sha>)` with back-link; propagation footer updated | ✅ **Cycle 2:** M9 T04 issue file updated on all five pointers (status line, ISS-02 subsection heading, detail-block status, Issue-log row, Propagation-status footer) — each now reads `✅ RESOLVED (M11 T01 <sha>)` with back-link to this issue file. The literal `<sha>` placeholder is the documented stamp-on-commit shape per spec (the commit-making turn substitutes the actual SHA). Back-propagation block added to this file's `## Propagation status` footer. |

## 🔴 HIGH

*None.*

## 🟡 MEDIUM

### ISS-01 — M9 T04 ISS-02 `RESOLVED` flip + propagation footer update not yet performed — ✅ RESOLVED (Cycle 2)

**Severity:** 🟡 MEDIUM (book-keeping, not functional)
**Status:** ✅ **RESOLVED (Cycle 2, 2026-04-22)** — Builder flipped the M9 T04 issue file on all five pointers (status-line paragraph, ISS-02 subsection heading, ISS-02 detail-block status + renamed old *Discovered* → *Originally deferred*, `## Issue log` row for `M9-T04-ISS-02`, `## Propagation status` footer). The `<sha>` placeholder is deliberately literal — the spec's AC-15 writes the target shape verbatim as `RESOLVED (M11 T01 <sha>)`, and the commit-making turn substitutes the actual SHA. The original re-audit gate for this issue ("Has the M9 T04 issue file been updated?") is satisfied.
**AC impacted:** AC-15 (the trailing propagation AC the spec itself flags: *"M9 T04 issue file ISS-02 flipped `OPEN → RESOLVED (M11 T01 <sha>)` with back-link; propagation footer updated"*).

**Finding.** The M9 T04 issue file currently reads:

> ISS-02 — Severity 🔴 HIGH — Status: 🔜 **DEFERRED → M11 T01** (2026-04-21). Propagation entry landed on the M11 T01 spec […]; **this issue flips to `RESOLVED` when M11 T01 lands**.

M11 T01 has now landed at the code level (schemas + dispatch + skill text + tests all green), but no commit has been created yet in this /clean-implement run — the CHANGELOG entry itself notes *"that lands at audit close via the M11 T01 audit issue-file write + back-propagation"*. The flip requires a SHA; until the user requests the commit, the audit cannot stamp one.

**Action / Recommendation.** On the next commit-making turn (user-initiated), edit [`design_docs/phases/milestone_9_skill/issues/task_04_issue.md`](../../milestone_9_skill/issues/task_04_issue.md) in the same commit that lands M11 T01:

1. Flip the ISS-02 *Status* line from `🔜 DEFERRED → M11 T01` to `✅ RESOLVED (M11 T01 <sha>)` with a back-link to the commit.
2. Update the same file's `## Issue log` table row: flip `M9-T04-ISS-02` status from `🔜 DEFERRED` to `✅ RESOLVED (M11 T01 <sha>)`.
3. Update the same file's `## Propagation status` footer: replace *"ISS-02 flips from DEFERRED to RESOLVED when M11 T01 closes"* with *"ISS-02 RESOLVED via M11 T01 (`<sha>`)"*.
4. Add a matching *Propagation status* footer to **this** issue file noting the back-propagation: `M11 T01 closes M9 T04 ISS-02 at commit <sha>`.

No audit re-run needed — this is a doc-only doc-link update, and `test_doc_links.py` already gate-enforces link validity.

## 🟢 LOW

### ISS-02 — Spec's AC-11 scoreboard says "Five new tests" but itemises six — ✅ RESOLVED (Cycle 2)

**Severity:** 🟢 LOW (cosmetic spec arithmetic)
**Status:** ✅ **RESOLVED (Cycle 2, 2026-04-22)** — Builder edited [`task_01_gate_pause_projection.md:175`](../task_01_gate_pause_projection.md#L175): `"Five new tests"` → `"Six new tests"`. Itemisation (4 + 1 + 1 = 6) now matches the scoreboard number.
**File:** [task_01_gate_pause_projection.md:175](../task_01_gate_pause_projection.md#L175).

**Finding.** The *Acceptance Criteria* bullet reads: *"Five new tests land and pass (four in `tests/mcp/test_gate_pause_projection.py`, one in `tests/mcp/test_aborted_status_roundtrip.py`, plus one skill-text test under `tests/skill/`)."* The itemisation totals 4 + 1 + 1 = **six**, not five. The implementation shipped six tests, matching the itemisation — no functional gap. The scoreboard number is a spec typo.

**Action / Recommendation.** On the next doc-touching turn, edit [task_01_gate_pause_projection.md:175](../task_01_gate_pause_projection.md#L175) and change *"Five new tests"* to *"Six new tests"*. Same edit belongs in the CHANGELOG entry's count if any number is quoted there (spot-check: the CHANGELOG lists the files, not a count — no edit needed there).

### ISS-03 — Defensive `_extract_gate_context` fallback silent; spec called for a `structlog` warning — ✅ RESOLVED (Cycle 2)

**Severity:** 🟢 LOW (never fires in practice; spec-deviation only)
**Status:** ✅ **RESOLVED (Cycle 2, 2026-04-22)** — Builder added `import structlog` at module scope in [`ai_workflows/workflows/_dispatch.py:66`](../../../../ai_workflows/workflows/_dispatch.py#L66), bound a module-level `_LOG = structlog.get_logger(__name__)` at [L87](../../../../ai_workflows/workflows/_dispatch.py#L87), and split the defensive fallback path in `_extract_gate_context` into two explicit `else` branches ([L622-L641](../../../../ai_workflows/workflows/_dispatch.py#L622-L641)): `_LOG.warning("mcp_gate_context_malformed_payload", workflow=workflow, payload_type=type(raw).__name__)` when the interrupt head `.value` is not a dict, and `_LOG.warning("mcp_gate_context_missing_interrupt", workflow=workflow)` when the `__interrupt__` tuple is empty. Docstring updated to mention the warning emission. Re-run gates: pytest 602 passed / 5 skipped, lint-imports 4 kept, ruff clean.
**File:** [ai_workflows/workflows/_dispatch.py:622-641](../../../../ai_workflows/workflows/_dispatch.py#L622-L641).

**Finding.** The task spec §*Deliverables → `_build_result_from_final` → Interrupt branch* is explicit:

> Defensive `.get(...)` everywhere — if the tuple is unexpectedly empty or the payload key is missing, fall back to `"<gate prompt not recorded>"` and **log a `structlog` warning** but do not raise.

The landed `_extract_gate_context` helper does the fallback — `payload.get("prompt", "<gate prompt not recorded>")` — but does not log. `_dispatch.py` does not import `structlog` at all (grep against the file returns zero matches). The defensive path only fires if `HumanGate` produces a malformed payload, which the live code path makes impossible — `human_gate.py` always stamps both `gate_id` and `prompt` as dict values. But the spec is explicit, and the missing log is a spec-compliance deviation.

**Why LOW, not MEDIUM.** (a) The path is dead-code in practice — a defensive "should never happen" branch. (b) No test asserts the log, so tests stay green. (c) The architecture-audit concern (KDR-004 / §8.1) is already served by `TieredNode`'s own `StructuredLogger` emit; `_extract_gate_context` is downstream of that. (d) The fallback value itself (`"<gate prompt not recorded>"`) is readable enough that an operator staring at it would know to check the logs/checkpointer state, which is the warning's purpose anyway.

**Action / Recommendation.** Small follow-up edit to `_extract_gate_context`: import `structlog` at module scope (first `structlog` usage in `_dispatch.py`, so this also adds a `logger = structlog.get_logger(__name__)` module-level binding), and emit `logger.warning("mcp_gate_context_missing_payload", run_id=..., has_interrupt=bool(interrupts))` inside the `else` branch (empty tuple) and the `isinstance` false branch. Two-line addition plus one import. Can land as a follow-up in an M11 T02 close-out if T01 is already committing. Non-blocking.

### ISS-04 — Skill-text Gap-2 test landed in `test_skill_md_shape.py` instead of spec-named landing spots

**Severity:** 🟢 LOW (Builder discretion; no functional gap)
**Status:** OPEN — note only, no action needed
**File:** [tests/skill/test_skill_md_shape.py:113-145](../../../../tests/skill/test_skill_md_shape.py#L113-L145).

**Finding.** The task spec §*Tests → Skill-text contract test (Gap 2)* says: *"Extend `tests/skill/test_skill_frontmatter.py` (or add a new `tests/skill/test_skill_gate_review.py` if the frontmatter file is already long)."* The Builder chose a third landing spot — `tests/skill/test_skill_md_shape.py` — which is an existing skill-body content-shape test file. Reasonable judgement call: `test_skill_frontmatter.py` covers frontmatter YAML only; `test_skill_md_shape.py` covers body assertions, which is the test's concern. The test exists, asserts both `plan` + `gate_context.gate_prompt` in the body + the pending-status example, and passes. No action needed beyond noting the deviation.

**Action / Recommendation.** None. Landing-spot choice is Builder discretion; the spec's "or" list was two examples, not an exhaustive enumeration. Flagging so future spec authors know that "landing spot is Builder's call" reads more naturally than enumerating.

## Additions beyond spec — audited and justified

- **`_stub_slice_tier_registry` autouse fixture in `test_gate_pause_projection.py` ([L149-156](../../../../tests/mcp/test_gate_pause_projection.py#L149-L156)).** Swaps `slice_refactor_module.slice_refactor_tier_registry` with an all-LiteLLM registry so the stub adapter intercepts every call regardless of route. **Justified.** The production `slice_refactor_tier_registry()` composes `planner_tier_registry()` (which the directory conftest already pins to LiteLLM) with an Ollama-routed `slice-worker` — monkey-patching the planner registry upstream doesn't cascade because slice_refactor imports the symbol by reference at import time. Without this fixture the slice-worker call would try to dial a real Ollama server. Fixture is scoped to the M11 test file only; no impact on other suites.
- **13 collateral test edits across 5 files** (`test_run_workflow.py`, `test_resume_run.py`, `test_slice_refactor_apply.py`, `test_slice_refactor_hard_stop.py`, `test_slice_refactor_strict_gate.py`, `test_slice_refactor_e2e.py`). **Justified.** (a) The helper signatures grew `workflow: str` kwarg ⇒ every direct call site needed the kwarg threaded in. (b) The interrupt + rejected branches now populate `plan` where they previously returned `None` ⇒ the two tests that asserted `plan is None` on those branches had to flip to `plan is not None` (with an M11-T01 inline comment on each). Pure contract propagation; zero drive-by scope creep. Every flipped assertion carries an explanatory comment naming M11 T01 / Gap 1.
- **CHANGELOG entry labelled `### Changed` rather than `### Added`.** **Justified.** The schema-literal + helper-signature changes are additive at the MCP wire (KDR-008) but the *semantics* of `plan` on `status="pending"` change from "always null" to "populated at gate pause". Keep-a-Changelog's `Changed` bucket is the correct fit per the spec's own framing ("The existing output models grow their `plan` population rule").
- **New `_extract_gate_context` helper (spec names this helper's behaviour but not its name).** **Justified.** The spec describes the projection inline without naming a helper. Extracting into `_extract_gate_context(final, *, workflow)` at module scope keeps the two `_build_*_from_final` helpers DRY + matches the `_dump_plan` factoring the spec *does* name. Private module-level helper, unit-testable via the integration tests, no import surface added.

## Gate summary

| Gate | Result |
| --- | --- |
| `uv run pytest` | ✅ **Cycle 1:** 602 passed, 5 skipped, 2 pre-existing yoyo warnings, 18.41s. **Cycle 2 (after structlog + doc edits):** 602 passed, 5 skipped, 2 pre-existing yoyo warnings, 18.45s — unchanged count; structlog warnings emit to the `StructuredLogger` JSON stream on stderr and are not asserted by any test (never-fires-in-practice defensive path). |
| `uv run lint-imports` | ✅ **Cycle 1 & 2:** 4 contracts kept, 0 broken (primitives / graph / workflows / evals boundaries preserved). No new layer surface from Cycle 2 edits. |
| `uv run ruff check` | ✅ **Cycle 1 & 2:** clean. |
| `grep -n 'only on ' ai_workflows/mcp/schemas.py` | ✅ no match (old "populated only on `'completed'`" text fully removed per AC-6) |
| `grep -n "_dump_plan(" ai_workflows/workflows/_dispatch.py` | ✅ 5 call sites (run-interrupt, run-completed, resume-interrupt, resume-rejected, resume-completed) per AC-8 |
| KDR-003 guardrail (`mcp/server.py` secret-read check) | ✅ `test_mcp_server_module_does_not_read_provider_secrets` green in full-suite run |
| Skill-text KDR-003 guardrail (`test_skill_md_forbids_anthropic_api`) | ✅ green |
| Additive-only contract (golden-plan regression on `completed`) | ✅ `test_completed_status_has_null_gate_context_and_matches_m4_plan_shape` green with byte-identical golden dict comparison |

## Issue log

| ID | Severity | Status | Owner / Next touch |
| --- | --- | --- | --- |
| M11-T01-ISS-01 | 🟡 MEDIUM | ✅ RESOLVED (Cycle 2) | M9 T04 issue file flipped on all five pointers with `<sha>` placeholder — commit-making turn stamps the actual SHA |
| M11-T01-ISS-02 | 🟢 LOW | ✅ RESOLVED (Cycle 2) | Spec AC-12 bullet: `"Five new tests"` → `"Six new tests"` landed |
| M11-T01-ISS-03 | 🟢 LOW | ✅ RESOLVED (Cycle 2) | `_extract_gate_context` now emits `_LOG.warning(...)` on both defensive branches; docstring updated |
| M11-T01-ISS-04 | 🟢 LOW | CLOSED (note only) | No action; Builder-discretion landing spot |

## Deferred to nice_to_have

*None.* No findings map to `nice_to_have.md`. ISS-03's structlog warning is an in-scope spec-compliance nit, not a deferred observability backend.

## Propagation status

- **M9 T04 ISS-02 — ✅ RESOLVED via M11 T01 (`<sha>`).** Cycle 2 Builder flipped all five pointers in [`design_docs/phases/milestone_9_skill/issues/task_04_issue.md`](../../milestone_9_skill/issues/task_04_issue.md):
  - Status-line paragraph: now states *"ISS-02 ✅ RESOLVED (M11 T01 `<sha>`) on 2026-04-22"* with a link to this issue file.
  - ISS-02 subsection heading: appended ` — ✅ RESOLVED`.
  - ISS-02 detail block: `Status` rewritten to *"✅ **RESOLVED (M11 T01 `<sha>`)** (2026-04-22)"* with the M11 T01 verdict summary; old `Discovered` line renamed to `Originally deferred`.
  - `## Issue log` table row for `M9-T04-ISS-02`: Status column flipped to *"✅ RESOLVED (M11 T01 `<sha>`)"*.
  - `## Propagation status` footer entry for ISS-02: rewritten as resolved-via-M11 T01 with back-link.
  The literal `<sha>` placeholder is the spec AC-15 shape (*"flipped `OPEN → RESOLVED (M11 T01 <sha>)`"*) — the commit-making turn substitutes the actual commit SHA across both issue files + the CHANGELOG in a single-pass find-and-replace.
- **No forward-deferral targets from this audit.** All three Cycle 1 OPEN issues closed in-milestone during Cycle 2. ISS-04 was a CLOSED Builder-discretion note from Cycle 1.
- **No `nice_to_have.md` entry.** ISS-03's `structlog` warning landed inside the existing observability frame (KDR-004 / §8.1); no new backend or dependency introduced.
