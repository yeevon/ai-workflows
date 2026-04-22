# Task 02 — Optional Plugin Manifest

**Status:** 📝 Deferred — no trigger fired (2026-04-21). See *Schema-check findings (2026-04-21)* below for what a future Builder should know when this task is re-opened.
**Grounding:** [milestone README §Task order](README.md) · [architecture.md §4.4](../../architecture.md) · [KDR-002](../../architecture.md).

## Schema-check findings (2026-04-21)

The M9 T02 *Schema check* step was executed during the M9 clean-implement loop on 2026-04-21 even though no trigger fired, so a future Builder starts with accurate facts instead of the original guessed shape.

**Real schema.** Claude Code plugins at the current CLI version (present on the dev machine at audit time) use `.claude-plugin/plugin.json` as the manifest location (not `.claude/plugins/<name>/plugin.json` as the original deliverable section of this task guessed). Inspected three first-party plugins under `~/.claude/plugins/marketplaces/claude-plugins-official/plugins/*` (`hookify`, `mcp-server-dev`, `pr-review-toolkit`); all three carried only three keys:

```json
{
  "name": "<plugin-name>",
  "description": "<one-sentence purpose>",
  "author": {"name": "...", "email": "..."}
}
```

No `version`, no `skills` array, no `mcp_servers` block. Skills live in a sibling `skills/` directory at the plugin root (auto-discovered); MCP servers are registered through the same marketplace flow (see `claude plugin install` / `claude plugin marketplace` in `claude plugin --help`).

**Implication for the deliverable section below.** If a trigger fires later and this task is re-opened, rewrite the *Deliverables* block to:

- Target `.claude-plugin/plugin.json` (not `.claude/plugins/ai-workflows/plugin.json`).
- Drop the invented `version`, `skills`, and `mcp_servers` fields from the required-fields list — only `name`, `description`, `author` are in the observed shape today.
- Drop `test_plugin_manifest_version_matches_pyproject` and `test_plugin_manifest_references_mcp_server` — neither field is part of the real schema. Keep `test_plugin_manifest_exists` and `test_plugin_manifest_references_skill` only if the skills-directory convention turns out to be manifest-declared at re-open time.
- Pick up the `claude plugin validate <path>` CLI (exposed by the current `claude` binary) as the authoritative shape check — a green `validate` run is a stronger AC than any hand-rolled JSON schema assertion.

The original (pre-check) *Deliverables* and *Tests* sections below are **retained verbatim for history** but are known-wrong as of 2026-04-21. Re-opening this task means replacing them with a spec written against the real schema.

## Trigger

This task only runs if **at least one** of the following is true at
M9 kickoff:

1. The user intends to distribute `ai-workflows` through the Claude
   Code plugin marketplace.
2. A second host (Cursor, Zed, VSCode extension) asks for a
   manifest-based install surface on top of the M4 MCP registration.
3. Internal sharing needs a one-command install surface across
   multiple machines without cloning the repo.

If none fire at kickoff, **skip this task** and proceed to T03. Record
the skip in the M9 README's Outcome section at T04 time and leave the
task file in place as `📝 Deferred (no trigger)`.

The milestone's Exit criterion #3 ("Short distribution doc explains
how to install the skill and register the MCP server") is satisfied
by T03 alone — the plugin manifest is *optional distribution polish*,
not a required exit.

## What to Build

A Claude Code plugin manifest that packages the `SKILL.md` from T01
plus the MCP server registration into a single installable unit.
**Packaging only** — no logic, no new Python modules, no new runtime
dependencies.

A plugin manifest is typically a single JSON file declaring the
plugin's name, version, commands, skills, and MCP servers. The exact
filename and schema follow Claude Code's plugin spec at
implementation time — the schema has not been frozen at the time
this task is drafted, so T02 begins with a **schema-check step** that
may itself be the whole task if the spec still requires authoring.

## Deliverables

### Schema check (first step, gating)

Before writing any manifest, verify Claude Code's current plugin
manifest schema:

- Read `claude plugin --help` output (if the command exists).
- Grep the local Claude Code installation for a published schema
  file (e.g. `~/.claude/plugins/schema.json`, `plugin.schema.json`).
- If the schema is not published or is in flux, **stop and ask** —
  do not invent a shape. Downgrade T02 to "Deferred — schema
  unstable" and record the blocker in the M9 issue log.

### [.claude/plugins/ai-workflows/plugin.json](../../../.claude/plugins/ai-workflows/plugin.json)

Minimum fields (subject to the schema check):

```json
{
  "name": "ai-workflows",
  "version": "<pyproject.toml [project].version>",
  "description": "LangGraph-backed planner + slice_refactor workflows, MCP-native.",
  "skills": [".claude/skills/ai-workflows/SKILL.md"],
  "mcp_servers": {
    "ai-workflows": {
      "command": "uv",
      "args": ["run", "aiw-mcp"]
    }
  }
}
```

The `version` field mirrors `pyproject.toml` `[project].version` so
a release bump in one place fans out to both surfaces. A CHANGELOG
entry at T04 close-out records the binding.

### Tests

[tests/skill/test_plugin_manifest.py](../../../tests/skill/test_plugin_manifest.py)
— only if T02 proceeds past the schema check:

- `test_plugin_manifest_exists` — `.claude/plugins/ai-workflows/plugin.json`
  resolves to a readable JSON file.
- `test_plugin_manifest_version_matches_pyproject` — parses
  `pyproject.toml` `[project].version` and asserts
  `plugin["version"] == pyproject_version`.
- `test_plugin_manifest_references_skill` — `plugin["skills"]` lists
  the T01 SKILL.md path.
- `test_plugin_manifest_references_mcp_server` — `plugin["mcp_servers"]`
  includes `ai-workflows` with `command == "uv"` and
  `args == ["run", "aiw-mcp"]`.

No live install test. The plugin marketplace round-trip is a manual
verification recorded in T04's CHANGELOG entry (same pattern as M4
T06's `claude mcp add` round-trip).

## Acceptance Criteria

- [ ] Schema check documented in the issue log — either the schema
      was found and the manifest validates, or the task was
      downgraded to Deferred with a named blocker.
- [ ] If manifest shipped: `.claude/plugins/ai-workflows/plugin.json`
      parses as JSON and declares `name`, `version`, `description`,
      `skills`, `mcp_servers` per the schema check.
- [ ] If manifest shipped: `version` matches
      `pyproject.toml` `[project].version` (test-enforced).
- [ ] No new runtime or dev dependency. `pyproject.toml` diff empty.
- [ ] No new import-linter contract. Four-contract count preserved.
- [ ] `uv run pytest` + `uv run lint-imports` + `uv run ruff check`
      all clean.

## Dependencies

- T01 complete (the manifest references the SKILL.md path).
- M4 close-out (the manifest references `aiw-mcp` — the console
  script landed at M4 T06).

## Out of scope (explicit)

- Publishing to the Claude Code plugin marketplace. (That's a
  distribution event, not a code change. If the user pursues
  marketplace publishing, it lands as a separate release-time
  checklist, not an M9 task.)
- Versioned skill bundling (e.g. `@0.1` / `@latest` resolution
  semantics). Deferred until the marketplace exposes the contract.
- Host-agnostic manifests (Cursor, Zed). Each host has its own
  surface; this task targets Claude Code only. A second host's
  manifest earns its own task under a future milestone if demand
  surfaces.
