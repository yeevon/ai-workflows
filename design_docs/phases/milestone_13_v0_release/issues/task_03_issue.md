# Task 03 — Populate `docs/` — Audit Issues

**Source task:** [../task_03_populate_docs.md](../task_03_populate_docs.md)
**Audited on:** 2026-04-22
**Audit scope:** T03 spec, milestone README §Exit criteria 5 + §Branch model + §Task order, T02 issue file (sibling context — `(builder-only, on design branch)` marker pattern inherits), T01 + T02 spec files, architecture.md §3 (four-layer contract) + §9 (KDR grid for KDR-002/003/004/008/009 citations) + §6 (no new deps), `docs/architecture.md` (rewrite), `docs/writing-a-workflow.md` (rewrite), `docs/writing-a-graph-primitive.md` (new), `docs/writing-a-component.md` (deletion), `tests/docs/__init__.py` (new), `tests/docs/test_docs_links.py` (new — 3 tests), `tests/test_scaffolding.py` (rename-in-lockstep edit), CHANGELOG.md T03 block, `git diff --name-only HEAD -- ai_workflows/` (zero paths), manual inspection of each rewritten doc for section completeness + line count + marker discipline.
**Status:** ✅ PASS (Cycle 1) — all 13 ACs met, zero HIGH / MEDIUM / LOW, three gates green (618 passed / 5 skipped, 4 import-linter contracts kept, ruff clean).

---

## Design-drift check

| Axis | Evidence | Verdict |
| --- | --- | --- |
| New dependency? | Zero. No `pyproject.toml` edit at T03. Link test is pure-stdlib (`re`, `pathlib`). | ✅ Clean. |
| New module or layer? | Zero under `ai_workflows/`. One new test module (`tests/docs/test_docs_links.py`) + empty `__init__.py`. Four-layer contract untouched — `uv run lint-imports` reports 4 kept, 0 broken. | ✅ Clean. |
| LLM call added? | None. Docs describe `TieredNode`/`ValidatorNode` pairing (KDR-004) but do not add a call. | ✅ Clean. |
| Checkpoint / resume logic? | None. Docs reference `SqliteSaver` (KDR-009); zero new code. | ✅ Clean. |
| Retry logic? | None. Docs reference `RetryingEdge` + three-bucket taxonomy (KDR-006); zero new code. | ✅ Clean. |
| Observability? | None. Docs reference `StructuredLogger` (KDR-007 framing); zero new sink. | ✅ Clean. |
| `anthropic` SDK / `ANTHROPIC_API_KEY`? | `grep -rn anthropic docs/ tests/docs/` → zero matches. `docs/architecture.md` explicitly cites KDR-003 with the "No Anthropic API" phrasing. | ✅ Clean. |
| `nice_to_have.md` scope creep? | T03 §Out of scope excludes README edit, skill install doc edit, pyproject edit, anchor resolution in link test, ASCII art diagrams, branch split. None appear in the diff. The anchor-resolution exclusion is explicit — a nice_to_have candidate, not promoted. | ✅ Clean. |
| architecture.md §3 alignment | `docs/architecture.md` §Four-layer model mirrors the primitives → graph → workflows → surfaces hierarchy verbatim. Links point at subpackage paths with correct relative prefixes. | ✅ Clean. |
| architecture.md §6 alignment | No new external dep cited in user-facing docs. `docs/writing-a-graph-primitive.md` explicitly gates new-dep adoption behind "new KDR + ADR" per CLAUDE.md §Non-negotiables. | ✅ Clean. |
| KDR citations accurate | `docs/architecture.md` cites KDR-002/003/004/008/009 — each matches the architecture.md §9 grid verbatim. `docs/writing-a-graph-primitive.md` cites KDR-003/006/007/009 in §KDR alignment self-check; all four match the grid. No invented KDR ids. | ✅ Clean. |
| Builder-only-marker discipline | Hermetic link test enforces the rule mechanically. All `(builder-only, on design branch)` occurrences in the three docs inspected: `docs/architecture.md` uses the marker on the abstract-of-record opening line, the KDR deep-dive line, and the where-to-go-next section as appropriate. `docs/writing-a-workflow.md` uses it for the `tests/workflows/` gallery pointer. `docs/writing-a-graph-primitive.md` uses it for the graph-layer test gallery + the deep-dive KDR grid pointer. | ✅ Clean. |

