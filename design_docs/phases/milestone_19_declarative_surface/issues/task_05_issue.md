# Task 05 — Rewrite `docs/writing-a-workflow.md` declarative-first — Audit Issues

**Source task:** [../task_05_writing_workflow_rewrite.md](../task_05_writing_workflow_rewrite.md)
**Audited on:** 2026-04-26 (cycle 1) · re-audited 2026-04-26 (cycle 2)
**Audit scope:** `docs/writing-a-workflow.md` (full rewrite — 677 lines after cycle 2), `docs/writing-a-custom-step.md` (cycle-1 stub forward-anchor for T06 — unchanged in cycle 2), `tests/docs/test_writing_workflow_snippets.py` (cycle 1: 18 tests; cycle 2: 23 tests after 5 cycle-2 regression-pin additions + `test_worked_example_matches_summarize_py` rewritten for byte-equality), `CHANGELOG.md` (cycle 1: `### Changed — M19 Task 05` block; cycle 2: new `### Fixed — M19 Task 05 (cycle 2)` block stacked above it), `design_docs/phases/milestone_19_declarative_surface/task_05_writing_workflow_rewrite.md` (status flipped to ✅ Done in cycle 1; AC + carry-over checkboxes flipped to `[x]`), `design_docs/phases/milestone_19_declarative_surface/README.md` (task-table row 05 flipped to ✅ Implemented in cycle 1). Cross-referenced against ADR-0008 §Documentation surface, `architecture.md` §3 + §9, the M19 README §Exit criteria #7, predecessor T01–T04 issue files. Verified the doc text against the live source for: `WorkflowSpec` field shape (`ai_workflows/workflows/spec.py`), `register`/`register_workflow` signatures (`ai_workflows/workflows/__init__.py`), `summarize` worked-example source (`ai_workflows/workflows/summarize.py` + `summarize_tiers.py`), CLI command shape (`ai_workflows/cli.py:519–545` — confirms `--gate-response`, no `--approve`, no `cancel`), `ExternalWorkflowImportError` shape (`ai_workflows/workflows/loader.py`), `StubLLMAdapter` import path (`ai_workflows/evals/_stub_adapter.py:64–129`), and `LiteLLMAdapter` monkey-patch site (`ai_workflows/graph/tiered_node.py:88`). Cycle-2 byte-match test executed via direct python invocation: 72 lines vs. 72 lines, equal True. All three task gates re-run from scratch each cycle (`uv run pytest`, `uv run lint-imports`, `uv run ruff check`).

**Status:** ✅ PASS (cycle 2). HIGH=0, MEDIUM=0; LOW-3 remains OPEN as out-of-scope deferral (T08 close-out / spec polish, non-blocking). 5 cycle-1 findings closed: HIGH-1 RESOLVED, HIGH-2 RESOLVED, MEDIUM-1 RESOLVED (user-locked Path a), LOW-1 RESOLVED, LOW-2 RESOLVED. MEDIUM-2 was RESOLVED in cycle 1. 13/13 ACs + 2/2 carry-overs met; gates green; 720 passed (was 715 in cycle 1) + 23 doc-snippet tests (was 18 in cycle 1) + 0 broken contracts + ruff clean.

## Design-drift check

No KDR drift in either cycle. Doc remains text-only — no source-code edits in `ai_workflows/`. Cross-reference against the seven load-bearing KDRs:

- **Four-layer rule.** `lint-imports` → 4 contracts kept, 0 broken, 107 dependencies (unchanged across cycles 1 + 2). The cycle-2 test additions in `tests/docs/test_writing_workflow_snippets.py` import `ai_workflows.cli` (Typer-app introspection only) — that import is at the test surface, not in `ai_workflows/`, and does not affect lint-imports' contracts.
- **KDR-002 / KDR-008 (MCP wire).** Doc explicitly documents the existing FastMCP `payload` wrapper convention; MCP wire shape unchanged. Tool list (`run_workflow`, `resume_run`, `list_runs`, `cancel_run`) matches the four shipped tools. Cycle-2 §"Surfaces are automatic" rewrite confirms `cancel_run` is the MCP-only cancellation surface — correctly framed.
- **KDR-003 (no Anthropic API).** No `anthropic` SDK or `ANTHROPIC_API_KEY` reference in the doc.
- **KDR-004 (validator pairing).** Doc explicitly teaches that `LLMStep.response_format` is required so KDR-004 is enforced *by construction*. Matches the actual `spec.py` constraint.
- **KDR-006 (three-bucket retry).** `RetryPolicy` is taught as a step-config field via the worked example; doc does not invent a new retry surface. Cycle-2 byte-match restoration of the inline `# re-exported from ai_workflows.primitives.retry per locked Q1` comment further reinforces the framing.
- **KDR-009 (SqliteSaver checkpoints).** Doc references `SqliteSaver` only in §`GateStep`; no hand-rolled checkpoint logic taught.
- **KDR-013 (user-owned code).** §"External workflows from a downstream consumer" preserves the dotted-path discovery surface from M16; minimum module shape uses `WorkflowSpec` per ADR-0008 §Documentation surface; `register(name, build_fn)` survives as the documented Tier 4 escape hatch. KDR-013 framing exactly preserved.

