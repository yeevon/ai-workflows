# Task 01 — `TierConfig.fallback` schema

**Status:** 📝 Planned (rescoped 2026-04-30; spec needs rewrite before implementation — overlay loader deliverables dropped; scope = `TierConfig.fallback` schema + hermetic tests only).
**Grounding:** [milestone README](README.md) · [architecture.md §4.1 + §9](../../architecture.md) · [ai_workflows/primitives/tiers.py](../../../ai_workflows/primitives/tiers.py) · [ai_workflows/workflows/_dispatch.py:264-274](../../../ai_workflows/workflows/_dispatch.py#L264-L274) (the `_resolve_tier_registry()` function, three-step: workflow-registry → `load_overlay` (noop) → `_apply_tier_overrides`) · [KDR-014](../../architecture.md) (framework owns quality policy; tier defaults in module constants; env-var override only).

## What to Build

Two independent-but-paired deliverables that together lay the schema foundation for M15:

1. **Tier overlay loader.** A path-resolver + YAML loader + merge-rule implementation at the primitives layer, plus a one-line integration point in `_resolve_tier_registry()`. The loader resolves `$AIW_TIERS_PATH` → `~/.ai-workflows/tiers.yaml` → none, parses the file as a `dict[str, TierConfig]`, and merges over the workflow's own registry with "replace by name" semantics. Missing overlay is silent; unknown tier names in the overlay log a structlog warning and are dropped.
2. **`TierConfig.fallback` schema field.** A new optional `fallback: list[LiteLLMRoute | ClaudeCodeRoute]` field on `TierConfig`, with pydantic validation that rejects nested fallbacks at schema-check time. No dispatch logic in T01 — that's T02. T01 ships the schema + tests; T02 wires it up.

T01 deliberately separates **schema + loader (primitives layer)** from **dispatch + cascade behaviour (graph layer, T02)**. This respects the four-layer contract and keeps the review surface small.

## Deliverables

### 1. `ai_workflows/primitives/tiers.py` — overlay loader

Add a new module-level function `load_overlay(overlay_path: Path | None = None) -> dict[str, TierConfig]` and a new classmethod `TierRegistry.merge_overlay(workflow_registry: dict[str, TierConfig], overlay: dict[str, TierConfig]) -> dict[str, TierConfig]`.

Path resolution (done by a helper `_resolve_overlay_path()`):

```python
def _resolve_overlay_path() -> Path | None:
    env = os.environ.get("AIW_TIERS_PATH")
    if env:
        p = Path(env).expanduser()
        return p if p.exists() else None  # explicit path but file missing → None + warning
    default = Path.home() / ".ai-workflows" / "tiers.yaml"
    return default if default.exists() else None
```

`load_overlay()` reads the resolved path (if any) via the existing `_read_yaml_mapping()` helper, then parses each entry into a `TierConfig` via the existing pydantic model (same shape as `TierRegistry.load()`). Errors during parse raise `OverlayParseError` (new) with the file path + the pydantic validation error — loud fail-fast, not silent.

`TierRegistry.merge_overlay()` implements the merge rule:

```python
@classmethod
def merge_overlay(
    cls,
    workflow_registry: dict[str, TierConfig],
    overlay: dict[str, TierConfig],
) -> dict[str, TierConfig]:
    """Replace workflow tiers by name. Unknown overlay names warn + drop."""
    result = dict(workflow_registry)
    for name, tier in overlay.items():
        if name in workflow_registry:
            result[name] = tier
        else:
            _LOG.warning(
                "unknown_tier_in_overlay",
                tier_name=name,
                workflow_tiers=sorted(workflow_registry.keys()),
                overlay_path=str(_resolve_overlay_path()),
            )
            # drop the overlay entry silently (already logged)
    return result
```

### 2. `ai_workflows/workflows/_dispatch.py` — integration point

Change `_resolve_tier_registry(workflow, module)` (currently lines 220-230) from:

```python
def _resolve_tier_registry(workflow: str, module: Any) -> dict:
    helper = getattr(module, f"{workflow}_tier_registry", None)
    if helper is None:
        return {}
    return helper()
```

to:

```python
def _resolve_tier_registry(workflow: str, module: Any) -> dict:
    helper = getattr(module, f"{workflow}_tier_registry", None)
    workflow_registry = helper() if helper else {}
    overlay = load_overlay()  # empty dict when no overlay
    return TierRegistry.merge_overlay(workflow_registry, overlay)
```

Minimal surface delta. Preserves the "workflow registers nothing" edge case (empty dict in, empty dict out if no overlay either).

### 3. `ai_workflows/primitives/tiers.py` — `TierConfig.fallback` schema

Extend the existing `TierConfig` pydantic model:

```python
class TierConfig(BaseModel):
    name: str
    route: Annotated[LiteLLMRoute | ClaudeCodeRoute, Field(discriminator="kind")]
    max_concurrency: int = 1
    per_call_timeout_s: int = 180
    # NEW in 0.2.0 (M15 T01):
    fallback: list[Annotated[LiteLLMRoute | ClaudeCodeRoute, Field(discriminator="kind")]] = Field(
        default_factory=list,
        description=(
            "Ordered fallback routes tried after this tier's retry budget "
            "exhausts (M15). Flat only — routes in this list cannot themselves "
            "carry a `fallback` field. Cascade logic lives in TieredNode."
        ),
    )

    @field_validator("fallback", mode="before")
    @classmethod
    def _reject_nested_fallback(cls, v: Any) -> Any:
        """Nested fallback is architecturally forbidden (ADR-0006)."""
        if isinstance(v, list):
            for item in v:
                if isinstance(item, dict) and "fallback" in item:
                    raise ValueError(
                        "nested fallback is not allowed: the fallback list "
                        "contains an entry with a 'fallback' field of its own."
                    )
        return v
```

The route-union type reuse means the same `${VAR:-default}` env-var expansion that `LiteLLMRoute` already supports works in fallback entries too — no new secrets path.

### 4. Tests — `tests/primitives/test_tier_overlay.py` (new)

Hermetic — no disk I/O outside `tmp_path`, no provider calls.

- `test_overlay_env_var_wins_over_default_path` — sets `AIW_TIERS_PATH` to a tmp file, asserts `_resolve_overlay_path()` returns that path; unsets env var, asserts fallback to `~/.ai-workflows/tiers.yaml`.
- `test_overlay_missing_file_returns_empty` — no overlay file anywhere, `load_overlay()` returns `{}` (silent, no exception).
- `test_overlay_explicit_path_missing_warns_and_returns_empty` — `AIW_TIERS_PATH` set to a non-existent path, `load_overlay()` returns `{}` **and** a structlog warning fires naming the missing path.
- `test_overlay_parse_error_raises_loud` — malformed YAML in the overlay, `load_overlay()` raises `OverlayParseError` with the file path + the pydantic validation error. No silent swallow.
- `test_merge_overlay_replaces_by_name` — workflow registry has `{planner-synth: opus}`; overlay has `{planner-synth: sonnet}`; merged result is `{planner-synth: sonnet}`.
- `test_merge_overlay_unknown_name_warns_and_drops` — workflow has `{planner-synth: opus}`; overlay has `{nonexistent-tier: sonnet}`; merged result is `{planner-synth: opus}` (overlay dropped); structlog warning fires naming `nonexistent-tier` + the workflow's known tier names.
- `test_merge_overlay_preserves_workflow_tiers_not_overridden` — workflow has `{planner-explorer: qwen, planner-synth: opus}`; overlay only touches `planner-synth`; merged result keeps `planner-explorer` unchanged.
- `test_tierconfig_fallback_field_accepts_flat_list` — construct a `TierConfig` with a two-entry `fallback` list; assert it parses successfully.
- `test_tierconfig_fallback_field_rejects_nested_fallback` — attempt to construct a `TierConfig` where a `fallback` entry carries its own `fallback` key; assert pydantic `ValidationError` with the "nested fallback is not allowed" message.
- `test_tierconfig_fallback_defaults_to_empty_list` — every existing `TierConfig` that doesn't declare `fallback` round-trips through pydantic unchanged; `tier.fallback == []`.

### 5. `tests/primitives/test_tiers_loader.py` — adjust existing tests

The existing loader tests stay green; two adjustments:

- Remove any assertion that expects a specific number of tiers in `tiers.yaml` at the repo root. Post-0.1.3 the repo-root YAML has different contents (`planner` + `implementer` entries deleted); post-M15 T04 it's relocated to `docs/tiers.example.yaml`. The loader tests stay focused on schema parsing, not on the specific repo-root file's contents.
- Add one integration test `test_resolve_tier_registry_applies_overlay_when_set` — monkeypatches `AIW_TIERS_PATH` to a tmp overlay, calls `_resolve_tier_registry("planner", planner_module)`, asserts the returned registry reflects the overlay's rebind.

### 6. `ai_workflows/primitives/tiers.py` — module docstring update

Add a new "Overlay loading (M15)" subsection under the existing Relationship-to-other-modules section. Documents:

- The `$AIW_TIERS_PATH` env var + `~/.ai-workflows/tiers.yaml` default path.
- The replace-by-name merge rule.
- The "unknown tier in overlay warns + drops" behaviour.
- The `load_overlay()` + `TierRegistry.merge_overlay()` surface.
- Forward-link to `TieredNode` where fallback dispatch will live (T02).

## Acceptance Criteria

- [ ] **AC-1: `TierConfig.fallback` schema.** The field exists on `TierConfig`, defaults to `[]`, accepts flat lists of `LiteLLMRoute | ClaudeCodeRoute`, and rejects nested fallbacks at pydantic validation time.
- [ ] **AC-2: `load_overlay()` path resolution.** `$AIW_TIERS_PATH` env var wins; else `~/.ai-workflows/tiers.yaml`; else `None`. An explicit env-var path pointing at a missing file logs a structlog warning and returns `{}`.
- [ ] **AC-3: Overlay parse errors are loud.** A malformed overlay file raises `OverlayParseError` with the file path + pydantic validation error. No silent swallow.
- [ ] **AC-4: Merge rule is "replace by name."** Overlay entries whose names the workflow registry declares replace the workflow's `TierConfig`. Overlay entries whose names the workflow does not declare are dropped with a structlog warning naming the unknown tier + the workflow's known tier names.
- [ ] **AC-5: `_resolve_tier_registry()` integrated.** The dispatch-time call at `_dispatch.py` now applies the overlay. Workflows with no overlay present return the bare workflow registry (behaviour preserved).
- [ ] **AC-6: Hermetic tests land green.** `tests/primitives/test_tier_overlay.py` — 10 new tests covering path resolution, parse errors, merge rule, and the new `fallback` schema field. All pass.
- [ ] **AC-7: Existing tests stay green.** `tests/primitives/test_tiers_loader.py` adjusted (two edits) + one new integration test for the overlay path through `_resolve_tier_registry()`.
- [ ] **AC-8: Module docstring updated.** `ai_workflows/primitives/tiers.py` gains a new "Overlay loading (M15)" subsection.
- [ ] **AC-9: No behaviour change for no-overlay case.** Running `aiw run planner …` with no `$AIW_TIERS_PATH` set and no `~/.ai-workflows/tiers.yaml` file produces byte-identical dispatch behaviour to pre-T01. Verified by running `aiw run planner --goal 'smoke' --run-id t01-smoke` and checking the resolved tier registry matches `planner_tier_registry()` exactly.
- [ ] **AC-10: Four-layer contract preserved.** `uv run lint-imports` reports 4 kept, 0 broken. No `ai_workflows.graph` / `ai_workflows.workflows` / surface-layer imports leak into `primitives`.
- [ ] **AC-11: Gates green.** `uv run pytest` + `uv run lint-imports` + `uv run ruff check` on both branches.
- [ ] **AC-12: CHANGELOG entry.** `CHANGELOG.md` under `[Unreleased]` (both branches) — new `### Added — M15 Task 01: tier overlay loader + TierConfig.fallback schema (YYYY-MM-DD)` entry naming files touched, ACs satisfied, deviations from spec (if any).

## Dependencies

- **0.1.3 patch prerequisites.** T01 assumes the 0.1.3 patch has landed (or will be folded in): `tiers.yaml` has been cleaned of the misleading `planner` / `implementer` entries, and the per-workflow tier registries are the authoritative source. If 0.1.3 has not shipped, T01's work proceeds unchanged but the test-suite baseline numbers shift.
- **No runtime dependencies from earlier milestones beyond M1 (tier-config primitive) and M13 (0.1.0 release baseline).**

## Out of scope (explicit)

- **Any dispatch-layer cascade logic.** That's T02. T01 ships the schema + loader + merge; no `TieredNode` changes.
- **Cost-attribution changes.** T02 + T03 territory. `CostTracker` API is unchanged at T01.
- **`aiw list-tiers` CLI command.** T03 deliverable.
- **Relocating `tiers.yaml` → `docs/tiers.example.yaml`.** T04 deliverable. T01 works against whatever shape `tiers.yaml` has at T01 kickoff (post-0.1.3-patch).
- **Documentation rewrites in `docs/writing-a-workflow.md`.** T04 deliverable. T01 only touches the `tiers.py` module docstring.
- **Any change to `_mid_run_tier_overrides` (M8 T04 post-gate fallback).** M15's declarative fallback and M8's reactive override coexist. T02 validates both fire correctly in the same run; T01 does not touch the M8 surface.
- **MCP schema change.** No input/output models gain an "overlay" field. Per M15 README non-goals.

## Risks

1. **Path-lookup collisions on Windows / non-POSIX homes.** `Path.home() / ".ai-workflows" / "tiers.yaml"` may behave differently on Windows. Current mitigation: document the env-var override as the portable path; the default resolves per OS convention. A future Windows-support milestone would re-evaluate.
2. **Overlay entries silently dropped on typos.** A user who mistypes a tier name (`planner-sinth` instead of `planner-synth`) gets a structlog warning — but warnings may scroll past in an MCP HTTP session. Mitigation: `aiw list-tiers` (T03) prints the effective registry + overlay provenance, making drift discoverable. If this becomes a recurring UX issue, promote the warning to a CLI-startup-time check.
3. **Pydantic error messages on nested-fallback rejection.** Must be clear enough that a user reading the error knows *which* nested fallback tripped the check, not just "validation failed." The `@field_validator` message names the violating entry explicitly.
