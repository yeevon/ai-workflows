"""Milestone 1 exit-criteria smoke test.

Exercises every runtime primitive end-to-end, against both runtime tiers:

* ``gemini_flash`` — paid Gemini API via openai_compat. Non-zero cost.
  Validates the budget-cap path (we intentionally set a very low cap and
  expect the cap to either hold or surface ``BudgetExceeded``).
* ``local_coder`` — local Qwen via Ollama. ``is_local=True`` → cost
  stamped as ``$0.00`` and excluded from aggregates.

After both runs complete, the script dumps the path to the SQLite DB so
you can validate with:

    uv run aiw --db-path /tmp/aiw_m1_smoke.db list-runs
    uv run aiw --db-path /tmp/aiw_m1_smoke.db inspect <run_id>

Not wired into pytest — this is a manual validation step.
"""

from __future__ import annotations

import asyncio
import sys
import uuid
from pathlib import Path

from dotenv import load_dotenv
from pydantic_ai import Agent

# Load .env from the repo root so GEMINI_API_KEY / OLLAMA_BASE_URL are
# available. Mirrors the behaviour of tests/conftest.py.
load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=False)

from ai_workflows.primitives.cost import BudgetExceeded, CostTracker
from ai_workflows.primitives.llm.model_factory import build_model, run_with_cost
from ai_workflows.primitives.llm.types import WorkflowDeps
from ai_workflows.primitives.logging import configure_logging
from ai_workflows.primitives.storage import SQLiteStorage
from ai_workflows.primitives.tiers import load_pricing, load_tiers
from ai_workflows.primitives.workflow_hash import compute_workflow_hash

DB_PATH = Path("/tmp/aiw_m1_smoke.db")
SMOKE_PROMPT = "Reply in one short sentence: what is 2 + 2?"


async def _run_tier(
    *,
    tier_name: str,
    storage: SQLiteStorage,
    tiers: dict,
    pricing: dict,
    budget_cap_usd: float | None,
) -> str:
    """Drive one end-to-end call through a tier; return the run_id."""
    run_id = f"smoke-{tier_name}-{uuid.uuid4().hex[:6]}"
    workflow_id = f"m1_smoke_{tier_name}"
    # Hash the repo root as a stand-in — we just need a non-empty hash.
    workflow_dir_hash = compute_workflow_hash(Path.cwd())

    await storage.create_run(
        run_id=run_id,
        workflow_id=workflow_id,
        workflow_dir_hash=workflow_dir_hash,
        budget_cap_usd=budget_cap_usd,
    )

    tracker = CostTracker(storage, pricing, budget_cap_usd=budget_cap_usd)
    model, caps = build_model(tier_name, tiers, tracker)
    print(
        f"[{tier_name}] provider={caps.provider} model={caps.model} "
        f"max_context={caps.max_context}"
    )

    agent = Agent(model)
    deps = WorkflowDeps(
        run_id=run_id,
        workflow_id=workflow_id,
        component="smoke_worker",
        tier=tier_name,
        project_root=str(Path.cwd()),
    )

    try:
        result = await run_with_cost(agent, SMOKE_PROMPT, deps, tracker)
        output = str(result.output).strip()
        total = await tracker.run_total(run_id)
        await storage.update_run_status(run_id, "completed", total_cost_usd=total)
        print(f"[{tier_name}] OK  run_id={run_id}  cost=${total:.6f}")
        print(f"[{tier_name}] model said: {output[:120]}")
    except BudgetExceeded as exc:
        total = await tracker.run_total(run_id)
        await storage.update_run_status(run_id, "failed", total_cost_usd=total)
        print(
            f"[{tier_name}] BUDGET CAP FIRED (expected path) "
            f"run_id={run_id} cost=${exc.current_cost:.6f} cap=${exc.cap:.6f}"
        )
    except Exception as exc:
        await storage.update_run_status(run_id, "failed")
        print(f"[{tier_name}] FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise

    return run_id


async def main() -> None:
    configure_logging(level="INFO")
    if DB_PATH.exists():
        DB_PATH.unlink()
    storage = await SQLiteStorage.open(DB_PATH)
    tiers = load_tiers()
    pricing = load_pricing()

    # Run A — gemini_flash: paid API, non-zero cost. Generous cap so the
    # one call completes; the budget path is still exercised on record().
    await _run_tier(
        tier_name="gemini_flash",
        storage=storage,
        tiers=tiers,
        pricing=pricing,
        budget_cap_usd=0.10,
    )

    # Run B — local_coder: Ollama, zero cost, is_local=True.
    await _run_tier(
        tier_name="local_coder",
        storage=storage,
        tiers=tiers,
        pricing=pricing,
        budget_cap_usd=None,  # no cap needed — cost is always 0
    )

    print()
    print(f"DB: {DB_PATH}")
    print(f"Verify:  uv run aiw --db-path {DB_PATH} list-runs")


if __name__ == "__main__":
    asyncio.run(main())
