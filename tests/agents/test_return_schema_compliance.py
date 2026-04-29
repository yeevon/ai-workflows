"""Schema-compliance tests for all 9 sub-agents.

Task: M20 Task 01 — Sub-agent return-value schema (3-line verdict / file / section).

This module uses a stub-spawn model for the default test suite (no live agent
calls): canned fixture texts (one per verdict token per agent, stored under
``tests/agents/fixtures/<agent_name>/``) are parsed by the orchestrator-side
parser and checked for conformance.

Live Task spawns are gated behind ``AIW_AGENT_SCHEMA_E2E=1`` (L1 carry-over,
round 1, 2026-04-27) — they consume weekly Max quota and add nondeterminism.
The default suite uses pre-written fixtures; the E2E suite spawns real agents
via the Claude Code ``Task`` tool (not invoked here — that layer lives in the
slash-command orchestrator).

Per-AC coverage:
  AC-1 — Each of the 9 agent files has a ``## Return to invoker`` section
          with the 3-line schema.  Checked by ``test_agent_file_has_schema``.
  AC-4 — ``tests/agents/test_return_schema_compliance.py`` passes for all 9
          agents, at least 3 fixture cases per agent, one per verdict token.
  AC-6 — Token cap (≤ 100 tokens per agent return) passes for every fixture.
          Proxy: ``len(re.findall(r"\\S+", text)) * 1.3`` (L8 carry-over).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from tests.agents._helpers import (
    AGENT_VERDICT_TOKENS,
    parse_agent_return,
    token_count_proxy,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).parents[2]
AGENTS_DIR = REPO_ROOT / ".claude" / "agents"
FIXTURES_DIR = Path(__file__).parent / "fixtures"

TOKEN_CAP = 100  # AC-6 / spec §Tests token-cap assertion


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fixture_texts(agent_name: str) -> list[tuple[str, str]]:
    """Return [(verdict_token, text)] for all fixture files for ``agent_name``."""
    agent_fixture_dir = FIXTURES_DIR / agent_name
    if not agent_fixture_dir.is_dir():
        return []
    results = []
    for fixture_file in sorted(agent_fixture_dir.iterdir()):
        if fixture_file.suffix in {".txt", ".md"}:
            text = fixture_file.read_text()
            results.append((fixture_file.stem.upper().replace("-", "-"), text))
    return results


# ---------------------------------------------------------------------------
# AC-1: Every agent file has a "## Return to invoker" section with the schema
# ---------------------------------------------------------------------------

ALL_AGENT_NAMES = list(AGENT_VERDICT_TOKENS.keys())


@pytest.mark.parametrize("agent_name", ALL_AGENT_NAMES)
def test_agent_file_has_schema(agent_name: str) -> None:
    """AC-1: agent file must contain '## Return to invoker' and 'verdict:' line."""
    agent_file = AGENTS_DIR / f"{agent_name}.md"
    assert agent_file.exists(), f"Agent file missing: {agent_file}"
    content = agent_file.read_text()
    assert "## Return to invoker" in content, (
        f"{agent_name}.md is missing '## Return to invoker' section"
    )
    assert "verdict:" in content, (
        f"{agent_name}.md is missing a 'verdict:' line in the schema block"
    )


@pytest.mark.parametrize("agent_name", ALL_AGENT_NAMES)
def test_agent_file_schema_has_all_three_keys(agent_name: str) -> None:
    """AC-1: agent file schema block must reference all three keys."""
    agent_file = AGENTS_DIR / f"{agent_name}.md"
    content = agent_file.read_text()
    for key in ("verdict:", "file:", "section:"):
        assert key in content, (
            f"{agent_name}.md is missing '{key}' in the schema block"
        )


@pytest.mark.parametrize("agent_name", ALL_AGENT_NAMES)
def test_agent_file_verdict_tokens_match_spec(agent_name: str) -> None:
    """AC-1: every allowed verdict token for the agent must appear in its file."""
    agent_file = AGENTS_DIR / f"{agent_name}.md"
    content = agent_file.read_text()
    allowed = AGENT_VERDICT_TOKENS[agent_name]
    for token in allowed:
        assert token in content, (
            f"{agent_name}.md is missing verdict token '{token}' in the schema block"
        )


# ---------------------------------------------------------------------------
# Regression test: architect prompt body token set matches _helpers.py
# (cycle 2 carry-over — sr-dev FIX-1)
# ---------------------------------------------------------------------------

def test_architect_prompt_body_token_set_matches_helper() -> None:
    """Architect prompt body verdict-token line must match AGENT_VERDICT_TOKENS['architect'].

    Greps `.claude/agents/architect.md` for the Trigger A verdict line and asserts
    every token in AGENT_VERDICT_TOKENS['architect'] appears there.  Hermetic string
    grep — no live agent spawn.
    """
    architect_md = AGENTS_DIR / "architect.md"
    assert architect_md.exists(), "architect.md not found"
    content = architect_md.read_text()
    allowed = AGENT_VERDICT_TOKENS["architect"]
    for token in allowed:
        assert token in content, (
            f"Token {token!r} from AGENT_VERDICT_TOKENS['architect'] not found in "
            f"architect.md — prompt body and helper are out of sync."
        )


# ---------------------------------------------------------------------------
# AC-4 + AC-6: Fixture-based schema-compliance + token-cap tests
# ---------------------------------------------------------------------------

def _build_fixture_params() -> list[tuple[str, str, str]]:
    """Collect (agent_name, fixture_label, fixture_text) for all fixtures."""
    params: list[tuple[str, str, str]] = []
    for agent_name in ALL_AGENT_NAMES:
        for label_raw, text in _fixture_texts(agent_name):
            params.append((agent_name, label_raw, text))
    return params


_FIXTURE_PARAMS = _build_fixture_params()


@pytest.mark.parametrize("agent_name,label,text", _FIXTURE_PARAMS)
def test_fixture_parses_cleanly(agent_name: str, label: str, text: str) -> None:
    """AC-4: each fixture text parses to (verdict, file, section) without error."""
    verdict, file_val, section = parse_agent_return(text, agent_name=agent_name)
    assert verdict, "verdict is empty"
    assert file_val, "file value is empty"
    assert section, "section value is empty"


@pytest.mark.parametrize("agent_name,label,text", _FIXTURE_PARAMS)
def test_fixture_verdict_in_allowed_set(agent_name: str, label: str, text: str) -> None:
    """AC-4: verdict token from fixture must be in the agent's allowed set."""
    verdict, _, _ = parse_agent_return(text, agent_name=agent_name)
    allowed = AGENT_VERDICT_TOKENS[agent_name]
    assert verdict in allowed, (
        f"Verdict {verdict!r} not in allowed set {sorted(allowed)} for {agent_name}"
    )


