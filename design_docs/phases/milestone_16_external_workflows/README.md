# Milestone 16 — External Workflows + Primitives Load Path

**Status:** 📝 Planned (drafted 2026-04-23).
**Grounding:** [architecture.md §3 + §4.2](../../architecture.md) · [roadmap.md](../../roadmap.md) · [analysis/post_0.1.2_audit_disposition.md](../../analysis/post_0.1.2_audit_disposition.md) · [ai_workflows/workflows/__init__.py:58-76](../../../ai_workflows/workflows/__init__.py#L58-L76) (the workflow registry — `_REGISTRY: dict[str, WorkflowBuilder]` populated by `register(name, builder)` calls at import time) · [ai_workflows/workflows/_dispatch.py:202-217](../../../ai_workflows/workflows/_dispatch.py#L202-L217) (the dynamic-import site) · [M15 README](../milestone_15_tier_overlay/README.md) (tier overlay — precondition).

## Why this milestone exists

The workflow registry today is **closed at the package level.** [`ai_workflows/workflows/__init__.py:58-76`](../../../ai_workflows/workflows/__init__.py#L58-L76) exposes `register(name, builder)`, and the only callers are the shipped workflow modules themselves (`planner.py`, `slice_refactor.py`) — registration fires when those modules are imported. Dispatch resolves `aiw run <name>` via `importlib.import_module("ai_workflows.workflows.<name>")` at [`_dispatch.py:202-217`](../../../ai_workflows/workflows/_dispatch.py#L202-L217) — there is no scan of any directory outside the installed package.

Consequence: a PyPI-installed user who wants to run their own workflow — a CS-300 question-generator, a document-summariser, a code-review flow — must **fork** the package. The extension surface the architecture promises via KDR-002 ("CLI and MCP are peers") is actually gated behind "edit the installed site-packages" on the CLI side.

Two related gaps also surfaced in the post-0.1.2 audit (2026-04-23):

1. **No user-primitives load path.** Users who write their own workflow may want a custom primitive too — a domain-specific validator, a role-tagged cost aggregator, a specialised graph adapter. Today the primitives layer is closed the same way the workflows layer is.
2. **`configure_logging()` is only called at CLI/MCP entry.** A library-style import (`from ai_workflows.workflows.planner import build_planner` from a user's own Python) silently drops all structured logs. When user-supplied workflows become a first-class surface, this silent-logging failure mode will bite every consumer who doesn't know to call `configure_logging()` explicitly.

M16 closes both gaps with the minimum viable extension surface: **directory scanning via `importlib.util.spec_from_file_location`** — not Python entry points, not a plugin API. Reason: entry points force a reinstall on every iteration ("scaffold, tweak, re-run" becomes "scaffold, tweak, reinstall, re-run"), which kills the dev-loop that makes M17's scaffold workflow usable. Directory scan preserves the edit-in-place workflow.

## What M16 ships

1. **`AIW_WORKFLOWS_PATH`** env var (colon-delimited list, POSIX-style). At `aiw` / `aiw-mcp` startup, every directory on the path is walked for `*.py` files; each file is imported via `importlib.util.spec_from_file_location(...)` with a stable module name. The imported module is expected to call `register(name, builder)` at top level — same contract as the shipped workflows. Modules that fail to import or raise during `register(...)` log a structlog error + are skipped (other workflows in the same directory still load). Modules that don't call `register(...)` at all are imported silently (no harm done).
2. **`AIW_PRIMITIVES_PATH`** env var, same shape. Scanned before `AIW_WORKFLOWS_PATH` so user-primitives are available when user-workflows import them. User-supplied primitives are expected to self-register any extension points (same module-top-level contract). The four-layer contract still applies to user code: `import-linter` is **not** run against user modules (ai-workflows does not police user code), but the documentation makes the expected layer relationship clear.
3. **Programmatic-import logging default.** `ai_workflows/__init__.py` gains a `_ensure_logging_configured()` call that invokes `configure_logging(level=os.environ.get("AIW_LOG_LEVEL", "INFO"))` **if no handler is yet attached to the structlog root logger**. Idempotent with the existing CLI/MCP-entry calls (those still call `configure_logging()` explicitly — `_ensure_...()` is a no-op once a handler is present). Gives library-style imports sensible default logging; explicit callers can still `configure_logging(level="DEBUG")` to override.
4. **`aiw inspect <workflow>` CLI command.** Prints the workflow's tier points (name → default tier, post-M15-overlay), validator edges, `HumanGate` positions, and the source location (in-package vs. `$AIW_WORKFLOWS_PATH`). Pure read against the (extended) registry — zero LLM surface, zero dispatch side-effects. Pairs with M15's `aiw list-tiers` for end-to-end visibility: **"what tiers exist"** + **"what workflow uses them"**.
5. **Error surfacing for broken user modules.** User-module import errors do **not** fail `aiw` startup. Each error is logged via structlog with the file path + exception chain; the CLI exit code is 0 for startup (other workflows load fine); `aiw inspect` + `aiw list-workflows` report the failure next to a placeholder entry so a user looking for their workflow can see "this file failed to load, here's why."
6. **KDR-013 added to architecture.md §9.** *"External workflows and primitives load via AIW_WORKFLOWS_PATH and AIW_PRIMITIVES_PATH (colon-delimited directory lists). Loading uses importlib.util.spec_from_file_location; user modules are expected to call the package's register() helpers at module top level. Entry-point discovery (PEP 621) is deferred to a separate milestone triggered by users wanting to pip-publish their workflows. User code is owned by the user — ai-workflows does not lint, test, or sandbox it."* Composes over KDR-002 (CLI/MCP surface parity — both surfaces see the extended registry).
7. **ADR-0007 added.** *"User-owned code contract."* Records the decision to defer entry-point discovery, the risk-ownership boundary (user owns generated/supplied code; framework surfaces errors but does not police), and the rejected alternatives (entry-point-only, full plugin protocol, sandboxing).

## Goal

A user with no git clone can drop a Python file into a directory, set one env var, and run their workflow through the same `aiw` surface the shipped workflows use:

```bash
# User's own workflow file at ~/my-workflows/question_gen.py:
cat <<EOF > ~/my-workflows/question_gen.py
from ai_workflows.workflows import register
from langgraph.graph import StateGraph
# ... user defines build_question_gen() ...
register("question_gen", build_question_gen)
EOF

# Register it:
export AIW_WORKFLOWS_PATH=~/my-workflows

# Inspect + run:
aiw list-workflows
# -> planner (ai_workflows.workflows.planner)
#    slice_refactor (ai_workflows.workflows.slice_refactor)
#    question_gen (~/my-workflows/question_gen.py)

aiw inspect question_gen
# -> prints tier points, validators, gates, source path

aiw run question_gen --goal 'write 10 questions about KDR-003' --run-id qg-1
```

The same flow works through the MCP HTTP transport (`aiw-mcp --transport http`) — M11's gate-pause projection and M15's tier overlay both apply unchanged to user workflows. This is the foundation CS300 rides on: CS300's Astro frontend calls `run_workflow` via MCP, naming a workflow CS300 itself supplies via `AIW_WORKFLOWS_PATH`.

## Exit criteria

1. **`AIW_WORKFLOWS_PATH` + `AIW_PRIMITIVES_PATH` env vars.** Colon-delimited directory lists (POSIX convention — matches `$PATH`). Unset = no external load. Empty string = no external load. Non-existent directory on the path = structlog warning + skip that directory + continue to the next.
2. **Import mechanism.** `importlib.util.spec_from_file_location(unique_name, file_path)` + `module_from_spec` + `spec.loader.exec_module()`. Unique module name scheme: `aiw_external.<hash-of-abs-path>.<filename-stem>` (avoids collisions between identically-named files in different directories). Modules are cached in `sys.modules` so a second `aiw` invocation in the same process sees the same registered surface.
3. **Error surfacing — module-level.** `SyntaxError` / `ImportError` / arbitrary `Exception` raised during `exec_module()` is caught per-file; structlog error logs the file path + the full traceback; module is skipped; other files in the same directory continue loading.
4. **Error surfacing — registration-level.** A user module that imports cleanly but fails to call `register(...)` is a valid case (maybe it's a utility file shared by two workflow files). No warning. A user module that calls `register(...)` with a name that collides with a shipped workflow (`register("planner", ...)`) fails loudly at registration time: `WorkflowCollisionError` with a message that names both sources.
5. **Load order determinism.** `AIW_PRIMITIVES_PATH` directories scan first, then `AIW_WORKFLOWS_PATH`. Within each path, directories are scanned in the order they appear in the env var; within each directory, files are scanned in sorted-filename order. A user can predict which of two name-colliding user-workflows wins (it's "last one loaded wins," with a structlog warning). Internal (in-package) workflows always load first and cannot be shadowed (the collision check fires before override).
6. **Programmatic-import logging default.** `ai_workflows/__init__.py` calls `_ensure_logging_configured()` on module import. Idempotent — if a handler is already attached (e.g. CLI entry already called `configure_logging()`), the call is a no-op. A library-style `from ai_workflows.workflows.planner import build_planner` in a user's own script emits structlog events to stderr from that point onward. `$AIW_LOG_LEVEL` overrides the default INFO level.
7. **`aiw inspect <workflow>` command.** Prints tier points (post-M15 overlay), validator names, gate positions, source path, and — for external workflows — the absolute path of the `.py` file they live in. Pure read. Exit 0 if the workflow is registered, exit 1 if not.
8. **`aiw list-workflows` extends to external sources.** The existing surface (if any; see implementation research at T01 kickoff) reports in-package workflows; M16 extends it to list external ones alongside, flagged with their source path. Broken external modules show up as `question_gen: FAILED (syntax error at line 12)` so the user knows where to look.
9. **MCP surface parity.** The MCP server's `run_workflow` tool can invoke external workflows identically to in-package ones. No MCP schema change; the extension is invisible at the wire layer.
10. **Hermetic tests.** New `tests/workflows/test_external_load_path.py` — tmp-directory fixture, writes a sample workflow file, points `AIW_WORKFLOWS_PATH` at it, asserts the workflow is registered + runnable. Negative-path tests for import errors, registration collisions, empty directories, nonexistent directories. New `tests/test_programmatic_logging.py` — subprocess-style test that imports `ai_workflows.workflows.planner` directly without calling `configure_logging()`, asserts structlog events still land on stderr.
11. **KDR-013 in architecture.md §9.** Full text drafted at T04; T01 adds a placeholder reference.
12. **ADR-0007 under `design_docs/adr/0007_user_owned_code_contract.md`.** Records the deferral decision + risk-ownership framing.
13. **Documentation.** `docs/writing-a-workflow.md` gains a new **§External workflows** section with the directory + env-var + `register()` contract, a worked example, and the error-surfacing behaviour. `docs/architecture.md` references the new load path.
14. **Gates green on both branches.** `uv run pytest` + `uv run lint-imports` (4 kept — no new layer; external load is a primitive concern) + `uv run ruff check`.

## Non-goals

- **No entry-point discovery (PEP 621 `[project.entry-points.'ai_workflows.workflows']`).** Deferred to a future milestone triggered by "a user wants to pip-publish their workflows as a distributable package." Entry-point discovery and directory scan coexist fine; M16's choice is just about which one lands first. Directory scan + M17's scaffold workflow is the dev-loop-friendly path.
- **No sandboxing of user code.** User code runs in the same Python process, with the same filesystem access, as the framework. This is consistent with the project's local-only / solo-use posture (see `project_local_only_deployment.md` memory). If a future milestone introduces multi-tenant deployments, sandboxing becomes a concern then.
- **No linting of user code.** `uv run ruff check` and `uv run lint-imports` stay pointed at the package source only. User code is user-owned; the framework does not police style or layer compliance. Documentation makes this boundary explicit (ADR-0007).
- **No auto-discovery beyond the named env vars.** No `~/.ai-workflows/workflows/` default path (would make user code mysteriously active without an env var). Explicit opt-in via `$AIW_WORKFLOWS_PATH` is the only trigger.
- **No hot-reload.** `aiw-mcp` running as a long-lived HTTP server does not pick up new files in `$AIW_WORKFLOWS_PATH` without restart. Hot-reload is a future concern triggered by "a user wants to iterate on a workflow against a running MCP HTTP session."
- **No MCP tool for uploading workflow source.** The MCP surface does not gain a "write user workflow to disk" tool. M17's scaffold workflow writes to disk via a HumanGate-approved file write — that's its own surface, not M16's.
- **No change to `register()` semantics.** The existing in-package convention (`register(name, builder)` called at module top level) is preserved. External modules use the same API; no "external-only" registration helper.
- **No Anthropic API (KDR-003).** No new provider call. External load is a dispatch-layer concern.

## Key decisions in effect

| Decision | Reference |
|---|---|
| Directory scan over entry points (dev-loop friendliness) | M16 "Why" + ADR-0007 |
| User code is user-owned; framework surfaces errors but does not police | ADR-0007 + KDR-013 |
| In-package workflows cannot be shadowed by external ones | KDR-013 |
| Programmatic import triggers default logging | KDR-013 (logging paragraph) |
| MCP surface parity — external workflows are first-class via `run_workflow` | KDR-002 preserved |
| Four-layer import contract preserved — `import-linter` unchanged | architecture.md §3 |
| No new Anthropic / provider surface | KDR-003 |

## Task order

| # | Task | Kind |
|---|---|---|
| 01 | [`AIW_WORKFLOWS_PATH` + `AIW_PRIMITIVES_PATH` loader + collision + error surfacing](task_01_external_load_path.md) | code + test |
| 02 | Programmatic-import logging default + `aiw inspect` + `aiw list-workflows` external surface | code + test |
| 03 | KDR-013 + ADR-0007 + `docs/writing-a-workflow.md` §External workflows | doc |
| 04 | Milestone close-out | doc |

Per-task spec files land as each predecessor closes.

## Dependencies

- **M15 (tier overlay + fallback) — precondition.** External workflows need a stable tier-configuration surface; M15's overlay means external workflow authors can rely on users rebinding tiers without editing the supplied Python.
- **M13 (v0.1.0 release) — precondition.** External load path ships as 0.3.0.
- **M14 (MCP HTTP transport) — composes over.** External workflows invoke identically over stdio + HTTP.
- **M17 (scaffold workflow) — M16 is precondition.** M17 generates user workflows; those workflows land in `$AIW_WORKFLOWS_PATH`, which M16 introduces.

## Open questions (resolve before T01 kickoff)

- **`AIW_PRIMITIVES_PATH` load order vs. `AIW_WORKFLOWS_PATH`.** Current plan: primitives first, then workflows. Reason: a user workflow may import a user primitive at module load time; the primitive must already be resolvable. If a user's file structure needs both in one directory, the directory should appear on `AIW_PRIMITIVES_PATH` **first** — the scan then picks up any `register()` calls for primitive types before walking the workflows path. Alternatively, we make `AIW_WORKFLOWS_PATH` the only path and document that primitives + workflows share the scan — simpler, but less explicit.
- **Module-name hash algorithm.** `aiw_external.<hash-of-abs-path>.<stem>` — what hash? `blake2b(path, digest_size=8)` is fast + stable + short; `hash(path)` would reuse the built-in but collision-resolve is weaker. Current plan: `blake2b`, 16-hex-char prefix.
- **Collision-check granularity.** A user workflow at `~/my-workflows/planner.py` that calls `register("planner", ...)` would collide with the shipped `planner`. Current plan: block at `register()` time with `WorkflowCollisionError`. Alternative: prefix external names with the directory name (e.g. `my-workflows:planner`) — feels heavier; rejected for M16.

## Carry-over from prior milestones

- *None at M16 kickoff.* The 0.1.3 patch + M15 absorb every audit finding that predates M16.

## Propagation status

Filled in at audit time. Anticipated forward-deferrals:

- **Entry-point discovery (PEP 621).** `nice_to_have.md` candidate — trigger: a user wants to pip-publish their workflow package. Composes over M16's directory-scan path (entry points would be an additional discovery channel, not a replacement).
- **Hot-reload for `aiw-mcp` HTTP mode.** `nice_to_have.md` candidate — trigger: a user wants to iterate on a workflow against a running HTTP server. Current design is load-once at startup.
- **Workflow-signing / tamper-detection.** `nice_to_have.md` candidate — trigger: M16 external workflows get distributed outside the author's own machine. Not a concern for CS300 (single-operator, single-machine).

## Issues

Land under [issues/](issues/) after each task's first audit.