No `import langgraph` in any Tier-1 / Tier-2 code block — verified by `test_no_import_langgraph_in_tier1_tier2_blocks`. `langgraph` import appears only in the §Escape hatch code block, which is correct.

## AC grading (cycle 2 — final)

| AC | Status | Notes |
| -- | ------ | ----- |
| **AC-1** Doc rewritten declarative-first; Tier 1 + Tier 2 coverage; no `import langgraph` in Tier-1/Tier-2 code blocks | ✅ Met | Unchanged from cycle 1 — first executable code block (line 51) is a tier-registry helper, not LangGraph; `import langgraph` confined to §Escape hatch. |
| **AC-2** Section structure matches Deliverable 1 | ✅ Met | All 9 prescribed sections present in the prescribed order — verified by `test_doc_section_order`. |
| **AC-3** Worked `summarize` example present + doctest-compilable | ✅ Met (cycle 2 fix) | **Cycle 2 RESOLVED MEDIUM-1** — doc snippet now byte-matches `summarize.py` modulo doctest markers, the LOW-2 sibling-module comment, trailing whitespace, and leading/trailing blank lines. `test_worked_example_matches_summarize_py` rewritten to enforce byte-equality (72 lines == 72 lines, equal True under direct invocation). |
| **AC-4** §Running documents MCP `{"payload": {...}}` wrapper | ✅ Met | Unchanged from cycle 1 — payload wrapper documented with worked `fastmcp.Client.call_tool` snippet. |
| **AC-5** `result.artifact` canonical; `result.plan` deprecated alias | ✅ Met | Unchanged from cycle 1 — `result.artifact` canonical; `result.plan` framed verbatim per TA-LOW-01. |
| **AC-6** §"When you need more" cross-links to T06 + T08-aligned graph-primitive doc; Tier 3 framing covers `execute()` AND `compile()` upgrade path | ✅ Met | Unchanged from cycle 1 — both cross-links present; `compile_step_in_isolation` named in §Testing per TA-LOW-06. |
| **AC-7** §External workflows uses `WorkflowSpec`; `get_run_status` removed; `<workflow>_tier_registry()` convention stated | ✅ Met (cycle 2 fix) | All three sub-claims still verified. **Cycle 2** also resolved the §"Surfaces are automatic" sub-section's CLI-flag bugs that originally taunted this AC's "minimum module shape works" promise (HIGH-1). |
| **AC-8** §Escape hatch present; honest framing; cross-link to graph-primitive guide | ✅ Met | Unchanged from cycle 1. |
| **AC-9** Cross-reference rot cleared (no outdated "(builder-only, on design branch)" on items in main tree) | ✅ Met | Unchanged from cycle 1 — Builder correctly retained the marker on `[ADR-0007]` / `[ADR-0008]` design_docs links (factually accurate); `test_doc_no_builder_only_annotation_on_main_tree_items` verifies no shipped *code* construct carries the marker. LOW-3 (spec text polish) remains OPEN as out-of-scope deferral. |
| **AC-10** Doctest verification; every code block compiles | ✅ Met (cycle 2 fix) | All 23 tests pass; `test_all_python_blocks_compile` confirms every `\`\`\`python` block parses. **Cycle 2 RESOLVED HIGH-2** — the §Testing fixture pattern is now runtime-correct (correct import path + correct patch target + correct constructor pattern lifted from `tests/workflows/test_summarize.py`). Two new pin-tests guard against regression. |
| **AC-11** No regression in pedagogical strength | ✅ Met | Cycle-2 changes are doc-hygiene + bug-fix only; no pedagogical content lost. The progression unchanged: minimum-viable spec → per-step-type → worked example → running → deeper tiers. |
| **AC-12** CHANGELOG entry under `[Unreleased]` | ✅ Met (cycle 2 fix) | Cycle 1: `### Changed — M19 Task 05` block. Cycle 2: new `### Fixed — M19 Task 05 (cycle 2)` block stacked above (lines 10–48). Both Keep-a-Changelog vocabulary; cycle-2 entry uses `### Fixed` correctly for the bug-fix nature; KDRs cited. |
| **AC-13** Gates green | ✅ Met (cycle 2 re-verified) | Re-run from scratch this audit: `uv run pytest` → 720 passed, 9 skipped, 0 failed (31.06s; cycle 1 was 715 — the +5 cycle-2 pin tests); `uv run lint-imports` → 4 contracts kept, 0 broken (107 deps); `uv run ruff check` → All checks passed. |
| **TA-LOW-01** Deprecation-timeline framing consistency | ✅ Met | Unchanged from cycle 1 — canonical phrasing verbatim. |
| **TA-LOW-06** Cross-spec consistency on `compile_step_in_isolation` | ✅ Met | Unchanged from cycle 1 — `compile_step_in_isolation` referenced by exact name. |

