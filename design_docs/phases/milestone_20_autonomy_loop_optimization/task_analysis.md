# M20 — Autonomy Loop Optimization — Task Analysis

**Round:** 1
**Analyzed on:** 2026-04-27
**Specs analyzed:** task_01, task_02, task_03, task_04, task_05, task_06, task_07, task_08, task_09, task_20, task_21, task_22, task_23, task_27, task_28 (15 specs)
**Analyst:** task-analyzer agent
**Working location:** `/home/papa-jochy/prj/ai-workflows-m20/` (worktree on `workflow_optimization` branch)

## Summary

| Severity | Count |
| --- | --- |
| 🔴 HIGH | 6 |
| 🟡 MEDIUM | 17 |
| 🟢 LOW | 8 |
| Total | 31 |

**Stop verdict:** OPEN

(6 HIGH + 17 MEDIUM block the loop; 8 LOW would normally push to spec carry-over but cannot land until HIGH/MEDIUM clear.)

---

## Findings

### 🔴 HIGH

#### H1 — T22 references nonexistent `ai_workflows/orchestration/` module that contradicts its own spec

**Task:** task_22_per_cycle_telemetry.md
**Location:** task_22 §Deliverables, line 41–43:
> `### Telemetry wrapper module — `ai_workflows/orchestration/telemetry.py` (NEW, repo-side runtime)`
> `A small Python module that the slash-command orchestrator imports (or invokes via a one-liner) at every Task spawn boundary. **Wait — the slash commands are markdown procedure documents, not Python.** Reframe: the wrapper is a CLI utility (`scripts/telemetry_record.py`) that the orchestrator invokes via Bash at each spawn boundary:`

**Issue:** The spec opens by naming a runtime module `ai_workflows/orchestration/telemetry.py`, then mid-paragraph rejects its own framing ("Wait — the slash commands are markdown procedure documents, not Python") and pivots to `scripts/telemetry_record.py`. The misleading first heading remains. Critically:

- `ai_workflows/orchestration/` directory does not exist in the package. Current package layout is `cli.py`, `evals/`, `graph/`, `__init__.py`, `mcp/`, `primitives/`, `workflows/`. Adding `orchestration/` creates a new top-level subpackage with no clear placement in the four-layer rule (`primitives → graph → workflows → surfaces`).
- The orchestration code lives entirely in `.claude/commands/*.md` (markdown procedure files); it is NOT runtime Python. Adding a Python module under `ai_workflows/` for orchestration plumbing crosses the runtime-vs-infra boundary M20 explicitly preserves (README §Scope note: *"M20 changes the autonomy infrastructure — agent prompts (`.claude/agents/`), slash commands (`.claude/commands/`), and the project context doc (`CLAUDE.md`). Runtime code is read-only at this milestone except where a finding requires a runtime hook."*).
- The actual deliverable is `scripts/telemetry_record.py` (correctly placed).
- Tests are at `tests/orchestration/` (which doesn't exist yet — see M2 below for the directory-spelling clash with `tests/orchestrator/`).

**Recommendation:** Delete the `ai_workflows/orchestration/telemetry.py` heading + its first paragraph. Promote the `scripts/telemetry_record.py` framing to the only Deliverable heading. Keep the test file path discussion (will be reconciled with the orchestrator/orchestration spelling fight in M2).

**Apply this fix:**

`old_string` (in task_22, lines 41–47):
```
### Telemetry wrapper module — `ai_workflows/orchestration/telemetry.py` (NEW, repo-side runtime)

A small Python module that the slash-command orchestrator imports (or invokes via a one-liner) at every Task spawn boundary. **Wait — the slash commands are markdown procedure documents, not Python.** Reframe: the wrapper is a CLI utility (`scripts/telemetry_record.py`) that the orchestrator invokes via Bash at each spawn boundary:
```

`new_string`:
```
### Telemetry wrapper script — `scripts/telemetry_record.py` (NEW)

A CLI utility the orchestrator invokes via Bash at each Task-spawn boundary. The slash commands are markdown procedure documents, not Python — telemetry capture is shell-out, not in-process import. (No new code lands under `ai_workflows/`; M20 preserves the runtime-vs-orchestration-infra boundary per README §Scope note.)
```

---

#### H2 — T05 silently restructures two gates without naming the change

**Task:** task_05_parallel_terminal_gate.md
**Location:** task_05 §What to Build, opening paragraphs:
> `Replace the **sequential terminal gate** in `/auto-implement` with a **parallel multi-Task spawn**. Today the orchestrator spawns sr-dev → sr-sdet → security-reviewer in series (each invocation waits for the previous to return).`

**Issue:** Today's `/auto-implement` does not have one "terminal gate" containing all three reviewers. It has two distinct gates:

- **Security gate** (line 121 of `.claude/commands/auto-implement.md`): Step S1 spawns `security-reviewer`; Step S2 conditionally spawns `dependency-auditor`. Runs FIRST, after FUNCTIONALLY CLEAN.
- **Team gate** (line 149): Step T1 spawns `sr-dev`; Step T2 spawns `sr-sdet`; Step T3 conditionally spawns `architect`. Runs SECOND, after SECURITY CLEAN.

T05's design merges security-reviewer into the team gate's parallel batch, which means:

1. Eliminating the standalone **Security gate** as a separate phase.
2. Moving security-reviewer's invocation to run concurrently with sr-dev / sr-sdet, not before them.
3. Re-thinking the SECURITY CLEAN → TEAM CLEAN sequencing the orchestrator currently uses for stop-condition evaluation.

The spec doesn't acknowledge any of this. The Builder will land changes that look like minor edits but actually collapse two gates into one. Downstream consequences include (a) what happens when security-reviewer says BLOCK while sr-dev says SHIP (today's logic halts at security-gate boundary; new logic must define precedence), (b) whether dependency-auditor still gates separately or also runs in parallel, (c) whether the orchestrator still has a SECURITY CLEAN stop condition or replaces it with a unified TEAM CLEAN.

**Recommendation:** T05 must explicitly call out the gate restructuring. Either (a) merge into one terminal gate with reformulated stop conditions, or (b) parallelize within each gate (sr-dev || sr-sdet within Team gate; security-reviewer stays alone in Security gate — only 2× speedup achievable, not 3×).

If (a): name "Security gate" as deleted; reformulate stop conditions; specify dependency-auditor placement; specify how a security-reviewer BLOCK precedence interacts with sr-dev SHIP.

If (b): drop the wall-clock 2× target for terminal gate (sr-dev || sr-sdet alone is at most 1.5–1.7× — security-reviewer's serial latency floor remains). Update the AC.

**Apply this fix:** Manual — see Recommendation. Stop and ask the user which option to pursue (significant scope difference).

---

#### H3 — T21 omits `implement.md` (still has `thinking: high` literal) — migration is incomplete

**Task:** task_21_adaptive_thinking_migration.md
**Location:** task_21 §Deliverables — Slash command frontmatter, line 38:
> `For each of the 6 confirmed hits (`auto-implement.md`, `audit.md`, `clean-tasks.md`, `clean-implement.md`, `queue-pick.md`, `autopilot.md`), replace:`

**Issue:** `.claude/commands/implement.md` has `thinking: high` (verified by `grep -nE "^thinking:" .claude/commands/`). T21's deliverables list six commands; `implement.md` is missing. The smoke test only greps for `thinking:[[:space:]]*max`, which by design misses `thinking: high` — but per the research brief Lens 3.3 the `thinking: <literal>` shorthand (whether `max`, `high`, `medium`, `low`) is itself the deprecated form being replaced by `thinking: {type: "adaptive"}` + `effort:`. Leaving `implement.md` with `thinking: high` ships M20 with one of the seven slash commands using the deprecated dial.

If it's intentional that `implement.md` retains the legacy form (e.g. it's effectively unused after autonomous-mode adoption), the spec needs to say so explicitly and to make the smoke test consistent with that decision.

