# M15 — Task Analysis
**Round:** 1 | **Analyzed on:** 2026-04-30 | **Analyst:** task-analyzer agent
**Specs analyzed:** `task_01_overlay_and_fallback_schema.md` (T02–T05 follow incremental-spec convention; not analyzed)

## Summary
| Severity | Count |
| --- | --- |
| 🔴 HIGH | 5 |
| 🟡 MEDIUM | 4 |
| 🟢 LOW | 3 |

**Stop verdict:** OPEN

The M15 milestone (drafted 2026-04-23) and T01 (drafted alongside the README) **predate** KDR-014 + ADR-0009 (proposed 2026-04-27, locked in M12 close-out 2026-04-29). KDR-014 explicitly names "tier defaults" and "fallback chains (M15)" as quality knobs that live in **module-level constants per workflow** with **env-var operator override**, NOT user-supplied YAML overlay. The entire M15 design direction — `~/.ai-workflows/tiers.yaml` overlay, "user owns the rebind" — directly contradicts the live KDR-014 mirror principle (framework owns quality policy). Most M15 surface assumptions are also stale: package is at 0.3.1 (M15 expected to ship 0.2.0); M16 already shipped without M15 as precondition; project memory flags M15 as on standby pending CS300 trigger. **This requires user arbitration before any code lands.** Findings H1–H3 collectively rise to a stop-and-ask.

## Findings

### 🔴 HIGH

#### H1 — M15 design direction conflicts with KDR-014 (framework owns quality policy)
**Task:** T01 (and the milestone as a whole)
**Location:** `design_docs/architecture.md:295` (KDR-014) · `design_docs/adr/0009_framework_owns_policy.md:154` ("fallback chains (M15)" listed as quality knob in module constants)
**Issue:** KDR-014 (locked 2026-04-29) explicitly states: *"Quality knobs (audit cascade, validator strictness, retry budget defaults, **tier defaults**, **fallback chains**, audit-failure escalation thresholds) live in module-level constants in each workflow source file — never on `*Input` pydantic models, `WorkflowSpec` fields, CLI flags on `aiw run`, or MCP tool input schemas. The only operator-side override path is environment variables."* ADR-0009 §Consequences/Positive bullet 5 explicitly lists "fallback chains (M15)" as an example of where this pattern applies. The M15 README's central thesis — *"workflow owns the default; user owns the rebind"* via `~/.ai-workflows/tiers.yaml` YAML overlay — is the precise pattern KDR-014 rejects. Tier rebinding through user YAML is operator-equivalent override, but KDR-014 names env-vars (not config files) as the legitimate operator escape hatch.
**Recommendation:** **Stop and ask the user.** This is not a fixable spec drift; it's a scope/architecture conflict. Three legitimate resolutions: (a) retract M15 in favour of env-var-driven module-constant overrides per KDR-014 (`AIW_TIER_PLANNER_SYNTH_ROUTE=...`); (b) amend KDR-014 to carve out a YAML-overlay exception specifically for tier routing (with a new ADR explaining why tier routing is operator-territory whereas cascade/validator-strictness is framework-territory); (c) abandon M15 entirely if the underlying need (CS300 wheel-installable provider rebinding) has been overtaken by M16's external workflows path. The user picks; the analyzer cannot.
**Apply this fix:** *Stop and ask the user* before any further M15 work.

#### H2 — KDR-012 + ADR-0006 slot are unowned but the milestone treats them as load-bearing
**Task:** Milestone-level (T01 doesn't introduce them; T04 does — but T01's correctness depends on them existing)
**Location:** `design_docs/architecture.md:283-295` · `design_docs/adr/`
**Issue:** Milestone README exit-criteria 10–11 propose "KDR-012" and "ADR-0006." Verified: architecture.md §9 jumps from KDR-011 directly to KDR-013, KDR-014 (no KDR-012 slot exists, was skipped). The ADR slot 0006 is also unused (existing ADRs: 0001, 0002, 0004, 0005, 0007, 0008, 0009; 0003 + 0006 are gaps). So the slot numbers are syntactically free — but the **content** of the proposed KDR-012 directly contradicts KDR-014 (see H1). Adopting KDR-012 as drafted in the README would require either rescinding KDR-014's "fallback chains" and "tier defaults" coverage, or accepting two KDRs that contradict each other.
**Recommendation:** Resolve H1 first. If H1 resolves toward (b) "amend KDR-014 to carve out tier routing," the proposed KDR-012 needs to be drafted to **explicitly cite KDR-014 as superseded for tier routing** and explain the carve-out. If H1 resolves toward (a) "retract M15," KDR-012 is not added at all.
**Apply this fix:** Block on H1 resolution.