## 🔴 HIGH

### HIGH-1 — Doc teaches CLI flags + commands that do not exist (`aiw resume --approve`, `aiw cancel`)

**Status:** ✅ **RESOLVED 2026-04-26 (cycle 2)**.

**Cycle 1 finding (preserved for history):** The doc taught `aiw resume <run_id> --approve` (line 220, 456) and `aiw cancel <run_id>` (line 459) — neither exists. `aiw resume` actually takes `--gate-response approved|rejected` (default `approved`); there is no `aiw cancel` command, only the MCP `cancel_run` tool. A downstream consumer following the doc would hit `Error: No such option '--approve'` and `Error: No such command 'cancel'`.

**Cycle-2 verification:**
- Doc lines 220–222 now read: `aiw resume <run_id>` (default gate response is `approved`) or `aiw resume <run_id> --gate-response approved` for the explicit form, or the MCP `resume_run` tool. Verified against `ai_workflows/cli.py:519–545` (`gate_response: str = typer.Option(..., "--gate-response", "-r", ...)`).
- Doc lines 471–478 (§"Surfaces are automatic"): `aiw resume <run_id>` documented with default-vs-explicit framing; cancellation explicitly framed as "MCP `cancel_run` tool only — `aiw cancel` is not implemented at this version." Honest + accurate.
- Cycle-2 added three regression pins in `tests/docs/test_writing_workflow_snippets.py`:
  - `test_doc_cli_no_approve_flag` — asserts `--approve` not in doc. PASSES.
  - `test_doc_cli_no_aiw_cancel_command` — asserts `aiw cancel` not taught as a valid command (allows prose negation like "is not implemented"). PASSES.
  - `test_doc_cli_resume_registered_commands` — introspects `app.registered_commands` and asserts `resume` registered + `cancel` NOT registered. PASSES. The test correctly handles Typer's `name=None` callback-name resolution by replacing `_` with `-` in the callback's `__name__`.
- Manual cross-check against `ai_workflows/cli.py`: `@app.command()` decorators on lines 145 (run), 225 (?), 446 (show-inputs), 519 (resume), 614 (list-runs). No `cancel` definition. Verified.

**Action / Recommendation:** None — closed. Pin tests prevent regression.

### HIGH-2 — §Testing your workflow ships a fixture pattern that is runtime-broken on two counts

**Status:** ✅ **RESOLVED 2026-04-26 (cycle 2)**.

**Cycle 1 finding (preserved for history):** The fixture taught (a) wrong module path `ai_workflows.primitives.providers.litellm_adapter` (does not exist; correct is `ai_workflows.primitives.llm.litellm_adapter`); (b) wrong patch target — patching the source module after `tiered_node` already imported `LiteLLMAdapter` is a no-op for the consumer-side reference; the correct target is `ai_workflows.graph.tiered_node.LiteLLMAdapter`; (c) `StubLLMAdapter()` constructor missing required keyword-only args (`route` + `per_call_timeout_s`).

