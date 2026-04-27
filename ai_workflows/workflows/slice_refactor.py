"""Slice-refactor workflow (M6).

.. note::

   **Quality knobs (M12 Task 03 / ADR-0009 / KDR-014)**

   The audit cascade for ``slice-worker`` is opt-in via a module-level
   constant:

   - ``_AUDIT_CASCADE_ENABLED_DEFAULT = False`` — framework-author default.
   - ``AIW_AUDIT_CASCADE=1`` — global env-var override; flips ALL workflows.
   - ``AIW_AUDIT_CASCADE_SLICE_REFACTOR=1`` — per-workflow override.

   Per KDR-014, quality knobs MUST NOT appear on ``SliceRefactorInput`` or
   any ``WorkflowSpec``/CLI flag. The decision is made once per Python process
   at module-import time. See ADR-0009 §Open questions for the enable-only
   asymmetry.

   The ``_AUDIT_CASCADE_ENABLED`` constant has the same name in ``planner.py``
   and ``slice_refactor.py`` by design — each module owns its own decision;
   cross-module references must qualify with the module name.

   The composed planner sub-graph inherits the planner module's own cascade
   decision via ``build_planner()`` — its compiled graph reflects whatever the
   planner module decided at its own import. ``slice_refactor``'s cascade
   decision applies only to the ``slice-worker`` node inside
   ``_build_slice_branch_subgraph()``.

Original module docstring follows.

Outer DAG that composes the M3/M5 ``planner`` sub-graph with a parallel
per-slice worker fan-out, strict-review gate, and ``apply`` terminal.
Introduced by **M6 Task 01** (slice-discovery phase); extended by
**M6 Task 02** (this revision) with the per-slice worker fan-out and
the ``slice_refactor`` carry-over of M4 T05's in-flight cancellation
wiring.

T06 graph shape:

    START → planner_subgraph → slice_list_normalize
          → (Send fan-out) slice_branch  [one per SliceSpec]
          → aggregate → slice_refactor_review (HumanGate, strict_review=True)
                      → apply → END   [on "approved" — writes one artefact
                                      row per succeeded SliceResult]
                      → END           [on "rejected" — no artefacts; dispatch
                                      flips runs.status = gate_rejected]

Each ``slice_branch`` is a compiled sub-graph that runs ``slice_worker``
(plain :func:`tiered_node`) → ``slice_worker_validator`` with a
:func:`retrying_edge` self-loop on ``RetryableTransient`` /
``RetryableSemantic``, then flows through ``slice_branch_finalize``
(T04) on the terminal path to convert an exhausted-retry branch into
a :class:`SliceFailure` row. This is the LangGraph-native shape for
per-branch retry under :class:`Send` — the retry state
(last_exception, retry counts) stays scoped to the single Send payload,
so a semantic retry on slice *i* re-runs slice *i* only (not siblings),
satisfying T03 ACs 3 + 4.

T02 shipped a compound worker node with an inline parse as a shortcut;
T03 reverts that shortcut per the M6-T02-ISS-01 carry-over: the worker
and validator are now distinct nodes with a ``retrying_edge`` between
them, matching the KDR-004 pattern used by the planner
(``TieredNode → ValidatorNode → retrying_edge``).

T04 replaces the placeholder ``aggregate`` body with the real
:func:`_aggregate` that composes ``slice_results`` (successes) and
``slice_failures`` (exhausted branches) into a single
:class:`SliceAggregate`. Partial-failure handling is faithful — the
aggregator runs even when every branch fails; the double-failure
hard-stop (architecture.md §8.2) is T07's wiring, gated on
``_non_retryable_failures >= 2`` before the aggregator edge.

T05 adds the strict-review ``HumanGate`` (architecture.md §8.3) between
``aggregate`` and ``apply``. The gate id is exported as module-level
:data:`TERMINAL_GATE_ID` so :mod:`ai_workflows.workflows._dispatch` can
resolve the resumed-response state key uniformly across workflows
(resolves T01-CARRY-DISPATCH-GATE from the T01 audit).

T06 replaces the T05-era stub with the real :func:`_apply` node: on
``"approved"`` it writes one :class:`SliceResult` per succeeded slice
to the ``artifacts`` table via :meth:`SQLiteStorage.write_artifact`
(keyed ``(run_id, f"{SLICE_RESULT_ARTIFACT_KIND}:{slice_id}")`` so
repeat invocations are idempotent under the existing
``ON CONFLICT(run_id, kind)`` clause — no schema migration, no
signature change to ``write_artifact``). It returns
``{"applied_artifact_count": <int>}`` so dispatch can detect completion
via the :data:`FINAL_STATE_KEY` convention (``T01-CARRY-DISPATCH-COMPLETE``
resolution from the T01 audit).

On ``"rejected"`` the graph routes straight to ``END`` and dispatch's
``_build_resume_result_from_final`` flips ``runs.status = gate_rejected``;
on ``"approved"`` the graph flows through ``apply`` → ``END`` and
dispatch flips ``runs.status = completed``.

T07 adds the double-failure hard-stop edge (architecture.md §8.2):
a conditional edge between the fan-in of ``slice_branch`` and the
``aggregate`` node that routes to :func:`_hard_stop` when
``len(state["slice_failures"]) >= HARD_STOP_FAILURE_THRESHOLD`` (==2).
The ``_hard_stop`` terminal node writes a ``hard_stop_metadata``
artefact (failing slice ids) via :meth:`SQLiteStorage.write_artifact`
and returns ``{"hard_stop_failing_slice_ids": [...]}`` so dispatch
can flip ``runs.status = "aborted"`` with ``finished_at``. The edge
reads ``slice_failures`` directly (``operator.add``-reduced — exact
count) rather than ``_non_retryable_failures`` (``max``-reduced —
undercounts under parallel writes, see :func:`_merge_non_retryable_failures`
docstring and M6-T04-ISS-01). Per-tier concurrency semaphore lands
in :mod:`ai_workflows.workflows._dispatch._build_semaphores` —
dispatch builds one :class:`asyncio.Semaphore` per tier from the
registry's ``max_concurrency`` and threads it through
``configurable["semaphores"]`` for :func:`tiered_node` to acquire at
the provider-call boundary.

Architecture grounding:
[architecture.md §4.3](../../design_docs/architecture.md) — "slice_refactor:
planner sub-graph → per-slice worker nodes (parallel) → per-slice
validator → aggregate → strict-review gate → apply". KDR-001 (LangGraph
owns composition / parallelism), KDR-009 (checkpointer shared across
parent + sub-graph), KDR-010 (bare-typed schemas, enforced by paired
validators in later tasks).

Durability on the ``ainvoke`` path (T02, carry-over from M4 T05)
----------------------------------------------------------------
LangGraph's ``durability="sync"`` flag guarantees the last-completed-step
checkpoint hits SQLite before a cancellation unwinds — load-bearing for
the in-flight ``cancel_run → immediate resume`` path that T02 owns.
The T02 task spec placed the flag on :meth:`StateGraph.compile`, but the
installed LangGraph version exposes ``durability`` as a kwarg on
:meth:`CompiledStateGraph.ainvoke` / :meth:`astream`, **not** on
:meth:`StateGraph.compile` (verified via ``inspect.signature``: compile
accepts ``checkpointer / cache / store / interrupt_before /
interrupt_after / debug / name`` only). The dispatch shim
:mod:`ai_workflows.workflows._dispatch` therefore threads
``durability="sync"`` at the ``ainvoke`` boundary for every run, which
is functionally equivalent — the checkpointer still synchronously
commits last-completed-step state before ``CancelledError`` propagates.
This deviation from the spec's literal compile-time wiring is documented
in CHANGELOG under the T02 entry.

ToolNode absence (T02, carry-over from M4 T05)
----------------------------------------------
M6's workflows do **not** use LangGraph's ``ToolNode``. Workers are
plain :class:`TieredNode` calls that return a raw string, which a
paired :class:`ValidatorNode` (T03) turns into a :class:`SliceResult`.
:issue:`langchain-ai/langgraph#6726` (mid-tool-call cancel leaves
``AIMessage.tool_calls`` unpaired with ``ToolMessage``, corrupting
message history) therefore is not reachable from this workflow's code
path. A future task that adds ``ToolNode`` will own the mid-tool-call
cancel guard.

Relationship to sibling modules
-------------------------------
* :mod:`ai_workflows.workflows.planner` — reused as a sub-graph via
  ``build_planner().compile()``. The planner's gate_id
  ``plan_review`` and its state keys (``input`` / ``plan`` /
  ``explorer_report`` / ``gate_plan_review_response``) flow through
  the sub-graph boundary into the outer state. T01 declares those
  keys on :class:`SliceRefactorState` so the sub-graph's writes land
  on the parent state — LangGraph's state-channel semantics only
  propagate keys declared on both sides.
* :mod:`ai_workflows.workflows._dispatch` — the shared run/resume
  entry point. T01 introduces a module-level ``initial_state`` hook
  (see :func:`initial_state` below) so dispatch can construct the
  initial state dict for ``slice_refactor`` without hardcoding a
  second ``*Input`` class name in ``_build_initial_state``. T02
  relies on the same helper to thread ``durability="sync"`` through
  ``ainvoke`` for every dispatched run.
* :mod:`ai_workflows.graph.tiered_node` — the ``slice-worker`` node
  is a :func:`tiered_node` call; the tier registry declared by
  :func:`slice_refactor_tier_registry` routes the tier to local Qwen
  via Ollama by default (cost-free, KDR-003).
"""

from __future__ import annotations

import json
import operator
import os
from typing import Annotated, Any, Literal, TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ai_workflows.graph.audit_cascade import audit_cascade_node
from ai_workflows.graph.error_handler import wrap_with_error_handler
from ai_workflows.graph.human_gate import human_gate
from ai_workflows.graph.ollama_fallback_gate import (
    FALLBACK_DECISION_STATE_KEY,
    FallbackChoice,
    build_ollama_fallback_gate,
)
from ai_workflows.graph.retrying_edge import retrying_edge
from ai_workflows.graph.tiered_node import tiered_node
from ai_workflows.primitives.circuit_breaker import CircuitOpen
from ai_workflows.primitives.retry import (
    AuditFailure,
    NonRetryable,
    RetryableSemantic,
    RetryPolicy,
)
from ai_workflows.primitives.tiers import LiteLLMRoute, TierConfig
from ai_workflows.workflows import register
from ai_workflows.workflows.planner import (
    ExplorerReport,
    OllamaFallback,
    PlannerInput,
    PlannerPlan,
    build_planner,
    planner_tier_registry,
)

