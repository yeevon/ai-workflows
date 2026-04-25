# Task 06 — Milestone Close-out

**Status:** 📝 Planned.
**Grounding:** [milestone README](README.md) · [CLAUDE.md](../../../CLAUDE.md) close-out conventions · [M8 T06](../milestone_8_ollama/task_06_milestone_closeout.md) (pattern to mirror).

## What to Build

Close M10 **and publish `jmdl-ai-workflows==0.2.1` to PyPI**. Confirm
every exit criterion from the [milestone README](README.md). Update
[CHANGELOG.md](../../../CHANGELOG.md), flip M10 complete in
[roadmap.md](../../roadmap.md), refresh the root [README.md](../../../README.md)
where the M8/M10 fallback story is summarised, and run the M13 release
ceremony to publish the patch wheel.

**No code change beyond what M10 T01–T05 landed.** Any code finding
surfaced during close-out becomes a forward-deferred carry-over on the
next relevant task or a new `nice_to_have.md` entry, never a drive-by
fix.

Mirrors [M8 Task 06](../milestone_8_ollama/task_06_milestone_closeout.md)
for the close-out muscle memory and
[M13 T07](../milestone_13_v0_release/task_07_changelog_publish.md) +
[release_runbook.md](../milestone_13_v0_release/release_runbook.md) for
the publish ceremony.

## Why a publish at this milestone

T02 lands an operator-visible behaviour change (the new RETRY-cooldown
sentence in `render_ollama_fallback_prompt`) and an additive deprecation
warning on the public `build_ollama_fallback_gate` API. External KDR-013
workflow consumers (CS300 today; future workflow authors via M16's
loader) read this surface. Shipping the change without a publish would
leave consumers running 0.2.0 with no visible upgrade path, and would
bury the deprecation warning that exists specifically to give them a
migration window. **0.2.1 is a backward-compatible patch** (cooldown
sentence is purely additive; the `cooldown_s` kwarg stays optional with
a `DeprecationWarning` shim), so SEMVER-patch is the correct bump.

## Deliverables

### [README.md](README.md) (milestone)

