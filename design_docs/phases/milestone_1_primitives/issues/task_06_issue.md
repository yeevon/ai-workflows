# Task 06 — Stdlib Tools (fs, shell, http, git) — Audit Issues

**Source task:** [../task_06_stdlib_tools.md](../task_06_stdlib_tools.md)
**Audited on:** 2026-04-18
**Audit scope:** full Task 06 surface —
[ai_workflows/primitives/tools/fs.py](../../../../ai_workflows/primitives/tools/fs.py),
[ai_workflows/primitives/tools/shell.py](../../../../ai_workflows/primitives/tools/shell.py),
[ai_workflows/primitives/tools/http.py](../../../../ai_workflows/primitives/tools/http.py),
[ai_workflows/primitives/tools/git.py](../../../../ai_workflows/primitives/tools/git.py),
[ai_workflows/primitives/tools/stdlib.py](../../../../ai_workflows/primitives/tools/stdlib.py),
[ai_workflows/primitives/tools/__init__.py](../../../../ai_workflows/primitives/tools/__init__.py),
[tests/primitives/tools/](../../../../tests/primitives/tools/) (conftest + 5 test files, 75 tests total),
[CHANGELOG.md](../../../../CHANGELOG.md) (M1 Task 06 entry),
[README.md](../README.md), sibling task files (02, 03, 04, 05, 07, 08, 11),
[design_docs/issues.md](../../../issues.md),
[pyproject.toml](../../../../pyproject.toml),
[.github/workflows/ci.yml](../../../../.github/workflows/ci.yml),
[task_05_issue.md](task_05_issue.md) (carry-over source).
All three gates re-run locally after the audit read.

**Status:** ✅ PASS — every acceptance criterion satisfied, every carry-
over item from Task 05 closed with a pinning test. One HIGH regression
(missing runtime imports for `RunContext` / `WorkflowDeps`) was caught
*during* the audit, fixed in-band, and pinned by
`test_register_stdlib_tools_can_be_built_for_pydantic_ai`. No other
OPEN issues. Three LOW / informational items are ⏸️ DEFERRED to named
future owners.

---

## 🔴 HIGH

_No OPEN HIGH issues._

### M1-T06-ISS-01 — Stdlib tool modules hid `RunContext` behind `TYPE_CHECKING`, breaking `Tool(…)` schema generation · ✅ RESOLVED in-band

**Status:** ✅ RESOLVED (same audit cycle) — commit-local fix.

**What was observed.** The first pass of
[fs.py](../../../../ai_workflows/primitives/tools/fs.py),
[shell.py](../../../../ai_workflows/primitives/tools/shell.py),
[http.py](../../../../ai_workflows/primitives/tools/http.py), and
[git.py](../../../../ai_workflows/primitives/tools/git.py) imported
`pydantic_ai.RunContext` and
`ai_workflows.primitives.llm.types.WorkflowDeps` under
`if TYPE_CHECKING:` for the return-type / parameter annotation. The
unit tests passed because they invoke the callables directly — they
never go through `pydantic_ai.Tool.__init__`. A smoke test against the
full registration path (`register_stdlib_tools(r) →
r.build_pydantic_ai_tools(r.registered_names())`) failed with
`NameError: name 'RunContext' is not defined` out of
`pydantic_ai._function_schema.function_schema → typing.get_type_hints`.

**Why this matters.** HIGH — this is the one code path the Worker
(M2 Task 02) will actually exercise on every run. Without this fix
the stdlib tools could be registered but not built, so the AC "tools
pull `allowed_executables` and `project_root` from
`RunContext[WorkflowDeps]`" would have been satisfied *by annotation
only*, not by a runtime call.

**Resolution.** Moved the imports out of `TYPE_CHECKING` in all four
modules; `RunContext` and `WorkflowDeps` are now plain runtime
imports. No cycle risk — the `primitives.llm.types` module does not
import from `primitives.tools`.

**Regression guard.** Added
[test_register_stdlib_tools_can_be_built_for_pydantic_ai](../../../../tests/primitives/tools/test_stdlib.py) —
calls `register_stdlib_tools(r)` then `r.build_pydantic_ai_tools(r.registered_names())`
and asserts that every canonical stdlib name survives schema generation.
Any future regression in the annotation-resolution path (e.g. a new
stdlib tool added under `TYPE_CHECKING` by habit) fails this test.

---

## 🟡 MEDIUM

_No MEDIUM issues._

---

## 🟢 LOW

