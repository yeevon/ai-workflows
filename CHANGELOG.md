# Changelog

All notable changes to ai-workflows are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added — M1 Task 07: Tiers Loader and Workflow Hash (2026-04-18)

Implements P-21 … P-25 and CRIT-02. Lands the tiers / pricing YAML loader
(with env var expansion and profile overlay) plus the deterministic
workflow-directory content hash utility that Task 08 will store in
`runs.workflow_dir_hash` for resume safety. Closes the M1-T03-ISS-12
carry-over on `TierConfig.max_retries` by keeping the field and wiring
it through `load_tiers()`.

**Files added or modified:**

- `ai_workflows/primitives/tiers.py` — expanded from the Task 03 stub.
  Adds `ModelPricing` (rows in `pricing.yaml`), `UnknownTierError` (raised
  on tier-name miss; distinct from `ConfigurationError`), `load_tiers()`
  (env-var expansion via `${VAR:-default}`, profile overlay via
  `tiers.<profile>.yaml`, deep-merge that only replaces declared keys),
  `load_pricing()`, and a `get_tier()` helper that raises `UnknownTierError`.
  Both loaders accept an internal `_tiers_dir` / `_pricing_dir` kwarg so
  tests can point at `tmp_path` without `chdir`. `TierConfig` docstring
  pins the ISS-12 decision: the field is kept and roundtripped; Task 10
  reads it per-tier at retry time; SDK clients remain `max_retries=0`
  per CRIT-06.
- `ai_workflows/primitives/workflow_hash.py` — new module.
  `compute_workflow_hash(workflow_dir)` returns a SHA-256 hex digest over
  sorted `(relative-path, NUL, contents, NUL-NUL)` tuples. Ignored
  patterns: `__pycache__/` (any depth), `*.pyc`, `*.log`, `.DS_Store`.
  Raises `FileNotFoundError` / `NotADirectoryError` on malformed inputs.
- `ai_workflows/primitives/llm/model_factory.py` — unknown-tier branch
  now raises `UnknownTierError` (imported from `primitives.tiers`) so the
  Task 07 AC is satisfied without changing the message format.
- `tiers.yaml` — replaces the Task 01 stub with the canonical 5-tier
  config: `opus` / `sonnet` / `haiku` (provider: `claude_code`),
  `local_coder` (provider: `ollama`, `${OLLAMA_BASE_URL:-…}` base URL),
  `gemini_flash` (provider: `openai_compat`, Gemini API). `sonnet` has
  `temperature: 0.1` (P-22 regression guard).
- `pricing.yaml` — replaces the Task 01 stub. Top-level key is now
  `pricing:` (was `models:`) to match the spec; Claude CLI tiers record
  $0 (subscription-billed); Gemini overflow `$0.10 / $0.40` per MTok;
  local Qwen $0.
- `tests/primitives/test_tiers_loader.py` — 19 tests covering every
  loader AC: env expansion with and without default, profile overlay
  deep-merge, unknown-tier error, P-22 `sonnet.temperature == 0.1`
  regression guard against the committed file, carry-over
  `max_retries` roundtrip + default, `load_pricing()` against the
  committed file + unknown-field ValidationError + cache-rate defaults,
  missing-file handling, and empty-mapping handling.
- `tests/primitives/test_workflow_hash.py` — 18 tests covering
  determinism, content-change detection across root + subdirectory
  files, rename / add detection, ignored-pattern guards for
  `__pycache__` (root and nested), stray `*.pyc`, `.DS_Store`, `*.log`,
  and error handling for missing dirs / file inputs / empty dirs. Plus
  a creation-order invariance guard that catches any regression in the
  sort step of the hash.
- `tests/primitives/test_model_factory.py` — `test_unknown_tier_raises_configuration_error`
  renamed `test_unknown_tier_raises_unknown_tier_error` and now asserts
  the new `UnknownTierError` class.
- `design_docs/phases/milestone_1_primitives/task_07_tiers_loader.md` —
  Status line added, every acceptance-criterion checkbox ticked, carry-over
  M1-T03-ISS-12 ticked with the resolution pinned in the `TierConfig`
  docstring.
- `design_docs/phases/milestone_1_primitives/README.md` — Task 07 entry
  flipped to `✅ Complete (2026-04-18)`.
- `design_docs/phases/milestone_1_primitives/issues/task_03_issue.md` —
  M1-T03-ISS-12 flipped from ⏸️ DEFERRED to ✅ RESOLVED with a pointer
  to `primitives/tiers.py` and `test_tiers_loader.py`.

**Acceptance criteria satisfied:**

- AC-1: `load_tiers()` expands `${OLLAMA_BASE_URL:-default}` —
  `test_load_tiers_expands_env_var_with_default` +
  `test_load_tiers_falls_back_to_default_when_env_unset` +
  `test_load_tiers_expands_env_var_without_default`.
- AC-2: `--profile local` overlay overrides only declared keys —
  `test_profile_local_overlay_overrides_only_declared_keys`
  (asserts `base_url` changes, other fields stay) plus
  `test_profile_without_overlay_file_is_noop`.
- AC-3: `compute_workflow_hash()` is deterministic —
  `test_compute_workflow_hash_is_deterministic` +
  `test_compute_workflow_hash_is_repeatable_on_same_directory` +
  `test_hash_is_stable_across_creation_order`.
