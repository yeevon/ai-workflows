# Task 05 — Tool Registry and Forensic Logger — Audit Issues

**Source task:** [../task_05_tool_registry.md](../task_05_tool_registry.md)
**Audited on:** 2026-04-18
**Audit scope:** full Task 05 surface —
[ai_workflows/primitives/tools/registry.py](../../../../ai_workflows/primitives/tools/registry.py),
[ai_workflows/primitives/tools/forensic_logger.py](../../../../ai_workflows/primitives/tools/forensic_logger.py),
[ai_workflows/primitives/tools/__init__.py](../../../../ai_workflows/primitives/tools/__init__.py),
[tests/primitives/test_tool_registry.py](../../../../tests/primitives/test_tool_registry.py),
[CHANGELOG.md](../../../../CHANGELOG.md) (M1 Task 05 entry),
the milestone [README.md](../README.md), sibling task files (02, 03, 04, 06, 07),
[design_docs/issues.md](../../../issues.md) (CRIT-04, P-11, P-20, X-07),
[pyproject.toml](../../../../pyproject.toml),
[.github/workflows/ci.yml](../../../../.github/workflows/ci.yml).
pydantic-ai `Tool` surface verified on 1.x (`.function`, `.name`,
`.description`, `.takes_ctx` attributes present).
All three gates executed locally after the audit read.

**Status:** ✅ PASS — every acceptance criterion satisfied and pinned by an
automated test. Three forward-looking LOW items are ⏸️ DEFERRED to named
future owners (M1 Task 06 stdlib tools, M1 Task 11 logging config, M2 Worker
wiring). None are actionable inside Task 05 and none block Task 06.

---

## 🔴 HIGH

_No HIGH issues._

---

## 🟡 MEDIUM

_No MEDIUM issues._

---

## 🟢 LOW

### M1-T05-ISS-01 — Forensic wrapper is not yet exercised on a real pydantic-ai Agent call

**Severity:** LOW · **Status:** ✅ RESOLVED (2026-04-18) — pinned by
`tests/primitives/tools/test_stdlib.py::test_forensic_wrapper_survives_real_agent_run`.
Uses `pydantic_ai.models.test.TestModel(call_tools=["injected_tool"])` to
invoke a tool whose output trips an `INJECTION_PATTERNS` marker and
asserts the `tool_output_suspicious_patterns` WARNING fires through the
real pydantic-ai tool-call protocol.

**What's observed.** The forensic wrapper returned by
[`ToolRegistry.build_pydantic_ai_tools()`](../../../../ai_workflows/primitives/tools/registry.py)
is covered by direct-invocation tests
([test_sync_tool_output_passes_through_forensic_logger](../../../../tests/primitives/test_tool_registry.py),
[test_async_tool_output_passes_through_forensic_logger](../../../../tests/primitives/test_tool_registry.py))
that call `tools[0].function(...)` without going through a real
`pydantic_ai.Agent`. This proves the wrapper is correctly installed into
the `Tool` object, but it does not prove that a live pydantic-ai tool call
routes through the wrapper end-to-end (e.g. that pydantic-ai does not
`inspect.unwrap()` past `functools.wraps` and call the original function,
or that the wrapper's signature is accepted by pydantic-ai's JSON-schema
generator under the real call path).

**Why this matters.** Forward-looking. pydantic-ai's internal tool-call
mechanism is a private protocol that could, in principle, bypass the
wrapper if it grabbed the underlying callable via `__wrapped__`. The
signature-preservation test
([test_wrapper_preserves_original_function_signature](../../../../tests/primitives/test_tool_registry.py))
confirms `inspect.signature` behaves correctly, which is the API
pydantic-ai uses — so the risk is low — but a live test would be
conclusive.

**Recommendation.** When M1 Task 06 lands the stdlib tools (`read_file`,
`grep`, `run_command`), or when M2's Worker integration test runs a live
agent loop, add a test that:

1. Registers a tool whose output contains an `INJECTION_PATTERNS` marker.
2. Runs a real `Agent.run(..., deps=WorkflowDeps(...))` that invokes the
   tool (against `TestModel` from `pydantic_ai.models.test` so no API key
   is needed).
3. Asserts a `tool_output_suspicious_patterns` WARNING was emitted.

No code change in Task 05 is required. Record as `M1-T05-ISS-01` and close
it when the end-to-end hook exists.

### M1-T05-ISS-02 — `log_suspicious_patterns` does not route through a configured structlog pipeline

**Severity:** LOW · **Status:** ⏸️ DEFERRED — owner: M1 Task 11

**What's observed.** The module uses `structlog.get_logger(__name__)`
([forensic_logger.py:40](../../../../ai_workflows/primitives/tools/forensic_logger.py)),
which, absent a `structlog.configure()` call, falls back to structlog's
default wrapper. The unit tests explicitly reconfigure structlog (see the
`structlog_warnings` fixture in
[test_tool_registry.py](../../../../tests/primitives/test_tool_registry.py))
so the WARNING events can be captured via stdlib `caplog`. In production,
the global structlog configuration lands in M1 Task 11; until then,
forensic WARNINGs are emitted to structlog's default processors, which
may not match the eventual logfire / JSON-line format.

