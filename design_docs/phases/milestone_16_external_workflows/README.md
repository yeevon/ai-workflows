# Milestone 16 — External Workflow Module Discovery

**Status:** 📝 Planned (revised 2026-04-24 — narrowed from the original 4-task `AIW_WORKFLOWS_PATH` directory-scan shape to a single-task dotted-module loader at CS-300's explicit request).
**Grounding:** [architecture.md §3 + §4.2](../../architecture.md) · [roadmap.md](../../roadmap.md) · [analysis/post_0.1.2_audit_disposition.md](../../analysis/post_0.1.2_audit_disposition.md) · [ai_workflows/workflows/__init__.py](../../../ai_workflows/workflows/__init__.py) (the `register(name, builder)` API + module-level `_REGISTRY`) · [ai_workflows/workflows/_dispatch.py:202-217](../../../ai_workflows/workflows/_dispatch.py#L202-L217) (`_import_workflow_module` — the dispatch-side import site) · CS-300 feature request filed 2026-04-24 (see §"Why this milestone exists" below).

## Why this milestone exists

CS-300 (the first downstream consumer of `jmdl-ai-workflows==0.1.3` over the MCP HTTP transport) filed a feature request on 2026-04-24 that amounts to: *"I have a workflow module at `cs300.workflows.question_gen`; how do I get `aiw` and `aiw-mcp` to discover it without forking the wheel?"*

Today the registry is closed at the package level. [`_dispatch._import_workflow_module`](../../../ai_workflows/workflows/_dispatch.py#L202-L217) hardcodes `importlib.import_module(f"ai_workflows.workflows.{workflow}")`, so the only workflows `aiw run <name>` can find are the ones shipped in-package. A downstream consumer's options today are all bad:

- Fork `jmdl-ai-workflows` and drop the workflow into the source tree (loses upstream sync; ships domain-specific code in the wheel).
- Monkey-patch `_dispatch._import_workflow_module` at runtime (fragile; breaks on every upstream rename).
- Publish the consumer's own code as a pip-installable package (overkill for a single-machine course-notes repo; the CS-300 case).

M16 closes this gap with the **minimum viable extension surface**:

- An env var `AIW_EXTRA_WORKFLOW_MODULES` listing **dotted Python module paths** (comma-separated).
- A repeatable `--workflow-module <dotted>` CLI flag on both `aiw` and `aiw-mcp`.
- A startup-time loader that `importlib.import_module(...)`s each entry — the user's `register(...)` call at module top level fires as a side effect, populating the existing registry.

The consumer puts their package on `PYTHONPATH` (or installs it normally via `uv pip install -e .`) and names the module dotted-path-style, matching every other Python extension mechanism. No directory scanning, no `spec_from_file_location`, no namespace collision games — just standard Python imports.

### Why dotted paths (not directory scan)

The original M16 draft (2026-04-23) proposed `AIW_WORKFLOWS_PATH` directory-scan semantics via `importlib.util.spec_from_file_location`. CS-300's ask narrowed the scope for three concrete reasons, all adopted here:

1. **Namespace-collision games disappear.** `cs300.workflows.question_gen` is its own module in `sys.modules`; there is no "two `foo.py` files in different directories" problem to solve.
2. **Editable installs are the idiomatic dev loop.** `uv pip install -e ./cs300` + `AIW_EXTRA_WORKFLOW_MODULES=cs300.workflows.question_gen` beats symlinking `.py` files into a scanned directory. Entry points remain a clean future layer on top (explicitly deferred below).
3. **CS-300's consumer repo already has a package.** Directory-scan would force CS-300 to invent a second "loose `.py` file" authoring path alongside their real package layout.

User-supplied primitives, `aiw inspect`, and `aiw list-workflows` extension are **out of scope** for M16 and deferred — see §Non-goals.

## What M16 ships

1. **`ai_workflows/workflows/loader.py`** — new module. Public `load_extra_workflow_modules(*, cli_modules=None) -> list[str]`. Imports each named module once; raises `ExternalWorkflowImportError` (`ImportError` subclass) on failure. Source order: env-var entries first, then CLI entries appended (CLI can extend / re-attempt an env-var baseline).
2. **`AIW_EXTRA_WORKFLOW_MODULES` env var.** Comma-separated dotted module paths. Unset / empty = no extra load. Whitespace around entries is trimmed. Empty entries (e.g. trailing comma) are skipped silently.
3. **`--workflow-module <dotted>` CLI flag**, repeatable, on both `aiw` and `aiw-mcp`. Composes with the env var — env imports first, CLI entries appended after.
4. **Dispatch routing extension** ([`_dispatch._import_workflow_module`](../../../ai_workflows/workflows/_dispatch.py#L202-L217)). Check `workflows._REGISTRY` **before** attempting `ai_workflows.workflows.<name>` import — if the name is already registered (because the external loader pre-imported the module at startup), return the builder's module via `sys.modules[builder.__module__]`. In-package workflows keep their lazy-import fallback unchanged. The `<workflow>_tier_registry()` helper pattern (M3 T03) works identically for external modules — they expose the same helper on their own module.
5. **Idempotence.** A module imported once stays in `sys.modules`; a second call to `load_extra_workflow_modules()` in the same process is a no-op for already-loaded entries (Python's import machinery guarantees this; the existing `register()` handles the re-registration case). This matters for test harnesses (`pytest.MonkeyPatch.setenv` + repeated `CliRunner.invoke`).
6. **Startup-atomicity.** If any entry fails to import, `ExternalWorkflowImportError` is raised **after** any earlier entries' side effects have already landed in `sys.modules`. Python's import system does not roll back on partial failure. We document this under "Failure mode" rather than try to fake atomicity — a failure at entry *k* means entries *0..k-1* already executed their top-level `register()` calls. In practice this is the same semantic Python itself guarantees for `from pkg import a, b, c` with a broken `b`.
7. **KDR-013 added to architecture.md §9.** *"External workflows discover via `AIW_EXTRA_WORKFLOW_MODULES` and `--workflow-module` (dotted Python module paths, not filesystem paths). Loading uses `importlib.import_module`; user modules are expected to call the package's `register()` helper at module top level. Entry-point discovery (PEP 621) is deferred to a future milestone triggered by users wanting to pip-publish distributable workflow packages. User code is owned by the user — ai-workflows does not lint, test, or sandbox it."* Composes over KDR-002 (CLI/MCP surface parity).
8. **ADR-0007 added under `design_docs/adr/0007_user_owned_code_contract.md`.** Records the dotted-path-over-directory-scan decision, the risk-ownership boundary (user owns imported code; framework surfaces `ExternalWorkflowImportError` but does not police), and the rejected alternatives (entry-point-only, directory scan, full plugin protocol, sandboxing).
9. **`docs/writing-a-workflow.md`** gains a new **§External workflows from a downstream consumer** section with the env-var + CLI-flag surfaces and a worked example (the CS-300 shape).
10. **Root `README.md` `## MCP server` section** gains a one-line pointer to the external-workflow docs.

## Goal

A downstream consumer publishes (or editable-installs) their own Python package and runs their workflow through the same `aiw` / `aiw-mcp` surface the shipped workflows use:

```bash
# Downstream consumer's package layout at ./cs300/:
#   cs300/workflows/question_gen.py  ← calls register("question_gen", build_question_gen)
uv pip install -e .

# Register via env var:
AIW_EXTRA_WORKFLOW_MODULES=cs300.workflows.question_gen \
  aiw run question_gen --goal 'write 10 questions about KDR-003' --run-id qg-1

# Or via MCP HTTP transport (CS-300's actual shape):
AIW_EXTRA_WORKFLOW_MODULES=cs300.workflows.question_gen,cs300.workflows.grade \
  uvx --from jmdl-ai-workflows aiw-mcp \
    --transport http --port 8080 --cors-origin http://localhost:4321

# Or via CLI flag (no env var needed):
aiw --workflow-module cs300.workflows.question_gen run question_gen --goal '...'
```

M11's gate-pause projection and M14's HTTP transport both apply unchanged.

## Exit criteria

1. **`AIW_EXTRA_WORKFLOW_MODULES` env var is honoured.** Unset / empty string = no import. Comma-separated list = each entry imported in order. Whitespace around entries is trimmed; empty entries from trailing commas are skipped silently.
2. **`--workflow-module` CLI flag** is accepted on both `aiw` (root-level callback option, repeatable) and `aiw-mcp` (root-level Typer option, repeatable). Entries compose with the env var: env first, CLI appended.
3. **Import mechanism.** `importlib.import_module(dotted_path)`. No filesystem paths, no `spec_from_file_location`. Modules must already be importable via the running interpreter's `sys.path` (typical: user `uv pip install -e .` or `pip install`s their package).
4. **Failure surfacing.** A module that fails to import raises `ExternalWorkflowImportError` (an `ImportError` subclass) naming the dotted path + the chained underlying cause. Startup aborts — subsequent entries are **not** attempted after the first failure. Earlier successful imports have already executed their `register()` side effects in `sys.modules` (Python import semantics); this is documented, not fought.
5. **Registration failure is non-fatal at startup.** A module that imports cleanly but does not call `register(...)` is accepted silently (it may be a utility module shared by two workflow modules). `aiw run <missing>` then surfaces the existing "workflow 'X' not registered; known: [...]" error from `_dispatch` — no special-casing.
6. **Name collision handling.** A module calling `register(name, ...)` where `name` already exists in `_REGISTRY` raises from the existing `register()` check in `ai_workflows/workflows/__init__.py:58-76` (`ValueError` with a list of known workflows). The existing collision semantic is preserved — M16 does not weaken it. In-package workflows register lazily on first dispatch; external workflows load at startup; an external module that shadows `planner` hits the collision check the moment dispatch touches `planner` (or vice versa, depending on load order). Either ordering produces a loud error with both sources named.
7. **Idempotent re-load.** Calling `load_extra_workflow_modules()` twice in the same Python process is a no-op for already-imported modules. `register()`'s identical-re-registration path (`existing is builder → return`) handles the workflow-registry side; Python's `sys.modules` cache handles the import side.
8. **Dispatch routing extension.** [`_dispatch._import_workflow_module`](../../../ai_workflows/workflows/_dispatch.py#L202-L217) is extended to consult `workflows._REGISTRY` **before** attempting the in-package import. If the workflow name is already registered, return `sys.modules[builder.__module__]` so `_resolve_tier_registry(workflow, module)` can find the `<workflow>_tier_registry()` helper on the external module. The lazy-import fallback for in-package workflows is preserved unchanged.
9. **MCP surface parity.** `run_workflow(workflow_id="question_gen", ...)` over both stdio and HTTP transports succeeds for an external workflow registered via `AIW_EXTRA_WORKFLOW_MODULES` at server startup. No MCP schema change; the extension is invisible at the wire layer.
10. **Hermetic tests.** New `tests/workflows/test_external_module_loader.py` — six tests for the loader (env-only, CLI-only, env+CLI compose, invalid module, registry untouched-on-failure, idempotent re-load). New `tests/cli/test_external_workflow.py` — one round-trip test for `aiw run <external>`. New `tests/mcp/test_external_workflow.py` — round-trip tests for `run_workflow` over both stdio and HTTP transports. All tests hermetic: a stub workflow registered from `tmp_path` via `sys.path` manipulation, no provider calls.
11. **KDR-013 in architecture.md §9.** Full text drafted in this task.
12. **ADR-0007 under `design_docs/adr/0007_user_owned_code_contract.md`.** Records the deferral decision + risk-ownership framing.
13. **Documentation.** `docs/writing-a-workflow.md` gains §External workflows from a downstream consumer with the env-var and CLI-flag surfaces + a worked example. Root `README.md` `## MCP server` section gains a one-line pointer.
14. **Gates green on both branches.** `uv run pytest` + `uv run lint-imports` (4 kept — no new layer; loader lives in the workflows layer) + `uv run ruff check`.
15. **CHANGELOG entry.** Under `[Unreleased]` on both branches — new `### Added — M16 Task 01: external workflow module discovery (YYYY-MM-DD)` entry.

## Non-goals

- **No `AIW_WORKFLOWS_PATH` directory-scan loader.** Rejected in favour of dotted-path imports after CS-300 filed the feature request with dotted paths as the explicit shape. Directory scan is not on any roadmap; the need would have to resurface with a concrete forcing function before it re-opens.
- **No `AIW_PRIMITIVES_PATH`.** Deferred. No concrete user case today — CS-300 needs workflow registration, not primitive registration. Re-opens when a consumer asks.
- **No entry-point discovery (PEP 621 `[project.entry-points."ai_workflows.workflows"]`).** Deferred to a future milestone triggered by a consumer wanting to pip-publish a distributable workflow package. Entry points compose fine on top of the dotted-path loader; M16's choice is just about which one lands first.
- **No `aiw inspect <workflow>` command.** Deferred to a separate milestone (discoverability polish). CS-300's flow does not need it.
- **No extension of `aiw list-workflows`** to flag external workflows with their source. The registry already includes them once loaded; the existing surface does not distinguish sources and does not need to for CS-300.
- **No programmatic-import logging default** in `ai_workflows/__init__.py`. Library-style imports outside the CLI/MCP entries are not in CS-300's flow; a consumer hitting that path can call `configure_logging()` themselves. Deferred pending a concrete forcing function.
- **No sandboxing of user code.** User modules execute with full process privileges as part of the same Python process. This is consistent with the project's local-only solo-use posture (see `project_local_only_deployment.md` memory). Revisit when multi-tenant hosting becomes a concern — not a CS-300 case.
- **No linting of user code.** `uv run ruff check` and `uv run lint-imports` stay pointed at the package source only. User code is user-owned; the framework does not police style or layer compliance. Documentation makes this boundary explicit (ADR-0007).
- **No hot-reload.** `aiw-mcp --transport http` running as a long-lived server loads extra modules once at startup; new files in the consumer's package are not picked up without a server restart. Hot-reload is a future concern triggered by a real user asking for it.
- **No MCP tool for uploading workflow source.** The MCP surface does not gain a "write user workflow to disk" tool. M17's future scaffold-workflow deliberation is a separate surface, not M16's.
- **No change to `register()` semantics.** The existing in-package convention (`register(name, builder)` called at module top level; identical re-registration is a no-op; mismatched re-registration raises `ValueError`) is preserved. External modules use the same API; no "external-only" registration helper.
- **No Anthropic API (KDR-003).** No new provider call. External load is a dispatch-layer concern — it never touches the LLM adapters.

## Key decisions in effect

| Decision | Reference |
|---|---|
| Dotted-path imports over directory scan (consumer-idiomatic; no namespace games) | M16 "Why" + ADR-0007 |
| User code is user-owned; framework surfaces errors but does not police | ADR-0007 + KDR-013 |
| In-package workflows cannot be shadowed by external ones (existing `register()` collision check) | KDR-013 |
| Dispatch checks registry before attempting in-package import | [`_dispatch._import_workflow_module`](../../../ai_workflows/workflows/_dispatch.py#L202-L217) extension |
| MCP surface parity — external workflows are first-class via `run_workflow` | KDR-002 preserved |
| Four-layer import contract preserved — `import-linter` unchanged | architecture.md §3 |
| No new Anthropic / provider surface | KDR-003 |

## Task order

| # | Task | Kind |
|---|---|---|
| 01 | [`AIW_EXTRA_WORKFLOW_MODULES` loader + `--workflow-module` flag + dispatch-registry routing + KDR-013 + ADR-0007 + docs + tests](task_01_external_workflow_modules.md) | code + test + doc |

Single-task milestone. Previous 4-task shape (`AIW_WORKFLOWS_PATH`, `aiw inspect`, doc-only task, close-out) collapsed into one at the CS-300 narrow-scope review (2026-04-24).

## Dependencies

- **M13 (v0.1.0 release) — precondition.** Landed 2026-04-22 → 2026-04-23 through 0.1.3. The extension surface ships on top of the published package.
- **M14 (MCP HTTP transport) — composes over.** External workflows invoke identically over stdio + HTTP.
- **M15 (tier overlay) — not a precondition.** Original M16 draft called M15 a precondition; the narrowed M16 scope does not introduce any tier-configuration surface, so M15 and M16 are independent. Either can ship first. M15 currently has no forcing function (CS-300 has not asked for it); M16 is CS-300-blocking as of 2026-04-24.

## Open questions

None at kickoff. Scope was negotiated directly with CS-300 in the 2026-04-24 feature request; shape is final.

## Carry-over from prior milestones

- *None at M16 kickoff.* The 0.1.3 patch + M15 absorb every audit finding that predates M16.

## Propagation status

Filled in at audit time. Anticipated forward-deferrals:

- **Entry-point discovery (PEP 621).** `nice_to_have.md` candidate — trigger: a consumer wants to pip-publish their workflow package. Composes over M16's dotted-path loader (entry points would be an additional discovery channel, not a replacement).
- **`AIW_PRIMITIVES_PATH`.** `nice_to_have.md` candidate — trigger: a consumer asks for a user-primitives extension point.
- **`aiw inspect <workflow>` command.** `nice_to_have.md` candidate — trigger: discoverability polish demand.
- **Programmatic-import logging default.** `nice_to_have.md` candidate — trigger: a consumer reports silent logging when importing `ai_workflows` directly from their own script.
- **Hot-reload for `aiw-mcp` HTTP mode.** `nice_to_have.md` candidate — trigger: a consumer wants to iterate on a workflow against a running HTTP server.

## Issues

Land under [issues/](issues/) after each task's first audit.

## Release

0.2.0 minor bump (pure additive surface addition; backwards-compatible — unset env var + absent flag = zero behavioural change from 0.1.3).
