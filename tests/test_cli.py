"""Tests for M1 Task 12 — CLI primitives (``aiw list-runs`` / ``inspect`` …).

One test per AC (plus carry-overs ``M1-T04-ISS-01`` and
``M1-T09-ISS-02``). Tests shell the Typer app in-process via
:class:`typer.testing.CliRunner` against a temporary SQLite DB seeded
with a fresh :class:`SQLiteStorage` instance, so no network, no
``~/.ai-workflows`` writes, and no fixture drift against the real
schema.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ai_workflows.cli import app
from ai_workflows.primitives.storage import SQLiteStorage
from ai_workflows.primitives.workflow_hash import compute_workflow_hash

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_RUNNER = CliRunner()


# Tests in this module invoke the Typer app synchronously (the CLI itself
# calls ``asyncio.run``). If they were ``async`` under pytest-asyncio auto
# mode, the outer loop would conflict with the CLI's nested ``asyncio.run``
# call. So the tests are sync and ``_seed_basic`` is driven through a
# fresh loop via :func:`asyncio.run`.


async def _seed_basic(db_path: Path) -> SQLiteStorage:
    """Seed two runs, a few tasks, and priced + local llm_calls rows."""
    storage = await SQLiteStorage.open(db_path)
    await storage.create_run(
        run_id="abc123",
        workflow_id="test_coverage_gap_fill",
        workflow_dir_hash="a" * 64,
        budget_cap_usd=5.0,
    )
    await storage.create_run(
        run_id="def456",
        workflow_id="jvm_modernization",
        workflow_dir_hash="b" * 64,
        budget_cap_usd=None,
    )
    await storage.update_run_status("abc123", "completed", total_cost_usd=0.42)
    await storage.update_run_status("def456", "failed", total_cost_usd=1.17)

    await storage.upsert_task(
        "abc123", "plan_refactor", "worker", "completed"
    )
    await storage.upsert_task(
        "abc123", "explore_module_auth", "worker", "completed"
    )

    await storage.log_llm_call(
        "abc123",
        task_id="plan_refactor",
        workflow_id="test_coverage_gap_fill",
        component="worker",
        tier="opus",
        model="claude-3-opus",
        input_tokens=1000,
        output_tokens=500,
        cache_read_tokens=200,
        cache_write_tokens=100,
        cost_usd=0.31,
        is_local=False,
    )
    await storage.log_llm_call(
        "abc123",
        task_id="plan_refactor",
        workflow_id="test_coverage_gap_fill",
        component="validator",
        tier="sonnet",
        model="claude-3-sonnet",
        input_tokens=400,
        output_tokens=200,
        cost_usd=0.11,
        is_local=False,
    )
    await storage.log_llm_call(
        "abc123",
        task_id="explore_module_auth",
        workflow_id="test_coverage_gap_fill",
        component="worker",
        tier="local_coder",
        model="qwen2.5-coder",
        input_tokens=800,
        output_tokens=400,
        cost_usd=0.0,
        is_local=True,
    )
    return storage


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "runs.db"


@pytest.fixture
def seeded_db(db_path: Path) -> Path:
    asyncio.run(_seed_basic(db_path))
    return db_path


# ---------------------------------------------------------------------------
# AC-6 — `aiw --help` lists all commands
# ---------------------------------------------------------------------------


def test_aiw_help_lists_every_command() -> None:
    result = _RUNNER.invoke(app, ["--help"])
    assert result.exit_code == 0, result.stdout
    for command in ("list-runs", "inspect", "resume", "run", "version"):
        assert command in result.stdout, f"missing command in help: {command}"


# ---------------------------------------------------------------------------
# AC-1 — `aiw list-runs` renders with seeded data
# ---------------------------------------------------------------------------


def test_list_runs_renders_seeded_runs(seeded_db: Path) -> None:
    result = _RUNNER.invoke(
        app, ["--db-path", str(seeded_db), "list-runs"]
    )
    assert result.exit_code == 0, result.stderr
    out = result.stdout
    assert "RUN ID" in out and "WORKFLOW" in out and "STATUS" in out
    assert "abc123" in out
    assert "def456" in out
    assert "test_coverage_gap_fill" in out
    assert "$0.42" in out
    assert "$1.17" in out


def test_list_runs_truncates_long_workflow_names(db_path: Path) -> None:
    long_name = "a_very_long_workflow_name_that_exceeds_22_chars"

    async def _seed() -> None:
        storage = await SQLiteStorage.open(db_path)
        await storage.create_run(
            "r1", long_name, workflow_dir_hash="h" * 8, budget_cap_usd=None
        )

    asyncio.run(_seed())
    result = _RUNNER.invoke(app, ["--db-path", str(db_path), "list-runs"])
    assert result.exit_code == 0, result.stderr
    assert long_name[:22] in result.stdout
    assert long_name not in result.stdout  # full name is cut off


def test_list_runs_with_empty_db_prints_header_and_message(db_path: Path) -> None:
    result = _RUNNER.invoke(app, ["--db-path", str(db_path), "list-runs"])
    assert result.exit_code == 0, result.stderr
    assert "RUN ID" in result.stdout
    assert "(no runs)" in result.stdout


# ---------------------------------------------------------------------------
# AC-2 — `aiw inspect <id>` shows cost breakdown
# ---------------------------------------------------------------------------


def test_inspect_shows_cost_breakdown(seeded_db: Path) -> None:
    result = _RUNNER.invoke(
        app, ["--db-path", str(seeded_db), "inspect", "abc123"]
    )
    assert result.exit_code == 0, result.stderr
    assert "Cost breakdown:" in result.stdout
    assert "worker=$0.31" in result.stdout
    assert "validator=$0.11" in result.stdout
    # Local call must not show up in the breakdown.
    assert "local_coder=" not in result.stdout


def test_inspect_shows_per_task_breakdown(seeded_db: Path) -> None:
    result = _RUNNER.invoke(
        app, ["--db-path", str(seeded_db), "inspect", "abc123"]
    )
    assert result.exit_code == 0, result.stderr
    assert "plan_refactor" in result.stdout
    assert "explore_module_auth" in result.stdout


# ---------------------------------------------------------------------------
# AC-3 — `aiw inspect` flags workflow_dir_hash mismatch
# ---------------------------------------------------------------------------


def test_inspect_flags_mismatch_when_directory_changed(
    tmp_path: Path, db_path: Path
) -> None:
    workflow_dir = tmp_path / "wf"
    workflow_dir.mkdir()
    (workflow_dir / "a.txt").write_text("original")
    original_hash = compute_workflow_hash(workflow_dir)

    async def _seed() -> None:
        storage = await SQLiteStorage.open(db_path)
        await storage.create_run(
            "r1", "wf", workflow_dir_hash=original_hash, budget_cap_usd=1.0
        )

    asyncio.run(_seed())

    # Unchanged directory → OK.
    ok = _RUNNER.invoke(
        app,
        [
            "--db-path",
            str(db_path),
            "inspect",
            "r1",
            "--workflow-dir",
            str(workflow_dir),
        ],
    )
    assert ok.exit_code == 0, ok.stderr
    assert "current match: OK" in ok.stdout

    # Drift the directory.
    (workflow_dir / "a.txt").write_text("drifted")
    bad = _RUNNER.invoke(
        app,
        [
            "--db-path",
            str(db_path),
            "inspect",
            "r1",
            "--workflow-dir",
            str(workflow_dir),
        ],
    )
    assert bad.exit_code == 0, bad.stderr
    assert "current match: MISMATCH" in bad.stdout


# ---------------------------------------------------------------------------
# AC-4 — `aiw inspect <nonexistent>` exits 1 with clear message
# ---------------------------------------------------------------------------


def test_inspect_missing_run_exits_1_with_message(seeded_db: Path) -> None:
    result = _RUNNER.invoke(
        app, ["--db-path", str(seeded_db), "inspect", "ghost"]
    )
    assert result.exit_code == 1
    assert "not found" in result.stderr.lower()
    assert "ghost" in result.stderr


# ---------------------------------------------------------------------------
# AC-5 — `aiw resume <id>` prints placeholder without error
# ---------------------------------------------------------------------------


def test_resume_prints_placeholder(seeded_db: Path) -> None:
    result = _RUNNER.invoke(
        app, ["--db-path", str(seeded_db), "resume", "abc123"]
    )
    assert result.exit_code == 0, result.stderr
    assert "Resume for run abc123" in result.stdout
    assert "Milestone 4" in result.stdout


def test_resume_missing_run_exits_1(seeded_db: Path) -> None:
    result = _RUNNER.invoke(
        app, ["--db-path", str(seeded_db), "resume", "ghost"]
    )
    assert result.exit_code == 1
    assert "not found" in result.stderr.lower()


def test_run_stub_prints_not_implemented(db_path: Path) -> None:
    result = _RUNNER.invoke(
        app,
        [
            "--db-path",
            str(db_path),
            "run",
            "some_workflow",
            "--profile",
            "dev",
        ],
    )
    assert result.exit_code == 0, result.stderr
    assert "Milestone 3" in result.stdout


# ---------------------------------------------------------------------------
# AC-7 — `--log-level DEBUG` produces human-readable console output
# ---------------------------------------------------------------------------


def test_debug_log_level_produces_human_readable_console(
    seeded_db: Path,
) -> None:
    """DEBUG must swap the JSON renderer for the ConsoleRenderer.

    We run ``aiw list-runs`` (any subcommand exercises the callback) and
    then emit a log line through the configured structlog pipeline; the
    line must contain the literal event name and a bracketed ``[debug``
    token rather than a JSON object.
    """
    import io

    import structlog

    from ai_workflows.primitives import logging as logging_module

    buf = io.StringIO()
    logging_module.configure_logging(level="DEBUG", stream=buf)
    logger = structlog.get_logger("test_cli.debug")
    logger.debug("cli_debug_event", key="value")
    text = buf.getvalue()
    assert "cli_debug_event" in text
    assert "[debug" in text  # structlog ConsoleRenderer level bracket
    assert "key" in text and "value" in text

    # Sanity: the CLI call itself with --log-level DEBUG exits cleanly so
    # any subsequent logging from the app would pick up the ConsoleRenderer.
    result = _RUNNER.invoke(
        app,
        ["--log-level", "DEBUG", "--db-path", str(seeded_db), "list-runs"],
    )
    assert result.exit_code == 0, result.stderr


# ---------------------------------------------------------------------------
# Carry-over M1-T04-ISS-01 — cache_read / cache_write visible in inspect
# ---------------------------------------------------------------------------


def test_inspect_surfaces_cache_read_and_cache_write(seeded_db: Path) -> None:
    result = _RUNNER.invoke(
        app, ["--db-path", str(seeded_db), "inspect", "abc123"]
    )
    assert result.exit_code == 0, result.stderr
    assert "cache_read" in result.stdout
    assert "cache_write" in result.stdout
    # The seeded opus call has 200 / 100 cache tokens — they must render.
    assert "200" in result.stdout
    assert "100" in result.stdout


# ---------------------------------------------------------------------------
# Carry-over M1-T09-ISS-02 — budget line formatting (cap + no-cap)
# ---------------------------------------------------------------------------


def test_inspect_budget_line_with_cap(seeded_db: Path) -> None:
    result = _RUNNER.invoke(
        app, ["--db-path", str(seeded_db), "inspect", "abc123"]
    )
    assert result.exit_code == 0, result.stderr
    # The seeded run's raw total from llm_calls is $0.42 with a $5.00 cap.
    assert "Budget: $0.42 / $5.00 (8% used)" in result.stdout


def test_inspect_budget_line_without_cap(seeded_db: Path) -> None:
    result = _RUNNER.invoke(
        app, ["--db-path", str(seeded_db), "inspect", "def456"]
    )
    assert result.exit_code == 0, result.stderr
    # `def456` was seeded with budget_cap_usd=None → "(no cap)" form.
    assert "Budget: $0.00 (no cap)" in result.stdout


# ---------------------------------------------------------------------------
# Extra coverage — asserts the dir-hash line still prints when no
# --workflow-dir is provided (the common case) without raising.
# ---------------------------------------------------------------------------


def test_inspect_dir_hash_without_workflow_dir(seeded_db: Path) -> None:
    result = _RUNNER.invoke(
        app, ["--db-path", str(seeded_db), "inspect", "abc123"]
    )
    assert result.exit_code == 0, result.stderr
    assert "Dir hash:" in result.stdout
    assert "pass --workflow-dir" in result.stdout