- Flip **Status** from `📝 Planned` to `✅ Complete (<YYYY-MM-DD>)`.
- Append an **Outcome** section summarising:
  - **ADR-0003 ([task 01](task_01_fallback_tier_adr.md))** — the
    `fallback_tier="planner-synth"` decision is locked with three
    rationales (decoupled failure mode, no marginal API key, acceptable
    cost envelope). Both `OllamaFallback` constants cite the ADR.
  - **RETRY cooldown UX ([task 02](task_02_retry_cooldown_prompt.md))** —
    `render_ollama_fallback_prompt` and `build_ollama_fallback_gate`
    gain an optional `cooldown_s` kwarg under a `DeprecationWarning`
    shim (the flip from optional to required is deferred to a future
    minor release per T02's out-of-scope clause); when callers pass it,
    the rendered prompt names the actual breaker cooldown and warns the
    operator to wait wall-clock time before RETRY.
  - **Single-gate cross-workflow invariant test
    ([task 03](task_03_single_gate_invariant.md))** —
    [`tests/workflows/test_ollama_fallback_single_gate_invariant.py`](../../../tests/workflows/test_ollama_fallback_single_gate_invariant.py)
    composes a synthetic three-branch workflow, asserts one
    `record_gate('ollama_fallback')` call across N parallel `CircuitOpen`
    emissions, plus a plain-test negative control that proves the
    assertion is non-trivial. Architecture.md §8.4 grew a *"Composing
    the fallback path into a new parallel workflow"* subsection.
  - **Send-payload carry invariant test
    ([task 04](task_04_send_payload_invariant.md))** —
    [`tests/workflows/test_ollama_fallback_send_payload_carry.py`](../../../tests/workflows/test_ollama_fallback_send_payload_carry.py)
    pins `_mid_run_tier_overrides` carry into re-fired Send payloads;
    catches future `langgraph` upgrades that would silently change Send
    semantics.
  - **Documentation sweep ([task 05](task_05_doc_sweep.md))** —
    architecture.md §8.4 grew a **Limitations** paragraph (process-local
    breaker scope, heuristic tuning, single-level fallback). Five new
    `nice_to_have.md` entries (§23–§27) record deferred follow-ups with
    named triggers.
  - **Manual verification**: degraded-mode e2e smoke rerun once at
    close-out time with a real Ollama instance — three branches still
    green; the new RETRY cooldown sentence is observed in the rendered
    prompt. Procedure: follow the operator runbook in
    [tests/workflows/test_ollama_outage.py](../../../tests/workflows/test_ollama_outage.py)'s
    module docstring (the M8 T05 degraded-mode protocol — kill the
    Ollama daemon to force `connection_refused`, observe the breaker
    trip, exercise each `FallbackChoice` branch). The only M10
    addition to the M8 T05 protocol: confirm the new cooldown sentence
    appears in the rendered prompt and names the actual breaker
    cooldown value.
  - **Green-gate snapshot**: `uv run pytest`, `uv run lint-imports`
    (**4 contracts kept** — M10 added no layer contract), `uv run ruff
    check`.
- Keep the **Carry-over from prior milestones** section as written
  (currently *None*).

### [roadmap.md](../../roadmap.md)

Flip the M10 row `Status` from `planned` to `✅ complete (<YYYY-MM-DD>)`.
If the roadmap has separate columns for "shipped fixes" / "shipped tests"
/ "shipped docs", check each one against M10 T01–T05.

### [CHANGELOG.md](../../../CHANGELOG.md)

Promote accumulated `[Unreleased]` entries from M10 tasks into a dated
section `## [0.2.1] - <YYYY-MM-DD>` (versioned section, since the
publish ceremony below ships this slug to PyPI). Keep the top-of-file
`[Unreleased]` section intact and empty. Add a T06 close-out entry at
the top of the new dated section under the canonical heading
`### Changed — M10 Task 06: Milestone Close-out (<YYYY-MM-DD>)` —
mirror M13 T08's shape (see `CHANGELOG.md:269` for the canonical
close-out form), not M8 T06's (M8 T06 used a milestone-named section
because no publish was run; M13 T08 is the M13-era close-out and is
the right reference for a publish-bearing milestone close-out).
`### Changed` is the right Keep-a-Changelog kind for a close-out
because the close-out reframes existing landed surface rather than
introducing new behavioural surface. Record:

- The degraded-mode e2e smoke rerun at close-out time — commit sha
  baseline + the operator's pass/fail observation.
- The `uv run lint-imports` 4-contract snapshot confirming no new
  contracts landed at M10 (M10 is composition + docs, not new layers).
- ADR-0003 acceptance date + the rationale lock.
- The new architecture.md §8.4 *Composing the fallback path* subsection
  and the Limitations paragraph as the load-bearing doc additions of
  the milestone.
- `nice_to_have.md` slot drift recorded explicitly — the milestone
  README originally planned §17–§21; final slots are §23–§27 (T05
  reconciled this).

### Publish ceremony (0.2.0 → 0.2.1)

**Pre-publish gate.** The publish ceremony does **not** start until the
*Audit-before-close check* (below) reports zero open `🔴 HIGH` or
`🟡 MEDIUM` entries across `issues/task_0[1-5]_issue.md`. A failed
audit hard-stops the publish; the resolution lands as a doc edit
(or a forward-deferred carry-over to the next milestone) before the
publish ceremony begins (step 4 of the order-of-operations below; the
`__version__` bump itself is step 1 of the Pre-publish sub-list further
down). **Order of operations during T06:**

1. Run the *Audit-before-close check* (later in this spec) and resolve
   every finding it surfaces.
2. **Reconcile any residual `[Unreleased]` entries from earlier
   milestones.** Verify the `[Unreleased]` block contains only M10
   entries. If it still carries the M16 Task 01 / 0.2.0 entry that was
   never promoted to a dated section on `design_branch` (a pre-existing
   M16-close-out drift recorded against `main`'s already-published
   0.2.0 wheel), **first** promote that entry to a
   `## [0.2.0] - 2026-04-24` section above the new
   `## [0.2.1] - <today>` section to match `main`'s shape — then
   proceed with M10 promotion. If anything else is in `[Unreleased]`
   that does not belong to M10, stop and ask.