**Recommendation:** Include `implement.md` in the migration. Add it to the deliverables list and to the `for cmd in ...` smoke loop. Effort assignment for `implement.md` → `effort: high` (single Builder pass mirrors `clean-implement` and `auto-implement`).

**Apply this fix:**

`old_string` (in task_21, line 38):
```
For each of the 6 confirmed hits (`auto-implement.md`, `audit.md`, `clean-tasks.md`, `clean-implement.md`, `queue-pick.md`, `autopilot.md`), replace:
```

`new_string`:
```
For each of the 7 commands (`auto-implement.md`, `audit.md`, `clean-tasks.md`, `clean-implement.md`, `queue-pick.md`, `autopilot.md`, `implement.md` — confirmed by `grep -nE "^thinking:" .claude/commands/`), replace:
```

Also in §Effort assignment per slash command — add the line:
```
- `implement` → `effort: high` (single Builder pass; mirrors `clean-implement`)
```

Also in the smoke test loop, change `for cmd in auto-implement audit clean-tasks clean-implement queue-pick autopilot` to `for cmd in auto-implement audit clean-tasks clean-implement queue-pick autopilot implement`.

Also update the milestone README §Goals item 4 from "6 hits" to "7 hits". And §Task pool T21's row prose from "6 hits across `.claude/commands/` 2026-04-27 grep" to "7 hits".

---

#### H4 — T05 + T22 fragment-file path conflicts with README's `.cycle/{agent}.verdict.md` framing

**Task:** Cross-spec — task_05_parallel_terminal_gate.md, task_22_per_cycle_telemetry.md, README.md
**Location:**

- README.md goal 2 + exit criterion 5: `runs to per-reviewer fragment file (`.cycle/{agent}.verdict.md`)`.
- README.md goal 7 + exit criterion 12: `Persist to `.cycle/{agent}.usage.json`.`
- README.md task pool T22 row: `persists to `.cycle/{agent}.usage.json``.
- task_05.md §Mechanism, line 18: `runs/<task>/<cycle>/sr-dev-review.md`.
- task_22.md §Captured fields + AC #2: `runs/<task>/<cycle>/<agent>.usage.json`.
- task_03.md §Deliverables: `runs/<task-shorthand>/cycle_<N>_summary.md` plus `runs/<task>/<cycle>/<agent>.usage.json`.

**Issue:** The README uses a hidden `.cycle/` directory convention; every per-task spec uses `runs/<task>/<cycle>/`. These are two different conventions. The Builder cannot satisfy both — picking one breaks the smoke test of the other. README's `.cycle/` is also directly at variance with task_03's `runs/<task>/cycle_<N>_summary.md` per-task file naming (`.cycle/` is a top-level dir; `runs/<task>/` is a per-task dir).

**Recommendation:** Specs are consistent with each other on `runs/<task>/<cycle>/` — fix the README to match. The `runs/` convention is also consistent with the existing `.gitignore` rule `runs/*` and the existing autopilot recommendation-file convention `runs/autopilot-<run-ts>-iter<N>.md`.

**Apply this fix:**

In README.md:
- Goal 2 (line 35): `.cycle/{agent}.verdict.md` → `runs/<task>/<cycle>/<agent>-review.md` (matches T05 §Mechanism path).
- Goal 7 (line 40): `.cycle/{agent}.usage.json` → `runs/<task>/<cycle>/<agent>.usage.json`.
- Exit criterion 5 (line 54): `.cycle/{agent}.verdict.md` → `runs/<task>/<cycle>/<agent>-review.md`.
- Exit criterion 12 (line 61): `.cycle/{agent}.usage.json` → `runs/<task>/<cycle>/<agent>.usage.json`.
- Task pool T22 row (line 123): `.cycle/{agent}.usage.json` → `runs/<task>/<cycle>/<agent>.usage.json`.

---

#### H5 — T20 cites M12-T01 carry-over patch as "in template, possibly held back from live" — confirmed missing from live; spec must own porting it as REQUIRED, not optional

**Task:** task_20_carry_over_checkbox_cargo_cult_extended.md
**Location:** task_20 §Deliverables — `Verify the M12-T01 patch is in the live auditor file (it was added to the *template* but possibly held back from live during the M12 autopilot session — see memory thread #5: "carry-over checkbox-cargo-cult catch has been added to both projects' auditor.md (post-M12-T01 lesson)"). Confirm by grep; if missing, port from template.`

**Issue:** Verified empirically:
- `template/.claude/agents/auditor.md` contains the patch (line 40: `**Carry-over checkbox-cargo-cult** (real failure mode observed in autonomy validation)...`).
- `.claude/agents/auditor.md` (live) does NOT contain it (`grep -n "carry-over.*checkbox\|carry-over.*diff\|cargo cult" /home/papa-jochy/prj/ai-workflows-m20/.claude/agents/auditor.md` returns no hits).

So the patch is definitively missing from live. The spec phrases this as conditional ("possibly held back…confirm by grep; if missing, port") — which means the Builder might do nothing on the assumption it landed. But the live file's evidence shows the spec is authoritative: patch IS missing, MUST port.

The framing also confuses the M12-T01 fix (Detection 1) with the new T20 detections (Detection 2 — cycle-N overlap; Detection 3 — rubber-stamp). All three need to land; spec presents (1) as conditional and (2)+(3) as new, where in fact (1) is also new on the live side.

**Recommendation:** Strengthen "verify…confirm by grep; if missing, port" → "Port the M12-T01 patch from template to live (verified missing 2026-04-27)." Make it a definite deliverable, not a conditional one. Add a smoke-test line that asserts the patch lands.

**Apply this fix:**

`old_string` (in task_20 §Deliverables — second paragraph):
```
### `.claude/agents/auditor.md` — port the M12-T01 carry-over patch

Verify the M12-T01 patch is in the live auditor file (it was added to the *template* but possibly held back from live during the M12 autopilot session — see memory thread #5: "carry-over checkbox-cargo-cult catch has been added to both projects' auditor.md (post-M12-T01 lesson)"). Confirm by grep; if missing, port from template.
```

`new_string`:
```
### `.claude/agents/auditor.md` — port the M12-T01 carry-over patch from template to live (verified missing 2026-04-27)

The patch landed in `template/.claude/agents/auditor.md` (line 40: `**Carry-over checkbox-cargo-cult**...`) but did NOT land in the live `.claude/agents/auditor.md` (verified by grep 2026-04-27 — zero matches for `"carry-over.*checkbox\|cargo cult"`). T20 ports the same paragraph (verbatim) from template to live as a separate deliverable from the new Phase 4.5 detections (2 and 3). Both ships in this task.
```

Also in §Acceptance criteria #2: change `The M12-T01 carry-over patch is confirmed live (not just template)` → `The M12-T01 carry-over patch is ported from template to live (verified missing 2026-04-27 grep).`

---

#### H6 — T27 path-A frontmatter cannot land in a `.claude/agents/*.md` file — Claude Code agent frontmatter does not accept arbitrary keys

