# Task 01 — Sub-agent return-value schema (3-line `verdict / file / section`)

**Status:** 📝 Planned.
**Kind:** Compaction / doc + code.
**Grounding:** [milestone README](README.md) · [research brief `research_analysis` §Lens 1.3](research_analysis) · memory `project_autonomy_optimization_followups.md` thread #12 · [`.claude/agents/auditor.md`](../../../.claude/agents/auditor.md) · [`.claude/agents/builder.md`](../../../.claude/agents/builder.md) · [other 7 agents under `.claude/agents/`](../../../.claude/agents/) · [`.claude/commands/auto-implement.md`](../../../.claude/commands/auto-implement.md).

## What to Build

A **hard 3-line return-value schema** enforced across all 9 sub-agents in the autonomy fleet (builder, auditor, security-reviewer, dependency-auditor, task-analyzer, architect, sr-dev, sr-sdet, roadmap-selector). Each agent's `## Return to invoker` section is rewritten to mandate this exact format:

```
verdict: <one-of-allowed-tokens>
file: <path-to-durable-artifact-or-"—">
section: <## section header just written or "—">
```

The orchestrator (slash-command layer) parses these 3 lines deterministically; any return that doesn't match the schema halts the autonomy loop and surfaces the malformed return for user investigation. **No auto-retry on malformed return** — a non-conformant return signals a deeper problem with the agent prompt or the agent's reasoning, and halt-and-surface is safer than auto-retry which would mask the bug.

This task is the **foundation of the M20 compaction quartet (Phase A)**. Without T01, downstream pruning (T02 input prune, T03 in-task cycle compaction, T04 cross-task iteration compaction) leaks chat-summary bodies that the orchestrator has to filter at parse time. With T01, the bodies do not exist in the agent's return at all — the schema mandate eliminates them upstream. T01 also unblocks T05 (parallel terminal gate — fragment-file format reuses the schema) and T08 (gate-output integrity uses the verdict line as the first parse target).

## Why a hard schema, not a soft convention

The autonomy loop's stop conditions (CLEAN, OPEN, STOP-AND-ASK, etc.) are evaluated by the orchestrator reading the verdict line. Today, agents return verdict-tokens embedded in multi-paragraph chat summaries; the orchestrator regex-greps for the verdict and trusts the surrounding prose. Two failure modes already observed in the M12 autopilot validation:

1. **Verdict ambiguity.** An auditor return that says "I would normally call this PASS but there's a HIGH finding..." has both PASS and HIGH in the text. The orchestrator's regex picks the first match, which can be wrong.
2. **Context bloat.** A 2 KB chat summary per agent invocation × 9 agents per cycle × 5 cycles per task × 5 tasks per autopilot run = 450 KB of chatter the orchestrator carries through stop-condition evaluation. Hard schema reduces this to ~50 tokens per invocation.

The 3-line schema eliminates both: the verdict line is unambiguous (`verdict: PASS` is a complete signal), and the orchestrator reads the durable artifact (issue file, recommendation file) for any detail it needs.

## Per-agent verdict tokens

| Agent | Verdict tokens | Durable artifact (`file:` field) | Section header (`section:` field) |
|---|---|---|---|
| `builder` | `BUILT` / `BLOCKED` / `STOP-AND-ASK` | `runs/<task>/cycle_<N>/builder_handoff.md` (NEW per T03 — per-cycle nested directory per audit M11) | `—` |
| `auditor` | `PASS` / `OPEN` / `BLOCKED` | `design_docs/phases/<milestone>/issues/task_<NN>_issue.md` | `—` (auditor writes the entire issue file) |
| `security-reviewer` | `SHIP` / `FIX-THEN-SHIP` / `BLOCK` | `design_docs/phases/<milestone>/issues/task_<NN>_issue.md` | `## Security review (YYYY-MM-DD)` |
| `dependency-auditor` | `SHIP` / `FIX-THEN-SHIP` / `BLOCK` | `design_docs/phases/<milestone>/issues/task_<NN>_issue.md` (or CHANGELOG `### Security`) | `## Dependency audit (YYYY-MM-DD)` |
| `task-analyzer` | `CLEAN` / `LOW-ONLY` / `OPEN` | `design_docs/phases/<milestone>/task_analysis.md` | `—` |
| `architect` | `ALIGNED` / `MISALIGNED` / `OPEN` / `PROPOSE-NEW-KDR` | `design_docs/phases/<milestone>/issues/task_<NN>_issue.md` | `## Architect review (YYYY-MM-DD)` |
| `sr-dev` | `SHIP` / `FIX-THEN-SHIP` / `BLOCK` | `design_docs/phases/<milestone>/issues/task_<NN>_issue.md` | `## Sr. Dev review (YYYY-MM-DD)` |
| `sr-sdet` | `SHIP` / `FIX-THEN-SHIP` / `BLOCK` | `design_docs/phases/<milestone>/issues/task_<NN>_issue.md` | `## Sr. SDET review (YYYY-MM-DD)` |
| `roadmap-selector` | `PROCEED` / `NEEDS-CLEAN-TASKS` / `HALT-AND-ASK` | `runs/queue-pick-<ts>.md` (or invoker-named recommendation file) | `—` |

