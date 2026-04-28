"""FastMCP server factory for the ai-workflows MCP surface.

M4 Task 01 shipped the scaffold; M4 Task 02 wires the first real tool.
M6 Task 02 lands in-flight ``cancel_run`` wiring (carry-over from M4
T05): ``run_workflow`` registers its dispatch task under the run id in
a process-local registry so ``cancel_run`` can call
:meth:`asyncio.Task.cancel` before performing the existing storage-level
status flip (``architecture.md §8.7``).

M12 Task 05 adds the standalone ``run_audit_cascade`` tool (the fifth
``@mcp.tool()``). Per Option A locked 2026-04-27: the tool bypasses the
``AuditCascadeNode`` primitive entirely and instantiates a single-pass
auditor ``tiered_node`` directly (the cascade primitive requires a primary
LLM call that the standalone artefact-audit does not have).  Four private
helpers live in this module (not in ``workflows/_dispatch.py`` — that would
violate the layer rule by coupling workflows to surfaces):

* ``_resolve_audit_artefact`` — resolves ``run_id_ref + artefact_kind``
  via ``storage.read_artifact`` + ``json.loads(row["payload_json"])``, or
  returns the caller-supplied ``inline_artefact_ref`` dict unchanged.
* ``_build_standalone_audit_config`` — per-call
  :class:`~ai_workflows.primitives.cost.CostTracker` +
  :class:`~ai_workflows.graph.cost_callback.CostTrackingCallback` +
  :class:`~ai_workflows.primitives.retry.RetryPolicy` + auditor tier
  registry.  NOT shared with the dispatch's tracker/callback.
* ``_build_audit_configurable`` — constructs the ``config["configurable"]``
  dict that :func:`~ai_workflows.graph.tiered_node.tiered_node` reads.
* ``_make_standalone_auditor_prompt_fn`` — returns the ``(system, messages)``
  prompt builder that embeds the artefact JSON inside an
  ``<artefact>…</artefact>`` block.

Tool list:

* ``run_workflow``  — wired in M4 T02 against
  :func:`ai_workflows.workflows._dispatch.run_workflow`, the shared
  dispatch helper that the ``aiw run`` CLI command also routes through.
  M6 T02 wraps the dispatch call in :func:`asyncio.create_task` and
  registers the task so the in-flight cancel path can abort it.
* ``resume_run``    — M4 T03.
* ``list_runs``     — M4 T04.
* ``cancel_run``    — M4 T05 (storage-flip only) + M6 T02 (in-flight
  :meth:`asyncio.Task.cancel` before the storage flip; unknown-run-id
  falls back to the M4 behaviour cleanly).
* ``run_audit_cascade`` — M12 T05.

Relationship to other modules
-----------------------------
* :mod:`ai_workflows.mcp.schemas` — the pydantic I/O models each tool
  binds to its signature. FastMCP auto-derives the JSON-RPC schema from
  those annotations (KDR-008), so this module is only responsible for
  registering the five callables and returning the server instance.
* [architecture.md §4.4](../../design_docs/architecture.md) — lists the
  four tools; the fifth (``get_cost_report``) was dropped at M4 kickoff
  in favour of ``list_runs`` surfacing ``total_cost_usd``.
* :mod:`ai_workflows.workflows._dispatch` — the shared dispatch helper.
  Both this module and :mod:`ai_workflows.cli` call into it so the CLI
  and MCP surfaces stay in lockstep. ``_dispatch`` invokes LangGraph
  with ``durability="sync"`` so the last-completed-step checkpoint is
  guaranteed to hit SQLite before :class:`asyncio.CancelledError`
  unwinds the task — load-bearing for the cancel-and-immediately-resume
  path that M6 T02 tests.
* :mod:`ai_workflows.cli` — the sibling CLI surface that routes through
  the same dispatch helper. The CLI does not participate in in-flight
  cancellation (no long-running MCP session to hold the task handle).
* :mod:`ai_workflows.graph.tiered_node` — ``run_audit_cascade`` invokes
  :func:`~ai_workflows.graph.tiered_node.tiered_node` directly with
  ``role="auditor"`` (M12 T04 factory-time role binding; KDR-011).
* :mod:`ai_workflows.graph.audit_cascade` — provides the
  :class:`~ai_workflows.graph.audit_cascade.AuditVerdict` model that the
  auditor parses its raw output into.
* :mod:`ai_workflows.workflows` — ``run_audit_cascade`` uses
  :func:`~ai_workflows.workflows.auditor_tier_registry` (M12 T05) to
  obtain the auditor-only tier registry without importing
  workflow-specific planner/slice-refactor tiers.

Per the import-linter four-layer contract, ``ai_workflows.mcp`` is part
of the surfaces layer: it may import
:mod:`ai_workflows.workflows` / :mod:`ai_workflows.primitives` but
nothing imports it.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import Callable, Mapping
from typing import Any

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from ai_workflows.graph.audit_cascade import AuditVerdict, _strip_code_fence
from ai_workflows.graph.cost_callback import CostTrackingCallback
from ai_workflows.graph.tiered_node import tiered_node
from ai_workflows.mcp.schemas import (
    CancelRunInput,
    CancelRunOutput,
    ListRunsInput,
    ResumeRunInput,
    ResumeRunOutput,
    RunAuditCascadeInput,
    RunAuditCascadeOutput,
    RunSummary,
    RunWorkflowInput,
    RunWorkflowOutput,
)
from ai_workflows.primitives.cost import CostTracker
from ai_workflows.primitives.retry import (
    NonRetryable,
    RetryableSemantic,
    RetryableTransient,
    RetryPolicy,
)
from ai_workflows.primitives.storage import SQLiteStorage, default_storage_path
from ai_workflows.primitives.tiers import TierConfig
from ai_workflows.workflows import auditor_tier_registry
from ai_workflows.workflows._dispatch import (
    ResumePreconditionError,
    UnknownTierError,
    UnknownWorkflowError,
)
from ai_workflows.workflows._dispatch import (
    resume_run as _dispatch_resume_run,
)
from ai_workflows.workflows._dispatch import (
    run_workflow as _dispatch_run_workflow,
)

__all__ = ["build_server"]


# ---------------------------------------------------------------------------
# Private helpers for ``run_audit_cascade`` (M12 T05 — Option A bypass)
# These live in mcp/server.py, NOT in workflows/_dispatch.py — the latter
# is workflows-layer code and importing it from surfaces is fine, but the
# helpers themselves couple to the tiered_node + storage surfaces which
# belong in the surfaces layer.  Moving them to _dispatch.py would violate
# the four-layer rule (workflows must not import mcp/cli).
# ---------------------------------------------------------------------------


async def _resolve_audit_artefact(payload: RunAuditCascadeInput) -> dict[str, Any]:
    """Resolve the artefact to audit from ``payload``.

    Two paths per H2 Option A (locked 2026-04-27):

    * ``run_id_ref + artefact_kind`` — calls
      ``storage.read_artifact(run_id, kind)``; the returned SQL row
      wrapper has shape ``{run_id, kind, payload_json: str, created_at}``.
      ``payload_json`` is a stringified JSON blob the storage layer stored
      verbatim (``storage.py:181-186``); this helper decodes it via
      ``json.loads`` before returning so the auditor sees the artefact
      dict, not the storage wrapper.  Raises :class:`fastmcp.exceptions.ToolError`
      on a ``None`` return (unknown ``(run_id, kind)`` pair).
    * ``inline_artefact_ref`` — returns the caller-supplied dict unchanged;
      no decode needed because the caller supplied a real Python dict.
    """
    if payload.run_id_ref is not None:
        run_id = payload.run_id_ref
        kind = payload.artefact_kind  # validated non-None by schema
        storage = await SQLiteStorage.open(default_storage_path())
        row = await storage.read_artifact(run_id, kind)  # type: ignore[arg-type]
        if row is None:
            raise ToolError(
                f"no artefact found for run_id={run_id!r}, kind={kind!r}"
            )
        # Round-2 H2: read_artifact returns the SQL row wrapper, not the
        # artefact payload.  Decode the stored JSON string.
        return json.loads(row["payload_json"])
    # inline_artefact_ref — schema guarantees exactly one source is set
    return payload.inline_artefact_ref  # type: ignore[return-value]


def _build_standalone_audit_config(
    audit_run_id: str,
) -> tuple[CostTracker, CostTrackingCallback, RetryPolicy, dict[str, TierConfig]]:
    """Build per-call plumbing for a standalone audit invocation.

    Returns a 4-tuple ``(cost_tracker, cost_callback, policy, tier_registry)``:

    * ``cost_tracker`` — fresh in-memory :class:`~ai_workflows.primitives.cost.CostTracker`
      isolated from any dispatch-layer tracker.
    * ``cost_callback`` — fresh :class:`~ai_workflows.graph.cost_callback.CostTrackingCallback`
      wrapping ``cost_tracker``; no budget cap (standalone audit is cost-display only).
    * ``policy`` — :class:`~ai_workflows.primitives.retry.RetryPolicy` with
      ``max_transient_attempts=1, max_semantic_attempts=1`` (single-pass; no
      node-level self-loop for standalone audit).
    * ``tier_registry`` — auditor-only ``{"auditor-sonnet": ..., "auditor-opus": ...}``
      via :func:`~ai_workflows.workflows.auditor_tier_registry`.

    None of these objects are shared with the process-level dispatch tracker/
    callback so telemetry for the standalone audit stays isolated.
    """
    cost_tracker = CostTracker()
    cost_callback = CostTrackingCallback(cost_tracker=cost_tracker, budget_cap_usd=None)
    policy = RetryPolicy(max_transient_attempts=1, max_semantic_attempts=1)
    registry = auditor_tier_registry()
    return cost_tracker, cost_callback, policy, registry


def _build_audit_configurable(
    *,
    cost_callback: CostTrackingCallback,
    policy: RetryPolicy,
    tier_registry: dict[str, TierConfig],
    run_id: str,
) -> dict[str, Any]:
    """Build the ``config["configurable"]`` dict for a standalone audit node call.

    Keys required by :func:`~ai_workflows.graph.tiered_node.tiered_node`
    (verified against ``tiered_node.py:204-221``):

    * ``tier_registry`` — required; auditor-only entries.
    * ``cost_callback`` — required; per-call telemetry isolation.
    * ``run_id`` — required; for cost-record keying.
    * ``pricing`` — explicit per spec (Max flat-rate computes $0 with empty
      pricing; future per-tier-pricing change would surface non-zero values
      without code change).  ``ClaudeCodeSubprocess`` defaults gracefully on
      missing model keys (``tiered_node.py:218`` ``configurable.get("pricing") or {}``),
      but we pass it explicitly for forward-compatibility.
    * ``workflow`` — for log-record triage; mirrors ``_dispatch._build_cfg`` pattern.

    NOT supplied: ``semaphores`` (no concurrency caps for one-shot audit),
    ``ollama_circuit_breakers`` (auditors are Claude-only; no Ollama path).
    """
    return {
        "tier_registry": tier_registry,
        "cost_callback": cost_callback,
        "run_id": run_id,
        "pricing": {},  # explicit per spec — Max flat-rate computes $0 with empty pricing
        "workflow": "standalone-audit",
    }


def _make_standalone_auditor_prompt_fn(
    artefact: dict[str, Any],
) -> Callable[[Mapping[str, Any]], tuple[str | None, list[dict]]]:
    """Return a prompt builder that embeds ``artefact`` for the auditor tier.

    The returned callable conforms to
    :func:`~ai_workflows.graph.tiered_node.tiered_node`'s ``prompt_fn``
    contract: ``(state) -> (system, messages)`` where ``system`` may be
    ``None``.  State is ignored — the artefact is captured at factory time
    so the prompt is fixed for this invocation.

    The prompt embeds the artefact JSON inside an ``<artefact>…</artefact>``
    block and instructs the auditor to return
    :class:`~ai_workflows.graph.audit_cascade.AuditVerdict` JSON, consistent
    with the cascade's own auditor-prompt template.
    """
    artefact_json = json.dumps(artefact, indent=2)
    system = (
        "You are a strict auditor. Return ONLY valid JSON matching the "
        "AuditVerdict schema: "
        '{"passed": bool, "failure_reasons": [str, ...], "suggested_approach": str | null}. '
        "No prose, no code blocks, no explanation — raw JSON only."
    )
    content = (
        "Audit the following artefact for correctness. "
        "Return AuditVerdict JSON.\n\n"
        f"<artefact>{artefact_json}</artefact>"
    )

    def _prompt_fn(state: Mapping[str, Any]) -> tuple[str | None, list[dict]]:  # noqa: ARG001
        return (
            system,
            [{"role": "user", "content": content}],
        )

    return _prompt_fn


_ACTIVE_RUNS: dict[str, asyncio.Task] = {}
"""Process-local registry of in-flight run dispatch tasks (M6 T02).