#### H3 — Spec line numbers and integration point are factually wrong
**Task:** T01
**Location:** `task_01_overlay_and_fallback_schema.md` "Grounding" line 4 + Deliverable §2 line 62
**Issue:** Spec cites `_resolve_tier_registry()` at "lines 220-230" of `_dispatch.py`. Verified: the function actually lives at lines 264-274 (`grep -n "def _resolve_tier_registry" ai_workflows/workflows/_dispatch.py`). More important: the spec's proposed integration replaces the body but does not address `_apply_tier_overrides()` (lines 155-180), which is the M5 T05 mid-pipeline mutation step that already runs **after** `_resolve_tier_registry()` returns and **before** the registry is threaded into `cfg`. The drafted T02 dispatch call site (`run_workflow` line 581-582) shows the order: `base_registry = _resolve_tier_registry(...)` → `tier_registry = _apply_tier_overrides(base_registry, tier_overrides)`. The spec's design assumes a clean two-step (workflow registry → overlay) but reality is a three-step (workflow registry → overlay → per-call `tier_overrides`). Builder needs to know whether the overlay applies before or after `tier_overrides` and what happens when both touch the same tier name.
**Recommendation:** Update T01 line 4 to cite the correct line range (264-274 as of HEAD `d101ced`). Add an explicit decision in §2 about composition order with `_apply_tier_overrides`: pre-overlay or post-overlay. Recommended order is `workflow_registry → load_overlay → merge_overlay → _apply_tier_overrides` (overlay rebinds the tier; per-call override remaps after — same precedence chain as today: framework default → operator config → per-call override). Add an AC pinning this with a test.
**Apply this fix:** Re-grep `_dispatch.py` for the current line range; rewrite §2 of T01 with the three-step composition explicit.

#### H4 — Roadmap version target (0.2.0) is two minor versions stale
**Task:** Milestone-level
**Location:** `design_docs/roadmap.md:56` · `ai_workflows/__init__.py:33` (`__version__ = "0.3.1"`)
**Issue:** Roadmap says "M15 ... Ships `0.2.0`." Live `__version__` is already `0.3.1` (M16 shipped 2026-04-24 as 0.3.0; 0.3.1 patch landed per memory `project_0_3_1_live.md`; M19 shipped under 0.3.x). M15 cannot ship as 0.2.0 — that version range is past. Per project memory `project_m13_shipped_cs300_next.md`, post-0.2.0 the project pivoted to CS300; M15 is on standby pending CS300 return-trigger. The README states "**M13 (v0.1.0 release) — prerequisite. M15 is the first post-release feature milestone. Ships as `0.2.0`**" — but **0.2.0 was the first post-release minor and has already been used** for unrelated post-M13 work.
**Recommendation:** If H1 resolves toward proceeding with M15: update README §Dependencies to remove the "first post-release feature milestone" framing, target `0.4.0` (or whatever the next minor is when M15 actually ships), update the schema's "NEW in 0.2.0 (M15 T01)" comment in §3 of T01 to "NEW in 0.X.0 (M15 T01)" with the version chosen at landing time. If H1 resolves toward retraction, this finding evaporates.
**Apply this fix:** Replace `0.2.0` with TBD-at-landing in README + T01; remove "first post-release feature milestone" framing.

#### H5 — Roadmap claim "M15 is precondition for M16 + M17" is invalidated
**Task:** Milestone-level
**Location:** `design_docs/roadmap.md:29` (M16 shipped 2026-04-24) · `roadmap.md:56` (M15 still "📝 planned ... precondition for M16 + M17")
**Issue:** README §Dependencies claims "M16 (external workflows) — M15 is precondition. ... M15 ships first so M16's load-path has a stable tier surface to target." Verified false: M16 already shipped on 2026-04-24 (roadmap.md line 29: ✅ complete) without M15 ever landing. The dependency relationship recorded in the README is contradicted by reality. The "stable tier surface" framing was speculative; M16 succeeded without it.
**Recommendation:** Update README §Dependencies to reframe M16 as "shipped without M15"; reframe M17 dependency from "precondition" to "composes with if both ship" (M17 is also still planned per roadmap line 30). Note the order inversion in the milestone's open-questions section — the user may want to redirect M15 entirely toward solving the gap M16 actually exposed.
**Apply this fix:** Rewrite README §Dependencies M16/M17 paragraphs to reflect actual landed state.

### 🟡 MEDIUM

