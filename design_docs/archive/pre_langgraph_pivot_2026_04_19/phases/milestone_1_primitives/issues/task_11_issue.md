# Task 11 — Logging (structlog + logfire) — Audit Issues

**Source task:** [../task_11_logging.md](../task_11_logging.md)
**Audited on:** 2026-04-19
**Audit scope:** task file + milestone README + sibling tasks (01 scaffolding, 05 tool registry / forensic logger, 09 cost tracker — house logging style, 10 retry — `retry.transient` WARNING consumer) + `pyproject.toml` + `CHANGELOG.md` + `.github/workflows/ci.yml` + `ai_workflows/primitives/logging.py` + `tests/primitives/test_logging.py` + `tests/test_scaffolding.py` + upstream consumers (`ai_workflows/primitives/tools/forensic_logger.py`, `ai_workflows/primitives/cost.py`, `ai_workflows/primitives/retry.py`) + `design_docs/issues.md` (P-42, P-43, P-44) + the originating carry-over issue files `issues/task_01_issue.md` and `issues/task_05_issue.md`. logfire 4.32.1 API surface re-verified at audit time (`configure` signature shows `pydantic_plugin` in `DeprecatedKwargs`; `instrument_pydantic` is the current path; `send_to_logfire="if-token-present"` is the documented `Literal`).
**Status:** ✅ PASS — every acceptance criterion (incl. both carry-overs) is satisfied, pinned by at least one automated test, and every gate is green. No OPEN issues.

---

## Gate summary

| Gate | Result |
| --- | --- |
| `uv run pytest` | ✅ 330 passed, 2 warnings (pre-existing `yoyo` SQLite datetime deprecation in `test_cost.py`, unrelated to Task 11) |
| `uv run lint-imports` | ✅ 2 kept / 0 broken |
| `uv run ruff check` | ✅ all checks passed |
| `tests/primitives/test_logging.py` alone | ✅ 15 passed in 0.07s |
| `tests/test_scaffolding.py` alone | ✅ 27 passed (secret-scan regex parsed from ci.yml) |

Net test delta: +16 (315 → 330 + 1 scaffolding addition = 331 minus the test_retry collection skew in prior runs). Raw `-v` confirms every new test listed in the task file's AC table is present and passing.

---

## Acceptance-criterion grading