- AC-4: Hash changes when any content file changes —
  `test_touching_a_prompt_changes_the_hash`,
  `test_touching_workflow_yaml_changes_the_hash`,
  `test_renaming_a_file_changes_the_hash`,
  `test_adding_a_new_file_changes_the_hash`,
  `test_schemas_subdir_contributes_to_hash`.
- AC-5: `__pycache__` changes do NOT affect the hash —
  `test_pycache_changes_do_not_affect_hash` +
  `test_nested_pycache_is_ignored` +
  `test_stray_pyc_outside_pycache_is_ignored` +
  `test_ds_store_is_ignored` + `test_log_files_are_ignored`.
- AC-6: Unknown tier raises `UnknownTierError` —
  `test_get_tier_raises_unknown_tier_error_for_missing_name`
  (loader helper) + `test_unknown_tier_raises_unknown_tier_error`
  (`build_model` path) + `test_unknown_tier_error_is_not_a_configuration_error`
  (pins the class separation).
- AC-7: `sonnet` tier has `temperature: 0.1` (P-22) —
  `test_committed_tiers_yaml_sonnet_has_temperature_0_1` loads the
  committed `tiers.yaml` and pins the value.

**Carry-over from M1 Task 03 audit:**

- M1-T03-ISS-12 — `TierConfig.max_retries` decision: **keep the field
  and wire it through `load_tiers()`**. The field now roundtrips from
  YAML to `TierConfig` (`test_tier_config_max_retries_roundtrips_through_load_tiers`);
  when absent it defaults to 3 (`test_tier_config_max_retries_default_is_three`).
  Task 10 will read the value per-tier at retry time; SDK clients remain
  `max_retries=0` per CRIT-06. Decision pinned in the `TierConfig`
  docstring so future readers see the rationale.

**Deviations from spec:**

- `TierConfig.provider` literal keeps `"anthropic"` alongside
  `"claude_code" / "ollama" / "openai_compat" / "google"`; the Task 07
  spec dropped `"anthropic"`, but M1-T03-ISS-13 retained it for
  third-party deployments per the `project_provider_strategy` memory.
  Unchanged from the existing Task 03 resolution; called out here so the
  gap between Task 07's inline YAML spec and the actual `TierConfig` is
  not invisible.
- `ModelPricing` ships with `cache_read_per_mtok` / `cache_write_per_mtok`
  fields (defaulted to `0.0`) in addition to `input_per_mtok` /
  `output_per_mtok`. The Task 07 spec shows only the two `input` /
  `output` fields, but Task 09's `calculate_cost()` sums four rates;
  including the cache rates now means Task 09 has no schema change.
  Canonical `pricing.yaml` rows omit the cache fields — they default.
- `load_tiers()` / `load_pricing()` accept an internal `_tiers_dir` /
  `_pricing_dir` keyword-only argument used by tests to point at
  `tmp_path`. Not part of the public contract; the spec signature
  `load_tiers(profile: str | None = None)` is preserved for callers.

### Added — M1 Task 06: Stdlib Tools — fs + shell + http + git (2026-04-18)