**Cycle-2 verification:**
- Doc lines 654–667 now reproduce the working pattern from `tests/workflows/test_summarize.py:97–101`:

  ```python
  import pytest
  from ai_workflows.graph import tiered_node as tiered_node_module
  from ai_workflows.evals._stub_adapter import StubLLMAdapter


  @pytest.fixture(autouse=True)
  def stub_llm(monkeypatch):
      """Replace the LiteLLM adapter at the import site so no real provider call fires."""
      StubLLMAdapter.arm(expected_output='{"summary": "stubbed"}')
      monkeypatch.setattr(tiered_node_module, "LiteLLMAdapter", StubLLMAdapter)
      yield StubLLMAdapter
      StubLLMAdapter.disarm()
  ```

  Verified each surface against the live source:
  - `ai_workflows.graph.tiered_node` is the correct patch site (`ai_workflows/graph/tiered_node.py:88` confirms `from ai_workflows.primitives.llm.litellm_adapter import LiteLLMAdapter` at module load — patch target must be the consumer-side reference).
  - `StubLLMAdapter.arm(expected_output=...)` matches `_stub_adapter.py:122` (`def arm(cls, *, expected_output: str)`).
  - `StubLLMAdapter.disarm()` matches `_stub_adapter.py:129`.
  - The `monkeypatch.setattr(tiered_node_module, "LiteLLMAdapter", StubLLMAdapter)` form bypasses the constructor-argument issue entirely — `StubLLMAdapter` (the class) is passed as the replacement, and it absorbs the `*args, **kwargs` the framework calls it with via its `__init__(self, *, route, per_call_timeout_s)` signature, then defers to its armed expected_output for every call.
- Cycle-2 added two regression pins:
  - `test_doc_testing_fixture_no_broken_import_path` — asserts the broken `ai_workflows.primitives.providers.litellm_adapter` path is absent. PASSES.
  - `test_doc_testing_fixture_uses_correct_patch_target` — asserts `tiered_node` appears in the §Testing section. PASSES.

**Action / Recommendation:** None — closed. Pin tests prevent regression.

## 🟡 MEDIUM

### MEDIUM-1 — Worked-example snippet is not byte-for-byte source-shared with `summarize.py` (spec line 59 violated as-written)

**Status:** ✅ **RESOLVED 2026-04-26 (cycle 2)** via user-locked Path (a) — tighten doc to actually match.

**Cycle 1 finding (preserved for history):** Doc snippet diverged from `summarize.py` on three counts: missing `from __future__ import annotations`; missing inline comment on `RetryPolicy` import; missing trailing `_SPEC` module-level docstring. Builder relaxed the AC-3 test from byte-equality to key-phrase presence, which silently weakened the spec-line-59 promise.

