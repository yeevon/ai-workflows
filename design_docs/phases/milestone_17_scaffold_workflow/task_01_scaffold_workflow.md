# Task 01 — `scaffold_workflow` graph + validator + write-safety + CLI/MCP wiring

**Status:** 📝 Planned.
**Grounding:** [milestone README](README.md) · [ai_workflows/workflows/planner.py](../../../ai_workflows/workflows/planner.py) (shape to mirror) · [ai_workflows/workflows/__init__.py:58-76](../../../ai_workflows/workflows/__init__.py#L58-L76) (`register()` — scaffold outputs code that calls this) · [M11 README](../milestone_11_gate_review/README.md) (gate-pause projection — scaffold surfaces code preview here) · [M16 task_01](../milestone_16_external_workflows/task_01_external_load_path.md) (load-path the scaffold's output rides on).

## What to Build

The end-to-end `scaffold_workflow` `StateGraph`: input handling, LLM synthesis node (`TieredNode` routing to Claude Opus by default via M15 overlay), schema-validator node (`ValidatorNode` enforcing parseable Python + `register()` shape), `HumanGate` surfacing the code preview, atomic write-to-disk node. Plus the CLI command, the MCP tool parameters, and the stub-adapter-driven hermetic tests. Prompt engineering iteration lands in T02; ADR + doc updates land in T03.

## Deliverables

### 1. New module `ai_workflows/workflows/scaffold_workflow.py`

Mirrors the shape of `planner.py`. Contains:

- `ScaffoldWorkflowInput` pydantic model: `goal: str`, `target_path: Path`, `force: bool = False`, `tier_preferences: dict[str, str] | None = None`, `existing_workflow_context: str | None = None` (optional — user can hint at an existing workflow's shape).
- `ScaffoldedWorkflow` pydantic model (the LLM output schema): `name: str`, `source_python: str`, `description: str`, `declared_tiers: dict[str, TierConfig]`, `requires_human_gate: bool`, `reasoning: str`.
- `build_scaffold_workflow()` factory that returns a compiled `StateGraph`.
- `scaffold_workflow_tier_registry()` helper — declares a single `scaffold-synth` tier routing to `ClaudeCodeRoute(cli_model_flag="opus")` with sensible concurrency/timeout defaults (match `planner-synth`: `max_concurrency=1`, `per_call_timeout_s=300`).
- Module-top `register("scaffold_workflow", build_scaffold_workflow)` call, per the existing convention.

Graph shape (minimum):

```
[validate_input]       # pydantic parse + target_path safety guards
      │
      ▼
[synthesize_source]    # TieredNode, tier=scaffold-synth, output=ScaffoldedWorkflow
      │
      ▼
[validate_output]      # ValidatorNode — ast.parse + register() AST walk
      │                  (on failure, loops back to synthesize_source up to retry budget)
      ▼
[preview_gate]         # HumanGate — gate_id="scaffold_review"; surfaces source_python + summary
      │                  (resume with approved=True → proceed; approved=False → abort)
      ▼
[write_to_disk]        # atomic write of source_python to target_path
      │
      ▼
 [END]                 # returns WriteOutcome(target_path, sha256_of_written_file)
```

### 2. Write-safety module `ai_workflows/workflows/_scaffold_write_safety.py`

Separate module because the safety rules are load-bearing and testable in isolation. Public surface:

```python
class TargetInsideInstalledPackageError(ValueError): ...
class TargetDirectoryNotWritableError(OSError): ...
class TargetExistsError(FileExistsError): ...
class TargetRelativePathError(ValueError): ...

def validate_target_path(
    target: Path,
    *,
    force: bool = False,
) -> Path:
    """Resolve, validate, and return an absolute target path.

    Rejects:
      - Paths inside the installed ai_workflows package.
      - Parent directories that don't exist or aren't writable.
      - Existing files when force=False.
      - Relative paths (ambiguous against server/client cwd).

    Returns the resolved absolute path on success.
    """

def atomic_write(target: Path, content: str) -> str:
    """Write content atomically. Returns SHA256 hex of written bytes.

    Uses tempfile.NamedTemporaryFile in the same directory, then
    os.replace() to swap. Ensures a partial write cannot corrupt a
    previous good file on crash.
    """
```

Package-root detection: compare `target.resolve()` against `Path(ai_workflows.__file__).parent.resolve()` (and all its ancestors up to site-packages) using `.is_relative_to()`.

### 3. Validator module `ai_workflows/workflows/_scaffold_validator.py`

```python
class ScaffoldOutputValidationError(ValueError):
    """Raised when ScaffoldedWorkflow output fails schema checks."""

def validate_scaffold_output(output: ScaffoldedWorkflow) -> None:
    """Raise if output is not a valid scaffolded workflow.

    Checks:
      1. source_python parses via ast.parse() (syntax-valid).
      2. The AST contains at least one top-level Call node whose
         func name is "register" and whose first arg is a string
         literal equal to output.name.
      3. The source_python length is non-trivial (>= 80 chars —
         catches empty / placeholder emits; tune at T02 post-smoke).
    """
```

Returns `None` on success; raises `ScaffoldOutputValidationError` with a descriptive message on failure. The `ValidatorNode` wraps this and triggers `RetryingEdge` on failure per KDR-006.

### 4. CLI command

Add a new Typer command to `ai_workflows/cli.py`:

```python
@app.command()
def run_scaffold(
    goal: str = typer.Option(..., "--goal", help="Description of the workflow to scaffold."),
    target: Path = typer.Option(..., "--target", help="Absolute path to write the .py file to."),
    force: bool = typer.Option(False, "--force", help="Overwrite an existing file at target."),
    tier_override: list[str] = typer.Option(None, "--tier-override", help="Override a tier for this run (name=replacement)."),
) -> None:
    """Alias for `aiw run scaffold_workflow ...` with the scaffold's specific flags."""
```

This is a **thin alias** — it routes through the existing `aiw run <workflow>` dispatch with `workflow="scaffold_workflow"` and the scaffold's `ScaffoldWorkflowInput` shape. Reason: users invoking `aiw run scaffold_workflow --target ... --force` via the generic surface would need to pass `--goal` + `--target` + `--force` as workflow-input JSON, which is friction. The alias keeps the UX clean.

### 5. MCP exposure

No new MCP tool. The existing `run_workflow(workflow="scaffold_workflow", input={...})` surface covers it — `ScaffoldWorkflowInput` is just another workflow-input schema. The gate-pause projection (M11) surfaces the code preview in `gate_context`. `resume_run(run_id=..., approved=True)` completes the write.

T01 adds one MCP test asserting the scaffold round-trips correctly via `fastmcp.Client` over HTTP (mirrors the M14 pattern). The test uses the stub adapter to script the LLM output.

### 6. Tests — `tests/workflows/test_scaffold_workflow.py` (new)

Hermetic. Uses stub adapter + tmp_path + pytest fixtures. No live LLM.

**Validator tests** (test the `_scaffold_validator.py` surface directly):

- `test_validator_accepts_well_formed_output` — a hand-written `ScaffoldedWorkflow` with a valid two-line source + matching `register(...)`; assert no raise.
- `test_validator_rejects_syntactically_invalid_python` — source with `def =` (parse error); assert raises.
- `test_validator_rejects_missing_register_call` — valid Python but no `register()` call; raises.
- `test_validator_rejects_register_with_wrong_name` — calls `register("other_name", ...)` but `output.name == "my_workflow"`; raises.
- `test_validator_rejects_register_first_arg_non_string` — calls `register(some_var, ...)`; raises (arg must be a string literal).
- `test_validator_rejects_trivially_short_source` — 20-character string that parses but is too short to be a real workflow; raises (minimum-length floor at T01 = 80 chars; tune at T02).

**Write-safety tests** (test `_scaffold_write_safety.py` directly):

- `test_atomic_write_creates_file_and_returns_sha256` — write "hello", assert file contents + SHA256.
- `test_atomic_write_overwrites_only_on_replace` — write twice; mid-write-crash simulation asserts original file intact (inject an exception between tempfile write + rename).
- `test_validate_target_rejects_inside_installed_package` — resolve the ai_workflows package dir; construct a target inside it; assert `TargetInsideInstalledPackageError`.
- `test_validate_target_rejects_nonexistent_parent_directory` — target at `/tmp/nonexistent-xyz/file.py`; assert `TargetDirectoryNotWritableError`.
- `test_validate_target_rejects_readonly_parent` — chmod a tmp directory 0500; target inside it; assert `TargetDirectoryNotWritableError`.
- `test_validate_target_rejects_existing_file_when_not_forced` — existing file + `force=False`; raises `TargetExistsError`.
- `test_validate_target_accepts_existing_file_when_forced` — existing file + `force=True`; returns resolved path.
- `test_validate_target_rejects_relative_path` — `"./scaffolded.py"`; raises `TargetRelativePathError`.

**Integration tests** (stub adapter, full graph):

- `test_scaffold_end_to_end_with_stub_adapter` — stub LLM emits a valid `ScaffoldedWorkflow`; validator passes; gate triggers; resume with approve; file is written to tmp_path; SHA256 matches expected; the written file's contents round-trip through `ast.parse()` cleanly.
- `test_scaffold_validator_retry_on_bad_output` — stub emits invalid output on first attempt, valid output on second; assert `RetryingEdge` drives the second attempt; file writes successfully.
- `test_scaffold_gate_rejection_aborts_without_write` — stub emits valid output; gate rejects (`resume_run(..., approved=False)`); tmp_path has no new file.
- `test_scaffold_write_failure_after_approve_surfaces_error` — stub emits valid output; gate approves; the write-safety guard trips (e.g. target-inside-package); assert structured error surfaces through the workflow.

**MCP HTTP parity test** — new `tests/mcp/test_http_scaffold_workflow.py`:

- `test_scaffold_round_trips_over_http` — spin the HTTP server with a stubbed scaffold tier; `run_workflow(workflow="scaffold_workflow", input=...)` + resume; assert the written file matches expectations. Mirrors M14's HTTP-parity test pattern.

### 7. Stub adapter harness for scaffold tests

`tests/workflows/conftest.py` (or similar) gains a `scaffold_stub_adapter` fixture that scripts LLM output for the scaffold's tier. Uses the existing `StubLLMAdapter` pattern from `ai_workflows/evals/_stub_adapter.py` — no new test harness.

### 8. Module docstrings

- `scaffold_workflow.py` — cites M17 T01, the sibling workflows (planner, slice_refactor) the shape mirrors, the relationship to M15 tier overlay + M16 external load path.
- `_scaffold_write_safety.py` — cites M17 T01 + ADR-0008 (the risk-ownership decision the safety guards enforce).
- `_scaffold_validator.py` — cites M17 T01 + ADR-0008 + the explicit non-goal of linting/testing user code.

### 9. CHANGELOG entry

Under `[Unreleased]` on both branches — new `### Added — M17 Task 01: scaffold_workflow meta-workflow graph + validator + write safety (YYYY-MM-DD)` entry. Names the new modules, the ACs covered, the tier-default, the MCP surface, and the ADR-0008 placeholder (filled at T03).

## Acceptance Criteria

- [ ] **AC-1: `scaffold_workflow` registered.** `aiw list-workflows` shows `scaffold_workflow` alongside `planner` + `slice_refactor`. The module-top `register()` call fires on import.
- [ ] **AC-2: `ScaffoldWorkflowInput` + `ScaffoldedWorkflow` pydantic models** exist with the fields named above. Schema validation is strict (extra fields forbidden; types enforced).
- [ ] **AC-3: Validator enforces parseable Python + `register()` shape.** `_scaffold_validator.py` runs `ast.parse()` + walks the AST. Six validator tests pass (five reject cases + one accept case).
- [ ] **AC-4: Write-safety guards enforced.** Eight write-safety tests pass covering every rejection class + the atomic-write contract.
- [ ] **AC-5: `HumanGate` preview carries the code + declared tiers.** Gate's `gate_context` (per M11) includes `source_python`, `declared_tiers`, `target_path`, and a short summary. The HTTP parity test asserts the preview survives transport.
- [ ] **AC-6: Atomic write on gate approval.** On `resume_run(..., approved=True)`, the file is written via `os.replace()` from a temp file in the same directory. SHA256 of the written bytes matches the scaffold's output.
- [ ] **AC-7: CLI alias `aiw run-scaffold`.** The Typer alias is registered; `--goal` + `--target` + `--force` + `--tier-override` flags work. Routes through the generic `run_workflow` dispatch under the hood.
- [ ] **AC-8: MCP surface unchanged externally.** `run_workflow(workflow="scaffold_workflow", input=...)` works over stdio + HTTP. No new MCP tool; no schema drift.
- [ ] **AC-9: Tier registry declared.** `scaffold_workflow_tier_registry()` exists and declares `scaffold-synth` routing to Claude Opus. M15's overlay can rebind it.
- [ ] **AC-10: Retry + abort semantics.** On validator failure, `RetryingEdge` drives a second attempt with the validator's error re-rendered into the next prompt (T02 scope for the prompt engineering; T01 scope for the retry wiring). On gate rejection, the run terminates with `status="rejected"` and no file is written.
- [ ] **AC-11: Hermetic tests land green.** `tests/workflows/test_scaffold_workflow.py` — all integration + validator + write-safety tests pass. `tests/mcp/test_http_scaffold_workflow.py` — HTTP round-trip passes.
- [ ] **AC-12: Four-layer contract preserved.** `uv run lint-imports` reports 4 kept, 0 broken. Scaffold lives in `workflows/` layer; write-safety + validator modules sit alongside.
- [ ] **AC-13: KDR-004 compliance.** The LLM synthesis node is paired with a validator node immediately downstream. The gate node is not a validator (it's a human-review step, not a schema check). Confirmed by reading the graph wiring.
- [ ] **AC-14: KDR-003 compliance.** No `anthropic` SDK import. No `ANTHROPIC_API_KEY` env-var lookup. Claude access is via `ClaudeCodeSubprocess` only.
- [ ] **AC-15: Gates green.** `uv run pytest` + `uv run lint-imports` + `uv run ruff check` on both branches.
- [ ] **AC-16: Module docstrings land** per the spec above.
- [ ] **AC-17: CHANGELOG entry** under `[Unreleased]` on both branches. Names files touched, ACs satisfied, T02 follow-up scope (prompt iteration + live-mode smoke + CS300 dogfood).

## Dependencies

- **M15 landed** (tier overlay + fallback). Scaffold's default tier can be rebound via M15 overlay.
- **M16 landed** (external workflows load path). Scaffold's output files land in `$AIW_WORKFLOWS_PATH`; without M16 they have no runtime home.
- **M11 landed** (gate-pause projection). Scaffold's review step surfaces the preview through `RunWorkflowOutput.gate_context`.

## Out of scope (explicit)

- **Prompt template engineering.** T02 deliverable. T01 uses a placeholder prompt + stub adapter to exercise the graph wiring; T02 iterates the prompt against live Claude Opus output.
- **Live-mode smoke.** T02 deliverable. T01 tests are stub-only.
- **CS300 dogfood.** T02 deliverable. T01 does not touch CS300; the handoff happens at T02 close when prompts are stable.
- **ADR-0008 + skill-install doc updates.** T03 deliverables. T01 adds a placeholder reference to ADR-0008 in module docstrings; the ADR itself is drafted at T03.
- **Multi-file scaffolding.** Per M17 non-goals.
- **Scaffold-a-primitive workflow.** Per M17 non-goals — forward option.
- **Automatic re-registration after write.** User restarts `aiw` / `aiw-mcp` after a scaffold; M16's load path picks up the new file at next startup.

## Risks

1. **Validator minimum-length floor is arbitrary.** 80 chars is a heuristic. A legitimate tiny workflow (e.g. a single `register(...)` call importing a builder from elsewhere) could trip it. Mitigation: the floor is tunable; T02's prompt work will surface whether 80 chars is too aggressive.
2. **Write-safety `is_relative_to()` semantics vary.** Python 3.9 introduced `Path.is_relative_to()`; 3.12 (our target) has it stable. Confirmed at spec time; if a future minimum-Python bump needed, re-verify.
3. **Stub-adapter script must match the scaffold's `ScaffoldedWorkflow` shape exactly.** If the schema grows a field, the stub fixtures need updating in lockstep. Mitigated by the schema being pydantic (IDE + test-time errors surface drift).
4. **Atomic write on network filesystems.** `os.replace()` is POSIX-atomic on local FS but may not be on NFS. Mitigation: local-only / solo-use posture means the target is a local FS. If a consumer ever targets NFS, the failure mode is "file is written but not atomically" — still correct at a cold-start level.
5. **Re-registration on re-run.** If the user runs the scaffold twice with the same `--target` + `--force`, the old file is replaced. The `aiw-mcp` HTTP server still has the **old** module loaded in `sys.modules` from its initial scan. First run = old version stays active; restart needed to pick up the rewrite. T01 doesn't change this; M17 non-goals document the restart expectation; a future "hot-reload" milestone could address it.