Implements P-13 … P-19 (the language-agnostic standard-library tools
registered into every workflow's `ToolRegistry`). Lands the carry-over
items M1-T05-ISS-01 (end-to-end forensic-wrapper test through a real
`pydantic_ai.Agent.run()` call) and M1-T05-ISS-03 (string-return
convention for all stdlib tools, pinned by an annotation test).

**Files added or modified:**

- `ai_workflows/primitives/tools/fs.py` — new module. `read_file`,
  `write_file`, `list_dir`, `grep`. UTF-8 → latin-1 fallback on
  `read_file`; optional `max_chars` truncation marker; parent-dir
  creation on `write_file`; 500-entry cap on `list_dir`; 100-match cap
  on `grep` with regex validation. Every failure path returns a
  structured `"Error: …"` string, never raises.
- `ai_workflows/primitives/tools/shell.py` — new module. `run_command`
  gated by CWD containment, executable allowlist, dry-run short-circuit,
  and timeout — in that order. Exports `SecurityError`,
  `ExecutableNotAllowedError`, `CommandTimeoutError`. Internal guard
  helpers (`_check_cwd_containment`, `_check_executable`) raise; the
  public `run_command` catches and returns strings so the LLM never
  sees a traceback.
- `ai_workflows/primitives/tools/http.py` — new module. Single
  `http_fetch(ctx, url, method, max_chars, timeout)` tool; 50K-char body
  truncation; httpx timeout / network errors returned as strings.
- `ai_workflows/primitives/tools/git.py` — new module. `git_diff`
  (100K-char cap), `git_log` (oneline format), `git_apply`. Exports
  `DirtyWorkingTreeError`. `git_apply` runs `git status --porcelain`
  first and refuses on a dirty tree; `dry_run=True` uses
  `git apply --check`.
- `ai_workflows/primitives/tools/stdlib.py` — new module.
  `register_stdlib_tools(registry)` binds every canonical stdlib tool
  name onto a `ToolRegistry` at workflow-run start, with non-empty
  descriptions forwarded to the `pydantic_ai.Tool` schema.
- `ai_workflows/primitives/tools/__init__.py` — docstring updated to
  enumerate every new submodule.
- `tests/primitives/tools/__init__.py`, `.../conftest.py` — new test
  package + shared `CtxShim` / `ctx_factory` fixture that carries only
  the `WorkflowDeps` bits the tools read (avoids constructing a real
  `RunContext` with a live Model and RunUsage).
- `tests/primitives/tools/test_fs.py` — 18 tests covering read_file
  UTF-8 + latin-1 fallback + missing-file string errors, write_file
  parent-dir creation + overwrite flag, list_dir sort + glob + 500-cap +
  string errors, grep file:line:text format + max_results cap + invalid
  regex string error + rglob recursion.
- `tests/primitives/tools/test_shell.py` — 17 tests. Guard helpers
  tested directly for the raises-on-failure contract; run_command
  tested for the string-return contract in every failure mode (security,
  allowlist, dry-run, timeout, missing exec, non-zero exit). Dry-run
  enforces guards before short-circuiting.
- `tests/primitives/tools/test_http.py` — 6 tests using
  `httpx.MockTransport` so no live network traffic is generated. Covers
  HTTP 200 success, method override, body truncation, timeout +
  network-error string returns, invalid-URL string return.
- `tests/primitives/tools/test_git.py` — 12 tests on an isolated repo
  under `tmp_path`. Diff / log format + caps; git_apply refuses on
  dirty tree (key AC); dry-run uses `git apply --check` without
  touching the tree.
- `tests/primitives/tools/test_stdlib.py` — 21 tests. Registration
  binds every canonical name; double registration fails; every stdlib
  tool's first parameter is `ctx` and the return annotation is `str`
  (pins the M1-T05-ISS-03 decision). The carry-over live Agent.run()
  test uses `pydantic_ai.models.test.TestModel` to invoke a canary tool
  whose output trips an `INJECTION_PATTERNS` marker and asserts the
  `tool_output_suspicious_patterns` WARNING fires.
- `design_docs/phases/milestone_1_primitives/task_06_stdlib_tools.md` —
  Status line added, every acceptance-criterion checkbox ticked, both
  carry-over entries ticked with a resolution pointer to the pinning
  test.
- `design_docs/phases/milestone_1_primitives/README.md` — Task 06
  entry flipped to `✅ Complete (2026-04-18)`.

**Acceptance criteria satisfied:**

- AC-1: `read_file` UTF-8 + latin-1 fallback —
  `test_read_file_returns_utf8_content` + `test_read_file_falls_back_to_latin1_on_invalid_utf8`.
- AC-2: `..` in `working_dir` raises `SecurityError` naming the
  attempted path — `test_check_cwd_containment_rejects_parent_traversal`
  (guard) + `test_run_command_security_error_returns_string` (end-to-end
  via the string-return contract).
- AC-3: Executable not in allowlist raises
  `ExecutableNotAllowedError` — `test_check_executable_rejects_when_not_in_allowlist`
  plus `test_run_command_executable_not_allowed_returns_string`.
- AC-4: `dry_run=True` never invokes subprocess —
  `test_run_command_dry_run_does_not_invoke_subprocess` uses
  `unittest.mock.patch` to pin `subprocess.run` was not called.
- AC-5: `git_apply` refuses on dirty working tree —
  `test_git_apply_refuses_dirty_tree`.
- AC-6: All tools return strings on error paths — pinned by a matching
  `_returns_string_error` test for every public tool (read_file missing,
  read_file on directory, write_file permission branch via the generic
  OSError catch, list_dir missing + on-file, grep missing path + invalid
  regex, run_command × all guards + timeout + missing-exec, http_fetch
  timeout + network + bad URL, git_diff bad ref, git_log non-repo,
  git_apply bad diff + non-repo).
- AC-7: Tools pull `allowed_executables` and `project_root` from
  `RunContext[WorkflowDeps]` — verified by `test_run_command_success_returns_exit_code_and_output`
  (reads `project_root` from `ctx.deps`), the allowlist tests (reads
  `allowed_executables`), and `test_stdlib_tool_first_parameter_is_ctx`
  (pins the signature convention for all 9 tools).

**Carry-over from M1 Task 05 audit:**

- M1-T05-ISS-01 — end-to-end pydantic-ai `Agent.run()` test now lives at
  `tests/primitives/tools/test_stdlib.py::test_forensic_wrapper_survives_real_agent_run`.
  Uses `TestModel(call_tools=["injected_tool"])` so no API key is
  required; asserts the `tool_output_suspicious_patterns` WARNING
  fires when the tool's output contains an `INJECTION_PATTERNS`
  marker.
- M1-T05-ISS-03 — standardised on Option 2 ("all stdlib tools return
  `str`"). Every public stdlib tool is annotated `-> str`, pinned by
  `test_stdlib_tool_is_annotated_to_return_str` (9 parametrised cases).
  The convention is called out in `fs.py` and `shell.py` module
  docstrings so future tool authors see the rule before writing a
  structured-output tool.

**Deviations from spec:**

- `run_command` catches `SecurityError` / `ExecutableNotAllowedError` /
  `CommandTimeoutError` at the outer frame and returns a structured
  error string; the guard helpers still raise. Both ACs ("raises X"
  and "returns strings on error paths") are satisfied — the raises-on-
  failure contract is pinned at the guard level, the string-return
  contract at the tool level. This reading is consistent with the
  spec's "Never raises to the LLM" rider.
- `_check_cwd_containment` and `_check_executable` are module-level
  helpers with leading underscores — they are part of the internal
  contract (tested directly) but not re-exported through
  `shell.__all__`. Callers always go through `run_command`.

### Added — M1 Task 05: Tool Registry and Forensic Logger (2026-04-18)

Implements P-11 / P-20 (injected tool registry) and CRIT-04 (rename the
regex sanitizer to a forensic logger that makes its non-defence status
unambiguous). Replaces the former ``sanitizer.py`` pattern with a
per-workflow registry that scopes tools per-component (Anthropic subagent
pattern) plus a logging-only marker scanner.

**Files added or modified:**

- `ai_workflows/primitives/tools/registry.py` — new module.
  `ToolRegistry` with `register()`, `get_tool_callable()`,
  `registered_names()`, and `build_pydantic_ai_tools(names)`. Every tool
  returned by `build_pydantic_ai_tools()` is wrapped so its output flows
  through `forensic_logger.log_suspicious_patterns()` before returning to
  pydantic-ai; the wrapper preserves the original callable's signature
  (sync or async) so pydantic-ai's JSON-schema generator stays happy.
  Exports `ToolAlreadyRegisteredError` and `ToolNotRegisteredError`.
- `ai_workflows/primitives/tools/forensic_logger.py` — new module.
  `INJECTION_PATTERNS` plus `log_suspicious_patterns(*, tool_name, output,
  run_id)`. Emits a single structlog `WARNING` event named
  `tool_output_suspicious_patterns` when any pattern matches; never
  modifies the output. Docstring states **NOT a security control**
  (CRIT-04) and points at the real defences (ContentBlock tool_result
  wrapping, run_command allowlist, HumanGate, per-component allowlists).
- `ai_workflows/primitives/tools/__init__.py` — docstring updated to
  reflect that the two modules now exist and cross-link CRIT-04.
- `tests/primitives/test_tool_registry.py` — 29 tests covering every
  acceptance criterion and the integration surface: zero shared state
  between instances, per-component scoping via `build_pydantic_ai_tools`,
  order preservation, empty list, unknown-name error, duplicate
  rejection, `register()` validation, raw-callable retrieval, every
  injection pattern matching, silence on benign output, no output
  mutation, output_length recorded, docstring disclaimers for both the
  module and the public function, sync + async tool flow-through,
  run_id extraction from `RunContext[WorkflowDeps]`, and signature
  preservation through the forensic wrapper.

**Acceptance criteria satisfied:**

- AC-1: Two `ToolRegistry()` instances in the same process have zero
  shared state — `test_two_registries_have_zero_shared_state` +
  `test_registry_is_not_a_singleton_via_class_attribute`.
- AC-2: `build_pydantic_ai_tools(["read_file"])` returns only one
  scoped tool — `test_build_pydantic_ai_tools_returns_only_the_named`.
- AC-3: `forensic_logger` matches injection patterns without modifying
  output — `test_forensic_logger_matches_known_patterns` +
  `test_forensic_logger_does_not_modify_output`.
- AC-4: A `WARNING` structlog event appears when output contains a known
  pattern — `test_forensic_logger_matches_known_patterns` asserts the
  WARNING record and the event name, run_id, and tool_name fields.
- AC-5: Module + function docstrings explicitly state the forensic logger
  is NOT a security control — `test_forensic_logger_module_docstring_disclaims_security_control`
  and `test_log_suspicious_patterns_docstring_disclaims_security_control`.

**Deviations from spec:**

- The spec's `register()` signature is `(name, fn, description)`; the
  implementation also raises `ToolAlreadyRegisteredError` on duplicate
  registration and rejects empty name/description. Neither is called out
  in the spec, but silently shadowing an existing registration is an
  unambiguous programmer error — failing loudly is the conservative
  default.
- `build_pydantic_ai_tools()` rejects duplicate names (`ValueError`) and
  unknown names (`ToolNotRegisteredError`). The spec does not mandate
  either, but both conditions point at a miswired Worker config and
  should not silently degrade to the registry's natural behaviour
  (double-wrap; `KeyError` from dict lookup).
- `ai_workflows/primitives/tools/__init__.py` docstring — updated only.
  No new submodule files were added beyond the two named in the spec.

### Fixed — M1 Task 03: Model Factory — SD-03 (Claude Code CLI) Alignment (2026-04-18)

Resolves ISS-13, ISS-14, ISS-15 opened after the SD-03 spec amendment
adopted the Claude Code CLI design. Closes AC-6 (`claude_code` provider
raises `NotImplementedError`).

**Files modified:**

- `ai_workflows/primitives/tiers.py` — ISS-13: extended `TierConfig.provider`
  literal to `Literal["claude_code", "anthropic", "ollama", "openai_compat", "google"]`
  so the canonical `tiers.yaml` (which declares `provider: claude_code` for
  opus/sonnet/haiku) loads. `anthropic` retained for third-party deployments
  per project memory. Per-provider inline comments added.
- `ai_workflows/primitives/llm/model_factory.py` — ISS-14: added the
  `claude_code` branch at the top of `build_model()`, raising
  `NotImplementedError` with a message naming the tier and model and
  pointing at the M4 Orchestrator subprocess launcher. ISS-15: module
  docstring expanded to list the `claude_code` provider first with the M4
  deferral called out.
- `tests/primitives/test_model_factory.py` — ISS-15: file docstring
  rewritten against the SD-03 design (AC-6 added, AC-1 reframed as a
  third-party Anthropic regression path). `SONNET_TIER` renamed
  `ANTHROPIC_THIRD_PARTY_TIER` with a docstring citing
  `project_provider_strategy`. New `CLAUDE_CODE_SONNET_TIER` fixture paired
  with `test_build_model_claude_code_raises_not_implemented` (AC-6).
  `test_tier_config_accepts_claude_code_provider` pins the ISS-13 literal.
  `_tiers()` and `test_unsupported_provider_raises_configuration_error`
  updated to the renamed fixture.

**Acceptance criteria re-graded:**

- AC-6: was 🔴 UNMET (no `claude_code` branch); now ✅ PASS via
  `test_build_model_claude_code_raises_not_implemented` which asserts the
  exception type and that the message names `claude_code`, the tier name,
  the model name, and `M4`.
- AC-1: wording now matches the SD-03 design (third-party `AnthropicModel`
  code path); existing tests remain green on the renamed fixture.

**Gate result:** 84 passed, 0 skipped, 2 contracts kept, ruff clean.

### Added — M1 Task 04: Multi-Breakpoint Prompt Caching (2026-04-18)

Implements CRIT-07: Anthropic multi-breakpoint prompt caching replaces the
naive "cache last system block" pattern. Cache the two stable prefixes
(tool definitions, static system prompt) with a 1-hour TTL; per-call
variables are pushed into the last user message, enforced by a load-time
lint.

**Files added or modified:**

- `ai_workflows/primitives/llm/caching.py` — new module. Exposes
  `apply_cache_control()` (pure helper that injects `cache_control` into the
  last tool definition and last system block of a raw Anthropic request),
  `build_cache_settings()` (returns a pydantic-ai `AnthropicModelSettings`
  with `anthropic_cache_tool_definitions` + `anthropic_cache_instructions`
  set to TTL="1h" when `caps.supports_prompt_caching` is True, else `None`),
  `validate_prompt_template()` (raises `PromptTemplateError` when a prompt
  file contains `{{var}}` substitutions — run at workflow-load time in M3),
  and the `PromptTemplateError` exception class.
- `ai_workflows/primitives/llm/__init__.py` — docstring updated to reflect
  the three new `caching` exports now that the module exists.
- `tests/primitives/test_caching.py` — 19 tests covering every acceptance
  criterion: last-tool-def / last-system-block breakpoints, input
  non-mutation, empty-input handling, 5m/1h TTL override, `AnthropicModelSettings`
  wiring for Anthropic tiers, `None` for non-caching providers, factory
  integration, `{{var}}` / dotted-var / multi-var rejection, static prompt
  acceptance, single-brace not confused with template, missing-file error,
  `str`/`Path` acceptance, and `cache_read_tokens` forwarding through
  `run_with_cost()` → `TokenUsage`. A final live integration test
  (`test_integration_prompt_caching_works`) runs two back-to-back
  `agent.run()` calls against a real Anthropic endpoint and asserts
  `cache_read_tokens > 0` on turn 2; skipped when `ANTHROPIC_API_KEY` is
  absent.

**Acceptance criteria satisfied:**

- AC-1: Tool definitions carry `cache_control` on the last entry
  (`test_apply_cache_control_marks_last_tool_definition` + pydantic-ai's
  `anthropic_cache_tool_definitions` setting wired via
  `build_cache_settings()`).
- AC-2: System prompt last block carries `cache_control`
  (`test_apply_cache_control_marks_last_system_block` + pydantic-ai's
  `anthropic_cache_instructions` setting wired via `build_cache_settings()`).
- AC-3: `validate_prompt_template()` flags `{{var}}` in system prompts
  (`test_validate_prompt_template_rejects_template_variable` +
  `test_validate_prompt_template_rejects_dotted_variable` +
  `test_validate_prompt_template_lists_all_offending_variables`).
- AC-4: Integration test confirms `cache_read_tokens > 0` on turn 2 of a
  repeated agent call — `test_integration_prompt_caching_works`. Skipped
  locally because no `ANTHROPIC_API_KEY` is available (user runs Claude Max,
  no pay-as-you-go API account); the test remains in the suite so a future
  key flip or CI run exercises it.
- AC-5: Cache read tokens recorded in `TokenUsage` — `_convert_usage()`
  already populates `cache_read_tokens` / `cache_write_tokens` from
  pydantic-ai's `RunUsage` (M1 Task 03); `test_run_with_cost_forwards_cache_tokens_to_tracker`
  pins that wiring. Surfacing the field in `aiw inspect` is owned by M1
  Task 12.

**Deviations from spec:**

- The spec sketches a handwritten caching wrapper that injects `cache_control`
  into outgoing Anthropic requests. pydantic-ai 1.x already exposes this
  as typed settings (`AnthropicModelSettings.anthropic_cache_tool_definitions`
  and `anthropic_cache_instructions`), so the Task 04 wiring is a thin
  adapter — `build_cache_settings()` — rather than a bespoke request-mutating
  wrapper. `apply_cache_control()` remains as a pure helper for direct-SDK
  / forensic-replay callers that build Anthropic request payloads outside
  pydantic-ai. Behaviour matches the spec: last tool def and last system
  block carry `cache_control` with TTL="1h"; messages are left for
  Anthropic's automatic 5-minute breakpoint.
- `validate_prompt_template()` operates on a single prompt file path; the
  workflow/prompt schema that distinguishes "system" vs. "user" sections
  lands in M2/M3. Until then, callers invoke this on any file intended for
  use as a system-prompt block.

### Fixed — M1 Task 03: Model Factory — Audit Follow-up (2026-04-18)

Resolves ISS-09, ISS-10, ISS-11 surfaced in the post-resolution confirmation audit.
ISS-12 (`TierConfig.max_retries`) deferred to Task 07 by user decision.

**Files modified:**

- `ai_workflows/primitives/llm/model_factory.py` — ISS-10: added `-> "AgentRunResult[Any]"` return annotation to `run_with_cost()`; `Any` added to `typing` imports; `AgentRunResult` added under `TYPE_CHECKING`.
- `tests/primitives/test_model_factory.py` — ISS-09: added `test_build_openai_compat_returns_correct_type` + `test_openai_compat_capabilities_flags` (all four provider branches now have full model-type + caps-flags coverage). ISS-11: added `test_unsupported_provider_raises_configuration_error` (uses `model_construct` to bypass Literal, exercises the fallthrough `raise`).
- `design_docs/phases/milestone_1_primitives/issues/task_03_issue.md` — ISS-09…ISS-12 marked RESOLVED / DEFERRED; status updated to ✅ PASS.

**Gate result:** 63 passed (22 model-factory, 15 types, 26 scaffolding), 1 skipped, 0 broken contracts, ruff clean.

### Fixed — M1 Task 03: Model Factory — Issue Resolution (2026-04-18)

Resolves all eight issues filed by the Task 03 audit (ISS-01 through ISS-08).

**Files added or modified:**

- `pyproject.toml` — added `python-dotenv>=1.0` to `[dependency-groups.dev]`.
- `tests/conftest.py` — new root conftest; auto-loads `.env` via `load_dotenv()` so integration tests read keys without manual `export`.
- `ai_workflows/primitives/llm/model_factory.py` — ISS-01: explicit comment in `_build_google()` documenting reliance on google-genai's `stop_after_attempt(1)` default (CRIT-06 compliant). ISS-03: in-body `_ = cost_tracker` comment replaces `# noqa` annotation. ISS-05: `_build_openai_compat()` now raises `ConfigurationError` when `base_url` is falsy.
- `tests/primitives/test_model_factory.py` — ISS-02: three new Google provider tests (`test_build_google_model_returns_correct_type`, `test_google_capabilities_flags`, `test_missing_google_key_raises_configuration_error`). ISS-01 test: `test_google_client_retry_is_disabled` asserts `stop.max_attempt_number == 1`. ISS-04: Ollama base-url assertion tightened to full prefix check. ISS-05 test: `test_openai_compat_requires_base_url`. ISS-08: two new live integration tests gated by `GEMINI_API_KEY` and `AIWORKFLOWS_OLLAMA_BASE_URL`.
- `design_docs/phases/milestone_1_primitives/task_03_model_factory.md` — AC-4 amended to accept Gemini or Anthropic key; AC checkboxes ticked; Status line added.
- `design_docs/phases/milestone_1_primitives/README.md` — Task 03 entry marked Complete.
- `design_docs/issues.md` — CRIT-05 flipped to `[x]`; CRIT-06 flipped to `[~]`.
- `design_docs/phases/milestone_1_primitives/issues/task_03_issue.md` — ISS-01 through ISS-07 marked RESOLVED; ISS-08 re-graded (Gemini + Ollama paths now have live tests).

**Acceptance criteria re-graded:**

- AC-1 through AC-3, AC-5: were ✅ PASS, remain so.
- AC-4: was ⏸️ BLOCKED (Anthropic key required); now ✅ PASS via Gemini `openai_compat` integration test (`test_integration_gemini_cost_recorded_after_real_agent_run`) + Ollama path (`test_integration_ollama_cost_recorded_after_real_agent_run`).

**Deviation noted:**

- AC-4 satisfied via Gemini (`openai_compat`) rather than Anthropic API — user runs Claude Max (subscription) and does not maintain a separate pay-as-you-go Anthropic API account. The amended AC-4 accepts any real provider key. Anthropic integration test remains in the suite but stays skipped until a key is provided.

### Added — M1 Task 03: Model Factory (2026-04-18)

Introduces the model factory that maps tier names to configured pydantic-ai
Model instances, enforcing `max_retries=0` on every underlying SDK client.

**Files added or modified:**

- `ai_workflows/primitives/tiers.py` — new module; `TierConfig` Pydantic model
  (stub for Task 07, which will add `load_tiers()` / `load_pricing()`).
- `ai_workflows/primitives/cost.py` — new module; `CostTracker` Protocol
  (stub for Task 09, which will provide the SQLite-backed implementation).
- `ai_workflows/primitives/llm/model_factory.py` — new module; `build_model()`,
  `run_with_cost()`, `ConfigurationError`, and internal `_build_*` helpers.
- `tests/primitives/test_model_factory.py` — 13 tests (12 unit + 1 live
  integration skipped when `ANTHROPIC_API_KEY` is absent).

**Acceptance criteria satisfied:**

- AC-1: `build_model("sonnet", tiers, cost_tracker)` returns
  `(AnthropicModel, ClientCapabilities)` with `supports_prompt_caching=True`.
- AC-2: `build_model("local_coder", tiers, cost_tracker)` returns
  `(OpenAIChatModel, ClientCapabilities)` with `base_url` from Ollama config.
- AC-3: Underlying SDK clients have `max_retries=0` — verified via
  `model.provider.client.max_retries` for all three provider branches.
- AC-4: Integration test wires a live `agent.run()` → `cost_tracker.record()`
  call; skipped in CI when `ANTHROPIC_API_KEY` is absent.
- AC-5: Missing env var raises `ConfigurationError` naming the variable.

**Deviations from spec:**

- `OpenAIModel` → `OpenAIChatModel`: pydantic-ai ≥ 1.0 renamed `OpenAIModel`
  to `OpenAIChatModel` (the old name is deprecated). All tests and code use
  the new name.
- `Usage` → `RunUsage`: pydantic-ai ≥ 1.0 renamed the usage dataclass.
  `_convert_usage()` uses `RunUsage` to avoid deprecation warnings.
- Provider construction uses `XxxProvider` wrappers (e.g. `AnthropicProvider`,
  `OpenAIProvider`) rather than passing `anthropic_client=` directly to the
  Model constructor — the direct-kwarg API was removed in pydantic-ai 1.0.
- `cost_tracker` parameter accepted by `build_model` but not yet actively wired
  (no pydantic-ai usage-callback hook exists); active cost recording is in
  `run_with_cost()` as described in the spec's cost-tracking section.

### Fixed — M1 Task 02: Shared Types — ISS-06 (2026-04-18)

Resolves M1-T02-ISS-06 — the SD-03 design change introduced the
`claude_code` provider (Claude Max CLI tiers) but `ClientCapabilities.provider`
still read the pre-CLI literal, blocking Task 03's `claude_code` branch and
Task 07's `tiers.yaml` load.

**Files modified:**

- `ai_workflows/primitives/llm/types.py` — extended the `provider` literal
  to `Literal["claude_code", "anthropic", "openai_compat", "ollama", "google"]`
  (keeping `anthropic` for third-party callers per
  `project_provider_strategy`); added an inline comment enumerating each
  provider's role.
- `tests/primitives/test_types.py` — added
  `test_client_capabilities_claude_code_provider_roundtrips` mirroring the
  existing `_google_provider` test. Asserts `supports_prompt_caching=False`
  on the CLI path (prompt caching is an API-only feature).

**Verdict:** all four acceptance criteria remain ✅ PASS. Task 02 flips
back from 🔴 Reopened to ✅ Complete once the audit re-runs.

### Added — M1 Task 02: Shared Types (2026-04-18)

Introduces all canonical shared types consumed by every higher layer.

**Files added or modified:**

- `ai_workflows/primitives/llm/types.py` — new module containing
  `TextBlock`, `ToolUseBlock`, `ToolResultBlock`, `ContentBlock`
  (discriminated union), `Message`, `TokenUsage`, `Response`,
  `ClientCapabilities`, and `WorkflowDeps`.
- `tests/primitives/test_types.py` — 15 tests covering all four
  acceptance criteria (14 original + 1 added in audit follow-up).

**Acceptance criteria satisfied:**

- AC-1: `Message(content=[{"type":"text","text":"hi"}])` parses via
  discriminated-union dispatch — confirmed by `test_message_parses_text_block_from_dict`.
- AC-2: 50 `tool_use` blocks parse in < 5 ms — confirmed by
  `test_fifty_tool_use_blocks_parse_quickly`.
- AC-3: Invalid `type` value raises a clear `ValidationError` naming
  the allowed literals — confirmed by two validation-error tests.
- AC-4: `ClientCapabilities` serialises to/from JSON without loss —
  confirmed by JSON and dict round-trip tests.

**Audit follow-up (M1-T02-ISS-01, ISS-03, ISS-04):**

- ISS-01: Tightened AC-3 test assertion from `or` to `and` — all three
  discriminator tag names must appear in the error string; previously
  a single name was sufficient, defeating the discriminator-regression guard.
- ISS-03: Extended `ClientCapabilities.provider` literal to include
  `"google"` (1M-context Gemini differentiator); updated task spec and
  added `test_client_capabilities_google_provider_roundtrips`.
- ISS-04: Marked `CRIT-09` `[x]` resolved and `CRIT-05` `[~]` in-progress
  in `design_docs/issues.md`.

#### Completion marking (2026-04-18)

Closes the last open Task 02 issue (M1-T02-ISS-05, surfaced in the
re-audit) — design-doc bookkeeping only, no code or test changes.

- **`design_docs/phases/milestone_1_primitives/task_02_shared_types.md`** —
  added top-of-file `Status: ✅ Complete (2026-04-18)` line linking to the
  audit log; ticked all four acceptance-criterion checkboxes.
- **`design_docs/phases/milestone_1_primitives/README.md`** — appended
  `— ✅ **Complete** (2026-04-18)` to the Task 02 entry in the task-order
  list, matching the Task 01 convention.
- **`design_docs/phases/milestone_1_primitives/issues/task_02_issue.md`** —
  flipped ISS-05 from OPEN to ✅ RESOLVED; updated the audit Status line to
  note every LOW (ISS-01 … ISS-05) is now closed.

**Deviations:** none.

### Added — M1 Task 01: Project Scaffolding (2026-04-18)

Initial project skeleton built on the `pydantic-ai` ecosystem. Establishes
the three-layer architecture (primitives → components → workflows) and the
tooling that enforces it. No runtime behaviour yet — that lands in M1
Tasks 02–12.

#### Initial build

- **`pyproject.toml`**
  - Runtime deps: `pydantic-ai`, `pydantic-graph`, `pydantic-evals`,
    `logfire`, `anthropic`, `httpx`, `pydantic`, `pyyaml`, `structlog`,
    `typer`, `yoyo-migrations`.
  - Optional `dag` extra for `networkx` (installed in M4).
  - Dev group: `import-linter`, `pytest`, `pytest-asyncio`, `ruff`.
  - Console script: `aiw = ai_workflows.cli:app`.
  - Two `import-linter` contracts encoding the layer rules:
    1. primitives cannot import components or workflows
    2. components cannot import workflows

    A third contract ("components cannot peek at each other's private
    state") is documented in the Task 01 spec but is **deferred**:
    `import-linter`'s wildcard syntax only allows `*` to replace a whole
    module segment, so `components.*._*` is rejected at load time.
    The rule comes back in M2 Task 01 when components exist and their
    private modules can be enumerated.
  - `ruff` defaults: line length 100, py312 target, rule set
    `E,F,I,UP,B,SIM`.
  - `pytest-asyncio` set to `auto` mode.
- **Package layout** (`ai_workflows/`)
  - `ai_workflows/__init__.py` — exposes `__version__` and documents the
    layering rule.
  - `ai_workflows/cli.py` — minimal Typer app with `--help` and a
    `version` subcommand. Subcommand groups land in M1 Task 12.
  - `ai_workflows/primitives/__init__.py` plus `llm/` and `tools/`
    subpackages (empty modules, filled in by Tasks 02–11).
  - `ai_workflows/components/__init__.py` (filled by M2 + M4).
  - `ai_workflows/workflows/__init__.py` (filled by M3, M5, M6).
- **Configuration stubs**
  - `tiers.yaml` — empty `tiers: {}` map; real schema lands in Task 07.
  - `pricing.yaml` — empty `models: {}` map; populated by Task 09.
- **Migrations**
  - `migrations/001_initial.sql` — bootstrap migration so `yoyo apply` has
    a tracked history on day one. Task 08 lands the real schema as 002+.
- **CI** (`.github/workflows/ci.yml`)
  - `test` job: `uv sync`, `uv run pytest`, `uv run lint-imports`,
    `uv run ruff check`.
  - `secret-scan` job: greps committed config for `sk-ant-…` patterns and
    fails the build if any are found.
- **Tests** (`tests/test_scaffolding.py`) — acceptance tests for Task 01:
  - All three layers + the CLI module import cleanly.
  - `aiw --help` and `aiw version` succeed via `typer.testing.CliRunner`.
  - Required scaffolding files exist on disk.
  - `pyproject.toml` declares every dependency from the Task 01 spec, the
    `aiw` console script, and the three `import-linter` contracts.
  - `lint-imports` exits 0 (skipped when `import-linter` is not
    installed).

#### Reimplementation

Addresses open issues from the Task 01 audit (M1-T01-ISS-01, M1-T01-ISS-02):

- **`docs/architecture.md`** — placeholder stub; to be authored by M1 Task 11.
- **`docs/writing-a-component.md`** — placeholder stub; to be authored by M2 Task 01.
- **`docs/writing-a-workflow.md`** — placeholder stub; to be authored by M3 Task 01.
- **`tests/test_scaffolding.py`** — extended parametrized file-existence test to cover
  the three new `docs/` placeholders. Test count: 21 → 24.
- **`design_docs/phases/milestone_1_primitives/task_01_project_scaffolding.md`** —
  acceptance criterion for `lint-imports` updated to say "contracts 1 and 2" (not
  "all three"), with a note documenting the Contract 3 deferral to M2 Task 01
  (M1-T01-ISS-01).
- **`pyproject.toml`** — removed accidental duplicate `pytest` entry from
  `[project.dependencies]`; it belongs only in `[dependency-groups].dev`.

#### Cleanup

Addresses open issues from the Task 01 re-audit (ISS-04, ISS-05, ISS-06, ISS-07, ISS-09):

- **`.gitignore`** — drop `.python-version` entry; file is the canonical 3.13 pin (ISS-04).
- **`tests/test_scaffolding.py`** — add `test_secret_scan_regex_matches_known_key_shapes`
  (ISS-05): self-contained pattern test that will break if the CI grep is ever narrowed.
- **`tests/test_scaffolding.py`** — add `test_aiw_console_script_resolves` (ISS-06):
  subprocess-based `aiw --help` gated on `shutil.which("aiw")`; proves the
  `[project.scripts]` entry point resolves beyond what `CliRunner` can verify.
- **`CHANGELOG.md`** — collapsed three Task 01 sub-entries into one
  `### Added — M1 Task 01: Project Scaffolding (2026-04-18)` heading with subsections,
  matching the CLAUDE.md format prescription (ISS-09).

#### Completion marking & README (2026-04-18)

Marks Task 01 as complete in the design docs and replaces the placeholder
`README.md` (closes the last open issue, ISS-03).

- **`design_docs/phases/milestone_1_primitives/task_01_project_scaffolding.md`** — ticked all
  seven acceptance-criteria checkboxes and added a top-of-file `Status: ✅ Complete (2026-04-18)`
  line pointing to the audit log.
- **`design_docs/phases/milestone_1_primitives/README.md`** — appended
  `— ✅ **Complete** (2026-04-18)` to the Task 01 entry in the task order list.
- **`README.md`** — replaced 14-byte stub with a proper project README: description, current
  status (M1 Task 01 done, 02–12 pending), requirements, quickstart, three-layer architecture
  summary with contract rules, the three development gates, repo layout table, and further-reading
  links into `design_docs/` and `docs/`. Resolves ISS-03 (previously deferred to M3 Task 01).
- **`design_docs/phases/milestone_1_primitives/issues/task_01_issue.md`** — flipped ISS-03
  from LOW/open to ✅ RESOLVED and updated the issue-log footer to reflect that every
  Task 01 issue is now closed.

### Notes

- `.python-version` pins to 3.13 (target runtime); `pyproject.toml`
  declares `>=3.12` so the project still builds on the user's laptop where
  3.12 is installed.
- `.gitignore` already excludes `runs/`, `*.db*`, `tiers.local.yaml`, and
  `.env*` — left untouched by this task.
