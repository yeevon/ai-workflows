# Task 01 — `WorkflowSpec` + step-type taxonomy + `register_workflow` entry point — Audit Issues

**Source task:** [../task_01_workflow_spec.md](../task_01_workflow_spec.md)
**Audited on:** 2026-04-26
**Audit scope:** `ai_workflows/workflows/spec.py` (new), `ai_workflows/workflows/__init__.py` (modified), `tests/workflows/test_spec.py` (new), `CHANGELOG.md` entry. Cross-referenced against ADR-0008 (load-bearing decision), `architecture.md` §3 four-layer rule + §6 dep table + §9 KDRs (002 / 003 / 004 / 008 / 013), Builder's cycle-1 report, and the three task gates run from scratch.
**Status:** ✅ PASS

## Design-drift check

No drift detected. Cross-reference against the seven load-bearing KDRs + the four-layer rule:

- **Four-layer rule.** `spec.py` imports stdlib + `pydantic` + `ai_workflows.primitives.retry` + `ai_workflows.primitives.tiers`. The `workflows → primitives` direction is permitted; `lint-imports` reports 4 contracts kept, 0 broken (re-run from scratch this audit). No graph or surface imports. `CompiledStep` is imported under `TYPE_CHECKING` only — no runtime dependency on the as-yet-unshipped `_compiler` module.
- **KDR-002 / KDR-008 (MCP wire surface).** No MCP imports added. `WorkflowSpec` is a pydantic data object — no LangGraph type leaks into the MCP schemas.
- **KDR-003 (no Anthropic API).** No `anthropic` SDK import; no `ANTHROPIC_API_KEY` reference. Spec API does not introduce a provider surface.
- **KDR-004 (validator pairing).** Strengthened to construction invariant for `LLMStep` exactly as ADR-0008 mandates: `response_format: type[BaseModel]` is a required field with no default. An unvalidated `LLMStep` cannot be expressed in the type system. Verified via `test_llm_step_requires_response_format`.
- **KDR-006 (three-bucket retry).** `RetryPolicy` is re-exported from `primitives.retry` — no parallel class is defined in `spec.py`. Verified by `test_retry_policy_reexport_is_same_object` (asserts `RetryPolicy is PrimitivesRetryPolicy`).
- **KDR-009 (SqliteSaver checkpoints).** No checkpoint logic added; T01 ships pure data classes only.
- **KDR-013 (user-owned external code; in-package collision guard).** `register_workflow()` defers to existing `register(name, builder)`; the collision check (different-builder collision raises `ValueError`) fires reliably. Manually verified: registering an in-package builder under name `"planner"` then calling `register_workflow(spec)` with the same name raises with the actionable message, refusing to shadow.

ADR-0008 §Step taxonomy lists `LLMStep / ValidateStep / GateStep / TransformStep / FanOutStep` — all five built-ins ship with the documented field surfaces; no taxonomy extension beyond ADR-0008.

## AC grading

