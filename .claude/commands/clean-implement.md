---
model: claude-opus-4-7
thinking:
  type: adaptive
effort: high
# Per-role effort assignment: see .claude/commands/_common/effort_table.md
---

# /clean-implement

You are the **Clean Implementation loop controller** for: $ARGUMENTS

`$ARGUMENTS` is a task identifier — a task ID, spec file path, or shorthand like "m16 t1". You orchestrate a Builder → Auditor loop up to 10 cycles, then run a Security gate (security-reviewer + dependency-auditor when relevant) before declaring the task shippable. **All substantive work runs in dedicated subagents via `Task` spawns** — your job is orchestration and stop-condition evaluation only. Do not implement, do not audit, do not write the issue file yourself.

(This is `Task`-based subagent dispatch, not slash-command chaining. The orchestration loop below stays inlined here so the loop controller never halts after a sub-step returns.)

---

## Agent-return parser convention

After every `Task` spawn, parse the agent's return per
[`.claude/commands/_common/agent_return_schema.md`](_common/agent_return_schema.md):

1. Capture the full text return to `runs/<task>/cycle_<N>/agent_<name>_raw_return.txt`.
2. Split on `\n`; expect exactly 3 non-empty lines.
3. Each line must match `^(verdict|file|section): ?(.+)$`.
4. The `verdict` value must be one of the agent's allowed tokens (see schema reference); trailing whitespace on any value is stripped before validation.
5. On any failure: halt, surface `BLOCKED: agent <name> returned non-conformant text —
   see runs/<task>/cycle_<N>/agent_<name>_raw_return.txt`. **Do not auto-retry.**

---

## Project setup (run once at the start of cycle 1)

Resolve `$ARGUMENTS` to concrete paths:

- **Spec path:** `design_docs/phases/milestone_<M>_<name>/task_<NN>_<slug>.md`. Resolve shorthand by glob: "m16 t1" → `design_docs/phases/milestone_16_*/task_01_*.md`. If multiple matches, ask the user.
- **Issue file path:** `design_docs/phases/milestone_<M>_<name>/issues/task_<NN>_issue.md`. May not exist on cycle 1.
- **Parent milestone README:** `design_docs/phases/milestone_<M>_<name>/README.md`.

Build the **project context brief** — pass verbatim to every subsequent `Task` spawn so subagents don't have to rediscover conventions:

```text
Project: ai-workflows (Python, MIT, published as jmdl-ai-workflows on PyPI)
Layer rule: primitives → graph → workflows → surfaces (enforced by `uv run lint-imports`)
Gate commands: `uv run pytest`, `uv run lint-imports`, `uv run ruff check`
Architecture: design_docs/architecture.md (especially §3 four-layer rule, §6 dep table, §9 KDRs)
ADRs: design_docs/adr/*.md
Deferred-ideas file: design_docs/nice_to_have.md (out-of-scope by default)
Changelog convention: ## [Unreleased] → ### Added — M<N> Task <NN>: <Title> (YYYY-MM-DD)
Dep manifests: pyproject.toml + uv.lock — either changing triggers the dependency-auditor
Load-bearing KDRs: 002 (MCP-as-substrate), 003 (no Anthropic API), 004 (validator pairing),
                   006 (three-bucket retry via RetryingEdge), 008 (FastMCP + pydantic schema as
                   public contract), 009 (SqliteSaver-only checkpoints),
                   013 (user-owned external workflow code)
Issue file path: <resolved above>
Status surfaces (must flip together at task close): per-task spec **Status:** line,
                   milestone README task table row, tasks/README.md row if present,
                   milestone README "Done when" checkboxes
```

If anything material is unclear (spec missing, milestone README absent, ambiguous shorthand) — **stop and ask the user** before spawning agents.

---

## Spawn-prompt scope discipline

**Reference:** [`.claude/commands/_common/spawn_prompt_template.md`](_common/spawn_prompt_template.md)

Pass only what each agent will certainly use. Let agents pull the rest on demand via their
own `Read` tool. Full-document content inlining is wasteful; path references are always safe.

After every `Task` spawn, capture the spawn-prompt token count (regex proxy:
`len(re.findall(r"\S+", text)) * 1.3`, truncated to int) into
`runs/<task>/cycle_<N>/spawn_<agent>.tokens.txt` (nested per-cycle directory; no `_<cycle>`
suffix on the filename).