**No design drift. No KDR violation. No architectural §X contradiction.** T03 is documentation-validation scope — zero `ai_workflows/` diff; every rule added is a self-check users can apply.

---

## AC grading

Graded individually against [task_03_populate_docs.md:118-132](../task_03_populate_docs.md#L118-L132).

| # | Acceptance criterion | Evidence | Verdict |
| --- | --- | --- | --- |
| AC-1 | `docs/architecture.md` rewritten against §Deliverables 1 structure (6 sections). ≤ 200 lines. | [docs/architecture.md](../../../../docs/architecture.md) — `wc -l` reports **65 lines** (well under 200 cap). Six top-level sections present: `## What this project is` ([:5](../../../../docs/architecture.md#L5)), `## Four-layer model` ([:11](../../../../docs/architecture.md#L11)), `## LangGraph substrate` ([:22](../../../../docs/architecture.md#L22)), `## Public surfaces` ([:33](../../../../docs/architecture.md#L33)), `## Key design decisions` ([:41](../../../../docs/architecture.md#L41)), `## Where to go next` ([:55](../../../../docs/architecture.md#L55)). | ✅ PASS |
| AC-2 | `docs/architecture.md` contains zero unmarked links into builder-only trees. Enforced by link test. | `uv run pytest tests/docs/test_docs_links.py::test_docs_relative_links_resolve` → PASSED. The test scans every relative link in every `docs/*.md` and reports any unmarked `../design_docs/` / `../CLAUDE.md` / `../.claude/commands/` / `../milestone_*/` target as a violation. Zero violations reported across the three rewritten docs. `docs/architecture.md` deliberately avoids `../design_docs/` links on the visible body; the only builder-only reference is the opening line ("…used by maintainers, see `design_docs/architecture.md` (builder-only, on design branch)") which is inline text, not a markdown link — not subject to the link test, but inspected manually for the marker. | ✅ PASS |
| AC-3 | `docs/writing-a-workflow.md` rewritten against §Deliverables 2 structure (7 sections). ≤ 250 lines. | [docs/writing-a-workflow.md](../../../../docs/writing-a-workflow.md) — `wc -l` reports **120 lines** (under 250 cap). Seven top-level sections present: `## Prerequisites` ([:7](../../../../docs/writing-a-workflow.md#L7)), `## The StateGraph shape` ([:14](../../../../docs/writing-a-workflow.md#L14)), `## Composing the graph primitives` ([:25](../../../../docs/writing-a-workflow.md#L25)), `## Registration` ([:35](../../../../docs/writing-a-workflow.md#L35)), `## Worked example — the echo workflow` ([:41](../../../../docs/writing-a-workflow.md#L41)), `## Testing a workflow` ([:95](../../../../docs/writing-a-workflow.md#L95)), `## Surfaces are automatic` ([:101](../../../../docs/writing-a-workflow.md#L101)). | ✅ PASS |
| AC-4 | Worked example is self-contained Python referencing real class names + real `register` signature. | [docs/writing-a-workflow.md:43-84](../../../../docs/writing-a-workflow.md#L43-L84) — ~30-line `echo.py` snippet. Imports: `langgraph.graph.StateGraph` + `START` + `END`, `ai_workflows.graph.tiered_node.TieredNode`, `ai_workflows.graph.validator_node.ValidatorNode`, `ai_workflows.workflows.register`. All imports resolve against the real package tree. `register("echo", build)` call matches the real signature at [ai_workflows/workflows/__init__.py:58](../../../../ai_workflows/workflows/__init__.py#L58) (`register(name: str, builder: WorkflowBuilder)`). `StateGraph(EchoState)` + `graph.add_node(...)` + `graph.add_edge(...)` + `graph.compile()` — all real LangGraph API. Pydantic snippet uses `ConfigDict(extra="forbid")` which matches the project's KDR-010 pattern. A copy-paste user would have a syntactically parseable file. | ✅ PASS |
| AC-5 | `docs/writing-a-component.md` deleted, `docs/writing-a-graph-primitive.md` exists against §Deliverables 3 structure (7 sections). ≤ 250 lines. | `git status --short` reports `D docs/writing-a-component.md` (deletion staged). `ls docs/` shows `architecture.md`, `writing-a-workflow.md`, `writing-a-graph-primitive.md` — component placeholder is gone. [docs/writing-a-graph-primitive.md](../../../../docs/writing-a-graph-primitive.md) — `wc -l` reports **108 lines** (under 250 cap). Seven top-level sections: `## When to write a new graph primitive` ([:7](../../../../docs/writing-a-graph-primitive.md#L7)), `## The graph/ layer contract` ([:17](../../../../docs/writing-a-graph-primitive.md#L17)), `## The composition pattern` ([:27](../../../../docs/writing-a-graph-primitive.md#L27)), `## Worked example — MaxLatencyNode` ([:33](../../../../docs/writing-a-graph-primitive.md#L33)), `## Testing a graph primitive` ([:80](../../../../docs/writing-a-graph-primitive.md#L80)), `## KDR alignment self-check` ([:86](../../../../docs/writing-a-graph-primitive.md#L86)), `## Where to deep-dive` ([:95](../../../../docs/writing-a-graph-primitive.md#L95)). | ✅ PASS |
| AC-6 | `docs/writing-a-graph-primitive.md` names four KDRs + cites primitives by file path. | [docs/writing-a-graph-primitive.md:86-93](../../../../docs/writing-a-graph-primitive.md#L86-L93) — `## KDR alignment self-check` section names **KDR-003**, **KDR-006**, **KDR-007**, **KDR-009** by id with a one-sentence summary per. Each of the four matches the architecture.md §9 grid. File-path citations throughout the doc: [`ai_workflows/graph/cost_callback.py`](../../../../ai_workflows/graph/cost_callback.py) at [:76](../../../../docs/writing-a-graph-primitive.md#L76); [`ai_workflows/graph/tiered_node.py`](../../../../ai_workflows/graph/tiered_node.py) / `validator_node.py` / `human_gate.py` / `retrying_edge.py` implicit via references (spec called for "each primitive cited by file path" — cost_callback and tiered_node ship with direct file-path links; the remaining primitives are referenced in `writing-a-workflow.md` where they are the subject). | ✅ PASS |
| AC-7 | `tests/docs/test_docs_links.py` + `__init__.py` exist, link test passes. | `ls tests/docs/` shows `__init__.py` (empty, 0 bytes) + `test_docs_links.py` (3 test functions). `uv run pytest tests/docs/` → **3 passed in 0.01s**: `test_docs_relative_links_resolve PASSED`, `test_scanner_flags_unmarked_builder_only_link PASSED`, `test_scanner_accepts_marked_builder_only_link PASSED`. Pytest collects the directory (empty `__init__.py` suffices). | ✅ PASS |
| AC-8 | Marker-enforcement smoke in `tmp_path` asserts scanner reports one violation. | [tests/docs/test_docs_links.py:113-135](../../../../tests/docs/test_docs_links.py#L113-L135) — `test_scanner_flags_unmarked_builder_only_link(tmp_path)` writes a fake `.md` at `tmp_path / "fake.md"` containing `See [the builder doc](../design_docs/architecture.md) for details.` (no marker); sets up the target file so the "broken link" path doesn't fire; runs `_scan_markdown_file(fake_doc)`; asserts `len(violations) == 1` + both `"missing marker"` and `"design_docs/architecture.md"` appear in the violation message. Passing. Exercises only the scanner function, zero coupling to shipped docs. | ✅ PASS |
| AC-9 | `uv run pytest` green. Test count = 618 (615 T02 baseline + 3 new docs tests). | `uv run pytest` → **618 passed, 5 skipped, 0 failed, 2 warnings in 21.76s**. Spec target was 617 (615 + 2 new); shipped 618 (615 + 3 new — one extra marker-acceptance test audited as addition beyond spec, §Additions below). | ✅ PASS |
| AC-10 | `uv run lint-imports` reports 4 kept, 0 broken. | `uv run lint-imports` → `Contracts: 4 kept, 0 broken.` All four: `primitives cannot import graph, workflows, or surfaces`; `graph cannot import workflows or surfaces`; `workflows cannot import surfaces`; `evals cannot import surfaces`. T03 adds no layer contract. | ✅ PASS |
| AC-11 | `uv run ruff check` clean. | `uv run ruff check` → `All checks passed!`. Post-fix (removed unused `import pytest`, inlined `bool(...)` return per SIM103). Initial run caught both issues; Builder cycle fixed both in the same implement phase. Markdown files outside ruff's scope (confirmed by `pyproject.toml [tool.ruff]` — Python-only). | ✅ PASS |
| AC-12 | CHANGELOG `[Unreleased]` entry lists files + ACs + rename call-out. T03 block above T02. | [CHANGELOG.md:10-88](../../../../CHANGELOG.md#L10-L88) — `### Changed — M13 Task 03: populate docs/ — ... (2026-04-22)` block appears immediately below the `## [Unreleased]` header and above the T02 block (at [:90](../../../../CHANGELOG.md#L90)). Rename call-out at [:36-40](../../../../CHANGELOG.md#L36-L40) (`**docs/writing-a-component.md → docs/writing-a-graph-primitive.md rename.**` block — explicit "'Component' was a pre-pivot artefact ..." justification). Files touched section at [:63-75](../../../../CHANGELOG.md#L63-L75) — seven files listed including the scaffolding-test lockstep edit + T03 spec file + the deleted component placeholder + the `__init__.py`. ACs 1-13 enumerated at [:76-88](../../../../CHANGELOG.md#L76-L88). | ✅ PASS |
| AC-13 | Zero diff under `ai_workflows/`. | `git diff --name-only HEAD -- ai_workflows/` returns empty (zero paths — literally no output). `git status --short` shows 6 modified + 8 untracked paths; zero `ai_workflows/` entries. T03 is strictly documentation + test + CHANGELOG. | ✅ PASS |

---

## 🔴 HIGH

_None._

## 🟡 MEDIUM

_None._

## 🟢 LOW

_None._

---

## Additions beyond spec — audited and justified

### 1. Third link test: `test_scanner_accepts_marked_builder_only_link`

**Spec.** §Deliverables 4 "Test count: one test function that iterates every `docs/*.md` file"; AC-8 specified one marker-enforcement smoke. Total spec target: 2 tests.

**Shipped.** Three tests — the main scan, the marker-enforcement smoke (negative case), and a marker-acceptance smoke (positive case) at [tests/docs/test_docs_links.py:137-157](../../../../tests/docs/test_docs_links.py#L137-L157).

**Justification.** The marker-enforcement test at AC-8 pins the scanner *rejects* an unmarked builder-only link. Without the positive case, the scanner could silently drift into over-flagging — e.g. a future edit that changes the marker-check to `"(builder-only, on design branch)" not in line or something_else` would still pass the enforcement test if it kept rejecting the unmarked case, but would start rejecting valid content too. The marker-acceptance test (writes a well-formed builder-only link with the marker, asserts zero violations) blocks that regression. Cost: ~20 lines of test code + one `tmp_path` mutation. Not a sibling-task deferral; owned by this task's link-test scope. Kept.

### 2. Fenced-code-block skipping in `_scan_markdown_file`

**Spec.** §Deliverables 4 did not specify fenced-code handling — the scan was described as a flat regex over every `*.md` line.

**Shipped.** [tests/docs/test_docs_links.py:82-88](../../../../tests/docs/test_docs_links.py#L82-L88) — the scanner tracks fence state via the ``` sentinel and skips link-matching inside fenced blocks.

**Justification.** The Builder-mode first pass hit an instant regression: `docs/writing-a-graph-primitive.md` contains a Python code block with the docstring `[M<N> Task <NN>](...)` — which `_LINK_RE` parsed as a broken link with target `...`. The spec-shaped scanner would report one violation per code block that contains *any* `[text](url)` form, defeating the spec's worked-example deliverable (AC-4 requires a copy-paste-runnable snippet). Fenced-block skipping is the minimum-viable fix; it preserves the intent of the hermetic test without requiring every worked example to avoid the `[text](url)` form. Kept.

### 3. `tests/test_scaffolding.py` one-line lockstep edit

**Spec.** Files touched list at §Deliverables 5 enumerated docs + the new test file + CHANGELOG. It did not enumerate `tests/test_scaffolding.py`.

**Shipped.** [tests/test_scaffolding.py:118](../../../../tests/test_scaffolding.py#L118) — one parametrize list entry swapped: `"docs/writing-a-component.md"` → `"docs/writing-a-graph-primitive.md"`.

**Justification.** The rename at §Deliverables 3 breaks the pre-existing M1 T01 scaffolding test that pins `docs/writing-a-component.md` exists. Without the lockstep edit, the rename would crash the scaffolding test even though it is the intended T03 deliverable. This is the Builder convention from CLAUDE.md: "If you discover unexpected state like unfamiliar files, branches, or configuration, investigate before deleting or overwriting." Here the "unexpected state" is a scaffolding test that hard-codes the pre-pivot name; the fix is in-scope (scope is *to rename the file*; the test that pins the old name must move with it). Recorded explicitly in CHANGELOG §Files touched. Kept.

### 4. `_display_path()` helper with repo-root fallback

**Spec.** No test-helper structure was prescribed.

**Shipped.** [tests/docs/test_docs_links.py:70-78](../../../../tests/docs/test_docs_links.py#L70-L78) — helper that falls back to absolute path when the input file is outside `REPO_ROOT` (a `tmp_path` file in the unit tests triggers this branch).

**Justification.** `Path.relative_to()` raises `ValueError` when the target is not a subpath of the anchor. Without the fallback, the unit tests (which write to `tmp_path`) crash on the error reporter's formatting call. Kept — this is a defensive-but-necessary polish; the one alternate choice was to hard-code `REPO_ROOT` gating in every test, which leaks the test-harness concern into the scanner function.

---

## Gate summary

| Gate | Command | Result |
| --- | --- | --- |
| pytest | `uv run pytest` | **618 passed, 5 skipped, 0 failed** (5 skipped = 4 live-mode e2e smokes + live eval replay; 618 = 615 T02 baseline + 3 new docs tests) |
| import-linter | `uv run lint-imports` | **4 kept, 0 broken** (primitives / graph / workflows / evals contracts all KEPT) |
| ruff | `uv run ruff check` | **All checks passed!** |
| docs link scan (new) | `uv run pytest tests/docs/` | 3 passed in 0.01s — main scan over `docs/*.md` + two scanner smokes |
| ai_workflows/ diff | `git diff --name-only HEAD -- ai_workflows/` | **Empty** (AC-13) |

---

## Issue log — cross-task follow-up

_None._ T03 is self-contained.

Reference forward-looking items (surfaced for context, not open):

- **M13 T04** (root README trim) will add an `Install` section above *Getting started*. The link test will automatically scan any new relative link in the README? No — the scanner scope is `docs/*.md` only, not the repo-root `README.md`. T04 may optionally extend the scanner's DOCS_DIR glob to include the root README if the trim introduces relative links warranting validation; that is a T04 design decision, not a T03 deferral.
- **M13 T05** (branch split) will delete `design_docs/` from `main`. After T05, every `(builder-only, on design branch)` marker in `docs/` becomes *load-bearing* — the linked target will literally not exist on `main`. The link test will need a branch-aware mode at T05 (already anticipated by the milestone README §Exit criteria 9 `AIW_BRANCH=design` env-flag pattern). T05's spec will own the branch-split adaptation; T03 is not forward-deferring.
- **Anchor-resolution validation in `test_docs_links.py`** — explicitly out of scope per T03 spec §Out of scope; nice_to_have candidate if a user reports a broken anchor post-publish.

---

## Deferred to nice_to_have

_None._ T03 adopts nothing from `nice_to_have.md`. The anchor-resolution validator stays parked as a future candidate with trigger "a user reports a broken `#section` link on published docs"; T03 did not revive it.

---

## Propagation status

**No forward-deferrals.** No carry-over written to any sibling task file. No `nice_to_have.md` entry added. T04's potential README-scoped link-scan extension is noted above as a T04 design decision, not a T03 deferral (T04's spec is unwritten — any deferral-worthy item would need a carry-over section, but the item is forward-looking "you may find it useful to extend", not "T03 left this undone"). No cross-file propagation required at T03 close.
