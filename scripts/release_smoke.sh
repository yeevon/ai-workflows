#!/usr/bin/env bash
# M13 Task 02 — release-gate smoke for ai-workflows.
#
# Builds the wheel, installs it into a fresh venv outside the repo,
# and exercises the two CLI entry points + the migrations-from-wheel
# path. Intended to be run manually before `uv publish` (T07 runbook);
# NOT wired into CI — the optional real-provider stage at the bottom
# would cost money per PR and the hermetic stages duplicate
# tests/test_wheel_contents.py.
#
# Usage:
#   bash scripts/release_smoke.sh
#
#   # With optional live planner stage (requires Claude CLI + Ollama too):
#   AIW_E2E=1 GEMINI_API_KEY=... bash scripts/release_smoke.sh
#
# Exit code: 0 on success, non-zero on any failure.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

if [[ ! -f "pyproject.toml" ]]; then
    echo "FAIL: pyproject.toml not found at $REPO_ROOT — script must run from the repo root." >&2
    exit 1
fi

TMP_DIR="$(mktemp -d -t aiw-release-smoke-XXXXXX)"
cleanup() {
    rm -rf "$TMP_DIR"
}
trap cleanup EXIT

echo "=== M13 release smoke ==="
echo "Repo:    $REPO_ROOT"
echo "TempDir: $TMP_DIR"
echo

# -----------------------------------------------------------------------------
# Stage 1: build wheel
# -----------------------------------------------------------------------------
echo "[1/7] uv build --wheel ..."
uv build --wheel --out-dir "$TMP_DIR/dist" > "$TMP_DIR/build.log" 2>&1 || {
    echo "FAIL: uv build failed. Log:" >&2
    cat "$TMP_DIR/build.log" >&2
    exit 1
}