**Why this matters.** Forward-looking. Task 05's AC-4 says "a `WARNING`
structlog event appears" — it does, and the test pins that. But the
*shape* of that event (JSON keys, correlation IDs, logfire span linkage)
is owned by Task 11. If Task 11 picks a global processor chain that
swallows warnings below INFO, or renames structured fields, this module
may need a single-line adjustment to bind its logger correctly.

**Recommendation.** When Task 11 wires the canonical structlog
configuration, add a smoke test that calls
`log_suspicious_patterns(...)` through the production pipeline and
asserts the event lands in the expected sink with `level=warning` and the
four expected keys (`tool_name`, `run_id`, `patterns`, `output_length`).
No code change required in Task 05 today.

### M1-T05-ISS-03 — Non-string tool outputs are forensic-scanned via `str(result)` — lossy for dicts / binary

**Severity:** LOW · **Status:** ✅ RESOLVED (2026-04-18) — Option 2
chosen. Every stdlib tool in M1 Task 06 is annotated `-> str`; the
convention is documented in the `fs.py` and `shell.py` module docstrings
and pinned by
`tests/primitives/tools/test_stdlib.py::test_stdlib_tool_is_annotated_to_return_str`
(9 parametrised cases). Worker (M2 Task 02) and any future tool author
who ships a non-string return type will trip the test.

**What's observed.** The wrapper in
[registry.py::_wrap_with_forensics](../../../../ai_workflows/primitives/tools/registry.py)
calls `log_suspicious_patterns(..., output=str(result), ...)`. When a
tool returns a string, this is a no-op. When a tool returns a `dict`,
`list`, Pydantic model, or `bytes`, the forensic scan sees
`str(dict(...))` — `{'key': 'value'}` — which obscures the payload that
the model will actually receive. pydantic-ai serialises structured tool
outputs itself before handing them to the model, so the scan is looking
at a different string than the model sees.

**Why this matters.** Forensic coverage is slightly weaker than intended
for non-string tools. The primary use-case — `read_file`, `grep`,
`run_command` in Task 06 — all return `str`, so the gap is latent until
structured-output tools exist.

**Recommendation.** When Task 06 or later introduces a tool that returns
non-string data, one of:

1. Wrap the value with the same JSON serialiser pydantic-ai uses (check
   `pydantic_ai.tools._function_schema`'s serialisation path) so the
   forensic scan sees the exact bytes the model will receive.
2. Document the convention that registered tools return `str`; anything
   else is serialised by the caller.

Option 2 is simpler and matches the Task 05 spec signature
(`get_tool_callable(name) -> Callable`) without mandating a return type.
Pick option 1 only if a real non-string tool ships before M3.

---

## Additions beyond spec — audited and justified

| Addition | Justification |
| --- | --- |
| `ToolAlreadyRegisteredError(ValueError)` raised on duplicate `register()` | Spec's `register(name, fn, description) -> None` is silent on duplicates. Silently shadowing an existing tool registration is an unambiguous programmer error — a workflow almost never wants two callables under the same name. Fail loud. Subclasses `ValueError` so an `except ValueError` at the caller still catches. |
| `ToolNotRegisteredError(KeyError)` raised on unknown name in `get_tool_callable` / `build_pydantic_ai_tools` | Spec signature is `get_tool_callable(name: str) -> Callable`; the natural `KeyError` is too vague — the error message has to tell the caller what *was* registered so a typo is one-hop to fix. Subclasses `KeyError` so idiomatic catches still work. |
| `ToolRegistry.registered_names() -> list[str]` | Not in spec. Convenience for diagnostics, the eventual `aiw` CLI surface (Task 12), and error messages that list what *is* registered when a name is missing. Read-only — cannot break invariants. |
| Duplicate-name rejection inside `build_pydantic_ai_tools(names)` | Spec is silent. Passing `["read_file", "read_file"]` would otherwise wrap the same callable twice and emit two forensic events per call — measurable waste and a misleading audit log. Fail loud with `ValueError`. |
| Empty-name / empty-description rejection in `register()` | Defensive; silent-pass leads to tools the model cannot describe or address. `ValueError`. |
| `_wrap_with_forensics` supports sync + async and extracts `run_id` from `RunContext[WorkflowDeps]` when present | Spec's "Tool Execution Flow" section describes this logging step but does not name the signature contract. The wrapper uses `functools.wraps` so pydantic-ai's `inspect.signature` still reads the correct schema (pinned by `test_wrapper_preserves_original_function_signature`). When the tool takes `ctx` as first param, `run_id` is lifted out of `ctx.deps.run_id`; otherwise `"unknown"` (the forensic entry is still useful). |
| `INJECTION_PATTERNS` additions beyond the five listed in the spec (`### NEW INSTRUCTION`, `DISREGARD … ABOVE`) | The spec list ends with `# ...`. Both extras are common prompt-injection openers (documented in public red-team corpora); zero cost to include and covered by the parametrised test. |

No additions cross the layering boundary: `registry.py` imports only
`pydantic_ai.Tool` and the sibling `forensic_logger`; `forensic_logger.py`
imports only `structlog`. Both are inside
`ai_workflows.primitives.tools`. `import-linter` confirms (`Contracts: 2
kept, 0 broken`).

---

## Gate summary (2026-04-18)

| Gate | Result |
| --- | --- |
| `uv run pytest` | ✅ 113 passed, 0 skipped (29 new Task 05 tests + 84 pre-existing) |
| `uv run lint-imports` | ✅ 2 kept / 0 broken |
| `uv run ruff check` | ✅ all checks passed |
| Task-spec CI check (`secret-scan`) | ✅ not applicable — Task 05 does not touch committed config |

---

## Acceptance-criterion grading

| AC | Verdict | Evidence |
| --- | --- | --- |
| AC-1: Two `ToolRegistry()` instances have zero shared state | ✅ PASS | `test_two_registries_have_zero_shared_state` (name set isolation after write) + `test_registry_is_not_a_singleton_via_class_attribute` (pins `self._entries` is instance-level, not class-level) |
| AC-2: `build_pydantic_ai_tools(["read_file"])` returns exactly 1 tool | ✅ PASS | `test_build_pydantic_ai_tools_returns_only_the_named` (asserts length 1 and name); reinforced by `test_build_pydantic_ai_tools_preserves_order` and `test_build_pydantic_ai_tools_empty_list_returns_empty_list` |
| AC-3: `forensic_logger` matches patterns without modifying output | ✅ PASS | `test_forensic_logger_matches_known_patterns` (8 parametrised cases) + `test_forensic_logger_does_not_modify_output` (asserts return is `None` and input unchanged) + `test_forensic_logger_silent_on_benign_output` |
| AC-4: WARNING structlog event on known pattern | ✅ PASS | `test_forensic_logger_matches_known_patterns` asserts `rec.levelno == logging.WARNING` and the event name `tool_output_suspicious_patterns` + fields `run_id`, `tool_name`; reinforced by `test_forensic_logger_records_output_length` |
| AC-5: Docstrings explicitly state NOT a security control | ✅ PASS | `test_forensic_logger_module_docstring_disclaims_security_control` + `test_log_suspicious_patterns_docstring_disclaims_security_control` — both search for the literal phrase |

---

## Issue log — tracked for cross-task follow-up

- **M1-T05-ISS-01** ✅ RESOLVED (2026-04-18) — pinned by
  `tests/primitives/tools/test_stdlib.py::test_forensic_wrapper_survives_real_agent_run`
  (M1 Task 06).
- **M1-T05-ISS-02** ⏸️ DEFERRED — smoke test that the forensic WARNING
  survives the production structlog processor chain. Owner: M1 Task 11
  (global structlog + logfire configuration).
- **M1-T05-ISS-03** ✅ RESOLVED (2026-04-18) — Option 2 (string returns)
  chosen. Pinned by
  `tests/primitives/tools/test_stdlib.py::test_stdlib_tool_is_annotated_to_return_str`
  (M1 Task 06).

**Propagation status.** All three deferrals are mirrored as "Carry-over
from prior audits" entries in the target task spec(s) so the Builder
picks them up automatically:

- `M1-T05-ISS-01` → [../task_06_stdlib_tools.md](../task_06_stdlib_tools.md)
  (primary) and [../../milestone_2_components/task_02_worker.md](../../milestone_2_components/task_02_worker.md)
  (alternative).
- `M1-T05-ISS-02` → [../task_11_logging.md](../task_11_logging.md).
- `M1-T05-ISS-03` → [../task_06_stdlib_tools.md](../task_06_stdlib_tools.md)
  (primary) and [../../milestone_2_components/task_02_worker.md](../../milestone_2_components/task_02_worker.md)
  (alternative).

Cross-refs resolved by this task:

- `CRIT-04` — flipped to `[x]` in
  [design_docs/issues.md](../../../issues.md): sanitizer never landed;
  `forensic_logger.py` ships with the required NOT-a-security-control
  disclaimers and is wired as logging-only through
  `ToolRegistry.build_pydantic_ai_tools()`.
- `P-11`, `P-20` — already `[x]` in the backlog (historical marking);
  `ToolRegistry` now physically exists.
- `M1-T04-ISS-03` (forensic-replay use of `apply_cache_control()`) —
  unchanged: Task 05's forensic logger is a passive scanner, not a
  replayer; the Task 04 helper remains the canonical pure-function
  reference and is not called here.