**Task:** task_27_tool_result_clearing.md
**Location:** task_27 §Deliverables — Path A — server-side, lines 43–58:
> ``.claude/agents/auditor.md` adds frontmatter:`
> ```yaml
> context_management:
>   edits:
>     - type: clear_tool_uses_20250919
>       trigger:
>         type: input_tokens
>         value: 60000
>       ...
> ```

**Issue:** Claude Code's agent file frontmatter recognises a fixed set of keys (`name`, `description`, `tools`, `model` — verified across all 9 existing agents). There is no documented mechanism for Claude Code to read `context_management:` from agent frontmatter and pass it through to the underlying SDK Task call. The research brief itself notes the parameter is a property of the **Anthropic Agent SDK**, not Claude Code's `Task` tool surface (T01's "Out of scope" §145 is the explicit precedent: `outputFormat: json_schema` cannot land via Claude Code Task either, so T01 fell back to orchestrator-side parsing).

T27 partially acknowledges this in §Surface check ("does Claude Code's `Task` tool surface the `context_management.edits` parameter? If not, T27 reduces to a NO-GO sibling…"), then describes a Path A that places the YAML in agent frontmatter as if Claude Code would read it. Even if the SDK accepts the parameter, the agent-file frontmatter is the wrong landing site — Claude Code would parse it as an unknown key and ignore it.

**Recommendation:** Treat Path A as analytically NO-GO based on the same evidence T01 used. T27's only viable deliverable is Path B (client-side simulation: orchestrator monitors token volume; spawns fresh Auditor with compacted input via cycle_summary). Or the surface check (the empirical pre-step) lands as the deliverable and Path B is conditional on the check showing Path A unreachable.

Better still: collapse T27 + T28 into one analysis spike whose deliverable is the surface-check result + the GO/NO-GO decision, with implementation deferred to a follow-up if surfaces turn out to be exposed.

**Apply this fix:** Manual — see Recommendation. Stop and ask the user which framing to pursue (T27 stays as Path B only, or T27 + T28 collapse into a single surface-check analysis task).

---

### 🟡 MEDIUM

#### M1 — `tests/orchestrator/` vs `tests/orchestration/` directory-name fight across specs

**Task:** Cross-spec — task_02, task_03, task_05, task_07, task_08, task_09, task_21, task_22, task_23
**Location:**

- T02 / T03 / T05 / T08 / T09 / T21 / T23 use `tests/orchestrator/`.
- T07 / T22 use `tests/orchestration/`.

**Issue:** Two different test directories. Builder will create whichever the current spec names; subsequent tasks land tests in a different directory; pytest discovers both (per `pyproject.toml` `testpaths = ["tests"]`) but the codebase ends up with two parallel orchestration-test homes.

**Recommendation:** Pick one. `tests/orchestration/` parses better grammatically; `tests/orchestrator/` parses better as "the orchestrator's tests". Either is fine; consistency is the gate. `tests/orchestrator/` has 7 specs using it vs 2 — go with the majority.

**Apply this fix:**

In task_07_dynamic_model_dispatch.md, replace_all `tests/orchestration/` → `tests/orchestrator/`.

In task_22_per_cycle_telemetry.md, replace_all `tests/orchestration/` → `tests/orchestrator/`.

---

#### M2 — README §Cross-phase dependencies says T01 *blocks* T05 + T08, specs say *strongly precedent*

**Task:** Cross-spec — README.md vs task_05.md, task_08.md
**Location:**

- README.md line 159: `**T01** (return-value schema) → **blocks** **T05** … and **T08** …`
- task_05.md §Dependencies: `**T01** … — strongly precedent.`
- task_08.md §Dependencies: `**T01** … — strongly precedent.`

**Issue:** README says blocking; specs say strongly-precedent (= non-blocking). One of these is wrong. The Builder for T05 / T08 reads the spec; the orchestrator (`/queue-pick`) reads the README's task pool to determine eligibility. If they conflict, queue-pick may eligible-list T05 before T01 ships, then the Builder finds it can't satisfy ACs without T01's schema in place.

**Recommendation:** Decide based on the actual content. T05's fragment-file format reuses T01's 3-line schema in its stitch step (line 24, 33). T08's first-defence-layer is T01's parser (T08 line 21). Both are *content* dependencies — without T01's schema landed, T05 and T08 do not have a definite contract to depend on. **Make them blocking.** Update each spec's Dependencies section.

**Apply this fix:**

In task_05_parallel_terminal_gate.md §Dependencies:
`old_string`: `- **T01** (return-value schema) — strongly precedent. T05's stitch step parses each agent's T01 return; the fragment-file format reuses T01's `file:` and `section:` semantics.`
`new_string`: `- **T01** (return-value schema) — **blocking**. T05's stitch step parses each agent's T01 return; the fragment-file format reuses T01's `file:` and `section:` semantics. Without T01's schema landed, T05 has no definite contract to depend on.`

In task_08_gate_output_integrity.md §Dependencies:
`old_string`: `- **T01** (orchestrator parser) — strongly precedent. T08 reuses T01's "halt with structured BLOCKED surface" pattern.`
`new_string`: `- **T01** (orchestrator parser) — **blocking**. T08's first-defence-layer is T01's parser; without T01 landed, T08 has nothing to layer atop.`

---

#### M3 — T09's "task-kind" check has no consistent source of truth across specs

**Task:** task_09_task_integrity_safeguards.md
**Location:** task_09 §Mechanism, step 2: `If task-kind includes `code` (per the spec's kind line)` and §Deliverables — pre-commit ceremony, step 2: `If task-kind includes `code` (per the spec's kind line per the spec)`.

**Issue:** Only T06 and T28 declare a `**Kind:**` line in their `**Status:**` block. T01–T05, T07–T08, T20–T23, T27 do not. The README's task pool table has a "Phase / Kind" column with values like `Compaction / doc + code`, `Performance / doc + code`, `Safeguards / code`. So `Kind` lives in the README's task-table, not in the per-task spec.

For T09's check to work, the Builder needs a deterministic way to read the Kind for the task currently being audited. The spec doesn't specify a parser; the README format is `| <NN> | <title> | <verdict> | <Phase> / <Kind> | <Status> |` which is parseable but undocumented as the source of truth.

**Recommendation:** Either (a) add a `**Kind:**` line to every M20 spec's status block (mirrors T06 / T28's pattern), or (b) document in T09 that the Kind is parsed from the milestone README task-table's "Phase / Kind" column with a regex like `^\| <NN> \| .*? \| .*? \| <Phase> / <Kind> \|`.

(a) is cleaner; (b) reuses an existing source. Pick (a) and add a carry-over to all 15 M20 specs to add the line at task-close. Adding it to the spec template up front saves a re-loop.

**Apply this fix:**

In task_09 §Mechanism step 2:
`old_string`: `2. If task-kind includes `code`: orchestrator runs `git diff --stat <pre-task-commit>..HEAD -- tests/` and asserts non-zero (2).`
`new_string`: `2. If task-kind includes `code` (parsed from the spec's `**Kind:**` line in the Status block — the orchestrator falls back to the README's task-pool "Phase / Kind" column if the spec's Kind line is missing): orchestrator runs `git diff --stat <pre-task-commit>..HEAD -- tests/` and asserts non-zero (2).`

In task_09 §Deliverables — step 2 of the markdown block: same edit (add the parse-source clarification).

Also: add to T09's deliverables a short carry-over note that "every M20 spec gains an explicit `**Kind:**` line in its Status block matching its README task-pool Kind column" — and surface as a coordinated edit across all 15 specs.