#### M1 — Spec docstring claim "_LOG = structlog.get_logger" but tiers.py imports no structlog
**Task:** T01
**Location:** `task_01_overlay_and_fallback_schema.md` Deliverable §1 line 50 (`_LOG.warning(...)`) · `ai_workflows/primitives/tiers.py:1-47` (no structlog import)
**Issue:** T01 §1 uses `_LOG.warning("unknown_tier_in_overlay", ...)` syntax in `merge_overlay()`, but the live `ai_workflows/primitives/tiers.py` has no `import structlog` and no `_LOG` module-level binding. Builder needs to know to add the import + binding. Tests "test_overlay_explicit_path_missing_warns_and_returns_empty" + "test_merge_overlay_unknown_name_warns_and_drops" require structlog capture — capturing structlog kwargs in pytest needs the structlog testing helpers (`structlog.testing.capture_logs` or similar). Spec doesn't specify the test pattern.
**Recommendation:** Add to T01 §1 an explicit "add `import structlog` + `_LOG = structlog.get_logger(__name__)` to module top". Add to §4 a one-liner about the test's structlog-capture pattern (`with structlog.testing.capture_logs() as captured: ...`).
**Apply this fix:** Insert the import note + test-helper note in T01.

#### M2 — `_resolve_overlay_path()` has a footgun: env-var path missing returns None silently
**Task:** T01
**Location:** `task_01_overlay_and_fallback_schema.md` Deliverable §1 lines 23-31 + AC-2 line 155
**Issue:** AC-2 says *"An explicit env-var path pointing at a missing file logs a structlog warning and returns `{}`."* — but the helper code in §1 lines 23-31 returns `None` silently with no warning emission. The helper as drafted: `return p if p.exists() else None`. The warning has to fire **somewhere** — either inside `_resolve_overlay_path()` or inside `load_overlay()` immediately after, otherwise AC-2 is unfalsifiable. Test `test_overlay_explicit_path_missing_warns_and_returns_empty` (§4 line 126) requires the warning fires.
**Recommendation:** Either (a) move the warning into `_resolve_overlay_path()` directly with an `_LOG.warning("aiw_tiers_path_missing", path=str(p))` before returning None; or (b) make `_resolve_overlay_path()` return a 2-tuple `(path | None, env_var_was_set: bool)` so `load_overlay()` knows to warn. (a) is simpler; pin it in the spec.
**Apply this fix:** Update §1 helper to emit the warning before returning None when env-var was set but file missing.

#### M3 — Schema design: `fallback: list[Route]` reuses the discriminated union but T01 §3 spells the type out twice
**Task:** T01
**Location:** `task_01_overlay_and_fallback_schema.md` Deliverable §3 lines 91-95
**Issue:** The live `ai_workflows/primitives/tiers.py` already exports `Route = Annotated[LiteLLMRoute | ClaudeCodeRoute, Field(discriminator="kind")]` at module scope (line 80). T01 §3 redefines the inline `Annotated[...]` annotation for `fallback`, duplicating the discriminator boilerplate instead of reusing `Route`. This isn't a bug (the redundant form is equivalent) but it makes the diff noisier and creates two places where future schema-shape edits must be kept in sync.
**Recommendation:** Use `fallback: list[Route] = Field(default_factory=list, description=...)` — single line, references the existing alias.
**Apply this fix:** Replace §3's `fallback: list[Annotated[...]]` with `fallback: list[Route]`.

