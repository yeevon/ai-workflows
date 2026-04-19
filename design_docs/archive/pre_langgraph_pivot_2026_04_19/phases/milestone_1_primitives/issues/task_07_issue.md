# Task 07 — Tiers Loader and Workflow Hash — Audit Issues

**Source task:** [../task_07_tiers_loader.md](../task_07_tiers_loader.md)
**Audited on:** 2026-04-18
**Audit scope:** full Task 07 surface —
[ai_workflows/primitives/tiers.py](../../../../ai_workflows/primitives/tiers.py),
[ai_workflows/primitives/workflow_hash.py](../../../../ai_workflows/primitives/workflow_hash.py),
[ai_workflows/primitives/llm/model_factory.py](../../../../ai_workflows/primitives/llm/model_factory.py)
(unknown-tier branch),
[tiers.yaml](../../../../tiers.yaml),
[pricing.yaml](../../../../pricing.yaml),
[tests/primitives/test_tiers_loader.py](../../../../tests/primitives/test_tiers_loader.py),
[tests/primitives/test_workflow_hash.py](../../../../tests/primitives/test_workflow_hash.py),
[tests/primitives/test_model_factory.py](../../../../tests/primitives/test_model_factory.py)
(renamed unknown-tier test),
[CHANGELOG.md](../../../../CHANGELOG.md) (M1 Task 07 entry),
the milestone [README.md](../README.md), sibling task files
(03 / 08 / 09 / 10 / 12) for interface-drift,
[design_docs/issues.md](../../../issues.md) (P-21 … P-25, CRIT-02),
[.github/workflows/ci.yml](../../../../.github/workflows/ci.yml) (secret
scan still clean on the expanded YAMLs), and
[pyproject.toml](../../../../pyproject.toml). All three gates executed
locally; public surface probed via REPL to confirm the committed
`tiers.yaml` / `pricing.yaml` load cleanly under Task 07's new parser.

**Status:** ✅ PASS — every acceptance criterion is satisfied with dedicated
tests, the M1-T03-ISS-12 carry-over is resolved, and three gates are green.
No OPEN issues. Three deviations from the task spec are called out and
justified below; none reduces the behavioural contract.

---

## 🔴 HIGH

_None._

## 🟡 MEDIUM

_None._

## 🟢 LOW

_None._

---

## Additions beyond spec — audited and justified

| Addition | Justification |
| --- | --- |
| `TierConfig.provider` keeps `"anthropic"` alongside the four providers named in the Task 07 YAML block | M1-T03-ISS-13 extended the Literal to `["claude_code", "anthropic", "ollama", "openai_compat", "google"]` so third-party Anthropic-API deployments continue to have a tested build path. The Task 07 spec dropped `"anthropic"` from the inline Literal; this deviation was accepted at Task 03 resolution time and carried forward. Called out in the Task 07 CHANGELOG Deviations list. |
| `ModelPricing` ships with `cache_read_per_mtok` / `cache_write_per_mtok` defaulted to `0.0` | Task 09's `calculate_cost()` sums four rates `(in * in_rate + out * out_rate + cr * cr_rate + cw * cw_rate) / 1e6`. Including the cache rates with `0.0` defaults means the canonical `pricing.yaml` rows (which only list `input_per_mtok` / `output_per_mtok`) validate today, and Task 09 has no schema work when it lands. Pinned by `test_load_pricing_cache_fields_default_to_zero` and `test_model_pricing_accepts_cache_rates_when_present`. |
| `load_tiers()` / `load_pricing()` accept a keyword-only `_tiers_dir` / `_pricing_dir` test hook | The Task 07 spec signature `load_tiers(profile=None)` is preserved for production callers. The underscore-prefixed kwarg is explicitly test-only (used by `test_tiers_loader.py` to point at `tmp_path` without `monkeypatch.chdir`). Cheaper than the alternative (global `_PROJECT_ROOT = Path.cwd()` monkey-patch) and more obvious in call sites. |
| `UnknownTierError` defined in `tiers.py`, not in `llm.model_factory` | The Task 07 AC owns this class; placing it beside `load_tiers()` keeps the error vocabulary co-located with the data it guards. Explicitly not a subclass of `ConfigurationError` — the two are orthogonal (typo-in-tier vs. bad config), pinned by `test_unknown_tier_error_is_not_a_configuration_error`. |
| `get_tier(tiers, name)` helper | Cheap wrapper that satisfies the AC ("unknown tier raises `UnknownTierError`") at the point of lookup. Existing callers that prefer `tiers[name]` can keep using the raw dict; new callers with structured error handling use the helper. |
| `compute_workflow_hash(workflow_dir)` widened to accept `str | Path` | Spec signature is `str`; widening is backwards compatible. Pinned by `test_compute_workflow_hash_accepts_str_and_path`. |
| `compute_workflow_hash` raises `FileNotFoundError` / `NotADirectoryError` on bad inputs | The spec's pseudocode falls through silently for non-existent dirs. Explicit errors fail loudly at the caller instead of producing the digest of an empty tree (which would match any empty dir). Pinned by two tests. |

No additions import from `components` or `workflows`. No adapter-specific
types leak into the new modules.

---

## Gate summary (2026-04-18)

| Gate | Result |
| --- | --- |
| `uv run pytest` | ✅ 225 passed, 0 skipped (61 relevant to Task 07: 19 tiers-loader, 18 workflow-hash, 24 model-factory confirming the unknown-tier rename) |
| `uv run lint-imports` | ✅ 2 kept / 0 broken |
| `uv run ruff check` | ✅ all checks passed |
| CI `secret-scan` (local dry run) | ✅ `grep -E 'sk-ant-[A-Za-z0-9_-]+' tiers.yaml pricing.yaml` returns no matches |

