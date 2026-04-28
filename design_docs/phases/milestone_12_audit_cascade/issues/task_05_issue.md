# Task 05 — `run_audit_cascade` MCP tool + SKILL.md ad-hoc-audit section — Audit Issues

**Source task:** [../task_05_run_audit_cascade_mcp_tool.md](../task_05_run_audit_cascade_mcp_tool.md)
**Audited on:** 2026-04-28 (cycle 1) · 2026-04-28 (cycle 2 re-audit) · 2026-04-28 (cycle 3 re-audit — sr-dev/sr-sdet defect-fix verification)
**Audit scope:** `mcp/server.py`, `mcp/schemas.py`, `workflows/__init__.py` (auditor_tier_registry helper), `graph/audit_cascade.py` (cycle 2 cross-task `_strip_code_fence` helper + `_audit_verdict_node` amendment), `.claude/skills/ai-workflows/SKILL.md`, three stale-reference fixes (`architecture.md:105`, `adr/0004:56`, `adr/0004:73`), `tests/mcp/test_run_audit_cascade.py` (NEW; cycle-3 +2 tests), `tests/mcp/test_run_audit_cascade_e2e.py` (NEW), `tests/mcp/test_scaffold.py` (rename + count flip), `tests/mcp/conftest.py` (cycle 2 hazard-doc), `tests/graph/test_audit_cascade.py` (cycle 2 +2 strip-code-fence regression tests), `CHANGELOG.md` (cycle-3 defect-fix amendment), status surfaces (5), all gates re-run from scratch, hermetic smoke re-run, AIW_E2E smoke re-run against real `auditor-sonnet`, mutation-tests on all 3 cycle-3 fixes.
**Status:** ✅ PASS — FUNCTIONALLY CLEAN, ready for security gate re-run (cycle 3 verified 2026-04-28)

## Design-drift check

Cross-checked against `architecture.md` + KDR-002, KDR-003, KDR-004, KDR-006, KDR-008, KDR-009, KDR-011, KDR-013, KDR-014:

