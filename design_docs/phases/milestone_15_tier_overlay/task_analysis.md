# M15 — Task Analysis (Round 3, T04 only)

**Round:** 3 | **Analyzed on:** 2026-04-30 | **Analyst:** task-analyzer agent
**Specs analyzed:** `task_04_adr_0006_and_tiers_doc_relocation.md`
(T01–T03 ✅ shipped; T05 close-out not yet drafted.)

## Summary

| Severity | Count |
| --- | --- |
| 🔴 HIGH | 0 |
| 🟡 MEDIUM | 0 |
| 🟢 LOW | 1 |

**Stop verdict:** LOW-ONLY

Round-2 fixes status:

- **H3** (`tests/test_scaffolding.py` parametrize) — ✅ resolved. Spec now contains a new
  Deliverable 3a (lines 69–71) calling out the parametrize-list update with the exact file path
  (`tests/test_scaffolding.py:113-127`, entry at line 117). Verified literally:
  `test_scaffolding.py:113-127` is the parametrize block; line 117 is `"tiers.yaml",`. AC-4
  (line 140) now reads "Five committed-file references update cleanly: four in
  `tests/primitives/test_tiers_loader.py` … and one in `tests/test_scaffolding.py`
  (parametrize entry replaced with `"docs/tiers.example.yaml"`)" — matches the deliverable.
- **M4** (heading anchor `### Tier registry (\`tiers=\`)`) — ✅ resolved. Verified at
  `docs/writing-a-workflow.md:36`. Both Deliverable C (line 14) and Deliverable 4 (line 75) now
  read "the existing `### Tier registry (`tiers=`)` subsection" with line-36 cited explicitly
  in Deliverable C. Heading topology re-checked: line 36 (`### Tier registry (`tiers=`)`) →
  line 68 (`### Minimum viable spec`) — sibling-H3 insertion remains structurally sound.
- **L3** (Dependencies section `yaml_path` line) — ✅ resolved. Spec line 179 now reads
  *"No production-code dependency — T04 is documentation + test-path update only.
  `ai_workflows/primitives/tiers.py` is unchanged."* TA-LOW-03 carry-over entry (lines 208–
  209) records the round-2 history correctly.

`_load_example_tiers()` helper shape re-verified end-to-end:

- `TierConfig` (`ai_workflows/primitives/tiers.py:84-122`) requires `name` + `route`; defaults
  `max_concurrency=1`, `per_call_timeout_s=120`, `fallback=[]`.
- The committed `tiers.yaml` shape (`<key>: {route: {...}, max_concurrency: …,
  per_call_timeout_s: …}`) is exactly what `TierConfig.model_validate({**v, "name": k})`
  expects when `k` is the dict key and `v` is the per-tier mapping.
- The four assertions hit by the four named tests (`set(tiers) == {"local_coder", "opus",
  "sonnet", "haiku"}`, `isinstance(.route, LiteLLMRoute)`, `.cli_model_flag == "opus"`,
  `.model.startswith("ollama/")`) all remain valid against `_load_example_tiers()`'s return
  type `dict[str, TierConfig]`. ✅

---

## Findings

### 🟢 LOW

#### L4 — `tests/test_wheel_contents.py:150, 170` strings still mention `tiers.yaml` (informational)

**Task:** T04
**Issue:** `tests/test_wheel_contents.py:150` (docstring) and `tests/test_wheel_contents.py:170`
(`f"Repo-root `tiers.yaml` / `pricing.yaml` are dev-time only and …"`) still mention
`tiers.yaml` after T04 deletes the file. The test logic is unaffected — the invariant pinned
is "no bare-root `*.yaml` files in the wheel"; that remains true after `tiers.yaml` is moved
under `docs/`. The mention is a stale-but-harmless string.

**Recommendation:** Push to spec carry-over (informational; the Builder may optionally tidy
the docstring/error-message during T04 but is not required to). The wheel-contents test will
continue to pass unchanged.

**Push to spec:** add to T04's "Carry-over from task analysis" section:

> **TA-LOW-04 — `tests/test_wheel_contents.py` docstring + error message reference
> `tiers.yaml`** (severity: LOW, source: task_analysis.md round 3)
> The wheel-contents test at `tests/test_wheel_contents.py:150, 170` still names
> `tiers.yaml` in its docstring + assertion message. Test logic is unaffected (the
> invariant — "no bare-root `*.yaml` in the wheel" — is unchanged), but the string is
> mildly stale after T04.
> **Recommendation:** Optionally update the strings to read `docs/tiers.example.yaml`
> while in the file; non-blocking.

---

## What's structurally sound

- **H3 / M4 / L3 round-2 fixes all land cleanly.** Deliverable 3a is well-scoped and
  specific (file path, line range, exact entry to replace). M4 anchor text now matches
  `docs/writing-a-workflow.md:36` literally. Dependencies §line is internally consistent
  with Deliverable 3 + Out-of-scope §1.
- **`_load_example_tiers()` helper shape correct.** Cross-checked against `TierConfig`
  Pydantic model — required fields `name` + `route`, all others default. Helper signature
  `dict[str, TierConfig]` is exactly what the four named tests expect.
- **`REPO_ROOT` preservation correctly justified.** `test_committed_pricing_yaml_has_only_
  claude_cli_entries` (line 328 — verified) still loads `pricing.yaml` via `REPO_ROOT`; all
  `_write(tmp_path / "tiers.yaml", …)` helpers (verified at lines 178, 200, 212, 224, 236,
  252, 272, 310) still need `tmp_path`-rooted writes. Both classes of caller stay correct.
- **AC-1 / AC-4 enumerations match the file.** AC-1 seven §Decision points map 1:1 to
  Deliverable 1's seven numbered items (line 27). AC-4 names the five expected references
  (4 + 1) precisely.
- **AC-7 (`uv run pytest`) is now achievable.** With Deliverable 3a in place, both the
  loader-test suite (4 tests) and the scaffolding-files invariant (1 parametrize entry)
  flip together.
- **Out-of-scope discipline.** Forecloses `tiers.py` edits, `AIW_TIERS_PATH`,
  `~/.ai-workflows/tiers.yaml`, YAML-fallback authoring — all explicitly out per
  rescoping.
- **No KDR drift.** No layer violations, no Anthropic SDK imports, no validator skips, no
  bespoke retry, no SqliteSaver edits. Doc + test-path-update only.
- **Status surfaces handled correctly.** Deliverable 6 names all four surfaces; exit
  criteria #7 + #8 correctly noted as milestone-level (T05 close-out flips them).
- **ADR file path open.** Verified `design_docs/adr/0006_tier_fallback_cascade_semantics.md`
  does not yet exist (next free slot is 0006 — present ADRs are 0001, 0002, 0004, 0005,
  0007, 0008, 0009, 0010 — no 0003 or 0006 collision).

## Cross-cutting context

- **Project memory check.** `MEMORY.md` is consistent — M15 rescoped 2026-04-30, T04 is
  doc-only territory; no on-hold flag for T04.
- **CHANGELOG entry not yet drafted** — Deliverable 5 calls for one. No conflict with
  `[Unreleased]`.
- **importlinter contract count drift** (carry-over from round 1, surfaces at T05). AC-8
  says "5 contracts kept, 0 broken"; M15 README line 55 still says "4 contracts kept" —
  README copy drift. Already noted in round 1; will surface at T05 close-out spec authoring.
- **`test_wheel_contents.py` invariant.** The "no bare-root `*.yaml` in the wheel" check
  in `test_built_wheel_excludes_dotenv_and_loose_yaml` continues to pass after T04 — the
  file is moved (still in repo source tree, just under `docs/`) but the wheel-builder
  convention (`packages = ["ai_workflows"]`) excluded it before and excludes it after.
  L4 above is the only stale-string remnant (informational).
- **Existing ADRs as templates.** ADR-0004 + ADR-0009 verified to exist; both follow
  Status / Context / Decision / Alternatives / Consequences shape that Deliverable 1
  inherits.
- **Sibling task consistency.** T01 / T02 / T03 cross-references all resolve cleanly
  post-T04; no re-edits needed in shipped specs.

---

**Round 3 verdict:** spec is at LOW-ONLY. The single LOW (L4) is informational and
non-blocking — push to spec carry-over and proceed to `/clean-implement m15 t04`.
