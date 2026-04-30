# Task 01 — `scaffold_workflow` graph + validator + write-safety + CLI/MCP wiring

**Status:** ✅ Built (cycle 1, 2026-04-30).
**Grounding:** [milestone README](README.md) · [ai_workflows/workflows/summarize.py](../../../ai_workflows/workflows/summarize.py) (canonical WorkflowSpec-based workflow to mirror) · [ai_workflows/workflows/spec.py:329-404](../../../ai_workflows/workflows/spec.py#L329-L404) (`WorkflowSpec` + `register_workflow` — scaffold outputs code that calls this) · [ai_workflows/workflows/__init__.py:54-110](../../../ai_workflows/workflows/__init__.py#L54-L110) (`register_workflow` primary entry point; `register` = Tier-4 escape hatch) · [M11 README](../milestone_11_gate_review/README.md) (gate-pause projection — scaffold surfaces code preview here) · [M16 task_01](../milestone_16_external_workflows/task_01_external_load_path.md) (load-path the scaffold's output rides on; env-var is `AIW_EXTRA_WORKFLOW_MODULES`).

## What to Build

The end-to-end `scaffold_workflow` `StateGraph`: input handling, LLM synthesis node (`TieredNode` routing to Claude Opus by default; per-call rebind via `--tier-override` / `tier_overrides` per KDR-014), schema-validator node (`ValidatorNode` enforcing parseable Python + `register_workflow(spec)` shape — post-M19 declarative authoring surface), `HumanGate` surfacing the code preview, atomic write-to-disk node. Plus the CLI command, the MCP tool parameters, and the stub-adapter-driven hermetic tests.

The scaffold generates a `.py` file that defines a `WorkflowSpec` and calls `register_workflow(spec)` — the framework's primary post-M19 authoring entry point. The user never has to touch `StateGraph`, `TieredNode`, or `ValidatorNode` directly. Prompt engineering iteration lands in T02; ADR + doc updates land in T03.

## Deliverables

### 1. New module `ai_workflows/workflows/scaffold_workflow.py`

Mirrors the shape of `planner.py`. Contains:

- `ScaffoldWorkflowInput` pydantic model: `goal: str`, `target_path: Path`, `force: bool = False`, `existing_workflow_context: str | None = None` (optional — user can hint at an existing workflow's shape to mimic). `tier_preferences` was dropped: per KDR-014 quality knobs live in module constants; use `--tier-override` / `tier_overrides` for per-call rebinding.
- `ScaffoldedWorkflow` pydantic model (the LLM output schema): `name: str`, `spec_python: str`, `description: str`, `reasoning: str`. `spec_python` is the full content of the generated `.py` file — a `WorkflowSpec` definition + `register_workflow(spec)` call. `declared_tiers`/`requires_human_gate` dropped: the `WorkflowSpec` carries its own `tiers` dict; the generated code is always reviewed at the gate.
- `build_scaffold_workflow()` factory that returns a compiled `StateGraph`.
- `scaffold_workflow_tier_registry()` helper — declares a single `scaffold-synth` tier routing to `ClaudeCodeRoute(cli_model_flag="opus")` with sensible concurrency/timeout defaults (match `planner-synth`: `max_concurrency=1`, `per_call_timeout_s=300`). **The function name `scaffold_workflow_tier_registry` is load-bearing** — `_dispatch._resolve_tier_registry()` looks up `<workflow_name>_tier_registry()` by convention; renaming it breaks dispatch silently.
- Module-top `register("scaffold_workflow", build_scaffold_workflow)` call, per the existing imperative convention. (The scaffold *itself* uses the Tier-4 `register()` path; the code *it generates* uses `register_workflow(spec)` — the primary declarative path.)

Graph shape (minimum):

```
[validate_input]       # pydantic parse + target_path safety guards
      │
      ▼
[synthesize_source]    # TieredNode, tier=scaffold-synth, output=ScaffoldedWorkflow
      │
      ▼
[validate_output]      # ValidatorNode — ast.parse + register_workflow() AST walk
      │                  (on failure, loops back to synthesize_source up to retry budget)
      ▼
[preview_gate]         # HumanGate — gate_id="scaffold_review"; surfaces spec_python + summary
      │                  (resume with gate_response="approved" → proceed; gate_response="rejected" → abort)
      ▼
[write_to_disk]        # atomic write of spec_python to target_path
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

    Uses `tempfile.NamedTemporaryFile(dir=target.parent)` to guarantee
    same-filesystem placement (required for `os.replace` atomicity on
    POSIX), then `os.replace()` to swap. Ensures a partial write cannot
    corrupt a previous good file on crash.
    """
```

Package-root detection: compare `target.resolve()` against `Path(ai_workflows.__file__).parent.resolve()` (and all its ancestors up to site-packages) using `.is_relative_to()`.

### 3. Validator module `ai_workflows/workflows/_scaffold_validator.py`

```python
class ScaffoldOutputValidationError(ValueError):
    """Raised when ScaffoldedWorkflow output fails schema checks."""

def validate_scaffold_output(output: ScaffoldedWorkflow) -> None:
    """Raise if output is not a valid scaffolded workflow spec.

    Checks:
      1. spec_python parses via ast.parse() (syntax-valid).
      2. The AST contains at least one top-level Call node whose
         func name is "register_workflow".  The argument may be a
         Name reference (e.g. register_workflow(_SPEC)) or a direct
         Call/constant — any form is accepted; the validator does not
         resolve bindings.
      3. The spec_python length is non-trivial (>= 80 chars —
         catches empty / placeholder emits; tune at T02 post-smoke).
    """
```

Returns `None` on success; raises `ScaffoldOutputValidationError` with a descriptive message on failure. The `ValidatorNode` wraps this and triggers `RetryingEdge` on failure per KDR-006.

**Why `register_workflow`, not `register`:** the scaffold targets the post-M19 declarative authoring surface. `register_workflow(spec)` is the primary entry point; `register(name, build_fn)` is the Tier-4 escape hatch not surfaced to generated code.

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

No new MCP tool. The existing `run_workflow(workflow="scaffold_workflow", input={...})` surface covers it — `ScaffoldWorkflowInput` is just another workflow-input schema. The gate-pause projection (M11) surfaces the code preview in `gate_context`. `resume_run(run_id=..., gate_response="approved")` completes the write; `gate_response="rejected"` aborts without writing. (`gate_response: Literal["approved", "rejected"]` — verified `ai_workflows/mcp/schemas.py:182`.)

T01 adds one MCP test asserting the scaffold round-trips correctly via `fastmcp.Client` over HTTP (mirrors the M14 pattern). The test uses the stub adapter to script the LLM output.

### 6. Tests — `tests/workflows/test_scaffold_workflow.py` (new)

Hermetic. Uses stub adapter + tmp_path + pytest fixtures. No live LLM.

**Validator tests** (test the `_scaffold_validator.py` surface directly):

- `test_validator_accepts_well_formed_output` — a hand-written `ScaffoldedWorkflow` with a valid `WorkflowSpec` definition + `register_workflow(_SPEC)` call; assert no raise.
- `test_validator_accepts_register_workflow_with_name_reference` — `register_workflow(MY_SPEC)` where `MY_SPEC` is a module-level name; assert no raise (validator does not resolve bindings — any `register_workflow(...)` call shape passes).
- `test_validator_rejects_syntactically_invalid_python` — `spec_python` with `def =` (parse error); assert raises.
- `test_validator_rejects_missing_register_workflow_call` — valid Python but no `register_workflow(...)` call; raises.
- `test_validator_rejects_trivially_short_source` — 20-character string that parses but is too short; raises (minimum-length floor at T01 = 80 chars; tune at T02).

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

- `test_scaffold_end_to_end_with_stub_adapter` — stub LLM emits a valid `ScaffoldedWorkflow` (with `spec_python` containing a `WorkflowSpec` + `register_workflow` call); validator passes; gate triggers; resume with `gate_response="approved"`; file is written to tmp_path; SHA256 matches expected; the written file's `spec_python` round-trips through `ast.parse()` cleanly.
- `test_scaffold_validator_retry_on_bad_output` — stub emits invalid `spec_python` on first attempt (missing `register_workflow`), valid on second; assert `RetryingEdge` drives the second attempt; file writes successfully.
- `test_scaffold_gate_rejection_aborts_without_write` — stub emits valid output; gate rejects (`resume_run(..., gate_response="rejected")`); tmp_path has no new file.
- `test_scaffold_write_failure_after_approve_surfaces_error` — stub emits valid output; gate approves; the write-safety guard trips (e.g. target-inside-package); assert structured error surfaces through the workflow.

**MCP HTTP parity test** — new `tests/mcp/test_scaffold_workflow_http.py` (renamed from `test_http_scaffold_workflow.py` to avoid collision with existing `tests/mcp/test_scaffold.py` — M4 server bringup fixture):

- `test_scaffold_round_trips_over_http` — spin the HTTP server with a stubbed scaffold tier; `run_workflow(workflow="scaffold_workflow", input=...)` + `resume_run(..., gate_response="approved")`; assert the written file matches expectations. Mirrors M14's HTTP-parity test pattern.

### 7. Stub adapter harness for scaffold tests

`tests/workflows/conftest.py` (or similar) gains a `scaffold_stub_adapter` fixture that scripts LLM output for the scaffold's tier. Uses the existing `StubLLMAdapter` pattern from `ai_workflows/evals/_stub_adapter.py` — no new test harness.

### 8. Module docstrings

- `scaffold_workflow.py` — cites M17 T01, the sibling workflows (planner, slice_refactor, summarize) as reference, the relationship to M16 external load path (`AIW_EXTRA_WORKFLOW_MODULES`), and the M19 declarative authoring surface (`WorkflowSpec` / `register_workflow`).
- `_scaffold_write_safety.py` — cites M17 T01 + ADR-0010 (the risk-ownership decision the safety guards enforce; ADR drafted at T03).
- `_scaffold_validator.py` — cites M17 T01 + ADR-0010 + the explicit non-goal of linting/testing user code.

### 9. CHANGELOG entry

Under `[Unreleased]` on `design_branch` — new `### Added — M17 Task 01: scaffold_workflow meta-workflow graph + validator + write safety (YYYY-MM-DD)` entry. Names the new modules, the ACs covered, the tier-default, the MCP surface, and the ADR-0010 placeholder (filled at T03). Promotion to `main` happens at milestone close-out (T04 scope).

## Acceptance Criteria

- [ ] **AC-1: `scaffold_workflow` registered.** The module-top `register("scaffold_workflow", build_scaffold_workflow)` call fires on import. Verified by `python -c "from ai_workflows.workflows import list_workflows; assert 'scaffold_workflow' in list_workflows()"`.
- [ ] **AC-2: `ScaffoldWorkflowInput` + `ScaffoldedWorkflow` pydantic models** exist with the fields named above (`spec_python: str` not `source_python`; no `tier_preferences`, no `declared_tiers`, no `requires_human_gate`). Schema validation is strict (extra fields forbidden; types enforced).
- [ ] **AC-3: Validator enforces parseable Python + `register_workflow()` shape.** `_scaffold_validator.py` runs `ast.parse()` + walks the AST. Five validator tests pass (three reject cases + two accept cases including the Name-reference form).
- [ ] **AC-4: Write-safety guards enforced.** Eight write-safety tests pass covering every rejection class + the atomic-write contract.
- [ ] **AC-5: `HumanGate` preview carries the spec + target path.** Gate's `gate_context` (per M11) includes `spec_python`, `target_path`, and a short summary. The HTTP parity test asserts the preview survives transport.
- [ ] **AC-6: Atomic write on gate approval.** On `resume_run(..., gate_response="approved")`, the file is written via `os.replace()` from a temp file in the same directory. SHA256 of the written bytes matches the scaffold's output.
- [ ] **AC-7: CLI alias `aiw run-scaffold`.** The Typer alias is registered; `--goal` + `--target` + `--force` + `--tier-override` flags work. Routes through the generic `run_workflow` dispatch under the hood.
- [ ] **AC-8: MCP surface unchanged externally.** `run_workflow(workflow="scaffold_workflow", input=...)` works over stdio + HTTP. No new MCP tool; no schema drift.
- [ ] **AC-9: Tier registry declared.** `scaffold_workflow_tier_registry()` exists and declares `scaffold-synth` routing to Claude Opus via `ClaudeCodeRoute(cli_model_flag="opus")`. The function name is load-bearing (resolved by `_dispatch._resolve_tier_registry()` via `<workflow_name>_tier_registry()` convention). Per-call rebind via `--tier-override scaffold-synth=<replacement>` / `tier_overrides={"scaffold-synth": "<replacement>"}` per KDR-014.
- [ ] **AC-10: Retry + abort semantics.** On validator failure, `RetryingEdge` drives a second attempt with the validator's error re-rendered into the next prompt (T02 scope for the prompt engineering; T01 scope for the retry wiring). On gate rejection (`gate_response="rejected"`), the run terminates with `status="rejected"` and no file is written.
- [ ] **AC-11: Hermetic tests land green.** `tests/workflows/test_scaffold_workflow.py` — all integration + validator + write-safety tests pass. `tests/mcp/test_scaffold_workflow_http.py` — HTTP round-trip passes.
- [ ] **AC-12: Four-layer contract preserved.** `uv run lint-imports` reports 4 kept, 0 broken. Scaffold lives in `workflows/` layer; write-safety + validator modules sit alongside.
- [ ] **AC-13: KDR-004 compliance.** The LLM synthesis node is paired with a validator node immediately downstream. The gate node is not a validator (it's a human-review step, not a schema check). Confirmed by reading the graph wiring.
- [ ] **AC-14: KDR-003 compliance.** No `anthropic` SDK import. No `ANTHROPIC_API_KEY` env-var lookup. Claude access is via `ClaudeCodeSubprocess` only.
- [ ] **AC-15: Gates green.** `uv run pytest` + `uv run lint-imports` + `uv run ruff check`.
- [ ] **AC-16: Module docstrings land** per the spec above.
- [ ] **AC-17: CHANGELOG entry** under `[Unreleased]` on `design_branch`. Names files touched, ACs satisfied, T02 follow-up scope (prompt iteration + live-mode smoke + CS300 dogfood). Promotion to `main` at T04 close-out.

## Dependencies

- **M16 landed** (external workflows load path, shipped 2026-04-24). Scaffold's output files are loaded via `AIW_EXTRA_WORKFLOW_MODULES` (dotted module path); without M16 they have no runtime home.
- **M11 landed** (gate-pause projection). Scaffold's review step surfaces the preview through `RunWorkflowOutput.gate_context`.
- **M15 deferred** (tier fallback chains, rescoped 2026-04-30). Not a hard M17 dependency. Scaffold tier is rebindable per-call via `--tier-override` / `tier_overrides` per KDR-014; M15's `TierConfig.fallback` chains will compose with M17 once M15 ships.

## Out of scope (explicit)

- **Prompt template engineering.** T02 deliverable. T01 uses a placeholder prompt + stub adapter to exercise the graph wiring; T02 iterates the prompt against live Claude Opus output.
- **Live-mode smoke.** T02 deliverable. T01 tests are stub-only.
- **CS300 dogfood.** T02 deliverable. T01 does not touch CS300; the handoff happens at T02 close when prompts are stable.
- **ADR-0010 + skill-install doc updates.** T03 deliverables. T01 adds a placeholder reference to ADR-0010 in module docstrings; the ADR itself is drafted at T03.
- **Multi-file scaffolding.** Per M17 non-goals.
- **Scaffold-a-primitive workflow.** Per M17 non-goals — forward option.
- **Automatic re-registration after write.** User restarts `aiw` / `aiw-mcp` after a scaffold; M16's load path picks up the new file at next startup.

## Risks

1. **Validator minimum-length floor is arbitrary.** 80 chars is a heuristic. A legitimate tiny workflow (e.g. a single `register_workflow(SPEC)` call importing the spec from elsewhere) could trip it. Mitigation: the floor is tunable; T02's prompt work will surface whether 80 chars is too aggressive.
2. **Write-safety `is_relative_to()` semantics vary.** Python 3.9 introduced `Path.is_relative_to()`; 3.12 (our target) has it stable. Confirmed at spec time; if a future minimum-Python bump needed, re-verify.
3. **Stub-adapter script must match the scaffold's `ScaffoldedWorkflow` shape exactly.** If the schema grows a field, the stub fixtures need updating in lockstep. Mitigated by the schema being pydantic (IDE + test-time errors surface drift).
4. **Atomic write on network filesystems.** `os.replace()` is POSIX-atomic on local FS but may not be on NFS. Mitigation: local-only / solo-use posture means the target is a local FS. If a consumer ever targets NFS, the failure mode is "file is written but not atomically" — still correct at a cold-start level.
5. **Re-registration on re-run.** If the user runs the scaffold twice with the same `--target` + `--force`, the old file is replaced. The `aiw-mcp` HTTP server still has the **old** module loaded in `sys.modules` from its initial scan. First run = old version stays active; restart needed to pick up the rewrite. T01 doesn't change this; M17 non-goals document the restart expectation; a future "hot-reload" milestone could address it.
6. **Gate rejection is terminal for the run.** `gate_response="rejected"` terminates the run with `status="rejected"` and no file is written. Users iterate by invoking `aiw run scaffold_workflow` again with a fresh `run_id` + revised `--goal`. The scaffold does not store rejected attempts for later review.

## Carry-over to T02

- **Validator minimum-length floor retune.** The 80-char floor (Risk #1) and `test_validator_rejects_trivially_short_source` fixture must retune together if T02's prompt iteration changes the realistic minimum. If the floor changes, both the constant and the test fixture move in lockstep.
