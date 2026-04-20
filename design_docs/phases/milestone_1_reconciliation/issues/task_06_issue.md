# Task 06 — Refit TierConfig + tiers.yaml — Audit Issues

**Source task:** [../task_06_refit_tier_config.md](../task_06_refit_tier_config.md)
**Source audit:** [../audit.md](../audit.md) (produced by [M1 Task 01](../task_01_reconciliation_audit.md))
**Audited on:** 2026-04-19 (cycle 1 post-build audit — overwrites the PENDING BUILDER pre-build file)
**Audit scope:** [task_06_refit_tier_config.md](../task_06_refit_tier_config.md), pre-build amendments in this file's prior revision, [../audit.md](../audit.md) T06 rows (`ai_workflows/primitives/tiers.py` §1, `tiers.yaml` §1a, `tests/primitives/test_tiers_loader.py` §3), [architecture.md](../../../architecture.md) §3 / §4.1 / §6 / §8.6 / §9, KDR-003 / KDR-007, [CHANGELOG.md](../../../../CHANGELOG.md) under `[Unreleased]`, the working-tree diff against `HEAD` (`CHANGELOG.md`, `ai_workflows/primitives/tiers.py`, `pricing.yaml`, `tests/primitives/test_tiers_loader.py`, `tiers.yaml`), plus fresh `uv run pytest` / `uv run ruff check` / `uv run lint-imports` runs.
**Status:** ✅ PASS on T06's explicit ACs **with MEDIUM forward-deferral to T07** for a runtime test-shape break in `tests/primitives/test_retry.py` that the new `TierConfig` signature exposes, and a MEDIUM note in `ai_workflows/primitives/retry.py`'s docstring that still references the removed `TierConfig.max_retries` field. Post-T03 carry-over [M1-T03-ISS-01](task_03_issue.md#-medium--m1-t03-iss-01-test_tiers_loaderpy-runtime-import-break-owned-by-t06) is **RESOLVED** — the offending test is deleted and the suite re-anchors on the post-refit tier surface.

## Design-drift check

Cross-checked every change against [architecture.md](../../../architecture.md) §3 / §4.1 / §6 / §8.6 / §9 + KDR-003 + KDR-007.

| Change | Reference | Drift? |
| --- | --- | --- |
| Rewrote `ai_workflows/primitives/tiers.py` around `LiteLLMRoute` / `ClaudeCodeRoute` discriminated `route` union | KDR-007 ("LiteLLM is the unified adapter for Gemini + Qwen/Ollama. … Claude Code CLI stays bespoke"); [architecture.md §4.1](../../../architecture.md) ("Tiers that route to LiteLLM-supported providers carry a LiteLLM model string; the `claude_code` tier carries a subprocess invocation spec.") | ✅ Aligned — the discriminator is the literal shape the architecture names. |
| Dropped `provider`, `model`, `max_tokens`, `temperature`, `api_key_env`, `base_url`, `max_retries` scalar fields | [architecture.md §4.1](../../../architecture.md) collapses these into the route sub-model; KDR-006/KDR-007 hand retry-and-pricing to LiteLLM and to T07's taxonomy | ✅ Aligned — same information is expressed via `route.model` / `route.api_base` / `route.cli_model_flag`; `max_retries` is the retry layer's concern (T07). |
| Added `max_concurrency` (default 1) + `per_call_timeout_s` (default 120) | [architecture.md §8.6](../../../architecture.md) ("Per-provider semaphore (e.g. Gemini free-tier QPS). Configured in `TierConfig`.") | ✅ Aligned — makes the §8.6 semaphore observable in the tier shape. |
| Renamed loader from `load_tiers()` → `TierRegistry.load()` | Task spec §Deliverables ("`TierRegistry.load(path)` parses `tiers.yaml` into `dict[str, TierConfig]`.") | ✅ Aligned — exact spec wording. |
| Dropped top-level `tiers:` wrapper in `tiers.yaml` | Task spec §Deliverables YAML example has no wrapper; `TierRegistry.load` reads the file as the mapping directly | ✅ Aligned — matches the spec example shape. |
| `tiers.yaml` now lists `planner / implementer / local_coder / opus / sonnet / haiku` | Task spec §Deliverables YAML; [architecture.md §4.3](../../../architecture.md) planner/worker nodes | ✅ Aligned. |
| `tiers.yaml` Gemini tiers use `gemini/gemini-2.5-flash` instead of spec's `gemini/gemini-2.0-flash` | Spec note ("Values can stay as-is from the pre-pivot file if the audit confirms they were never LiteLLM-sourced"); the committed pre-pivot file already pinned `gemini-2.5-flash` because `gemini-2.0-flash` was retired. | ✅ Aligned — spec authorises staying with the pre-pivot value. |
| `tiers.yaml` Ollama tier uses `ollama/qwen2.5-coder:32b` instead of spec's `ollama/qwen2.5-coder:14b` | Same spec note; the installed Qwen variant is 32b per the pre-pivot file | ✅ Aligned. |
| `pricing.yaml` trimmed to three claude CLI entries | Task AC-3 ("`pricing.yaml` contains only Claude Code CLI entries.") — executed in T06 despite [../audit.md](../audit.md) §1a assigning the modify row to T08; see [§Deviations](#-medium--m1-t06-iss-02-pricingyaml-trim-overlaps-t08-scope-deferred-for-re-shape-by-t08) | ✅ Aligned on the task-AC reading; conflict with the audit row surfaced in the CHANGELOG and below. |
| Kept env expansion (`${VAR:-default}`) and `tiers.<profile>.yaml` overlay | Not mentioned by the T06 spec, but inherited from the pre-T06 loader; no architecture rule forbids them; pre-T02 memory/P-22 still wants them | ✅ Aligned — no expansion of surface, only preservation. |
| No new dependency | n/a | ✅ |
| No new module or layer | n/a — `primitives/tiers.py` keeps its spot under the four-layer tree | ✅ |
| No LLM call, no checkpoint/resume path, no retry loop, no observability sink added | n/a | ✅ |

Nothing silently adopted from [../../../nice_to_have.md](../../../nice_to_have.md).

Drift check: **clean**.

## Acceptance Criteria grading

| # | AC | Evidence | Verdict |
| --- | --- | --- | --- |
| 1 | `tiers.yaml` parses into `dict[str, TierConfig]` without errors. | `test_committed_tiers_yaml_parses_into_tier_config_mapping` pins the six tier names (`planner`, `implementer`, `local_coder`, `opus`, `sonnet`, `haiku`) and asserts every entry is a `TierConfig` with `.name` populated from the YAML key. | ✅ |
| 2 | Each tier's `route` validates as `LiteLLMRoute` or `ClaudeCodeRoute`. | `test_committed_tiers_resolve_to_the_correct_route_variant` iterates the committed tiers and checks `isinstance(..., LiteLLMRoute/ClaudeCodeRoute)` + `.kind` per tier. Cross-checked by `test_claude_code_tiers_carry_the_expected_cli_model_flags` and `test_litellm_tiers_carry_gemini_and_ollama_model_strings`. | ✅ |
| 3 | `pricing.yaml` contains only Claude Code CLI entries. | `test_committed_pricing_yaml_has_only_claude_cli_entries` pins the set to `{claude-opus-4-7, claude-sonnet-4-6, claude-haiku-4-5-20251001}` with zero rates for all three. [pricing.yaml](../../../../pricing.yaml) mirrors this. See [§Deviations](#-medium--m1-t06-iss-02-pricingyaml-trim-overlaps-t08-scope-deferred-for-re-shape-by-t08) — T06 executes the trim despite [../audit.md](../audit.md) §1a assigning the modify row to T08. | ✅ (task-AC scope) |
| 4 | `tests/primitives/test_tiers.py` covers: discriminator round-trip, unknown-tier lookup, malformed YAML rejection. | File lives at `tests/primitives/test_tiers_loader.py` (name predates T06, kept to minimise churn and mirror audit row §3). Covered by `test_discriminator_round_trip_from_litellm_dict`, `test_discriminator_round_trip_from_claude_code_dict`, `test_discriminator_rejects_unknown_kind`, `test_discriminator_rejects_wrong_branch_fields`, `test_get_tier_raises_unknown_tier_error_for_missing_name`, `test_malformed_yaml_tier_rejected_with_validation_error`, `test_non_mapping_top_level_rejected`, plus missing/empty-file coverage. | ✅ |
| 5 | `uv run pytest` green. | T06-scope green (`uv run pytest tests/primitives/test_tiers_loader.py` → 22 passed). Full-suite remains red on pre-existing T07 / T08 / T09 / T11 carry-over (see [§Gate summary](#gate-summary)) — matches the T02/T03/T04/T05 T-scope reading. | ✅ (T06-scope) |

All five ACs pass under the T-scope reading that every prior M1 post-build audit has applied (see [task_02_issue.md § M1-T02-ISS-01](task_02_issue.md)).

## Carry-over from prior audits — grading

- [x] **M1-T03-ISS-01 · MEDIUM — RESOLVED.** Post-T03 the test `test_unknown_tier_error_is_not_a_configuration_error` imported `ConfigurationError` from the deleted `ai_workflows.primitives.llm.model_factory`. The T03 carry-over gave the Builder two options — re-anchor the assertion against a `ConfigurationError` surface re-exposed by `primitives/tiers.py`, or delete the test if the new shape makes the cross-class check pointless. The post-refit tier module exposes only `UnknownTierError`; no `ConfigurationError` class remains. The new suite's `test_discriminator_rejects_unknown_kind` + `test_get_tier_raises_unknown_tier_error_for_missing_name` supersedes the original intent (distinguishing a tier-name typo from a configuration error). The offending test is deleted; Source: [task_03_issue.md §M1-T03-ISS-01](task_03_issue.md). [task_03_issue.md](task_03_issue.md) flips this line from `DEFERRED` → `RESOLVED (fdc… + next T06 commit)` on its next re-audit touch point.

## 🟡 MEDIUM — M1-T06-ISS-01: `tests/primitives/test_retry.py` TierConfig construction breaks on new shape — OWNED BY T07

**Finding.** `tests/primitives/test_retry.py:237-245` constructs a `TierConfig` with the old flat-shape kwargs (`provider="openai_compat"`, `model="gemini-2.0-flash"`, `max_tokens`, `temperature`, `max_retries`). After the T06 refit those kwargs are gone — `TierConfig` now takes `(name, route, max_concurrency, per_call_timeout_s)` with `route` a discriminated union. Attempting that construction post-T06 raises `ValidationError` rather than succeeding.

The file does not regress at **collection** time (that was already broken by its `from anthropic import …` / `from pydantic_ai.models.function import FunctionModel` imports at module top — T07 owns the sweep), so no new gate turns red. The runtime break only shows up once T07 starts rewriting the module.

**Severity rationale — MEDIUM.** No T06 AC unmet; no architecture rule broken; impact is confined to downstream task scope.

**Action — forward-deferral propagation (CLAUDE.md):**

- Append a carry-over to [task_07_issue.md](task_07_issue.md) so T07's Builder picks up the new `TierConfig` shape when rewriting `tests/primitives/test_retry.py`. Concrete "what to implement" line: **drop the `TierConfig(provider=…, model=…, max_tokens=…, temperature=…, max_retries=…)` construction at `tests/primitives/test_retry.py:237-245`; rebuild it against the post-T06 discriminated-union shape (`TierConfig(name=…, route=LiteLLMRoute(model=…) | ClaudeCodeRoute(cli_model_flag=…))`); or, if the test is scoped to an error-taxonomy concern where `TierConfig` is incidental, use a stub object instead.** Back-link: [task_06_issue.md § M1-T06-ISS-01](#-medium--m1-t06-iss-01-testsprimitivesretrypy-tierconfig-construction-breaks-on-new-shape--owned-by-t07).
- When T07's post-build audit ticks the carry-over, flip this line to `RESOLVED (commit sha)` in the issue log.

## 🟡 MEDIUM — M1-T06-ISS-02: `pricing.yaml` trim overlaps T08 scope — DEFERRED for re-shape by T08

**Finding.** Task 06 AC-3 requires `pricing.yaml` to contain only Claude Code CLI entries, but [../audit.md](../audit.md) §1a assigns the `pricing.yaml` MODIFY row to **T08** ("LiteLLM now supplies base per-call cost (KDR-007); `pricing.yaml` reduces to only sub-model / override entries that `CostTracker.modelUsage` still needs."). The pre-build T06 issue file's "Rows from audit.md this task must execute" §MODIFY table reflected the audit's assignment — it omitted `pricing.yaml`.

Per CLAUDE.md Builder convention ("Issue file is authoritative amendment to task file. If they disagree, task file wins; call out the conflict first."), the T06 Builder executed the AC-3 trim (removed the `gemini-2.5-flash` + `qwen2.5-coder:32b` rows; left the three claude CLI rows). The trim is deliberately minimal so that T08 can still reshape the file around `CostTracker.modelUsage` overrides without rework friction.

**Severity rationale — MEDIUM.** Spec/audit conflict, surfaced and resolved with a documented deviation rather than an escalation; downstream impact is re-shape, not re-do.

**Action — forward-deferral propagation (CLAUDE.md):**

- Append a carry-over to [task_08_issue.md](task_08_issue.md) noting that `pricing.yaml` has already been trimmed to the three claude CLI rows, and that T08's `CostTracker` refit may **reshape** the file further if the `modelUsage` sub-model aggregation needs sub-model override entries (per [../audit.md](../audit.md) §1a wording). Concrete "what to implement" line: **if the `CostTracker` refit requires sub-model override rows in `pricing.yaml`, add them on top of the existing three claude CLI entries; otherwise leave the file as-is. If `CostTracker` no longer reads `pricing.yaml` at all, drop the file and remove the `load_pricing` import/call sites.** Back-link: [task_06_issue.md § M1-T06-ISS-02](#-medium--m1-t06-iss-02-pricingyaml-trim-overlaps-t08-scope-deferred-for-re-shape-by-t08).
- When T08's post-build audit ticks the carry-over (either "no further reshape needed" or "reshaped — net state documented"), flip this line to `RESOLVED (commit sha)`.

## 🟡 MEDIUM — M1-T06-ISS-03: `ai_workflows/primitives/retry.py` docstring references removed `TierConfig.max_retries` — OWNED BY T07

**Finding.** `ai_workflows/primitives/retry.py` still carries docstring language referencing `TierConfig.max_retries`:

- [`ai_workflows/primitives/retry.py:35`](../../../../ai_workflows/primitives/retry.py) — `* ``primitives/tiers.py`` — ``TierConfig.max_retries`` holds the per-tier budget for our retry layer; callers pass it in as ``max_attempts``.`
- [`ai_workflows/primitives/retry.py:131`](../../../../ai_workflows/primitives/retry.py) — `per-tier budget pass ``tier_config.max_retries`` here.`

After the T06 refit `TierConfig.max_retries` no longer exists — KDR-007 delegates transient retry to LiteLLM under the LiteLLM adapter. The docstring is now stale.

**Severity rationale — MEDIUM.** Documentation drift, not a behavioural break. `primitives/retry.py` is already a MODIFY target for T07 ([../audit.md](../audit.md) §1), so T07's rewrite will purge the docstring naturally.

**Action — forward-deferral propagation (CLAUDE.md):**

- Append a carry-over to [task_07_issue.md](task_07_issue.md) so T07's Builder knows to drop the `TierConfig.max_retries` references from the retry module's docstrings while rewriting around the three-bucket taxonomy. Concrete "what to implement" line: **during the KDR-006 retry-taxonomy rewrite, drop the `TierConfig.max_retries` / `tier_config.max_retries` docstring references at `ai_workflows/primitives/retry.py:35` and `:131`; the field was removed by T06.** Back-link: [task_06_issue.md § M1-T06-ISS-03](#-medium--m1-t06-iss-03-ai_workflowsprimitivesretrypy-docstring-references-removed-tierconfigmax_retries--owned-by-t07).
- When T07's post-build audit ticks the carry-over, flip this line to `RESOLVED (commit sha)`.

## 🟢 LOW — M1-T06-ISS-04: `scripts/m1_smoke.py` imports the removed `load_tiers` — ✅ RESOLVED BY T13 (2026-04-19)

**Finding.** `scripts/m1_smoke.py:35` still contains `from ai_workflows.primitives.tiers import load_pricing, load_tiers`. T06 removed `load_tiers` (replaced by `TierRegistry.load`). The file was already broken post-T03 (imports `pydantic_ai`, `llm.model_factory`, `WorkflowDeps`), so the gate is not regressed — the file cannot be executed.

**Severity rationale — LOW.** Documentation-grade file, excluded from `scripts/spikes/` but still orphaned; belongs to **T13** (milestone close-out) per the [milestone README](../README.md) task-order graph (T13 closes the loop on orphaned pre-pivot scripts). T06 does not newly break it.

**Action — forward-deferral propagation (CLAUDE.md):**

- Append a note to [task_13_issue.md](task_13_issue.md) so T13's Builder knows to decide the file's fate (rewrite around the new substrate, or delete — both are valid close-out moves). Concrete "what to implement" line: **either rewrite `scripts/m1_smoke.py` against the post-pivot substrate (LiteLLM adapter + `TierRegistry.load`) or delete it entirely; the file is currently unreachable because it imports `pydantic_ai`, `llm.model_factory`, `WorkflowDeps`, and `load_tiers` — all removed in M1.** Back-link: [task_06_issue.md § M1-T06-ISS-04](#-low--m1-t06-iss-04-scriptsm1_smokepy-imports-the-removed-load_tiers--owned-by-t13).

**Resolution (T13 milestone close-out, 2026-04-19).** T13 chose the delete branch: `scripts/m1_smoke.py` is gone. Rewriting it against the post-pivot substrate would need the M2 LiteLLM adapter + the M3 workflow runner, neither of which exist yet. A post-pivot smoke script will be reintroduced in M3 when there is a runnable workflow to smoke-test. Verified by `tests/test_scaffolding.py::test_scripts_m1_smoke_removed_per_m1_t06_iss_04_and_m1_t10_iss_01`.

## Additions beyond spec — audited and justified

1. **`max_concurrency` + `per_call_timeout_s` keeping their defaults (1 / 120).** The task spec's YAML example overrides these on a subset of tiers (`planner` / `implementer` → 2, `opus` → 600). The committed `tiers.yaml` carries the same overrides. Defaults are explicit in the model so an absent-from-YAML field still validates.
2. **Env expansion (`${VAR:-default}`) preserved.** The T06 spec does not mention env expansion, but the pre-T06 loader implemented it (P-22) and the committed `tiers.yaml` relies on it for `api_base: "${OLLAMA_BASE_URL:-http://localhost:11434}"`. Preserving the feature keeps the committed file working without hard-coding the LAN address. No architecture rule forbids it; KDR-007 is agnostic to how the `api_base` string reaches the LiteLLM adapter.
3. **`tiers.<profile>.yaml` overlay preserved.** Same rationale — pre-T06 feature, useful for local vs. repo defaults. Spec-silent; not a new surface.
4. **Ollama tier uses model `ollama/qwen2.5-coder:32b`.** Spec example says `:14b`; committed repo state was `:32b`. Spec explicitly authorises "values can stay as-is from the pre-pivot file if the audit confirms they were never LiteLLM-sourced."
5. **`TierRegistry` as a classmethod-only class.** The spec names `TierRegistry.load(path)` without prescribing instance state. A classmethod-only shape is the minimum viable surface; callers that want caching cache the returned dict.

No additions that grow coupling or fabricate scope — every item is either preservation of a pre-T06 behaviour or a cleaner spelling of the spec text.

## Gate summary

| Gate | Command | Result |
| --- | --- | --- |
| ruff | `uv run ruff check` | ✅ `All checks passed!` |
| import-linter | `uv run lint-imports` | ✅ `Contracts: 2 kept, 0 broken.` |
| pytest (T06-scope) | `uv run pytest tests/primitives/test_tiers_loader.py` | ✅ 22 passed in 0.04s |
| pytest (full suite) | `uv run pytest --tb=line -q` | ❌ 3 collection errors (T07/T09/T11 — `test_retry.py` / `test_logging.py` / `test_cli.py`) + 17 failures (13 × `test_cost.py` via M1-T05-ISS-01 → T08; 4 × `test_scaffolding.py` via logfire → T09). **Zero T06-owned failures**; matches the T-scope reading in [task_02_issue.md § M1-T02-ISS-01](task_02_issue.md). |

## Issue log — cross-task follow-up

| ID | Severity | Owner | Status |
| --- | --- | --- | --- |
| M1-T03-ISS-01 | 🟡 MEDIUM | T06 | ✅ RESOLVED — offending test deleted; carry-over ticked. |
| M1-T06-ISS-01 | 🟡 MEDIUM | T07 | ✅ RESOLVED (T07 901b67c) — `test_retry.py` `TierConfig` construction fixed; carry-over ticked in [task_07_issue.md](task_07_issue.md). |
| M1-T06-ISS-02 | 🟡 MEDIUM | T08 | ✅ RESOLVED (T08 3af914b) — `pricing.yaml` kept as-is; cost.py no longer reads it; carry-over ticked in [task_08_issue.md](task_08_issue.md). |
| M1-T06-ISS-03 | 🟡 MEDIUM | T07 | ✅ RESOLVED (T07 901b67c) — `retry.py` docstring drift corrected; carry-over ticked in [task_07_issue.md](task_07_issue.md). |
| M1-T06-ISS-04 | 🟢 LOW | T13 | ✅ RESOLVED — T13 close-out deleted `scripts/m1_smoke.py` (2026-04-19). |

## Deferred to nice_to_have

_None._ No T06 finding maps to an item in [../../../nice_to_have.md](../../../nice_to_have.md).

## Propagation status

- [task_03_issue.md § M1-T03-ISS-01](task_03_issue.md) — flips `DEFERRED → RESOLVED` on its next re-audit touch point.
- [task_07_issue.md](task_07_issue.md) — carry-over appended covering M1-T06-ISS-01 (test_retry.py `TierConfig` construction) and M1-T06-ISS-03 (retry.py docstring drift).
- [task_08_issue.md](task_08_issue.md) — carry-over appended covering M1-T06-ISS-02 (pricing.yaml post-T06 shape).
- [task_13_issue.md](task_13_issue.md) — carry-over appended covering M1-T06-ISS-04 (scripts/m1_smoke.py orphaned import).
