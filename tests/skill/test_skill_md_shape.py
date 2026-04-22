"""Shape tests for the ai-workflows Claude Code skill (M9 T01).

Pure-filesystem tests: verify the packaged ``SKILL.md`` has the
frontmatter + body content the M9 spec requires. No imports from
``ai_workflows.primitives``, ``ai_workflows.graph``, or
``ai_workflows.workflows`` at the graph layer — we only touch the
top-level registry (``ai_workflows.workflows.list_workflows``) to
keep the test honest if a third workflow ever registers.

Relationship to other modules
-----------------------------
* ``.claude/skills/ai-workflows/SKILL.md`` — the artefact under test.
* :mod:`ai_workflows.workflows` — source of truth for registered
  workflow names; the shape test asserts the skill body names each
  currently-registered workflow.
"""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_PATH = REPO_ROOT / ".claude" / "skills" / "ai-workflows" / "SKILL.md"


def _read_skill_md() -> str:
    """Read the SKILL.md body as UTF-8."""
    return SKILL_PATH.read_text(encoding="utf-8")


def _parse_frontmatter(body: str) -> dict[str, str]:
    """Extract the YAML frontmatter block from ``body``.

    Raises ``AssertionError`` when the frontmatter opener / closer is
    missing or malformed. Returns an empty dict only if the
    frontmatter YAML parses to an empty document — the caller should
    assert on ``name`` / ``description`` explicitly.
    """
    assert body.startswith("---\n"), "skill must open with YAML frontmatter marker"
    _, _, rest = body.partition("---\n")
    fm_block, marker, _ = rest.partition("\n---\n")
    assert marker == "\n---\n", "skill frontmatter must close with a trailing ---"
    data = yaml.safe_load(fm_block) or {}
    assert isinstance(data, dict), "frontmatter must parse to a mapping"
    return data


def test_skill_md_exists() -> None:
    """``.claude/skills/ai-workflows/SKILL.md`` resolves to a readable file."""
    assert SKILL_PATH.is_file(), f"expected {SKILL_PATH} to exist"
    body = _read_skill_md()
    assert body.strip(), "SKILL.md must not be empty"


def test_skill_md_frontmatter() -> None:
    """Frontmatter has ``name`` == ``ai-workflows`` + non-empty ``description``."""
    body = _read_skill_md()
    fm = _parse_frontmatter(body)
    assert fm.get("name") == "ai-workflows", (
        f"skill name must be 'ai-workflows', got {fm.get('name')!r}"
    )
    description = fm.get("description")
    assert isinstance(description, str) and description.strip(), (
        "skill frontmatter must carry a non-empty description"
    )


def test_skill_md_names_all_four_mcp_tools() -> None:
    """Body names every MCP tool from architecture.md §4.4.

    Guards against silent drift if the MCP surface grows or shrinks —
    the skill must stay in lock-step with the four-tool contract
    M4 locked.
    """
    body = _read_skill_md()
    for tool in ("run_workflow", "resume_run", "list_runs", "cancel_run"):
        assert tool in body, f"SKILL.md must mention the {tool!r} MCP tool"


def test_skill_md_names_registered_workflows() -> None:
    """Body mentions every workflow registered at import time.

    Reads the live registry so a third workflow landing under
    ``ai_workflows.workflows.*`` surfaces here immediately.
    """
    import ai_workflows.workflows.planner  # noqa: F401 — import-for-side-effects
    import ai_workflows.workflows.slice_refactor  # noqa: F401 — import-for-side-effects
    from ai_workflows.workflows import list_workflows

    body = _read_skill_md()
    registered = list_workflows()
    assert registered, "expected at least one workflow registered"
    for name in registered:
        assert name in body, (
            f"SKILL.md must mention registered workflow {name!r}; "
            f"currently registered: {registered}"
        )


def test_skill_md_forbids_anthropic_api() -> None:
    """KDR-003 guardrail — skill must not mention the banned API surface."""
    body = _read_skill_md()
    assert "ANTHROPIC_API_KEY" not in body, (
        "SKILL.md must never instruct callers to set ANTHROPIC_API_KEY (KDR-003)"
    )
    assert "anthropic.com/api" not in body, (
        "SKILL.md must never reference the Anthropic public HTTP API (KDR-003)"
    )


def test_skill_names_plan_and_gate_prompt_in_pending_flow() -> None:
    """M11 T01 (Gap 2) — pending-flow section must name the reviewable fields.

    The M9 T04 live smoke surfaced that the skill told the operator
    *"nothing to check"* because the MCP response at gate pause had
    ``plan: null``. M11 T01 added ``plan`` + ``gate_context`` to the
    pause response and rewrote the skill's pending-flow section to
    surface both to the user. This test locks the contract: the
    rewrite cannot silently regress to the pre-M11 wording that
    ignored the new fields.

    Asserted on the whole body rather than a grepped sub-section so
    the test stays robust against cosmetic heading changes.
    """
    body = _read_skill_md()
    assert "gate_context" in body, (
        "SKILL.md must name the M11 gate_context field so the skill "
        "surfaces the gate prompt to the user at pause"
    )
    assert "gate_context.gate_prompt" in body or "gate_prompt" in body, (
        "SKILL.md must reference the gate_prompt subfield in the "
        "pending-flow instructions"
    )
    assert '"status": "pending"' in body or "'status': 'pending'" in body, (
        "SKILL.md must show an example of the status='pending' response"
    )
    pending_idx = body.find('"pending"')
    assert pending_idx >= 0, "SKILL.md should include a pending-status example"
    tail = body[pending_idx:]
    assert "plan" in tail and "gate_context" in tail, (
        "SKILL.md must show `plan` and `gate_context` as populated in "
        "the pending-status example, not null"
    )
