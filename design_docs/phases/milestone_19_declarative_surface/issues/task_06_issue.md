# Task 06 — New `docs/writing-a-custom-step.md` (Tier 3 dedicated guide) — Audit Issues

**Source task:** [../task_06_writing_custom_step.md](../task_06_writing_custom_step.md)
**Audited on:** 2026-04-26
**Audit scope:** `docs/writing-a-custom-step.md` (323 lines — full Tier 3 guide; Write-overwrite of T05's 6-line stub per CARRY-T05-MEDIUM-2), `ai_workflows/workflows/testing.py` (173 lines — new module; `compile_step_in_isolation` async function), `tests/workflows/test_testing_fixtures.py` (183 lines / 7 tests), `tests/docs/test_writing_custom_step_snippets.py` (326 lines / 19 tests), `CHANGELOG.md` (`### Added — M19 Task 06` block under `[Unreleased]`), task spec status surface, milestone README task-table row 06. Cross-referenced against `design_docs/architecture.md` (§3 four-layer rule, §6 deps, §9 KDRs), ADR-0008 (§Extension model, §Documentation surface), ADR-0007 (user-owned code contract), `ai_workflows/workflows/_compiler.py:880-918` (default compile path; reducer-merge for `FanOutStep`), `ai_workflows/workflows/spec.py:120-140` (`Step.compile()` Q4 default delegating to `_default_step_compile`), `ai_workflows/workflows/_dispatch.py:573-621` (production state-key surfacing on the wire — divergence from fixture analysed below). Predecessor T01–T05 issue files reviewed for carry-over context. All three gates re-run from scratch.

**Status:** ✅ PASS

## Design-drift check

**No drift detected.**

| Drift category | Verdict | Evidence |
|---|---|---|
| New dependency | None — `testing.py` imports `langgraph.constants`, `langgraph.graph`, `ai_workflows.workflows.spec`, `ai_workflows.workflows._compiler` only. No `pyproject.toml` / `uv.lock` change. | `git diff --stat HEAD` confirms no manifest touch. |
| New module / layer crossing | New module `ai_workflows/workflows/testing.py` placed in workflows layer. Layer rule preserved — `lint-imports` 4 contracts kept. | `uv run lint-imports` re-run from scratch: 4 kept, 0 broken. `test_testing_module_is_in_workflows_layer` pins placement. |
| LLM call added | None — fixture explicitly calls `step.execute()`/`step.compile()` only; no `TieredNode`/`ValidatorNode` machinery introduced. | `testing.py:125` (`step.compile()`); no `TieredNode` import. |
| Checkpoint / resume logic (KDR-009) | Fixture **explicitly omits** `SqliteSaver`; documented as a deliberate isolation-fixture decision. Doc §Testing line 232 names the omission. KDR-009 alignment-section in module docstring (`testing.py:25-27`). | KDR-009 honoured — the fixture is a unit-test primitive, not a persistence round-trip. |
| Retry logic (KDR-006) | None added. Fixture seeds `_retry_counts` / `_non_retryable_failures` for read-side compatibility but does not drive retry. | `testing.py:154-160`. |
| Observability / external backends | None added. | n/a |
| External workflow loading (KDR-013) | Doc §User-owned code boundary cites KDR-013 + ADR-0007 explicitly. Fixture calls `step.execute()`/`step.compile()` exactly as the framework does — no linting, no sandboxing. | Doc lines 301–314; `testing.py:28-30` KDR alignment block. |
| Workflow tier names | Doc's `WebFetchStep` worked example uses `summarize-url-llm` (illustrative, not an in-tree tier) per TA-LOW-09 carry-over. Pre-pivot tier names absent. | Doc lines 156–162; `test_web_fetch_step_uses_generic_tier_name` pins absence of `planner-explorer`. |
| MCP tool surface (KDR-008) | No MCP changes. | n/a |

## AC grading

| AC | Status | Notes |
|---|---|---|
| AC-1 — 9-section structure + both `execute()` and `compile()` paths | ✅ MET | All 9 sections present (Title + intro / §When to write / §Step base class contract / §Advanced — overriding `compile()` directly / §Worked example / §State-channel conventions / §Testing / §Graduation hints / §User-owned code boundary / §Pointers to adjacent tiers). Verified by `test_section_structure` (line 132). The §Step base class contract section covers both paths; locked Q4 default-compile-wraps-execute is stated at line 74-76. |
| AC-2 — `WebFetchStep` doctest-skip + `AddOneStep` doctest-runnable | ✅ MET | `# doctest: +SKIP` marker present at line 123 (before `class WebFetchStep`). `AddOneStep` synthetic substitute uses stdlib only (lines 178-188); `test_add_one_step_present_as_runnable_substitute` + `test_web_fetch_step_present_and_skip_marked` pin both invariants. Smoke-confirmed via `uv run python -c` direct execution of `AddOneStep` against the fixture — returns `{'n': 1}` as expected. |
| AC-3 — `Step` contract: `execute()` + `compile()` + frozen + extra='forbid' + Q4 default | ✅ MET | `execute(state) -> dict` async signature documented (lines 60-72). `compile(state_class: type, step_id: str) -> CompiledStep` advanced-override path documented (lines 78-114) with `MyFanOutStep` example. Frozen + extra='forbid' invariants stated at line 44-46. Q4 default-compile-wraps-execute explicitly stated at line 74-76 with ADR-0008 citation. Live shape verified against `ai_workflows/workflows/spec.py:120-140`. |
| AC-4 — §State-channel conventions: 4 conventions | ✅ MET | All four present (lines 196-206): read from `state[<field>]`; write a dict of updates; don't mutate; don't reach for `_mid_run_*` framework keys. `test_state_channel_conventions_four_bullets` verifies all four phrases. |
| AC-5 — §Testing references `compile_step_in_isolation` | ✅ MET | Line 218 imports the fixture; lines 226-230 show the worked test against `AddOneStep`. The `StubLLMAdapter` integration pattern (lines 263-277) cross-links to `tests/workflows/test_summarize.py`. |
| AC-6 — §Graduation hints: 3 signals + cross-link | ✅ MET | Three signals at lines 287-296 (used in 2+ workflows; copy-paste-propagation; reusable wiring → graph primitive). Cross-link to `writing-a-graph-primitive.md` at line 295. |
| AC-7 — §User-owned code: KDR-013 + ADR-0007 | ✅ MET | KDR-013 cited at line 303; ADR-0007 cited at line 308. Framing matches the M16 external-workflow loader contract per ADR-0007. |
| AC-8 — §Pointers cross-links resolve | ✅ MET | `writing-a-workflow.md` → exists. `writing-a-graph-primitive.md` → exists. `tests/docs/test_docs_links.py` (3 tests) re-run from scratch: passed. The `architecture.md §Extension model` link is **intentionally omitted** (T07 ships that section); flagged as LOW-1 below for forward-deferral to T07. |
| AC-9 — Doctest verification | ✅ MET | `test_all_python_blocks_compile` re-run: 19 doc-snippet tests pass. All Python blocks compile cleanly; skip markers present where required. |
| AC-10 — `compile_step_in_isolation` ships in `workflows/testing.py`, exported, docstring, tests, layer-compliant | ✅ MET | File exists in workflows layer (`testing.py`); module docstring cites M19 T06 + locked M4 + KDR-009 + KDR-013 (lines 1-31); function has full docstring with Examples block (lines 50-110); 7 hermetic tests in `tests/workflows/test_testing_fixtures.py`; layer-rule-compliant (verified by `lint-imports` 4 contracts kept + `test_testing_module_is_in_workflows_layer`). |
| AC-11 — CHANGELOG entry | ✅ MET | `### Added — M19 Task 06: docs/writing-a-custom-step.md (Tier 3 dedicated guide) + compile_step_in_isolation testing fixture (2026-04-26)` block under `[Unreleased]`. Keep-a-Changelog vocabulary; KDR citations present; deviations explicitly noted as none. |
| AC-12 — Gates green | ✅ MET | `uv run pytest`: 746 passed, 9 skipped, 24 warnings (all pre-existing deprecation warnings on `result.plan` access from M19 T03 alias). `uv run lint-imports`: 4 contracts kept, 0 broken. `uv run ruff check`: All checks passed. |

### Carry-over AC grading

| Carry-over | Status | Notes |
|---|---|---|
| TA-LOW-04 — `WebFetchStep` doctest-skip + `AddOneStep` substitute | ✅ MET | Skip marker at line 123; `AddOneStep` synthetic substitute at lines 181-188. Verified by `test_skipped_blocks_have_doctest_skip_marker`. |
| TA-LOW-09 — Generic tier name (not `planner-explorer`) | ✅ MET | Doc uses `summarize-url-llm`; `test_web_fetch_step_uses_generic_tier_name` pins absence of `planner-explorer`. Framing comment at lines 155-157 explains the illustrative-only nature with cross-link to `writing-a-workflow.md` for the concrete `TierConfig` shape. |
| CARRY-T05-MEDIUM-2 — Write-overwrite stub, no vestiges | ✅ MET | T05's "This guide ships with M19 Task 06" stub fully replaced. `test_doc_exists` explicitly asserts the stub phrase is **not** present in the new file. Doc grew from 6 lines to 323 lines via Write (not Edit). |

## 🔴 HIGH

*None.*

## 🟡 MEDIUM

*None.*

## 🟢 LOW

### LOW-1 — `architecture.md §Extension model` cross-link absent (forward-anchor to T07)

**Where:** `docs/writing-a-custom-step.md` — no link to `architecture.md` (only `ADR-0008 §Extension model` is cited at line 118).

**What:** Spec Deliverable 3 calls for `architecture.md §Extension model` to be a cross-link target alongside the two sibling docs (`writing-a-workflow.md`, `writing-a-graph-primitive.md`). The Builder elected to omit the link entirely rather than ship a broken anchor — correct given the dependency direction (T07 ships the §Extension model section after T06). Verified honest: there is no `architecture.md` cross-link in the doc, broken or otherwise.

**Why LOW:** T06 cannot reference an anchor T07 hasn't created. The Builder's choice is the right intermediate state. The forward-deferral to T07 is the natural fix.

**Action / Recommendation:** Forward-defer to T07 (M19-T06-ISS-LOW-1). When T07 lands the §Extension model subsection in `architecture.md`, T07 should also add a back-link from `docs/writing-a-custom-step.md` (e.g. in the §Pointers to adjacent tiers section, or inline in the §When to write a custom step intro) to `../design_docs/architecture.md#extension-model`. T07 already cross-touches all three doc surfaces (architecture.md + README.md + writing-a-graph-primitive.md), so this is the natural owner. **Propagated to T07 spec via `## Carry-over from prior audits`.**

### LOW-2 — `compile_step_in_isolation` returns framework-internal seeded keys

**Where:** `ai_workflows/workflows/testing.py:154-173`.

**What:** The fixture seeds `run_id`, `last_exception`, `_retry_counts`, `_non_retryable_failures`, `_mid_run_tier_overrides` into the state before invoking the graph (so framework-aware nodes don't `KeyError`), then returns the merged dict — including those seeded keys — to the caller. Smoke-confirmed: `compile_step_in_isolation(AddOneStep(counter_field='n'), initial_state={'n': 0})` returns `{'run_id': '', 'last_exception': None, '_retry_counts': {}, '_non_retryable_failures': 0, '_mid_run_tier_overrides': None, 'n': 1}`.

This diverges from production: on the wire, `_dispatch.py:573-621` surfaces only the artefact field (`final.get(final_state_key)`); consumers never see the framework-internal keys. The doc itself tells authors at line 203 "Don't reach for framework-internal keys" — and yet the fixture hands them back. A well-meaning author writing strict-equality assertions (`assert result == {"n": 1}`) would fail.

The shipped worked test (line 226-230) and the 7 fixture tests use key-targeted assertions (`result["n"] == 1`), so they pass. The semantics are not silently wrong — just mildly leaky.

**Why LOW:** The fixture is a unit-testing primitive, not a production surface. The leak is recoverable on the test author's side (key-targeted assertions). No AC fails. The 7 hermetic tests prove the merge semantics work.

**Action / Recommendation:** *Either* (a) filter the seeded keys out of `merged` before returning (one-liner: `for k in ("run_id", "last_exception", "_retry_counts", "_non_retryable_failures", "_mid_run_tier_overrides"): merged.pop(k, None)` if `k` was not in `initial_state`), *or* (b) extend the fixture's docstring (`testing.py:50-110`) with a "Notes" subsection naming the seeded keys explicitly so authors expect them in the return value. Option (b) is the lower-cost choice and preserves the option to inspect the seeded keys for debugging custom steps that read them. Either landing is appropriate at next-touch on T06 (cycle 2) or as forward-deferred polish if no other cycle-2 work surfaces. **Not propagated** — narrowly-scoped to T06's own deliverables.

### LOW-3 — `MyFanOutStep` snippet imports `GraphEdge` but never uses it; reducer-merge divergence not documented

**Where:** `docs/writing-a-custom-step.md:91` (`from ai_workflows.workflows._compiler import CompiledStep, GraphEdge`).

**What:** Two minor doc-hygiene issues in the §Advanced — overriding `compile()` directly snippet:

1. The `MyFanOutStep` example imports `GraphEdge` but never uses it (the `edges=[...]` body is a stub). Pyright/ruff would normally flag this; the doc-snippet test (`test_all_python_blocks_compile`) only checks `compile()` (syntax), not unused-import lint. A copy-pasting reader will get `F401` from their own ruff.
2. The `compile()` override path *can* introduce reducer-merge channels (e.g. `Annotated[list, _append_reducer]` for fan-out) which `compile_step_in_isolation` (with `dict` state class) does not reproduce — `_compiler.py:1018-1020` shows the production reducer is registered in the TypedDict-derived state class, but the fixture uses plain `dict`. The `MyFanOutStep` is illustrative-only, but a downstream consumer who actually authors a `compile()`-override fan-out step and then runs it through `compile_step_in_isolation` will see different state-merge behaviour than production.

**Why LOW:** Both issues are minor. (1) is doc cosmetics — the snippet is a stub anyway (`# ... build dispatch + sub-graph + merge nodes ...`); the unused import does not block syntactic compilation. (2) is a fixture limitation, not a correctness issue — the doc already tells authors at line 110-114 that the `compile()` override path is rare and to surface a feature request first.

**Action / Recommendation:** *Either* (a) drop the `GraphEdge` import from the snippet (one-line edit), *or* (b) replace `nodes=[...]` with `nodes=[...], edges=[GraphEdge(source=..., target=...)]` so the import is used. Option (a) is simpler. For (2), append one line to the doc's §Testing section noting that `compile_step_in_isolation` runs the step in a one-node graph without reducer channels; for `compile()`-override steps that emit reducer-merged channels, full integration tests (compile_spec + dispatch) are the right choice. Both fixes are doc-only; safe to land at next-touch. **Not propagated** — narrowly-scoped to T06's own doc.

## Additions beyond spec — audited and justified

| Addition | Justification | Verdict |
|---|---|---|
| 7 fixture tests (spec asked for "at least one") | Spec called for at least one; Builder shipped 7 covering happy path + None initial_state + state-merge preservation + error propagation + call independence + importability + layer placement. Each targets a distinct invariant; no tautologies. | ✅ Justified |
| 19 doc-snippet tests | Each pins a specific AC or carry-over invariant (AC-1 through AC-9 + CARRY-T05-MEDIUM-2 + TA-LOW-04 + TA-LOW-09). High but justified given the doc is load-bearing per ADR-0008 §Documentation surface ("a doc gap at any tier is a regression"). | ✅ Justified |
| `MyFanOutStep` snippet in §Advanced — overriding `compile()` directly | Spec Deliverable 1 §Step base class contract calls for the `compile()` upgrade path with an example. Builder shipped one. Stub body is intentional (the example is illustrative; the real fan-out wiring lives in `_compiler.py` for `FanOutStep`). | ✅ Justified (with LOW-3 doc-hygiene caveat) |
| `_mid_run_*` and retry framework keys named in §State-channel conventions | Spec called for "don't reach for `_mid_run_*` framework keys"; Builder additionally enumerated `last_exception`, `_retry_counts`, `_non_retryable_failures` (the retry-machinery keys). Strictly broader than the spec — but useful for authors who would otherwise discover these the hard way. | ✅ Justified |
| `StubLLMAdapter` integration pattern in §Testing (lines 263-277) | Spec called for "at least one worked test using `compile_step_in_isolation`"; Builder additionally documented the integration-test pattern with stub LLM. Useful for downstream consumers writing custom-step + LLM-step workflows; cross-links to `tests/workflows/test_summarize.py` for the full pattern. | ✅ Justified |

## Gate summary

| Gate | Command | Result |
|---|---|---|
| Pytest | `uv run pytest` | ✅ 746 passed, 9 skipped, 24 warnings (24 warnings = pre-existing `result.plan` deprecation on M19 T03 alias; not new) |
| Layer rule | `uv run lint-imports` | ✅ 4 contracts kept, 0 broken |
| Ruff | `uv run ruff check` | ✅ All checks passed |
| Spec smoke 1 | `test -f docs/writing-a-custom-step.md` | ✅ |
| Spec smoke 2 | `uv run python -c "from ai_workflows.workflows.testing import compile_step_in_isolation; print('OK')"` | ✅ |
| Spec smoke 3 | `uv run pytest --doctest-modules docs/writing-a-custom-step.md` | ⚠️ Collected 0 items — `--doctest-modules` does not collect markdown; the actual doctest-compilability check is `tests/docs/test_writing_custom_step_snippets.py::test_all_python_blocks_compile`, which passes. The spec's smoke command is loosely-worded (markdown isn't a "module"). Not a finding. |
| Spec smoke 4 | `grep -E '^## §' docs/writing-a-custom-step.md` | ⚠️ Returns nothing — doc uses `## Section name` (no literal `§` in section headings). Sections are present and verified by `test_section_structure`. The spec's grep was loosely-worded (the spec text itself uses `§` as a section-naming convention but the actual headings drop the symbol). Not a finding. |
| Doc cross-link checker | `uv run pytest tests/docs/test_docs_links.py` | ✅ 3 passed |
| End-to-end fixture smoke | `uv run python -c "...AddOneStep + compile_step_in_isolation..."` | ✅ Returns `{'run_id': '', 'last_exception': None, '_retry_counts': {}, '_non_retryable_failures': 0, '_mid_run_tier_overrides': None, 'n': 1}` (LOW-2 captures the seeded-key leak). |

**Gate integrity verdict:** All Builder-claimed pass/fail outcomes verified independently. No gate the Builder reported passing now fails.

## Status-surface integrity

| Surface | Required state | Actual state | Verdict |
|---|---|---|---|
| Per-task spec `**Status:**` line | ✅ Implemented (2026-04-26) | ✅ Implemented (2026-04-26) | ✅ |
| Milestone README task table row 06 | ✅ Implemented (2026-04-26) | ✅ Implemented (2026-04-26) | ✅ |
| `tasks/README.md` row | n/a (file does not exist) | n/a | ✅ |
| Milestone README "Done when" checkboxes | n/a — M19 README §Exit criteria is numbered (not checkbox) | n/a | ✅ |
| AC-1 through AC-12 checkboxes in spec | All `[x]` | All `[x]` | ✅ |
| Carry-over checkboxes (TA-LOW-04 / TA-LOW-09 / CARRY-T05-MEDIUM-2) | All `[x]` | All `[x]` | ✅ |

All status surfaces flipped together. No drift across surfaces.

## Issue log — cross-task follow-up

| ID | Severity | Owner / next touch point | Status |
|---|---|---|---|
| M19-T06-ISS-LOW-1 | LOW | T07 Builder (architecture.md §Extension model adds back-link to writing-a-custom-step.md) | DEFERRED — propagated to T07 spec carry-over (see Propagation status below) |
| M19-T06-ISS-LOW-2 | LOW | T06 next-touch (Builder, cycle 2 — optional polish) | OPEN — fixture leaks framework-internal seeded keys; doc-only or fixture-only fix; both options recommended in finding |
| M19-T06-ISS-LOW-3 | LOW | T06 next-touch (Builder, cycle 2 — optional polish) | OPEN — `GraphEdge` unused import in `MyFanOutStep` snippet + reducer-merge divergence note for fan-out fixture limitation |

LOW-2 and LOW-3 are local to T06 and do not block PASS. They can land at next-touch (cycle-2 polish if any subsequent finding triggers a re-cycle) or be deferred indefinitely as cosmetic. No re-cycle is required to clear them.

## Deferred to nice_to_have

*None.* All findings have natural T06 or T07 owners.

## Propagation status

- **M19-T06-ISS-LOW-1 — `architecture.md §Extension model` cross-link** → propagated to `design_docs/phases/milestone_19_declarative_surface/task_07_extension_model_propagation.md` `## Carry-over from prior audits` section. T07's existing scope already touches `architecture.md §Extension model` (Deliverable: new subsection in architecture.md), so T07 is the natural owner of the back-link addition.

---

## Security review (2026-04-26)

Reviewed against the threat model in `.claude/agents/security-reviewer.md`. T06 is doc + new-fixture-module work. Threat surface is small: no subprocess, no network calls, no manifest changes, no new dependencies.

### Threat-model items covered

1. **Wheel contents** — `ai_workflows/workflows/testing.py` correctly lands in the wheel (`[tool.hatch.build.targets.wheel] packages = ["ai_workflows"]`). Verified with `unzip -l dist/jmdl_ai_workflows-0.2.0-py3-none-any.whl`: `ai_workflows/workflows/testing.py` present; `docs/writing-a-custom-step.md` absent from the wheel (docs/ is not under `ai_workflows/`). No `.env*`, no `design_docs/`, no `runs/`, no `*.sqlite3`, no `.claude/`, no `.github/` in the wheel.

2. **Subprocess / network surface in `testing.py`** — zero hits for `subprocess`, `os.system`, `httpx`, `requests`, `socket`, `eval`, `exec` in `ai_workflows/workflows/testing.py`. The fixture is pure in-memory LangGraph invocation.

3. **`ANTHROPIC_API_KEY` / `anthropic` SDK** — zero hits across the entire `ai_workflows/` package. KDR-003 boundary intact.

4. **Test hermeticity** — `tests/workflows/test_testing_fixtures.py`: no subprocess, no network, no filesystem writes. `tests/docs/test_writing_custom_step_snippets.py`: `compile(src, ..., "exec")` at line 107 is Python's built-in AST-level syntax check only; it compiles to a code object that is immediately discarded with no subsequent `exec()` call. No untrusted code execution.

5. **MCP HTTP bind address** — `ai_workflows/mcp/__main__.py:74` confirms `host: str = typer.Option("127.0.0.1", ...)`. Default remains loopback. T06 makes no MCP changes.

6. **KDR-003 alignment** — `docs/writing-a-custom-step.md` §User-owned code boundary explicitly states "ai-workflows never reads `ANTHROPIC_API_KEY`" is not required in this doc (framework boundary; KDR-013 is the correct cite here). Verified: no ANTHROPIC_API_KEY mention in doc; consistent with KDR-003.

7. **Layer rule** — `ai_workflows/workflows/testing.py` imports only `langgraph.constants`, `langgraph.graph`, `ai_workflows.workflows.spec`, `ai_workflows.workflows._compiler`. No upward import to surfaces. `lint-imports` 4/0 confirmed by functional auditor.

8. **Logging hygiene** — `testing.py` contains no `StructuredLogger` calls, no logging, no key/token emission.

9. **SQLite paths** — no SQLite in `testing.py` (intentionally, per KDR-009 isolation note in docstring). No new path handling introduced.

### 🔴 Critical — must fix before publish/ship

None.

### 🟠 High — should fix before publish/ship

None.

### 🟡 Advisory — track; not blocking

**ADV-1 — SSRF advisory absent from `docs/writing-a-custom-step.md` §Worked example**

**File:** `docs/writing-a-custom-step.md`, lines 116–172 (`WebFetchStep` worked example).

**Threat-model item:** Wheel contents (public consumer-facing doc shipped in sdist; `docs/` lands in sdist via hatchling default-include behaviour).

**What:** The `WebFetchStep` example accepts `state[self.url_field]` as the URL passed directly to `httpx.AsyncClient().get()`. The `url_field` parameter is framework-author-controlled at step instantiation time, but the URL value itself is end-user-controlled at run time (via `WorkflowSpec.input_schema`). The doc does not advise workflow authors that if their step accepts a user-supplied URL without validation, downstream consumers of the registered workflow are exposed to SSRF (server-side request forgery) — i.e. an attacker can supply `http://169.254.169.254/` (cloud metadata endpoint) or any internal-network URL.

The doc correctly marks the block `# doctest: +SKIP` and correctly notes `httpx` is not a project dependency. The §User-owned code boundary section accurately states "if your custom step calls a third-party API, manages credentials, or performs file I/O, the security of those operations is yours to own" (line 314). This partially covers the concern but does not name SSRF specifically for the network-fetch pattern, which is the primary Tier 3 use-case the `WebFetchStep` example teaches.

**Why advisory:** The framework does not execute the worked example (doctest: +SKIP), the URL value is workflow-author-controlled at registration time (a trusted author surface per KDR-013), and single-user local deployment reduces the blast radius. However, the doc is published on PyPI (via sdist long description and on the repo), and the `WebFetchStep` pattern is the primary motivating example for Tier 3. A downstream consumer copying the pattern without URL validation could expose themselves to SSRF if they later deploy as a service. Adding a one-line warning is the appropriate action for a public consumer-facing doc.

**Action:** In the `WebFetchStep` example comment block (around line 119–121) or at the end of the worked example, add a one-line advisory note: e.g. "If `url_field` is populated from end-user input, validate the URL before fetching (allowlist of domains or schemes) to prevent server-side request forgery." Safe to land at T06 next-touch or T07 (doc polish pass); does not block ship.

### Verdict: SHIP

T06 ships a pure doc + in-memory fixture module. No subprocess, no network calls, no manifest changes, no new dependencies, no secrets, no layer violations. The `compile_step_in_isolation` fixture is correctly public-surface (non-private path, documented, exported via `__all__`). The `WebFetchStep` SSRF advisory (ADV-1) is a doc-polish note for the next touch; it does not block publication. The pre-existing T01 HIGH-1 sdist-leakage finding (`.claude/`, `design_docs/`, `tests/` in sdist) remains folded to T08 and is unaffected by T06's changes — T06 adds `docs/writing-a-custom-step.md` to the sdist, which continues the pre-existing `docs/` pattern established by T05 and is not a new leakage class.

## Dependency audit (2026-04-26)

**Skipped — no manifest changes.** T06 cycle 1 added `ai_workflows/workflows/testing.py` (new), `docs/writing-a-custom-step.md` (Write-overwrite of T05's stub), `tests/workflows/test_testing_fixtures.py` (new), `tests/docs/test_writing_custom_step_snippets.py` (new), and `CHANGELOG.md`. Plus T06 spec status surfaces + milestone README task-table row 06 + a carry-over entry on T07's spec (LOW-1 propagation). Neither `pyproject.toml` nor `uv.lock` was touched, so the dependency-auditor pass is not triggered per /clean-implement S2.
