# Task 03 — Populate `docs/` (user-facing architecture + two tutorials + link test)

**Status:** 📝 Planned (drafted 2026-04-22 after T02 audit closed clean).
**Grounding:** [milestone README §Exit criteria 5](README.md#L48-L52) · [task_02 close](task_02_name_claim_release_smoke.md) · [design_docs/architecture.md](../../architecture.md) (source material for user-facing rewrite) · [ai_workflows/graph/](../../../ai_workflows/graph/) (TieredNode / ValidatorNode / HumanGate reference) · [ai_workflows/workflows/__init__.py](../../../ai_workflows/workflows/__init__.py) (registry API) · [CLAUDE.md](../../../CLAUDE.md).

## What to Build

Three documentation rewrites + one new hermetic test. All four close one M13 exit criterion (§5 "`docs/` populated") without touching any `ai_workflows/` runtime code.

1. **Rewrite [docs/architecture.md](../../../docs/architecture.md)** — from 5-line pre-pivot placeholder to a user-facing architecture overview. Four-layer model (primitives → graph → workflows → surfaces), LangGraph `StateGraph` substrate, MCP as public surface, KDR summary. No `design_docs/` links (that tree does not ship on `main`); any reference to a builder-only doc is marked `(builder-only, on design branch)`.
2. **Rewrite [docs/writing-a-workflow.md](../../../docs/writing-a-workflow.md)** — from 5-line placeholder to a tutorial for authoring a new `StateGraph` under `ai_workflows/workflows/`. Composes the M2 graph primitives (`TieredNode`, `ValidatorNode`, `HumanGate`), registers via `ai_workflows.workflows.register`, surfaces through both `aiw run <name>` (CLI) and `run_workflow` (MCP).
3. **Rename [docs/writing-a-component.md](../../../docs/writing-a-component.md) → `docs/writing-a-graph-primitive.md`** and rewrite it. "Component" is a pre-pivot artefact from the abandoned substrate; "graph primitive" matches the current vocabulary. Tutorial for authoring a new adapter under `ai_workflows/graph/` over an existing primitive (matching the `TieredNode` / `ValidatorNode` / `HumanGate` / `RetryingEdge` / `CostTrackingCallback` pattern).
4. **Add [tests/docs/test_docs_links.py](../../../tests/docs/test_docs_links.py)** — a hermetic test that scans every `*.md` under `docs/` and asserts every relative markdown link resolves. Closes the other half of exit criterion §5 ("a new `tests/docs/test_docs_links.py` hermetic test pins that every relative link in `docs/` resolves").

## Deliverables

### 1. [docs/architecture.md](../../../docs/architecture.md) — user-facing architecture

**Audience:** a developer who has just installed `ai-workflows` from PyPI and wants a one-file orientation before reading tutorials. Not a builder, not an auditor. The `design_docs/architecture.md` on the `design` branch is the architecture of record for maintainers — this file is the **public abstract** of that doc, not a replacement.

**Structure (target ≤ 200 lines):**

1. **What this project is** (two paragraphs). LangGraph-native workflow framework exposing both a CLI (`aiw`) and an MCP server (`aiw-mcp`). Runs on a laptop with `uv` + provider keys (Gemini via LiteLLM, Ollama for local tiers, Claude Code via OAuth subprocess). No Anthropic API (KDR-003 citation).
2. **Four-layer model.** `primitives → graph → workflows → surfaces`. Per-layer one-paragraph summary. Import-linter enforces the one-way dependency direction ([pyproject.toml `[tool.importlinter]`](../../../pyproject.toml) — user-checkable via `uv run lint-imports`). No ASCII-art diagram required; a plain table maps layer → `ai_workflows/` subpackage → one-sentence role.
3. **LangGraph substrate.** A workflow is a Python module that builds a `langgraph.graph.StateGraph`. Registers via `ai_workflows.workflows.register(name, builder)`. State flows through nodes; checkpointing uses LangGraph's `SqliteSaver` (KDR-009); retry + error routing uses the three-bucket taxonomy (KDR-006) via `RetryingEdge`; LLM calls route through `TieredNode` paired with a `ValidatorNode` (KDR-004).
4. **Public surfaces.** Two: `aiw` CLI (entry points in [`ai_workflows/cli.py`](../../../ai_workflows/cli.py)) and `aiw-mcp` MCP server (entry point in [`ai_workflows/mcp/`](../../../ai_workflows/mcp/)). MCP tool schemas are the public contract — 0.1.0 freezes the shape (KDR-008). Browser-origin consumers reach the MCP surface via the streamable-HTTP transport (M14).
5. **KDR summary table.** Five rows — the KDRs actively load-bearing at v0.1.0: KDR-002 (portable surface), KDR-003 (no Anthropic API), KDR-004 (validator after every LLM node), KDR-008 (MCP schema public contract), KDR-009 (LangGraph checkpointer). One-sentence explanation per row. Each row's "deep dive" link points at the `design_docs/architecture.md §9` anchor on the **`design` branch** with a `(builder-only, on design branch)` note (users on `main` will not have `design_docs/` locally).
6. **Where to go next.** Three bullets: `docs/writing-a-workflow.md` for authoring a new workflow; `docs/writing-a-graph-primitive.md` for authoring a new graph adapter; the [README Install section](../../../README.md) for install + first run.

**Builder-only links guardrail.** Any pointer to `design_docs/…`, `CLAUDE.md`, `.claude/commands/`, or a milestone/task file gets a parenthesised `(builder-only, on design branch)` suffix. The `tests/docs/test_docs_links.py` test enforces this: a relative link that starts with `../design_docs/` or `../CLAUDE.md` must be accompanied by the `(builder-only, …)` marker on the same markdown line OR the link is flagged as a HIGH violation. See §Deliverables 4 for the rule grammar.

### 2. [docs/writing-a-workflow.md](../../../docs/writing-a-workflow.md) — authoring a new workflow

**Audience:** a developer who has read `architecture.md` and wants to ship their first workflow.

**Structure (target ≤ 250 lines):**

1. **Prerequisites.** Installed (`uv tool install ai-workflows` or working from clone), provider env vars set (`GEMINI_API_KEY`), `claude` CLI on PATH (only if the workflow will use the `claude_code` tier).
2. **The `StateGraph` shape.** A workflow is a function returning a compiled `StateGraph`. Minimal example: a single-node workflow that reads a field from state, calls a `TieredNode`, passes through a `ValidatorNode`, and writes the validated output back. State is a `TypedDict` or a `pydantic` model; shapes are free-form per workflow but must be picklable for LangGraph's checkpointer.
3. **Composing the graph primitives.** The four building blocks a workflow author composes, in order of typical use:
   - `TieredNode` — routes the LLM call to the tier the workflow requested (`orchestrator` / `implementer` / `gemini_flash` for Gemini; `local_coder` for Ollama-backed Qwen; `claude_code` for the OAuth CLI subprocess path).
   - `ValidatorNode` — mandatory pair after every `TieredNode` (KDR-004). Validates the LLM output shape; on failure, routes via `RetryingEdge` per the three-bucket taxonomy (KDR-006).
   - `HumanGate` — pauses the run, writes a checkpoint, exits with a `paused` status. Resume via `aiw resume <run_id>`.
   - `RetryingEdge` — wired between `ValidatorNode` and the retry target node; bucketed retry (transient / deterministic / hard-stop) per KDR-006.

   Each block references the actual class it composes (e.g. [`ai_workflows/graph/tiered_node.py`](../../../ai_workflows/graph/tiered_node.py)) with a one-paragraph API sketch — **no deep-dive** (that belongs in `docs/writing-a-graph-primitive.md`).
4. **Registration.** `ai_workflows.workflows.register(name, builder)` at module-import time. The `aiw run <name>` command + the MCP `run_workflow(workflow_id=<name>, …)` tool both resolve by name — no extra wiring per surface.
5. **Worked example.** A ~30-line "echo" workflow: single `TieredNode` + `ValidatorNode`, no `HumanGate`, uses the `gemini_flash` tier, registered as `echo`. Run via `aiw run echo --goal 'hello' --run-id demo`.
6. **Testing a workflow.** Pattern reference: use `StubLLMAdapter` (at [`ai_workflows/evals/_stub_adapter.py`](../../../ai_workflows/evals/_stub_adapter.py)) to inject deterministic LLM responses; LangGraph runs the state machine without a real provider call. Link to `tests/workflows/` on the `design` branch (builder-only) for the full test gallery.
7. **Surfaces automatic.** Once registered, the workflow is reachable via `aiw run <name>`, `aiw resume <run_id>`, and the MCP `run_workflow` / `resume_run` / `cancel_run` / `list_runs` tools — no per-workflow CLI code, no per-workflow MCP schema edit.

### 3. [docs/writing-a-graph-primitive.md](../../../docs/writing-a-graph-primitive.md) — authoring a new graph adapter

**Audience:** a developer who has shipped a workflow and now wants to extend the graph layer itself — e.g. a new `ValidatorNode` variant, a new retry strategy, or a new observability sink.

**Structure (target ≤ 250 lines):**

1. **When to write a new graph primitive vs. composing in the workflow.** Heuristic: if the same node-wiring pattern appears in ≥ 2 workflows, promote it to `ai_workflows/graph/`. Solo usage stays inline. This keeps the graph layer small and each primitive earn-its-weight-tested.
2. **The `graph/` layer contract.** Imports `primitives` + stdlib + `langgraph`. **No** imports from `workflows/` or `surfaces`. Enforced by import-linter — violations break `uv run lint-imports`.
3. **The composition pattern.** Every graph primitive:
   - Is a class or a function that returns a LangGraph `node` (or a `Runnable`).
   - Owns one concern (single-tier LLM call, single validation strategy, single observability sink). Don't bundle.
   - Has a module docstring citing the KDR(s) it implements and the primitive(s) it composes over.
   - Emits `StructuredLogger` events at entry + exit (KDR-007 — observability). No other backend.
4. **Worked example.** A ~40-line `MaxLatencyNode` that wraps an arbitrary node, records wall-clock runtime via `time.monotonic()`, and emits a `StructuredLogger.info` event at node exit. Demonstrates the wrap-and-delegate pattern used by `CostTrackingCallback` today.
5. **Testing a graph primitive.** Pattern reference: unit-test the primitive against a trivial LangGraph (one node, one edge). Compose against real `primitives` stubs (`StubProvider`, `FakeStorage`) — do not mock LangGraph itself.
6. **KDR alignment self-check.** Before merging a new primitive, confirm it does not import `anthropic` (KDR-003), does not add a second observability backend (KDR-007 — `StructuredLogger` only), does not introduce hand-rolled retry (KDR-006 — `RetryingEdge` only), and does not hand-roll checkpoint writes (KDR-009 — delegate to `SqliteSaver`).
7. **Where to deep-dive.** Link to `design_docs/architecture.md §3` (four-layer contract) and `§9` (KDR grid) with the `(builder-only, on design branch)` marker.

### 4. [tests/docs/test_docs_links.py](../../../tests/docs/test_docs_links.py) — hermetic relative-link test

New test file under new `tests/docs/` directory. Module docstring cites M13 T03 and its relationship to the `docs/` rewrite.

**Contract.**

- Scans every `*.md` file under `docs/`.
- For every relative markdown link `[text](path)` (anchors ignored), asserts the target file exists relative to the link's source file.
- Absolute links (`http://…` / `https://…`) are skipped.
- Fragment-only links (`#section`) are skipped.
- Links into `../design_docs/`, `../CLAUDE.md`, `../.claude/commands/`, or any `../milestone_*/` path **must** be accompanied by the literal string `(builder-only, on design branch)` on the same markdown line (the link's own line, not a neighbouring paragraph). Without the marker, the test fails — the reader landing on `main` via `uvx --from ai-workflows …` will not have those paths locally, and the marker is the only signal they get.
- Anchor fragments in relative links (e.g. `architecture.md#four-layer-model`) are tolerated — the test checks the file exists but does not validate the anchor resolves. Anchor validation is `nice_to_have.md` scope; not here.

**Test count:** one test function that iterates every `docs/*.md` file. Subtest / parametrisation optional — a single failure message listing the first broken link is sufficient.

**Fixture reuse.** None — the test is a pure filesystem + regex scan with no `uv build` dependency. Adds zero runtime to the pytest suite.

### 5. [CHANGELOG.md](../../../CHANGELOG.md)

Under `## [Unreleased]`, append a new block **above** the T02 entry:

```markdown
### Changed — M13 Task 03: populate `docs/` — architecture.md + writing-a-workflow.md + writing-a-graph-primitive.md + link test (YYYY-MM-DD)
```

Covers:

- Three docs rewritten from 5-line pre-pivot placeholders to user-facing content (line counts listed — target ≤ 200 / 250 / 250 respectively).
- `docs/writing-a-component.md` → `docs/writing-a-graph-primitive.md` rename (pre-pivot vocabulary retired).
- `tests/docs/test_docs_links.py` new — hermetic, pins every relative link resolves + enforces the `(builder-only, on design branch)` marker on `design_docs/` / `CLAUDE.md` / `.claude/` / `milestone_*/` targets.
- Files touched: `docs/architecture.md`, `docs/writing-a-workflow.md`, `docs/writing-a-graph-primitive.md` (new name), `docs/writing-a-component.md` (deleted), `tests/docs/__init__.py` (new, empty — pytest collection), `tests/docs/test_docs_links.py` (new), `CHANGELOG.md` (this entry).
- **Not touched:** `ai_workflows/` (documentation-only — AC-13); `pyproject.toml` (no new dep); `README.md` (T04 owns the root README trim).
- ACs satisfied (1-13).

## Acceptance Criteria

- [ ] AC-1: `docs/architecture.md` rewritten against §Deliverables 1 structure (6 sections: what it is / four-layer model / LangGraph substrate / public surfaces / KDR summary / where to go next). ≤ 200 lines.
- [ ] AC-2: `docs/architecture.md` contains zero links into `../design_docs/` / `../CLAUDE.md` / `../.claude/commands/` / `../milestone_*/` **without** the `(builder-only, on design branch)` marker on the same line. Enforced by the link test.
- [ ] AC-3: `docs/writing-a-workflow.md` rewritten against §Deliverables 2 structure (7 sections: prerequisites / StateGraph shape / graph primitives / registration / worked example / testing / surfaces automatic). ≤ 250 lines.
- [ ] AC-4: `docs/writing-a-workflow.md`'s worked example is a self-contained Python snippet that references real class names (`TieredNode`, `ValidatorNode`) and the real `register` API signature. A copy-paste user could type the example into a new module and have it syntactically parse — no pseudocode.
- [ ] AC-5: `docs/writing-a-component.md` is **deleted**, `docs/writing-a-graph-primitive.md` **exists** and is written against §Deliverables 3 structure (7 sections). ≤ 250 lines.
- [ ] AC-6: `docs/writing-a-graph-primitive.md` names the four KDRs self-checked at §Deliverables 3 item 6 (KDR-003, KDR-006, KDR-007, KDR-009) and cites each primitive by file path (e.g. [`ai_workflows/graph/tiered_node.py`](../../../ai_workflows/graph/tiered_node.py)).
- [ ] AC-7: `tests/docs/test_docs_links.py` exists, scans every `*.md` under `docs/`, and passes. Empty `tests/docs/__init__.py` lands alongside for pytest collection.
- [ ] AC-8: `tests/docs/test_docs_links.py` detects (via a targeted smoke inside the test itself, or via a separate `test_builder_only_marker` variant) a missing `(builder-only, on design branch)` marker on a `../design_docs/…` link — proven by a test case that mutates a temporary `.md` file in a `tmp_path`, writes a `design_docs/` link without the marker, runs the link-scanner function against it, and asserts it reports a violation.
- [ ] AC-9: `uv run pytest` green. Test count: 615 (from T02) + new link test functions (target: 2 — the main scan + the marker-enforcement smoke) = **617**.
- [ ] AC-10: `uv run lint-imports` reports 4 contracts kept, 0 broken. T03 adds no new layer contract.
- [ ] AC-11: `uv run ruff check` clean. The new test file lints clean; markdown files are outside ruff's scope.
- [ ] AC-12: CHANGELOG `[Unreleased]` entry lists files + ACs + the rename call-out (`writing-a-component.md` → `writing-a-graph-primitive.md`). T03 block lands above T02's.
- [ ] AC-13: Zero diff under `ai_workflows/`. T03 is documentation-only.

## Dependencies

- **T02 complete and clean** (✅ landed 2026-04-22, Cycle 1 of `/clean-implement`). T03 references the release-smoke gate in passing (`docs/architecture.md §6 Where to go next` optionally points at `scripts/release_smoke.sh` — builder-only, so the marker applies).
- **Source material:** `design_docs/architecture.md` — abstract for user-facing; do **not** copy wholesale (that doc is 400+ lines of builder-facing context).
- **No external dependency.** The link test is pure-Python filesystem scan + regex; no new packaging edit.

## Out of scope (explicit)

- **No runtime code change.** `ai_workflows/` is not touched. Documentation + test only.
- **No README edit.** Root `README.md` is T04's scope.
- **No skill install doc edit.** `skill_install.md` uvx option is T06's scope.
- **No `pyproject.toml` edit.** No new dep.
- **No anchor-resolution validation in `test_docs_links.py`.** `nice_to_have.md` candidate; add only on report.
- **No ASCII-art architecture diagram.** Table-based layer summary is sufficient; diagrams rot under doc edits and add maintenance cost for marginal clarity.
- **No branch split.** T05 owns the split; T03 runs on `design`.

## Propagation status

Filled in at audit time. Anticipated forward-deferrals: none — T03 is narrow documentation. Any MEDIUM / LOW that surfaces during audit is likely a doc-quality issue that lands as carry-over on T03 itself, not a sibling task.