### runs/<task>/ directory convention

Create `runs/<task-shorthand>/cycle_1/` at the **start of cycle 1**, before spawning the
first Builder.  Create `runs/<task-shorthand>/cycle_<N>/` at the start of each subsequent
cycle.  `<task-shorthand>` is `m<MM>_t<NN>` with both M and T zero-padded to two digits
(e.g. `m20_t03`, `m05_t02`, `m09_t01`).

Per-cycle directory layout (canonical):

```
runs/<task-shorthand>/
  cycle_1/
    summary.md                  ← T03 — cycle-summary (Auditor emits)
    security-review.md          ← security reviewer fragment
    spawn_<agent>.tokens.txt    ← T02 — per-spawn token count
    agent_<name>_raw_return.txt ← T01 — full text return per agent
    auditor_rotation.txt        ← T27 — rotation event log (present only if rotation fired)
  cycle_2/
    ...
  cycle_N/
    ...
  integrity.txt                 ← T09 — pre-commit ceremony (top-level, latest run wins)
```

See [`.claude/commands/_common/cycle_summary_template.md`](_common/cycle_summary_template.md)
for the full `cycle_<N>/summary.md` template and the read-only-latest-summary rule.

### Builder spawn — read-only-latest-summary rule

**Cycle 1** — minimal pre-load set:
- Task spec path
- Issue file path (may not exist yet)
- Parent milestone README path
- Project context brief

**Cycle N (N ≥ 2)** — replace the parent milestone README with the latest cycle summary:
- Task spec path
- Issue file path
- **Most recent `runs/<task>/cycle_{N-1}/summary.md`** (include path + content inline)
- Project context brief

**Do not include** prior Builder reports' chat content, prior Auditor chat content, or
prior cycle summaries beyond `cycle_{N-1}/summary.md`.  The summary is the durable
carry-forward; earlier chat history is ephemeral and must not re-enter the spawn prompt.

**Remove from inline content (all cycles):** sibling task issue files, `architecture.md`
content, `CHANGELOG.md` content.

Output budget directive (include verbatim in the Builder spawn prompt):

```
Output budget: 4K tokens. Durable findings live in the file you write;
the return is the 3-line schema only — see .claude/commands/_common/agent_return_schema.md
```

### Auditor spawn — read-only-latest-summary rule

**Cycle 1** — minimal pre-load set:
- Task spec path
- Issue file path
- Parent milestone README path
- Project context brief
- Current `git diff`
- Cited KDR identifiers (parsed from the task spec — e.g. "KDR-003, KDR-013")

**Cycle N (N ≥ 2)** — add the latest cycle summary:
- Task spec path
- Issue file path
- Parent milestone README path
- Project context brief
- Current `git diff`
- Cited KDR identifiers (compact pointer)
- **Most recent `runs/<task>/cycle_{N-1}/summary.md`** (include path + content inline)

**Do not include** prior cycle summaries beyond the most recent one.  The summary is the
durable carry-forward; full prior-cycle chat history must not re-enter the spawn prompt.

**Remove from inline content (all cycles):** whole `architecture.md` content (Auditor reads
on-demand), sibling issue file content, whole-milestone-README content. Path references
stay; content inlining goes.