| AC | Status | Notes |
| -- | ------ | ----- |
| AC-1 — module + types + `frozen + extra="forbid"` + RetryPolicy re-export | ✅ PASS | `spec.py` ships `WorkflowSpec`, `Step`, `LLMStep`, `ValidateStep`, `GateStep`, `TransformStep`, `FanOutStep`, `RetryPolicy` re-export, `register_workflow`. Every model has `model_config = ConfigDict(frozen=True, extra="forbid")` (with `arbitrary_types_allowed=True` where pydantic v2 needs it for `type[BaseModel]` and callable fields). `RetryPolicy` is `from ai_workflows.primitives.retry import RetryPolicy as RetryPolicy`; identity preserved. |
| AC-2 — `LLMStep` requires `response_format`; both / neither prompt-source raises | ✅ PASS | `response_format` is a required pydantic field (no default). Tests `test_llm_step_requires_response_format`, `test_llm_step_requires_exactly_one_prompt_source_both_set` (asserts `"got both"`), `test_llm_step_requires_exactly_one_prompt_source_neither_set` (asserts `"got neither"`) all green. Error messages match Deliverable 1's prescribed wording. |
| AC-3 — `Step.execute()` `NotImplementedError` pointing to doc + `compile()` signature locked + base default never used by built-ins | ✅ PASS | `Step.execute()` raises `NotImplementedError(...docs/writing-a-custom-step.md...)`; covered by `test_step_base_class_execute_raises_when_unimplemented`. `Step.compile(self, state_class, step_id) -> CompiledStep` signature locked; body raises `NotImplementedError("…lands in M19 T02…")` (Builder chose this over the spec's `...  # noqa: stub` body — clearer failure mode given the typed return; reasonable interpretation, see LOW-3). Built-in step types do not override `compile()` at T01 — consistent with spec ("T02 owns the wiring"). |
| AC-4 — cross-step invariants (empty steps, unknown tier, prompt exclusivity, FanOut warn, name collision) | ✅ PASS | All five invariants verified: `test_register_workflow_empty_steps_raises`, `test_register_workflow_unknown_tier_raises_with_typo_message` (asserts `"planner-syth"` + at least one of the available tier names appear in the message; manually re-verified the message *does* include the full set as required), `test_register_workflow_collision_raises`, `test_fan_out_step_unresolvable_iter_field_warns_not_raises` (UserWarning, not raise; registration succeeds). Prompt exclusivity is enforced at construction time (Q2). |
| AC-5 — `register_workflow` calls `register()`; builder thunk raises `NotImplementedError("compiler lands in M19 T02")` | ✅ PASS | `test_register_workflow_calls_underlying_register` confirms `list_workflows()` contains the registered name and the builder thunk raises `NotImplementedError("compiler lands in M19 T02")` when invoked. |
| AC-6 — `tests/workflows/test_spec.py` exists with the 8 tests, hermetic, <1s | ✅ PASS | 16 tests (Builder added 8 beyond spec — `test_workflow_spec_extra_field_raises`, `test_llm_step_with_prompt_template_constructs`, `test_llm_step_with_prompt_fn_constructs`, `test_retry_policy_reexport_is_same_object`, expanded coverage). Wall-clock 0.80 s. Hermetic — imports stdlib + pydantic + `ai_workflows.workflows` + `ai_workflows.primitives.tiers` only; no LangGraph, no provider calls. Registry-isolation autouse fixture (`_reset_for_tests()` before/after each test) is correctly wired. Spec called for ≥8; the 8 additions are useful coverage with no scope creep. |
| AC-7 — Deliverable 6 smoke prints `T01 smoke OK`, exit 0 | ✅ PASS | Re-ran the `python -c` block from scratch this audit: stdout `T01 smoke OK`, exit 0. (One pydantic `UserWarning` about `schema` shadowing — see LOW-1; cosmetic, does not affect exit code.) |
| AC-8 — `__init__.py` re-exports new surface alongside M16; M16 imports unaffected | ✅ PASS | `__all__` lists every M19 export plus the original M16 + earlier names. Manually verified `register`, `get`, `list_workflows`, `ExternalWorkflowImportError`, `load_extra_workflow_modules` still import and behave unchanged. Module docstring extended with an "M19 Task 01" subsection. |
| AC-9 — module docstring cites M19 T01 + ADR-0008 + KDR-004 + KDR-013 + four-tier extension model; class docstrings cite role + audience | ✅ PASS | `spec.py` module docstring cites all five required references plus the four-tier model. Each public class has a docstring with role + audience (e.g. `LLMStep`: "Audience: any consumer using the declarative authoring surface", `WorkflowSpec`: "Audience: external workflow authors using the declarative authoring surface (Tier 1 + Tier 2 per ADR-0008)"). Field-level docstrings are present on every public attribute. |
| AC-10 — `lint-imports` 4 contracts kept; `spec.py` imports stdlib + pydantic + `ai_workflows.workflows` only | ✅ PASS *(with note)* | `lint-imports` reports 4 contracts kept, 0 broken (re-run from scratch). `spec.py` imports stdlib + pydantic + `ai_workflows.primitives.retry` + `ai_workflows.primitives.tiers`. The "primitives only" addition is required by Deliverable 1 (Q1 lock — `RetryPolicy` re-export from `primitives.retry`) and by the `WorkflowSpec.tiers: dict[str, TierConfig]` field type. The `workflows → primitives` direction is allowed by the four-layer rule. Internal spec inconsistency (AC-10 wording vs Deliverable 1) — see LOW-2. Per spec discipline (Deliverable wins on a "what to ship" item; AC text is a verification statement that is internally inconsistent with the deliverable it should be verifying), grading PASS-with-note. |
| AC-11 — `pytest`, `lint-imports`, `ruff check` all green | ✅ PASS *(with caveat)* | All three gates pass. `pytest` reports 658 passed, 9 skipped, 1 failed — the one failure is `tests/test_main_branch_shape.py::test_design_docs_absence_on_main`, **pre-existing** and orthogonal to M19 T01. Verified by stashing M19 T01 changes and re-running: failure persists. Root cause is the `AIW_BRANCH` env-var detection on `design_branch` (defaults to `"main"` when unset; the `@pytest.mark.skipif(_ON_DESIGN, …)` guard never fires). Tracked separately — see DEFERRED-1. M19 T01 itself does not introduce or modify any test that fails. |
| AC-12 — CHANGELOG entry under `[Unreleased]` matches Deliverable 7 | ✅ PASS | `### Added — M19 Task 01: WorkflowSpec + step-type taxonomy + register_workflow entry point (2026-04-26)` under `[Unreleased]`. Mentions all five public exports + `RetryPolicy` re-export framing + the `register_workflow` cross-step invariants + the T01-stub-builder behaviour + ADR-0008 status. Keep-a-Changelog vocabulary only (`### Added`). |

All 12 ACs pass. Smoke verification (Deliverable 6) green.

## 🔴 HIGH

*None.*

## 🟡 MEDIUM

*None.*

## 🟢 LOW

### LOW-1 — Pydantic `UserWarning` on `ValidateStep.schema` field shadowing

**Where:** `ai_workflows/workflows/spec.py:212` (the `class ValidateStep(Step):` declaration).

**Symptom:** Importing `spec.py` (or any module that imports it) emits a one-time pydantic `UserWarning`:

```
UserWarning: Field name "schema" in "ValidateStep" shadows an attribute in parent "Step"
```

`BaseModel.schema()` is a deprecated v1-era method on pydantic v2; defining a field named `schema` on a subclass triggers pydantic's shadow-detection warning. The field works correctly — `ValidateStep(target_field="y", schema=_FooOut).schema` returns the model class as expected — but the warning surfaces in pytest output, smoke runs, and any consumer-facing import.

**Impact:** Cosmetic. Test green-ness is preserved (warnings, not errors). The warning is visible in the Deliverable 6 smoke output (Auditor-run) and in `uv run pytest tests/workflows/test_spec.py -v` summary lines.

**Why this is a LOW (not a Builder finding):** The field name `schema` is **mandated by the spec** — Deliverable 1: *"`ValidateStep(Step)` — schema validator without an LLM call. Fields: `target_field: str` (state-key whose value the validator checks), `schema: type[BaseModel]`."* The Builder did not deviate. The conflict is between the spec wording and pydantic v2's parent-attribute shadowing rule. Renaming the field (e.g. `model: type[BaseModel]` or `schema_model: type[BaseModel]`) is the structural fix but lands as a spec amendment, not a Builder change.

**Action / Recommendation:** Open a spec-amendment ticket on `task_01_workflow_spec.md` to consider renaming `ValidateStep.schema` → `ValidateStep.model` (or another non-shadowing name) before the spec API stabilises in 0.3.0. The rename would compose cleanly with `WorkflowSpec.input_schema` / `output_schema` (which already use the `_schema` suffix). Until then, suppressing the warning at module top with `warnings.filterwarnings("ignore", message=r'Field name "schema" .* shadows an attribute', category=UserWarning)` is a one-liner workaround that hides the noise without changing the public API. **Decision needed:** rename (cleaner) vs suppress (keeps Q1-locked field name). Recommend deferring to T05 / T06 documentation review where field naming gets a fresh read; flagging here for visibility.

### LOW-2 — Internal spec inconsistency: AC-10 wording vs Deliverable 1 imports

**Where:** `design_docs/phases/milestone_19_declarative_surface/task_01_workflow_spec.md` AC-10 (line 219).

**Symptom:** AC-10 reads *"`spec.py` imports stdlib + `pydantic` + `ai_workflows.workflows` only; no graph or primitives imports."* But Deliverable 1 (line 16) explicitly requires *"Imports stdlib + `pydantic` + `ai_workflows.workflows` + `ai_workflows.primitives.retry` (for `RetryPolicy` re-export per Q1)."* And `WorkflowSpec.tiers: dict[str, TierConfig]` (Deliverable 1, line 20) requires `from ai_workflows.primitives.tiers import TierConfig` to type the dict values.

**Impact:** A future audit (or a Builder reading AC-10 in isolation) could grade AC-10 as failed and trigger a rework that strips the required `primitives.retry` and `primitives.tiers` imports — which would silently break `RetryPolicy` re-export identity (KDR-006 spirit) and the `WorkflowSpec.tiers` field type. The four-layer rule explicitly allows `workflows → primitives`; the AC-10 wording is more restrictive than the architecture rule.

**Action / Recommendation:** Edit AC-10 to read: *"Layer rule preserved — `uv run lint-imports` reports 4 contracts kept, 0 broken. `spec.py` imports stdlib + `pydantic` + `ai_workflows.primitives.retry` + `ai_workflows.primitives.tiers` only (the permitted `workflows → primitives` direction); no graph or surface imports."* This aligns AC-10 with Deliverable 1 + the four-layer rule and prevents the inconsistency from recurring.

Owner: T01 spec amendment (apply at any time before milestone close-out at T08).

### LOW-3 — `Step.compile()` body diverges from spec text (NotImplementedError vs `... # noqa: stub`)

**Where:** `ai_workflows/workflows/spec.py:120-138` vs spec Deliverable 3 lines 117-127.

**Symptom:** Spec Deliverable 3 shows the `compile()` stub body as `...  # noqa: stub`. Builder ships `raise NotImplementedError("…lands in M19 T02 (_compiler.py)…")` instead.

**Impact:** None — Builder's choice is **better** than the spec text. A method with a typed return (`-> CompiledStep`) and an `Ellipsis` body silently returns `None` if invoked, which would propagate as a confusing downstream error if anything hit it before T02. The `NotImplementedError` produces an immediately diagnostic failure with a forward-compatible message. The locked **public contract** is the signature; the body is implementation detail. Builder's deviation is reasonable.

**Action / Recommendation:** Optional spec hygiene — annotate Deliverable 3's stub with a note that the body shape is Builder's choice (e.g. *"`NotImplementedError(...)` or `...` are both acceptable; the locked contract is the signature, not the body"*). No source-code change required.

## Additions beyond spec — audited and justified

1. **8 extra tests** (16 total vs spec's 8). The additions are: `test_workflow_spec_extra_field_raises`, `test_llm_step_with_prompt_template_constructs`, `test_llm_step_with_prompt_fn_constructs`, `test_retry_policy_reexport_is_same_object`, plus the M11-fix coverage broken into separate happy-path + warning-path tests. Each addition exercises a distinct contract (`extra="forbid"`, the two valid prompt-source paths, RetryPolicy identity). No coupling beyond what's already required. Net coverage increase, no scope creep.

2. **`arbitrary_types_allowed=True`** on `LLMStep`, `ValidateStep`, `TransformStep`, `WorkflowSpec` model configs. Required by pydantic v2 to allow `type[BaseModel]` and `Callable` fields without registering a custom schema. Implementation detail of pydantic typing, not new surface.

3. **`_validate_llm_step_tiers` and `_warn_fan_out_unresolvable_fields` helpers** factored out of `register_workflow()` body. Improves readability of the main entry-point function; both helpers are private (leading underscore). Net positive; not visible in the public surface.

4. **TYPE_CHECKING-guarded `CompiledStep` import.** Avoids a runtime dependency on `_compiler.py` (T02). Necessary given the type annotation on `Step.compile() -> CompiledStep`. Standard Python idiom; no concern.

5. **`stacklevel=3` on the `FanOutStep` warnings.** Makes the warning point at the caller's `register_workflow(spec)` line rather than at the helper internal. Quality-of-life improvement; no spec deviation.

All five additions are justified and within the spec's intent. No drive-by refactors of unrelated code.

## Gate summary

| Gate | Command | Result |
| -- | ------ | ----- |
| Pytest (full suite) | `uv run pytest` | 658 passed, 9 skipped, **1 failed (pre-existing)** in 29.21 s. Failure: `tests/test_main_branch_shape.py::test_design_docs_absence_on_main` — `AIW_BRANCH` env-var detection broken on `design_branch`. **Verified pre-existing** via `git stash` reproduction. Orthogonal to M19 T01. |
| Pytest (M19 T01 only) | `uv run pytest tests/workflows/test_spec.py -v` | 16 passed, 0 failed in 0.80 s. |
| Import-linter | `uv run lint-imports` | 4 contracts kept, 0 broken. Analyzed 40 files, 96 dependencies. |
| Ruff | `uv run ruff check` | All checks passed. |
| Smoke (Deliverable 6) | `uv run python -c "..."` (the embedded block) | Stdout `T01 smoke OK`; exit 0. |

All M19 T01-attributable gates green. The pre-existing main-branch-shape failure is logged as DEFERRED below.

## Issue log — cross-task follow-up

| ID | Severity | Owner / next touch point | Status |
| -- | -------- | ------------------------ | ------ |
| M19-T01-ISS-01 | LOW | Spec amendment on `task_01_workflow_spec.md` (`ValidateStep.schema` field-shadowing warning — see LOW-1). Defer touch-up to T05 / T06 documentation review. | OPEN |
| M19-T01-ISS-02 | LOW | Spec amendment on `task_01_workflow_spec.md` AC-10 wording (LOW-2). Apply inline at any time. | OPEN |
| M19-T01-ISS-03 | LOW | Spec hygiene note on Deliverable 3's stub body (LOW-3). Optional. | OPEN |
| M19-T01-ISS-04 | LOW | Pre-existing `tests/test_main_branch_shape.py::test_design_docs_absence_on_main` failure on `design_branch` — see DEFERRED-1 below. **Resolved 2026-04-26** by adding git-auto-detection to `_detect_branch()`; `AIW_BRANCH` env-var preserved as override. Full pytest now reports 659 passed (was 658 + 1 pre-existing failure). | RESOLVED |

## Deferred to nice_to_have

*Not applicable.* No findings naturally map to `nice_to_have.md` entries.

## Forward-deferral

### DEFERRED-1 — Pre-existing main-branch-shape test failure on `design_branch`

**Where:** `tests/test_main_branch_shape.py::test_design_docs_absence_on_main`.

**What:** The test guards "main must not contain `design_docs/`, `CLAUDE.md`, etc." It uses `_BRANCH = os.environ.get("AIW_BRANCH", "main").lower()` and `_ON_DESIGN = _BRANCH == "design"` to skip on `design_branch`. When `AIW_BRANCH` is unset (the default in `uv run pytest`), `_BRANCH == "main"` and the skip never fires, so the test runs on `design_branch` and fails because builder-only paths (`design_docs/`, `CLAUDE.md`, `.claude/commands/`, `tests/skill/`, `scripts/spikes/`) all exist on this branch by design.

**Verified pre-existing:** stashed all M19 T01 changes (`git stash`), re-ran `uv run pytest tests/test_main_branch_shape.py` — same failure. Re-running with `AIW_BRANCH=design uv run pytest tests/test_main_branch_shape.py` would skip the failing test and run `test_design_docs_presence_on_design_branch` instead (the inverse-direction guard).

**Why orthogonal to M19 T01:** M19 T01 changes nothing under `tests/test_main_branch_shape.py`, nothing under any of the watched paths' parents, and adds no env-var contract. The failure is independent of this cycle.

**Owner candidates:** Either the M13 T05 spec (which introduced the `_BRANCH`-detection mechanism) or a future workflow-tooling task that wires `AIW_BRANCH` into the local pytest harness automatically. Recommend filing a small follow-up issue to either (a) auto-detect the branch via `git rev-parse --abbrev-ref HEAD` so the test self-skips on `design_branch` without env-var ceremony, or (b) document the `AIW_BRANCH=design` requirement in `pyproject.toml`'s pytest config or in CONTRIBUTING.md.

**Status:** **RESOLVED 2026-04-26** — user requested this be fixed before starting M19 T02 rather than deferred. The fix adds `_detect_branch()` to `tests/test_main_branch_shape.py` that resolves the current branch via (1) `AIW_BRANCH` env override (preserved for CI), (2) `git rev-parse --abbrev-ref HEAD` auto-detection (`design_branch` → `design`), (3) `main` fallback when git isn't available. Verified: full `uv run pytest` reports 659 passed, 9 skipped, 0 failed; `AIW_BRANCH=design` and `AIW_BRANCH=main` overrides both still work as expected. Resolution is one self-contained edit to the test module — does not touch any M19 spec-API surface.

## Propagation status

*Not applicable for this cycle.* No findings forward-deferred to a specific future task. The one DEFERRED item (DEFERRED-1) has no natural M19 owner — surfaced to user instead per CLAUDE.md cross-cutting backlog convention.

LOW-1 / LOW-2 / LOW-3 are all spec-amendment items on `task_01_workflow_spec.md` itself and can be resolved inline by the user without crossing tasks.

---

## Security review (2026-04-26)

**Scope:** M19 Task 01 — `ai_workflows/workflows/spec.py` (new), `ai_workflows/workflows/__init__.py` (modified), `tests/workflows/test_spec.py` (new), `CHANGELOG.md` entry. No manifest changes; dependency-auditor skipped per /clean-implement S2 conditional. T01 is a pure data-model layer: no subprocess, no network, no SQLite, no provider surface.

### Checks performed

| Check | Command / method | Result |
| ----- | ---------------- | ------ |
| Wheel contents | `unzip -l dist/jmdl_ai_workflows-0.2.0-py3-none-any.whl` | Clean — `ai_workflows/` + `migrations/` + dist-info only. No `.env*`, no `design_docs/`, no `.claude/`, no `tests/`, no `runs/`. |
| sdist contents | `tar tzf dist/jmdl_ai_workflows-0.2.0.tar.gz` | Contains `.env.example`, `CLAUDE.md`, `.claude/` (agent prompts + `settings.local.json`), `design_docs/`, `.github/` — see HIGH-1 below. |
| KDR-003 / no Anthropic API | `grep -rn "ANTHROPIC_API_KEY\|import anthropic" ai_workflows/` | Zero hits. |
| Subprocess / network surface | Source review of `spec.py` | None. Pure data classes + pydantic validators. |
| Logging hygiene | `grep -rn "GEMINI_API_KEY\|Bearer \|Authorization\|prompt=\|messages=" spec.py` | Zero hits. |
| Error messages for secrets | Source review of all `ValueError` / `UserWarning` strings | No env vars, no file contents, no keys in any message. Only tier names and field names (user-supplied strings) appear. |
| `Step.execute()` error message | `spec.py:114-118` | Contains `docs/writing-a-custom-step.md` path string — documentation path only, no PII, no traversal vector. |
| Test hermetics | Source review of `tests/workflows/test_spec.py` | No filesystem writes, no subprocess calls, no network calls, no SQLite access, no `.env` reads. Registry-isolation autouse fixture cleanly wraps each test. |
| CHANGELOG entry | `CHANGELOG.md` M19 Task 01 block | No file-system paths, no secrets, no internal implementation details beyond intended public surface description. |
| `frozen=True` + `extra="forbid"` discipline | Source review of all model configs | All five step types and `WorkflowSpec` carry `frozen=True, extra="forbid"`. `arbitrary_types_allowed=True` added only where required by pydantic v2 for `type[BaseModel]` / `Callable` fields — no mutable-state injection path. |

### 🔴 Critical — must fix before publish/ship

*None.*

### 🟠 High — should fix before publish/ship

#### HIGH-1 — sdist contains `.claude/settings.local.json`, `CLAUDE.md`, agent prompts, and `design_docs/`

**Threat-model item:** Wheel / sdist contents leakage (surface 1).

**Where:** `dist/jmdl_ai_workflows-0.2.0.tar.gz` — verified by `tar tzf`. Affected entries:

- `jmdl_ai_workflows-0.2.0/.claude/settings.local.json` — contains the full local tool-permission allow-list for the operator's Claude Code session (exact `Bash(...)` / `Read(...)` rules, including the operator's home directory path `/home/papa-jochy/`). This is a builder-machine artefact; it has no meaning on a downstream consumer's machine and leaks the operator's username and workflow preferences.
- `jmdl_ai_workflows-0.2.0/.claude/agents/*.md` — full subagent system prompts (security-reviewer, dependency-auditor, builder, auditor, task-analyzer). These are development-tooling internals; publishing them to PyPI exposes the project's review and security gate procedures.
- `jmdl_ai_workflows-0.2.0/CLAUDE.md` — project instructions file including threat-model summary and KDR details.
- `jmdl_ai_workflows-0.2.0/design_docs/` — full architecture, ADRs, roadmap, and milestone specs.
- `jmdl_ai_workflows-0.2.0/.env.example` — placeholder-only (no real values; `GEMINI_API_KEY=` with an empty value). Not a secrets leak but is a configuration noise artefact in a published sdist.

**Severity note:** The wheel (`.whl`) is clean — this finding is sdist-only. `uvx` and `uv tool install` consume the wheel, not the sdist. However: (a) downstream packagers for Linux distributions (Debian, Arch, etc.) build from the sdist; (b) PyPI hosts and indexes the sdist; (c) `pip install --no-binary` or `uv pip install --no-binary` builds from sdist. The `.claude/settings.local.json` operator-path leak is the sharpest concern; `design_docs/` and `.claude/agents/` are IP/information-leakage.

**Note:** The wheel is clean. This finding pre-dates M19 T01 (the sdist exclusion gap is not introduced by T01's changes). It is surfaced here because the security review runs `uv build` as part of its standard check, and the finding is within scope of threat-model item 1. M19 T01 itself does not worsen the sdist leakage.

**Action:** Add a `[tool.hatch.build.targets.sdist]` exclude list to `pyproject.toml` before the next PyPI publish:

```toml
[tool.hatch.build.targets.sdist]
exclude = [
    ".claude/",
    "CLAUDE.md",
    ".env.example",
    ".env*",
    "design_docs/phases/",
    "evals/",
    "runs/",
    "*.sqlite3",
    ".github/workflows/",
]
```

`design_docs/architecture.md`, `design_docs/adr/`, and `design_docs/analysis/` may be intentionally included for downstream packagers — the owner should decide. `design_docs/phases/` (milestone + task specs) is definitively builder-only. The critical exclusion is `.claude/`.

Owner: should be applied before any 0.3.x publish; does not block M19 T01 functionality.

### 🟡 Advisory — track; not blocking

*None.* The T01 data-model layer introduces no new I/O, no prompt logging, no provider calls, and no new dependencies. The three points below are informational only.

- **`TransformStep.fn` and `LLMStep.prompt_fn` accept arbitrary callables.** These are user-supplied callables that the framework stores in frozen pydantic models and later invokes at dispatch time (T02+). No sanitisation is possible or appropriate (KDR-013 boundary). Confirmed out of scope per threat model.
- **`FanOutStep.iter_field` / `merge_field` warning messages embed user-supplied field-name strings.** The strings are echoed back to the calling process via `UserWarning` only — no log emission, no network transmission. No PII vector.
- **`register_workflow` error messages embed `spec.name` and tier name strings.** Both are user-supplied. The same analysis applies: raised as local `ValueError`, not logged or transmitted.

### Verdict: SHIP

T01's code changes (`spec.py`, `__init__.py` re-exports, `test_spec.py`) are clean against every applicable threat-model check. The wheel is clean. HIGH-1 (sdist leakage of `.claude/settings.local.json` and `design_docs/`) is a pre-existing publish-hygiene gap that does not block M19 T01 shipping — it should be patched in `pyproject.toml` before the next PyPI release regardless of milestone. No finding is introduced or worsened by T01.

## Dependency audit (2026-04-26)

**Skipped — no manifest changes.** T01 modified `ai_workflows/workflows/spec.py` (new), `ai_workflows/workflows/__init__.py`, `tests/workflows/test_spec.py` (new), and `CHANGELOG.md` only. Neither `pyproject.toml` nor `uv.lock` was touched, so the dependency-auditor pass is not triggered per /clean-implement S2.
