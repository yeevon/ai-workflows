"""Unit tests for the orchestrator-side agent-return parser.

Task: M20 Task 01 — Sub-agent return-value schema (3-line verdict / file / section).

Exercises all positive and negative paths in ``tests.agents._helpers.parse_agent_return``.
The parser is the Python equivalent of the prose parser convention described in each
slash command under ``## Agent-return parser convention``, which links to
``.claude/commands/_common/agent_return_schema.md``.

Per-AC coverage:
  AC-5 — All positive + negative parser cases pass.
"""

from __future__ import annotations

import pytest

from tests.agents._helpers import (
    AGENT_VERDICT_TOKENS,
    MalformedAgentReturn,
    parse_agent_return,
    token_count_proxy,
)

# ---------------------------------------------------------------------------
# Positive cases
# ---------------------------------------------------------------------------

def test_conformant_three_line_return_parsed_correctly() -> None:
    """Conformant 3-line return parses to (verdict, file, section) tuple."""
    text = (
        "verdict: BUILT\n"
        "file: design_docs/phases/milestone_20/issues/task_01_issue.md\n"
        "section: —"
    )
    verdict, file_val, section = parse_agent_return(text, agent_name="builder")
    assert verdict == "BUILT"
    assert file_val == "design_docs/phases/milestone_20/issues/task_01_issue.md"
    assert section == "—"


def test_dash_placeholder_in_file_field() -> None:
    """'—' is a valid value in the file: field."""
    text = "verdict: BLOCKED\nfile: —\nsection: —"
    verdict, file_val, section = parse_agent_return(text, agent_name="builder")
    assert verdict == "BLOCKED"
    assert file_val == "—"


def test_section_with_header_text() -> None:
    """Section field containing a ## header is parsed correctly."""
    text = (
        "verdict: SHIP\n"
        "file: design_docs/phases/milestone_20/issues/task_01_issue.md\n"
        "section: ## Security review (2026-04-28)"
    )
    verdict, file_val, section = parse_agent_return(text, agent_name="security-reviewer")
    assert verdict == "SHIP"
    assert section == "## Security review (2026-04-28)"


def test_trailing_newline_is_tolerated() -> None:
    """A single trailing blank line does not break parsing."""
    text = "verdict: PASS\nfile: some/path.md\nsection: —\n"
    verdict, file_val, section = parse_agent_return(text, agent_name="auditor")
    assert verdict == "PASS"


def test_optional_space_after_colon() -> None:
    """Both 'verdict: X' (space) and 'verdict:X' (no space) are accepted."""
    text_space = "verdict: CLEAN\nfile: analysis.md\nsection: —"
    text_nospace = "verdict:CLEAN\nfile:analysis.md\nsection:—"
    v1, _, _ = parse_agent_return(text_space, agent_name="task-analyzer")
    v2, _, _ = parse_agent_return(text_nospace, agent_name="task-analyzer")
    assert v1 == v2 == "CLEAN"


def test_no_agent_name_skips_verdict_validation() -> None:
    """When agent_name is None, any non-empty verdict value is accepted."""
    text = "verdict: TOTALLY-CUSTOM-VERDICT\nfile: —\nsection: —"
    verdict, _, _ = parse_agent_return(text, agent_name=None)
    assert verdict == "TOTALLY-CUSTOM-VERDICT"


@pytest.mark.parametrize("agent_name,tokens", AGENT_VERDICT_TOKENS.items())
def test_each_allowed_verdict_token_parses_correctly(
    agent_name: str, tokens: frozenset[str]
) -> None:
    """Every allowed verdict token for every agent round-trips through the parser."""
    for token in tokens:
        text = f"verdict: {token}\nfile: some/path.md\nsection: —"
        verdict, _, _ = parse_agent_return(text, agent_name=agent_name)
        assert verdict == token


def test_trailing_spaces_in_verdict_are_tolerated() -> None:
    """Trailing whitespace on any value line is stripped before validation."""
    text = "verdict: BUILT  \nfile: —  \nsection: —  "
    verdict, file_val, section = parse_agent_return(text, agent_name="builder")
    assert verdict == "BUILT"
    assert file_val == "—"
    assert section == "—"


# ---------------------------------------------------------------------------
# Negative cases — all must raise MalformedAgentReturn
# ---------------------------------------------------------------------------