3. Land the close-out doc updates (milestone README outcome,
   roadmap, root README, CHANGELOG `## [0.2.1]` section with
   placeholder footer) — but **not** the `__version__` bump yet.
4. Once close-out docs are committed and the audit is clean, start
   the publish ceremony (steps 1–13 below) with the `__version__`
   bump as step 1.
5. After the post-publish smoke + footer stamp, this task is done.

Follow the M13-derived runbook. T06 is the first M10 task that commits
on **both** branches — the publish-side commit lands on `main`; the
post-publish footer cherry-picks back to `design_branch`. Below is the
M10-specific summary; the canonical procedure lives in
[release_runbook.md](../milestone_13_v0_release/release_runbook.md) and
[M13 T07](../milestone_13_v0_release/task_07_changelog_publish.md).

**Pre-publish (on `design_branch`):**

1. Bump `__version__` in
   [`ai_workflows/__init__.py`](../../../ai_workflows/__init__.py) from
   `"0.2.0"` to `"0.2.1"`.
2. Promote the accumulated `[Unreleased]` block to a dated `## [0.2.1] -
   <YYYY-MM-DD>` section in [CHANGELOG.md](../../../CHANGELOG.md). Keep
   `[Unreleased]` empty above it. Add a `### Published` footer **with
   placeholder values** (`<filled-in-post-publish>`) — the post-publish
   amendment fills them in.
3. Run `bash scripts/release_smoke.sh` — must report green.
4. Run the four standard gates: `uv run pytest`, `uv run lint-imports`
   (4 contracts kept), `uv run ruff check`, plus the
   `python -W error::DeprecationWarning` check from M10 T02's smoke.
5. Run `uv build`, then inspect the wheel contents per CLAUDE.md
   *Dependency audit gate*. Expected: only `ai_workflows/`, `LICENSE`,
   `README.md`, `CHANGELOG.md`, `<dist-info>/`. **Stop if** `.env*`,
   `design_docs/`, `runs/`, `*.sqlite3`, or any `tests/` content appears:

   ```bash
   unzip -l dist/jmdl_ai_workflows-0.2.1-py3-none-any.whl
   ```

6. Spawn the `dependency-auditor` agent on the wheel. If it raises
   anything, append findings to this task's issue file under a
   `Security` tag and resolve before publishing.

**Cherry-pick to `main`:** the `__version__` bump, the dated CHANGELOG
section, and the placeholder footer commit cleanly to `main`. **Stop and
get operator confirmation** before the next step (the irreversible one).

**Publish (on `main`):**

1. Operator confirmation checkpoint: print `git log -1 --oneline`, the
   wheel filename about to upload, and the `[0.2.1]` CHANGELOG block
   verbatim. Wait for explicit "proceed."
2. Verify name + version availability. Output must list `0.2.0` (and
   prior) but **not** `0.2.1`. If `0.2.1` already appears, **stop** —
   patch-bump to `0.2.2` and restart from pre-publish step 1:

   ```bash
   uv pip index versions jmdl-ai-workflows --index https://pypi.org/simple/
   ```

3. `set -a && source .env && set +a` to load `UV_PUBLISH_TOKEN`.
4. `uv publish dist/jmdl_ai_workflows-0.2.1-py3-none-any.whl`. This is
   the **irreversible** step — pypi.org never accepts a re-upload of
   the same `name + version` pair.

**Post-publish (back on `main`, then mirror to `design_branch`):**

1. Live install smoke from a clean directory. Expected output: `0.2.1`.
   Anything else is a hard-stop — open an issue on this task's issue
   file before doing anything else:

   ```bash
   cd /tmp && uvx --refresh --from jmdl-ai-workflows==0.2.1 aiw version
   ```

