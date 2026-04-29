# Task 06 — Eval harness fixture convention for cascade author/auditor node pairs

**Status:** ✅ Complete (2026-04-29).
**Grounding:** [milestone README](README.md) (§Goal item 6 + Exit-criteria #9) · [ADR-0004 §Decision item 6 — telemetry is load-bearing](../../adr/0004_tiered_audit_cascade.md) · [architecture.md §4.1 (evals layer) / §9 KDR-011 (audit cascade) / KDR-009 (storage discipline) / KDR-004 (validator pairing)](../../architecture.md) · [task_02 close-out (cascade primitive — `_primary` / `_auditor` node-name suffixes)](task_02_audit_cascade_node.md) · [task_03 close-out (workflow wiring — `_AUDIT_CASCADE_ENABLED` per workflow)](task_03_workflow_wiring.md) · [task_04 close-out (`TokenUsage.role` factory-time binding on `tiered_node`)](task_04_telemetry_role_tag.md) · [ai_workflows/evals/capture_callback.py:117-154 (`on_node_complete` writes `evals/<dataset>/<workflow>/<node_name>/<case_id>.json`)](../../../ai_workflows/evals/capture_callback.py) · [ai_workflows/evals/storage.py (`fixture_path`, `save_case`, `load_case`)](../../../ai_workflows/evals/storage.py) · [ai_workflows/evals/runner.py:284-344 (`_invoke_replay` + `_resolve_node_scope` — KDR-004 validator-pair lookup)](../../../ai_workflows/evals/runner.py) · [ai_workflows/graph/audit_cascade.py:312, 349, 531-540 (cascade node-name builders + sub-graph node registration)](../../../ai_workflows/graph/audit_cascade.py) · [ai_workflows/workflows/planner.py:564-570 (`audit_cascade_node(name="planner_explorer_audit")`)](../../../ai_workflows/workflows/planner.py) · [ai_workflows/workflows/slice_refactor.py:1047-1053 (`audit_cascade_node(name="slice_worker_audit")`)](../../../ai_workflows/workflows/slice_refactor.py) · [ai_workflows/workflows/_dispatch.py:472-493 (`AIW_CAPTURE_EVALS` opt-in path)](../../../ai_workflows/workflows/_dispatch.py).

## What to Build

Document and lock the eval-fixture convention for cascade-enabled workflow runs, plus one golden test per opt-in workflow that exercises the convention end-to-end (cascade-enabled run → fixtures captured → fixtures loadable as `EvalCase` instances).

**Convention (already realised by T02 + M7 capture wiring; T06 documents and tests it):**

- A cascade-enabled run with `AIW_CAPTURE_EVALS=<dataset>` set writes one fixture per `tiered_node` invocation. The cascade primitive constructs two distinct `tiered_node` instances per cascade pair: the primary at `node_name=f"{name}_primary"` (with `role="author"` per T04 factory binding) and the auditor at `node_name=f"{name}_auditor"` (with `role="auditor"`). `CaptureCallback` writes each fixture to `evals/<dataset>/<workflow>/<node_name>/<case_id>.json` (existing T02 convention — `fixture_path()` keys off `node_name`).
- The author/auditor split is therefore **automatic and directory-segregated**: for the planner workflow the primary fixtures live under `planner/planner_explorer_audit_primary/` and auditors under `planner/planner_explorer_audit_auditor/` (per `planner.py:570` `name="planner_explorer_audit"` kwarg passed to `audit_cascade_node()`); for slice_refactor the primary fixtures live under `slice_refactor/slice_worker_audit_primary/` and auditors under `slice_refactor/slice_worker_audit_auditor/` (per `slice_refactor.py:1053` `name="slice_worker_audit"`). The directory split is realised by `CaptureCallback`'s existing `node_name`-keyed fixture path; **zero engine change** to `CaptureCallback`, `EvalRunner`, or the cascade primitive.
- The cascade verdict node (`f"{name}_verdict"`) is a pure parse step — no LLM call, no `tiered_node`, no fixture written. Verified at `audit_cascade.py:_audit_verdict_node` (no LLM dispatch path; only `AuditVerdict.model_validate_json`).
- **Replay constraint (HIGH-fix scope clarification):** `EvalRunner` cannot replay cascade-emitted fixtures via the standard `run_eval_case` path, because `_resolve_node_scope` (`runner.py:307-320`) requires a paired `<node_name>_validator` graph node per KDR-004, and the cascade graph registers validators as `<cascade_name>_validator` (single underscore segment) rather than `<cascade_name>_primary_validator` / `<cascade_name>_auditor_validator`. **T06 therefore scopes replay verification to direct `load_case(path)` (or `EvalCase.model_validate_json(path.read_text())`) — confirming the captured fixture loads as a valid `EvalCase` independently.** Full `EvalRunner` replay of cascade fixtures is forward-deferred (see §Propagation status); README Exit-criteria #9 phrasing "No change to `EvalRunner`'s engine" is honoured because T06 introduces no engine change at all — the convention IS the directory split, which is already realised.

**Why T06 is doc + golden test only (no code change):** T02 + T03 + T04 together already produce the directory split via the `_primary` / `_auditor` `node_name` suffix and T04's factory-time `role="author"` / `role="auditor"` binding on the cascade's two `tiered_node` constructions. The `CaptureCallback`'s existing `node_name`-keyed fixture path produces independent author/auditor directories without modification. The "existing role-tag can be read" framing in the M12 README §Goal item 6 refers to (a) the `_primary` / `_auditor` suffix on `node_name` (visible to any reader of the fixture path), and (b) the `usage.role` stamp on the recorded `TokenUsage` (visible to anyone replaying via `CostTracker.by_role`). T06 locks the contract by adding golden tests; spec edits to CaptureCallback or EvalRunner would be invented scope per CLAUDE.md "no drive-by refactors".

## Deliverables

### [evals/README.md](../../../evals/README.md) — convention documentation (new file or update if present)

Add a top-level layout-reference section + the cascade-fixture convention. Keep operator-facing — anchor on observable filesystem paths so a reader can verify by `ls evals/<workflow>/`.

```markdown
# evals/ — captured cases + golden suites

This tree holds two kinds of artefacts: hand-authored seed fixtures used as
golden cases, and capture-callback-emitted fixtures from real workflow runs
(opt-in via `AIW_CAPTURE_EVALS=<dataset>`). The replay engine lives in
`ai_workflows.evals` (see `evals/runner.py`).

## Layout reference

Two shapes coexist in `evals/`:

- **Hand-written / seed fixtures** (M7 T05) — `evals/<workflow>/<node>/<case>.json`.
  Authored directly via `save_case()` or committed by hand. The `EvalRunner`
  finds them via `load_suite(workflow_id)`. Examples on disk:
  `evals/planner/explorer/happy-path-01.json`,
  `evals/slice_refactor/slice_worker/happy-path-01.json`.
- **Capture-callback-emitted fixtures** (M7 T02) — `evals/<dataset>/<workflow>/<node>/<case>.json`.
  Written when a workflow run sets `AIW_CAPTURE_EVALS=<dataset>` (or a future
  surface threads `--capture-evals <dataset>`). The `<dataset>` segment
  disambiguates capture batches.

The cascade fixture convention below is a sub-shape of the second layout.

## Cascade fixture convention (M12 T06)

When the audit cascade is enabled for a workflow (`AIW_AUDIT_CASCADE_PLANNER=1`,
`AIW_AUDIT_CASCADE_SLICE_REFACTOR=1`, or the global `AIW_AUDIT_CASCADE=1` —
see ADR-0009 / KDR-014), each cascade pair writes two independent fixtures
when `AIW_CAPTURE_EVALS=<dataset>` is also set:

```
evals/<dataset>/<workflow>/<cascade_name>_primary/<case_id>.json    # role="author"
evals/<dataset>/<workflow>/<cascade_name>_auditor/<case_id>.json    # role="auditor"
```

`<cascade_name>` is the `name=` kwarg passed to `audit_cascade_node()` in the
workflow's compile function. For in-tree workflows:

| Workflow | `<cascade_name>` | Primary path | Auditor path |
|---|---|---|---|
| `planner` | `planner_explorer_audit` (`planner.py:570`) | `evals/<dataset>/planner/planner_explorer_audit_primary/` | `evals/<dataset>/planner/planner_explorer_audit_auditor/` |
| `slice_refactor` | `slice_worker_audit` (`slice_refactor.py:1053`) | `evals/<dataset>/slice_refactor/slice_worker_audit_primary/` | `evals/<dataset>/slice_refactor/slice_worker_audit_auditor/` |

Each captured fixture is independently loadable via
`ai_workflows.evals.storage.load_case(path)` (or
`EvalCase.model_validate_json(path.read_text())`); operators can spot-check
or hand-edit one side of a cascade pair without touching the other.

The cascade verdict node (`<cascade_name>_verdict`) is a pure parse step
(no LLM call); no fixture is written for it.

**Full-suite replay through `EvalRunner` is a follow-up.** Cascade nodes do
not match the engine's `<node>_validator` pair-lookup convention (KDR-004) —
`runner.py:_resolve_node_scope` looks for `<cascade_name>_primary_validator` /
`<cascade_name>_auditor_validator`, but the cascade graph only registers
`<cascade_name>_validator` (single underscore segment). T06 therefore scopes
replay verification to direct `load_case` loading. A future task may extend
`EvalRunner` to recognise cascade-internal node-name conventions.

Per-fixture telemetry: each captured `EvalCase` is paired with a
`TokenUsage` ledger entry stamped via `usage.role` at `tiered_node` factory
time (closure-bound — see `audit_cascade.py:313, 349`). The role tag is
NOT read from graph state, so retried/re-fired cascade attempts inherit the
correct role on every record. `state['cascade_role']` exists as a debug
surface for in-flight inspection of which sub-node last ran, but
`TokenUsage.role` is the persistent telemetry field. Aggregate via
`CostTracker.by_role(run_id)`.
```

If `evals/README.md` already exists, restructure under the heading layout above. If absent, create the file with the full content above.

### [.claude/skills/ai-workflows/SKILL.md](../../../.claude/skills/ai-workflows/SKILL.md) — cross-reference (one-line addition)

Under the existing eval section (or §"Primary surface — MCP" if no eval section exists yet), add a single bullet pointing readers at the new `evals/README.md` cascade-fixture convention. Format mirrors the existing tool-reference bullets:

```markdown
- **Cascade fixture layout** (M12 T06) — when capturing fixtures from a
  cascade-enabled run (`AIW_CAPTURE_EVALS=<dataset>` + cascade env-var
  flipped on), authors land under `evals/<dataset>/<workflow>/<cascade_name>_primary/`
  and auditors under `<cascade_name>_auditor/`. See `evals/README.md` for
  the full convention (planner: `<cascade_name>=planner_explorer_audit`;
  slice_refactor: `<cascade_name>=slice_worker_audit`).
```

### Tests

#### [tests/evals/test_cascade_fixture_convention.py](../../../tests/evals/test_cascade_fixture_convention.py) — new (hermetic, 4 tests)

Hermetic. Stub LLM dispatch via the established `_StubClaudeCodeAdapter` pattern at `tests/graph/test_audit_cascade.py:107` (the canonical reuse target — single-tier cascade test fixture). Use `tmp_path` and `monkeypatch.setattr(default_evals_root, ...)` (or pass `root=tmp_path` directly into `CaptureCallback.__init__`) so capture lands in a clean directory per test.

**Setup pattern (shared across tests 1–4 — drives the cascade graph inline, not via `run_workflow`, so the test owns the `CostTracker` instance):**

```python
import uuid
from ai_workflows.primitives.cost import CostTracker
from ai_workflows.graph.cost_callback import CostTrackingCallback
from ai_workflows.evals import CaptureCallback
from ai_workflows.evals.storage import load_case
from ai_workflows.graph.audit_cascade import audit_cascade_node

# Use a deterministic cascade_name for the test so the directory split is predictable:
CASCADE_NAME = "test_cascade"   # → primary node "test_cascade_primary", auditor "test_cascade_auditor"

run_id = f"test-{uuid.uuid4().hex[:12]}"
tracker = CostTracker()
cost_callback = CostTrackingCallback(cost_tracker=tracker, budget_cap_usd=None)
capture = CaptureCallback(
    dataset_name="test-dataset",
    workflow_id="cascade_test",
    run_id=run_id,
    root=tmp_path,
)
# ... build the cascade sub-graph via audit_cascade_node(name=CASCADE_NAME, ...) ...
# ... thread tracker + capture into config["configurable"] keys
#     (cost_callback, eval_capture_callback, tier_registry, run_id, thread_id, workflow="cascade_test", semaphores=...) ...
# ... drive `compiled.ainvoke(state, config=cfg)` with the stub adapter monkey-patched in ...
```

The setup is the established `tests/graph/test_audit_cascade.py` pattern (verify its current shape at implementation time and match it). Tests 2 + 3 below reference `tracker.by_role(run_id)` against the local `tracker` instance constructed here.

1. `test_cascade_run_emits_separate_primary_and_auditor_fixtures` — drive a single cascade-enabled invocation through the cascade graph with capture wired. Assert: exactly one fixture lands at `tmp_path / "test-dataset" / "cascade_test" / "test_cascade_primary"` (one `*.json` file), exactly one at `tmp_path / "test-dataset" / "cascade_test" / "test_cascade_auditor"`. No fixture under `test_cascade_verdict/` (verdict node has no LLM call). Fixture filenames match the `<case_id>.json` pattern.

2. `test_primary_fixture_role_tag_is_author` — after the same setup as test 1, assert `tracker.by_role(run_id).get("author", 0.0)` is the cost the primary `tiered_node` recorded (matches the cascade-primary stub adapter's emitted token count × pricing; concretely: assert `"author" in roles` and the entry maps to a non-negative float). The fixture file itself does not carry `role` — `role` lives on the `TokenUsage` ledger entry. Test pins both surfaces by cross-referencing the same `run_id`: load the primary fixture via `load_case(path)`, assert `case.captured_from_run_id == run_id`, then assert `tracker.by_role(run_id)` contains the `"author"` key.

3. `test_auditor_fixture_role_tag_is_auditor` — symmetric to test 2 for the auditor side. Asserts `tracker.by_role(run_id)` contains the `"auditor"` key, and the loaded auditor fixture has `case.captured_from_run_id == run_id`.

4. `test_captured_fixtures_load_independently_as_eval_cases` — load both fixtures via `load_case(primary_path)` and `load_case(auditor_path)`. Assert: `primary_case.node_name == "test_cascade_primary"`, `auditor_case.node_name == "test_cascade_auditor"`, `primary_case.workflow_id == "cascade_test"`, `auditor_case.workflow_id == "cascade_test"`, both `captured_from_run_id == run_id`. **NOT** invoking `EvalRunner` — the cascade replay through `EvalRunner._resolve_node_scope` is known-broken (validator-pair lookup mismatch) and forward-deferred (see spec §Propagation status). The contract this test pins is independent loadability of the two captured fixtures, which is exactly what README Exit-criteria #9 calls out as the convention.

These tests exercise the convention contract (directory split + role-tag visibility + independent loadability) without touching production code paths beyond what T02-T04 already shipped.

#### [tests/workflows/test_planner_cascade_fixture_golden.py](../../../tests/workflows/test_planner_cascade_fixture_golden.py) — new (hermetic, 1 golden test)

Hermetic. Stub planner LLM via the canonical `_StubClaudeCodeAdapter` shape from `tests/graph/test_audit_cascade.py:107` (preferred reuse target). Drive the planner workflow with cascade flipped on (`monkeypatch.setenv("AIW_AUDIT_CASCADE_PLANNER", "1")`) and `AIW_CAPTURE_EVALS=test-dataset` set. Test owns its `CostTracker` + thread-through (same shared-setup pattern as `test_cascade_fixture_convention.py`).

1. `test_planner_cascade_capture_writes_primary_and_auditor_fixtures` — run the planner workflow once with cascade enabled and capture wired; assert exactly two fixtures land:
   - One under `tmp_path / "test-dataset" / "planner" / "planner_explorer_audit_primary" / *.json`
   - One under `tmp_path / "test-dataset" / "planner" / "planner_explorer_audit_auditor" / *.json`

   Assert each fixture loads via `load_case(path)` cleanly; assert `case.workflow_id == "planner"`, primary `case.node_name == "planner_explorer_audit_primary"`, auditor `case.node_name == "planner_explorer_audit_auditor"`. Assert `tracker.by_role(run_id)` contains both `"author"` and `"auditor"` keys.

#### [tests/workflows/test_slice_refactor_cascade_fixture_golden.py](../../../tests/workflows/test_slice_refactor_cascade_fixture_golden.py) — new (hermetic, 1 golden test)

Hermetic. Symmetric to the planner golden test, for the slice_refactor workflow. Cascade env-var: `AIW_AUDIT_CASCADE_SLICE_REFACTOR=1`. Stub slice_refactor LLM via the canonical `_StubClaudeCodeAdapter` shape from `tests/graph/test_audit_cascade.py:107` (preferred reuse target — same as `test_cascade_fixture_convention.py`). If `slice_refactor` requires a different stub-adapter seed (e.g. multi-slice fan-out shape), Builder may fall back to whatever stub-adapter is in use at `tests/workflows/test_slice_refactor_cascade_enable.py`.

1. `test_slice_refactor_cascade_capture_writes_primary_and_auditor_fixtures` — symmetric to the planner test. Slice_refactor's cascade attaches via `audit_cascade_node(name="slice_worker_audit")` per `slice_refactor.py:1053`, so the primary node_name is `slice_worker_audit_primary` and the auditor is `slice_worker_audit_auditor`. Assert fixture paths match: `tmp_path / "test-dataset" / "slice_refactor" / "slice_worker_audit_primary" / *.json` and `tmp_path / "test-dataset" / "slice_refactor" / "slice_worker_audit_auditor" / *.json`. Assert `case.node_name == "slice_worker_audit_primary"` and `case.node_name == "slice_worker_audit_auditor"` respectively. Assert `tracker.by_role(run_id)` contains both `"author"` and `"auditor"` keys.

### KDR guardrails — verify, don't extend

- KDR-009 (SqliteSaver-only checkpoints) — T06 writes JSON fixtures under `evals/`, NOT new SQLite tables. No persistence-layer change.
- KDR-011 (audit cascade) — T06 documents the cascade's eval-fixture surface; no behaviour change to the cascade itself.
- KDR-013 (user-owned external workflow code) — convention applies to any `tiered_node`-using workflow including external ones. The convention is observable from filesystem paths; external workflow authors get it for free as long as they use the cascade primitive.
- KDR-004 (validator pairing) — T06 explicitly carves out cascade-fixture replay from `EvalRunner` because `_resolve_node_scope` enforces a `<node>_validator` pair-lookup that the cascade graph (intentionally) does not satisfy for its `_primary` / `_auditor` sub-nodes. T06 documents the constraint; resolving it is forward-deferred (see §Propagation status).

No new KDR proposed; no `architecture.md` edit needed.

### [CHANGELOG.md](../../../CHANGELOG.md)

`### Added — M12 Task 06: eval-harness fixture convention for cascade author/auditor node pairs (YYYY-MM-DD)`. List files touched (`evals/README.md`, `.claude/skills/ai-workflows/SKILL.md`, three new test files). Cite KDR-011 + KDR-004 (constraint carve-out). Note: documentation + golden tests only; no production code change (the convention is realised by T02 + T04 surfaces already shipped).

## Acceptance Criteria

- [x] `evals/README.md` exists with `## Layout reference` (two-shape coexistence: seed M7 T05 vs capture M7 T02) + `## Cascade fixture convention (M12 T06)` sections. The cascade-convention section enumerates the explicit primary/auditor paths for both opt-in workflows (`planner_explorer_audit_*` for planner, `slice_worker_audit_*` for slice_refactor), names the `<cascade_name>` placeholder with cross-references to `planner.py:570` and `slice_refactor.py:1053`, documents the verdict-node-no-fixture rule, calls out the `EvalRunner` replay carve-out (cascade nodes do not match `_resolve_node_scope`'s `<node>_validator` lookup; full-suite replay forward-deferred), and explains the `TokenUsage.role` (factory-time; persistent telemetry) vs `state['cascade_role']` (debug-only) distinction with `audit_cascade.py:313, 349` references.
- [x] `.claude/skills/ai-workflows/SKILL.md` carries a one-bullet cross-reference to `evals/README.md` for the cascade fixture layout convention; bullet names both opt-in workflows' `<cascade_name>` literals.
- [x] `tests/evals/test_cascade_fixture_convention.py` — 4 hermetic tests pass: (1) primary+auditor fixture emission at the deterministic `<dataset>/<workflow_id>/<cascade_name>_primary/` and `<cascade_name>_auditor/` paths under `tmp_path`; (2) primary fixture's `captured_from_run_id` matches the test's `run_id` AND `tracker.by_role(run_id)` contains `"author"`; (3) auditor fixture's `captured_from_run_id` matches AND `tracker.by_role(run_id)` contains `"auditor"`; (4) both fixtures load independently via `load_case(path)` and surface the expected `node_name` / `workflow_id` / `captured_from_run_id` triples.
- [x] `tests/workflows/test_planner_cascade_fixture_golden.py` — 1 golden hermetic test passes: cascade-enabled planner run with capture writes primary+auditor fixtures at `<tmp>/<dataset>/planner/planner_explorer_audit_primary/` and `<cascade>_auditor/` matching the convention; both fixtures load via `load_case`; `tracker.by_role(run_id)` contains both role keys.
- [x] `tests/workflows/test_slice_refactor_cascade_fixture_golden.py` — 1 golden hermetic test passes: cascade-enabled slice_refactor run with capture writes primary+auditor fixtures at `<tmp>/<dataset>/slice_refactor/slice_worker_audit_primary/` and `<cascade>_auditor/`; both fixtures load via `load_case`; `tracker.by_role(run_id)` contains both role keys.
- [x] All three new test files use the inline-cascade-construction pattern (NOT `run_workflow`) so the test owns the `CostTracker` instance and can directly query `tracker.by_role(run_id)`. Tests use `tmp_path` for fixture roots; no production `evals/` directory side effects.
- [x] No diff to `ai_workflows/evals/capture_callback.py`, `ai_workflows/evals/runner.py`, `ai_workflows/evals/storage.py`, `ai_workflows/evals/schemas.py`. No diff to `ai_workflows/graph/audit_cascade.py`, `ai_workflows/graph/tiered_node.py`. No diff to `ai_workflows/workflows/_dispatch.py`, `ai_workflows/workflows/planner.py`, `ai_workflows/workflows/slice_refactor.py`. T06 is doc + tests only — production code is already correct from T02-T04.
- [x] No `pyproject.toml` / `uv.lock` diff.
- [x] KDR-003 guardrail test still passes (no Anthropic SDK introduced).
- [x] `uv run pytest` + `uv run lint-imports` (5 contracts kept; no new contract added) + `uv run ruff check` all clean.
- [x] CHANGELOG entry under `[Unreleased]` cites KDR-011 + KDR-004 (constraint carve-out) and notes "documentation + golden tests only; no production code change".
- [x] **Hermetic smoke test:** `tests/evals/test_cascade_fixture_convention.py::test_cascade_run_emits_separate_primary_and_auditor_fixtures` is the convention-pin smoke test. Always-on; pins the directory split contract.
- [x] No wire-level (AIW_E2E) test required. T06 ships no new LLM dispatch path; the convention is realised entirely above the dispatch surface. Capture is hermetically observable.
- [x] Status surfaces flipped together at task close: (a) spec `**Status:**` line: `📝 Planned` → `✅ Complete (YYYY-MM-DD)`; (b) milestone README task-table row 06 Status column: `📝 Planned` → `✅ Complete (YYYY-MM-DD)`; (c) milestone README §Exit-criteria bullet 9 ticked from `[ ]` to `[x]`; (d) `tasks/README.md` row — N/A (M12 has no per-task subdirectory README).

## Dependencies

- **T02** ✅ shipped at `fc8ef19` — provides the cascade primitive emitting `<cascade_name>_primary` and `<cascade_name>_auditor` `tiered_node` instances (verified at `audit_cascade.py:312, 349`).
- **T03** ✅ shipped at `1677889` — wires planner + slice_refactor to opt-in cascade via env-var flip; cascade-name kwargs land at `planner.py:570` (`name="planner_explorer_audit"`) and `slice_refactor.py:1053` (`name="slice_worker_audit"`).
- **T04** ✅ shipped at `f6904cb` — adds `role="author"` / `role="auditor"` factory-time binding on `tiered_node`; `CostTracker.by_role` is the surface tests 2 + 3 of `test_cascade_fixture_convention.py` cross-reference.
- **T05** ✅ shipped at `8c664f6` — independent of T06; T05's standalone-audit tool does not capture fixtures (single-pass in-memory).

## Out of scope (explicit)

- **No CaptureCallback signature change.** `on_node_complete` keeps its existing signature (`run_id`, `node_name`, `inputs`, `raw_output`, `output_schema`). The role information is observable via the `node_name` suffix and via the same-run `CostTracker.by_role` query — no need to thread `role` into the capture call.
- **No EvalRunner engine change.** Per README Exit-criteria #9. Cascade replay via `EvalRunner.run_eval_case` is known-broken (validator-pair lookup mismatch — see KDR-004 carve-out above) and forward-deferred. T06's tests exercise loadability via `load_case`, not `EvalRunner.run_eval_case`.
- **No new fixture file format or filename prefix.** The `<cascade_name>_primary` / `<cascade_name>_auditor` directory split carries the role; filenames stay as `<case_id>.json`. The README §Goal item 6 phrasing "`author_<case_id>.json` + `auditor_<case_id>.json`" is the directory-split convention realised today, not a literal filename-prefix requirement.
- **No new MCP tool, no new CLI command.** Convention surfaces via documentation + tests only.
- **No new dependency.** Hermetic tests reuse the canonical `_StubClaudeCodeAdapter` shape from `tests/graph/test_audit_cascade.py:107`.
- **No cascade-enablement flip on planner or slice_refactor defaults.** Both stay default-off per ADR-0004 §Decision item 4. T06's golden tests flip the env-var inside the test scope only.
- **No author/auditor multi-tier capture.** T06 covers single-tier cascade pairs (the only shape T01 + T02 ship). Multi-tier cascading is a future task.
- **No Anthropic API.** KDR-003 preserved (no LLM dispatch path added).

## Carry-over from prior milestones

- *None.* T06 reuses M7's CaptureCallback + EvalRunner verbatim; no M7 surface gains a deliverable here.

## Carry-over from prior audits

- *None at spec time.* Populated by `/clean-implement` audit cycle if findings emerge.

## Carry-over from task analysis

- [x] **TA-LOW-01 (Round 1)** — In the proposed `evals/README.md` cascade-fixture-convention block, the role-tag paragraph already calls out the difference between `state['cascade_role']` (debug-only) and `TokenUsage.role` (telemetry source-of-truth) per the round-1 fix to M3. Builder verifies this paragraph lands in the final README and confirms the `audit_cascade.py:313, 349` references match production line numbers at implementation time (rather than spec-write time).
- [x] **TA-LOW-02 (Round 1)** — When implementing `tests/workflows/test_slice_refactor_cascade_fixture_golden.py`, prefer to reuse the canonical `_StubClaudeCodeAdapter` shape from `tests/graph/test_audit_cascade.py:107` (already cited for `test_cascade_fixture_convention.py`); fall back to whatever stub-adapter is in use at `tests/workflows/test_slice_refactor_cascade_enable.py` only if `slice_refactor` requires a different fixture seed. Update the spec citation if the chosen adapter differs.

## Propagation status

Filled in at audit time. Anticipated forward-deferrals from T06:

- **`<cascade_name>_verdict` capture** — currently no fixture (verdict node is pure-parse). If a future task adds an LLM-call verdict node (e.g. an LLM-graded verdict instead of pydantic-parsed), the convention naturally extends (`<cascade_name>_verdict/` becomes a third fixture directory). No T06 deliverable; documented as forward-option only.
- **EvalRunner cascade-fixture replay** — `EvalRunner._resolve_node_scope` enforces a `<node>_validator` pair-lookup (KDR-004) that does not match the cascade graph's `<cascade_name>_validator` (single underscore segment) registration. Adding cascade-aware lookup is an engine change with KDR/ADR implications. Triggered by "an operator wants to replay a captured cascade fixture through `EvalRunner` end-to-end"; entry forward to `nice_to_have.md` after T06 ships.
- **External-workflow cascade fixture convention** — KDR-013 user-owned workflows that use the cascade primitive get this convention for free. If external workflows want a different layout (e.g. flatten the per-node directory split), they would author a custom CaptureCallback. Not a T06 deliverable; flag for `nice_to_have.md` if a CS300 or other external user requests it.
- **Multi-tier cascade fixture layout** — when single-tier audit verdicts prove unstable and multi-tier cascading lands as a future task, the directory convention extends from `<cascade_name>_auditor/` to per-tier sub-paths (e.g. `<cascade_name>_auditor_sonnet/`, `<cascade_name>_auditor_opus/`). No T06 deliverable.