@pytest.mark.parametrize("agent_name,label,text", _FIXTURE_PARAMS)
def test_fixture_token_cap(agent_name: str, label: str, text: str) -> None:
    """AC-6: fixture text must be ≤ 100 token-proxy units (L8 carry-over)."""
    approx_tokens = token_count_proxy(text)
    assert approx_tokens <= TOKEN_CAP, (
        f"{agent_name}/{label}: approx {approx_tokens:.1f} tokens > cap {TOKEN_CAP}"
    )


def test_all_agents_have_at_least_one_fixture() -> None:
    """AC-4: every agent must have at least one fixture file."""
    for agent_name in ALL_AGENT_NAMES:
        fixtures = _fixture_texts(agent_name)
        assert len(fixtures) >= 1, (
            f"No fixture files found for agent '{agent_name}' under {FIXTURES_DIR}"
        )


def test_all_agents_have_three_fixtures_per_spec() -> None:
    """AC-4: every agent must have at least 3 fixture files (one per verdict token)."""
    for agent_name in ALL_AGENT_NAMES:
        fixtures = _fixture_texts(agent_name)
        expected_count = len(AGENT_VERDICT_TOKENS[agent_name])
        assert len(fixtures) >= expected_count, (
            f"Agent '{agent_name}' has {len(fixtures)} fixtures; "
            f"expected at least {expected_count} (one per verdict token)."
        )


# ---------------------------------------------------------------------------
# E2E guard (opt-in via AIW_AGENT_SCHEMA_E2E=1)
# ---------------------------------------------------------------------------

_E2E_ENABLED = os.getenv("AIW_AGENT_SCHEMA_E2E") == "1"


@pytest.mark.skipif(not _E2E_ENABLED, reason="Set AIW_AGENT_SCHEMA_E2E=1 to run live spawns")
def test_e2e_placeholder() -> None:
    """Placeholder for live agent spawns (gated behind AIW_AGENT_SCHEMA_E2E=1).

    Real E2E tests would spawn each agent via the Claude Code Task tool with a
    minimal fixture task, capture the return text, and assert conformance + token cap.
    This lives in the slash-command orchestrator layer; this placeholder confirms the
    opt-in guard works.
    """
    assert _E2E_ENABLED, "E2E guard should prevent reaching this assertion"