def test_empty_return_raises() -> None:
    """Empty string raises MalformedAgentReturn."""
    with pytest.raises(MalformedAgentReturn, match="empty"):
        parse_agent_return("")


def test_whitespace_only_return_raises() -> None:
    """Whitespace-only string raises MalformedAgentReturn."""
    with pytest.raises(MalformedAgentReturn, match="empty"):
        parse_agent_return("   \n\n\t  ")


def test_four_lines_raises() -> None:
    """4 non-empty lines raises MalformedAgentReturn."""
    text = "verdict: BUILT\nfile: —\nsection: —\nextra: line"
    with pytest.raises(MalformedAgentReturn, match="3 non-empty lines"):
        parse_agent_return(text)


def test_two_lines_raises() -> None:
    """2 non-empty lines raises MalformedAgentReturn."""
    text = "verdict: BUILT\nfile: —"
    with pytest.raises(MalformedAgentReturn, match="3 non-empty lines"):
        parse_agent_return(text)


def test_bad_regex_on_first_line_raises() -> None:
    """Line that doesn't match the key: value regex raises MalformedAgentReturn."""
    text = "BUILT\nfile: —\nsection: —"
    with pytest.raises(MalformedAgentReturn, match="does not match"):
        parse_agent_return(text)


def test_bad_key_name_raises() -> None:
    """Wrong key name (e.g. 'result:' instead of 'verdict:') raises."""
    text = "result: BUILT\nfile: —\nsection: —"
    with pytest.raises(MalformedAgentReturn, match="does not match"):
        parse_agent_return(text)


def test_keys_out_of_order_raises() -> None:
    """Keys in wrong order (file before verdict) raises MalformedAgentReturn."""
    text = "file: —\nverdict: BUILT\nsection: —"
    with pytest.raises(MalformedAgentReturn):
        parse_agent_return(text)


def test_whitespace_only_value_raises() -> None:
    """A line with key but whitespace-only value raises MalformedAgentReturn."""
    # This won't match the regex if there's nothing after ': ' — test both cases:
    # (a) 'verdict: ' followed by spaces — the regex requires at least one non-space
    text = "verdict:   \nfile: —\nsection: —"
    with pytest.raises(MalformedAgentReturn):
        parse_agent_return(text)


def test_verdict_outside_allowed_set_raises() -> None:
    """Verdict not in the agent's allowed set raises MalformedAgentReturn."""
    text = "verdict: UNKNOWN_VERDICT\nfile: —\nsection: —"
    with pytest.raises(MalformedAgentReturn, match="not in the allowed set"):
        parse_agent_return(text, agent_name="builder")


def test_prose_body_before_schema_raises() -> None:
    """Prose before the 3-line schema results in >3 non-empty lines — raises."""
    text = (
        "Here is my summary of what I did.\n"
        "It was very complex.\n"
        "verdict: BUILT\n"
        "file: —\n"
        "section: —"
    )
    with pytest.raises(MalformedAgentReturn, match="3 non-empty lines"):
        parse_agent_return(text)


def test_prose_body_after_schema_raises() -> None:
    """Prose after the 3-line schema results in >3 non-empty lines — raises."""
    text = (
        "verdict: BUILT\n"
        "file: —\n"
        "section: —\n"
        "Also here is some extra information the orchestrator didn't ask for."
    )
    with pytest.raises(MalformedAgentReturn, match="3 non-empty lines"):
        parse_agent_return(text)


# ---------------------------------------------------------------------------
# Token-count proxy utility tests
# ---------------------------------------------------------------------------

def test_token_count_proxy_empty_string() -> None:
    """Empty string has zero token-proxy units."""
    assert token_count_proxy("") == 0.0


def test_token_count_proxy_single_word() -> None:
    """Single word has 1.3 token-proxy units."""
    assert token_count_proxy("hello") == pytest.approx(1.3)


def test_token_count_proxy_three_line_schema() -> None:
    """A typical 3-line schema return is well under 100 token-proxy units."""
    text = (
        "verdict: BUILT\n"
        "file: design_docs/phases/milestone_20/issues/task_01_issue.md\n"
        "section: —"
    )
    approx = token_count_proxy(text)
    assert approx < 100, f"Expected < 100 token-proxy units; got {approx:.1f}"