(`section:` is `—` for agents that write a whole standalone file. The orchestrator reads the entire file for those.)

## Deliverables

### 9 agent files — uniform `## Return to invoker` section

For each of the 9 files in `.claude/agents/`, replace the existing `## Return to invoker` section (or insert before the `## Verification discipline` boilerplate if no such section exists) with the canonical 3-line-schema block, customised per agent:

```markdown
## Return to invoker

Three lines, exactly. No prose summary, no preamble, no chat body before or after:

\`\`\`
verdict: <one of: <PER-AGENT TOKEN LIST>>
file: <repo-relative path to the durable artifact you wrote, or "—" if none>
section: <## section header just written, or "—" if you wrote a standalone file or no file at all>
\`\`\`

The orchestrator reads the durable artifact directly for any detail it needs. A return that includes a chat summary, multi-paragraph body, or any text outside the three-line schema is non-conformant — the orchestrator halts the autonomy loop and surfaces the agent's full raw return for user investigation. Do not narrate, summarise, or contextualise; the schema is the entire output.
```

The PER-AGENT TOKEN LIST is the second column of the table above.

### `.claude/commands/auto-implement.md` — orchestrator-side parser

Add a parsing convention under the Task-spawn invocation. The orchestrator, after every Task return:

1. Captures the agent's full text return into `runs/<task>/cycle_<N>/agent_<name>_raw_return.txt` (durable record for debugging — per-cycle nested directory per audit M11; T03 §directory layout is authoritative on artifact placement).
2. Splits the return on `\n`; expects exactly 3 non-empty lines.
3. Each line matches `^(verdict|file|section): ?(.+)$`.
4. The `verdict` value is one of the agent's allowed tokens.
5. On any failure: halt the loop, surface `🚧 BLOCKED: agent <name> returned non-conformant text — see runs/<task>/cycle_<N>/agent_<name>_raw_return.txt for full output`. Do not auto-retry.

(Same parser pattern in `/clean-tasks.md`, `/clean-implement.md`, `/queue-pick.md`, `/autopilot.md` — each command that spawns agents needs the parser. The parser logic is described in prose in each command file, not as code, since slash commands are markdown procedure documents.)

### `.claude/commands/_common/` directory + `agent_return_schema.md` (NEW — T01 lands the first file under `_common/`)