### M1-T06-ISS-02 — `read_file` reads entire bytes before applying `max_chars`

**Severity:** LOW · **Status:** ⏸️ DEFERRED — owner: cross-cutting fs
hardening backlog (tracked as `P-20a` in
[design_docs/issues.md](../../../issues.md))

**What's observed.**
[`fs.read_file`](../../../../ai_workflows/primitives/tools/fs.py) calls
`Path(path).read_bytes()` before applying the `max_chars` truncation.
For a 1 GB log file the whole thing is pulled into RAM even if the
caller only wanted the first 1 KiB.

**Why this matters.** Forward-looking. The stdlib tools target project
trees and source code (small files), and the forensic scan at
`ToolRegistry.build_pydantic_ai_tools` only sees the truncated string,
so the model-visible surface stays correct. The exposure is purely
resident memory during the tool call.

**Recommendation.** No code change now. When a workflow reports an OOM
or slow `read_file`, replace the `read_bytes()` path with a chunked
read that reads up to `max_chars * 4` bytes (UTF-8 upper bound) then
decodes — yields the same output with bounded memory. Until then this
is a documentation-only entry.

### M1-T06-ISS-03 — `list_dir` returns `entry.name` only, losing nested structure under recursive glob

**Severity:** LOW · **Status:** ⏸️ DEFERRED — owner:
[M2 Task 02 Worker](../../milestone_2_components/task_02_worker.md)
(first consumer that might pass a recursive pattern through a prompt)

**What's observed.**
[`fs.list_dir`](../../../../ai_workflows/primitives/tools/fs.py) emits
`entry.name` for each listing entry. When the caller passes a
recursive pattern (`pattern="**/*.py"`), `Path.glob("**/*.py")` returns
paths like `Path("/base/pkg/mod.py")` whose `.name` is `"mod.py"` — the
`pkg/` prefix is dropped. The returned listing therefore cannot
distinguish two files with the same basename in different
subdirectories.

**Why this matters.** Forward-looking. Task 06's tests only exercise
`pattern="*.py"` (non-recursive), where `entry.name` is unambiguous.
The spec says "glob-aware" without naming the recursive case. When a
workflow starts passing `**/…` patterns, ambiguous names will confuse
the model.

**Recommendation.** When a workflow first files a "I saw two identical
filenames in a list_dir result" bug — or preemptively, when the Worker
integration test lands in M2 — change the emission to
`str(entry.relative_to(base))` when `pattern` is passed *and* the
pattern contains `**`, else keep `entry.name`. Or unconditionally
emit the relative path; it is always unambiguous. Pick the latter if
schema-churn concerns are low.

### M1-T06-ISS-04 — `_check_clean_tree` raises `DirtyWorkingTreeError` for non-repo paths

**Severity:** LOW · **Status:** ⏸️ DEFERRED — owner:
[M2 Task 02 Worker](../../milestone_2_components/task_02_worker.md)
(first consumer to drive `git_apply` end-to-end)

**What's observed.**
[`git._check_clean_tree`](../../../../ai_workflows/primitives/tools/git.py)
runs `git -C {repo_path} status --porcelain`; on a non-repo path the
command exits non-zero and we raise `DirtyWorkingTreeError` with the
`stderr` content embedded. Strictly this is semantic drift — "not a
git repo" is not the same as "dirty tree", and the error class name
misleads a reader who only sees the exception name.

