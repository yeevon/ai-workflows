# ADR-0010 — User-owned generated code contract for scaffold_workflow

**Status:** Accepted (M17, 2026-04-30).
**Decision owner:** [M17 Task 03](../phases/milestone_17_scaffold_workflow/task_03_adr_and_docs.md).
**References:** [architecture.md §4.2 + §4.3](../architecture.md) · [KDR-004](../architecture.md#section-9) · [KDR-013](../architecture.md#section-9) · [ADR-0007](0007_user_owned_code_contract.md) · [M17 README](../phases/milestone_17_scaffold_workflow/README.md).

## Context

M17's `scaffold_workflow` generates `.py` files on the user's behalf. The workflow receives a
plain-English goal from the user, runs it through an LLM synthesis step (a `TieredNode` routing
to Claude Opus), validates the output against a schema, surfaces the generated code at a
`HumanGate` for operator review, and — on approval — writes the file to the user-supplied target
path.

From the moment a file is written to disk, it is **user-owned**. This raises a question that
ADR-0007 left open: how much does ai-workflows certify or police the *generated* code, as
opposed to merely *loaded* external modules?

Three tensions shape the decision:

1. **Validator scope.** The scaffold's paired `ValidatorNode` (required by KDR-004) can verify
   "parseable Python + `register_workflow(spec)` call shape" only, or it can also run `ruff
   check`, `pytest --collect-only`, or `import-linter`. Where does the schema check end and
   user-territory begin?
2. **Write-target safety.** The scaffold writes files at user-supplied paths. Which path
   constraints does the framework enforce (to protect the installed package and the user's
   filesystem), and which does it leave to the user?
3. **Post-write lifecycle.** After the file is written, how does the user load it, and who is
   responsible for making it work?

This ADR records the decisions across all three axes and the alternatives that were rejected.

## Decision

Four binding rules govern `scaffold_workflow`'s behaviour from validation through to post-write
handoff:

### Rule 1 — Validator scope is schema-only

The `ValidatorNode` paired with the LLM synthesis node (KDR-004) enforces exactly two
conditions:

1. `spec_python` parses as valid Python via `ast.parse()`. If parsing raises, the validator
   rejects the output and the `RetryingEdge` retries the LLM call with the error message
   rendered back into the next prompt.
2. The parsed AST contains at least one top-level `Call` node whose `func` name is
   `register_workflow`. Any call-argument form is accepted (direct literal or Name reference).

**Anything beyond these two conditions is user territory.** The framework does not run `ruff`,
`import-linter`, `pytest`, or any other quality tool on the generated artefact before handing
it to the user. The `HumanGate` that follows is a *user-review* gate — "here is what I'll write
to disk; approve to save or reject to retry with different guidance" — not an ai-workflows
certification gate.

### Rule 2 — Write-target safety rules

The write-to-disk node enforces four safety guards before writing:

1. **No writes inside `ai_workflows/`.** The target path must not resolve to a path inside the
   installed package directory (compared against `ai_workflows/__file__`'s parent). A target
   that resolves inside the package fails immediately with `TargetInsideInstalledPackageError`.
2. **Parent directory must exist and be writable.** If the parent directory does not exist or is
   not writable by the running process, the write fails with `TargetDirectoryNotWritableError`
   carrying the attempted path.
3. **Existing files require `--force`.** If the target file already exists and `--force` was not
   passed (CLI flag) / `force=False` in the MCP input, the write fails with `TargetExistsError`.
4. **Writes are atomic.** The file is written via `tempfile.mkstemp` + `os.replace` so that a
   partial write on approval cannot corrupt a previously good file. The returned `WriteOutcome`
   carries the target path and the `sha256` of the written content.

Relative paths are rejected at input-validation time (`TargetRelativePathError`). All paths are
normalised via `Path(target).expanduser().resolve()` before the guards run.

### Rule 3 — Generated code is loaded via AIW_EXTRA_WORKFLOW_MODULES (KDR-013)

Once the file is written, the user loads it using the M16 external-module load path (KDR-013):

```bash
PYTHONPATH=~/path AIW_EXTRA_WORKFLOW_MODULES=<module_stem> aiw run <workflow_name> ...
```

The module name is the file stem (no `.py` extension). ai-workflows surfaces import errors at
startup (via `ExternalWorkflowImportError` per ADR-0007) but does not lint, test, or sandbox
the user-owned module. The framework's hands-off posture for external modules (ADR-0007) applies
to scaffold-generated modules without exception.

### Rule 4 — No auto-registration

After the scaffold writes a file, the user must **restart `aiw` or `aiw-mcp`** (or explicitly
add the module to `AIW_EXTRA_WORKFLOW_MODULES` before the next process start) to pick up the
new workflow. The scaffold does not trigger a hot-reload, does not modify the running registry,
and does not mutate the caller's environment. The user controls the load lifecycle.

## Rejected alternatives

### Lint the generated code before handing it over

Running `ruff check`, `import-linter`, or `pytest --collect-only` on the generated `.py` file
before surfacing it at the `HumanGate` would add a feedback loop on code quality.

**Rejected** for three reasons:

- **Latency + false confidence.** A generated file that passes `ruff` syntactic checks can
  still fail at import time or produce wrong LLM results at runtime. Lint-before-handover adds
  latency (potentially significant for a large generated file) while providing a false-security
  surface: "passed lint" does not mean "correct".
- **Framework-vs-user ownership inversion.** ai-workflows has no way to know which `ruff` rules
  the user expects, what `import-linter` contracts their project enforces, or what `pytest`
  fixtures their test suite needs. Imposing the framework's own lint config on user code would
  invert the KDR-013 ownership boundary — the framework would be opinionated about user project
  layout and coding standards.
- **Alignment with threat model.** ai-workflows is single-user, local-machine, MIT-licensed.
  The operator supplies both the framework and the generated code. There is no untrusted-code
  hygiene concern to address with a lint gate.

**Re-opens if:** a consumer surfaces a concrete regression class that a lint gate would
reliably catch and that the user consistently overlooks at gate-review time. Has not surfaced.

### Sandbox the scaffold runtime

Execute the scaffold-generated code in a restricted Python context (e.g. `restrictedpython`, a
subprocess, or a Pyodide runtime) at review time to verify it imports cleanly.

**Rejected** for the same reasons as ADR-0007's sandboxing rejection:

- ai-workflows is a local-only solo-use tool. There is no trust boundary between the operator
  and the generated code — both are the same person. Sandboxing imposes engineering cost for a
  threat model that does not apply.
- Sandbox isolation would break legitimate workflow code that accesses the filesystem for
  reference materials, spawns subprocesses for Claude Code tier calls, or uses LiteLLM imports
  that rely on the full Python environment.
- The right safety model for generated code at this deployment tier is: human reviews the
  `HumanGate` preview; human approves or rejects; human owns the outcome.

**Re-opens if:** multi-tenant hosting becomes a concern (not on any current roadmap).

### Keep generated code inside the package

Write the generated `.py` file into `ai_workflows/workflows/` so it is auto-discovered at
startup without any `AIW_EXTRA_WORKFLOW_MODULES` configuration.

**Rejected** because it directly contradicts KDR-013 (user-owned external workflow code) and
the write-safety Rule 2 above. Generated code is user-owned by construction — it is the output
of a user-initiated, user-reviewed scaffolding run. Placing it inside the framework package
would:

- Commingle user code with package source under source control (or in the installed wheel).
- Make the scaffold modify the installed package at runtime, which is fragile (the package may
  be read-only, managed by `uv`, or installed in a shared environment).
- Obscure the KDR-013 ownership boundary by making user code look like framework code.

**Re-opens if:** a specific deployment context (e.g. a self-contained appliance with no
writeable home directory) requires bundling generated code in the wheel. Not a current case.

## Consequences

- **Users must verify generated code quality themselves.** The scaffold's `HumanGate` surfaces
  the full `spec_python` for review; approval is the user's acceptance of the code. Scaffold
  prompt engineering (T02) is the primary quality lever — a well-engineered prompt produces
  well-structured, runnable `WorkflowSpec` + `register_workflow(spec)` files consistently.
- **Import errors surface at startup, not at scaffold time.** If a generated module fails to
  import (e.g. it references a tier name that does not exist in `AIW_EXTRA_WORKFLOW_MODULES`),
  the error appears when the user next starts `aiw` or `aiw-mcp`, not at scaffold write time.
  This is consistent with ADR-0007's `ExternalWorkflowImportError` behaviour.
- **The `HumanGate` is a review gate, not a certification gate.** Downstream documentation and
  the gate prompt itself must be clear: ai-workflows is showing the user what it will write,
  not certifying that the code is correct. The user is the reviewer and approver.
- **Risk-ownership boundary is explicit and mirrors M16.** This ADR's four-rule framing extends
  ADR-0007's hands-off posture to the generated-code lifecycle, making the boundary clear for
  future questions of the form "should the scaffold do more checking?" — the answer is no
  unless a new milestone changes the posture.
- **Atomic writes protect previously-good files.** Even if the user approves a generated file
  that later fails to import, the `mkstemp` + `os.replace` atomic write ensures that any
  previously-written file at the same path is not corrupted by a partial write.

## Related

- **KDR-004** (validator pairing) — the scaffold's `ValidatorNode` is required by KDR-004.
  This ADR defines what the validator may and may not check.
- **KDR-013** (user-owned external workflow code) — the hands-off posture this ADR extends to
  generated code. The load path (`AIW_EXTRA_WORKFLOW_MODULES`) is the M16 path KDR-013 defines.
- **ADR-0007** (user-owned code contract for external workflow modules) — the M16 ADR this
  extends. ADR-0007 covers loading of user-authored modules; this ADR covers the scaffold's
  *generation* of those modules and the write-safety rules that precede the load step.