**Cycle-2 verification (user locked Path (a)):**
- Doc §Worked example code block restored to source-shared shape:
  - Line 311: `from __future__ import annotations` — present.
  - Line 317: `RetryPolicy,  # re-exported from ai_workflows.primitives.retry per locked Q1` — inline comment restored.
  - Lines 323–324: one-line LOW-2 clarifying comment on the sibling-module pattern (added per Path (a)'s "tighten + clarify" framing — the normaliser excludes it from byte-equality).
  - Lines 372–381: trailing `_SPEC` module-level docstring — present, byte-matches `summarize.py:109–118`.
  - Line 384: `register_workflow(_SPEC)` — present (matches `summarize.py:121`).
- `test_worked_example_matches_summarize_py` rewritten:
  - Reads `summarize.py` from `from __future__` onwards (skips the module docstring).
  - Reads doc's first `\`\`\`python` block under §Worked example.
  - Normalises both: strips `# doctest:` markers, strips lines starting with the LOW-2 comment fragments (`# (For brevity` and `# downstream authors can keep it inline as shown in`), strips trailing whitespace, strips leading/trailing blank lines.
  - Asserts line-set equality with a `difflib.unified_diff` on mismatch.
  - Result of direct invocation: source 72 lines, doc 72 lines, equal True.
- Drift detection sanity check: I verified the test would catch a drift by inspecting the comparison logic — adding a single non-comment line to either side moves the line count off, and adding a different comment that doesn't match the LOW-2 fragments leaves the line in the comparison set. The test is genuinely tight.

**Action / Recommendation:** None — closed. Path (a) executed cleanly.

### MEDIUM-2 — `docs/writing-a-custom-step.md` stub creates a propagation obligation T06 must explicitly absorb

**Status:** ✅ **RESOLVED 2026-04-26 (cycle 1)**.

**Cycle 1 finding (preserved for history):** The Builder created an 11-line placeholder so the cross-link from `writing-a-workflow.md` resolves under the link-checker. T06 must `Write` the file (not `Edit`) to overwrite the stub completely.

**Cycle 1 resolution:** Auditor appended a `## Carry-over from prior audits` entry to `task_06_writing_custom_step.md` (lines 301–304 — verified still present in cycle 2). T06 Builder will see + tick this on T06 close-out. T06 Auditor instructed to confirm no stub vestiges remain.

**Cycle-2 status:** Carry-over still present in T06 spec (verified via grep). No cycle-2 work required on this finding.

## 🟢 LOW

### LOW-1 — `WorkflowSpec` table column count says four required fields but lists five

**Status:** ✅ **RESOLVED 2026-04-26 (cycle 2)**.

**Cycle 1 finding (preserved for history):** Line 26 read "Every `WorkflowSpec` requires four fields" but the table below listed five. The fifth (`tiers`) was added per locked Q3 — count was not updated.

**Cycle-2 verification:** Doc line 26 now reads "Every `WorkflowSpec` requires five fields:" — verified by direct read. Table at lines 28–34 lists all five: `name`, `input_schema`, `output_schema`, `steps`, `tiers`. Count matches table.

**Action / Recommendation:** None — closed.

### LOW-2 — `summarize_tier_registry()` import pattern divergence between worked example and inline tier-registry section

**Status:** ✅ **RESOLVED 2026-04-26 (cycle 2)**.

**Cycle 1 finding (preserved for history):** Worked example imports `summarize_tier_registry` from a sibling module (`ai_workflows.workflows.summarize_tiers`); the §"Tier registry" sub-section above shows the inline pattern. Downstream readers comparing the two patterns might be confused.

**Cycle-2 verification:** Doc lines 322–324 now read:

```python
from ai_workflows.workflows.summarize_tiers import summarize_tier_registry
# (For brevity the tier-registry helper lives in a sibling ``summarize_tiers.py`` module;
# downstream authors can keep it inline as shown in §Tier registry above.)
```

Two-line clarifier explains the sibling-module choice and points readers back at the inline pattern. The normaliser in `_normalise_for_comparison` (lines 213–223 of the test) excludes lines starting with `# (For brevity` or `# downstream authors can keep it inline as shown in` from the byte-equality check, so this addition does not break MEDIUM-1's byte-match.

I verified the normaliser logic does not over-exclude: it only matches the two specific LOW-2 fragment prefixes; arbitrary other comments would still be compared. If a future edit added a different comment to the doc (or to `summarize.py`), the byte-match test would catch it. Coverage preserved.

**Action / Recommendation:** None — closed.

### LOW-3 — `[ADR-0007]` / `[ADR-0008]` "(builder-only, on design branch)" annotations are factually correct but the AC-9 spec text was misleading

**Status:** ⚠️ **OPEN — out-of-scope deferral (T08 close-out / spec polish)**.

**Cycle 1 finding (preserved):** AC-9 spec text (line 178 of `task_05_writing_workflow_rewrite.md`) said "no outdated '(builder-only, on design branch)' annotations on items now in the main tree (e.g. ADR-0007, ADR-0008)." But ADR-0007 and ADR-0008 are NOT in the main tree (`design_docs/` is design-branch-only by design). The annotations on the doc are factually correct. The Builder did the right thing; the spec text is what's wrong.

**Cycle-2 status:** Per orchestrator instructions, LOW-3 is explicitly out of cycle-2 scope; T08 close-out absorbs the spec-text polish. This is a one-line documentation correction in the spec, not a doc fix; it does not block the audit.

**Action / Recommendation:** At T08 close-out, edit `task_05_writing_workflow_rewrite.md` line 178 to remove the misleading "(e.g. ADR-0007, ADR-0008)" example. Suggested rephrasing: "no outdated '(builder-only, on design branch)' annotations on items that have shipped to main — code constructs (`TieredNode`, `WorkflowSpec`, `LLMStep`, etc.) and `docs/`-tree files. ADR / design_docs links retain the marker because `design_docs/` is design-branch-only by design."

## Additions beyond spec — audited and justified

**Cycle 1 (preserved):**
- `docs/writing-a-custom-step.md` stub — justified; needed for `tests/docs/test_docs_links.py` cross-link resolution. See MEDIUM-2 (RESOLVED).
- §"Reserved field names" sub-section — absorbs T04 ADV-1 security advisory; tested.
- §"Brace-escaping caveat" sub-section — absorbs T04 ADV-2 security advisory; tested.
- §"Surfaces are automatic" sub-heading inside §Running — additive; cycle-1 source of HIGH-1 bugs (now resolved in cycle 2).
- 18 cycle-1 tests — every AC backed by ≥1 test; no tautologies; one borderline (`test_doc_documents_mcp_payload_wrapper`) acceptable.
- Cycle-1 CHANGELOG `### Changed` entry — justified; required by AC-12.

**Cycle 2 additions (audited):**
- 5 new tests in `tests/docs/test_writing_workflow_snippets.py` (23 total). Each test targets a specific cycle-1-finding regression:
  | Test | Backs cycle-1 finding | Tautology check |
  |---|---|---|
  | `test_doc_cli_no_approve_flag` | HIGH-1 (negative — `--approve` absent) | No — single-string negative pin; would fire if regression reintroduces `--approve` |
  | `test_doc_cli_no_aiw_cancel_command` | HIGH-1 (negative — `aiw cancel` absent except in negation context) | No — line-aware filter allows prose negations like "not implemented", catches reintroduction as a command invocation |
  | `test_doc_cli_resume_registered_commands` | HIGH-1 (positive — live Typer-app introspection) | No — actively reads `app.registered_commands` from `ai_workflows.cli`; would fire if `resume` were renamed in code or removed |
  | `test_doc_testing_fixture_no_broken_import_path` | HIGH-2 (negative) | No — would fire if regression reintroduced `ai_workflows.primitives.providers.litellm_adapter` |
  | `test_doc_testing_fixture_uses_correct_patch_target` | HIGH-2 (positive) | No — section-scoped check; `tiered_node` must appear in §Testing |
  All 5 tests verified meaningful + non-tautological + targeting specific cycle-1 regressions. Cycle-1's `test_worked_example_matches_summarize_py` rewritten for byte-equality with normaliser — strict, drift-detecting.
- Cycle-2 CHANGELOG `### Fixed — M19 Task 05 (cycle 2)` entry (lines 10–48). Keep-a-Changelog `### Fixed` vocabulary correctly chosen for bug-fix nature; KDRs cited (KDR-013, KDR-003); explicit "Deviations from spec: none" line.
- No new cycle-2 doc content beyond the targeted fixes; no scope creep; no `nice_to_have.md` adoption.

## Gate summary

| Gate | Command | Cycle 1 result | Cycle 2 result |
|---|---|---|---|
| Tests | `uv run pytest` | ✅ 715 passed, 9 skipped, 0 failed (29.40s) | ✅ 720 passed, 9 skipped, 0 failed (31.06s) — +5 cycle-2 pin tests |
| Layer contract | `uv run lint-imports` | ✅ 4 contracts kept, 0 broken (107 deps) | ✅ 4 contracts kept, 0 broken (107 deps) |
| Lint | `uv run ruff check` | ✅ All checks passed | ✅ All checks passed |
| Doc snippets | `uv run pytest tests/docs/test_writing_workflow_snippets.py -v` | ✅ 18 passed (0.88s) | ✅ 23 passed (0.86s) |

All gates re-run from scratch each cycle. Cycle-2 Builder report (720 passed, 4 contracts kept, ruff clean) verified verbatim — no gate integrity issue.

## Issue log — cross-task follow-up

| ID | Severity | Owner / next touch | Status |
|---|---|---|---|
| M19-T05-ISS-HIGH-1 | HIGH | Builder cycle 2 (this milestone) | ✅ RESOLVED 2026-04-26 (cycle 2) — `--approve` + `aiw cancel` references corrected; 3 pin tests added |
| M19-T05-ISS-HIGH-2 | HIGH | Builder cycle 2 (this milestone) | ✅ RESOLVED 2026-04-26 (cycle 2) — §Testing fixture replaced with `tiered_node_module` patch shape; 2 pin tests added |
| M19-T05-ISS-MED-1 | MEDIUM | Builder cycle 2 (user locked Path a) | ✅ RESOLVED 2026-04-26 (cycle 2) — doc snippet now byte-matches `summarize.py`; `test_worked_example_matches_summarize_py` rewritten for byte-equality |
| M19-T05-ISS-MED-2 | MEDIUM | T06 Builder | ✅ RESOLVED 2026-04-26 (cycle 1) — propagated as carry-over to `task_06_writing_custom_step.md`; verified still present in cycle 2 |
| M19-T05-ISS-LOW-1 | LOW | Builder cycle 2 (this milestone) | ✅ RESOLVED 2026-04-26 (cycle 2) — "four fields" → "five fields" |
| M19-T05-ISS-LOW-2 | LOW | Builder cycle 2 (this milestone) | ✅ RESOLVED 2026-04-26 (cycle 2) — sibling-module clarifier added; normaliser excludes from byte-match |
| M19-T05-ISS-LOW-3 | LOW | T08 close-out / spec polish | ⚠️ OPEN — out-of-scope deferral; spec text rephrasing only; no code/doc edit needed; non-blocking |

## Deferred to nice_to_have

None. The findings here are all task-scoped fixes against the actual deliverable.

## Propagation status

- **M19-T05-ISS-MED-2 (T06 stub overwrite obligation)** — ✅ propagated 2026-04-26 (cycle 1). `## Carry-over from prior audits` entry added to `design_docs/phases/milestone_19_declarative_surface/task_06_writing_custom_step.md` lines 301–304. Cycle-2 verification: entry still present (grep confirmed). Re-audit on T06 close: flip the carry-over checkbox `[ ] → [x]` and update this row to `RESOLVED (commit sha)`.
- **M19-T05-ISS-LOW-3 (AC-9 spec-text polish)** — ⚠️ deferred 2026-04-26 (cycle 2) to T08 close-out. No carry-over propagation needed since the fix is a one-line edit to T05's own spec, not a downstream-task deliverable; T08 close-out instructions absorb spec-polish items milestone-wide. If T08 misses it on close-out, surface to user.

## Cycle-2 audit close-out

All five cycle-2-scoped findings closed (HIGH-1, HIGH-2, MEDIUM-1, LOW-1, LOW-2). MEDIUM-2 was closed in cycle 1; cycle-2 verification preserves that. LOW-3 remains OPEN as out-of-scope deferral (non-blocking; T08 spec polish). No new findings introduced by cycle 2 — verified by:

1. Re-reading the full doc end-to-end (677 lines).
2. Re-running all three gates from scratch.
3. Spot-checking the byte-match normaliser does not hide drift it shouldn't (LOW-2 fragments are the only excluded comments; arbitrary other drift would still fire the test).
4. Verifying the 5 new tests are non-tautological and target specific cycle-1 regressions.
5. Verifying the cycle-2 CHANGELOG entry uses Keep-a-Changelog `### Fixed` vocabulary correctly.
6. Status-surface integrity check: T05 spec line 3 still `**Status:** ✅ Done (implemented 2026-04-26).`; milestone README task-table row 05 still `✅ Implemented (2026-04-26)` (line 161). No `tasks/README.md` for M19 (verified). All 13 AC + 2 carry-over checkboxes in T05 spec still `[x]`. No status-surface drift.

Audit cycle 2 closes ✅ PASS.

## Security review (2026-04-26)

**Scope:** T05 is a pure documentation task — `docs/writing-a-workflow.md` (full rewrite, 677 lines), `docs/writing-a-custom-step.md` (6-line stub), `tests/docs/test_writing_workflow_snippets.py` (23 tests), `CHANGELOG.md` entries. No `ai_workflows/` source touched in T05 cycles. Threat-model items 1–10 from the tasking brief evaluated below.

### 🔴 Critical — must fix before publish/ship

None.

### 🟠 High — should fix before publish/ship

None.

### 🟡 Advisory — track; not blocking

**ADV-SEC-1 — `(builder-only, on design branch)` annotation in a publicly-shipped doc (informational)**

- **File:line:** `docs/writing-a-workflow.md:518–519, 609`
- **Threat-model item:** 1 (wheel / sdist contents)
- **Finding:** Three link annotations in the published doc read `(builder-only, on design branch)`. They appear on `design_docs/adr/0007_…` and `design_docs/adr/0008_…` links. Those relative paths resolve inside `design_docs/`, which does ship in the sdist (pre-existing T01 HIGH-1 / T08 fix). The annotations are factually accurate (the ADR files are only on `design_branch`), but a PyPI consumer reading the rendered doc sees an internal workflow term ("design branch", "builder-only") that belongs to internal dev process, not public API surface. There is no secret or credential in these annotations — the exposure is limited to revealing the project uses a feature-branch publishing workflow and that the ADR files are design-branch-only.
- **Action:** At T07 doc-sweep or T08 close-out, consider rephrasing to `(architecture decision record — available in the source repository)` or simply dropping the parenthetical. This is a polish item; it does not block publish because the annotation discloses no secrets and no exploitable internals. ADV severity only.

**ADV-SEC-2 — sdist contains `.env.example`, `design_docs/`, `.claude/` (pre-existing, not T05-introduced)**

- **File:** `dist/jmdl_ai_workflows-0.2.0.tar.gz`
- **Threat-model item:** 1 (wheel / sdist contents)
- **Finding:** The 0.2.0 sdist (built before T05) already contains `.env.example`, the full `design_docs/` tree (including all issue files, phase specs, and audit logs), and the `.claude/` subtree (agent system prompts, slash commands, skill). T05 added `docs/writing-a-workflow.md` to the sdist — this file is appropriate public content (no secrets, correct placeholder `GEMINI_API_KEY=` line with no value). The `.env.example` file has `GEMINI_API_KEY=` with an empty value — no real key. This advisory is a reminder to the pre-publish run of `uv build` + `unzip -l` verification required at T08; T05 does not worsen the exposure.
- **Action:** T08 dependency-auditor / pre-publish gate (already tracked as T01 HIGH-1 folded to T08). Not T05's obligation.

### Verification results per tasking brief

| Item | Verified | Result |
|------|----------|--------|
| 1. Wheel + sdist contents for T05 files | Yes | Wheel (`0.2.0`) contains no `docs/`, no `design_docs/`, no `.env*`, no secrets — clean. Sdist contains `docs/writing-a-workflow.md` (appropriate; no secrets) and pre-existing `.claude/`+`design_docs/` (T08 gate, not T05). |
| 2. No `ai_workflows/` source changes | Yes | `git diff main -- ai_workflows/` shows M19 T01–T04 changes only (pre-T05). T05 cycles introduced zero source changes. |
| 3. `summarize.py` contains no secrets | Yes | File contains only public pydantic models + `WorkflowSpec` construction with `gemini/gemini-2.5-flash` model name (not a credential). No API keys, no tokens, no internal paths. |
| 4a. ADV-1 reserved field names documented | Yes | `run_id`, `last_exception`, `_retry_counts`, `_non_retryable_failures`, `_mid_run_tier_overrides`, `_ollama_fallback_fired` all listed. Framing is honest and proportionate — "logic error the framework cannot detect at registration time"; does not overclaim severity (KDR-013 author-owned). |
| 4b. ADV-2 `prompt_template` injection caveat | Yes | Brace-escaping caveat accurately describes the trust boundary: workflow-author-supplied template + end-user-supplied field values → confused LLM only, no framework state escape. Worst-case framing accurate. `{{`/`}}` mitigation and `prompt_fn=` upgrade path both documented. |
| 5. CLI-flag accuracy (`aiw resume --gate-response`, no `aiw cancel`) | Yes | `--approve` absent; `aiw cancel` absent except in prose negation ("not implemented at this version"). Verified against three pin tests (`test_doc_cli_no_approve_flag`, `test_doc_cli_no_aiw_cancel_command`, `test_doc_cli_resume_registered_commands`). |
| 6. Test fixture pattern — no `ANTHROPIC_API_KEY` normalisation | Yes | Fixture uses `StubLLMAdapter.arm(expected_output=...)` + `monkeypatch.setattr(tiered_node_module, "LiteLLMAdapter", StubLLMAdapter)`. No `os.environ` manipulation, no API key injection of any kind. |
| 7. No subprocesses / network calls in doc Python blocks | Yes | `grep` found no subprocess, no `http://` / `https://` hits in executable Python blocks. The MCP snippet uses `asyncio` + `fastmcp.Client` but is documentation-only (not executed by the test suite). No live network hit in any block the tests execute. |
| 8. `ANTHROPIC_API_KEY` / `anthropic` SDK not taught | Yes | Zero matches for `ANTHROPIC_API_KEY` or `anthropic` SDK in the doc. Claude access mentioned only in Prerequisites as `claude` CLI on PATH (logged in via `claude login`) — correct KDR-003 framing. |
| 9. CHANGELOG vocabulary | Yes | `### Changed — M19 Task 05` (cycle 1 doc rewrite) and `### Fixed — M19 Task 05 (cycle 2)` (bug fixes) are correct Keep-a-Changelog vocabulary. |
| 10. Test hermeticity | Yes | `tests/docs/test_writing_workflow_snippets.py` — no filesystem writes, no subprocess, no network calls, no `.env*` reads. `_REPO_ROOT` used only for `read_text()`. Typer-app introspection (`app.registered_commands`) is pure in-process state read. |

### Verdict: SHIP

T05 is a documentation-only task with no new code, no manifest changes, and no new subprocess or network surface. The wheel is clean for T05's scope. The two advisories (ADV-SEC-1: internal dev-process annotation in public doc text; ADV-SEC-2: pre-existing sdist leakage of `design_docs/`+`.claude/`) are both pre-existing items gated to T08 — T05 does not introduce or worsen either. All ten tasking-brief verification items pass. No finding blocks ship.

## Dependency audit (2026-04-26)

**Skipped — no manifest changes.** T05 cycles 1+2 modified only `docs/writing-a-workflow.md` (rewrite + 5 fixes), `docs/writing-a-custom-step.md` (stub), `tests/docs/test_writing_workflow_snippets.py` (new + expanded), `CHANGELOG.md`, plus T05 spec status surfaces and milestone README task-table row. No `ai_workflows/` source changes; no `pyproject.toml` or `uv.lock` changes. The dependency-auditor pass is not triggered per /clean-implement S2.