**KDR pre-load rule:** parse KDR citations from the task spec. Pass only those identifiers
as a compact list (e.g. "Relevant KDRs: KDR-003, KDR-013 — read §9 of architecture.md
on-demand for the full text"). When no KDRs are cited, pass the §9 grid header only.

Output budget directive (include verbatim in the Auditor spawn prompt):

```
Output budget: 1-2K tokens. Durable findings live in the issue file you write;
the return is the 3-line schema only — see .claude/commands/_common/agent_return_schema.md
```

### Reviewer spawns (security-reviewer, dependency-auditor)

Minimal pre-load set: task spec path, issue file path, project context brief, current
`git diff`, list of files touched (aggregated from Builder reports across all cycles).

**Remove from inline content:** full source file content, full test file content,
`architecture.md` content.

Output budget directive (include verbatim in each reviewer spawn prompt):

```
Output budget: 1-2K tokens. Durable findings live in the issue file you append;
the return is the 3-line schema only — see .claude/commands/_common/agent_return_schema.md
```

---

## Stop conditions (check after every audit, in priority order)

1. **BLOCKER** — Issue file contains a HIGH issue marked `🚧 BLOCKED` requiring user input. Stop, surface verbatim.
2. **USER INPUT REQUIRED** — Any issue recommends "stop and ask the user" / "user decision needed" **and the auditor's recommendation is genuinely ambiguous** (two or more reasonable paths surfaced; the auditor declines to pick one; the choice is a substantive design lock the user must own). Stop, list all such issues. **Auditor-agreement bypass:** if the auditor surfaced a single clear recommendation (one path, not "Option A vs Option B for the user to pick") and the orchestrator concurs with that recommendation against the spec + KDRs + locked decisions in the issue file, treat the recommendation as the locked decision: stamp it into the issue file as `Locked decision (loop-controller + Auditor concur, YYYY-MM-DD): <one-line summary>`, feed it to the next Builder cycle as a carry-over AC, and continue the loop. Halt only if (a) the auditor presents two or more options without a recommendation, or (b) the recommendation conflicts with a locked KDR / prior user decision / the spec, or (c) the recommendation expands scope beyond the spec, or (d) the recommendation defers work to a future task that the user hasn't already agreed exists. Surface every auto-locked decision in the end-of-cycle one-liner so the user can override on the next turn.
3. **FUNCTIONALLY CLEAN** — Issue file status line reads `✅ PASS` with no OPEN issues. Proceed to the **security gate** below. Only after the security gate passes is the task fully CLEAN.
4. **CYCLE LIMIT** — 10 build → audit cycles without 1–3. Stop, present outstanding issues. **Do not run the security gate against an unclean task.**

**At the start of cycle 1 only:** if the issue file already contains an unresolved BLOCKER from a prior session, treat as condition 1 immediately — don't spawn the Builder against an open blocker.

---

## Loop procedure

For cycles 1..10:

### Step 1 — Builder

Spawn the `builder` subagent via `Task` with the inputs prescribed by the
"Builder spawn — read-only-latest-summary rule" section above (cycle 1: include
parent milestone README path; cycle N ≥ 2: replace it with the latest cycle
summary content). Wait for completion. Capture the Builder's report.

**Telemetry (T22):** before spawning, run:
```bash
python scripts/orchestration/telemetry.py spawn --task <task-shorthand> --cycle <N> \
  --agent builder --model <model-slug> --effort <effort>
```
After the Task returns, run:
```bash
python scripts/orchestration/telemetry.py complete --task <task-shorthand> --cycle <N> \
  --agent builder --input-tokens <n> --output-tokens <n> \
  [--cache-creation <n>] [--cache-read <n>] --verdict <BUILT|BLOCKED|STOP-AND-ASK> \
  [--fragment-path <path>] [--section <section>]
```
Record lands at `runs/<task>/cycle_<N>/builder.usage.json`.

### Step 2 — Auditor

**Input-volume rotation trigger (T27):** Before spawning the Auditor on cycle N ≥ 2,
read `runs/<task>/cycle_{N-1}/auditor.usage.json` (T22 record from the previous cycle).
Run the rotation check:

```bash
python scripts/orchestration/auditor_rotation.py \
  --input-tokens <input_tokens from cycle_{N-1} record> \
  --verdict <verdict from cycle_{N-1} record>
```

- Output `ROTATE` (exit 1) AND cycle N-1 verdict was `OPEN` → spawn the Auditor with
  the **compacted input** (spec path + issue file path + project context brief +
  current `git diff` + `runs/<task>/cycle_{N-1}/summary.md` content only).
  Write the rotation event log:
  ```bash
  # Path: runs/<task>/cycle_{N-1}/auditor_rotation.txt
  # Content: ROTATED: cycle <N-1> input_tokens=<value>; cycle <N> spawn input
  #          compacted (cycle_summary + diff only)
  ```
  See [`.claude/commands/_common/auditor_context_management.md`](_common/auditor_context_management.md)
  for the full compacted-input shape and Path A rejection rationale (audit H6).
- Output `NO-ROTATE` (exit 0) → spawn the Auditor with the **standard input** per
  the "Auditor spawn — read-only-latest-summary rule" section above.
- **Cycle 1:** no prior telemetry record exists; always use standard input (no rotation check).
- **Verdict PASS:** rotation check is moot — the loop ends. No rotation log written.

`AIW_AUDITOR_ROTATION_THRESHOLD` env var lowers/raises the trigger threshold (default
60 000 input tokens). Pass it through when invoking the helper.

Spawn the `auditor` subagent via `Task` with the inputs selected above (compacted or
standard). Include cited KDR identifiers (compact pointer per scope-discipline section
above). Wait for completion.

**Telemetry (T22):** before spawning, run:
```bash
python scripts/orchestration/telemetry.py spawn --task <task-shorthand> --cycle <N> \
  --agent auditor --model <model-slug> --effort <effort>
```
After the Task returns, run:
```bash
python scripts/orchestration/telemetry.py complete --task <task-shorthand> --cycle <N> \
  --agent auditor --input-tokens <n> --output-tokens <n> \
  [--cache-creation <n>] [--cache-read <n>] --verdict <PASS|OPEN|BLOCKED> \
  [--fragment-path <issue-file-path>] [--section <section>]
```
Record lands at `runs/<task>/cycle_<N>/auditor.usage.json`.

### Step 3 — Read issue file and evaluate stop conditions

**Read the issue file on disk.** Do not trust the Auditor's chat summary — the issue file is the source of truth. Evaluate the four stop conditions in order against what's actually written. If condition 3 (FUNCTIONALLY CLEAN) triggers, go to the **security gate**. If none trigger and cycles remain, loop to Step 1 targeting only the OPEN issues the audit identified.

**Between Step 1 and Step 2, forbidden:**

- Summary of what the Builder did.
- Verdict on the gates ("gates pass, so the cycle is clean").
- Self-predicted cycle status.
- A "ready for audit" todo update.
- Editing the issue file yourself.

The Auditor is the only thing that can decide whether the task is functionally clean.

---

## Security gate (runs once, after FUNCTIONALLY CLEAN)

The functional audit confirmed the task does what the spec says. The security gate confirms it doesn't introduce risks the spec didn't address. Runs **after** the loop reaches FUNCTIONALLY CLEAN, not on every cycle.

### Step S1 — Security reviewer (always runs)

Spawn `security-reviewer` via `Task` with: task identifier, spec path, issue file path, project context brief, list of files touched across the whole task (aggregate from all Builder reports), cited KDR identifiers (compact pointer per scope-discipline section above).

The security-reviewer writes findings into the same issue file under `## Security review`. Verdict line: `SHIP | FIX-THEN-SHIP | BLOCK`.

**Telemetry (T22):** before spawning, run:
```bash
python scripts/orchestration/telemetry.py spawn --task <task-shorthand> --cycle <N> \
  --agent security-reviewer --model <model-slug> --effort <effort>
```
After the Task returns, run `complete` with the security verdict. Record lands at
`runs/<task>/cycle_<N>/security-reviewer.usage.json`.

### Step S2 — Dependency auditor (conditional)

Run **only if** the aggregated diff across this task touched `pyproject.toml` or `uv.lock`. Check by inspecting Builder reports for manifest edits.

If triggered, spawn `dependency-auditor` via `Task` with: task identifier, list of dep-manifest files changed, project context brief, lockfile path. Output appends under `## Dependency audit` in the issue file. Verdict line: `SHIP | FIX-THEN-SHIP | BLOCK`.

If not triggered, note in the issue file: `Dependency audit: skipped — no manifest changes.`

### Step S3 — Read issue file and evaluate security verdicts

Re-read the issue file. Evaluate in priority order:

1. **SECURITY BLOCKER** — Either reviewer's verdict is `BLOCK`. Stop and surface findings verbatim. The task is **not** CLEAN. Next action is another Builder → Auditor cycle targeting these findings (security-relevant code changes must be re-audited for functional regressions), not a retry of the security gate alone.
2. **SECURITY FIX-THEN-SHIP** — Either reviewer's verdict is `FIX-THEN-SHIP`. Stop and surface findings. The same Auditor-agreement bypass from functional condition 2 applies here: if the security reviewer surfaced a single clear recommendation (e.g. "restore §X subsection per 0.1.3 wording", "deprecate flag Y", "add input length cap") and the orchestrator concurs against the threat model + KDRs, stamp it as `Locked security decision (loop-controller + reviewer concur, YYYY-MM-DD): <summary>` in the issue file, feed it to the next Builder cycle as a carry-over AC, and re-loop. Halt and surface only if (a) the reviewer presents two or more options without a recommendation, (b) the recommendation conflicts with a locked KDR / prior user decision / the spec, (c) the recommendation expands scope, or (d) the recommendation defers to a future task the user hasn't already agreed exists. **Pre-existing-regression carve-out:** when the reviewer explicitly frames a finding as a pre-existing regression introduced by an earlier task and names a specific future-task owner, that defers-work clause (d) is satisfied only if the future task already exists and accepts the carry-over without scope expansion.
3. **CLEAN** — All applicable reviewers' verdicts are `SHIP`. Report the task fully CLEAN.

When re-looping from a security verdict, the Builder's next-cycle inputs include the security findings as carry-over ACs (the Auditor grades them as ACs on re-audit — which is what you want; security fixes get the same "re-verify the whole scope" treatment as any other change).

---

## Gate-capture-and-parse convention (required before declaring CLEAN)

**Reference:** [`.claude/commands/_common/gate_parse_patterns.md`](_common/gate_parse_patterns.md)

Before declaring the task fully CLEAN (after the security gate passes), the orchestrator
independently runs each gate command and captures output to
`runs/<task>/cycle_<N>/gate_<name>.txt`.

### Capture step

For each gate (`uv run pytest`, `uv run lint-imports`, `uv run ruff check`, plus any
task-specific smoke test gates named in the spec):

1. Run the gate command via Bash.
2. Capture stdout + stderr + exit code into `runs/<task>/cycle_<N>/gate_<name>.txt`
   using the format described in `_common/gate_parse_patterns.md` §Capture format.
   Gate file names: `gate_pytest.txt`, `gate_lint-imports.txt`, `gate_ruff.txt`
   (task-specific gates use their command slug, e.g. `gate_smoke.txt`).
3. Record the exit code in the same file or a companion `gate_<name>.exit` file.

### Parse step

For each captured file, parse the footer line per the regex table in
`_common/gate_parse_patterns.md`:

- `pytest`:       `^=+ \d+ passed` (and no `failed` on the same line)
- `ruff`:         `^All checks passed\.$` or `^\d+ files? checked\.$`
- `lint-imports`: `^Contracts kept$` (exact, trimmed)

### Halt condition

If **any** of the following is true for any gate, halt immediately with:

```
🚧 BLOCKED: gate <name> output not parseable; see runs/<task>/cycle_<N>/gate_<name>.txt
```

1. The captured file is empty (zero bytes or whitespace only).
2. No line in the file matches the gate's footer regex.
3. Exit code ≠ 0 (even if a footer line is present).
4. Footer line is present but indicates failures (e.g. `failed` in a pytest footer).

**Do not declare the task CLEAN if any gate halts.**

The captured files become the durable record consulted by the user on their follow-up
review (per the per-cycle directory layout above).

---

## Reporting

End-of-cycle one-liner for build → audit cycles:

`Cycle N/10 — [FUNCTIONALLY CLEAN | OPEN: <count> issues | BLOCKED: <issue-id> | USER INPUT: <issue-id>]`

End-of-security-gate one-liner:

`Security gate — [CLEAN | SEC-BLOCK: <count> | SEC-FIX: <count>]`

Final-stop summary: stop condition triggered (functional or security), total cycle count (build → audit + re-loops from security), remaining OPEN issues (id + one-liner), what the user needs to do next.

---

## Why the security gate is separate, not per-cycle

Running security-reviewer every cycle would burn tokens on the same code twice — once when it's broken and noisy, once when it's stable. A Critical-severity security finding before the code even compiles is useless signal. The functional loop gets the code correct; the security gate then checks the corrected code against a threat model the functional Auditor doesn't own. Security findings still re-enter the functional loop as carry-over ACs — so a security fix doesn't skip the Auditor.

## Why the reviewers don't run inline

The security-reviewer and dependency-auditor have narrower scopes and more opinionated threat models than the Auditor. Fresh context, their own system prompts, and read-only-ish tooling is what makes their output worth the spend. Running their logic inside the Auditor's context would dilute both.

## Why the Builder and Auditor are subagents (not inline)

Inline implementation pollutes the orchestrator's context with every Builder edit + every Auditor re-read. The orchestrator only needs the issue file's status line + the Builder's terse report to drive the loop. Moving each phase into a `Task` spawn keeps the orchestrator's context small (so 10 cycles fit in budget) and lets the auditor's read-only stance be enforced by its agent definition rather than relying on inline self-discipline.