**Why this matters.** Minor. The outer `git_apply` catches the error
and returns a string; the string contains the original stderr ("not a
git repository") so the model can still react. The concern is purely
cleanliness of the exception class vs. the actual condition.

**Recommendation.** When the next git-tool PR lands, split the check
into two branches: non-zero return → `Error: not a git repository at
{repo_path}`; non-empty stdout → `DirtyWorkingTreeError`. Until then
the current behaviour is correct (refuses to apply) even if the error
label is broad.

---

## Additions beyond spec — audited and justified

| Addition | Justification |
| --- | --- |
| `_check_cwd_containment` / `_check_executable` as module-level helpers | The spec lists the guards as numbered steps of `run_command`. Extracting each into a pure helper gives (a) a focused raises-on-failure unit test per guard, satisfying both "raises X" ACs directly at the guard level, and (b) a single place to update the containment logic if symlink semantics need hardening later. Both helpers carry leading underscores and are intentionally not re-exported in `shell.__all__` — callers go through `run_command`. |
| `ai_workflows/primitives/tools/stdlib.py` new module | The spec says `register_stdlib_tools` "is called at workflow run start". Putting the registration helper into its own module keeps the tool-module imports linear (`fs` / `shell` / `http` / `git` have no knowledge of each other) and leaves `tools/__init__.py` as a pure docstring hub. |
| `tests/primitives/tools/conftest.py` — `CtxShim` + `ctx_factory` | Constructing a real `pydantic_ai.RunContext` requires a live `Model` and `RunUsage`. Every stdlib tool only reads `ctx.deps`, so a dataclass shim with a single `deps` attribute is sufficient for direct-invocation tests. This mirrors the pattern already used by `test_tool_registry.py::test_wrapper_extracts_run_id_from_runcontext_first_arg`. |
| `[DRY RUN] Diff applies cleanly.` / `Applied diff successfully.` / `Wrote {N} chars to {path}` success strings | The spec calls for "`Exit {code}\n{output}`" on `run_command` success but is silent on the non-shell tools. Explicit success strings surface completion state to the LLM so it can chain follow-up tool calls; they are short and do not include user data beyond what the caller already supplied. |
| Error-string prefixes that name the exception class (`SecurityError:`, `ExecutableNotAllowedError:`, `CommandTimeoutError:`, `DirtyWorkingTreeError:`) | The AC says "all tools return strings on error paths". Naming the original exception class in the prefix preserves the diagnostic value of the raised error without the traceback. Also makes tests cheap: `out.startswith("SecurityError")` is a single-line assertion. |
| `test_stdlib_tool_is_annotated_to_return_str` — 9 parametrised cases | Pins `M1-T05-ISS-03`'s "Option 2" decision at the test level. Any future stdlib tool author who sets the return annotation to `dict` / `BaseModel` / `bytes` fails this test. Cheaper than a commit-time review comment. |
| `test_register_stdlib_tools_can_be_built_for_pydantic_ai` regression guard | Pins the HIGH fix above (`RunContext` must be importable at runtime). Ensures a future tool author copying the old `TYPE_CHECKING` pattern hits the CI wall. |

No additions cross the layering boundary. `fs` / `shell` / `http` /
`git` each import only `pydantic_ai.RunContext` plus
`ai_workflows.primitives.llm.types.WorkflowDeps`; `stdlib` imports only
the four sibling modules and `ToolRegistry`. `import-linter` confirms
(`Contracts: 2 kept, 0 broken`).

---

## Gate summary (2026-04-18)

| Gate | Result |
| --- | --- |
| `uv run pytest` | ✅ 188 passed, 0 skipped (75 new Task 06 tests + 113 pre-existing) |
| `uv run lint-imports` | ✅ 2 kept / 0 broken |
| `uv run ruff check` | ✅ all checks passed |
| Task-spec CI check (`secret-scan`) | ✅ not applicable — Task 06 touches no committed config / secrets |

---

## Acceptance-criterion grading

| AC | Verdict | Evidence |
| --- | --- | --- |
| AC-1: `read_file` handles UTF-8 + latin-1 fallback gracefully | ✅ PASS | `test_read_file_returns_utf8_content` (UTF-8 path) + `test_read_file_falls_back_to_latin1_on_invalid_utf8` (invalid UTF-8 → `"café"` via latin-1 decode) |
| AC-2: `..` in `working_dir` raises `SecurityError` naming the attempted path | ✅ PASS | `test_check_cwd_containment_rejects_parent_traversal` (guard raises with "escape" in message) + `test_run_command_security_error_returns_string` (top-level tool returns `SecurityError: …` string containing the attempted path) |
| AC-3: Executable not in allowlist raises `ExecutableNotAllowedError` | ✅ PASS | `test_check_executable_rejects_when_not_in_allowlist` + `test_check_executable_rejects_empty_allowlist` + `test_run_command_executable_not_allowed_returns_string` |
| AC-4: `dry_run=True` never invokes subprocess | ✅ PASS | `test_run_command_dry_run_does_not_invoke_subprocess` uses `unittest.mock.patch.object(subprocess, "run")` and asserts `mocked_run.assert_not_called()`. Reinforced by `test_run_command_dry_run_still_enforces_guards` — dry-run still trips the earlier guards. |
| AC-5: `git_apply` refuses on dirty working tree | ✅ PASS | `test_git_apply_refuses_dirty_tree` (stages a diff, dirties the tree with an unrelated file, asserts the return string starts with `DirtyWorkingTreeError` and echoes the porcelain listing) |
| AC-6: All tools return strings on error paths | ✅ PASS | Every tool has a dedicated `_returns_string` test covering the taxonomy of failure modes. Non-exhaustive list: `read_file` missing / on-directory; `write_file` implicit via the OSError branch; `list_dir` missing / on-file; `grep` missing path / invalid regex; `run_command` all 3 guards + timeout + missing exec + non-zero exit; `http_fetch` timeout / network / invalid URL; `git_diff` bad ref; `git_log` non-repo; `git_apply` bad diff / non-repo. Each asserts `isinstance(out, str)`. |
| AC-7: Tools pull `allowed_executables` and `project_root` from `RunContext[WorkflowDeps]` | ✅ PASS | `test_stdlib_tool_first_parameter_is_ctx` (9 parametrised cases pin the `ctx` first-param convention); `run_command` body reads `ctx.deps.project_root` (tested via the success + security paths) and `ctx.deps.allowed_executables` (tested via the allowlist path); `test_register_stdlib_tools_can_be_built_for_pydantic_ai` pins that the `RunContext[WorkflowDeps]` annotations survive pydantic-ai's schema generation at runtime. |

### Carry-over from Task 05

| Carry-over | Verdict | Evidence |
| --- | --- | --- |
| M1-T05-ISS-01 — live `Agent.run()` test pins the forensic wrapper is in the path | ✅ RESOLVED | `test_forensic_wrapper_survives_real_agent_run` — uses `TestModel(call_tools=["injected_tool"])`, registers a tool whose output contains an `INJECTION_PATTERNS` marker, runs `agent.run(...)` with `deps=WorkflowDeps(...)`, and asserts the `tool_output_suspicious_patterns` WARNING fires. Any future pydantic-ai change that bypasses `__wrapped__` fails this test. |
| M1-T05-ISS-03 — standardise on `str` returns for stdlib tools | ✅ RESOLVED | Option 2 chosen — every stdlib tool is annotated `-> str`; pinned by `test_stdlib_tool_is_annotated_to_return_str` (9 parametrised cases). Convention is called out in `fs.py` + `shell.py` module docstrings ("pinned on M1-T05-ISS-03"). |

---

## Issue log — tracked for cross-task follow-up

- **M1-T06-ISS-01** ✅ RESOLVED in-band (audit cycle). Missing runtime
  imports broke `Tool(…)` schema generation. Fixed; pinned by
  `test_register_stdlib_tools_can_be_built_for_pydantic_ai`.
- **M1-T06-ISS-02** ⏸️ DEFERRED (LOW) — `read_file` loads entire file
  before truncation. Propagated to
  [design_docs/issues.md](../../../issues.md) as `P-20a` (cross-cutting
  fs hardening backlog).
- **M1-T06-ISS-03** ⏸️ DEFERRED (LOW) — `list_dir` loses nested
  structure under `**/…` glob. Propagated as a carry-over entry on
  [M2 Task 02 Worker](../../milestone_2_components/task_02_worker.md).
- **M1-T06-ISS-04** ⏸️ DEFERRED (LOW) — `_check_clean_tree` raises
  `DirtyWorkingTreeError` for non-repo paths. Propagated as a
  carry-over entry on
  [M2 Task 02 Worker](../../milestone_2_components/task_02_worker.md).

**Propagation status.** All three DEFERRED items have concrete owners
and are recorded where their next-touch Builder will read them:

| Issue | Target file | Entry |
| --- | --- | --- |
| M1-T06-ISS-02 | [design_docs/issues.md](../../../issues.md) | `P-20a` under Primitives → Tool Registry |
| M1-T06-ISS-03 | [M2 Task 02 Worker](../../milestone_2_components/task_02_worker.md) | Carry-over from prior audits |
| M1-T06-ISS-04 | [M2 Task 02 Worker](../../milestone_2_components/task_02_worker.md) | Carry-over from prior audits |

The two Task 05 carry-over items closed by this task
(`M1-T05-ISS-01`, `M1-T05-ISS-03`) were also ticked off on the Worker
task's carry-over list in the same edit, so the Worker Builder does not
need to re-audit them.

Cross-refs resolved by this task:

- `P-13`, `P-14` (fs tools), `P-15`, `P-16` (shell + guards), `P-17`
  (dry-run), `P-18` (http), `P-19` (git) — all landed.
- `M1-T05-ISS-01`, `M1-T05-ISS-03` — checkboxes ticked on
  [../task_06_stdlib_tools.md](../task_06_stdlib_tools.md); Task 05
  issue file entries can be flipped DEFERRED → ✅ RESOLVED on the next
  Task 05 re-read.