---

#### M4 — T01 leaves the README's exit-criterion 1 framing inconsistent with its own out-of-scope framing

**Task:** task_01_sub_agent_return_value_schema.md
**Location:** task_01 §Out of scope, lines 145:
> `**The README's exit criterion 1 should be re-read as "enforced via prompt-mandate + orchestrator-side parsing" instead of "via SDK `outputFormat`."** Surface as a MEDIUM at task-analyzer round 1 if not already in the README at /clean-tasks time.`

**Issue:** README §Exit criteria item 1 (line 50) does already say "enforced across all 9 agents via **prompt-mandate + orchestrator-side parsing**" — that's already correct. So the round-1 "surface as MEDIUM" instruction is a stale request the spec author left in expecting it to need a fix. Keeping it in the spec is non-actionable noise the Builder may misread as a remaining TODO.

**Recommendation:** Delete the surface-as-MEDIUM line; replace with a positive confirmation that README is consistent.

**Apply this fix:**

`old_string`: `**The README's exit criterion 1 should be re-read as "enforced via prompt-mandate + orchestrator-side parsing" instead of "via SDK `outputFormat`."** Surface as a MEDIUM at task-analyzer round 1 if not already in the README at /clean-tasks time.`
`new_string`: `(README's exit criterion 1 already names "prompt-mandate + orchestrator-side parsing" — no further README edit needed for this scope clarification.)`

---

#### M5 — T01 token-cap test claims `tiktoken` as test-only dep but pyproject lacks it

**Task:** task_01_sub_agent_return_value_schema.md
**Location:** task_01 §Tests:
> `Assert total return length ≤ 100 tokens (using `tiktoken` cl100k_base or equivalent token-counter; install as test-only dep if not already present).`

**Issue:** Verified `pyproject.toml` `[dependency-groups] dev` lacks `tiktoken`. Adding it requires `pyproject.toml` + `uv.lock` edits, which trigger the dependency-auditor agent (CLAUDE.md non-negotiable). T01 is positioned as a foundation task to land first; adding a dependency to it imposes additional review surface.

**Recommendation:** Use the regex-based proxy (split on whitespace + count). For 3-line schema validation the actual question is "is the return ≤ ~100 tokens" — a word-count + 1.3× ratio gives a usable proxy without `tiktoken`. The same proxy is named in T02's §Orchestrator measurement instrumentation as "regex-based proxy — token-counting accuracy is not load-bearing here, magnitude is."

**Apply this fix:**

`old_string`: `Assert total return length ≤ 100 tokens (using `tiktoken` cl100k_base or equivalent token-counter; install as test-only dep if not already present).`
`new_string`: `Assert total return length ≤ 100 tokens (using a regex-based proxy: `len(re.findall(r"\S+", text)) * 1.3` — accuracy is not load-bearing here, magnitude is. Same proxy as T02's spawn-prompt-size measurement, no new test-only deps needed).`

---

#### M6 — `_common/` directory creation is not called out in the first task that introduces it

**Task:** task_01_sub_agent_return_value_schema.md (first to create `.claude/commands/_common/`)
**Location:** task_01 §Deliverables — `.claude/commands/_common/agent_return_schema.md (NEW)`.

**Issue:** Verified `.claude/commands/_common/` does not exist (`ls .claude/commands/_common/` returns "No such file or directory"). T01 introduces the first `_common/` file but doesn't mention directory creation. T02 also introduces a `_common/` file (`spawn_prompt_template.md`) and assumes it exists; T05 / T07 / T08 / T09 / T21 / T23 / T27 each add another. None of them name the directory creation explicitly. The first task to land must `mkdir -p .claude/commands/_common/` (or rely on the Edit tool's directory-creation behaviour, which Claude Code's Write tool does provide). Spec should make this explicit so the Builder doesn't punt.

**Recommendation:** Add a short note to T01's deliverable list naming `mkdir -p .claude/commands/_common/` as the first operation when the file lands. Subsequent tasks can rely on the directory existing.

**Apply this fix:**

In task_01 §Deliverables, before `### `.claude/commands/_common/agent_return_schema.md (NEW)``:
`new_string` (insert):
```
### `.claude/commands/_common/` directory (NEW — created by T01 as the first task to introduce it)

T01 lands the first file under `.claude/commands/_common/`. Run `mkdir -p .claude/commands/_common/` (or use Write, which creates parent dirs) before writing the first file there. Subsequent tasks (T02, T05, T07, T08, T09, T21, T23, T27) populate additional files into this directory and can assume it exists.
```

---

#### M7 — T22's "captured fields" cite cache-* tokens that may not be exposed by Claude Code's Task tool

**Task:** task_22_per_cycle_telemetry.md
**Location:** task_22 §Captured fields and §Mechanism:
> `The model + effort + cache-* fields come from the Task tool's invocation metadata (these fields are returned in the Task response — already there, just not captured today).`

**Issue:** This claim is undocumented. The Anthropic Agent SDK exposes `cache_creation_input_tokens` and `cache_read_input_tokens` per the API docs, but Claude Code's `Task` tool wraps the SDK and may or may not surface them. T01's parallel concern about Task tool not exposing `outputFormat: json_schema` and T27's surface-check concern about Task tool not exposing `context_management.edits` both point in the same direction: the orchestrator surface is narrower than the SDK.

If Claude Code's Task tool does not return cache-* tokens, T22's per-record JSON has empty / null fields, T23's 2-call verification is impossible, and T06's per-cell `cache_read_input_tokens` data is not collectable.

**Recommendation:** T22 needs a surface-check step matching T27 + T28's pattern. Run an empirical Task spawn and inspect the response payload for cache-* fields. Document the result. If they're not exposed, either (a) reduce T22's scope to input/output token counts only (computed from prompt + return text), and downgrade T23 (cache-breakpoint verification) to "best-effort with the available signal," or (b) flag as STOP-AND-ASK to the user.

**Apply this fix:**

In task_22 §Mechanism (after the "captured fields" JSON block), insert:

```
### Surface-check pre-step

Before any production capture: run `python scripts/check_task_response_fields.py` (or a single `Task` spawn dump) to confirm whether Claude Code's Task tool returns `cache_creation_input_tokens`, `cache_read_input_tokens`, `input_tokens`, and `output_tokens` in its response payload. The result lands at `runs/m20_t22_surface_check.txt` for the audit trail. If cache-* fields are NOT exposed: T22 ships with the available subset (input/output tokens computed from prompt + return text, model + effort from spawn args, wall_clock from timestamps), and T23 (cache-breakpoint verification) downgrades to STOP-AND-ASK. If they ARE exposed: T22 ships full per the original spec.
```

---

#### M8 — T07's default-table commit flip says "isolated commit" but T07 is a single multi-deliverable task — Builder doesn't know which work goes on which commit

**Task:** task_07_dynamic_model_dispatch.md
**Location:** task_07 §Deliverables — KDR-isolation rule:
> `**Land the default-table change on a separate isolated commit** per autonomy decision 2 (CLAUDE.md non-negotiable). Other T07 work (helper module, slash-command integration, flag wiring, tests) can land on a single commit; the default-table flip lands separately…`

**Issue:** T07 has 6 logical deliverables. The spec correctly identifies the default-table flip as needing an isolated commit. But the autonomy decision 2 framing in CLAUDE.md is for **KDR additions** (architectural rules), and the default-table flip isn't a KDR — it's a configuration-policy change. CLAUDE.md non-negotiables: *"KDR additions land on a separate isolated commit per autonomy decision 2 so they can be reverted independently of task code."*