# ---------------------------------------------------------------------------
# M12 T03 / ADR-0009 / KDR-014 — cascade quality policy at module level.
# Same-named constant as planner.py by design — each module owns its own
# decision; cross-module references must qualify with the module name.
# Framework-author default; flip to True post-T04 telemetry per workflow,
# code-edit + commit + release. NO ``audit_cascade_enabled`` field on
# SliceRefactorInput; per KDR-014 quality knobs MUST NOT land on Input models.
# ---------------------------------------------------------------------------
_AUDIT_CASCADE_ENABLED_DEFAULT = False

# Operator override (read at module-import). Two granularities:
#   AIW_AUDIT_CASCADE=1                      — flips ALL workflows.
#   AIW_AUDIT_CASCADE_SLICE_REFACTOR=1       — flips ONLY this workflow.
# Same enable-only-asymmetry semantics as planner.py: per-workflow var
# cannot disable what the global enables. See ADR-0009 §Open questions
# for the three-state-override deferral.
_AUDIT_CASCADE_ENABLED = (
    _AUDIT_CASCADE_ENABLED_DEFAULT
    or os.getenv("AIW_AUDIT_CASCADE", "0") == "1"
    or os.getenv("AIW_AUDIT_CASCADE_SLICE_REFACTOR", "0") == "1"
)

__all__ = [
    "_AUDIT_CASCADE_ENABLED_DEFAULT",
    "_AUDIT_CASCADE_ENABLED",
    "SLICE_REFACTOR_OLLAMA_FALLBACK",
    "SliceRefactorInput",
    "SliceSpec",
    "SliceResult",
    "SliceFailure",
    "SliceAggregate",
    "SliceRefactorState",
    "SliceBranchState",
    "SLICE_WORKER_RETRY_POLICY",
    "TERMINAL_GATE_ID",
    "FINAL_STATE_KEY",
    "SLICE_RESULT_ARTIFACT_KIND",
    "HARD_STOP_FAILURE_THRESHOLD",
    "HARD_STOP_METADATA_ARTIFACT_KIND",
    "build_slice_refactor",
    "slice_refactor_tier_registry",
    "slice_refactor_eval_node_schemas",
    "initial_state",
]


SLICE_REFACTOR_OLLAMA_FALLBACK = OllamaFallback(
    logical="slice-worker",
    fallback_tier="planner-synth",
)
"""Tier-pair the ``slice_refactor`` workflow falls back to on an Ollama outage (M8 T04).

``slice-worker`` is ``ollama/qwen2.5-coder:32b`` per M6 T02 — identical
model to ``planner-explorer`` but a distinct registry entry so the
per-tier ``asyncio.Semaphore`` caps workers independently from the
planner sub-graph. The fallback route reuses ``planner-synth``
(``ClaudeCodeRoute(cli_model_flag="opus")``) — a non-Ollama,
non-breakered tier already declared by the composed
:func:`planner_tier_registry`, so no new registry entry is needed. After
:attr:`FallbackChoice.FALLBACK` every remaining :func:`tiered_node`
invocation tagged ``slice-worker`` resolves through the state-level
override mechanism (see
:func:`ai_workflows.graph.tiered_node._resolve_tier`) and dispatches the
Opus route.
"""


TERMINAL_GATE_ID = "slice_refactor_review"
"""Gate id for the strict-review ``HumanGate`` this workflow pauses at (T05).

Surfaced as a module-level constant so
:mod:`ai_workflows.workflows._dispatch` can resolve the gate-response
state key (``f"gate_{TERMINAL_GATE_ID}_response"``) for this workflow's
terminal approve/reject decision without hardcoding the planner's
``plan_review`` gate id. The planner exposes a matching constant at the
same symbol name so dispatch can discover it uniformly across workflows
(T01-CARRY-DISPATCH-GATE resolution).
"""


FINAL_STATE_KEY = "applied_artifact_count"
"""State key dispatch reads to detect a completed ``slice_refactor`` run (T06).

The ``apply`` node returns ``{"applied_artifact_count": <int>}`` on the
approve path (including ``0`` for a 0-success aggregate) — writing this
key signals the run reached its terminal artefact-persistence node.
:mod:`ai_workflows.workflows._dispatch` reads this constant (falling back
to ``"plan"`` for legacy workflows that omit it) to decide whether to
flip ``runs.status = completed`` post-resume. Resolves
``T01-CARRY-DISPATCH-COMPLETE`` from the T01 audit: before this
convention, dispatch hardcoded ``state["plan"]`` as the completion
signal, which was planner-specific and left slice_refactor's approve
path without a completion surface.
"""


SLICE_RESULT_ARTIFACT_KIND = "slice_result"
"""Namespace prefix for per-slice rows written by the ``apply`` node (T06).

Each succeeded :class:`SliceResult` lands in ``artifacts`` under
``kind=f"{SLICE_RESULT_ARTIFACT_KIND}:{slice_id}"``. Embedding the
``slice_id`` in the ``kind`` string gives a natural ``(run_id, slice_id)``
unique constraint on top of the existing ``(run_id, kind)`` primary key
(`migrations/003_artifacts.sql`) without requiring a schema change or
adding a slice-specific kwarg to :meth:`SQLiteStorage.write_artifact`.
The ``ON CONFLICT(run_id, kind) DO UPDATE`` clause makes re-invocation
of ``apply`` (e.g. via resume-after-crash) idempotent: the second call
overwrites each row with byte-identical payload, leaving the row count
unchanged — the "natural unique constraint" option from the T06 spec's
idempotency AC.
"""


HARD_STOP_FAILURE_THRESHOLD = 2
"""Number of per-slice ``NonRetryable`` failures that triggers the hard-stop (T07).

Matches architecture.md §8.2 verbatim: two distinct per-slice failures
abort the run regardless of sibling independence. The threshold is
read by :func:`_route_before_aggregate` against the length of
``state["slice_failures"]`` — the ``operator.add``-reduced list
populated by :func:`_slice_branch_finalize` when a branch exhausts
its retry budget. Using the list length (exact, monotonic under
parallel fan-in) rather than ``state["_non_retryable_failures"]``
(``max``-reduced — collapses parallel bumps, see
:func:`_merge_non_retryable_failures`) is load-bearing: the counter's
reducer undercounts under fan-out, so the hard-stop would never fire
in the fan-out case. The list-length approach is the M6-T04-ISS-01
resolution surfaced at T07 time.
"""


HARD_STOP_METADATA_ARTIFACT_KIND = "hard_stop_metadata"
"""Artefact ``kind`` for the hard-stop metadata row (T07).

:func:`_hard_stop` writes one ``artifacts`` row with this ``kind`` and
a JSON payload ``{"failing_slice_ids": [id1, id2, ...]}`` so the run's
post-mortem surface can read the identities of the failing branches
without re-running the graph. Reuses :meth:`SQLiteStorage.write_artifact`
(no schema change, no migration — same reuse pattern T06 picked for
``slice_result`` rows). One row per run (no ``slice_id`` suffix) —
multiple calls on the same ``run_id`` idempotently upsert the same
payload under the existing ``(run_id, kind)`` primary key.
"""


SLICE_WORKER_RETRY_POLICY = RetryPolicy(
    max_transient_attempts=5, max_semantic_attempts=3
)
"""Retry budget for the per-slice worker self-loop (T03).

Mirrors :data:`PLANNER_RETRY_POLICY`'s rationale: transient-bucket attempts
are cheap (request-admission failures with ``input_tokens=null``), so
five attempts absorb a short burst of Gemini/Ollama 503s; semantic
attempts burn real output tokens (a full slice re-roll), so three is the
hard cap per architecture.md §8.2. The semantic cap lines up with the
T03 spec's "max 3 retries" requirement verbatim.
"""


def _merge_last_exception(existing: Any, update: Any) -> Any:
    """Reducer for ``last_exception`` under parallel fan-out.

    Keeps the latest non-``None`` value so a failing parallel worker is
    not silently overwritten by a sibling worker's success-side clear
    (``tiered_node`` writes ``last_exception: None`` on the happy path
    per the T07 carry-over). Sequential writes degrade to "last-wins"
    (the previous planner sub-graph semantics) because every sequential
    update goes through the reducer with the prior channel value as
    ``existing`` — a non-``None`` update overwrites, a ``None`` update
    leaves ``existing`` untouched which is identical to the happy-path
    clear when ``existing`` is already ``None``.
    """
    return update if update is not None else existing


def _merge_retry_counts(
    existing: dict[str, int] | None, update: dict[str, int] | None
) -> dict[str, int]:
    """Reducer for ``_retry_counts`` under parallel fan-out.

    Shallow-merges two dicts. Parallel workers bump disjoint node-name
    keys (one per worker), so the merge is conflict-free in the T02
    fan-out shape. If a future task adds multiple writers for the
    same ``node_name`` in parallel (e.g. a retry that re-fans-out),
    last-wins applies to the duplicate key — T07 will revisit.
    """
    merged = dict(existing or {})
    if update:
        merged.update(update)
    return merged


def _merge_ollama_fallback_fired(
    existing: bool | None, update: bool | None
) -> bool:
    """Sticky-OR reducer for ``_ollama_fallback_fired`` under parallel fan-out (M8 T04).

    Once the Ollama-fallback gate has fired in this run the flag stays
    ``True`` forever. Re-fan branches after :attr:`FallbackChoice.RETRY`
    / :attr:`FallbackChoice.FALLBACK` carry the flag on their Send
    payload; with N parallel branches echoing ``True`` through the
    fan-in, a scalar channel would trip LangGraph's
    :class:`InvalidUpdateError`. ``sticky-OR`` is idempotent, safe
    against re-fire, and matches the semantic: fire-once per run.
    """
    return bool(existing) or bool(update)