2. Stamp the `### Published` footer with real values:

   - `**URL:**` `https://pypi.org/project/jmdl-ai-workflows/0.2.1/`
   - `**Wheel:**` `jmdl_ai_workflows-0.2.1-py3-none-any.whl`
   - `**SHA256:**` from `pip download --no-deps jmdl-ai-workflows==0.2.1`
     then `sha256sum jmdl_ai_workflows-0.2.1-py3-none-any.whl`.
   - `**Publish-side commit:**` the `main` SHA that produced the
     uploaded wheel.
   - `**Pre-publish release-smoke:**` `scripts/release_smoke.sh` green
     from `main` at `<sha>` and the publish-side commit pair.

3. Commit the stamped footer on `main` and cherry-pick to
   `design_branch` so both branches mirror the public CHANGELOG.

### Root [README.md](../../../README.md)

Update to M10-closed state where M8 + M10 share the fallback narrative:

- **Status table** — M10 row → `✅ Complete (<YYYY-MM-DD>)`.
- **Narrative** — append a one-paragraph post-M10 note covering:
  - The cooldown-aware RETRY prompt (the only operator-visible change).
  - The two new invariant tests as regression guards for the M8 design.
  - The §8.4 Limitations paragraph as the explicit charter for the
    single-process / heuristic-tuning / single-level-fallback
    assumptions.
- **What runs today** — keep the M8 bullets; if M9/M10 ordering shifts
  what "next" points at, update the **Next →** pointer accordingly.

Section-heading rename: `post-M8` → `post-M10` (or insert a new
`post-M10` heading if the M8 content is preserved as historical).

### [architecture.md](../../architecture.md) §8.4 reconciliation

Re-read §8.4 end-to-end and confirm:

- The four-step recipe subsection (T03) and the Limitations paragraph
  (T05) are both present.
- The §8.4 references to T03's invariant test and T04's Send-payload
  test exist and resolve to actual files (the Auditor confirms both
  paths under `tests/workflows/`).
- The seven KDR table at §9 is unchanged — M10 added no KDR.

### Audit-before-close check

The close-out Builder opens **every** M10 task issue file
(`design_docs/phases/milestone_10_ollama_hardening/issues/task_0[1-5]_issue.md`)
and confirms:

- No OPEN `🔴 HIGH` or `🟡 MEDIUM` entries.
- Every `DEFERRED` entry has a matching carry-over in its target task
  spec (propagation discipline, [CLAUDE.md](../../../CLAUDE.md)
  *Forward-deferral propagation*).
- Every `nice_to_have.md` deferral has a §N reference recorded — and the
  §N references match the **landed** numbering (§23–§27, not §17–§21).

Any hole found is the close-out's to fix in-audit (doc maintenance only,
not code). If a gap can't be closed with a doc edit, stop and ask the
user.

## Acceptance Criteria

**Close-out:**

- [ ] Every exit criterion in the milestone [README](README.md) has a
      concrete verification (paths / test names / issue-file links).
- [ ] `uv run pytest && uv run lint-imports && uv run ruff check`
      green on a fresh clone; `lint-imports` reports **4 contracts kept**.
- [ ] Close-out CHANGELOG entry records the degraded-mode e2e smoke
      rerun at close-out time (commit sha + three-branch observation).
- [ ] Close-out CHANGELOG entry records the ADR-0003 acceptance date.
- [ ] Close-out CHANGELOG entry records the `nice_to_have.md` slot drift
      (planned §17–§21 → landed §23–§27).