So the rule is being analogically extended. That may be fine for a high-impact policy change, but the spec should name the analogy explicitly so the Auditor doesn't mark it as "this isn't a KDR, so the isolated-commit framing is wrong."

**Recommendation:** Rename "KDR-isolation rule" → "Reverter-friendly commit isolation (analogy to autonomy decision 2)" and explicitly say "this is not a new KDR; the same revert-independently rationale applies because the default-table flip is the highest-impact-change-with-uncertain-quality-implications in T07."

**Apply this fix:**

`old_string`: `### KDR-isolation rule for the default-tier flip commit`
`new_string`: `### Reverter-friendly commit isolation for the default-tier flip (analogy to autonomy decision 2)`

`old_string`: `**Land the default-table change on a separate isolated commit** per autonomy decision 2 (CLAUDE.md non-negotiable).`
`new_string`: `**Land the default-table change on a separate isolated commit** in the spirit of autonomy decision 2 (CLAUDE.md non-negotiable, applied analogically — the default-table flip is not a KDR, but the same independent-revertability rationale applies given the change's impact + uncertain quality implications).`

---

#### M9 — T22's `quota_consumption_proxy` coefficients are unfounded priors

**Task:** task_22_per_cycle_telemetry.md
**Location:** task_22 §Captured fields:
> `is computed from input + output tokens against a per-model coefficient (Sonnet 4.6: 1.0; Opus 4.6: 1.67; Opus 4.7: 1.67 × 1.0–1.35 tokenizer-overhead factor; Haiku 4.5: 0.33).`

**Issue:** These are public-API per-token price ratios. T22 itself notes the binding constraint for ai-workflows is **weekly Max-subscription quota consumption**, not per-token API spend (per KDR-003 / README §Why this milestone exists). Quota consumption ratios are not 1.67×; they're operator-quota-share ratios that depend on Anthropic's internal accounting, which (per T22's own surface, anthropics/claude-code #52502) is opaque. Using API-price ratios as a quota-proxy is exactly the conflation T22's framing was supposed to avoid.

**Recommendation:** Either (a) acknowledge the proxy is API-price-based, name it `api_price_proxy` instead of `quota_consumption_proxy`, and document that it's a directional proxy with the actual quota consumption requiring measurement once T06 produces empirical data; or (b) delete the per-model coefficients and ship T22 with just the raw token counts, deferring the proxy to T06's analysis output (T06's deliverable, not T22's).

(b) is cleaner — T22 is the measurement substrate; deriving aggregations from it is T06's analysis layer.

**Apply this fix:**

`old_string` (in task_22 §Captured fields, lines 35–36):
```
The **`quota_consumption_proxy`** field is computed from input + output tokens against a per-model coefficient (Sonnet 4.6: 1.0; Opus 4.6: 1.67; Opus 4.7: 1.67 × 1.0–1.35 tokenizer-overhead factor; Haiku 4.5: 0.33). Values are normalised against Sonnet 4.6 = 1.0. This is a **proxy**, not ground-truth — Anthropic's actual quota accounting is opaque (per #52502). The proxy lets ai-workflows measure relative consumption across cells in the T06 study without depending on the upstream dashboard.
```

`new_string`:
```
T22 captures raw token counts only — `input_tokens`, `output_tokens`, `cache_creation_input_tokens`, `cache_read_input_tokens` (subject to the surface check above), `model`, `effort`. **No per-model coefficient applied at T22 capture time.** Per-cell quota-proxy aggregations are computed by T06's analysis script using the appropriate ratio model (API price, observed Max-quota consumption from the T06 runs themselves, or both). T22 is the measurement substrate; T06 owns the analysis layer.
```

Also remove `quota_consumption_proxy` from the JSON example (line 28) and replace with a comment noting "(quota proxy computed by T06 analysis, not at capture time)".

---

#### M10 — T07's helper file location `scripts/dispatch.py` collides with general `scripts/` namespace; needs differentiation

**Task:** task_07_dynamic_model_dispatch.md
**Location:** task_07 §Deliverables — `scripts/dispatch.py` (NEW).

**Issue:** Verified `scripts/` exists (`scripts/aiw-entrypoint.sh`, `scripts/release_smoke.sh`, `scripts/spikes/`). Adding `scripts/dispatch.py` is fine, but:

- T22 lands `scripts/telemetry_record.py` in the same directory.
- T23 lands `scripts/cache_verify.py` there.
- T27's surface-check lands `scripts/check_task_tool_surface.py` (or similar) there.

By the end of M20 the `scripts/` directory has 5+ M20-introduced Python files mixed with the existing shell helpers. Recommend nesting them under a clear namespace.

**Recommendation:** Create `scripts/orchestration/` as the namespace for M20-orchestration helpers. T22 → `scripts/orchestration/telemetry.py` (drop `_record` suffix; the directory provides the namespace). T23 → `scripts/orchestration/cache_verify.py`. T07 → `scripts/orchestration/dispatch.py`. T27's surface-check → `scripts/orchestration/check_task_surface.py`.

This is LOW-leaning, but the consistent prefix simplifies later cleanup and makes the helpers a coherent surface that future M21 tasks can extend.

**Apply this fix:** Rename across all four specs as above. Each spec's smoke test + AC + tests references must update accordingly.

---

#### M11 — T03 + T04 directory layout disagree about per-cycle vs per-iteration nesting

**Task:** task_03_in_task_cycle_compaction.md + task_04_cross_task_iteration_compaction.md
**Location:**

- T03 §`runs/<task>/` directory convention, lines 51–62: `runs/<task-shorthand>/` containing `cycle_<N>_summary.md`, `agent_<name>_raw_return.txt`, `spawn_<agent>_<cycle>.tokens.txt`.
- T04 §`runs/autopilot-<run-ts>/` directory convention, lines 61–70: `runs/autopilot-<run-ts>/` containing `iter_<N>.md`, `iter_<N>_shipped.md`.
- T22 + T05 + T08 use `runs/<task>/<cycle>/<agent>.usage.json` and `runs/<task>/<cycle>/<agent>-review.md` (per-cycle nested directory, NOT per-cycle files in a flat task dir).

**Issue:** T03 puts per-cycle files at the *top level* of `runs/<task-shorthand>/` (`cycle_<N>_summary.md`, `agent_<name>_raw_return.txt`). T22 / T05 / T08 nest per-cycle artifacts under `runs/<task>/<cycle>/` (a `<cycle>` subdirectory). The two conventions cannot coexist: a Builder satisfying T03 lands `runs/m20_t01/cycle_1_summary.md` (top-level); a Builder satisfying T05 lands `runs/m20_t01/1/sr-dev-review.md` (subdirectory `1`). Neither convention covers all artifacts cleanly.

**Recommendation:** Pick one — likely the nested form. Rewrite T03's directory layout to:

```
runs/<task-shorthand>/
  cycle_<N>/
    summary.md             (T03)
    sr-dev-review.md       (T05)
    sr-sdet-review.md      (T05)
    security-review.md     (T05)
    builder.usage.json     (T22)
    auditor.usage.json     (T22)
    ...
    gate_pytest.txt        (T08)
  agent_<name>_raw_return.txt   (T01 — top-level, per-task, not per-cycle? Or move to cycle_<N>/?)
```

Decide where T01's `agent_<name>_raw_return.txt` lives — top-level (one per agent across all cycles, latest wins) or per-cycle (one per agent per cycle, full audit trail). The latter is safer.

**Apply this fix:** Manual — see Recommendation. Update T03's directory convention block; coordinate with T01, T05, T08, T22 to reference the same structure.

---

#### M12 — T03 task-shorthand convention `m<N>_t<NN>` collides with M20 task numbering when N has 2 digits

**Task:** task_03_in_task_cycle_compaction.md
**Location:** task_03 §Deliverables — `<task-shorthand>` is `m<N>_t<NN>` (e.g. `m20_t01`).

**Issue:** Convention works at `m20_t01` but is ambiguous when M and N each have variable digits — `m1_t1` vs `m1_t10` vs `m11_t1` etc. The user's project memory (`user_shorthand_m_t.md`) defines the shorthand as "m1 t1" with optional leading zero — but as a directory name `m1_t1` clashes with `m1_t10` lexically. T22 reuses this shorthand. Several specs grep for it.

**Recommendation:** Pin the convention as `m<N>_t<NN>` (zero-padded both M and T). So `m01_t01`, not `m1_t01`. For M20 it's `m20_t01` either way. For M9 / M5 / M3, it'd be `m09_t01`, `m05_t02`, etc. Document explicitly.

**Apply this fix:**

In task_03 §Deliverables:
`old_string`: `<task-shorthand>` is `m<N>_t<NN>` (e.g. `m20_t01`). Directory creation handled by the orchestrator on cycle 1; subsequent cycles append.
`new_string`: `<task-shorthand>` is `m<MM>_t<NN>` — milestone and task numbers both two-digit-zero-padded (e.g. `m20_t01`, `m05_t02`, `m09_t01`). Directory creation handled by the orchestrator on cycle 1; subsequent cycles append.

Mirror the same convention in T22 (task field of the JSON record) and T05 (review fragment paths).

---

#### M13 — T01 / T02 Auditor pre-load discipline conflicts with auditor's "load full task scope" invariant in subtle ways

**Task:** task_02_sub_agent_input_prune.md
**Location:** task_02 §Deliverables — Auditor spawn:
> `**Auditor spawn:** task spec path + issue file path + project context brief + current `git diff` + the **specific KDR sections** the task spec cites (parsed at spawn time, not the whole §9 table). **Remove:** whole-milestone-README pre-load, pre-loaded architecture.md, pre-loaded sibling issue files. The Auditor pulls sibling issues + full architecture via Read on-demand.`

**Issue:** The Auditor agent (live `.claude/agents/auditor.md` line 19) requires "the full task scope, not the diff" — which includes parent milestone README, sibling tasks + their issue files, plus architecture.md and every cited KDR. T02 spec says "remove whole-milestone-README pre-load" but the Auditor must read the README per its own discipline. T02's framing is "the agent reads on-demand instead of having the orchestrator pre-load" — but the orchestrator currently passes the README *path*, not the *content*. So the prune is removing the *content* pre-load, leaving the *path* in place.

This subtle distinction is not made explicit in T02. The Builder may interpret "remove whole-milestone-README pre-load" as "remove the path reference too," which would force the Auditor to discover the README path on its own, slowing every audit.

**Recommendation:** Clarify in T02's deliverable that:
- Path references (paths the Auditor needs to know exist) STAY in the spawn prompt.
- Content pre-loads (the actual contents inlined into the spawn prompt) are REMOVED.

**Apply this fix:**

In task_02 §Deliverables — Auditor spawn:
`old_string`:
```
- **Auditor spawn:** task spec path + issue file path + project context brief + current `git diff` + the **specific KDR sections** the task spec cites (parsed at spawn time, not the whole §9 table). **Remove:** whole-milestone-README pre-load, pre-loaded architecture.md, pre-loaded sibling issue files. The Auditor pulls sibling issues + full architecture via Read on-demand.
```
`new_string`:
```
- **Auditor spawn:** task spec path + issue file path + parent milestone README path + project context brief + current `git diff` + the **specific KDR sections** the task spec cites (parsed at spawn time, not the whole §9 table). **Remove from inline content:** whole-milestone-README *content* (path stays; Auditor reads on-demand), pre-loaded architecture.md *content*, pre-loaded sibling issue file *content*. The Auditor pulls all of these via its own Read tool when its phases need them. **Path references stay; content inlining goes.** The Auditor's "load full task scope" invariant is preserved — it just does the loading itself, on-demand, instead of receiving everything pre-stuffed into the spawn prompt.
```

---

#### M14 — T03 Phase 7 numbering collides with future Auditor phase additions; Phase numbering should be more durable

**Task:** task_03_in_task_cycle_compaction.md + task_20_carry_over_checkbox_cargo_cult_extended.md
**Location:**

- task_03: `### `.claude/agents/auditor.md` — emit `cycle_summary.md` as final phase` and `Add a new "Phase 7 — Cycle summary" section…`.
- task_20: `Add a new "Phase 4.5 — Anti-cargo-cult inspections" section between the existing Phase 4 (critical sweep) and Phase 5 (issue-file write).`

**Issue:** Verified the live auditor.md has Phase 1–6 (1: Design-drift; 2: Gate re-run; 3: AC grading; 4: Critical sweep; 5: Issue file; 6: Forward-deferral propagation). T20 inserts Phase 4.5; T03 appends Phase 7. The spec specifies "between Phase 4 and Phase 5" / "after the existing audit phases" — but there's no rule about whether Phase 4.5 means "logically between 4 and 5" or "renumber 5 to 6, 6 to 7, 7 to 8, then add 5".

T03 also doesn't specify what happens when both T03 + T20 ship (does T03's "Phase 7" become "Phase 8" if T20 lands first?).

