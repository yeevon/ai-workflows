---
model: claude-opus-4-7
thinking: max
---

# /implement

Single Builder pass for: $ARGUMENTS

Spawn the `builder` subagent via `Task` with the resolved task identifier, spec path, issue file path, parent milestone README, and the project context brief. Wait for completion. Surface the Builder's terse report (files changed, gates run, ACs claimed satisfied).

**Do not audit. Do not commit.** This command runs Builder once and stops. Use `/audit <task>` to run the Auditor against the result, or `/clean-implement <task>` to run the full Builder → Auditor loop.

## Project context brief

Pass verbatim to the Builder spawn:

```text
Project: <PROJECT_NAME>
Layer rule: <LAYER_RULE>  (if applicable)
Gate commands: <GATE_COMMANDS>
Architecture: <ARCHITECTURE_DOC>
ADRs: <ADR_DIR>/*.md
Deferred-ideas file: <NICE_TO_HAVE>
Changelog convention: ## [Unreleased] → ### Added — M<N> Task <NN>: <Title> (YYYY-MM-DD)
Dep manifests: <MANIFEST_FILES>
Load-bearing KDRs: <KDR_LIST>
Issue file path: <ISSUE_FILE for the resolved task>
Status surfaces (must flip together at task close): per-task spec **Status:** line, milestone README task table row, plus any other tracked-status surface.
```

Resolve `$ARGUMENTS` to the task spec path (shorthand "m<N> t<NN>" → glob match). Halt and ask if multiple matches.