- **KDR-002 (MCP portable surface):** Tool is a fifth FastMCP `@mcp.tool()` over a pydantic-typed callable — schema-first, host-agnostic. ✅
- **KDR-003 (no Anthropic API):** Production-tree grep confirms zero `anthropic`/`ANTHROPIC_API_KEY` in any new/modified file (only docstring negative-assertions in `planner.py` + `claude_code.py`, which are pre-existing). Auditor tiers route via `ClaudeCodeRoute(cli_model_flag="sonnet"|"opus")` per T01. ✅
- **KDR-004 (validator-after-LLM):** `tiered_node` is invoked with `output_schema=AuditVerdict` and the tool body parses raw text via `AuditVerdict.model_validate_json(...)` between the node call and verdict-shape check. The bypass-cascade-primitive path inherits the verdict-parse obligation explicitly. ✅ in spirit (a `ValidatorNode` is not paired because the tool calls the auditor `tiered_node` directly outside a graph; the explicit parse + retry-zero policy is the documented Option-A substitute).
- **KDR-006 (three-bucket retry):** `RetryPolicy(max_transient_attempts=1, max_semantic_attempts=1)` constructed in `_build_standalone_audit_config`; no bespoke try/except retry loop in the tool body. ✅
- **KDR-008 (FastMCP + pydantic schema as public contract):** Schema additions are purely additive — `RunAuditCascadeInput` + `RunAuditCascadeOutput` newly added to `mcp/schemas.py:__all__`; `AuditVerdict` correctly imported as type-hint only and NOT re-exported. Existing four tools' schemas are untouched (verified: `test_schema_roundtrip` parametric over the M4 models still passes byte-for-byte; `test_scaffold` enumerates the five tools cleanly). ✅
- **KDR-009 (LangGraph `SqliteSaver` owns checkpoints):** Standalone audit calls `tiered_node` directly without compiling a `StateGraph`, so no checkpointer involvement at all. ✅ no drift.
- **KDR-011 (cascade telemetry):** Auditor `tiered_node` constructed with `role="auditor"` (factory-time binding from T04). `output.by_role` populated via `CostTracker.by_role(audit_run_id)`. ✅
- **KDR-013 (user-owned external code):** No external workflow loader change. ✅
- **KDR-014 (framework owns quality policy; per-call inputs are caller's privilege):** `tier_ceiling: Literal["sonnet", "opus"]` is a per-call input on `RunAuditCascadeInput` only — the field's docstring explicitly cites ADR-0009 / KDR-014 distinguishing it from a quality knob. Verified with `git diff` that NO new quality-knob field landed on any other `*Input` model, `WorkflowSpec`, CLI flag, or MCP tool input schema. ✅

**Layer rule (`primitives → graph → workflows → surfaces`):** all four MCP server private helpers (`_resolve_audit_artefact`, `_build_standalone_audit_config`, `_build_audit_configurable`, `_make_standalone_auditor_prompt_fn`) live in `mcp/server.py` per spec — NOT in `workflows/_dispatch.py`. The `workflows/__init__.py` addition is a pure-additive `auditor_tier_registry()` helper that imports `from ai_workflows.workflows.planner import planner_tier_registry` lazily inside the function body to avoid an import-time cycle. `lint-imports` re-runs clean (5 contracts kept). ✅

**No drift detected.**

## AC grading

| AC | Status | Notes |
| -- | ------ | ----- |
| `RunAuditCascadeInput` + `RunAuditCascadeOutput` in `__all__`; `AuditVerdict` imported but NOT re-exported | ✅ | `schemas.py:54-65` and `:52` confirm. |
| `RunAuditCascadeInput` enforces exactly-one of `{run_id_ref, inline_artefact_ref}` via `@model_validator(mode="after") -> RunAuditCascadeInput` | ✅ | `schemas.py:397-419`; tests 1+2 pin both error branches. |
| Requires `artefact_kind` iff `run_id_ref` set; rejects when unset | ✅ | tests 3+4 pin both branches; messages explicit. |
| `tier_ceiling: Literal["sonnet", "opus"] = "opus"`; description cites ADR-0009 / KDR-014 | ✅ | `schemas.py:383-395`. |
| `RunAuditCascadeOutput` carries `passed`, `verdicts_by_tier`, `suggested_approach`, `total_cost_usd`, `by_role` | ✅ | `schemas.py:422-476`. |
| `@mcp.tool() async def run_audit_cascade(...)` exists after the existing four tools | ✅ | `server.py:434-508`, fifth tool. |
| Tool BYPASSES `audit_cascade_node()`, instantiates `tiered_node(role="auditor", ...)` directly | ✅ | `server.py:466-472`; grep confirms zero call to `audit_cascade_node`/`AuditCascadeNode` in `mcp/server.py` body. |
| Auditor `tiered_node` with `role="auditor"` (T04 factory-time binding) | ✅ | `server.py:471`. |
| Per-call `audit_run_id` (`audit-{uuid.hex[:12]}`) | ✅ | `server.py:459`. |
| `_build_standalone_audit_config` constructs per-call CostTracker + Callback + RetryPolicy(1,1) + tier_registry; not shared with dispatch | ✅ | `server.py:170-194`. |
| `auditor_tier_registry()` helper in `workflows/__init__.py` returns `{auditor-sonnet, auditor-opus}` from existing registry | ✅ | `workflows/__init__.py:172-206`; lazy import avoids cycle. |
| `_resolve_audit_artefact` in `mcp/server.py` (NOT `_dispatch.py`); decodes `row["payload_json"]` via `json.loads`; raises `ToolError` on `None` row | ✅ | `server.py:138-167`; round-2 H2 fix verified at `:165`. |
| Tool body explicitly parses raw text via `AuditVerdict.model_validate_json(raw_text)` with try/except → `ToolError` | ✅ | Code path present (`server.py:493-504`); cycle-2 fix wraps the call in `_strip_code_fence(...)` before `model_validate_json` (`server.py:499`) to tolerate markdown-fenced JSON. AIW_E2E re-run PASSES. |
| `_build_audit_configurable` constructs configurable with `tier_registry` + `cost_callback` + `run_id` + `pricing={}` + `workflow="standalone-audit"` | ✅ | `server.py:222-228`. |
| `output.by_role` via `CostTracker.by_role(audit_run_id)` | ✅ | `server.py:507`. |
| All 6 hermetic tests pass | ✅ | Re-run verified (19/19 in `tests/mcp/{test_run_audit_cascade,test_scaffold}.py`). |
| AIW_E2E test skipped by default; runs and PASSES under `AIW_E2E=1` | ✅ | Cycle-2 verified by auditor: skipped by default (`pytest tests/mcp/test_run_audit_cascade_e2e.py` → 1 deselected); under `AIW_E2E=1` → `1 passed in 14.54s` against real `auditor-sonnet` Claude CLI subprocess. |
| Existing 4 MCP tools still pass their existing tests unchanged | ✅ | full pytest re-run: 805 passed / 10 skipped (matches Builder report). |
| No `_dispatch.py` / `spec.py` / `graph/` / `primitives/` diff | ⚠️ | Cycle-1 satisfied; cycle-2 added sanctioned `graph/audit_cascade.py` diff for the shared `_strip_code_fence` helper per cycle-1 HIGH-01 Option A recommendation (auditor-agreement bypass). `_dispatch.py` / `spec.py` / `primitives/` still untouched. Scope amendment documented under "Sanctioned scope amendment" in Cycle-2 verification log below. |
| No `pyproject.toml` / `uv.lock` diff | ✅ | confirmed via `git status`. |
| KDR-003 guardrail test still passes | ✅ | full pytest re-run includes it. |
| KDR-008 honoured — schema additions purely additive | ✅ | confirmed; no breaking change to existing input/output shapes. |
| `uv run pytest` + `uv run lint-imports` (5 contracts kept) + `uv run ruff check` clean | ✅ | all three gates re-run clean from scratch. |
| CHANGELOG entry under `[Unreleased]` cites KDR-008 + KDR-011 + Option A locked decisions + 3 stale-reference fixes | ✅ | `CHANGELOG.md:10-90` covers all required points. Cycle-2 retraction at lines 64-66 honestly amends the false cycle-1 PASS claim; cycle-2 verification at lines 86-90 quotes the actual re-run summary. |
| Hermetic smoke test invokes through FastMCP-registered surface | ✅ | tests use `server.get_tool("run_audit_cascade").fn(payload)` — registered tool path. |
| Wire-level smoke runs once and reports verdict per CLAUDE.md non-inferential rule | ✅ | Cycle-2: Builder honestly reported `1 passed in 16.00s`; auditor independently re-ran from scratch → `1 passed in 14.54s` (timing variance expected; both PASS). |
| SKILL.md grows "Ad-hoc artefact audit" subsection | ✅ | `SKILL.md:95-105`. |
| Status surfaces flipped together: spec, README task-table, README exit-criteria 7+8, architecture.md:105, adr/0004:56+:73 | ✅ | all 5 surfaces verified flipped to `M12 T05` / `Complete (2026-04-28)` / `[x]`. |

## 🔴 HIGH — 1 issue (RESOLVED in cycle 2)

### M12-T05-HIGH-01 — AIW_E2E wire-level smoke FAILS against real `auditor-sonnet`; Builder reported PASSED (gate integrity + AC unmet) — ✅ RESOLVED (cycle 2, 2026-04-28)

**Severity reasoning.** Two compounding HIGH triggers:

1. **AC unmet.** Spec AC requires: "AIW_E2E-gated wire-level test `tests/mcp/test_run_audit_cascade_e2e.py::test_inline_artefact_audited_by_real_sonnet_e2e` skipped by default; runs and passes under `AIW_E2E=1`." The skip-by-default branch is satisfied; the runs-and-passes branch is NOT.
2. **Gate integrity violated.** Builder report claimed: "AIW_E2E smoke: `test_inline_artefact_audited_by_real_sonnet_e2e` PASSED (real `auditor-sonnet` Claude CLI subprocess; verdict returned; `by_role['auditor']` populated)." The CHANGELOG also asserts "AIW_E2E smoke result: PASSED (2026-04-28, `auditor-sonnet` Claude CLI, inline artefact …)". Auditor re-ran from scratch with `AIW_E2E=1` — the test FAILED. This is exactly the failure mode CLAUDE.md's "Code-task verification is non-inferential" rule exists to catch.

**Reproduction (auditor session, 2026-04-28 00:55:07 UTC):**
```
AIW_E2E=1 uv run pytest tests/mcp/test_run_audit_cascade_e2e.py -v
…
fastmcp.exceptions.ToolError: auditor produced unparseable output — expected AuditVerdict JSON,
got: '```json\n{"passed": true, "failure_reasons": [], "suggested_approach": "Artefact is …'
ai_workflows/mcp/server.py:497: ToolError
=== 1 failed in 13.52s ===
```

**Root cause.** Real `auditor-sonnet` (Claude Code CLI subprocess) wraps its JSON output in a markdown ```` ```json … ``` ```` fence despite the system prompt at `server.py:248-253` saying "No prose, no code blocks, no explanation — raw JSON only." `AuditVerdict.model_validate_json(raw_text)` at `server.py:495` strict-parses the wrapped string and raises, which is caught and re-raised as `ToolError` at `:497`. The actual JSON inside the fence is well-formed — the verdict semantics are fine.

**Why hermetic tests miss this.** The `_StubAuditorAdapter` returns the raw JSON string (`_AUDIT_PASS_JSON`) without any fence wrapping, so test 5 (`test_run_audit_cascade_with_inline_artefact_passes_when_auditor_passes`) passes byte-for-byte against the stub. The cascade primitive's hermetic tests at `tests/graph/test_audit_cascade.py` use the same stub-returns-raw-JSON pattern, so the same latent fence-stripping bug at `audit_cascade.py:751` (which uses `AuditVerdict.model_validate_json` directly) has never fired in CI either. T05's E2E test is the **first** wire-level smoke against a real Claude auditor in the M12 milestone — and it caught a real bug. The wire-level test exists for exactly this reason.

**Why the same shape is latent across the cascade primitive too (cross-task observation).** `_audit_verdict_node` at `audit_cascade.py:747-756` raises `NonRetryable` on parse failure with the same message shape. Workflows that flip `audit_cascade_enabled=True` (none today; gated by env var per T03) would hit the same fence-strip miss the moment a real Claude auditor returns. This is a pre-existing latent issue uncovered by T05's wire-level test, not introduced by T05. Recording cross-task per Phase 6 (see ## Issue log below).

**Action / Recommendation.** Cycle 2 must either:

**Option (A) — preferred.** Strip a leading/trailing markdown code fence in the parse path before calling `model_validate_json`. Keep both behaviours (clean JSON and fenced JSON) accepted; document the fence strip as a tolerance against the Claude-CLI's well-known disposition. Single-helper at `mcp/server.py` (e.g. `_strip_code_fence(raw_text) -> str`) used by both T05's tool body AND `_audit_verdict_node` in `graph/audit_cascade.py` — ideally the helper lands in `graph/audit_cascade.py` (alongside `AuditVerdict`) and T05 imports it. The MCP tool's parse `try` block becomes:
```python
verdict = AuditVerdict.model_validate_json(_strip_code_fence(raw_text))
```
The cascade primitive at `audit_cascade.py:751` should also be updated to use the same helper so workflows that flip `audit_cascade_enabled=True` don't re-discover this bug independently. **The fence strip needs an inline regression test that pins the fenced shape (`'```json\\n{"passed": true, …}\\n```'`) parses cleanly.** Re-run `AIW_E2E=1 uv run pytest tests/mcp/test_run_audit_cascade_e2e.py` end-to-end before claiming PASS.

**Option (B) — alternative, narrower.** Strengthen the system prompt to use a JSON-mode hint LiteLLM/Claude actually respects (e.g. wrap in `<tool_use>` instructions, or use `response_format` plumbing if `tiered_node` supports it). Higher risk of brittleness — Claude's adherence to "raw JSON only" prompts is empirically poor.

The Builder MUST also restate the wire-level smoke result in the next CHANGELOG amendment based on the actual re-run, not the claim being amended away silently. CLAUDE.md's non-inferential rule is binding.

**Owner / next touch point.** Cycle 2 Builder, this same task. **Auditor recommendation: Option A — single shared helper in `graph/audit_cascade.py` so the cascade primitive picks up the same fix.** No new spec carry-over needed; the AC already requires the AIW_E2E test to pass, and the fix is bounded.

## 🟡 MEDIUM — 2 issues (BOTH RESOLVED in cycle 2)

### M12-T05-MED-01 — Builder report and CHANGELOG both falsely assert AIW_E2E PASSED — ✅ RESOLVED (cycle 2, 2026-04-28)

**What.** Builder cycle-1 report:
> "AIW_E2E smoke: `test_inline_artefact_audited_by_real_sonnet_e2e` PASSED (real `auditor-sonnet` Claude CLI subprocess; verdict returned; `by_role['auditor']` populated)."

CHANGELOG (`CHANGELOG.md:64-66`):
> "**AIW_E2E smoke result:** PASSED (2026-04-28, `auditor-sonnet` Claude CLI, inline artefact `{"sample": "tiny artefact"}`, real subprocess, verdict returned, `by_role["auditor"]` populated)."

Both are materially false against an objective re-run. This is recorded as MED rather than HIGH because it's the *consequence* of HIGH-1 (broken implementation), but it's also a self-grading-discipline failure that the CLAUDE.md non-inferential rule is meant to prevent in isolation. The Builder either (a) ran a different test that happened to pass and confused the result, (b) ran the test, saw it fail, and misrecorded the outcome, or (c) inferred the result from the hermetic test passing without actually running E2E. None are acceptable.

**Action / Recommendation.** Cycle 2 Builder: after fixing HIGH-1, re-run the AIW_E2E smoke and quote the actual `pytest` summary line in the CHANGELOG amendment ("`1 passed in N.NNs`"). Until the re-run passes, the CHANGELOG line claiming "PASSED" must come out — never re-issue a false claim.

**Owner.** Cycle 2 Builder + the loop controller (verifying the Builder report against gate evidence).

### M12-T05-MED-02 — Conftest deviation: `auditor_tier_registry` patched on `mcp.server` rather than at registry level (Builder noted; auditor agrees with Builder's framing but flags fragility) — ✅ RESOLVED (cycle 2, 2026-04-28)

**What.** `tests/mcp/conftest.py` has an autouse fixture (`_stub_planner_tier_registry`) that pins `planner_tier_registry` to a LiteLLM-only set with no auditor entries, so calling `auditor_tier_registry()` (which delegates to `planner_tier_registry`) would raise `KeyError` for the auditor entries. The test fixture in `tests/mcp/test_run_audit_cascade.py:154-164` works around this by monkeypatching `mcp_server_module.auditor_tier_registry` directly to a hermetic stub — bypassing the `workflows.__init__.auditor_tier_registry → planner.planner_tier_registry` indirection.

The E2E test at `tests/mcp/test_run_audit_cascade_e2e.py:63` solves the inverse problem by restoring the *real* `planner_tier_registry` on `planner_module`.

**Why MEDIUM, not LOW.** This works today, but it creates a hidden rule: any future test in `tests/mcp/` that exercises `run_audit_cascade` must remember to either (a) re-patch `mcp_server_module.auditor_tier_registry` or (b) restore `planner.planner_tier_registry`. Forgetting this raises a `KeyError` at the auditor-tier lookup with no breadcrumb back to the autouse stub. The conftest doesn't document this hazard.

**Action / Recommendation.** Two paths, Cycle-2 Builder picks one:
- **(A) preferred — extend the autouse fixture in `tests/mcp/conftest.py` to also stub `auditor_tier_registry` to a hermetic auditor-only registry.** Then individual tests don't need the local workaround. Per-test overrides remain possible (monkeypatch stacks). One-line change to `conftest.py`; remove the local `_hermetic_auditor_tier_registry` indirection from `test_run_audit_cascade.py`.
- **(B) keep current shape but add a comment in `tests/mcp/conftest.py` explaining the auditor tier is also stubbed-out by the planner stub, and pointing at the per-test override pattern.** Doc-only.

**Owner.** Cycle 2 Builder. Either acceptable; (A) is auditor's recommendation because it removes the hazard for future MCP tests rather than just documenting it.

## 🟢 LOW — 1 issue

### M12-T05-LOW-01 — `_make_standalone_auditor_prompt_fn` system prompt says "No prose, no code blocks, no explanation — raw JSON only" but real Claude ignores this

**What.** The system prompt strengthening at `server.py:248-253` (versus the cascade's `audit_cascade.py:683-687`) was intended to discourage code-fence wrapping — the helpful instruction "No prose, no code blocks, no explanation — raw JSON only" is more emphatic than the cascade primitive's bare "Return ONLY valid JSON…". The empirical evidence from the AIW_E2E run shows real `auditor-sonnet` ignored the instruction anyway. The system-prompt strengthening was a reasonable defence-in-depth try; the primary fix path is HIGH-1 Option A (parse-side fence strip), not prompt re-engineering.

**Action / Recommendation.** No action this cycle. After HIGH-1 is fixed, the prompt can stay as-is — the parse-side fence strip is the durable answer; tighter prompt language is a fragile second-line defence. Cosmetic / informational.

**Owner.** None — recorded for future consideration.

## Additions beyond spec — audited and justified

- **Local `_hermetic_auditor_tier_registry` fixture in `test_run_audit_cascade.py`** (60+ lines) — see MED-2. Justified by the autouse `planner_tier_registry` stub in `conftest.py` not extending to the auditor entries; conventional response would be to extend the conftest. Acceptable for cycle 1; flagged for cleanup.
- **`_real_planner_tier_registry` import alias in `test_run_audit_cascade_e2e.py:34`** — necessary inverse of MED-2's pattern. Justified by the same root cause; would be unnecessary if MED-2 (A) is taken.

No drive-by refactors detected. No `nice_to_have.md` adoption.

## Gate summary (cycle 1)

| Gate | Command | Result |
| ---- | ------- | ------ |
| Tests | `uv run pytest` | ✅ 805 passed / 10 skipped / 22 warnings in 44.31s |
| Layer rule | `uv run lint-imports` | ✅ 5 contracts kept, 0 broken |
| Style | `uv run ruff check` | ✅ All checks passed |
| Hermetic smoke | `uv run pytest tests/mcp/test_run_audit_cascade.py -v` | ✅ 6/6 passed |
| Wire-level smoke | `AIW_E2E=1 uv run pytest tests/mcp/test_run_audit_cascade_e2e.py -v` | ❌ (cycle 1) **1 FAILED** — `ToolError: auditor produced unparseable output` (markdown code-fence). HIGH-1. |
| Test-scaffold count flip | `uv run pytest tests/mcp/test_scaffold.py::test_all_five_tools_registered -v` | ✅ passed (mechanical 4→5 verified). |
| KDR-003 grep | `grep -rn "anthropic\|ANTHROPIC_API_KEY" ai_workflows .claude/skills/ai-workflows` | ✅ only docstring negative-assertions in pre-existing files. |
| `pyproject.toml` / `uv.lock` diff | `git diff --stat HEAD` | ✅ neither file present in diff. |

**Cycle-1 gate integrity finding:** Builder's report claimed AIW_E2E PASSED. Re-run from scratch by the auditor under the same `AIW_E2E=1` env shows FAILED. The Builder's "Hermetic smoke: PASSED" claim does match. KDR-003 grep matches. `pyproject.toml` / `uv.lock` no-diff matches. Status-surfaces flip matches. Lint and ruff match. The single false claim is the AIW_E2E smoke result.

## Gate summary (cycle 2 re-run)

| Gate | Command | Result |
| ---- | ------- | ------ |
| Tests | `uv run pytest` | ✅ **807 passed / 10 skipped / 22 warnings in 46.90s** (+2 from new strip-code-fence regression tests) |
| Layer rule | `uv run lint-imports` | ✅ 5 contracts kept, 0 broken |
| Style | `uv run ruff check` | ✅ All checks passed |
| Hermetic smoke | `uv run pytest tests/mcp/test_run_audit_cascade.py tests/mcp/test_scaffold.py -v` | ✅ 19/19 passed |
| Cascade primitive (regression) | `uv run pytest tests/graph/test_audit_cascade.py -v` | ✅ 15/15 passed (13 prior + 2 new) |
| **Wire-level smoke (mandatory)** | `AIW_E2E=1 uv run pytest tests/mcp/test_run_audit_cascade_e2e.py -v` | ✅ **`1 passed in 14.54s`** — auditor-verified, real `auditor-sonnet` Claude CLI subprocess |
| Full graph layer | `uv run pytest tests/graph/ -q` | ✅ 111/111 passed (cross-task `_audit_verdict_node` amendment introduced no regression) |
| KDR-003 grep | `grep -rn "anthropic\|ANTHROPIC_API_KEY" ai_workflows/` | ✅ only 2 docstring negative-assertions in pre-existing `planner.py:21` + `claude_code.py:15`. |

**Cycle-2 gate integrity verdict:** Builder's report (`807 passed / 10 skipped`, lint-imports 5/5, ruff clean, AIW_E2E `1 passed in 16.00s`) all verified by independent re-run. Timing variance on AIW_E2E (16.00s Builder vs. 14.54s auditor) is expected — Claude CLI subprocess latency. Builder honesty restored.

## Issue log — cross-task follow-up

| ID | Severity | Owner / next touch point | Status |
| -- | -------- | ----------------------- | ------ |
| M12-T05-HIGH-01 | HIGH | Cycle 2 Builder, this task | ✅ RESOLVED (cycle 2, 2026-04-28) — `_strip_code_fence` shared helper landed in `graph/audit_cascade.py:80-103`; both `_audit_verdict_node` (`audit_cascade.py:780`) and `run_audit_cascade` tool (`mcp/server.py:499`) call it before `model_validate_json`; AIW_E2E re-run PASSES (`1 passed in 14.54s`). |
| M12-T05-MED-01 | MED  | Cycle 2 Builder + loop controller | ✅ RESOLVED (cycle 2, 2026-04-28) — CHANGELOG `[Unreleased]` block now retracts the false cycle-1 PASS claim and quotes the actual cycle-2 re-run summary line (`CHANGELOG.md:64-90`). |
| M12-T05-MED-02 | MED  | Cycle 2 Builder, this task | ✅ RESOLVED (cycle 2, 2026-04-28) — `tests/mcp/conftest.py:42-56` docstring now documents the auditor-tier-registry hazard with explicit references to both established workaround patterns (per-test override at `test_run_audit_cascade.py` and real-registry restoration at `test_run_audit_cascade_e2e.py`). Builder picked Option B (doc) over Option A (extend autouse fixture); justified — both established patterns work and the doc closes the breadcrumb gap. |
| M12-T05-LOW-01 | LOW  | Future consideration only | NOTED — no action required; system prompt left as-is per cycle-1 recommendation. |

**Cross-task observation (RESOLVED in cycle 2):** `_audit_verdict_node` at `audit_cascade.py:780` now calls `_strip_code_fence(auditor_raw)` before `model_validate_json` — the same shared helper the standalone tool uses. T03's `audit_cascade_enabled=True` env-var path is no longer latently broken under real-Claude conditions; both call sites now tolerate markdown-fenced JSON output. Tests 14-15 in `tests/graph/test_audit_cascade.py` pin the fenced + unfenced shapes (15/15 PASS).

## Cycle 2 re-audit — verification log (2026-04-28)

**Gates re-run from scratch:**

| Gate | Command | Result |
| ---- | ------- | ------ |
| Tests | `uv run pytest` | ✅ **807 passed / 10 skipped / 22 warnings in 46.90s** (+2 vs. cycle 1, matches Builder claim of new strip-code-fence regression tests) |
| Layer rule | `uv run lint-imports` | ✅ 5 contracts kept, 0 broken |
| Style | `uv run ruff check` | ✅ All checks passed |
| Wire-level smoke (mandatory) | `AIW_E2E=1 uv run pytest tests/mcp/test_run_audit_cascade_e2e.py -v` | ✅ **`1 passed in 14.54s`** — `test_inline_artefact_audited_by_real_sonnet_e2e PASSED` against real `auditor-sonnet` Claude CLI subprocess |
| Cascade primitive regression | `uv run pytest tests/graph/test_audit_cascade.py -v` | ✅ 15/15 PASS (13 prior + 2 new strip-code-fence regression tests) |
| MCP tool hermetic | `uv run pytest tests/mcp/test_run_audit_cascade.py tests/mcp/test_scaffold.py -v` | ✅ 19/19 PASS |
| Full graph layer | `uv run pytest tests/graph/ -q` | ✅ 111/111 PASS — cross-task `_audit_verdict_node` amendment introduced no regression |

**HIGH-01 fix verification (cross-checked against issue file's Option A recommendation):**

- ✅ `_strip_code_fence(raw_text: str) -> str` helper exists at `graph/audit_cascade.py:80-103` — alongside `AuditVerdict` per Option A guidance.
- ✅ Helper exported in `__all__` at `graph/audit_cascade.py:75` (`["AuditVerdict", "_strip_code_fence", "audit_cascade_node"]`).
- ✅ `_audit_verdict_node` calls helper before `model_validate_json` at `graph/audit_cascade.py:780` — latent T02 bug closed for `audit_cascade_enabled=True` workflows.
- ✅ `mcp/server.py` imports `_strip_code_fence` (line 93) and calls it before `AuditVerdict.model_validate_json(...)` at `server.py:499`.
- ✅ Two new hermetic regression tests in `tests/graph/test_audit_cascade.py:1058-1104` pin fenced (`test_strip_code_fence_handles_markdown_wrapped_json`) + unfenced (`test_strip_code_fence_passes_unfenced_json_unchanged`) shapes.
- ✅ AIW_E2E re-run `1 passed in 14.54s` — auditor-verified, not Builder-claimed.

**MED-01 fix verification:**

- ✅ CHANGELOG `[Unreleased]` block lines 64-66 explicitly retract the cycle-1 false PASS: `**AIW_E2E smoke result (cycle 1 — RETRACTED):**`.
- ✅ CHANGELOG lines 86-90 quote the actual cycle-2 pytest summary line (`**AIW_E2E smoke result (cycle 2):** **1 passed in 16.00s**`). Builder's quoted output (`16.00s`) differs trivially from auditor's re-run (`14.54s`) — both are valid PASSes against the real subprocess; the timing variance is expected (network + Claude CLI latency).

**MED-02 fix verification:**

- ✅ `tests/mcp/conftest.py:42-56` docstring now contains the IMPORTANT hazard note explaining that `auditor_tier_registry` delegates to `planner_tier_registry` and is implicitly stubbed by the autouse fixture, with explicit pointers to both established workaround patterns (option a: per-test monkeypatch of `mcp_server_module.auditor_tier_registry`; option b: restore real `planner.planner_tier_registry`).

**Sanctioned scope amendment (acknowledged):** Cycle 2 added `ai_workflows/graph/audit_cascade.py` to the diff (`_strip_code_fence` helper + `_audit_verdict_node` amendment). The original spec AC stated "No `ai_workflows/graph/` diff", but this scope expansion was the auditor's explicit cycle-1 HIGH-01 Option A recommendation (single shared helper landing in `graph/audit_cascade.py` so the cascade primitive picks up the same fix). Per `/clean-implement` auditor-agreement bypass mechanic, this is a sanctioned cross-task fix the loop controller would have stamped. No additional HIGH on this — the scope amendment is documented + justified.

**Status surface re-verification:**

- ✅ Spec line 3: `**Status:** Complete (2026-04-28).` (no `✅` prefix, but matches T04 sibling pattern; cosmetic-only).
- ✅ M12 README line 68 (task table): `Complete (2026-04-28)` (matches spec).
- ✅ M12 README lines 32-33 (exit-criteria 7 + 8): both `[x]` ticked.
- ✅ `architecture.md:105`: `M12 T05`.
- ✅ `adr/0004:56`: `M12 T05`.
- ✅ `adr/0004:73`: `M12 T05`.

All four surfaces (spec / README task-table / README exit-criteria / cross-doc references) agree.

## Deferred to nice_to_have

(Not applicable — no findings forward-deferrable to `nice_to_have.md`.)

## Security review (2026-04-28)

### Scope

Files inspected: `ai_workflows/mcp/server.py`, `ai_workflows/mcp/schemas.py`, `ai_workflows/graph/audit_cascade.py` (`_strip_code_fence`), `ai_workflows/primitives/storage.py` (read-artifact + list-runs query paths), `ai_workflows/primitives/llm/claude_code.py` (subprocess integrity), `ai_workflows/primitives/retry.py`. Wheel at `dist/jmdl_ai_workflows-0.3.1-py3-none-any.whl` inspected via Python `zipfile`. No `pyproject.toml` / `uv.lock` changes — dependency-auditor not triggered.

### 1. KDR-003 boundary — no `ANTHROPIC_API_KEY` reads

`grep -rn "ANTHROPIC_API_KEY" ai_workflows/` — zero hits. New `run_audit_cascade` tool dispatches to `auditor-sonnet` / `auditor-opus` exclusively via `ClaudeCodeRoute` (`asyncio.create_subprocess_exec("claude", ...)` at `claude_code.py:135`). No new `anthropic` SDK import anywhere in the diff. KDR-003 boundary holds.

### 2. SQL injection — `run_id_ref` and `artefact_kind` inputs

`storage.read_artifact(run_id, kind)` at `storage.py:626-628` uses `"SELECT * FROM artifacts WHERE run_id = ? AND kind = ?"` with parameterised `?` placeholders. Both `run_id` and `kind` travel through `tuple(run_id, kind)` into `sqlite3.execute` — no string interpolation. The `_list_runs_sync` f-string at `storage.py:474-478` builds `where_sql` from hardcoded clause strings (`"status = ?"`, `"workflow_id = ?"`); user values are in the `params` tuple, not the SQL template. No SQL injection surface.

### 3. Path traversal — `artefact_kind` and `run_id_ref`

Both values are used only as column values in parameterised SQL queries (`artifacts WHERE run_id = ? AND kind = ?`). Neither is used in a file path, `os.path.join`, `open()`, or any shell invocation. No path traversal surface.

### 4. `inline_artefact_ref` prompt embedding

`_make_standalone_auditor_prompt_fn` at `server.py:247` calls `json.dumps(artefact, indent=2)` and embeds the result in the prompt between `<artefact>...</artefact>` XML tags. This is operator-supplied content flowing to an LLM prompt — no shell execution, no SQL, no file I/O occurs downstream of this embedding. Under the single-user local threat model the operator IS the user; adversarial prompt injection here is the operator attacking their own Claude session. Not a framework defect.

### 5. `_strip_code_fence` — ReDoS / unbounded memory

`_strip_code_fence` at `audit_cascade.py:80-103` is pure string manipulation: `.strip()`, `.startswith("` `` ` `` `` ` `` `` ` `` `")`, one `.split("\n", 1)` (bounded to at most 2 parts), and a trailing `text[:-3]` slice. No regex, no loop, O(n) on input length. The input is the auditor LLM's raw output which `tiered_node` already holds in memory. No ReDoS or unbounded-memory risk.

### 6. `json.loads(row["payload_json"])` error handling

`_resolve_audit_artefact` at `server.py:165` calls `json.loads(row["payload_json"])` on data written by the framework's own `storage.write_artifact` (framework-trusted path). If somehow the stored payload is malformed JSON (e.g. manual DB edit or storage corruption), `json.loads` raises `json.JSONDecodeError` which is NOT caught here — it propagates up to the tool body, where the only active handler is `except (UnknownTierError, NonRetryable, RetryableSemantic)` at `server.py:485`. This means a corrupt `payload_json` row produces an unhandled `JSONDecodeError` that FastMCP converts to a generic internal server error rather than a descriptive `ToolError`.

This is an Advisory-level robustness gap (not a security issue — the data was written by the framework itself, not by an attacker). Under the single-user local threat model this cannot be exploited, but it makes debugging corrupt storage rows harder than necessary.

### 7. Subprocess integrity — `ClaudeCodeRoute`

`claude_code.py:119-133`: argv is built as a Python list (`argv: list[str]`), extended via `argv.extend(["--system-prompt", system])` where `system` is a string passed directly as a positional argument (not shell-concatenated). `asyncio.create_subprocess_exec(*argv, ...)` uses `exec` semantics — no shell interpretation. `stdin=asyncio.subprocess.PIPE`, `stdout=asyncio.subprocess.PIPE`, `stderr=asyncio.subprocess.PIPE` — all three streams captured. Timeout enforced via `asyncio.wait_for(..., timeout=self._per_call_timeout_s)` at `claude_code.py:143-153`; on `TimeoutError` the process is killed and `subprocess.TimeoutExpired` raised. `subprocess.CalledProcessError` carries `stderr=stderr_bytes` and `retry.py:255` logs stderr (up to 2000 chars per `_extract_stderr` at `retry.py:274`). All KDR-003 integrity checks pass.

### 8. Subprocess CWD / env leakage

`asyncio.create_subprocess_exec` is called without an explicit `env=` argument, inheriting the parent environment. For the Claude Code OAuth subprocess this is correct by design — the `claude` CLI uses OAuth tokens stored in the OS keyring / session, not from environment variables. No `GEMINI_API_KEY`, `ANTHROPIC_API_KEY`, or other secret key is passed to the `claude` subprocess (KDR-003 boundary). No `cwd=` argument means the subprocess inherits the MCP server's working directory (operator-set), which is not attacker-controlled in the single-user local deployment. No concern.

### 9. Wheel contents — migrations inclusion is intentional

`dist/jmdl_ai_workflows-0.3.1-py3-none-any.whl` contains `migrations/001_initial.sql`, `migrations/002_reconciliation.rollback.sql`, etc. This is intentional and load-bearing: `pyproject.toml:92-103` explicitly includes `"migrations" = "migrations"` as package data so `yoyo-migrations` can apply schema migrations from an installed wheel. `_default_migrations_dir()` at `storage.py:212` resolves to `Path(__file__).resolve().parent.parent.parent / "migrations"` which in a wheel install points to `site-packages/migrations/`. No secrets, no `.env`, no design docs in the wheel. The migration files are SQL DDL only. Intentional inclusion, no defect.

### 10. Logging hygiene

`grep -rn "GEMINI_API_KEY\|ANTHROPIC_API_KEY\|Bearer \|Authorization" ai_workflows/` — zero hits. No API keys or auth tokens observed in log records. The `prompt=` / `messages=` LLM content is not logged by the new MCP tool helpers or the `_strip_code_fence` helper. No advisory finding.

### 11. SQLite path — `AIW_STORAGE_DB` env var

`default_storage_path()` at `storage.py:72-95` honours `AIW_STORAGE_DB` env var via `Path(env_override).expanduser()`. This gives the operator full control of the storage path (operator-owned risk by design; single-user local). No normalisation beyond `expanduser()` — a relative path in `AIW_STORAGE_DB` is accepted as-is. This is acceptable for a single-user local tool; the operator controls the environment variable. Default is `~/.ai-workflows/storage.sqlite` (user-owned dir). No concern under the threat model.

### 12. MCP HTTP transport bind address

Not changed by T05. No new bind-address or CORS configuration introduced.

---

### Findings summary

### Critical — must fix before publish/ship

None.

### High — should fix before publish/ship

None.

### Advisory — track; not blocking

**SEC-ADV-01 — `json.loads(row["payload_json"])` in `_resolve_audit_artefact` is not wrapped in a try/except**

File: `ai_workflows/mcp/server.py:165`. Threat-model item: storage-path robustness (§5 SQLite paths). If `payload_json` in the `artifacts` table is malformed (e.g. manual DB edit, storage corruption), `json.loads` raises `json.JSONDecodeError` which escapes the `try` block at `server.py:485` (that block only catches `UnknownTierError`, `NonRetryable`, `RetryableSemantic`). FastMCP converts the unhandled exception to a generic error response; the operator sees no actionable message. Under the single-user local threat model this cannot be exploited — the data was written by the framework. Advisory because it degrades debuggability of corrupt storage rows.

Action: In a future task, wrap `json.loads(row["payload_json"])` in a try/except and raise `ToolError(f"stored artefact payload_json is not valid JSON for run_id={run_id!r}, kind={kind!r}")`. Not blocking publish.

---

### Verdict: SHIP

## Propagation status

- **No forward-deferrals filed.** All cycle-1 findings (HIGH-1 + MED-1 + MED-2) resolved in cycle 2 of `/auto-implement m12 t05`. All cycle-2 sr-dev/sr-sdet BLOCK + FIX findings (SR-DEV-BLOCK-01, SR-SDET-BLOCK-01, SR-SDET-FIX-01, SR-SDET-FIX-02) resolved in cycle 3. No carry-over written to a future task spec. (TA-T05-LOW-02's deferred item — cascade-reuse framing rewrite to T07 — was already deferred by spec hardening, not by this audit.)
- **Cycle-2 cross-task observation closed in-place:** the latent `_audit_verdict_node` parse-without-fence-strip bug was fixed in the same cycle as T05's tool-body fix; T03's env-var-gated `audit_cascade_enabled=True` path is no longer broken under real-Claude conditions. No separate task needed.

## Cycle 3 re-audit — verification log (2026-04-28)

**Gates re-run from scratch:**

| Gate | Command | Result |
| ---- | ------- | ------ |
| Tests | `uv run pytest` | ✅ **`809 passed, 10 skipped, 22 warnings in 47.63s`** (matches Builder claim of +2 cycle-3 tests vs. cycle 2's 807) |
| Layer rule | `uv run lint-imports` | ✅ 5 contracts kept, 0 broken |
| Style | `uv run ruff check` | ✅ All checks passed |
| MCP tool hermetic | `uv run pytest tests/mcp/test_run_audit_cascade.py -v` | ✅ **8/8 PASS** in 0.69s (6 prior + 2 new cycle-3 tests) |
| **Wire-level smoke (mandatory)** | `AIW_E2E=1 uv run pytest tests/mcp/test_run_audit_cascade_e2e.py -v` | ✅ **`1 passed in 13.65s`** — `test_inline_artefact_audited_by_real_sonnet_e2e PASSED` against real `auditor-sonnet` Claude CLI subprocess |

**Cycle-3 fix verification (mutation-tested):**

- ✅ **SR-DEV-BLOCK-01 / SR-SDET-BLOCK-01 (RetryableTransient):**
  - `mcp/server.py:109-114` import expanded to include `RetryableTransient` (multi-line form).
  - `mcp/server.py:490` except tuple now contains all four exceptions: `(UnknownTierError, NonRetryable, RetryableSemantic, RetryableTransient)`.
  - Test 7 (`test_run_audit_cascade_raises_tool_error_on_retryable_transient`) seeds `RetryableTransient("simulated 429")` into stub adapter; asserts `pytest.raises(ToolError, match="audit invocation failed")`.
  - **Mutation verified:** Auditor removed `RetryableTransient` from the except tuple (`sed` mutation) and re-ran test 7 — test FAILED with bare `RetryableTransient: simulated 429` propagating through (not caught as `ToolError`). Source restored. Test genuinely exercises the new catch arm.
- ✅ **SR-SDET-FIX-01 (passed=False / suggested_approach branch):**
  - Test 8 (`test_run_audit_cascade_surfaces_suggested_approach_when_auditor_fails`) consumes `_AUDIT_FAIL_JSON` (no longer dead constant).
  - Asserts `output.passed is False`, `output.suggested_approach == "Try harder"`, `output.verdicts_by_tier["auditor-opus"].passed is False`, `output.verdicts_by_tier["auditor-opus"].failure_reasons == ["weak content"]`, `len(_StubAuditorAdapter.calls) == 1`.
  - **Mutation verified:** Auditor inverted the conditional at `server.py:514` from `if not verdict.passed else None` to `if verdict.passed else None`. Test 8 FAILED with `AssertionError: assert None == 'Try harder'`. Source restored. Test genuinely catches the inverted-condition regression.
- ✅ **SR-SDET-FIX-02 (tautological by_role assertion):**
  - Test 5's assertion at `tests/mcp/test_run_audit_cascade.py:262-265` now reads `assert "auditor" in output.by_role, (...)` followed by `assert output.by_role["auditor"] == 0.0`.
  - **Mutation verified:** Auditor changed `role="auditor"` to `role=""` at both `mcp/server.py:476` and the stub `tests/mcp/test_run_audit_cascade.py:115`. Test 5 FAILED with `AssertionError: expected 'auditor' key in by_role; got ['']` and `assert 'auditor' in {'': 0.0}`. Both sources restored. Membership check genuinely pins key existence rather than tolerating absent key via `.get()` default.

**Builder discipline verified:**

- ✅ Cycle-3 source touch limited to `ai_workflows/mcp/server.py` (`+2` lines: import expansion + except-tuple expansion). No other production-tree file touched in cycle 3.
- ✅ Cycle-3 test touch limited to `tests/mcp/test_run_audit_cascade.py` (3 changes per Builder report: test 5 assertion tighten + test 7 added + test 8 added).
- ✅ `CHANGELOG.md:86-91` cycle-3 amendment cites all three fixes (BLOCK-01, FIX-01, FIX-02) and lines 93-97 quote the cycle-2 AIW_E2E result; auditor-verified cycle-3 AIW_E2E re-run (`1 passed in 13.65s`) consistent with the cycle-2 quoted result (`1 passed in 16.00s`) — timing variance expected.
- ✅ Builder did NOT touch the spec (`task_05_run_audit_cascade_mcp_tool.md`) in cycle 3 (the `git status` modifications reflect cycle-1 status-flip; auditor diff verified pre-cycle-3 baseline already had `Status: Complete (2026-04-28)` and ticked carry-overs).
- ✅ Builder did NOT touch the issue file (`task_05_issue.md`) in cycle 3 (per non-negotiable; only the auditor writes here).
- ✅ No `git commit` / `git push` / `git tag` / `git merge` / `git rebase` / `uv publish` operations performed by the Builder in cycle 3.

**Updated issue log status (cycle 3):**

| ID | Severity | Owner / next touch point | Status |
| -- | -------- | ----------------------- | ------ |
| M12-T05-HIGH-01 | HIGH | Cycle 2 Builder, this task | ✅ RESOLVED (cycle 2, 2026-04-28) |
| M12-T05-MED-01 | MED  | Cycle 2 Builder + loop controller | ✅ RESOLVED (cycle 2, 2026-04-28) |
| M12-T05-MED-02 | MED  | Cycle 2 Builder, this task | ✅ RESOLVED (cycle 2, 2026-04-28) |
| M12-T05-LOW-01 | LOW  | Future consideration only | NOTED — no action required |
| SR-DEV-BLOCK-01 / SR-SDET-BLOCK-01 (RetryableTransient) | BLOCK | Cycle 3 Builder, this task | ✅ RESOLVED (cycle 3, 2026-04-28) — `RetryableTransient` added to import + except tuple; test 7 mutation-verified |
| SR-SDET-FIX-01 (passed=False path) | FIX | Cycle 3 Builder, this task | ✅ RESOLVED (cycle 3, 2026-04-28) — test 8 added; mutation-verified |
| SR-SDET-FIX-02 (tautological by_role) | FIX | Cycle 3 Builder, this task | ✅ RESOLVED (cycle 3, 2026-04-28) — test 5 assertion tightened; mutation-verified |
| SR-DEV-ADV-01 / 02 / 03 / 04 + SR-SDET-ADV-01 / 02 / 03 | ADV | Future consideration only | NOTED — no action required this cycle |

**Cycle-3 verdict:** ✅ PASS — FUNCTIONALLY CLEAN, ready for **security gate re-run + team gate re-run** (sr-dev + sr-sdet should re-grade and confirm their BLOCK is resolved).

## Sr. SDET re-review (2026-04-28) — cycle 3

**Test files reviewed:**
- `/home/papa-jochy/prj/ai-workflows/tests/mcp/test_run_audit_cascade.py` (8 hermetic tests — 6 prior + 2 new cycle-3)
- `/home/papa-jochy/prj/ai-workflows/ai_workflows/mcp/server.py` (lines 109–114, 488–517 — source under test)
- `/home/papa-jochy/prj/ai-workflows/ai_workflows/graph/tiered_node.py` (lines 318–375 — RetryableTransient re-raise path)
- `/home/papa-jochy/prj/ai-workflows/ai_workflows/primitives/cost.py` (lines 154–170 — by_role implementation)

**Skipped (out of scope):** `tests/mcp/test_run_audit_cascade_e2e.py`, `tests/mcp/test_scaffold.py`, `tests/mcp/conftest.py`, `tests/graph/test_audit_cascade.py` — unchanged relative to cycle 2; cycle-3 scope is the three specific fixes called out in cycle-2 findings.

**Verdict:** SHIP

### BLOCK — tests pass for the wrong reason

None. SR-SDET-BLOCK-01 resolved (see verification below).

### FIX — fix-then-ship

None. SR-SDET-FIX-01 and SR-SDET-FIX-02 resolved (see verification below).

### Advisory — track but not blocking

Cycle-2 advisories SR-SDET-ADV-01/02/03 carry forward unchanged. No new advisory findings introduced by the cycle-3 changes.

### Cycle-3 finding verification

**SR-SDET-BLOCK-01 — RetryableTransient now in import + except tuple; test 7 genuinely exercises the catch arm.**

- `server.py:109–114`: import block is now a multi-line form `from ai_workflows.primitives.retry import (NonRetryable, RetryableSemantic, RetryableTransient, RetryPolicy)`. `RetryableTransient` is present.
- `server.py:490`: except tuple reads `except (UnknownTierError, NonRetryable, RetryableSemantic, RetryableTransient) as exc`. All four exception types present.
- `test_run_audit_cascade.py:333–356` (test 7): seeds `_StubAuditorAdapter.script = [_RetryableTransient("simulated 429")]` — a live `RetryableTransient` instance, not a class. The stub's `complete()` at line 107 hits `isinstance(head, BaseException)` — `True`, since `RetryableTransient` inherits `Exception → BaseException`. It executes `raise head`, raising the instance from within `complete()`. `tiered_node` catches it at `tiered_node.py:322` (`except (RetryableTransient, NonRetryable) as exc`) and re-raises bare at line 345. The re-raised `RetryableTransient` then propagates to `server.py:490` which catches it and raises `ToolError("audit invocation failed: …")`. Test asserts `pytest.raises(ToolError, match="audit invocation failed")`.
- Mutation sensitivity confirmed by cycle-3 auditor: removing `RetryableTransient` from the except tuple causes test 7 to FAIL (bare `RetryableTransient` propagates through uncaught). The test genuinely exercises the new catch arm, not the surrounding machinery.
- No retry loop in `tiered_node` that would absorb the exception before it reaches the tool boundary: `tiered_node` has no internal retry; `RetryPolicy(max_transient_attempts=1, …)` is constructed but `RetryingEdge` (the graph-layer consumer of the policy) is not involved in the standalone-tool path.

**SR-SDET-FIX-01 — passed=False branch now exercised; suggested_approach and failure_reasons both asserted; _AUDIT_FAIL_JSON no longer dead.**

- `_AUDIT_FAIL_JSON` at line 124: `'{"passed": false, "failure_reasons": ["weak content"], "suggested_approach": "Try harder"}'`.
- Test 8 (`test_run_audit_cascade_surfaces_suggested_approach_when_auditor_fails`, lines 366–399) seeds `_StubAuditorAdapter.script = [(_AUDIT_FAIL_JSON, 0.0)]`. The stub returns the JSON string to `tiered_node`, which returns it under `"standalone_auditor_output"`. `_strip_code_fence` (no fence present) returns it unchanged; `AuditVerdict.model_validate_json` parses it into a real `AuditVerdict(passed=False, failure_reasons=["weak content"], suggested_approach="Try harder")`.
- `server.py:514`: `suggested_approach=verdict.suggested_approach if not verdict.passed else None`. With `verdict.passed=False`, `not verdict.passed=True`, so `suggested_approach="Try harder"`. Test asserts `output.suggested_approach == "Try harder"` (line 393) — value equality, not merely non-None. Inversion of the conditional would produce `None`; assertion would fail.
- Test also asserts `tier_verdict.failure_reasons == ["weak content"]` (line 398) — pins list propagation from `AuditVerdict` through `verdicts_by_tier`.
- Mutation sensitivity confirmed by cycle-3 auditor: inverting `server.py:514` condition causes test 8 to FAIL with `AssertionError: assert None == 'Try harder'`.

**SR-SDET-FIX-02 — by_role membership check now fires before value check; tautology eliminated.**

- Test 5, lines 261–265:
  ```python
  assert output.by_role is not None
  assert "auditor" in output.by_role, (
      f"expected 'auditor' key in by_role; got {list(output.by_role)}"
  )
  assert output.by_role["auditor"] == 0.0
  ```
- `assert "auditor" in output.by_role` at line 262 executes before the value check at line 265. `CostTracker.by_role` (cost.py:154–170) builds `{entry.role: cost}` from registered `TokenUsage` entries. The stub's `TokenUsage` carries `role="auditor"` (test file line 115). If `role` were `""`, `by_role` returns `{"": 0.0}`, and `assert "auditor" in {"": 0.0}` FAILS. `.get("auditor", 0.0)` would have returned `0.0` silently in that case — the tautology is eliminated.
- Mutation sensitivity confirmed by cycle-3 auditor: changing `role="auditor"` to `role=""` in the stub (line 115) causes test 5 to FAIL at the membership check with `AssertionError: expected 'auditor' key in by_role; got ['']`.
- Value check at line 265 (`output.by_role["auditor"] == 0.0`) is safe after the membership check — no `KeyError` risk. Correct two-step assertion shape.

### New coverage gap check (cycle-3 changes only)

- **Test 7 assertion completeness.** `match="audit invocation failed"` is a substring regex match against `ToolError("audit invocation failed: simulated 429")`. The test pins the catch-boundary transform (bare exception → labelled ToolError) but does not pin the exception's message suffix (`": simulated 429"`). This is acceptable: the goal is to verify the catch arm fires, not to lock in the exception's string representation which is implementation-internal.
- **Test 8 single-pass invariant.** `assert len(_StubAuditorAdapter.calls) == 1` (line 399) confirms the `passed=False` path does not trigger a retry loop — consistent with `RetryPolicy(max_transient_attempts=1, max_semantic_attempts=1)` in a standalone (non-RetryingEdge) call.
- **No fixture independence regression.** `_reset_stub` autouse fixture (lines 154–164) resets `_StubAuditorAdapter.script = []` and `calls = []` before every test. Tests 7 and 8 set their own `script` at test-body start. Class-level mutable state cannot bleed between tests.
- **No hermetic-gating regression.** Tests 7 and 8 are plain `@pytest.mark.asyncio` — no `AIW_E2E` skip needed; they use the stub adapter only. E2E file unchanged and still correctly gated.

### What passed review (one-line per lens)

- Tests-pass-for-wrong-reason: SR-SDET-BLOCK-01 and SR-SDET-FIX-02 both resolved with mutation-verified assertions; no new tautologies or wrong-reason passes observed in the cycle-3 additions.
- Coverage gaps: SR-SDET-FIX-01 resolved — `passed=False` branch, `suggested_approach` conditional, and `failure_reasons` propagation are all now asserted with value equality; `_AUDIT_FAIL_JSON` is no longer a dead constant.
- Mock overuse: unchanged from cycle 2; no new mocks introduced.
- Fixture / independence: `_reset_stub` autouse correctly covers tests 7 and 8; no order-dependent state; `monkeypatch` reverts patches after each test.
- Hermetic-vs-E2E gating: clean; tests 7 and 8 are hermetic; E2E gate unchanged.
- Naming / assertion-message hygiene: test 7 name (`test_run_audit_cascade_raises_tool_error_on_retryable_transient`) and test 8 name (`test_run_audit_cascade_surfaces_suggested_approach_when_auditor_fails`) both state the scenario and expected outcome clearly; assertion failure messages are present on the membership check (test 5 line 263).

## Sr. SDET review (2026-04-27)

**Test files reviewed:**
- `tests/mcp/test_run_audit_cascade.py` (NEW, 6 hermetic tests)
- `tests/mcp/test_run_audit_cascade_e2e.py` (NEW, 1 AIW_E2E-gated test)
- `tests/mcp/test_scaffold.py` (4→5 tool count; renamed test)
- `tests/mcp/conftest.py` (cycle-2 hazard docstring addition)
- `tests/graph/test_audit_cascade.py` (cycle-2 +2 `_strip_code_fence` regression tests)

**Skipped (out of scope):** `tests/workflows/test_slice_refactor_fanout.py` (unrelated to T05 scope).

**Verdict:** BLOCK

### BLOCK — tests pass for the wrong reason

#### SR-SDET-BLOCK-01 — `RetryableTransient` gap: production catch tuple missing, and no hermetic test seeds it

**Lens:** Tests pass for the wrong reason (Lens 1) — mirrors sr-dev SR-DEV-BLOCK-01.

**Test file:line:** `tests/mcp/test_run_audit_cascade.py` (no test for `RetryableTransient` path).
**Source line:** `ai_workflows/mcp/server.py:485`.

The `except (UnknownTierError, NonRetryable, RetryableSemantic)` tuple at `server.py:485` does not include `RetryableTransient`. `tiered_node` re-raises `RetryableTransient` bare (verified at `tiered_node.py:345`: `raise` inside `except (RetryableTransient, NonRetryable)`) — so a network blip, 429, or subprocess timeout propagates through `await auditor_node(state, config)` uncaught, landing as an opaque FastMCP internal error rather than `ToolError("audit invocation failed: …")`.

The hermetic test suite never seeds `RetryableTransient` into `_StubAuditorAdapter.script`. All six tests seed either a `(text, cost)` success tuple or rely on the validator path; no test exercises the transient-error catch arm. Because the exception never appears in the test inputs, the missing `except` arm is invisible — the tests pass regardless of whether `RetryableTransient` is in the tuple or not.

**Action/Recommendation:** Cycle-3 Builder adds `RetryableTransient` to the import at `server.py:109` (from `ai_workflows.primitives.retry`) and to the except tuple at `server.py:485`. Add one new test:
```python
async def test_run_audit_cascade_raises_tool_error_on_retryable_transient(...):
    from ai_workflows.primitives.retry import RetryableTransient
    _StubAuditorAdapter.script = [RetryableTransient("simulated 429")]
    ...
    with pytest.raises(ToolError, match="audit invocation failed"):
        await tool.fn(payload)
```
This is the test sr-dev described in SR-DEV-BLOCK-01. The test fails today (raises `RetryableTransient` uncaught rather than `ToolError`); it passes after the one-line fix.

### FIX — fix-then-ship

#### SR-SDET-FIX-01 — `_AUDIT_FAIL_JSON` defined but never used; `passed=False` path + `suggested_approach` logic uncovered

**Lens:** Coverage gap — AC implied behaviour untested (Lens 2).

**Test file:line:** `tests/mcp/test_run_audit_cascade.py:124–127` (`_AUDIT_FAIL_JSON` constant), `:509` in source (`server.py`).

`_AUDIT_FAIL_JSON = '{"passed": false, "failure_reasons": ["weak content"], "suggested_approach": "Try harder"}'` is defined at line 124 but never referenced in any test. The `passed=False` path is never exercised by the hermetic suite. Specifically uncovered:

1. `server.py:509` — `suggested_approach=verdict.suggested_approach if not verdict.passed else None` — the conditional branch that populates `suggested_approach` on a failed audit is dead in tests. A bug that inverted the condition (`if verdict.passed else None`) would pass all six tests.
2. `output.verdicts_by_tier[tier]["failure_reasons"]` is never asserted against a non-empty list; a bug that dropped `failure_reasons` from the `AuditVerdict` propagation would be invisible.
3. `output.suggested_approach` is only asserted to be `None` (the `passed=True` case). A bug returning `suggested_approach=None` on `passed=False` (e.g. removing the conditional) is undetected.

The spec's §Tests description for test 5 only requires asserting the pass case (`passed=True`, `suggested_approach is None`). No hermetic test was called out for the fail case. This is a gap the spec implied through the `RunAuditCascadeOutput.suggested_approach` field's documented semantics ("Populated on `passed=False`; None on `passed=True`") but did not enumerate as a named test.

**Action/Recommendation:** Cycle-3 Builder adds a seventh hermetic test using `_AUDIT_FAIL_JSON`:
```
test_run_audit_cascade_with_inline_artefact_surfaces_suggested_approach_when_auditor_fails
```
Asserts: `output.passed is False`, `output.suggested_approach == "Try harder"`, `output.verdicts_by_tier["auditor-opus"].failure_reasons == ["weak content"]`. This converts the dead constant into a live regression guard.

#### SR-SDET-FIX-02 — `by_role.get("auditor", 0.0) == 0.0` is tautological on a zero-cost stub; does not pin key membership

**Lens:** Tests pass for the wrong reason — trivial assertion (Lens 1, secondary).

**Test file:line:** `tests/mcp/test_run_audit_cascade.py:262`.

```python
assert output.by_role.get("auditor", 0.0) == 0.0  # Max flat-rate
```

The stub returns `cost_usd=0.0`. If the "auditor" key is absent from `by_role`, `.get("auditor", 0.0)` returns the default `0.0`, making the assertion pass. If the "auditor" key is present with value `0.0`, the assertion also passes. The test cannot distinguish "key properly populated with zero cost" from "key missing entirely". A bug where `CostTracker.by_role` returned `{}` (empty) would pass this assertion silently (the preceding `assert output.by_role is not None` only checks for `None`, not for an empty dict or missing key).

The E2E test at `test_run_audit_cascade_e2e.py:88` does this correctly: `assert "auditor" in output.by_role`. The hermetic test should do the same.

**Action/Recommendation:** Replace the assertion at line 262 with:
```python
assert "auditor" in output.by_role, (
    f"expected 'auditor' key in by_role; got {list(output.by_role)}"
)
assert output.by_role["auditor"] == 0.0  # Max flat-rate stub returns 0.0
```
This pins key membership and value independently, matching the pattern the E2E test already uses.

### Advisory — track but not blocking

#### SR-SDET-ADV-01 — Test 6 docstring claims `"run_id"` key is also asserted absent from prompt; assertion is missing

**Lens:** Naming / assertion-message hygiene (Lens 6) — minor docstring/test body mismatch.

**Test file:line:** `tests/mcp/test_run_audit_cascade.py:281`, `:309–315`.

The test 6 module-level docstring at line 15–16 and the inline docstring at line 281 both state: "the literal string `"run_id"` as a JSON key MUST NOT appear". The spec's test description (§Tests test 6) makes the same claim. But the actual assertions at lines 310–315 only check `'"payload_json"'` and `'"created_at"'`; there is no `assert '"run_id"' not in all_content` guard. The `"run_id"` check is mentioned in two doc locations but not in the code.

**Action/Recommendation (non-blocking):** Either add `assert '"run_id"' not in all_content` to match the documented intent, or remove the claim from the docstrings. The inner payload `{"sample": "known dict"}` does not contain a `"run_id"` key, so the assertion would pass trivially today — but explicitly guarding it closes the doc/code gap and would catch a future regression where the storage row is passed unstripped.

#### SR-SDET-ADV-02 — `_strip_code_fence` regression tests cover ```` ```json ```` and bare JSON but not bare ` ``` ` (no language tag)

**Lens:** Coverage gap — boundary condition (Lens 2, advisory-grade).

**Test file:line:** `tests/graph/test_audit_cascade.py:1072`.

The two regression tests pin:
- ```` ```json\n{...}\n``` ```` (fenced with `json` language tag) — test 14.
- `{...}` (no fence) — test 15.

The `_strip_code_fence` helper's `startswith("` `` ` `` `` ` `` `` ` `` `")` branch handles bare ` ``` ` (no language tag) by design, and the sr-dev ADV-03 confirms the implementation is sound. However, no hermetic test pins the ` ``` \n{...}\n` `` ` `` `` ` `` `` ` `` `` shape — the most common alternative Claude emits. Not blocking: the sr-dev reviewed the implementation and found it correct, and the regex-free `.split("\n", 1)` handles all ```` ``` ```` prefixes uniformly. Advisory for future test completeness.

**Action/Recommendation (non-blocking):** Add a third variant test for ` ``` ` (no `json` tag) to `tests/graph/test_audit_cascade.py`. Not required for cycle 3.

#### SR-SDET-ADV-03 — `tier_ceiling="sonnet"` path untested in hermetic suite; `verdicts_by_tier` key is always `"auditor-opus"`

**Lens:** Coverage gap — boundary condition (Lens 2, advisory-grade).

**Test file:line:** `tests/mcp/test_run_audit_cascade.py` (no test with `tier_ceiling="sonnet"`).

All hermetic tests use the default `tier_ceiling` (resolves to `"opus"`); the `verdicts_by_tier` key is always `"auditor-opus"` in the assertions. The `tier_ceiling="sonnet"` branch (which sets `auditor_tier_name = "auditor-sonnet"`) is exercised only by the AIW_E2E test. A bug that hard-coded `"auditor-opus"` as the key regardless of `tier_ceiling` would pass all hermetic tests. The code path at `server.py:460` is trivial (`f"auditor-{payload.tier_ceiling}"`), so the risk is low. Advisory — the E2E test covers it functionally; adding a hermetic parametrize for `tier_ceiling` would eliminate the gap.

**Action/Recommendation (non-blocking):** Parametrize test 5 over `tier_ceiling` values `["sonnet", "opus"]` and assert `verdicts_by_tier[f"auditor-{tier_ceiling}"]` is present. Not required for cycle 3.

### What passed review (one-line per lens)

- **Tests-pass-for-wrong-reason:** Two findings — BLOCK-01 (`RetryableTransient` catch gap, no hermetic test seeds it); FIX-02 (`by_role.get` tautological on zero-cost stub, doesn't pin key membership).
- **Coverage gaps:** FIX-01 (`_AUDIT_FAIL_JSON` dead constant — `passed=False` / `suggested_approach` logic uncovered); ADV-01 (doc claims `"run_id"` wrapper key asserted absent, assertion missing); ADV-02 (bare-fence shape unexercised); ADV-03 (`tier_ceiling="sonnet"` hermetically unexercised).
- **Mock overuse:** None observed. `_StubAuditorAdapter` correctly replaces `ClaudeCodeSubprocess` at the right boundary; the five real primitives (`CostTracker`, `RetryPolicy`, `SQLiteStorage`, `TierConfig`, `AuditVerdict`) all use real instances. Stub is `spec`-equivalent by constructor shape (takes `route`, `per_call_timeout_s`, `pricing`) — matches the real adapter's init signature.
- **Fixture / independence:** `_reset_stub` autouse fixture correctly resets class-level mutable state before each test. `tmp_db` correctly redirects storage via `monkeypatch.setenv` (auto-reverted). No order dependence observed. Conftest autouse hazard documented in cycle 2 (Option B taken — doc-only).
- **Hermetic-vs-E2E gating:** Correctly gated. `test_run_audit_cascade_e2e.py` is gated by `@pytest.mark.skipif(not os.getenv("AIW_E2E"), ...)`. AIW_E2E test verified by auditor (`1 passed in 14.54s`). No ungated network calls in hermetic suite.
- **Naming / assertion-message hygiene:** Test names are descriptive and spec-aligned. Assertion messages present on the multi-value asserts in test 6. Minor: `test_run_audit_cascade_with_inline_artefact_passes_when_auditor_passes` is accurate but does not name the `tier_ceiling` default — acceptable given the default-case framing. ADV-01 flags the doc/code mismatch.

## Sr. Dev review (2026-04-27)

**Files reviewed:** `ai_workflows/mcp/server.py`, `ai_workflows/mcp/schemas.py`, `ai_workflows/graph/audit_cascade.py` (lines 75–103 + 770–785), `ai_workflows/workflows/__init__.py` (lines 172–206), `tests/mcp/test_run_audit_cascade.py`, `tests/mcp/test_run_audit_cascade_e2e.py`, `tests/mcp/conftest.py`, `tests/mcp/test_scaffold.py`, `tests/graph/test_audit_cascade.py` (lines 1053–1104), `CHANGELOG.md` (lines 1–91), `.claude/skills/ai-workflows/SKILL.md` (lines 95–106).

**Skipped (out of scope):** `ai_workflows/workflows/planner.py` (not touched by this task — auditor tier definitions were not modified; reviewed only the `auditor_tier_registry()` helper that reads from it).

**Verdict:** BLOCK

### BLOCK — must-fix before commit

#### SR-DEV-BLOCK-01 — `RetryableTransient` escapes the `except` in `run_audit_cascade`, producing an opaque FastMCP internal error on network blips

**Lens:** Hidden bugs that pass tests.

**File:line:** `ai_workflows/mcp/server.py:483–486`.

**Code path:**

```python
try:
    verdict_state = await auditor_node(state, config)
except (UnknownTierError, NonRetryable, RetryableSemantic) as exc:
    raise ToolError(f"audit invocation failed: {exc}") from None
```

`tiered_node` (`graph/tiered_node.py:322–345`) catches `(RetryableTransient, NonRetryable)` in one `except` clause, logs them, and **re-raises both** with a bare `raise`. For `RetryableTransient` (429, 5xx, stream-interruption — the `classify()` output for transient provider errors), this means the exception propagates through `await auditor_node(...)` without being caught by the enclosing `except (UnknownTierError, NonRetryable, RetryableSemantic)`. FastMCP converts the unhandled `RetryableTransient` to a generic JSON-RPC internal error, stripping the diagnostic message the operator would need to understand the failure.

This is a real runtime gap: a `ClaudeCodeSubprocess` timeout or subprocess crash (common in CI and on slow machines) produces a bare exception at the MCP boundary instead of `ToolError("audit invocation failed: …")`.

**Why tests miss it.** `_StubAuditorAdapter` never raises `RetryableTransient` from its `script` (it only yields pre-set `(text, cost)` tuples or `BaseException` subclasses the caller scripts). No hermetic test seeds a `RetryableTransient` into the stub. The `except Exception` in the parse block (`server.py:500`) only catches exceptions from `_strip_code_fence` / `model_validate_json`, not from the node call.

**Reproduction:**

```python
_StubAuditorAdapter.script = [RetryableTransient("simulated 429")]
# tool body raises RetryableTransient, not ToolError
```

**Action/Recommendation.** Add `RetryableTransient` to the except tuple. The correct fix is a one-word change:

```python
except (UnknownTierError, NonRetryable, RetryableSemantic, RetryableTransient) as exc:
```

`RetryableTransient` is already imported transitively (it lives in `ai_workflows.primitives.retry` alongside `NonRetryable` — add it to the import at `server.py:109`). A matching test should seed `RetryableTransient("simulated transient")` into `_StubAuditorAdapter.script` and assert `ToolError` is raised.

Note: `UnknownTierError` in the existing catch is the one imported from `workflows._dispatch` (line 115 of `server.py`) — the `_dispatch`-layer class. The `tiered_node` path raises `NonRetryable` for unknown tier (not `UnknownTierError`), so that catch arm is dead in this context. It's harmless but confusing; this is flagged below as Advisory rather than a separate blocker since the missing `RetryableTransient` is the actionable item.

### FIX — fix-then-ship

*(none)*

### Advisory — track but not blocking

#### SR-DEV-ADV-01 — `UnknownTierError` catch in the tool's `except` clause is dead code for this code path

**Lens:** Defensive-code creep.

**File:line:** `ai_workflows/mcp/server.py:485`.

The `UnknownTierError` imported at line 115 is `workflows._dispatch.UnknownTierError`. `tiered_node` raises `NonRetryable` (not `UnknownTierError`) when the tier registry lookup fails (`tiered_node.py:226–229`). The `UnknownTierError` arm in the `except` tuple will never match in the standalone audit path (it is meaningful in `run_workflow` at line 347 where the dispatch layer validates tier overrides, but not here). Harmless as-is; the BLOCK-01 fix makes it more visible. Consider dropping it from the standalone-audit `except` tuple or leaving a comment explaining it's retained for symmetry. Advisory — no behaviour change either way.

#### SR-DEV-ADV-02 — `_StubAuditorAdapter` class-level mutable defaults are reset at fixture time, not class-definition time

**Lens:** Hidden bugs that pass tests (near-miss — not a current bug but a pattern that would become one if a test file fails before `_reset_stub` runs).

**File:line:** `tests/mcp/test_run_audit_cascade.py:84–85`.

```python
class _StubAuditorAdapter:
    script: list[Any] = []
    calls: list[dict] = []
```

These are class-level mutable defaults. The `_reset_stub` autouse fixture (line 154–164) reassigns them before each test, which is correct and matches the sibling pattern at `tests/graph/test_audit_cascade.py:150–153`. Not a current bug — the reset fixture fires reliably. However, if a future contributor copies only the class definition without the fixture reset, leaked state across tests would be invisible. The sibling file has the same pattern, so this is idiom-consistent; recording Advisory for awareness only.

#### SR-DEV-ADV-03 — `_strip_code_fence` does not handle ```` ``` ```` (no language tag, bare fence)

**Lens:** Simplification / correctness boundary.

**File:line:** `ai_workflows/graph/audit_cascade.py:96`.

```python
if text.startswith("```"):
```

This already handles the bare ` ``` ` case (no language tag) correctly — `split("\n", 1)` strips the fence line regardless of `json` suffix. The implementation is sound. Advisory: the docstring says "handles ` ```json `, ` ``` `, ` ```\n `, etc." which matches reality. No action needed; recorded for completeness.

#### SR-DEV-ADV-04 — `_resolve_audit_artefact` opens a fresh `SQLiteStorage` per call (not cached)

**Lens:** Simplification opportunities.

**File:line:** `ai_workflows/mcp/server.py:157`.

```python
storage = await SQLiteStorage.open(default_storage_path())
```

`SQLiteStorage.open` runs migrations (`_apply_migrations_sync` via `asyncio.to_thread`) on every call because `_initialized` is not persisted across instances. In the run-backed path this adds a `yoyo` migration scan per `run_audit_cascade` invocation. The other MCP tools (`list_runs`, `cancel_run`) do the same thing — this is the established MCP-surface idiom in this codebase, not an anomaly introduced by T05. Noting Advisory in case a future task wants to add a process-level storage singleton.

### What passed review (one-line per lens)

- **Hidden bugs:** One BLOCK finding — `RetryableTransient` missing from the `except` tuple in `run_audit_cascade`'s auditor-call try block.
- **Defensive-code creep:** `UnknownTierError` catch arm is dead for this code path (Advisory); no other unnecessary guards found.
- **Idiom alignment:** `structlog.get_logger(__name__)` not introduced (no new logging in the new code — existing `tiered_node` logger handles it); lazy import in `auditor_tier_registry()` matches prior lazy-import idioms for circular-avoidance; `@mcp.tool()` shape matches the four existing tools exactly.
- **Premature abstraction:** None observed. The four private helpers (`_resolve_audit_artefact`, `_build_standalone_audit_config`, `_build_audit_configurable`, `_make_standalone_auditor_prompt_fn`) each have one caller; they replace inline complexity rather than abstracting for a hypothetical second user. `auditor_tier_registry()` is a thin projection with one caller — justified by the circular-import constraint.
- **Comment / docstring drift:** Module docstring in `server.py` correctly cites M12 T05 and the four helpers. `_strip_code_fence` docstring cites the task ID and explains the *why*. `auditor_tier_registry()` docstring cites canonical owner and relationship. No restatement-of-code comments found in new code.
- **Simplification:** `_build_audit_configurable` could be inlined into `run_audit_cascade` (single caller, 6-line dict literal) — Advisory-quality, not surfaced as a finding given the spec explicitly named it as a distinct helper and it aids readability of the tool body.

## Sr. Dev re-review (2026-04-27) — cycle 3 BLOCK clearance

**Files reviewed (cycle-3 delta):** `ai_workflows/mcp/server.py` (lines 109–114, 488–491), `tests/mcp/test_run_audit_cascade.py` (lines 326–399 — tests 7 and 8, the two cycle-3 additions).

**Skipped (out of scope):** All files outside the cycle-3 delta — already reviewed in cycle 2; no changes made to them.

**Verdict:** SHIP

### BLOCK — must-fix before commit

*(none — SR-DEV-BLOCK-01 resolved; see clearance below)*

### SR-DEV-BLOCK-01 clearance

**Original finding:** `mcp/server.py:485` except tuple omitted `RetryableTransient`; a 429 / subprocess crash would escape the tool boundary as an opaque FastMCP internal error.

**Fix verified:**

1. `server.py:112` — `RetryableTransient` added to the import block alongside `NonRetryable`, `RetryableSemantic`, `RetryPolicy`. Import is clean; no shadowing, no duplicate import block. Verified via grep: the name appears exactly twice in `server.py` — once in the import (line 112) and once in the except tuple (line 490).

2. `server.py:490` — except tuple now reads `(UnknownTierError, NonRetryable, RetryableSemantic, RetryableTransient)`. The `from None` chain suppression is in place. The fix is a minimal, targeted addition with no side effects.

3. `tests/mcp/test_run_audit_cascade.py:333–356` — test 7 (`test_run_audit_cascade_raises_tool_error_on_retryable_transient`) seeds `_RetryableTransient("simulated 429")` directly into `_StubAuditorAdapter.script`. The autouse `_reset_stub` fixture has already cleared the script list before this test runs (verified: fixture at line 154–164 assigns `[]` unconditionally). The `isinstance(head, BaseException)` branch in `_StubAuditorAdapter.complete` (line 107) raises the exception directly, which flows up through `auditor_node` to the except tuple in `run_audit_cascade`. The assertion `pytest.raises(ToolError, match="audit invocation failed")` correctly pins the catch arm. The Auditor's mutation test (removing `RetryableTransient` from the tuple causes test 7 to FAIL) confirms the assertion exercises the new code, not a pre-existing catch.

4. Local import alias at test line 347 (`from ai_workflows.primitives.retry import RetryableTransient as _RetryableTransient`) does not shadow any module-level name — the test file has no top-level `RetryableTransient` import — and is consistent with the aliasing convention used for private test helpers in this file.

**No new bugs introduced by the cycle-3 fix.**

### FIX — fix-then-ship

*(none)*

### Advisory — track but not blocking

*(carry-over from cycle 2: SR-DEV-ADV-01 through SR-DEV-ADV-04 remain open and unresolved — none were blocking and none were touched by the cycle-3 fix)*

### What passed re-review (one-line per lens)

- **Hidden bugs:** SR-DEV-BLOCK-01 cleared. No new hidden bugs introduced by the cycle-3 delta.
- **Defensive-code creep:** No new defensive code in the cycle-3 delta. The `UnknownTierError` dead-arm advisory (SR-DEV-ADV-01) was not touched — still Advisory, not a blocker.
- **Idiom alignment:** Import placement matches the existing `primitives.retry` import block at `server.py:109–114`. Except-tuple style matches the other catch sites in `server.py`. No drift.
- **Premature abstraction:** None in the cycle-3 delta (two test functions, one import line, one except-tuple expansion).
- **Comment / docstring drift:** Test 7 docstring accurately describes the fix context, file:line reference, and expected behaviour. The historical `server.py:485` citation in the test docstring is a comment in a test, not a runtime assertion — acceptable.
- **Simplification:** No simplification opportunities in the minimal cycle-3 delta.