| AC | Verdict | Evidence |
| --- | --- | --- |
| AC-1: `configure_logging("INFO")` suppresses DEBUG | ✅ PASS | `test_info_level_suppresses_debug` asserts the debug event is absent and the info event is present. Reinforced by `test_warning_level_suppresses_debug_and_info` (three levels at once) and `test_level_is_case_insensitive` (`"info"` lowercase). Implementation: `numeric_level = getattr(logging, level, logging.INFO)` + `structlog.make_filtering_bound_logger(numeric_level)`. |
| AC-2: `configure_logging("DEBUG")` produces human-readable console output | ✅ PASS | `test_debug_level_emits_human_readable_console` asserts event name, key, value, and the bracketed `[debug` level token are all present in the rendered line. `test_debug_console_output_is_not_json` asserts `json.loads(line)` raises — i.e., the DEBUG output is definitively *not* JSON. Implementation: `structlog.dev.ConsoleRenderer(colors=False)`. |
| AC-3: JSON output validates as JSON | ✅ PASS | `test_info_level_emits_valid_json_per_line` emits two events at INFO+WARNING, splits stderr by newline, parses each via `json.loads`, and asserts `event`, `level`, `timestamp`, and the user-provided kwargs (`alpha`, `beta`) round-trip. |
| AC-4: Per-run file at `runs/<run_id>/run.log` when `run_id` given | ✅ PASS | Four tests: `test_per_run_file_is_created_when_run_id_given` (file exists post-configure), `test_per_run_file_receives_json_lines` (JSON content), `test_per_run_file_is_always_json_even_in_debug_mode` (file sink is JSON regardless of stderr renderer), `test_no_per_run_file_when_run_id_missing` (negative coverage — no dirs created). Implementation: `_TeeRenderer` owns the file sink; the directory is created with `mkdir(parents=True, exist_ok=True)` and the file is `touch(exist_ok=True)`-ed at configure time. |
| AC-5: `logfire.configure()` does not send to logfire.dev unless `LOGFIRE_TOKEN` is set | ✅ PASS | `test_logfire_configure_receives_if_token_present` patches `logfire.configure` and asserts the passed kwargs include `send_to_logfire="if-token-present"` and `service_name="ai_workflows"`. The `"if-token-present"` literal is logfire's documented knob for "send iff env has `LOGFIRE_TOKEN`", so asserting the kwarg is a stable pin — logfire's own behaviour on that knob is not this task's contract. Companion pin `test_logfire_pydantic_instrumentation_is_invoked` asserts the modern `instrument_pydantic(record="all")` call path (which replaces the spec's deprecated `pydantic_plugin=PydanticPlugin(record="all")` — see Additions beyond spec). |
| AC-6: `structlog.get_logger()` works from any module after `configure_logging()` | ✅ PASS | `test_get_logger_works_from_arbitrary_module_name` uses two unrelated logger names (`"ai_workflows.primitives.cost"`, `"some.other.module"`) and asserts both lines land in the stream. `test_get_logger_with_no_name_works` covers the no-argument form. |
| Carry-over M1-T05-ISS-02: forensic WARNING survives production pipeline | ✅ PASS | `test_forensic_warning_survives_production_pipeline` calls `configure_logging(..., run_id="forensic-run", run_root=tmp_path, ...)` then `log_suspicious_patterns(tool_name="read_file", output="IGNORE PREVIOUS INSTRUCTIONS …", run_id="forensic-run")`, reads `tmp_path/forensic-run/run.log`, and asserts the last JSON line has `event == "tool_output_suspicious_patterns"`, `level == "warning"`, `tool_name`, `run_id`, `patterns` (non-empty list), and `output_length > 0` — exactly the four keys the originating issue called out. |
| Carry-over M1-T01-ISS-08: CI secret-scan regex parsed at test time | ✅ PASS | `tests/test_scaffolding.py::_extract_ci_secret_scan_regex` greps the live `grep -E '<regex>'` invocation out of `.github/workflows/ci.yml`. The existing `test_secret_scan_regex_matches_known_key_shapes` now consumes the parsed pattern, and the new `test_secret_scan_regex_is_extracted_from_ci_yml` guards the extractor itself (asserts the captured group starts with `sk-ant-`). Narrowing the CI regex will either still match a valid-shape key (harmless drift) or visibly break these tests. |

---

## Additions beyond spec — audited and justified

