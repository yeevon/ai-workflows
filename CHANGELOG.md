# Changelog

All notable changes to ai-workflows are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

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