def _merge_mid_run_tier_overrides(
    existing: dict[str, str] | None, update: dict[str, str] | None
) -> dict[str, str]:
    """Reducer for ``_mid_run_tier_overrides`` under parallel fan-out (M8 T04).

    After :attr:`FallbackChoice.FALLBACK`, every re-fanned slice-branch
    Send payload carries the override dict so the sub-graph's
    :func:`tiered_node._resolve_tier` sees it. When N branches complete
    in parallel, each emits the same override back to the parent state
    — a scalar channel would trip :class:`InvalidUpdateError`. Shallow
    merge (last-wins per key) is safe: every branch writes the same
    dict, so duplicate-key collisions always resolve to the same value.
    Accepts ``None`` on either side (initial state / un-set channel).
    """
    merged = dict(existing or {})
    if update:
        merged.update(update)
    return merged


def _merge_non_retryable_failures(
    existing: int | None, update: int | None
) -> int:
    """Reducer for ``_non_retryable_failures`` under parallel fan-out.

    Uses ``max`` so a single burst of parallel failures reports the
    higher watermark rather than double-counting the same attempt
    when :func:`wrap_with_error_handler` reads the same pre-invocation
    ``prev_failures`` in every worker (each worker would write
    ``prev + 1``; summing would inflate the count by the fan-out
    width). Sequential writes still monotonically increase because each
    write's ``update`` is ``prev + 1`` read from the *updated* state.

    **Reliable only under sequential writes.** Across a parallel
    fan-out every branch reads the same pre-fan-in value (usually ``0``)
    from :func:`wrap_with_error_handler` and writes ``prev + 1 == 1``;
    ``max`` collapses N parallel failure writes to a counter of ``1``.
    Switching to a true sum would require a matching delta-write
    change in :mod:`ai_workflows.graph.error_handler` and affects every
    workflow — out of scope here and deliberately deferred. The
    canonical fan-out failure count is :data:`SliceRefactorState.slice_failures`
    (``operator.add``-reduced list), which :func:`_route_before_aggregate`
    uses for the double-failure hard-stop decision (T07 / M6-T04-ISS-01).
    """
    return max((existing or 0), (update or 0))


class SliceRefactorInput(BaseModel):
    """Caller-supplied input to ``slice_refactor``.

    T01 reuses ``goal`` / ``context`` / ``max_steps`` from
    :class:`PlannerInput` so the downstream planner sub-graph receives
    a properly-typed :class:`PlannerInput` without the caller having
    to know the sub-graph exists. Future M6 tasks may add
    slice-specific fields (e.g. ``slice_count_cap``) — keeping this
    class separate from :class:`PlannerInput` leaves that evolution
    path open without breaking the planner's contract.
    """

    goal: str = Field(min_length=1, max_length=4000)
    context: str | None = Field(default=None, max_length=4000)
    max_steps: int = Field(default=10, ge=1, le=25)