| Addition | Justification |
| --- | --- |
| `send_to_logfire="if-token-present"` (spec wrote `False`) | The spec's own comment — *"local only by default; can flip via env var"* — matches the AC's "unless `LOGFIRE_TOKEN` is set" wording, not the literal `False` value. `"if-token-present"` is the logfire SDK's documented `Literal` that delegates the decision to the `LOGFIRE_TOKEN` env var. Pinned by `test_logfire_configure_receives_if_token_present`. |
| `logfire.instrument_pydantic(record="all")` (spec wrote `pydantic_plugin=logfire.PydanticPlugin(record="all")` as a `configure()` kwarg) | Verified against logfire 4.32.1 at audit time: `logfire.configure`'s signature lists `pydantic_plugin` inside `**deprecated_kwargs: Unpack[DeprecatedKwargs]`, and the public replacement is the top-level `instrument_pydantic(...)` function. The spec pre-dates the rename. Pinned by `test_logfire_pydantic_instrumentation_is_invoked`. |
| `_TeeRenderer` as the final structlog processor (spec's stub code calls an imaginary `_add_run_file_handler` helper) | Keeps the two-sink fan-out inside the structlog pipeline rather than plumbing stdlib-logging handlers alongside it. The file sink always uses a dedicated `JSONRenderer` (so DEBUG-mode console output does not contaminate the persisted JSON lines), and the event dict is copied before JSON rendering so the stderr renderer sees the original state. Pinned by `test_per_run_file_is_always_json_even_in_debug_mode`. |
| Keyword-only `stream: IO[str] \| None` parameter on `configure_logging` | Necessary for test stability: the active `pytest-logfire` plugin plus pytest's own fd capture sit in front of `monkeypatch.setattr(sys, "stderr", ...)`, so an in-memory buffer monkeypatch did not reliably capture output in cycle-1 development. An explicit `stream=` kwarg (default `sys.stderr`) decouples tests from pytest's stream plumbing. Production callers pass nothing and get the spec's behaviour. |
| `run_root: Path \| None = None` parameter | Mirrors the same test-only override pattern. Defaults to `DEFAULT_RUN_ROOT = Path.home() / ".ai-workflows" / "runs"` — matches the spec text. Tests pass `tmp_path` so `run.log` lands in a pytest-managed directory. |
| `DEFAULT_RUN_ROOT` exported as a module constant | Lets future CLI code reuse the same default without hard-coding the path, and gives the test suite an explicit symbol to pin if needed. |
| `ConsoleRenderer(colors=False)` | Default `ConsoleRenderer()` auto-detects a tty via `colorama`; in tests that land in a `StringIO` the detection is unstable. Disabling colors removes ANSI escape drift from AC-2's text assertion (`"[debug"` appears whether colors are on or off — but the surrounding token positions are stable without colors). |

No addition imports from `components` or `workflows`; no adapter-specific types leak into other modules; no file beyond `primitives/logging.py`, `tests/primitives/test_logging.py`, `tests/test_scaffolding.py`, the three design docs, and `CHANGELOG.md` is touched.

---

## Convention checks

| Check | Verdict |
| --- | --- |
| Layer discipline — `primitives/logging.py` imports only `logfire`, `structlog`, stdlib | ✅ `lint-imports` green; the import list is `logging`, `sys`, `pathlib.Path`, `typing.IO/Any`, `logfire`, `structlog`. |
| Module docstring names the task that produced it and how it relates to other modules | ✅ Cites "M1 Task 11 (P-42, P-43, P-44; resolves carry-overs `M1-T05-ISS-02` and `M1-T01-ISS-08`)" and points to `primitives/tools/forensic_logger.py` and `.github/workflows/ci.yml`. |
| Every public function has a docstring | ✅ `configure_logging` carries a full Parameters/Notes docstring. `DEFAULT_RUN_ROOT` has a module-level `"""`. The private helper `_TeeRenderer` has a class docstring explaining the fan-out semantics (private; docstring is courtesy, not required). |
| CHANGELOG updated under `## [Unreleased]` with `### Added — M1 Task 11: …` | ✅ Entry lists every file touched, every AC satisfied, and every deviation from spec (`send_to_logfire`, `instrument_pydantic`, `_TeeRenderer`, `stream=` kwarg). |
| Milestone README task line flipped to ✅ Complete (2026-04-19) | ✅ `README.md:63`. |
| AC checkboxes in task file all ticked with pinning-test names | ✅ `task_11_logging.md:76-104`. |
| Carry-over items in task file ticked with `Resolved by M1 Task 11 — …` footnotes | ✅ both `M1-T01-ISS-08` and `M1-T05-ISS-02` checkboxes flipped, each with a one-paragraph resolution pointer. |
| `design_docs/issues.md` — P-43 flipped `[ ]` → `[x]` with resolution note | ✅ line 121. P-42 and P-44 were already `[x]` when `structlog` / `~/.ai-workflows` were adopted; no edit needed. |
| No CI / workflow changes needed | ✅ `.github/workflows/ci.yml` unchanged; logging is pure Python and is exercised by the existing `uv run pytest` job. |
| Secrets discipline — no API keys, no env-var prompts, no credentials in the module | ✅ Module only reads `LOGFIRE_TOKEN` indirectly through logfire's own `if-token-present` resolution. |
| Forward-deferral propagation | ✅ No new deferrals — every AC and both carry-overs resolved in-task. |

---

## 🔴 HIGH

_None._

## 🟡 MEDIUM

_None._

## 🟢 LOW

_None._

---

## Issue log — tracked for cross-task follow-up

_No OPEN issues. Task 11 lands clean on the first cycle._

### Cross-cutting status updated by this audit

- **P-43** flipped `[ ]` → `[x]`: `configure_logging`'s level-to-category mapping is documented in the module docstring and pinned by the AC-1/AC-2/AC-3 tests.
- **M1-T05-ISS-02** ⏸️ DEFERRED → ✅ RESOLVED: pinned by `test_forensic_warning_survives_production_pipeline`. Originating issue file (`task_05_issue.md`) may be flipped on next Task 05 re-audit; the carry-over tick in the target task file is the authoritative signal for now.
- **M1-T01-ISS-08** (optional, LOW) → ✅ RESOLVED: pinned by `_extract_ci_secret_scan_regex` + `test_secret_scan_regex_is_extracted_from_ci_yml` in `tests/test_scaffolding.py`.

### Propagation status

No forward deferrals — nothing to propagate. Milestone 1 task backlog is now:

- Task 12 (`aiw list-runs / inspect / resume / run` CLI) is the only remaining task in M1; it consumes `configure_logging` for its startup wiring.