Keyed by resolved ``run_id`` (the value ``_dispatch_run_workflow``
returns — either the caller-supplied id or an auto-generated ULID).
The registry is **best-effort** by architectural contract
(``architecture.md §8.7``): the storage-level status flip that
:meth:`SQLiteStorage.cancel_run` performs is authoritative, and the
:meth:`asyncio.Task.cancel` call is a nicety that unwinds an
actively-running dispatch task sooner than waiting for a gate or
timeout. The registry does not survive process restart; a run that
was mid-flight in a crashed MCP server simply loses its in-flight
cancel path, but ``runs.status`` is still flippable via the storage
surface.

Entries are inserted by ``run_workflow`` before the ``await`` on the
wrapping task and removed in the task's ``finally`` block so the
registry does not leak — in the happy path, the completion / pause
surfaces the id is already gone by the time ``cancel_run`` would
check. That no-longer-present branch falls back to the M4 storage-only
behaviour which, for a terminal row, is a no-op (``"already_terminal"``)
and for a still-``pending`` row does the flip — precisely the M4
contract.
"""


def build_server() -> FastMCP:
    """Construct a fresh FastMCP server with all five tools registered.

    Returns a new :class:`FastMCP` instance per call so tests can drive
    the surface in-process without global state (mirrors the ``aiw``
    Typer app pattern in :mod:`ai_workflows.cli`).

    Each tool is a ``@mcp.tool()``-decorated coroutine whose signature
    binds one of the pydantic I/O models from
    :mod:`ai_workflows.mcp.schemas`; FastMCP auto-derives the JSON-RPC
    schema from those annotations (KDR-008). M4 T02-T05 wired the first
    four tools; M12 T05 adds the fifth (``run_audit_cascade``).
    """
    mcp = FastMCP("ai-workflows")

    @mcp.tool()
    async def run_workflow(payload: RunWorkflowInput) -> RunWorkflowOutput:
        """Execute a workflow end-to-end. Pauses at HumanGate interrupts.

        Mirrors ``aiw run`` by routing through
        :func:`ai_workflows.workflows._dispatch.run_workflow`. Unknown
        workflow names and unknown ``tier_overrides`` entries (M5 T05)
        surface as a :class:`fastmcp.exceptions.ToolError` (JSON-RPC
        error response); in-band failures (budget breach, validator
        exhaust) come back as ``status="errored"`` with a descriptive
        ``error`` string in the output.

        M6 T02: the dispatch call is wrapped in an
        :func:`asyncio.create_task` and registered under the resolved
        ``run_id`` in :data:`_ACTIVE_RUNS` so ``cancel_run`` can abort
        the in-flight task. The registry entry is inserted **before**
        the ``await`` (so a cancel racing the run is visible) and
        removed in a ``finally`` regardless of success / failure /
        cancellation.
        """
        run_id_key = payload.run_id

        async def _dispatch_body() -> dict:
            return await _dispatch_run_workflow(
                workflow=payload.workflow_id,
                inputs=payload.inputs,
                budget_cap_usd=payload.budget_cap_usd,
                run_id=payload.run_id,
                tier_overrides=payload.tier_overrides,
            )

        task = asyncio.create_task(_dispatch_body())
        if run_id_key is not None:
            _ACTIVE_RUNS[run_id_key] = task
        try:
            try:
                result = await task
            except (UnknownWorkflowError, UnknownTierError) as exc:
                raise ToolError(str(exc)) from None
        finally:
            if run_id_key is not None:
                _ACTIVE_RUNS.pop(run_id_key, None)
        return RunWorkflowOutput(**result)

    @mcp.tool()
    async def resume_run(payload: ResumeRunInput) -> ResumeRunOutput:
        """Clear a pending ``HumanGate`` and advance the workflow.

        Mirrors ``aiw resume`` by routing through
        :func:`ai_workflows.workflows._dispatch.resume_run`. Precondition
        failures (unknown run id, cancelled run) and unknown workflow
        names surface as :class:`fastmcp.exceptions.ToolError` (JSON-RPC
        error response); in-band failures (post-gate exception,
        validator exhaust) come back as ``status="errored"`` with a
        descriptive ``error`` string in the output.
        """
        try:
            result = await _dispatch_resume_run(
                run_id=payload.run_id,
                gate_response=payload.gate_response,
            )
        except (ResumePreconditionError, UnknownWorkflowError) as exc:
            raise ToolError(str(exc)) from None
        return ResumeRunOutput(**result)

    @mcp.tool()
    async def list_runs(payload: ListRunsInput) -> list[RunSummary]:
        """List recorded runs (newest first). Pure read — no graph state touched.

        Filters compose with ``AND`` per :meth:`SQLiteStorage.list_runs`.
        Each :class:`RunSummary` carries ``total_cost_usd`` — the sole
        cost surface the MCP server exposes (see the M4 kickoff decision
        dropping ``get_cost_report`` in favour of this field).

        Mirrors ``aiw list-runs`` in :mod:`ai_workflows.cli`. Never opens
        the checkpointer, never compiles a graph.
        """
        storage = await SQLiteStorage.open(default_storage_path())
        rows = await storage.list_runs(
            limit=payload.limit,
            status_filter=payload.status,
            workflow_filter=payload.workflow,
        )
        return [RunSummary(**row) for row in rows]

    @mcp.tool()
    async def cancel_run(payload: CancelRunInput) -> CancelRunOutput:
        """Cancel a run: abort any in-flight dispatch task, then flip storage.

        Two halves per ``architecture.md §8.7``:

        1. **In-flight abort (M6 T02).** If :data:`_ACTIVE_RUNS` has a
           task for this ``run_id``, call :meth:`asyncio.Task.cancel`.
           This is best-effort and does not block on the task actually
           unwinding — the caller is notified via the storage flip
           return value, not by awaiting the cancelled task here
           (blocking here would let a stuck worker hang the MCP
           connection indefinitely). ``durability="sync"`` on the
           dispatcher's ``ainvoke`` call guarantees the
           last-completed-step checkpoint hits SQLite before
           :class:`asyncio.CancelledError` propagates, so a subsequent
           ``resume_run`` on the same ``run_id`` can continue from the
           last durable state.
        2. **Storage flip (M4 T05).** Authoritative per the
           architectural contract. Flips ``runs.status`` to
           ``cancelled`` + stamps ``finished_at``. A subsequent
           ``resume_run`` refuses cancelled rows via the M4 T03
           precondition guard.

        If the run is not in :data:`_ACTIVE_RUNS` (already completed,
        paused at a gate, or started in another process), step 1 is a
        no-op and we fall through to the M4 storage-only path cleanly
        — no ``KeyError``.
        """
        task = _ACTIVE_RUNS.get(payload.run_id)
        if task is not None and not task.done():
            task.cancel()
        storage = await SQLiteStorage.open(default_storage_path())
        try:
            result = await storage.cancel_run(payload.run_id)
        except ValueError as exc:
            raise ToolError(str(exc)) from None
        return CancelRunOutput(run_id=payload.run_id, status=result)

    @mcp.tool()
    async def run_audit_cascade(payload: RunAuditCascadeInput) -> RunAuditCascadeOutput:
        """Audit an existing artefact via a single ``auditor-{tier}`` call — standalone.

        Per Option A locked at M12 T05 round-1 (2026-04-27): this tool
        BYPASSES the cascade primitive (``audit_cascade_node``) and
        instantiates a single-pass auditor ``tiered_node`` directly — the
        cascade primitive requires a primary LLM call which standalone
        audit does not have.

        Resolves the artefact via ``payload.run_id_ref + artefact_kind``
        (recover via ``storage.read_artifact(run_id, kind)``) or
        ``payload.inline_artefact_ref`` (caller-supplied dict). Auditor
        tier: ``auditor-opus`` (default) or ``auditor-sonnet`` per
        ``payload.tier_ceiling``. Telemetry (T04) records the audit call
        with ``role="auditor"`` (factory-time binding on ``tiered_node``);
        output's ``by_role`` aggregates via
        ``CostTracker.by_role(audit_run_id)``.

        Errors surface as ``ToolError`` for: unknown ``(run_id, kind)``
        (storage.read_artifact returns None), tier registry lookup miss,
        auditor adapter failure (LLM dispatch or output-parse error).
        """
        artefact = await _resolve_audit_artefact(payload)

        audit_run_id = f"audit-{uuid.uuid4().hex[:12]}"
        auditor_tier_name = f"auditor-{payload.tier_ceiling}"

        cost_tracker, cost_callback, policy, tier_registry = _build_standalone_audit_config(
            audit_run_id=audit_run_id,
        )

        auditor_node = tiered_node(
            tier=auditor_tier_name,
            prompt_fn=_make_standalone_auditor_prompt_fn(artefact),
            output_schema=AuditVerdict,
            node_name="standalone_auditor",
            role="auditor",  # T04 factory-time role binding (KDR-011)
        )

        state: dict[str, Any] = {"run_id": audit_run_id}
        config = {
            "configurable": _build_audit_configurable(
                cost_callback=cost_callback,
                policy=policy,
                tier_registry=tier_registry,
                run_id=audit_run_id,
            )
        }
        try:
            verdict_state = await auditor_node(state, config)
        except (UnknownTierError, NonRetryable, RetryableSemantic, RetryableTransient) as exc:
            raise ToolError(f"audit invocation failed: {exc}") from None

        # Round-2 H1: tiered_node returns raw text under f"{node_name}_output"
        # (verified tiered_node.py:395-398) — does NOT auto-parse against
        # output_schema. The cascade primitive parses via _audit_verdict_node at
        # audit_cascade.py:751; Option A's bypass inherits the obligation to
        # parse explicitly here.
        raw_text = verdict_state.get("standalone_auditor_output", "") or ""
        try:
            # _strip_code_fence handles the markdown-fenced JSON shape that
            # real Claude CLI responses sometimes emit (M12 T05 HIGH-01 fix;
            # shared helper from graph/audit_cascade.py used here and in
            # _audit_verdict_node so both parse paths stay in sync).
            verdict = AuditVerdict.model_validate_json(_strip_code_fence(raw_text))
        except Exception as exc:
            raise ToolError(
                f"auditor produced unparseable output — expected AuditVerdict JSON, "
                f"got: {raw_text[:200]!r}"
            ) from exc

        return RunAuditCascadeOutput(
            passed=verdict.passed,
            verdicts_by_tier={auditor_tier_name: verdict},
            suggested_approach=verdict.suggested_approach if not verdict.passed else None,
            total_cost_usd=cost_tracker.total(audit_run_id),
            by_role=cost_tracker.by_role(audit_run_id),
        )

    return mcp
