# Task 02 — Optional Plugin Manifest — Audit Issues

**Source task:** [../task_02_plugin_manifest.md](../task_02_plugin_manifest.md)
**Audited on:** 2026-04-21
**Audit scope:** trigger check, schema check, task-spec *Deferred* flip, CHANGELOG entry documenting the deferral + the schema-check findings a future Builder will need.
**Status:** ✅ PASS — Cycle 1/10. T02 exits via the spec-sanctioned *"skip if no trigger fires at kickoff"* path. Zero shipped manifest; schema-check findings captured for the future Builder.

## Design-drift check

Cross-check against [architecture.md](../../../architecture.md) + cited KDRs.

| Concern | Finding |
| --- | --- |
| New dependency | None. No `pyproject.toml` diff. |
| New `ai_workflows.*` module | None. Docs-only change (task file + CHANGELOG). |
| New layer / contract | None. `uv run lint-imports` still 4 kept. |
| LLM call added | None. |
| Checkpoint / resume logic | None. |
| Retry logic | None. |
| Observability backend | None. |
| Anthropic API surface | N/A — no code or skill text change. |
| KDR-002 (packaging-only) | Honoured. No `ai_workflows/` diff. |
| Spec accuracy | **Improved.** The T02 spec's guessed manifest location (`.claude/plugins/<name>/plugin.json`) + guessed required fields (`version`, `skills`, `mcp_servers`) are known-wrong against the real Claude Code plugin convention observed in `~/.claude/plugins/marketplaces/claude-plugins-official/plugins/*/.claude-plugin/plugin.json`. The deferral paragraph + *Schema-check findings* section prepended to the task file corrects this for the future Builder. |

No drift. No HIGH findings.

## Trigger check (gating, per task spec §*Trigger*)

| # | Trigger | Fired this session? |
| --- | --- | --- |
| 1 | User intends to distribute `ai-workflows` through the Claude Code plugin marketplace. | ❌ No. |
| 2 | A second host (Cursor, Zed, VSCode extension) asks for a manifest-based install surface on top of M4 MCP registration. | ❌ No. |
| 3 | Internal sharing needs a one-command install surface across multiple machines without cloning the repo. | ❌ No. |

Zero triggers fired → the task spec directs **"skip this task and proceed to T03. Record the skip in the M9 README's Outcome section at T04 time and leave the task file in place as `📝 Deferred (no trigger)`"** (T02 §*Trigger*, paragraph 2). That is exactly what this audit grades.

## Schema check (performed anyway, for future Builder)

The task spec's §*Schema check* block is gating: "**If the schema is not published or is in flux, stop and ask**". The check was performed despite the no-trigger skip so the findings are pinned in the repo before they evaporate from developer memory.

**Method.**

- `claude plugin --help` (Claude Code CLI present at `/home/papa-jochy/.local/bin/claude`) listed the subcommand surface (`install`, `validate`, `marketplace`, `disable`, …).
- Inspected three first-party plugins under `~/.claude/plugins/marketplaces/claude-plugins-official/plugins/`: `hookify`, `mcp-server-dev`, `pr-review-toolkit`.

**Findings.**

- Real manifest location: `.claude-plugin/plugin.json` (not `.claude/plugins/<name>/plugin.json` as T02's spec originally guessed).
- All three first-party plugins carried **only** three keys: `name`, `description`, `author`. No `version`, no `skills` array, no `mcp_servers` block.
- Skills live as a sibling `skills/` directory under the plugin root; discovery is convention, not manifest-declared.
- `claude plugin validate <path>` exists as an authoritative shape check — a future Builder should treat a green `validate` as the AC, not a hand-rolled JSON-schema assertion.

**Recommendation recorded in the task file** (prepended as *Schema-check findings (2026-04-21)*): rewrite the *Deliverables* + *Tests* blocks against the real schema when a trigger fires.

## Acceptance criteria grading (deferred disposition)

| # | Criterion | Verdict under deferred disposition |
| --- | --- | --- |
| 1 | Schema check documented in the issue log — either the schema was found and the manifest validates, or the task was downgraded to Deferred with a named blocker. | ✅ Schema check performed and documented (task file *Schema-check findings* section + this audit file). Task downgraded to `📝 Deferred (no trigger — 2026-04-21)` with the missing-trigger named. |
| 2 | If manifest shipped: `.claude/plugins/ai-workflows/plugin.json` parses as JSON and declares `name`, `version`, `description`, `skills`, `mcp_servers` per the schema check. | ⚪ N/A — no manifest shipped (deferral). Had it shipped, the spec's guessed fields would have been wrong per the schema check anyway. |
| 3 | If manifest shipped: `version` matches `pyproject.toml [project].version` (test-enforced). | ⚪ N/A — deferral. |
| 4 | No new runtime or dev dependency. `pyproject.toml` diff empty. | ✅ No `pyproject.toml` diff. |
| 5 | No new import-linter contract. Four-contract count preserved. | ✅ `uv run lint-imports` → 4 kept, 0 broken. |
| 6 | `uv run pytest` + `uv run lint-imports` + `uv run ruff check` all clean. | ✅ 592 passed / 5 skipped; lint-imports 4 kept; ruff clean. |

## 🔴 HIGH

*None.*

## 🟡 MEDIUM

*None.*

## 🟢 LOW

*None.*

## Additions beyond spec — audited and justified

- **Schema check executed even under no-trigger skip.** Spec directs the check only when the task proceeds; running it under deferral is *above spec*. Justification: the schema facts are easier to harvest now (live dev machine with first-party plugins on disk) than at an unknown future re-open date. Pinning them in the task file prevents a future Builder from repeating the same probe and reproducing the same wrong initial guess.
- **Original *Deliverables* + *Tests* sections retained in place** instead of deleted, even though the audit confirmed they are wrong. Justification: preserves audit trail for anyone reading the task file + this issue together; the prepended *Schema-check findings* section is explicit about which blocks are known-wrong.

## Gate summary

| Gate | Result |
| --- | --- |
| `uv run pytest` | ✅ 592 passed, 5 skipped |
| `uv run lint-imports` | ✅ 4 contracts kept |
| `uv run ruff check` | ✅ clean |
| `pyproject.toml` diff | ✅ empty |
| `ai_workflows/*` diff | ✅ empty |
| `.claude-plugin/` diff | ✅ empty (no manifest shipped) |

## Issue log

| ID | Severity | Status | Owner |
| --- | --- | --- | --- |
| *(none)* | — | — | — |

## Deferred to nice_to_have

*None.* The whole task is deferred under its own spec's trigger gate; no finding maps to a `nice_to_have.md` entry.

## Propagation status

*No forward deferrals to other tasks.* The T02 deferral is owned by T04 close-out — the M9 README *Outcome* section at T04 time records the disposition (T04 spec §*Deliverables* bullet on "T02 disposition" already anticipates this).

T04 spec already contains a bullet ("**Plugin manifest (task 02) —** one of: *shipped at …* / *deferred (no trigger fired)* / *deferred (schema unstable)*. Record the exact disposition.") so no carry-over edit needed on T04 at this audit; the disposition is *"deferred (no trigger fired)"* with schema-check facts pinned in the T02 task file for any future re-open.