class SliceSpec(BaseModel):
    """One unit of refactor work derived from a :class:`PlannerStep`.

    T01 maps each :class:`PlannerStep` 1:1 to a :class:`SliceSpec`:
    ``id`` from the step's ``index`` (stringified), ``description``
    from ``title``, ``acceptance`` from ``actions``. The split from
    :class:`PlannerStep` is deliberate — planner steps are an
    LLM-output concern (schema constrained for Gemini's structured
    output budget, KDR-010), while slices are a worker-input concern
    and will evolve independently as T02+ attach worker-specific
    metadata.

    Bare-typed per KDR-010 / ADR-0002 — no ``Field(min_length=…)``
    bounds — so the schema stays usable as a LiteLLM
    ``response_format`` if a future worker wants one. ``extra="forbid"``
    is retained so a hallucinated key fails validation loud.
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    description: str
    acceptance: list[str]


class SliceResult(BaseModel):
    """One worker's output for a single :class:`SliceSpec` (T02).

    Produced by the paired :class:`ValidatorNode` (landing in T03) from
    the raw string the ``slice_worker`` :class:`TieredNode` returns.
    T02 ships only the model + fan-out wiring; the validator pairing
    + real worker prompt land in T03 with KDR-004 enforcement.

    Bare-typed per KDR-010 / ADR-0002 — the schema stays usable as a
    LiteLLM ``response_format`` for providers that support structured
    output (Gemini). ``extra="forbid"`` stays so a hallucinated key
    fails validation loud.
    """

    model_config = ConfigDict(extra="forbid")

    slice_id: str
    diff: str
    notes: str


class SliceFailure(BaseModel):
    """One branch's exhausted-retry record for the aggregator (T04).

    Emitted by the ``slice_branch_finalize`` sub-graph node when a
    branch reaches its sub-graph terminal with ``last_exception`` still
    populated — i.e. the worker → validator self-loop burnt through the
    three-bucket retry budget without producing a :class:`SliceResult`.
    The aggregator reads the concatenated ``slice_failures`` list
    (fanned in via ``operator.add``) alongside ``slice_results`` to
    build :class:`SliceAggregate`; T07 will read the same list to make
    the double-failure hard-stop decision (architecture.md §8.2).

    ``failure_bucket`` echoes the three-bucket retry taxonomy (KDR-006)
    but collapses :class:`RetryableTransient` exhaustion into
    ``non_retryable`` — at exhaustion the effect is indistinguishable
    from a :class:`NonRetryable` classification (further retries are
    impossible), and the spec literal-types only two buckets. The
    ``retryable_semantic`` variant is preserved for diagnostic clarity
    when the T03 in-validator escalation path did not fire (e.g. a
    future workflow whose validator does not self-escalate).

    Bare-typed per KDR-010 / ADR-0002 — ``extra="forbid"`` stays so a
    hallucinated key from a future writer fails validation loud.
    """

    model_config = ConfigDict(extra="forbid")

    slice_id: str
    last_error: str
    failure_bucket: Literal["retryable_semantic", "non_retryable"]


class SliceAggregate(BaseModel):
    """Summary of a fanned-out slice-refactor run (T04).

    Produced by the pure-function ``aggregate`` node over the reducer-
    accumulated ``slice_results`` (successes) and ``slice_failures``
    (exhausted branches). ``total_slices`` equals ``len(succeeded) +
    len(failed)`` by construction — it is not a separate input signal,
    just a convenience for the strict-review gate (T05) and the apply
    node (T06) so they don't have to re-derive it from both lists.

    No LLM call, no validator pairing (KDR-004 does not apply — this is
    synthesis, not generation). The aggregator is idempotent: calling
    it twice on the same state returns an equivalent :class:`SliceAggregate`.

    Bare-typed per KDR-010 / ADR-0002 — ``extra="forbid"`` stays. The
    schema is not sent to any LLM (no ``response_format`` consumer at
    T04); the bare-type guarantee keeps the option open.
    """

    model_config = ConfigDict(extra="forbid")

    succeeded: list[SliceResult]
    failed: list[SliceFailure]
    total_slices: int


class SliceRefactorState(TypedDict, total=False):
    """State carried through the compiled ``slice_refactor`` (parent) graph.

    The planner's state keys (``input`` / ``plan`` / ``explorer_output``
    / ``planner_output`` / ``explorer_report`` / gate-response slots /
    retry-taxonomy slots) are declared here so the planner sub-graph's
    writes propagate onto the outer state — LangGraph only shares
    channels declared on both sides of the sub-graph boundary.

    ``slice_worker_output`` was removed at T03. Under the T02 shortcut
    that key lived on the parent state (transiently populated by the
    compound worker node) and had to be omitted from the return dict to
    avoid the parallel-write collision. T03 scopes it to
    :class:`SliceBranchState` (the per-slice sub-graph's state) so it
    never crosses the Send/reduce boundary — the fan-out reducer only
    sees ``slice_results`` writes from each branch.

    Keys at T04 scope:
        slice_list: list of :class:`SliceSpec` written by
            ``slice_list_normalize``; read by the fan-out conditional
            edge.
        slice_results: accumulator — each happy-path branch
            contributes one :class:`SliceResult` via LangGraph's
            ``operator.add`` reducer; the parent sees the
            concatenated ``list[SliceResult]``.
        slice_failures: accumulator — each exhausted-retry branch
            contributes one :class:`SliceFailure` via ``operator.add``
            from the T04 ``slice_branch_finalize`` node; the parent
            sees the concatenated ``list[SliceFailure]``.
        aggregate: scalar :class:`SliceAggregate` written by the
            T04 ``aggregate`` node as pure synthesis over
            ``slice_results`` + ``slice_failures``. Consumed by T05
            (strict-review gate) and T06 (apply node).

    ``slice`` is deliberately **not** declared on the parent state — it
    lives only on :class:`SliceBranchState`. LangGraph propagates
    sub-graph keys back to the parent only when the parent declares the
    same channel; leaving ``slice`` off the parent keeps each branch's
    per-Send ``slice`` payload from colliding with sibling branches'
    ``slice`` writes when N branches complete (``InvalidUpdateError``).

    Retry-taxonomy reducers (T02, retained): ``last_exception`` /
    ``_retry_counts`` / ``_non_retryable_failures`` carry reducers
    that are no-ops for the sequential planner sub-graph but make the
    parallel fan-out survive LangGraph's concurrent-write guard
    (:class:`InvalidUpdateError` — ``Can receive only one value per
    step``). Without these reducers, every parallel branch's
    success-path ``{"last_exception": None}`` clear (from
    :func:`tiered_node`) would collide at the reduction step.
    """

    run_id: str
    input: PlannerInput
    explorer_output: str
    explorer_output_revision_hint: Any
    explorer_report: ExplorerReport
    planner_output: str
    planner_output_revision_hint: Any
    plan: PlannerPlan
    gate_plan_review_response: str
    gate_slice_refactor_review_response: str
    last_exception: Annotated[Any, _merge_last_exception]
    _retry_counts: Annotated[dict[str, int], _merge_retry_counts]
    _non_retryable_failures: Annotated[int, _merge_non_retryable_failures]
    slice_list: list[SliceSpec]
    slice_results: Annotated[list[SliceResult], operator.add]
    slice_failures: Annotated[list[SliceFailure], operator.add]
    aggregate: SliceAggregate
    applied_artifact_count: int
    hard_stop_failing_slice_ids: list[str]
    _mid_run_tier_overrides: Annotated[
        dict[str, str], _merge_mid_run_tier_overrides
    ]
    _ollama_fallback_fired: Annotated[bool, _merge_ollama_fallback_fired]
    _ollama_fallback_reason: str
    _ollama_fallback_count: int
    ollama_fallback_decision: FallbackChoice
    gate_ollama_fallback_response: str
    ollama_fallback_aborted: bool
    _circuit_open_slice_ids: Annotated[list[str], operator.add]


class SliceBranchState(TypedDict, total=False):
    """State carried through the per-slice sub-graph (T03).

    Each :class:`Send` invocation of the ``slice_branch`` sub-graph sees
    its own copy of this state — the Send payload seeds ``run_id`` and
    ``slice``, the worker writes ``slice_worker_output``, the validator
    reads that and writes ``slice_results: [parsed]``, and the
    ``retrying_edge`` routes on the three-bucket retry slots. When the
    sub-graph returns, only keys **also declared on**
    :class:`SliceRefactorState` propagate to the parent — that is how
    the parent graph's ``slice_results`` reducer receives one
    single-item list per branch while the scalar
    ``slice_worker_output`` / ``slice_worker_output_revision_hint``
    stay local to the branch (not exposed to the parent's
    concurrent-write guard).

    The retry-taxonomy slots are declared scalar (no reducers) because
    within a single sub-graph branch there is no parallelism —
    ``last_exception`` is written by one node at a time. The parent
    state's reducers still apply at the cross-branch reduction step.

    ``run_id`` is deliberately **not** declared on this state.
    :class:`TieredNode` reads run_id from ``config["configurable"]``
    (set by :mod:`ai_workflows.workflows._dispatch` at the ``ainvoke``
    boundary), and LangGraph propagates the :class:`RunnableConfig`
    into Send-dispatched sub-graph invocations automatically. Declaring
    ``run_id`` on the branch state would re-trigger the concurrent-write
    collision this task is engineered around, because the parent's
    scalar ``run_id`` channel would receive N identical writes at
    fan-in.
    """

    slice: SliceSpec
    slice_worker_output: str
    slice_worker_output_revision_hint: Any
    slice_results: Annotated[list[SliceResult], operator.add]
    slice_failures: Annotated[list[SliceFailure], operator.add]
    last_exception: Any
    _retry_counts: dict[str, int]
    _non_retryable_failures: int
    _ollama_fallback_fired: bool
    _circuit_open_slice_ids: Annotated[list[str], operator.add]
    _mid_run_tier_overrides: dict[str, str]

    # M12 T03 — cascade channels populated when slice_refactor's
    # _AUDIT_CASCADE_ENABLED is True. Per-branch only — parent
    # SliceRefactorState does NOT declare these (Option A locked
    # 2026-04-27; see issue file for round-3 H1 arbitration).
    cascade_role: str  # Literal["author", "auditor", "verdict"] in spirit
    # cascade_transcript inner shape: {"author_attempts": list[str],
    # "auditor_verdicts": list[AuditVerdict]} — per audit_cascade.py:674-677
    cascade_transcript: dict[str, list]
    slice_worker_audit_primary_output: str
    slice_worker_audit_primary_parsed: SliceResult  # branch-local; not propagated up
    slice_worker_audit_primary_output_revision_hint: str | None
    slice_worker_audit_auditor_output: str
    slice_worker_audit_auditor_output_revision_hint: str | None
    slice_worker_audit_audit_verdict: Any
    slice_worker_audit_audit_exhausted_response: str


def _slice_list_normalize(
    state: SliceRefactorState, config: RunnableConfig
) -> dict[str, Any]:
    """Map the planner's :class:`PlannerPlan.steps` 1:1 onto ``slice_list``.

    Pure function — no LLM call, no validator pairing required
    (KDR-004 only applies to LLM nodes). An empty plan is a logic
    error: if the planner approved a plan with zero steps there is
    nothing for downstream workers to do, so the workflow fails
    loud with :class:`NonRetryable` (KDR-006 / T01 AC-4) rather than
    silently producing a no-op ``slice_list``. ``NonRetryable`` is the
    correct bucket because re-running the same planner output with a
    retry hint will not produce more steps — the logic error is in
    reviewer approval of a zero-step plan, upstream of this node.
    """
    plan = state.get("plan")
    if plan is None:
        raise NonRetryable(
            "slice_refactor.slice_list_normalize: planner sub-graph did not "
            "populate state['plan'] — check that the sub-graph completed "
            "through its artifact node"
        )
    steps = plan.steps
    if not steps:
        raise NonRetryable(
            "slice_refactor.slice_list_normalize: planner returned zero "
            "steps; refusing to proceed with an empty slice_list"
        )
    slice_list = [
        SliceSpec(
            id=str(step.index),
            description=step.title,
            acceptance=list(step.actions),
        )
        for step in steps
    ]
    return {"slice_list": slice_list}


def _slice_worker_prompt(
    state: SliceRefactorState,
) -> tuple[str, list[dict[str, str]]]:
    """Build the worker's ``(system, messages)`` prompt from the per-Send state.

    Reads ``state["slice"]`` — the single :class:`SliceSpec` LangGraph
    sent to this invocation via the fan-out conditional edge. The
    worker is expected to produce a JSON object matching
    :class:`SliceResult`; the paired validator (T03) parses the result
    and writes the structured model into ``slice_results``.
    """
    slice_spec = state["slice"]
    acceptance_bullets = "\n".join(f"- {a}" for a in slice_spec.acceptance)
    system = (
        "You are a refactor worker. Given one slice of a larger refactor, "
        "produce the minimal unified diff that satisfies every acceptance "
        "criterion. Respond as JSON matching the SliceResult schema: "
        '{"slice_id": str, "diff": str, "notes": str}.'
    )
    user = (
        f"Slice id: {slice_spec.id}\n"
        f"Description: {slice_spec.description}\n"
        f"Acceptance criteria:\n{acceptance_bullets}"
    )
    return system, [{"role": "user", "content": user}]


def _format_slice_result_hint(exc: ValidationError) -> str:
    """Turn a :class:`ValidationError` into a prompt-ready revision hint.

    Local duplicate of the formatter in
    :mod:`ai_workflows.graph.validator_node`. Kept bespoke rather than
    imported because the stock helper is underscore-private (internal
    to that module) and exposing it publicly for one downstream caller
    would bloat the graph layer's API surface. The formatter is 12
    lines; duplication is cheaper than the cross-module coupling.
    """
    lines = [
        "Your previous output did not match the SliceResult schema.",
        "Please revise and re-emit valid JSON. Issues:",
    ]
    for err in exc.errors():
        loc = ".".join(str(part) for part in err.get("loc", ())) or "$"
        msg = err.get("msg", "invalid value")
        lines.append(f"- {loc}: {msg}")
    return "\n".join(lines)


async def _slice_worker_validator(
    state: SliceBranchState,
) -> dict[str, Any]:
    """Validate the slice-worker's raw output into a :class:`SliceResult`.

    Mirrors :func:`ai_workflows.graph.validator_node.validator_node`'s
    contract — raises :class:`RetryableSemantic` with a revision hint
    on any :class:`pydantic.ValidationError` so the paired
    :func:`retrying_edge` can self-loop back to ``slice_worker``
    (KDR-004). Differs in two shape details:

    1. Writes into the reducer-backed ``slice_results`` channel as a
       one-element list (not into a scalar ``output_key``) so each
       branch contributes exactly one entry that the parent graph's
       ``operator.add`` reducer concatenates at fan-in.
    2. Escalates :class:`RetryableSemantic` → :class:`NonRetryable`
       once the per-branch semantic-attempt counter has already been
       bumped ``policy.max_semantic_attempts - 1`` times — i.e. this
       validator call is the final allowed attempt and it failed. The
       escalation is in the validator (not the retrying_edge) because
       the stock :func:`retrying_edge` budget check keys off the
       ``on_semantic`` *routing target* (``slice_worker``), while
       :func:`wrap_with_error_handler` bumps the counter under the
       failing node's name (``slice_worker_validator``). The T03 spec
       calls for explicit ``NonRetryable`` emission on exhaustion so
       T07's hard-stop logic can observe the classified bucket.

    Upstream-failure passthrough: if ``slice_worker_output`` is absent
    (upstream worker raised :class:`NonRetryable` so tiered_node never
    wrote the output key), the validator is a no-op — the branch's
    ``last_exception`` already carries the upstream failure, and
    :func:`retrying_edge` will route terminal on the next hop.

    The stock ``validator_node`` factory is not reused here because its
    fixed ``{output_key: parsed}`` shape would write a single
    :class:`SliceResult` into ``slice_results``, bypassing the
    ``operator.add`` reducer contract (reducers receive list updates,
    not bare instances). A bespoke shim preserves the raise / revise
    semantics without muddling the stock factory's contract.
    """
    text = state.get("slice_worker_output")
    if text is None:
        return {}
    try:
        parsed = SliceResult.model_validate_json(text)
    except ValidationError as exc:
        retry_counts = state.get("_retry_counts") or {}
        prior_semantic_failures = retry_counts.get(
            "slice_worker_validator", 0
        )
        if prior_semantic_failures >= (
            SLICE_WORKER_RETRY_POLICY.max_semantic_attempts - 1
        ):
            raise NonRetryable(
                "slice_worker_validator: exhausted semantic retry budget "
                f"after {prior_semantic_failures + 1} attempts — last "
                "output still fails SliceResult validation"
            ) from exc
        raise RetryableSemantic(
            reason=(
                "slice_worker_validator: output failed SliceResult validation"
            ),
            revision_hint=_format_slice_result_hint(exc),
        ) from exc
    return {
        "slice_results": [parsed],
        "slice_worker_output_revision_hint": None,
    }


def _slice_branch_finalize(state: SliceBranchState) -> dict[str, Any]:
    """Convert an exhausted-retry branch terminal into a :class:`SliceFailure`
    (T04) or a pending-fallback marker (M8 T04).

    Runs as the sub-graph's final node after the retrying_edge decides
    ``on_terminal``. Three cases:

    * Happy path — ``last_exception`` is ``None`` (the T03 validator's
      success return flowed through without a bucket raise, and the
      worker's ``tiered_node`` success path cleared the slot). Return
      ``{}`` so the branch contributes only its ``slice_results`` entry
      (already accumulated on the branch state via ``operator.add``)
      to the parent's fan-in reducer.
    * :class:`CircuitOpen` on first firing — the Ollama-fallback gate
      has not yet fired (``_ollama_fallback_fired`` is ``False`` or
      unset on this branch). Emit the slice id into
      ``_circuit_open_slice_ids`` so :func:`_route_before_aggregate`
      can route the run to the single per-run ``ollama_fallback``
      gate (M8 T04, architecture.md §8.4). Intentionally **not**
      emitting a :class:`SliceFailure` here: the breaker trip is an
      infrastructure signal, not a slice-level failure — promoting it
      to ``slice_failures`` would double-bump the hard-stop counter
      when the breaker is shared across parallel branches.
    * Exhausted path (all other failures, incl.
      :class:`CircuitOpen` *after* gate fired) —
      ``last_exception`` still holds the classified exception the
      :func:`wrap_with_error_handler` shim wrote on the last failing
      attempt. Emit one :class:`SliceFailure` row into
      ``slice_failures`` so the parent's ``operator.add`` reducer
      appends it. The classification collapses transient exhaustion
      into ``non_retryable`` per :class:`SliceFailure`'s docstring
      (exhaustion is effectively non-retryable). A second
      :class:`CircuitOpen` *after* the operator already chose means
      Ollama is still broken; treating it as a slice failure feeds
      the normal double-failure hard-stop (architecture.md §8.2).

    Why this is a standalone node rather than baked into the validator:
    when the T03 in-validator escalation raises :class:`NonRetryable`,
    :func:`wrap_with_error_handler` catches it before the validator can
    emit an extra state-update dict. A separate terminal node is the
    only hook that runs *after* the error handler has written
    ``last_exception`` and *before* the sub-graph returns to the
    parent — the exact seam where the failure record needs to be
    produced.

    ``slice_id`` is read from the branch's ``slice`` payload (set by the
    :class:`Send` at fan-out time). Defensive ``"unknown"`` fallback
    guards against a hypothetical compiled-graph state leak; the
    fan-out invariant asserts every branch sees a ``slice``.
    """
    exc = state.get("last_exception")
    if exc is None:
        return {}
    slice_spec = state.get("slice")
    slice_id = slice_spec.id if slice_spec is not None else "unknown"
    already_fired = state.get("_ollama_fallback_fired") or False
    if isinstance(exc, CircuitOpen) and not already_fired:
        return {"_circuit_open_slice_ids": [slice_id]}
    # M12 T03 — cascade-exhausted branches: when _AUDIT_CASCADE_ENABLED is True
    # and audit_cascade_node(skip_terminal_gate=True) routes exhaustion to END,
    # the exception in state['last_exception'] at line 935 (the
    # state.get("last_exception") read) is an AuditFailure carrying structured
    # verdict data. Fold it into a SliceFailure with a structured prefix so
    # the parent's M11 gate-context projection distinguishes cascade exhaustion
    # from ordinary worker failures. The isinstance(exc, AuditFailure) check
    # must precede the generic RetryableSemantic branch because AuditFailure
    # is a RetryableSemantic subclass.
    if isinstance(exc, AuditFailure):
        reasons_joined = "; ".join(exc.failure_reasons) if exc.failure_reasons else "(none)"
        suggested = exc.suggested_approach or "(none)"
        audit_count = len(
            (state.get("cascade_transcript") or {}).get("auditor_verdicts") or []
        )
        last_error = (
            f"audit_cascade_exhausted: {audit_count} attempts; "
            f"reasons=[{reasons_joined}]; suggested_approach={suggested}"
        )
        return {
            "slice_failures": [
                SliceFailure(
                    slice_id=slice_id,
                    last_error=last_error,
                    failure_bucket="retryable_semantic",
                )
            ]
        }
    # The else branch covers NonRetryable (the T03 escalation pattern),
    # exhausted RetryableTransient (further retries are impossible, so
    # the effect matches non_retryable), any unclassified exception
    # that slipped through the three-bucket taxonomy, and CircuitOpen
    # that re-trips after the operator has already chosen on the
    # ollama_fallback gate (we treat the re-trip as a real slice
    # failure feeding the §8.2 double-failure hard-stop).
    bucket: Literal["retryable_semantic", "non_retryable"] = (
        "retryable_semantic"
        if isinstance(exc, RetryableSemantic)
        else "non_retryable"
    )
    return {
        "slice_failures": [
            SliceFailure(
                slice_id=slice_id,
                last_error=str(exc),
                failure_bucket=bucket,
            )
        ]
    }


def _build_slice_branch_subgraph() -> Any:
    """Return the compiled per-slice ``slice_branch`` sub-graph (T03 + T04).

    Shape at T04 scope::

        START → slice_worker → slice_worker_validator
                     ↑_____________________|         │
                     (on_semantic / on_transient)    ↓
                                       slice_branch_finalize → END

    - ``slice_worker`` is a plain :func:`tiered_node` (no inline parse;
      KDR-004 pairing restored from the T02 shortcut). Wrapped in
      :func:`wrap_with_error_handler` so raised
      :class:`RetryableTransient` / :class:`NonRetryable` become the
      state-update dict :func:`retrying_edge` reads (KDR-006).
    - ``slice_worker_validator`` parses the worker's output; on any
      :class:`ValidationError` it raises :class:`RetryableSemantic`
      which :func:`wrap_with_error_handler` surfaces as a
      ``last_exception`` write; the retrying_edge then routes back to
      ``slice_worker`` for a re-roll.
    - ``slice_branch_finalize`` (T04) converts an exhausted-retry
      branch into a :class:`SliceFailure` row so the parent's
      ``aggregate`` node has the failure record in state (T04 AC).
      Happy-path branches pass through unchanged — the reducer-backed
      ``slice_results`` already carries the validated output.
    - :func:`retrying_edge` fires after each LLM-adjacent node with
      ``on_transient="slice_worker"``, ``on_semantic="slice_worker"``,
      and ``on_terminal="slice_branch_finalize"`` (T04 change from
      ``END``) so an exhausted semantic or transient budget still
      flows through the finalize node on its way to END.

    Compiled without a checkpointer per KDR-009 — the parent's
    :class:`AsyncSqliteSaver` is shared at run time by LangGraph so
    Send-branch state rides the same durable store as the parent.

    M12 T03: when ``_AUDIT_CASCADE_ENABLED`` is True, the plain
    ``slice_worker`` node is replaced by an ``audit_cascade_node(...)``
    compiled cascade sub-graph with ``skip_terminal_gate=True`` (T08 —
    branch-local exhaustion folds into :class:`SliceFailure` via
    :func:`_slice_branch_finalize` without triggering N parallel operator
    interrupts). See ``slice_refactor.py`` module docstring §Quality knobs.
    """
    policy = SLICE_WORKER_RETRY_POLICY

    g: StateGraph = StateGraph(SliceBranchState)

    if _AUDIT_CASCADE_ENABLED:
        # Build-time only — do NOT call audit_cascade_node() in a
        # per-slice or per-step inner loop.
        slice_worker_node = audit_cascade_node(
            primary_tier="slice-worker",
            primary_prompt_fn=_slice_worker_prompt,
            primary_output_schema=SliceResult,
            auditor_tier="auditor-sonnet",
            policy=policy,
            name="slice_worker_audit",
            skip_terminal_gate=True,  # T08 — branch-local exhaustion folds into SliceFailure
        )

        # The cascade sub-graph writes results into slice_worker_audit_primary_parsed
        # and failures into last_exception. The slice_branch_finalize node handles
        # both the happy path (cascade-passed: slice_worker_audit_primary_parsed has
        # the SliceResult) and the exhausted path (AuditFailure in last_exception).
        def _cascade_to_slice_results(state: SliceBranchState) -> dict[str, Any]:
            """Bridge cascade output to the slice_results key expected by the parent.

            Reads ``slice_worker_audit_primary_parsed`` written by the cascade on
            the success path and folds it into the reducer-backed ``slice_results``
            channel so the parent's ``operator.add`` reducer accumulates it.
            On the failure path (AuditFailure in last_exception) this node
            returns ``{}`` — the finalize node handles the failure record.
            """
            exc = state.get("last_exception")
            if exc is not None:
                # Failure path — finalize handles it.
                return {}
            parsed = state.get("slice_worker_audit_primary_parsed")
            if parsed is not None:
                return {"slice_results": [parsed]}
            return {}

        g.add_node("slice_worker", slice_worker_node)
        g.add_node("cascade_bridge", _cascade_to_slice_results)
        g.add_node("slice_branch_finalize", _slice_branch_finalize)

        g.add_edge(START, "slice_worker")
        g.add_edge("slice_worker", "cascade_bridge")
        g.add_edge("cascade_bridge", "slice_branch_finalize")
        g.add_edge("slice_branch_finalize", END)
    else:
        # Standard M11 path.
        worker = wrap_with_error_handler(
            tiered_node(
                tier="slice-worker",
                prompt_fn=_slice_worker_prompt,
                output_schema=SliceResult,
                node_name="slice_worker",
            ),
            node_name="slice_worker",
        )
        validator = wrap_with_error_handler(
            _slice_worker_validator,
            node_name="slice_worker_validator",
        )

        decide_after_worker = retrying_edge(
            on_transient="slice_worker",
            on_semantic="slice_worker",
            on_terminal="slice_worker_validator",
            policy=policy,
        )
        decide_after_validator = retrying_edge(
            on_transient="slice_worker",
            on_semantic="slice_worker",
            on_terminal="slice_branch_finalize",
            policy=policy,
        )

        g.add_node("slice_worker", worker)
        g.add_node("slice_worker_validator", validator)
        g.add_node("slice_branch_finalize", _slice_branch_finalize)

        g.add_edge(START, "slice_worker")
        g.add_conditional_edges(
            "slice_worker",
            decide_after_worker,
            ["slice_worker", "slice_worker_validator"],
        )
        g.add_conditional_edges(
            "slice_worker_validator",
            decide_after_validator,
            ["slice_worker", "slice_branch_finalize"],
        )
        g.add_edge("slice_branch_finalize", END)
    return g.compile()


def _fan_out_to_workers(state: SliceRefactorState) -> list[Send]:
    """Return one :class:`Send` per :class:`SliceSpec` in ``slice_list``.

    LangGraph's ``Send`` API invokes the target node once per entry
    with the per-Send payload as its state view. Each payload carries
    the ``run_id`` (so the :class:`TieredNode`'s structured log + cost
    record stamp the parent run id) and the single ``slice`` the
    invocation is working on. ``slice_results`` is an ``operator.add``
    reducer on the outer state so the fan-in merges every branch's
    output into one list without a hand-rolled merge node.

    T03 repoints the Send target from ``slice_worker`` (T02's compound
    node) to ``slice_branch`` (the new per-slice sub-graph that does
    worker → validator with retry). The payload carries only ``slice``
    — ``run_id`` flows into the sub-graph via the shared
    :class:`RunnableConfig`'s ``configurable`` dict, which
    :class:`TieredNode` reads directly; carrying it on the state would
    trip :class:`InvalidUpdateError` at fan-in (N identical writes to
    a scalar parent channel).
    """
    slices = state.get("slice_list") or []
    return [Send("slice_branch", {"slice": s}) for s in slices]


def _aggregate(state: SliceRefactorState) -> dict[str, Any]:
    """Build the :class:`SliceAggregate` from fanned-in branch outputs (T04).

    Pure synthesis — no LLM call, no validator pairing (KDR-004 does
    not apply without an LLM). Reads:

    * ``slice_results`` — the reducer-accumulated list of validated
      per-slice :class:`SliceResult` rows (one per branch that landed
      its happy path via the T03 validator).
    * ``slice_failures`` — the reducer-accumulated list of
      :class:`SliceFailure` rows (one per branch the T04
      ``slice_branch_finalize`` node emitted because the branch's
      retry budget exhausted).

    Both lists are concatenated in LangGraph's fan-in order; the
    aggregator preserves that order without re-sorting. ``total_slices``
    is computed from both list lengths so downstream consumers (T05
    strict-review gate, T06 apply node, T07 hard-stop check) never
    have to re-derive it from the originating ``slice_list``.

    At T04 scope the aggregator always runs — the double-failure
    hard-stop (``_non_retryable_failures >= 2`` short-circuits to a
    terminal abort, architecture.md §8.2) is [T07]'s wiring, not
    T04's. T04 faithfully captures partial state so T07 has something
    to route on.
    """
    successes: list[SliceResult] = list(state.get("slice_results") or [])
    failures: list[SliceFailure] = list(state.get("slice_failures") or [])
    return {
        "aggregate": SliceAggregate(
            succeeded=successes,
            failed=failures,
            total_slices=len(successes) + len(failures),
        )
    }


def _render_review_prompt(state: SliceRefactorState) -> str:
    """Format :class:`SliceAggregate` into a terse, reviewable prompt (T05).

    Pure function — no LLM call, no validator pairing. Lists failures
    first (so the reviewer sees the most load-bearing signal at the top)
    with ``last_error`` inline, then successes with a short notes
    excerpt. One line per slice. Falls back to a minimal header when
    ``state['aggregate']`` is absent (defensive — the conditional edge
    upstream should guarantee the aggregate ran, but test paths that
    feed the gate directly should not crash the formatter).
    """
    aggregate = state.get("aggregate")
    if aggregate is None:
        return (
            "Review slice-refactor output (no aggregate available — "
            "upstream state missing)."
        )
    lines = [
        f"Review slice-refactor output — {aggregate.total_slices} slices "
        f"({len(aggregate.succeeded)} succeeded, "
        f"{len(aggregate.failed)} failed).",
    ]
    if aggregate.failed:
        lines.append("Failures:")
        for failure in aggregate.failed:
            lines.append(
                f"- slice {failure.slice_id} [{failure.failure_bucket}]: "
                f"{failure.last_error}"
            )
    if aggregate.succeeded:
        lines.append("Successes:")
        for success in aggregate.succeeded:
            notes_excerpt = success.notes.splitlines()[0] if success.notes else ""
            lines.append(f"- slice {success.slice_id}: {notes_excerpt}")
    lines.append("Approve to apply, reject to abort without artefacts.")
    return "\n".join(lines)


def _route_on_gate_response(state: SliceRefactorState) -> str:
    """Route the strict-review gate on the resumed response (T05).

    Returns ``"apply"`` when the reviewer approved, ``"END"`` when they
    rejected. Any other value (missing, unrecognised) raises
    :class:`NonRetryable` — callers that go through the MCP / CLI resume
    path cannot produce this state, so surfacing the contract violation
    loud protects against a future caller bypassing the resume surface.

    Reads ``state["gate_slice_refactor_review_response"]`` — the key
    :class:`human_gate` writes after the interrupt resumes
    (``f"gate_{gate_id}_response"`` with ``gate_id="slice_refactor_review"``).
    """
    response = state.get("gate_slice_refactor_review_response")
    if response == "approved":
        return "apply"
    if response == "rejected":
        return "END"
    raise NonRetryable(
        "slice_refactor_review: gate response must be 'approved' or "
        f"'rejected'; got {response!r}. Callers must use the MCP / CLI "
        "resume surface to supply a valid response."
    )


def _route_before_aggregate(state: SliceRefactorState) -> str:
    """Conditional-edge router: hard-stop vs. Ollama fallback vs. aggregate
    (T07, extended M8 T04).

    Pure ``(state) -> str``. Three branches, checked in order:

    1. ``"hard_stop"`` when the count of :class:`SliceFailure` rows
       accumulated in ``state["slice_failures"]`` reaches
       :data:`HARD_STOP_FAILURE_THRESHOLD` (==2). Reads the list length
       — not ``state["_non_retryable_failures"]`` — because the ``max``
       reducer on that counter undercounts parallel writes to ``1``
       (see :func:`_merge_non_retryable_failures`). The
       ``slice_failures`` list is ``operator.add``-reduced so its
       length is the exact cross-branch failure count at fan-in.
    2. ``"ollama_fallback_stamp"`` when one or more branches hit
       :class:`CircuitOpen` on this run *and* the per-run
       :data:`_ollama_fallback_fired` flag has not yet flipped.
       Routes into the M8 T04 fallback gate (architecture.md §8.4).
       Hard-stop is checked first: a run that has already accumulated
       two real :class:`SliceFailure` rows aborts regardless of
       pending :class:`CircuitOpen` branches (the failures are
       independent Ollama-health signals and the spec is explicit
       about the two-failure abort).
    3. ``"aggregate"`` otherwise — the normal happy path.

    Re-entry after the gate resumes re-fans only the circuit-open
    branches via :func:`_route_after_fallback_dispatch_slice`; on the
    second pass ``_ollama_fallback_fired`` is ``True`` so the
    circuit-open check short-circuits to ``aggregate`` (the new branch
    outputs have written either :class:`SliceResult` rows or
    :class:`SliceFailure` rows depending on whether the retry /
    fallback succeeded).

    The edge evaluates after all :class:`Send`-dispatched ``slice_branch``
    sub-graphs complete (LangGraph synchronises parent super-steps on
    fan-in). This is the earliest graph-topology moment at which the
    cross-slice failure count is knowable; in-flight mid-run abort is
    reserved for the external ``cancel_run`` path (M6 T02's
    ``_ACTIVE_RUNS`` registry + ``asyncio.Task.cancel``).
    """
    failures = state.get("slice_failures") or []
    if len(failures) >= HARD_STOP_FAILURE_THRESHOLD:
        return "hard_stop"
    circuit_open_ids = state.get("_circuit_open_slice_ids") or []
    already_fired = state.get("_ollama_fallback_fired") or False
    if circuit_open_ids and not already_fired:
        return "ollama_fallback_stamp"
    return "aggregate"


async def _hard_stop(
    state: SliceRefactorState, config: RunnableConfig
) -> dict[str, Any]:
    """Terminal node for the double-failure hard-stop (T07).

    Runs exclusively on the ``_route_before_aggregate`` → ``hard_stop``
    branch. Aggregator, strict-review gate, and :func:`_apply` are
    **skipped** — the run aborts without reviewer involvement or artefact
    persistence (architecture.md §8.2).

    Side effects:

    1. Writes one ``artifacts`` row with ``kind=HARD_STOP_METADATA_ARTIFACT_KIND``
       and a JSON payload ``{"failing_slice_ids": [ids]}``. Reuses
       :meth:`SQLiteStorage.write_artifact` so there is no new Storage
       surface and no migration (same reuse pattern T06 picked). The
       row is upserted, so re-invocation of the same graph on the same
       ``run_id`` is idempotent.
    2. Returns ``{"hard_stop_failing_slice_ids": [ids]}`` — a fresh
       state key :mod:`ai_workflows.workflows._dispatch` reads post-invocation
       to decide the terminal status (``"aborted"``). The dispatch flip
       (``update_run_status(run_id, "aborted", finished_at=...)``)
       lives in dispatch for symmetry with the ``gate_rejected``
       path; keeping the storage surface touchpoints threaded through
       one module makes the run-lifecycle state machine discoverable.

    ``storage`` and ``run_id`` are read from ``config["configurable"]``
    using the same pattern as :func:`_apply`; the ``KeyError`` path
    would surface as :class:`NonRetryable` via the caller (dispatch
    always populates these keys — see
    :func:`ai_workflows.workflows._dispatch._build_cfg`).

    KDR-004 does not apply (no LLM call); KDR-006 retry taxonomy: this
    is a terminal node for the non-retryable escalation branch, not a
    retry target. KDR-009: artefacts go to Storage, not LangGraph's
    checkpointer.
    """
    run_id = config["configurable"]["thread_id"]
    storage = config["configurable"]["storage"]
    failures = state.get("slice_failures") or []
    failing_ids = [failure.slice_id for failure in failures]
    payload = json.dumps({"failing_slice_ids": failing_ids})
    await storage.write_artifact(
        run_id,
        HARD_STOP_METADATA_ARTIFACT_KIND,
        payload,
    )
    return {"hard_stop_failing_slice_ids": failing_ids}


def _stamp_ollama_fallback_ctx_slice(
    state: SliceRefactorState,
) -> dict[str, Any]:
    """Render the Ollama-fallback gate's prompt context from ``last_exception``
    (M8 T04, slice_refactor).

    Runs on the ``_route_before_aggregate`` → ``ollama_fallback_stamp``
    branch immediately before the strict-review gate. Reads the
    :class:`CircuitOpen` exception the upstream
    :func:`wrap_with_error_handler` captured into
    ``state['last_exception']`` (the per-branch finalize did not clear
    it; the ``_merge_last_exception`` reducer keeps the non-``None``
    value at fan-in) and writes:

    * ``_ollama_fallback_reason`` — mirrors
      :attr:`CircuitOpen.last_reason` so the gate prompt rendered by
      :func:`render_ollama_fallback_prompt` can name the exact breaker
      trip cause.
    * ``_ollama_fallback_count`` — monotonically increments. A second
      trip in the same run would be short-circuited by
      ``_ollama_fallback_fired`` on :func:`_route_before_aggregate`, so
      the count is primarily a diagnostic signal (recorded in the
      ``gate_prompts`` table payload).

    Pure synthesis — no LLM call, no validator pairing (KDR-004 n/a).
    The fallback pair (:data:`SLICE_REFACTOR_OLLAMA_FALLBACK`) is
    workflow-scoped, so the stamp is workflow-local; the gate factory
    itself stays reusable across planner + slice_refactor.
    """
    exc = state.get("last_exception")
    reason = exc.last_reason if isinstance(exc, CircuitOpen) else ""
    count = (state.get("_ollama_fallback_count") or 0) + 1
    return {
        "_ollama_fallback_reason": reason,
        "_ollama_fallback_count": count,
    }


def _ollama_fallback_dispatch_slice(
    state: SliceRefactorState,
) -> dict[str, Any]:
    """Consume the operator's :class:`FallbackChoice` and stamp run-scoped
    state (M8 T04, slice_refactor).

    Runs after the per-run Ollama-fallback gate resumes. Three
    responsibilities mirror the planner's
    :func:`ai_workflows.workflows.planner._ollama_fallback_dispatch`:

    1. **Mark the gate as fired** (``_ollama_fallback_fired=True``) so
       :func:`_route_before_aggregate` short-circuits to ``aggregate``
       on the re-fan's fan-in (a second :class:`CircuitOpen` on the
       same run now falls through to :class:`SliceFailure` via
       :func:`_slice_branch_finalize`'s second branch, feeding the
       §8.2 double-failure hard-stop).
    2. **Clear the retry-taxonomy slots** (``last_exception=None``,
       ``_retry_counts={}``) so the re-fanned branches start with a
       clean transient budget. The ``_merge_last_exception`` reducer
       keeps the latest non-``None`` value — writing ``None`` here is
       idempotent (leaves any future non-``None`` write untouched) but
       more importantly lets the re-fanned branches overwrite cleanly
       if they hit a fresh transient failure.
    3. **Stamp the mid-run tier override** on
       :attr:`FallbackChoice.FALLBACK` so
       :func:`ai_workflows.graph.tiered_node._resolve_tier` swaps
       :data:`SLICE_REFACTOR_OLLAMA_FALLBACK.logical` for
       :attr:`OllamaFallback.fallback_tier` on every subsequent
       :func:`tiered_node` invocation in this run. Applies to *all*
       re-fanned branches because the override lives on the parent
       state and is propagated into each :class:`Send` payload by
       :func:`_route_after_fallback_dispatch_slice`.

    ABORT is routed by :func:`_route_after_fallback_dispatch_slice`
    without additional state writes — the conditional edge sees
    :attr:`FallbackChoice.ABORT` and directs to
    :func:`_slice_refactor_ollama_abort`.
    """
    decision = state.get(FALLBACK_DECISION_STATE_KEY)
    updates: dict[str, Any] = {
        "_ollama_fallback_fired": True,
        "last_exception": None,
        "_retry_counts": {},
    }
    if decision is FallbackChoice.FALLBACK:
        overrides = dict(state.get("_mid_run_tier_overrides") or {})
        overrides[SLICE_REFACTOR_OLLAMA_FALLBACK.logical] = (
            SLICE_REFACTOR_OLLAMA_FALLBACK.fallback_tier
        )
        updates["_mid_run_tier_overrides"] = overrides
    return updates


def _route_after_fallback_dispatch_slice(
    state: SliceRefactorState,
) -> str | list[Send]:
    """Conditional-edge router after :func:`_ollama_fallback_dispatch_slice`
    (M8 T04).

    Reads the :class:`FallbackChoice` the gate parsed into
    :data:`FALLBACK_DECISION_STATE_KEY` and dispatches:

    * :attr:`FallbackChoice.ABORT` → ``"slice_refactor_ollama_abort"``
      (terminal; :func:`_slice_refactor_ollama_abort` writes the
      metadata artefact and dispatch flips
      ``runs.status='aborted'``).
    * :attr:`FallbackChoice.RETRY` / :attr:`FallbackChoice.FALLBACK` →
      one :class:`Send` per circuit-open slice, re-dispatched to
      ``slice_branch``. Each payload carries
      ``_ollama_fallback_fired=True`` so the re-fanned branch's
      :func:`_slice_branch_finalize` promotes any second
      :class:`CircuitOpen` to :class:`SliceFailure` instead of
      re-adding to ``_circuit_open_slice_ids`` (the fan-out would
      otherwise bounce between gate and branches forever).

    RETRY vs. FALLBACK differ only in state stamping
    (:func:`_ollama_fallback_dispatch_slice` writes
    ``_mid_run_tier_overrides`` only on FALLBACK). The Send-fan below
    is identical for both — on FALLBACK, :func:`tiered_node` resolves
    each branch's ``slice-worker`` tier through the override to Opus;
    on RETRY the tier stays Ollama (the breaker is still OPEN but
    its half-open probe gives the retry a chance).

    **Defensive fallback.** When ``_circuit_open_slice_ids`` is empty
    (not reachable under the normal contract — the upstream router
    only directs here when the list is non-empty) the router returns
    ``"slice_refactor_ollama_abort"`` so the run terminates cleanly
    rather than emitting an empty Send list (LangGraph treats that as
    an unroutable edge).
    """
    decision = state.get(FALLBACK_DECISION_STATE_KEY)
    if decision is FallbackChoice.ABORT:
        return "slice_refactor_ollama_abort"
    slice_list = state.get("slice_list") or []
    slice_by_id = {s.id: s for s in slice_list}
    circuit_ids = state.get("_circuit_open_slice_ids") or []
    overrides = state.get("_mid_run_tier_overrides") or {}
    seen: set[str] = set()
    sends: list[Send] = []
    for sid in circuit_ids:
        if sid in seen:
            continue
        seen.add(sid)
        spec = slice_by_id.get(sid)
        if spec is not None:
            payload: dict[str, Any] = {
                "slice": spec,
                "_ollama_fallback_fired": True,
            }
            # Propagate the mid-run tier override into the sub-graph's
            # state so ``TieredNode._resolve_tier`` sees it. The parent
            # graph's `_mid_run_tier_overrides` channel only reaches the
            # sub-graph via the Send payload (LangGraph Sends start the
            # sub-graph with an explicit state view).
            if overrides:
                payload["_mid_run_tier_overrides"] = dict(overrides)
            sends.append(Send("slice_branch", payload))
    if not sends:
        return "slice_refactor_ollama_abort"
    return sends


async def _slice_refactor_ollama_abort(
    state: SliceRefactorState, config: RunnableConfig
) -> dict[str, Any]:
    """Terminal node for the Ollama-fallback ABORT branch (M8 T04, slice_refactor).

    Runs exclusively on the :attr:`FallbackChoice.ABORT` branch of
    :func:`_route_after_fallback_dispatch_slice`. Writes a
    :data:`HARD_STOP_METADATA_ARTIFACT_KIND` artefact via
    :meth:`SQLiteStorage.write_artifact` so the post-mortem surface can
    read why the run aborted without re-running the graph, then returns
    ``{"ollama_fallback_aborted": True}`` which
    :mod:`ai_workflows.workflows._dispatch` reads as the terminal
    signal to flip ``runs.status='aborted'``.

    Distinct from :func:`_hard_stop` (which writes ``failing_slice_ids``
    for the double-failure path): this node's metadata names the
    tripped tier and the operator's ABORT choice, not a per-slice
    failure list. Reusing the same ``hard_stop_metadata`` artefact
    ``kind`` keeps the cross-workflow schema uniform.
    """
    run_id = config["configurable"]["thread_id"]
    storage = config["configurable"]["storage"]
    circuit_ids = state.get("_circuit_open_slice_ids") or []
    payload = json.dumps(
        {
            "reason": "ollama_fallback_abort",
            "tier": SLICE_REFACTOR_OLLAMA_FALLBACK.logical,
            "circuit_open_slice_ids": list(dict.fromkeys(circuit_ids)),
        }
    )
    await storage.write_artifact(
        run_id,
        HARD_STOP_METADATA_ARTIFACT_KIND,
        payload,
    )
    return {"ollama_fallback_aborted": True}


async def _apply(
    state: SliceRefactorState, config: RunnableConfig
) -> dict[str, int]:
    """Persist each succeeded :class:`SliceResult` as a row in ``artifacts`` (T06).

    Terminal node on the approve branch of the strict-review gate. For
    every entry in ``state["aggregate"].succeeded``, writes one
    ``artifacts`` row via :meth:`SQLiteStorage.write_artifact` keyed by
    ``kind=f"{SLICE_RESULT_ARTIFACT_KIND}:{slice_id}"`` — the embedded
    ``slice_id`` gives the ``(run_id, slice_id)`` unique constraint the
    T06 idempotency AC asks for, without changing the helper's signature
    or adding a schema migration. Payload is :meth:`SliceResult.model_dump_json`
    so a caller can round-trip the row back into a :class:`SliceResult`
    via :meth:`SliceResult.model_validate_json` (pinned by the payload-shape
    test).

    Failed slices are **not** written — their audit trail lives in the
    gate-response row (:meth:`Storage.get_gate`, which carries the prompt
    the reviewer saw) and in the runtime log. The milestone README
    explicitly scopes applying to a real repo (subprocess / ``git apply``)
    as post-M6; this node is a Storage-layer commit only.

    Returns ``{"applied_artifact_count": <int>}`` so
    :mod:`ai_workflows.workflows._dispatch` can detect completion via the
    module-level :data:`FINAL_STATE_KEY` constant
    (``T01-CARRY-DISPATCH-COMPLETE`` resolution). ``0`` is a valid return
    value (a run where every slice failed but the reviewer approved
    anyway, e.g. to record the audit trail).

    KDR-004 does not apply (no LLM call); KDR-009 honoured (artefacts go
    to Storage, not LangGraph's checkpointer).
    """
    run_id = config["configurable"]["thread_id"]
    storage = config["configurable"]["storage"]
    aggregate = state.get("aggregate")
    if aggregate is None:
        raise NonRetryable(
            "slice_refactor.apply: state['aggregate'] missing — the T04 "
            "aggregator node must run before the apply terminal. Check "
            "the compiled graph edges."
        )
    count = 0
    for result in aggregate.succeeded:
        await storage.write_artifact(
            run_id,
            f"{SLICE_RESULT_ARTIFACT_KIND}:{result.slice_id}",
            result.model_dump_json(),
        )
        count += 1
    return {"applied_artifact_count": count}


def build_slice_refactor() -> StateGraph:
    """Return the uncompiled ``slice_refactor`` :class:`StateGraph`.

    Graph shape at T07 scope::

        START → planner_subgraph → slice_list_normalize
              → (Send fan-out) slice_branch (N parallel compiled sub-graphs)
              → _route_before_aggregate ─── hard_stop → END     (≥2 failures)
                                         └─ aggregate → slice_refactor_review
                                                         ├── "approved" → apply → END
                                                         └── "rejected" → END

    Each ``slice_branch`` Send dispatches into a compiled per-slice
    sub-graph (:func:`_build_slice_branch_subgraph`) that runs
    ``slice_worker`` → ``slice_worker_validator`` with a
    :func:`retrying_edge` self-loop for KDR-004 validator pairing and
    KDR-006 three-bucket retry routing. Fan-in uses the ``operator.add``
    reducer on the ``slice_results`` state key; no hand-rolled merge
    node. The caller compiles this builder with the shared
    ``AsyncSqliteSaver`` from :mod:`ai_workflows.graph.checkpointer`
    and invokes it with ``durability="sync"`` (threaded through by
    :mod:`ai_workflows.workflows._dispatch`); the planner sub-graph
    and each ``slice_branch`` share the parent's checkpointer at run
    time per KDR-009.

    T05 adds the strict-review ``HumanGate`` (architecture.md §8.3)
    between ``aggregate`` and the ``apply`` terminal. Reject routes
    straight to ``END`` — the `gate_rejected` terminal status is
    stamped by :mod:`ai_workflows.workflows._dispatch` when it reads
    the gate response off the resumed state. T06 lands the real
    :func:`_apply` body — one ``artifacts`` row per succeeded
    :class:`SliceResult` via :meth:`SQLiteStorage.write_artifact`,
    with :data:`FINAL_STATE_KEY` = ``"applied_artifact_count"`` so
    dispatch can flip ``runs.status = completed`` on approve.

    T07 inserts :func:`_route_before_aggregate` between the fan-in of
    ``slice_branch`` and ``aggregate``: when
    ``len(state["slice_failures"]) >= 2`` the graph routes directly
    to :func:`_hard_stop`, bypassing aggregator + gate + apply
    (architecture.md §8.2). Dispatch reads
    ``state["hard_stop_failing_slice_ids"]`` post-invocation and flips
    ``runs.status = "aborted"`` with ``finished_at``.
    """
    planner_subgraph = build_planner().compile()
    slice_branch = _build_slice_branch_subgraph()
    review_gate = human_gate(
        gate_id=TERMINAL_GATE_ID,
        prompt_fn=_render_review_prompt,
        strict_review=True,
    )
    ollama_fallback = build_ollama_fallback_gate(
        tier_name=SLICE_REFACTOR_OLLAMA_FALLBACK.logical,
        fallback_tier=SLICE_REFACTOR_OLLAMA_FALLBACK.fallback_tier,
    )

    g: StateGraph = StateGraph(SliceRefactorState)
    g.add_node("planner_subgraph", planner_subgraph)
    g.add_node("slice_list_normalize", _slice_list_normalize)
    g.add_node("slice_branch", slice_branch)
    g.add_node("aggregate", _aggregate)
    g.add_node("hard_stop", _hard_stop)
    g.add_node("slice_refactor_review", review_gate)
    g.add_node("apply", _apply)
    # M8 T04: Ollama-fallback gate lives *per run*, not per branch.
    # Architecture.md §8.4: "pause the run" — one interrupt, one gate
    # record, one operator choice applied to every remaining branch.
    # The single-gate shape is enforced by `_route_before_aggregate`
    # (only routes here once `_ollama_fallback_fired` is False) and
    # `_ollama_fallback_dispatch_slice` (flips the flag on the way out,
    # so re-fanned branches that trip a second time flow into
    # SliceFailure / hard_stop instead of bouncing back to the gate).
    g.add_node("ollama_fallback_stamp", _stamp_ollama_fallback_ctx_slice)
    g.add_node("ollama_fallback", ollama_fallback)
    g.add_node("ollama_fallback_dispatch", _ollama_fallback_dispatch_slice)
    g.add_node("slice_refactor_ollama_abort", _slice_refactor_ollama_abort)

    g.add_edge(START, "planner_subgraph")
    g.add_edge("planner_subgraph", "slice_list_normalize")
    g.add_conditional_edges(
        "slice_list_normalize",
        _fan_out_to_workers,
        ["slice_branch"],
    )
    g.add_conditional_edges(
        "slice_branch",
        _route_before_aggregate,
        {
            "aggregate": "aggregate",
            "hard_stop": "hard_stop",
            "ollama_fallback_stamp": "ollama_fallback_stamp",
        },
    )
    g.add_edge("hard_stop", END)
    g.add_edge("aggregate", "slice_refactor_review")
    g.add_conditional_edges(
        "slice_refactor_review",
        _route_on_gate_response,
        {"apply": "apply", "END": END},
    )
    g.add_edge("apply", END)
    g.add_edge("ollama_fallback_stamp", "ollama_fallback")
    g.add_edge("ollama_fallback", "ollama_fallback_dispatch")
    g.add_conditional_edges(
        "ollama_fallback_dispatch",
        _route_after_fallback_dispatch_slice,
        ["slice_branch", "slice_refactor_ollama_abort"],
    )
    g.add_edge("slice_refactor_ollama_abort", END)
    return g


def slice_refactor_tier_registry() -> dict[str, TierConfig]:
    """Return the tier registry for ``slice_refactor``.

    Composes the planner's tiers (``planner-explorer`` /
    ``planner-synth`` / ``auditor-sonnet`` / ``auditor-opus``) with the
    new T02 ``slice-worker`` tier so a single
    :func:`ai_workflows.workflows._dispatch.run_workflow` call can
    resolve every tier both the parent graph *and* the composed
    planner sub-graph call. Dispatch reads the workflow's own registry
    via ``<workflow>_tier_registry()`` — it does not merge a sibling
    workflow's registry implicitly, so the composition has to be
    declared here at the module level.

    The ``auditor-sonnet`` and ``auditor-opus`` entries are inherited
    via the ``dict(planner_tier_registry())`` composition (M12 Task 01
    / ADR-0004); no additional declaration is needed here.

    ``slice-worker`` is routed to local Qwen via Ollama
    (``ollama/qwen2.5-coder:32b``) by default — the same cost-free
    local model the M5 planner-explorer tier uses. KDR-003 spirit:
    this helper never reads API keys; env reads stay at the
    :class:`LiteLLMAdapter` boundary when a provider call actually
    fires. ``max_concurrency=1`` reflects the single-writer constraint
    of the local Ollama daemon — T07 will thread the §8.6
    workflow-wide semaphore on top to cap total concurrent workers
    independently of the per-tier budget. The ``--tier-override``
    surface from M5 T04 / T05 can repoint ``slice-worker`` at any
    other tier in this composed registry (e.g. ``planner-synth`` for
    a Claude-Opus run).
    """
    registry = dict(planner_tier_registry())
    registry["slice-worker"] = TierConfig(
        name="slice-worker",
        route=LiteLLMRoute(
            model="ollama/qwen2.5-coder:32b",
            api_base="http://localhost:11434",
        ),
        max_concurrency=1,
        per_call_timeout_s=180,
    )
    return registry


def slice_refactor_eval_node_schemas() -> dict[str, type[BaseModel]]:
    """Return the eval-capture schema map: ``node_name → output pydantic class``.

    M7 T04 capture helper reads this to stamp :attr:`EvalCase.output_schema_fqn`
    per captured node. ``slice_refactor`` contributes one LLM node
    (``slice_worker`` inside the per-slice sub-graph, emitting
    :class:`SliceResult`). The planner sub-graph composed into this
    workflow has its own registry at
    :func:`ai_workflows.workflows.planner.planner_eval_node_schemas` —
    dispatch does not merge sibling registries, so capture of a
    slice_refactor run walks only the node set this function declares.

    Note: ``slice_worker`` runs inside a LangGraph sub-graph, so the
    top-level :meth:`AsyncSqliteSaver.aget` snapshot that T04's
    ``aiw eval capture`` reads does **not** contain
    ``slice_worker_output`` at the parent thread level. The
    :class:`ai_workflows.evals.CaptureCallback` live-capture path
    (activated via ``AIW_CAPTURE_EVALS``) fires inside every
    :class:`TieredNode` invocation regardless of sub-graph nesting, so
    it is the authoritative capture path for this workflow. This
    function still ties the node name to its pydantic class so
    downstream replay (``aiw eval run slice_refactor``) resolves
    ``output_schema_fqn`` consistently.
    """
    return {"slice_worker": SliceResult}


def initial_state(run_id: str, inputs: dict[str, Any]) -> dict[str, Any]:
    """Convention hook: construct the initial graph state for this workflow.

    Called by :func:`ai_workflows.workflows._dispatch._build_initial_state`
    when the workflow module exposes this symbol (T01 option B in the
    Builder-phase scope review). Returns a dict that includes every
    state key the planner sub-graph reads on entry (``run_id``,
    ``input``) so the sub-graph runs identically to a bare
    ``aiw run planner`` invocation.
    """
    sri = SliceRefactorInput(**inputs)
    planner_input = PlannerInput(
        goal=sri.goal,
        context=sri.context,
        max_steps=sri.max_steps,
    )
    return {
        "run_id": run_id,
        "input": planner_input,
    }


register("slice_refactor", build_slice_refactor)