- [ ] Close-out CHANGELOG entry uses the canonical heading
      `### Changed — M10 Task 06: Milestone Close-out (<YYYY-MM-DD>)`
      (mirroring M13 T08's shape at `CHANGELOG.md:269`).
- [ ] M10 milestone README **and** roadmap reflect
      `✅ Complete (<YYYY-MM-DD>)`.
- [ ] Root README updated: status table, post-M10 narrative,
      What-runs-today reconciled.
- [ ] architecture.md §8.4 has both the four-step recipe (T03) and the
      Limitations paragraph (T05) landed in place; no new KDR.
- [ ] All M10 task issue files audited for propagation holes; any gap
      closed or escalated.
- [ ] Residual `[Unreleased]` reconciliation completed before the
      `## [0.2.1]` promotion: any pre-existing M16-close-out drift on
      `design_branch` (the M16 Task 01 entry that landed pre-M10) was
      promoted to `## [0.2.0] - 2026-04-24` to match `main`'s shape, or
      the operator confirmed `[Unreleased]` contained only M10 entries.

**Publish (0.2.0 → 0.2.1):**

- [ ] `ai_workflows/__init__.py:__version__` bumped to `"0.2.1"` on
      both `design_branch` and `main`.
- [ ] CHANGELOG has a dated `## [0.2.1] - <YYYY-MM-DD>` section
      (version-tagged, not milestone-tagged); `[Unreleased]` preserved
      at the top and empty.
- [ ] `bash scripts/release_smoke.sh` reported green from both
      `design_branch` and the publish-side `main` commit.
- [ ] `unzip -l dist/jmdl_ai_workflows-0.2.1-py3-none-any.whl` contains
      only `ai_workflows/`, `LICENSE`, `README.md`, `CHANGELOG.md`,
      `<dist-info>/` — no `.env*`, no `design_docs/`, no `runs/`, no
      `*.sqlite3`, no `tests/`.
- [ ] `dependency-auditor` agent ran on the wheel and reported no open
      `🔴 HIGH` or `🟡 MEDIUM` findings.
- [ ] Operator-confirmation checkpoint completed before `uv publish`
      (printed `git log -1 --oneline`, wheel filename, and CHANGELOG
      block; explicit "proceed" recorded in the issue file).
- [ ] `uv publish` succeeded; `uvx --refresh --from
      jmdl-ai-workflows==0.2.1 aiw version` from `/tmp` reports `0.2.1`.
- [ ] `### Published` footer in CHANGELOG `[0.2.1]` block stamped with
      real URL, wheel filename, SHA256, publish-side commit, and
      pre-publish smoke commit pair — on both branches.

## Dependencies

- [Task 01](task_01_fallback_tier_adr.md) through [Task 05](task_05_doc_sweep.md).

## Out of scope (explicit)

- **Any code change beyond what M10 T01–T05 landed.** Close-out is
  doc + version-bump + publish; any code finding flows to next-milestone
  carry-over or `nice_to_have.md`.
- **Any retroactive edit to the M10 README's task table** beyond the
  slot-drift reconciliation T05 owned. The README's other sections were
  validated at T01 kickoff.
- **A SEMVER-minor or -major bump.** 0.2.0 → 0.2.1 is the correct shape:
  T02's deprecation shim keeps the public API backward-compatible, and
  the cooldown sentence is purely additive. A minor or major bump would
  warrant external announcement and a migration period; a patch does
  not.
- **`cooldown_s` flip from optional to required.** Stays optional this
  release. The deprecation warning is the migration signal; the flip
  happens at a future minor version when external workflow consumers
  have had time to migrate.

## Carry-over from prior milestones

*None.* M9 close-out clean (when it lands) or M9 not-yet-active does not
gate M10 close-out — M10 stands alone as a M8 hardening pass and does
not require M9 to be complete.

## Carry-over from prior audits

Populated by the Builder as M10 T01–T05 audits complete. Forward-deferred
items from those audits land here, each ticked when the close-out absorbs
them.

## Carry-over from task analysis

- [ ] **TA-LOW-06 — CHANGELOG `[0.2.1]` promotion described twice**
      (severity: LOW, source: task_analysis.md round 4)
      The CHANGELOG `## [0.2.1]` promotion is described twice — once in
      the order-of-operations step 3 (close-out doc-updates phase) and
      once in Pre-publish step 2 (publish-ceremony phase). A Builder
      reading both will either do it twice (the second pass is a no-op
      the first time it ran cleanly, but creates a confusing diff), or
      get confused about whether the `[0.2.1]` promotion is part of the
      close-out commit or part of the publish-ceremony commit.
      **Recommendation:** At implement time, treat order-of-operations
      step 3 as canonical (the CHANGELOG promotion lands as part of the
      close-out commit, mirroring M13 T08); read Pre-publish step 2 as
      a verify-step that confirms the close-out commit's CHANGELOG
      block is intact before `uv build`. If a future revision of T06 is
      needed, collapse Pre-publish step 2 into an explicit verify-clause.
