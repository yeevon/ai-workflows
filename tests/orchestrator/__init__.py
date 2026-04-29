"""Test package for orchestrator-side autonomy infrastructure.

Task: M20 Task 02 — Sub-agent input prune (orchestrator-side scope discipline).
Relationship: Tests the spawn-prompt sizing discipline and KDR-section extraction
  logic described in `.claude/commands/_common/spawn_prompt_template.md`.

This package intentionally lives under `tests/` (not `ai_workflows/`) because
it tests the autonomy orchestration layer (`.claude/`), not the runtime Python
package. No runtime caller exists for this logic inside `ai_workflows/`, so
placing it there would create a dead-end subpackage.
"""