T01 is the first M20 task to introduce `.claude/commands/_common/`. Verified absent 2026-04-27 (`ls .claude/commands/_common/` returns "No such file or directory"). Run `mkdir -p .claude/commands/_common/` (or use Write, which creates parent dirs) before writing the first file there. Subsequent M20 tasks (T02 `spawn_prompt_template.md`, T05 `parallel_spawn_pattern.md`, T07 `dispatch_table.md`, T08 `gate_parse_patterns.md`, T09 `integrity_checks.md`, T21 `effort_table.md`, T23 extends T02's spawn_prompt_template.md, T27 `auditor_context_management.md`) populate additional files into this directory and can assume it exists.

#### `.claude/commands/_common/agent_return_schema.md`

A single canonical reference for the 3-line schema + the per-agent verdict tokens table. Each slash command's parser section links to this file rather than duplicating the table. Reduces drift if a verdict token is added or renamed later.

## Tests

### `tests/agents/test_return_schema_compliance.py` (NEW)

For each of the 9 agents, parametrize a hermetic spawn-and-validate test:

- Spawn the agent against a minimal fixture task (see fixture layout below).
- Capture the agent's return text.
- Assert exactly 3 lines, each matching `^(verdict|file|section): ?(.+)$`.
- Assert the `verdict` token is in the agent's allowed set.
- Assert total return length ≤ 100 tokens — using a **regex-based proxy** (`len(re.findall(r"\S+", text)) * 1.3`). Accuracy is not load-bearing; magnitude is. Same proxy as T02's spawn-prompt-size measurement and T22's input/output capture; canonical helper defined once in T02 and reused. **No `tiktoken` dependency** — adding a test-only dep would trigger the dependency-auditor on a foundation task; not worth it for a magnitude check.

Each agent gets at least 3 fixture cases — one per verdict-token outcome. Fixtures live under `tests/agents/fixtures/<agent_name>/`.

### `tests/agents/test_orchestrator_parser.py` (NEW)

Hermetic unit test of the orchestrator-side parser logic (extracted from the slash-command markdown into a small Python helper for testability):

- Conformant 3-line return → parsed correctly, returns `(verdict, file, section)` tuple.
- Empty return → raises `MalformedAgentReturn`.
- 4+ lines → raises.
- Bad regex on any line → raises.
- Verdict outside allowed set → raises.
- Whitespace-only line in the middle → raises.

## Acceptance criteria

1. All 9 agent files (`builder`, `auditor`, `security-reviewer`, `dependency-auditor`, `task-analyzer`, `architect`, `sr-dev`, `sr-sdet`, `roadmap-selector`) have a uniform `## Return to invoker` section structured as the 3-line schema with the per-agent verdict tokens from the table.
2. `.claude/commands/_common/agent_return_schema.md` exists as the canonical reference; it lists all 9 agents + their verdict tokens + their durable-artifact paths.
3. The 5 slash commands that spawn agents (`auto-implement`, `clean-tasks`, `clean-implement`, `queue-pick`, `autopilot`) describe the orchestrator-side parser convention with halt-on-malformed semantics, and link to `_common/agent_return_schema.md`.
4. `tests/agents/test_return_schema_compliance.py` passes for all 9 agents — at least 3 fixture cases per agent, one per verdict-token outcome.
5. `tests/agents/test_orchestrator_parser.py` passes with all positive + negative cases.
6. The token-cap test (≤ 100 tokens per agent return) passes for every fixture case.
7. CHANGELOG.md updated under `[Unreleased]` with `### Changed — M20 Task 01: Sub-agent return-value schema (3-line verdict / file / section), schema-compliance tests, orchestrator parser convention (research brief §Lens 1.3)`.
8. Status surfaces flip together at task close: this spec's `**Status:**` line, milestone README's task table row for T01, milestone README's "Done when" exit criterion #1.

## Smoke test (Auditor runs)

```bash
# Verify 3-line schema landed in every agent file
for agent in builder auditor security-reviewer dependency-auditor task-analyzer architect sr-dev sr-sdet roadmap-selector; do
  grep -A 6 "^## Return to invoker" .claude/agents/$agent.md | grep -q "^verdict:" \
    && echo "$agent OK" \
    || { echo "$agent FAIL — schema missing"; exit 1; }
done

# Verify _common reference exists
test -f .claude/commands/_common/agent_return_schema.md && echo "common reference OK"

# Verify each slash command links to the common reference
for cmd in auto-implement clean-tasks clean-implement queue-pick autopilot; do
  grep -q "_common/agent_return_schema.md" .claude/commands/$cmd.md \
    && echo "$cmd OK" \
    || { echo "$cmd FAIL — missing parser convention link"; exit 1; }
done

# Run schema-compliance + parser tests
uv run pytest tests/agents/test_return_schema_compliance.py tests/agents/test_orchestrator_parser.py -v
```

## Out of scope

- **Server-side `outputFormat: json_schema` enforcement via SDK.** Claude Code's `Task` tool surface (the orchestrator's spawn primitive) does not expose schema-enforcement parameters. Orchestrator-side parsing is the enforcement mechanism for T01. If Claude Code later exposes `outputFormat`, the parser becomes redundant — but that's a future change, not an M20 dep. (README's exit criterion 1 already names "prompt-mandate + orchestrator-side parsing" — no further README edit needed.)
- **Per-agent context-input pruning** — that's T02. T01 prunes only the *output* side; T02 prunes the *input* side.
- **Re-spawn-on-malformed retry** — non-conformant returns halt. The autonomy-loop boundary is "halt on sub-agent disagreement," and a malformed return is a kind of disagreement (the agent didn't produce the expected output shape). User investigation is the recovery mechanism.
- **Per-line token-count validation beyond the ≤ 100 total cap** — finer-grained caps (per-line, per-agent custom limits) would be over-engineering for schema enforcement.
- **Migration of the `template/` mirror agents** to the new schema. The `/home/papa-jochy/prj/ai-workflows-template/template/.claude/agents/` files are project-template scaffolds. T01 mirrors the schema to the template once the live ai-workflows agents are landing — but this is a small mirror-edit follow-up, not a substantive task.

## Dependencies

- **None blocking.** T01 is the foundation of M20 and lands first.

## Carry-over from prior milestones

*None.*

## Carry-over from task analysis

- **L1 (round 1, 2026-04-27):** Make the per-agent fixture-spawn schema-compliance tests opt-in via `AIW_AGENT_SCHEMA_E2E=1` (cite the existing `AIW_E2E=1` pattern). The default test suite uses a stub-spawn that returns canned schema-conformant + canned non-conformant text and asserts the orchestrator-side parser handles each correctly. Live Task spawns consume weekly Max quota and add LLM-output nondeterminism — gate them behind the env var.
- **L8 (round 1, 2026-04-27):** Use the regex-based proxy (`len(re.findall(r"\S+", text)) * 1.3`) for token-cap assertion. No `tiktoken` dep added; same proxy as T02 / T22 for consistency.

## Carry-over from prior audits

(populated by `/clean-implement` audit cycles)