shopt -s nullglob
WHEELS=("$TMP_DIR/dist"/*.whl)
shopt -u nullglob
if [[ ${#WHEELS[@]} -ne 1 ]]; then
    echo "FAIL: expected exactly 1 wheel in $TMP_DIR/dist, got ${#WHEELS[@]}." >&2
    ls -la "$TMP_DIR/dist" >&2
    exit 1
fi
WHEEL_PATH="${WHEELS[0]}"
echo "      built: $(basename "$WHEEL_PATH")"

# -----------------------------------------------------------------------------
# Stage 2: create clean venv outside the repo
# -----------------------------------------------------------------------------
echo "[2/7] uv venv (fresh, outside repo) ..."
uv venv "$TMP_DIR/venv" > "$TMP_DIR/venv.log" 2>&1 || {
    echo "FAIL: uv venv failed. Log:" >&2
    cat "$TMP_DIR/venv.log" >&2
    exit 1
}
VENV_PY="$TMP_DIR/venv/bin/python"
VENV_BIN="$TMP_DIR/venv/bin"

# -----------------------------------------------------------------------------
# Stage 3: install the built wheel
# -----------------------------------------------------------------------------
echo "[3/7] uv pip install <wheel> ..."
uv pip install --python "$VENV_PY" "$WHEEL_PATH" > "$TMP_DIR/install.log" 2>&1 || {
    echo "FAIL: wheel install failed. Log:" >&2
    cat "$TMP_DIR/install.log" >&2
    exit 1
}

# -----------------------------------------------------------------------------
# Stage 4: help-smoke both CLI entry points
# -----------------------------------------------------------------------------
echo "[4/7] aiw --help + aiw-mcp --help ..."
"$VENV_BIN/aiw" --help > "$TMP_DIR/aiw_help.log" 2>&1 || {
    echo "FAIL: aiw --help failed." >&2
    cat "$TMP_DIR/aiw_help.log" >&2
    exit 1
}
"$VENV_BIN/aiw-mcp" --help > "$TMP_DIR/aiw_mcp_help.log" 2>&1 || {
    echo "FAIL: aiw-mcp --help failed." >&2
    cat "$TMP_DIR/aiw_mcp_help.log" >&2
    exit 1
}

# -----------------------------------------------------------------------------
# Stage 5: migrations-from-wheel smoke (the headline gate)
# -----------------------------------------------------------------------------
# aiw list-runs opens SQLiteStorage.open(...), which applies all migrations
# from the wheel-bundled migrations/ directory via yoyo. If the T01
# force-include hook ever regresses, yoyo raises "no migration scripts
# found" and this stage fails loudly.
echo "[5/7] aiw list-runs against fresh AIW_STORAGE_DB (migrations apply) ..."
export AIW_STORAGE_DB="$TMP_DIR/storage.db"
export AIW_CHECKPOINT_DB="$TMP_DIR/checkpoints.db"
"$VENV_BIN/aiw" list-runs > "$TMP_DIR/list_runs.log" 2>&1 || {
    echo "FAIL: aiw list-runs failed — migrations-from-wheel path broken." >&2
    cat "$TMP_DIR/list_runs.log" >&2
    exit 1
}
if [[ ! -f "$AIW_STORAGE_DB" ]]; then
    echo "FAIL: expected $AIW_STORAGE_DB to exist after aiw list-runs." >&2
    exit 1
fi

# -----------------------------------------------------------------------------
# Stage 6: spec-API dispatch smoke (the 0.3.1 hotfix gate)
# -----------------------------------------------------------------------------
# 0.3.0 shipped a non-functional declarative-API path: register_workflow()
# compiled the spec but discarded it, leaving _build_initial_state with no
# way to construct typed input. Every existing "wire-level" test side-stepped
# this by re-registering the workflow imperatively. The fix is the
# _SPEC_REGISTRY plumbing in 0.3.1; this stage exercises it against the
# installed wheel + a synthetic no-LLM spec-API workflow registered through
# AIW_EXTRA_WORKFLOW_MODULES. Mirrors tests/release/test_install_smoke.py at
# the bash gate so the publish ceremony catches the same class of regression
# even when running the script standalone (without uv run pytest).
echo "[6/7] aiw run spec-api smoke against installed wheel (0.3.1 hotfix gate) ..."
WORKFLOW_DIR="$TMP_DIR/workflow_pkg"
mkdir -p "$WORKFLOW_DIR"
cat > "$WORKFLOW_DIR/release_smoke_workflow.py" <<'PYEOF'
"""No-LLM spec-API workflow used by scripts/release_smoke.sh Stage 6."""

from pydantic import BaseModel

from ai_workflows.workflows import (
    ValidateStep,
    WorkflowSpec,
    register_workflow,
)


class SmokeInput(BaseModel):
    message: str


class SmokeOutput(BaseModel):
    message: str


register_workflow(
    WorkflowSpec(
        name="release_smoke_workflow",
        input_schema=SmokeInput,
        output_schema=SmokeOutput,
        tiers={},
        steps=[
            ValidateStep(target_field="message", schema=SmokeOutput),
        ],
    )
)
PYEOF

PYTHONPATH="$WORKFLOW_DIR" \
AIW_EXTRA_WORKFLOW_MODULES="release_smoke_workflow" \
"$VENV_BIN/aiw" run release_smoke_workflow \
    --input message=release-smoke-stage-6 \
    > "$TMP_DIR/spec_api_run.log" 2>&1 || {
    echo "FAIL: aiw run on spec-API workflow exited non-zero." >&2
    echo "      The 0.3.0 dispatch regression may have resurfaced." >&2
    cat "$TMP_DIR/spec_api_run.log" >&2
    exit 1
}
if grep -q "exposes no Input schema" "$TMP_DIR/spec_api_run.log"; then
    echo "FAIL: 0.3.0 dispatch regression detected — _build_initial_state could not resolve spec." >&2
    cat "$TMP_DIR/spec_api_run.log" >&2
    exit 1
fi
if ! grep -q "release-smoke-stage-6" "$TMP_DIR/spec_api_run.log"; then
    echo "FAIL: spec-API workflow did not surface the input message in stdout." >&2
    cat "$TMP_DIR/spec_api_run.log" >&2
    exit 1
fi

# -----------------------------------------------------------------------------
# Stage 7 (optional): real-provider planner run
# -----------------------------------------------------------------------------
# Gated by BOTH env vars. When either is missing, print a skip line and
# continue with exit 0. Not run in the default release gate — matches
# the tests/e2e/ double-gate pattern.
echo "[7/7] real-provider planner run (optional) ..."
if [[ "${AIW_E2E:-0}" == "1" && -n "${GEMINI_API_KEY:-}" ]]; then
    echo "      AIW_E2E=1 + GEMINI_API_KEY set — driving aiw run planner"
    timeout 60 "$VENV_BIN/aiw" run planner \
        --goal "wheel-smoke" \
        --run-id "wheel-smoke-$(date +%s)" \
        > "$TMP_DIR/planner_run.log" 2>&1 && RC=0 || RC=$?
    # Accept: 0 (completed), or non-zero with "paused" / "gate" in the log.
    if [[ $RC -eq 0 ]] || grep -qiE "(paus|gate|interrupt)" "$TMP_DIR/planner_run.log"; then
        echo "      planner run: ok (exit $RC; gate/pause acceptable)"
    else
        echo "FAIL: planner run exited $RC with no gate/pause signal. Log:" >&2
        cat "$TMP_DIR/planner_run.log" >&2
        exit 1
    fi
else
    echo "      skip — set AIW_E2E=1 and GEMINI_API_KEY to exercise this stage"
fi

echo
echo "=== OK — release smoke passed ==="
