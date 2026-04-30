# Task 04 — ADR-0006 + `docs/tiers.example.yaml` relocation + `docs/writing-a-workflow.md` tier-config section

**Status:** 📝 Planned.
**Grounding:** [milestone README](README.md) · [architecture.md §9 KDR-006 / KDR-014](../../architecture.md) · [design_docs/adr/](../../adr/) · [docs/writing-a-workflow.md](../../../docs/writing-a-workflow.md) · [tiers.yaml](../../../tiers.yaml) · [KDR-006](../../architecture.md) (three-bucket retry) · [KDR-014](../../architecture.md) (framework owns tier policy).

## What to Build

Three documentation deliverables in one task (all spec'd by milestone README exit criteria #7 + #8):

**Deliverable A — ADR-0006:** Write `design_docs/adr/0006_tier_fallback_cascade_semantics.md`. Records the decisions made and alternatives rejected when designing the M15 fallback cascade. Must cover: trigger condition (retry-budget exhaustion after the `RetryingEdge` three-bucket cycle, not immediate error-class bypass), cost-accounting posture (truthful — every attempted route logs its `TokenUsage`), validator interaction (against successful route only; `RetryingEdge` retries the primary on semantic validation failure — KDR-004 preserved), nesting limit (flat — nested fallbacks explicitly rejected), and rejected alternatives (immediate-fail-over on first `NonRetryable`, score-based routing, provider-health probes, YAML overlay). Must explicitly note that the YAML-overlay design was considered and rejected due to KDR-014 (framework owns quality policy; env-var is the only operator override path).

**Deliverable B — Relocate `tiers.yaml` → `docs/tiers.example.yaml`:** Move the repo-root `tiers.yaml` to `docs/tiers.example.yaml`. Update its comment header to remove the now-stale "Forward-looking: M15 introduces..." sentence. Remove `tiers.yaml` from the repo root. Update all test references that loaded the file from `REPO_ROOT` (specifically `tests/primitives/test_tiers_loader.py` lines that call `TierRegistry.load(REPO_ROOT)` for the committed-file smoke tests — see §Deliverables below for the exact change shape). No runtime code loads `tiers.yaml` at dispatch time (that was verified in the M1 Task 06 audit); this is schema-smoke-fixture relocation only.

**Deliverable C — `docs/writing-a-workflow.md` tier-config section:** Append a new `### Fallback chains` subsection immediately after the existing `### Tier registry (\`tiers=\`)` subsection (line 36 of the doc; sibling H3, before `### Minimum viable spec`, both nested under `## The WorkflowSpec shape`). The subsection documents the `TierConfig.fallback` field (list of routes), the semantics (attempted in declaration order after retry-budget exhaustion), `AllFallbacksExhaustedError` on total failure, and a `ClaudeCodeRoute` → `LiteLLMRoute` fallback example. Reference `docs/tiers.example.yaml` as a schema reference for YAML-based exploration. Cross-link to ADR-0006.

---

## Deliverables

### 1. `design_docs/adr/0006_tier_fallback_cascade_semantics.md`

New ADR file. Follow the existing ADR structure (see `0004_tiered_audit_cascade.md` and `0009_framework_owns_policy.md` as templates). Required sections:

- **Title:** Tier Fallback Cascade Semantics
- **Status:** Accepted (M15)
- **Context:** The gap — when a tier's retry budget exhausts there was no declarative fallback. The M8 reactive post-gate fallback (`_mid_run_tier_overrides`) existed but was Ollama-specific and required a `HumanGate` pause. YAML-overlay approach considered + rejected (KDR-014 conflict).
- **Decision:** (1) `TierConfig.fallback: list[Route]` — flat list, no nesting. (2) Trigger: after `RetryingEdge` exhaustion, not on first error signal. (3) `TieredNode._node()` walks fallback list, fresh retry counter per fallback route. (4) Cost: every attempt logs via `CostTracker`. (5) Validator: runs on successful route's output; semantic validation failure is a primary-route concern (not cascade trigger). (6) `AllFallbacksExhaustedError(NonRetryable)` carries `attempts: list[TierAttempt]` for diagnostics. (7) YAML overlay rejected — KDR-014 (framework owns quality policy; env-var is operator override; persistent config requires KDR-014 amendment).
- **Alternatives rejected:** immediate-fail-over on first `NonRetryable` (bypasses retry budget, complicates cost reasoning), score-based routing (non-deterministic, testing complexity), provider-health probes (network dependency at routing time, violates simplicity), YAML overlay (KDR-014 conflict).
- **Consequences:** Fallback chains are Python-only (declared in workflow tier registries). Operator-level override remains `--tier-override` / `tier_overrides` per KDR-014. A future persistent-config path requires a KDR-014 amendment, not a tiers.yaml file.

### 2. `docs/tiers.example.yaml` (new file) and `tiers.yaml` (delete)

Create `docs/tiers.example.yaml` from the current `tiers.yaml` content with these header changes:
- Remove the stale forward-looking sentence:
  > `Forward-looking: M15 introduces `AIW_TIERS_PATH` + `~/.ai-workflows/tiers.yaml` as a user-supplied overlay that merges with workflow registries at dispatch time. This file becomes the reference/example `docs/tiers.example.yaml` once M15 ships.`
- Replace with:
  > `M15 shipped: this file has been relocated from `tiers.yaml` to `docs/tiers.example.yaml` as a user-facing schema-reference example. It is not loaded at runtime.`
- All tier entries (`local_coder`, `opus`, `sonnet`, `haiku`) remain unchanged.

Then delete `tiers.yaml` from the repo root.

### 3. `tests/primitives/test_tiers_loader.py` — update committed-file smoke tests

The four tests at lines 70, 86, 98, and 112 that call `TierRegistry.load(REPO_ROOT)` for the committed-file path must be updated since `REPO_ROOT / "tiers.yaml"` no longer exists after Deliverable B. The four tests by name:
- `test_committed_tiers_yaml_parses_into_tier_config_mapping` (line 58, call at line 70)
- `test_committed_tiers_resolve_to_the_correct_route_variant` (line 84, call at line 86)
- `test_claude_code_tiers_carry_the_expected_cli_model_flags` (line 96, call at line 98)
- `test_litellm_tier_carries_ollama_model_string` (line 104, call at line 112)

`REPO_ROOT` must be **preserved** — it is still used by `test_committed_pricing_yaml_has_only_claude_cli_entries` (line 331) which loads `pricing.yaml`, and by all `_write(tmp_path / "tiers.yaml", …)` helpers. Add a new constant alongside it:

```python
DOCS_DIR = Path(__file__).resolve().parents[2] / "docs"
```

Update each of the four committed-file calls to load the YAML directly via `yaml.safe_load` + `TierConfig.model_validate`:

```python
import yaml

def _load_example_tiers() -> dict:
    with open(DOCS_DIR / "tiers.example.yaml") as f:
        raw = yaml.safe_load(f)
    return {k: TierConfig.model_validate({**v, "name": k}) for k, v in raw.items()}
```

Replace each `TierRegistry.load(REPO_ROOT)` call in the four tests with a call to `_load_example_tiers()`. No production-code change needed; `ai_workflows/primitives/tiers.py` is unchanged.

### 3a. `tests/test_scaffolding.py` — replace `"tiers.yaml"` with `"docs/tiers.example.yaml"` in the parametrize list

`tests/test_scaffolding.py:113-127` includes `"tiers.yaml"` in the `test_scaffolding_file_exists` parametrize list (line 117). After Deliverable B deletes `tiers.yaml` from the repo root, this assertion fails. Replace the entry with `"docs/tiers.example.yaml"` so the scaffolding-files invariant tracks the relocated file. `REPO_ROOT / "docs/tiers.example.yaml"` will be created by Deliverable B.

### 4. `docs/writing-a-workflow.md` — `### Fallback chains` subsection

Append the new subsection immediately after the existing `### Tier registry` subsection (sibling H3 under `## The WorkflowSpec shape`, placed before `### Minimum viable spec`). The subsection content:

```markdown
### Fallback chains

When a route's retry budget exhausts (after `RetryingEdge`'s three-bucket cycle), `TieredNode`
walks the tier's `fallback` list in declaration order, attempting each route against a fresh
retry counter. If all routes fail, it raises `AllFallbacksExhaustedError` carrying a
`attempts: list[TierAttempt]` log for diagnostics.

Declare a fallback chain in `TierConfig.fallback`:

```python
from ai_workflows.primitives.tiers import ClaudeCodeRoute, LiteLLMRoute, TierConfig


def planner_tier_registry() -> dict[str, TierConfig]:
    return {
        "planner-synth": TierConfig(
            name="planner-synth",
            route=ClaudeCodeRoute(cli_model_flag="opus"),
            fallback=[
                ClaudeCodeRoute(cli_model_flag="sonnet"),   # first fallback
                LiteLLMRoute(model="gemini/gemini-2.5-flash"),  # last-resort
            ],
        ),
    }
```

**Semantics:**
- `fallback` is a flat list — no nested fallbacks. `TierConfig` rejects fallback routes that
  carry their own `fallback` field at schema-validation time.
- Cascade triggers *after retry-budget exhaustion*, not on the first error signal. The retry
  budget is the primary correctness surface.
- Cost attribution is truthful — every attempted route (primary + each fallback) logs its
  `TokenUsage`. `CostTracker.total(run_id)` reflects the aggregate.
- The `ValidatorNode` downstream of an `LLMStep` runs unchanged: it always validates the
  final successful route's output. Semantic-validation failure is a primary-route concern and
  does *not* trigger the cascade.

See [`docs/tiers.example.yaml`](tiers.example.yaml) for a YAML-syntax schema reference.
See [ADR-0006](../design_docs/adr/0006_tier_fallback_cascade_semantics.md) for the design
rationale and rejected alternatives.
```

### 5. `CHANGELOG.md`

Add an entry under `## [Unreleased] → ### Added` for M15 Task 04 noting: ADR-0006 added, `tiers.yaml` relocated to `docs/tiers.example.yaml`, `docs/writing-a-workflow.md` tier-config / fallback section added.

### 6. Status surfaces

- Flip this spec's `**Status:**` from `📝 Planned` to `✅ Built (cycle N, 2026-04-30)`.
- Update milestone README task-04 row to `✅ Built (cycle N)`.
- No `tasks/README.md` at repo root.
- Milestone README "Done when" exit criteria: T04 satisfies #7 (`docs/tiers.example.yaml` exists) and #8 (ADR-0006 added). Both flip at milestone close (T05 close-out) — they are milestone-level, not per-task checkboxes.

---

## Acceptance Criteria

| AC | Description |
|---|---|
| AC-1 | `design_docs/adr/0006_tier_fallback_cascade_semantics.md` exists; covers the seven §Decision points (fallback schema, trigger condition, cascade walk, cost attribution, validator interaction, `AllFallbacksExhaustedError` shape, YAML-overlay rejection) and the four §Alternatives-rejected items (immediate-fail-over, score-based routing, provider-health probes, YAML overlay) |
| AC-2 | `docs/tiers.example.yaml` exists; contains `local_coder`, `opus`, `sonnet`, `haiku` tiers; stale "Forward-looking" sentence removed from header |
| AC-3 | `tiers.yaml` no longer exists at repo root (`ls tiers.yaml` exits non-zero) |
| AC-4 | Five committed-file references update cleanly: four in `tests/primitives/test_tiers_loader.py` (load via `_load_example_tiers()` helper; no `TierRegistry.load(REPO_ROOT)` calls in `test_committed_tiers_yaml_parses_into_tier_config_mapping`, `test_committed_tiers_resolve_to_the_correct_route_variant`, `test_claude_code_tiers_carry_the_expected_cli_model_flags`, `test_litellm_tier_carries_ollama_model_string`), and one in `tests/test_scaffolding.py` (parametrize entry replaced with `"docs/tiers.example.yaml"`) |
| AC-5 | `docs/writing-a-workflow.md` contains `### Fallback chains` subsection with `TierConfig.fallback` example, flat-only semantics, cascade-trigger semantics, cost-attribution note, ADR-0006 cross-link |
| AC-6 | `CHANGELOG.md` updated under `[Unreleased]` |
| AC-7 | `uv run pytest` passes (full suite, including `tests/primitives/test_tiers_loader.py`) |
| AC-8 | `uv run lint-imports` passes — 5 contracts kept, 0 broken |
| AC-9 | `uv run ruff check` passes |

---

## Smoke test

AC-7 + AC-8 + AC-9 are the gate-level gates. The Auditor additionally verifies:

```bash
# AC-3: tiers.yaml gone from root
ls tiers.yaml  # must exit non-zero

# AC-2: example file present and parseable
python -c "
import yaml
from pathlib import Path
with open('docs/tiers.example.yaml') as f:
    data = yaml.safe_load(f)
assert 'local_coder' in data and 'opus' in data and 'sonnet' in data and 'haiku' in data
print('tiers.example.yaml OK —', list(data.keys()))
"

# AC-1: ADR file present
ls design_docs/adr/0006_tier_fallback_cascade_semantics.md

# AC-5: fallback section in docs
grep -n "Fallback chains" docs/writing-a-workflow.md
```

---

## Dependencies

- **M15 T01–T03** — must be ✅ Built before T04. T04 documents the fallback schema + cascade semantics that T01–T03 implement. (All three are shipped as of 2026-04-30.)
- **No production-code dependency** — T04 is documentation + test-path update only. `ai_workflows/primitives/tiers.py` is unchanged.

---

## Out of scope

- No changes to `ai_workflows/primitives/tiers.py`.
- No changes to dispatch logic (`ai_workflows/graph/tiered_node.py`).
- No YAML overlay runtime feature — explicitly dropped per rescoping note (KDR-014 conflict).
- No new `~/.ai-workflows/tiers.yaml` user-config surface.
- No `AIW_TIERS_PATH` environment variable.
- No YAML-based fallback chain authoring — fallback chains are Python-only (declared in `TierConfig.fallback` within the workflow's tier registry function).

---

## Carry-over from prior milestones

*(none at T04 kickoff)*

## Carry-over from prior audits

*(none at T04 kickoff — will be populated by the Auditor if findings arise)*

## Carry-over from task analysis

- [ ] **TA-LOW-01 — Grounding line cites `tiers.yaml` after the file is deleted** (severity: LOW, source: task_analysis.md round 1)
      The spec's Grounding line cross-links `[tiers.yaml](../../../tiers.yaml)`. After Deliverable B lands, that link is broken.
      **Recommendation:** Update the Grounding line to `[docs/tiers.example.yaml](../../../docs/tiers.example.yaml)` in the same commit that deletes `tiers.yaml`.

- [ ] **TA-LOW-04 — `tests/test_wheel_contents.py` docstring + error message reference `tiers.yaml`** (severity: LOW, source: task_analysis.md round 3)
      `tests/test_wheel_contents.py:150, 170` still name `tiers.yaml` in a docstring and assertion message. Test logic is unaffected (the "no bare-root `*.yaml` in the wheel" invariant is unchanged), but the strings are mildly stale after T04.
      **Recommendation:** Optionally update the strings to read `docs/tiers.example.yaml` in the same T04 commit; non-blocking if deferred.

- [ ] **TA-LOW-03 — Dependencies §"No production-code dependency" line mentioned the dropped `yaml_path` kwarg** (severity: LOW, source: task_analysis.md round 2)
      Spec's Dependencies section line said "The one exception is the optional `yaml_path` kwarg on `TierRegistry.load()`…" — contradicted Deliverable 3 and Out-of-scope §1. Fixed in round 2 to read "No production-code dependency — T04 is documentation + test-path update only. `ai_workflows/primitives/tiers.py` is unchanged." No Builder action needed; already resolved inline.

- [ ] **TA-LOW-02 — ADR-0006 link in `writing-a-workflow.md` should include `(builder-only, on design branch)` suffix** (severity: LOW, source: task_analysis.md round 1)
      Existing ADR cross-links in `docs/writing-a-workflow.md` all carry the `(builder-only, on design branch)` suffix (e.g. line 568, 658, 691). The spec's content block for the `### Fallback chains` subsection omits it.
      **Recommendation:** Match the pattern — render the ADR-0006 link as `[ADR-0006](../design_docs/adr/0006_tier_fallback_cascade_semantics.md) (builder-only, on design branch)` when adding the cross-link in `docs/writing-a-workflow.md`.