#### M4 — Status-surface-discipline gap: T01 specifies CHANGELOG entry + spec status flip but not the milestone-README task-table row
**Task:** T01
**Location:** `task_01_overlay_and_fallback_schema.md` AC-12 + non-negotiable status-surface rule (CLAUDE.md)
**Issue:** AC-12 names CHANGELOG entry. Standard four-surface flip per CLAUDE.md "Status-surface discipline" requires also flipping (a) per-task spec `**Status:**` line, (b) milestone README task-order table row (line 88, currently no checkmark column — the README uses `Kind` not status), and (d) milestone README "Done when" / Exit-criteria checkboxes (the README has 13 numbered exit criteria; T01 satisfies items 1, 2, 3, ~half of 4 if "schema only", and item 12's first bullet). Spec doesn't enumerate which boxes T01 ticks, leaving it for the Builder to figure out.
**Recommendation:** Add AC-13: "Status surfaces flipped: (a) T01 spec **Status:** flipped from 📝 Planned to ✅ Complete with date; (b) milestone README task-order table row 01 marked complete (add a status column or convention); (c) exit-criteria items 1, 2, 3, and the schema-portion of 4 + 12 ticked."
**Apply this fix:** Add the status-surface AC enumerating the specific README exit-criteria items T01 satisfies.

### 🟢 LOW

#### L1 — Carry-over: prefer the existing `_deep_merge` style over a new `dict(workflow_registry); for ...`
**Task:** T01
**Issue:** T01 §1's `merge_overlay()` is a hand-rolled loop; the live `ai_workflows/primitives/tiers.py:148-162` already has a `_deep_merge` helper. The merge semantics differ (`merge_overlay` is replace-by-name only; `_deep_merge` recurses into dicts), so the new helper is needed — but a comment in the new helper noting "intentionally not _deep_merge — overlay tier replacement is whole-config replace, not field-merge" prevents a future Builder from "fixing" this into a deep-merge call.
**Recommendation:** Push to T01 carry-over.
**Push to spec:** *"Carry-over: add a one-line comment in `TierRegistry.merge_overlay()` noting why this isn't `_deep_merge` (whole-config replace by name, not field merge)."*

#### L2 — Carry-over: AC-9 byte-identical assertion is unfalsifiable as written
**Task:** T01
**Issue:** AC-9 says *"Running `aiw run planner --goal 'smoke' --run-id t01-smoke` ... produces byte-identical dispatch behaviour to pre-T01."* "Byte-identical" is undefined for a network-calling subprocess; the actual check is "the resolved tier registry returned by `_resolve_tier_registry('planner', planner_module)` equals `planner_tier_registry()` when no overlay is set." Pin that check, not "byte-identical."
**Recommendation:** Push to T01 carry-over.
**Push to spec:** *"Carry-over: rewrite AC-9 as 'with `AIW_TIERS_PATH` unset and `~/.ai-workflows/tiers.yaml` absent, `_resolve_tier_registry('planner', planner_module) == planner_tier_registry()`. Use a `monkeypatch.delenv` + `monkeypatch.setattr(Path, 'home', ...)` to a tmp dir without the file.'"*

#### L3 — Carry-over: `tiers.yaml` repo-root header comment already discusses M15 forward-looking work — confirm T01 doesn't fight it
**Task:** T01
**Issue:** The committed `tiers.yaml` (line 36-39) already has a header comment forward-referencing M15: *"M15 introduces `AIW_TIERS_PATH` + `~/.ai-workflows/tiers.yaml` as a user-supplied overlay..."*. Builder should leave this header comment alone (T01 doesn't relocate the file — that's T04) but be aware the comment exists.
**Recommendation:** Push to T01 carry-over.
**Push to spec:** *"Carry-over: do not edit the `tiers.yaml` header comment in T01 — the M15 forward-reference there matches T01's actual schema landing; T04 finishes the relocation."*

## What's structurally sound

- **The four-layer respect.** T01 correctly places overlay loader + schema in `primitives/`; cascade dispatch is explicitly deferred to T02 in `graph/`. Layer rule respected.
- **The non-goals list.** Comprehensive and correct: no role vocabulary, no new route kinds, no score-based routing, no immediate error-class fallback, no MCP schema change. These pre-emptively close obvious scope creep.
- **The "no nested fallbacks" architectural lock.** ADR-0006 (when authored) will have a clean rejected-alternatives section; the rationale (avoid infinite chains) is sound.
- **Hermetic test discipline.** All proposed tests are tmp_path-scoped, no provider calls, no disk I/O outside tmp_path. Matches project convention.
- **The "replace by name" merge semantic** is clean and matches user-visible mental models: workflow registers `{planner-synth: opus}`; user wants `{planner-synth: sonnet}`; user writes one entry, not a partial-field merge that requires understanding the schema. Good UX.
- **Out-of-scope list** is precise — `_mid_run_tier_overrides`, `aiw list-tiers`, the relocation, and `_dispatch._apply_tier_overrides` are all correctly carved out (modulo H3's `_apply_tier_overrides` ordering question).

## Cross-cutting context

- **Project memory says M15 is on standby pending CS300 return-trigger** (`project_m13_shipped_cs300_next.md`, `project_m10_specs_clean_pending_implement.md`). H1 is best resolved in the same conversation as "is the CS300 trigger live now?" The user's answer to "do we still need M15?" may render H1–H5 moot.
- **Slot drift on `nice_to_have.md`**: highest-numbered slot is §25 (EvalRunner replay for cascade fixtures, added in M12 close-out 2026-04-29). The forward-deferral candidates listed in the README §Propagation status (lines 119-122) are unnumbered — which is fine, since they'd be added at audit time. No slot drift in T01 itself.
- **CS300 framing in the README is load-bearing for the milestone's existence**: line 13 says *"Both gaps are CS300-relevant."* If CS300 has since absorbed both gaps via its own workflow modules (M16's external-workflow path landing on 2026-04-24), the underlying need may have evaporated. The user should confirm before re-investing in M15.
- **No conflicts with the seven load-bearing KDRs** (002 / 003 / 004 / 006 / 008 / 009 / 013) at the *T01-deliverable level*. The conflict is exclusively with KDR-014 (added after M15 was drafted). This is the cleanest case for "stop and ask the user about precedence."

## Stop-and-ask summary

The single decision the user must make before any code lands: **Does M15's "user-owned YAML overlay rebinds tier routing" framing supersede KDR-014's "framework owns tier defaults; env-var is the only operator override," or does KDR-014 retire M15 in favour of a smaller env-var-driven solution?**

All five HIGH findings flow from this one decision. Resolve it; everything else can be patched in a second-round task analysis.