---

## Acceptance-criterion grading

| AC | Verdict | Evidence |
| --- | --- | --- |
| AC-1: `load_tiers()` expands `${OLLAMA_BASE_URL:-default}` from env | ✅ PASS | `test_load_tiers_expands_env_var_with_default` (env set → env value), `test_load_tiers_falls_back_to_default_when_env_unset` (env absent → default after `:-`), `test_load_tiers_expands_env_var_without_default` (bare `${VAR}` form). |
| AC-2: `--profile local` overlay overrides only declared keys | ✅ PASS | `test_profile_local_overlay_overrides_only_declared_keys` writes a base with `local_coder` + `haiku` tiers, overlays only `local_coder.base_url`, and asserts `base_url` changes while `model`, `max_tokens`, `temperature`, and the entire `haiku` tier stay from base. `test_profile_without_overlay_file_is_noop` confirms missing overlay files don't error. |
| AC-3: `compute_workflow_hash()` is deterministic | ✅ PASS | `test_compute_workflow_hash_is_deterministic` (two distinct directories with identical contents → identical digests), `test_compute_workflow_hash_is_repeatable_on_same_directory`, `test_hash_is_stable_across_creation_order` (creation order of files cannot affect the digest — guards the `sorted()` step). |
| AC-4: Hash changes when any content file changes | ✅ PASS | Five tests: touch a prompt, touch `workflow.yaml`, rename a file, add a new file, touch a `schemas/` file. All change the digest. |
| AC-5: `__pycache__` changes do NOT affect the hash | ✅ PASS | `test_pycache_changes_do_not_affect_hash` (root `__pycache__/`), `test_nested_pycache_is_ignored` (`schemas/__pycache__/`), `test_stray_pyc_outside_pycache_is_ignored`, `test_ds_store_is_ignored`, `test_log_files_are_ignored`. |
| AC-6: Unknown tier raises `UnknownTierError` | ✅ PASS | `test_get_tier_raises_unknown_tier_error_for_missing_name` (loader helper path), `test_unknown_tier_raises_unknown_tier_error` in `test_model_factory.py` (`build_model` path), `test_unknown_tier_error_is_not_a_configuration_error` (pins the class separation). |
| AC-7: `sonnet` tier has `temperature: 0.1` (P-22) | ✅ PASS | `test_committed_tiers_yaml_sonnet_has_temperature_0_1` loads the *committed* `tiers.yaml` via `load_tiers(_tiers_dir=REPO_ROOT)` and asserts `tiers["sonnet"].temperature == 0.1`, `.provider == "claude_code"`, `.model == "claude-sonnet-4-6"`. `test_committed_tiers_yaml_has_all_five_canonical_tiers` pins the tier-set envelope. |

---

## Carry-over grading

| Carry-over | Verdict | Evidence |
| --- | --- | --- |
| M1-T03-ISS-12 — `TierConfig.max_retries` field decision | ✅ RESOLVED | Decision: option (a), keep field + wire through `load_tiers()`. Pinned by `test_tier_config_max_retries_roundtrips_through_load_tiers` (YAML value flows through validation) and `test_tier_config_max_retries_default_is_three` (absent → 3). Rationale in the `TierConfig` docstring at `ai_workflows/primitives/tiers.py`. Issue flipped from ⏸️ DEFERRED to ✅ RESOLVED in `issues/task_03_issue.md`. |

---

## Additional coverage beyond ACs (not required, but present)

- `test_load_pricing_parses_committed_file` — end-to-end load of the
  committed `pricing.yaml`, asserting every Claude tier is $0, Gemini
  is `$0.10 / $0.40`, and Qwen is $0. Catches accidental drift in the
  committed file.
- `test_load_pricing_validates_unknown_keys` — typos like `inpput_per_mtok`
  surface as `pydantic.ValidationError` at load time (the typo drops,
  the required `input_per_mtok` is missing, validation fires).
- `test_load_tiers_missing_file_raises_file_not_found` /
  `test_load_pricing_missing_file_raises_file_not_found` — explicit
  error on missing config.
- `test_load_tiers_allows_empty_mapping` — the Task 01 stub shape
  (`tiers: {}`) still loads. Useful for tests that don't need real tiers.
- `test_compute_workflow_hash_returns_lowercase_hex_digest` — 64-char
  lowercase hex, parseable as int(16). Pins the return contract for
  Task 08's `runs.workflow_dir_hash TEXT` column.
- `test_empty_workflow_directory_has_stable_hash` — an empty dir is
  still a valid input and yields a stable digest.
- `test_missing_directory_raises_file_not_found` /
  `test_passing_a_file_path_raises_not_a_directory` — explicit
  validation of the input contract.

---

## Propagation status

- M1-T03-ISS-12 (DEFERRED → RESOLVED) does not require any carry-over
  entry on a future task's spec file — the resolution lands entirely
  within Task 07. `issues/task_03_issue.md` updated to reflect the
  closed state (issue body + issue-log footer).
- Task 07 surfaces no forward-deferred items; no carry-over sections
  needed on Task 08 (storage), Task 09 (cost tracker), or Task 10
  (retry). Task 10 inherits an **existing** contract (read
  `TierConfig.max_retries` per-tier at retry time) that is already in
  the Task 10 spec — no change needed there.

---

## Issue log — tracked for cross-task follow-up

- **M1-T07-ISS-NN** — _no issues opened; clean first-pass audit_.