**Recommendation:** Be explicit. T20's Phase 4.5 is a sub-phase numbering convention (not a re-number). T03's Phase 7 is the new last phase. Once both land:

- Phase 1 — Design-drift check
- Phase 2 — Gate re-run
- Phase 3 — AC grading
- Phase 4 — Critical sweep
- Phase 4.5 — Anti-cargo-cult inspections (T20)
- Phase 5 — Issue file
- Phase 6 — Forward-deferral propagation
- Phase 7 — Cycle summary (T03)

Or — move T03's emission to be part of Phase 5 (issue file emission) since cycle_summary.md is a structured projection of issue file content. Avoids a new Phase entirely.

**Apply this fix:** Add an Auditor-phase coordination paragraph to both T03 and T20 that names the final intended phase ordering. Or simpler — T03's cycle_summary emission becomes part of Phase 5 (issue file); T20's anti-cargo-cult inspections become part of Phase 4 (critical sweep). No new phases, less drift.

(Recommendation: collapse both into existing phases. T03 → Phase 5 amendment; T20 → Phase 4 amendment.)

---

#### M15 — T22's "T04 aggregation hook" creates a concrete dependency T04's spec doesn't acknowledge

**Task:** task_22_per_cycle_telemetry.md
**Location:** task_22 §Deliverables — Aggregation hook for T04:
> `T04's `iter_<N>_shipped.md` reads all `runs/<task>/<cycle>/*.usage.json` files for the iteration's task and emits an aggregation table: ## Telemetry summary | Cycle | Agent | Model | Effort | Input tokens | Output tokens | Cache hit % | Quota proxy | Verdict |`

**Issue:** T04's spec does not describe a "Telemetry summary" section in its iteration-shipped artifact. T22 says "T04's aggregation hook reads…" — but T04 is positioned upstream of T22 in the README's phase ordering (T04 lands in Phase A, T22 in Phase C). At the time T04 lands, T22 doesn't exist yet, so T04's `iter_<N>_shipped.md` template doesn't have the Telemetry summary section; when T22 lands later, T22's Builder needs to retrofit T04's already-shipped artifact format.

**Recommendation:** Either (a) add a Telemetry summary placeholder section to T04's spec now (so the structure is in place when T22 fills it), or (b) move T22's "T04 aggregation hook" to T22's own deliverable (T22 owns the aggregation script that reads telemetry + appends to `iter_<N>_shipped.md`, even if T04's template doesn't anticipate it).

(b) is cleaner since T04 ships before T22 — T22's Builder can use Edit to insert the section into pre-existing `iter_<N>_shipped.md` files generated by T04 in the interim. Document this explicitly in T22.

**Apply this fix:**

In task_22 §Deliverables — Aggregation hook for T04:
`old_string`:
```
T04's `iter_<N>_shipped.md` reads all `runs/<task>/<cycle>/*.usage.json` files for the iteration's task and emits an aggregation table:
```
`new_string`:
```
T22's aggregation hook reads all `runs/<task>/<cycle>/*.usage.json` files for the iteration's task and appends a Telemetry summary section to T04's `iter_<N>_shipped.md` artifact:

(T04 ships before T22 in Phase A vs Phase C; T22's Builder uses Edit to insert the section into pre-existing T04 artifacts. T04's template is unchanged at T04 land time; T22 retrofits it. The contract is: T22 owns the aggregation; T04 owns the iteration-shipped artifact's other sections; both files share `iter_<N>_shipped.md` as the durable surface.)
```

Also add a corresponding note in task_04 §Deliverables that the Telemetry summary section will be added later by T22 (so the T04 Builder doesn't try to anticipate it).

---

#### M16 — T20 §Detection 2 uses Jaccard finding-overlap with no defined metric or threshold-tuning method

**Task:** task_20_carry_over_checkbox_cargo_cult_extended.md
**Location:** task_20 §Mechanism, step 2:
> `Compute Jaccard overlap between cycle N's findings and cycle (N-1)'s findings (by finding-title fuzzy match). If overlap > 70 % → new MEDIUM finding "cycle-N findings substantially overlap cycle-(N-1) — loop may be spinning; recommend human review."`

**Issue:** "Finding-title fuzzy match" is undefined. Edit distance? `difflib.SequenceMatcher`? Token-level Jaccard? The 70% threshold has no calibration.

A concrete failure mode: cycle 1 surfaces "AC-3 not met"; cycle 2 surfaces "AC-3 still not met (cycle 2 update: see line 42)". The titles differ by "still" + "(cycle 2 update: see line 42)". Whether this counts as overlap depends entirely on the matching method.

**Recommendation:** Define the matching method concretely. Options:

- Strip the AC ID prefix, then `difflib.SequenceMatcher(a, b).ratio() > 0.7` per pair.
- Token-set Jaccard on word-stems with stopwords removed.

Pick one, document in T20. Note: the threshold is a heuristic — make it tunable via env var (`AIW_LOOP_DETECTION_THRESHOLD=0.7`) so an operator can adjust without a code change.

**Apply this fix:**

`old_string` (in task_20 §Mechanism step 2):
```
**(2) Cycle-N-vs-cycle-(N-1) finding-overlap detection.** New Auditor phase: read cycle (N-1)'s issue file (if exists). Compute Jaccard overlap between cycle N's findings and cycle (N-1)'s findings (by finding-title fuzzy match). If overlap > 70 % → new MEDIUM finding "cycle-N findings substantially overlap cycle-(N-1) — loop may be spinning; recommend human review."
```
`new_string`:
```
**(2) Cycle-N-vs-cycle-(N-1) finding-overlap detection.** New Auditor phase: read cycle (N-1)'s issue file (if exists). For each finding in cycle N, find the maximum `difflib.SequenceMatcher(<title-N>, <title-N-1>).ratio()` over cycle (N-1)'s finding titles (after stripping the AC-ID prefix and severity tag). If ≥ 50 % of cycle N's findings score > 0.70 against any cycle (N-1) finding → emit MEDIUM finding "cycle-N findings substantially overlap cycle-(N-1) — loop may be spinning; recommend human review." Threshold is operator-tunable via `AIW_LOOP_DETECTION_THRESHOLD` (default `0.70`).
```

---

#### M17 — T28 verdict logic + nice_to_have.md slot drift unaddressed

**Task:** task_28_evaluate_server_side_compaction.md
**Location:** task_28 §Smoke test:
> `# If verdict is DEFER, nice_to_have.md has a new entry`
> `if grep -iq "verdict.*DEFER" design_docs/analysis/server_side_compaction_evaluation.md; then`
> `  grep -q "server.side compaction" design_docs/nice_to_have.md`

**Issue:** Verified `design_docs/nice_to_have.md` exists; T28 makes no slot-number claim, just appends with title-grep. That part is OK. However:

- `design_docs/analysis/` exists (verified — has `langgraph_mcp_pivot.md` and `post_0.1.2_audit_disposition.md`). T28's deliverable lands there, fine.
- T06 also lands a doc in `design_docs/analysis/` (`autonomy_model_dispatch_study.md`). Two new analysis docs land within M20.
- Neither T06 nor T28 flags how they show up in `design_docs/analysis/`'s "what's here" index (if there is one). The directory's existing files lack a README.

**Recommendation:** Lower-priority. Add a deliverable note to T06 + T28 that `design_docs/analysis/` gains an entry; if there's no README in that directory, no further action. Otherwise update the README.

(Ship this as carry-over to T06 + T28 specs.)

**Apply this fix:** Add to task_06 + task_28 §Deliverables a single line: "If `design_docs/analysis/README.md` exists, add a row to its index pointing at this study/evaluation. (Verified absent 2026-04-27 — no README.md needed at this milestone; can be added later.)"

---

### 🟢 LOW

#### L1 — T01 fixture-spawn tests (`tests/agents/test_return_schema_compliance.py`) require live Task spawns to be hermetic

**Task:** task_01_sub_agent_return_value_schema.md
**Issue:** Spawning each agent on a "minimal fixture task" and asserting the return parses cleanly requires running the actual Claude Code Task tool with each agent. That's not hermetic — it consumes weekly quota, depends on model availability, and adds nondeterminism (LLM output variance).
**Recommendation:** Make the fixture-spawn tests opt-in via an env-var (`AIW_AGENT_SCHEMA_E2E=1`), not the default. The default test suite uses a stub-spawn that returns canned schema-conformant text + canned non-conformant text + asserts the orchestrator-side parser handles each correctly. Cite the existing `AIW_E2E=1` pattern.
**Push to spec:** yes — append to T01 carry-over.

---

#### L2 — T03's `(within 10 %)` test threshold

**Task:** task_03_in_task_cycle_compaction.md
**Issue:** Cycle 2 input ≈ cycle 1 input "within 10 %" — what's the source of the 10% number? Without a concrete baseline (the M12 T01 spawn was 12.4 K input tokens; cycle 2's spawn is target 12.4 K ± 1.24 K) the test is impressionistic.
**Recommendation:** Replace with a concrete absolute threshold tied to a real measurement, OR keep the relative threshold but note in the test docstring that 10% is the heuristic (not an empirical bound).
**Push to spec:** yes.

---

#### L3 — T04 cross-task test thresholds same issue as L2

**Task:** task_04_cross_task_iteration_compaction.md
**Issue:** "Iter 5's input-token-count ≈ iter 1's (within 10 %)" — same 10% heuristic. Same recommendation.
**Push to spec:** yes.

---

#### L4 — T05 wall-clock benchmark is `bench_terminal_gate.py` (not in CI) — needs explicit invocation hook

**Task:** task_05_parallel_terminal_gate.md
**Issue:** The bench file lands but is "not in CI" — needs a documented invocation hook (e.g. add to a `pytest.ini` `markers` block or a Makefile target) so future runs can find it. Without one it's a forgotten file.
**Recommendation:** Add `@pytest.mark.benchmark` decorator + register the marker in pyproject.toml's `[tool.pytest.ini_options]` block. Then `uv run pytest -m benchmark` runs benchmarks on demand.
**Push to spec:** yes.

---

#### L5 — T06 weekly-quota cost estimate "1-2% of weekly Max quota" is a guess

**Task:** task_06_shadow_audit_study.md
**Issue:** §Methodology line 54: "Estimate: 1-2% of weekly Max quota for the study." No source. Could be 5%; could be 10%. Worth labelling explicitly as a guess so the user has appropriate expectations going in.
**Recommendation:** Reframe as "expected to consume 1–2% of weekly quota based on prior observation, but instrument with T22 telemetry from the first cell run and bail if cost exceeds 5% projected to study end."
**Push to spec:** yes.

---

#### L6 — T20 ADVISORY tier doesn't exist in the live auditor's severity vocabulary

**Task:** task_20_carry_over_checkbox_cargo_cult_extended.md
**Issue:** Live auditor uses HIGH / MEDIUM / LOW. T20 introduces "ADVISORY" for the rubber-stamp detection. Cleanest is to use one of the three existing tiers (probably MEDIUM with a "(advisory — verify reasoning)" suffix) rather than introducing a new tier.
**Recommendation:** Use MEDIUM. Same severity, same surface, no new tier.
**Push to spec:** yes.

---

#### L7 — T07 helper supports flag values via Python CLI but slash commands describe a markdown procedure

**Task:** task_07_dynamic_model_dispatch.md
**Issue:** §Deliverables — `python scripts/dispatch.py <role> --flag <default|expert|cheap>` is a Python invocation; slash commands are markdown procedure documents. The orchestrator (running in Claude Code) does have Bash access, so the invocation works — but it's worth being explicit about the boundary the same way T22 does ("the orchestrator runs in Claude Code, has Bash + Read access, can do this in a single follow-up turn after each Task return").
**Recommendation:** Add a one-line clarification in T07 that the helper is invoked via Bash by the slash-command orchestrator at each spawn boundary.
**Push to spec:** yes.

---

#### L8 — Several specs cite `tiktoken` as a candidate token-counter without confirming dep landing strategy

**Task:** task_02_sub_agent_input_prune.md (mentions `tiktoken` as candidate; falls back to "regex-based proxy"); same hedge in T03 / T22.
**Issue:** Multiple specs hedge between `tiktoken` and a regex proxy without picking one. The hedge plus M5's pyproject.toml note plus M9's no-coefficient stance all converge on "regex proxy is the right answer." Just commit to it across all specs.
**Recommendation:** Pick the regex proxy across T01, T02, T03, T22, T23. Drop `tiktoken` references everywhere.
**Push to spec:** yes (consolidated note: every spec that proxies token-counts uses the same regex helper, defined once in T02 and reused).

---

## What's structurally sound

The Round-1 specs land most of the heavy lifting correctly. Verified-correct elements:

- **README §Cross-phase dependencies** correctly identifies T21 → T06/T07 (Opus 4.7 forward-compat blocker) and T22 → T06 (telemetry as evidence-gathering).
- **Task spec dependency declarations on T21 + T22** for T06 + T07 are consistent with README (HIGH/blocking on both surfaces).
- **Research-brief Lens citations** (Lens 1.3, 1.4, 2.1, 2.2, 2.3, 2.4, 3.2, 3.3, 3.4, 3.5) all map to real `### N.M` headings in `research_analysis`.
- **All cited prior-milestone references for T06's task selection** check out: `M12 T01`, `M12 T02`, `M12 T03`, `M16 T01`, `M14 close-out` (= M14 T02 milestone_closeout) all exist.
- **T01's "out of scope" hedge** about Claude Code Task tool not exposing `outputFormat: json_schema` is consistent with the actual surface evidence (the same pattern recurs in T27 + T28 — surface-check needed).
- **The seven `thinking:` literals are correctly inventoried** by T21 (6 × `thinking: max` + 1 × `thinking: high`); the spec just needs to include the seventh (H3).
- **KDR-014 / ADR-0009 grounding** is correctly cited in README's Key-decisions table for T07's `--expert` / `--cheap` operator-knob framing.
- **Autonomy-decision-2 isolated-commit rule** is correctly invoked by T07 (modulo M8's framing fix).
- **`runs/` is gitignored** per current `.gitignore` (`runs/*` + `!runs/.gitkeep`).
- **`scripts/` directory exists** so T07 / T22 / T23 / T27 helper additions don't need directory creation.
- **`design_docs/analysis/` directory exists** for T06 + T28 study/evaluation outputs.

---

## Cross-cutting context

- **Project memory state.** `project_autonomy_optimization_followups.md` confirms autopilot validated 2026-04-27; M20's optimization scope is informed by that validation. `feedback_autonomous_mode_boundaries.md` confirms the eight autonomy decisions M20 leans on (especially decision 2 — KDR / high-impact change isolation on separate commits). Memory does NOT flag M20 as on-hold or pending external trigger — the milestone is active.
- **M20 split into M20 + M21 (audit recommendation M3).** M20's task pool (15 specs) is the post-split scope. M21 directory exists at `design_docs/phases/milestone_21_autonomy_loop_continuation/` (verified). Cross-references TO M21 in M20 specs ("moved to M21") are not analyzed in this round (M21 is its own milestone scope).
- **Research-brief is the load-bearing grounding doc for almost every M20 spec.** The file `research_analysis` is text-format with `### N.M` Lens headings; specs cite as `§Lens N.M` which is unambiguous. No drift detected between specs and brief.
- **Structural design: M20 changes infra, not runtime.** No KDR-002 / -003 / -004 / -006 / -008 / -009 / -013 drift findings raised — those KDRs are runtime invariants and the M20 spec set leaves runtime alone (modulo H1's incorrect runtime-module reference, which is an authoring slip not a real KDR violation). KDR-014 / ADR-0009 IS load-bearing and is correctly cited (M8 verifies T07's framing aligns).
- **Surface-feasibility risk is the dominant theme across HIGH findings** (H1, H6, M7). The Anthropic SDK exposes parameters that Claude Code's Task wrapper may not surface. T01 already absorbed this lesson by demoting `outputFormat: json_schema` to "out of scope." T22 + T27 + T28 all need similar surface-checks before their main deliverables can be relied upon. Recommend the orchestrator coordinate a single empirical surface-check probe (one-time spike) before Phase A starts in earnest, rather than three independent checks.
- **The M12 T07 close-out task is repeatedly referenced as the M20 prerequisite** (README §Dependencies on prior milestones), but M12 T07 spec does not yet exist. This is M12's scope (and M12's existing issue files track it as `DEFERRED (owner: M12 T07, spec pending)`). M20 inherits the pre-condition; not M20's job to fix, but worth the user knowing M20 cannot ship its before/after measurements until M12 T07 closes.
