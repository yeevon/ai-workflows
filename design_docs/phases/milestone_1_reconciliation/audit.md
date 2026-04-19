# M1 Reconciliation Audit

**Status:** ✅ Produced 2026-04-19 (M1 Task 01).
**Source task:** [task_01_reconciliation_audit.md](task_01_reconciliation_audit.md).
**Grounding:** [architecture.md](../../architecture.md) · [roadmap.md](../../roadmap.md) · [nice_to_have.md](../../nice_to_have.md).

This document is the single reference every remaining M1 task consumes. Every `ai_workflows/` module, every `pyproject.toml` entry, every `tests/` file, and every `migrations/` SQL file is tagged **KEEP**, **MODIFY**, **REMOVE**, **ADD** (new), or **DECIDE** (task 10 outcome), with a reason citing a KDR or an [architecture.md](../../architecture.md) section and a target task that will execute the change.

Verdict legend:

- **KEEP** — no change required. Reason cites the KDR / §N it supports.
- **MODIFY** — survives but is reshaped by a named task.
- **REMOVE** — deleted outright.
- **ADD** — does not exist yet; introduced by [task 02](task_02_dependency_swap.md).
- **DECIDE** — resolved by [task 10](task_10_workflow_hash_decision.md) ADR.

Pure-KEEP rows with no follow-on work use a dash (`—`) in the Target task column, matching AC: "No row has a blank Target task column except for pure-KEEP items with no follow-on work."

---

## 1. File audit (`ai_workflows/`)

| Path | Verdict | Reason | Target task |
| --- | --- | --- | --- |
| `ai_workflows/__init__.py` | MODIFY | Needs `__version__` dunder for `aiw version` ([task 11](task_11_cli_stub_down.md) deliverable); otherwise keeps package init role. | [task 11](task_11_cli_stub_down.md) |
| `ai_workflows/cli.py` | MODIFY | Strip every command whose body imports pydantic-ai; leave `--help` + `version` stubs with `TODO(M3)` pointers per [architecture.md §4.4](../../architecture.md). | [task 11](task_11_cli_stub_down.md) |
| `ai_workflows/components/__init__.py` | REMOVE | `components/` layer is collapsed into `graph/` per [architecture.md §3](../../architecture.md); deleting the empty package also satisfies the four-layer import-linter contract. | [task 12](task_12_import_linter_rewrite.md) |
| `ai_workflows/primitives/__init__.py` | MODIFY | Docstring re-exports `llm` + `tools` subpackages which are being deleted in [task 03](task_03_remove_llm_substrate.md) / [task 04](task_04_remove_tool_registry.md); docstring and any re-exports must be rewritten. | [task 03](task_03_remove_llm_substrate.md) |
| `ai_workflows/primitives/cost.py` | MODIFY | `CostTracker` is preserved per [architecture.md §4.1](../../architecture.md) but its surface shrinks — LiteLLM now supplies per-call base cost (KDR-007); keep `modelUsage` aggregation + budget enforcement only. | [task 08](task_08_prune_cost_tracker.md) |
| `ai_workflows/primitives/logging.py` | MODIFY | `StructuredLogger` is the single observability surface per [architecture.md §8.1](../../architecture.md); sanity-pass to drop any logfire imports and confirm record shape still matches §4.1. | [task 09](task_09_logger_sanity.md) |
| `ai_workflows/primitives/retry.py` | MODIFY | Refit to the three-bucket taxonomy (`RetryableTransient` \| `RetryableSemantic` \| `NonRetryable`) per KDR-006 and [architecture.md §8.2](../../architecture.md); LiteLLM now owns the transient retry layer underneath. | [task 07](task_07_refit_retry_policy.md) |
| `ai_workflows/primitives/storage.py` | MODIFY | Shrink to run registry + gate log only; all checkpoint-adjacent methods move to LangGraph `SqliteSaver` per KDR-009. | [task 05](task_05_trim_storage.md) |
| `ai_workflows/primitives/tiers.py` | MODIFY | Needs LiteLLM model strings and the `claude_code` subprocess spec column per [architecture.md §4.1](../../architecture.md) (KDR-007) — current tier shape predates both. | [task 06](task_06_refit_tier_config.md) |
| `ai_workflows/primitives/workflow_hash.py` | DECIDE | Pre-pivot hash guarded `aiw resume` against directory drift; LangGraph checkpoint keys may cover the same concern (KDR-009). Option A (keep) / Option B (delete) resolved by ADR-0001. | [task 10](task_10_workflow_hash_decision.md) |
| `ai_workflows/primitives/llm/__init__.py` | REMOVE | `llm/` subpackage is the pydantic-ai substrate removal target per KDR-001 / KDR-005; `TieredNode` + LiteLLM adapter land in M2, not here. | [task 03](task_03_remove_llm_substrate.md) |
| `ai_workflows/primitives/llm/caching.py` | REMOVE | pydantic-ai `ModelResponse` caching; no replacement — LiteLLM handles its own retries, and an in-process LLM cache is not part of [architecture.md](../../architecture.md). | [task 03](task_03_remove_llm_substrate.md) |
| `ai_workflows/primitives/llm/model_factory.py` | REMOVE | Builds pydantic-ai `Model` instances; replaced by `TieredNode` + LiteLLM adapter in M2 (KDR-001, KDR-007). | [task 03](task_03_remove_llm_substrate.md) |
| `ai_workflows/primitives/llm/types.py` | REMOVE | Message/response types bespoke to the pydantic-ai loop; LiteLLM supplies the OpenAI-shaped contract used downstream. | [task 03](task_03_remove_llm_substrate.md) |
| `ai_workflows/primitives/tools/__init__.py` | REMOVE | Tool registry is out of scope for the new architecture — LangGraph nodes call providers directly and tool exposure lives at the MCP surface (KDR-002, KDR-008). | [task 04](task_04_remove_tool_registry.md) |
| `ai_workflows/primitives/tools/forensic_logger.py` | REMOVE | Pre-pivot tool-call forensic ledger; observability is `StructuredLogger` only per [architecture.md §8.1](../../architecture.md). | [task 04](task_04_remove_tool_registry.md) |
| `ai_workflows/primitives/tools/fs.py` | REMOVE | Stdlib tool; no consumer under the new architecture. | [task 04](task_04_remove_tool_registry.md) |
| `ai_workflows/primitives/tools/git.py` | REMOVE | Stdlib tool; no consumer under the new architecture. | [task 04](task_04_remove_tool_registry.md) |
| `ai_workflows/primitives/tools/http.py` | REMOVE | Stdlib tool + the only direct `httpx` consumer in `ai_workflows/`; post-removal `httpx` is transitive via LiteLLM only. | [task 04](task_04_remove_tool_registry.md) |
| `ai_workflows/primitives/tools/registry.py` | REMOVE | Tool registry core — no concept in the new architecture. | [task 04](task_04_remove_tool_registry.md) |
| `ai_workflows/primitives/tools/shell.py` | REMOVE | Stdlib tool; no consumer under the new architecture. | [task 04](task_04_remove_tool_registry.md) |
| `ai_workflows/primitives/tools/stdlib.py` | REMOVE | Stdlib tool wiring; no consumer under the new architecture. | [task 04](task_04_remove_tool_registry.md) |
| `ai_workflows/workflows/__init__.py` | KEEP | Empty placeholder for the M2+ `workflows/` layer per [architecture.md §4.3](../../architecture.md); no pydantic-ai imports present. | — |

## 1a. Root-level configuration data

| Path | Verdict | Reason | Target task |
| --- | --- | --- | --- |
| `tiers.yaml` | MODIFY | Needs to express LiteLLM model strings + a `claude_code` subprocess spec per KDR-007 and [architecture.md §4.1](../../architecture.md). | [task 06](task_06_refit_tier_config.md) |
| `pricing.yaml` | MODIFY | LiteLLM now supplies base per-call cost (KDR-007); `pricing.yaml` reduces to only sub-model / override entries that `CostTracker.modelUsage` still needs. | [task 08](task_08_prune_cost_tracker.md) |

---

## 2. Dependency audit (`pyproject.toml`)

### `[project].dependencies`

| Dependency | Verdict | Reason | Target task |
| --- | --- | --- | --- |
| `pydantic-ai>=1.0` | REMOVE | Pydantic-ai substrate is replaced by LangGraph per KDR-001 / KDR-005. | [task 02](task_02_dependency_swap.md) |
| `pydantic-graph>=1.0` | REMOVE | Hand-rolled DAG helper from the pydantic-ai era; LangGraph owns DAGs per KDR-001. | [task 02](task_02_dependency_swap.md) |
| `pydantic-evals>=1.0` | REMOVE | Eval harness is explicitly deferred — M7 re-introduces a fresh one per [roadmap.md](../../roadmap.md); no current consumer. | [task 02](task_02_dependency_swap.md) |
| `logfire>=2.0` | REMOVE | Observability is `StructuredLogger` only per [architecture.md §8.1](../../architecture.md); hosted tracing (Langfuse / LangSmith / OTel) is deferred — [nice_to_have.md](../../nice_to_have.md) §1, §3, §8. Task 02 AC ("`logfire` specifically has a verdict") satisfied. | [task 02](task_02_dependency_swap.md) |
| `anthropic>=0.40` | REMOVE | No Anthropic API per KDR-003; Claude access is OAuth-only via the `claude` CLI subprocess. | [task 02](task_02_dependency_swap.md) |
| `httpx>=0.27` | KEEP | Remains as a transitive for LiteLLM ([architecture.md §6](../../architecture.md)) after `primitives/tools/http.py` is deleted; task_02 explicitly keeps it. | — |
| `pydantic>=2.0` | KEEP | First-class per [architecture.md §6](../../architecture.md); defines MCP tool contracts and node I/O. | — |
| `pyyaml>=6.0` | KEEP | Loads `tiers.yaml` + `pricing.yaml` (KDR-007, [architecture.md §4.1](../../architecture.md)). | — |
| `structlog>=24.0` | KEEP | Underpins `StructuredLogger` per [architecture.md §4.1 / §8.1](../../architecture.md). | — |
| `typer>=0.12` | KEEP | Current `aiw` CLI framework; the CLI-framework swap is parked in [nice_to_have.md §4](../../nice_to_have.md) and not adopted here. (Note: [architecture.md §4.4](../../architecture.md) currently phrases the CLI as "Click-based for now" — stale wording against the Typer reality; correction parked for a future ADR under `design_docs/adr/` per M1-T01-ISS-03.) | — |
| `yoyo-migrations>=9.0` | KEEP | `Storage` migrations (including the reconciliation migration in [task 05](task_05_trim_storage.md)) ride on yoyo; LangGraph's `SqliteSaver` owns its own schema separately (KDR-009). | — |

### `[project.optional-dependencies]`

| Dependency | Verdict | Reason | Target task |
| --- | --- | --- | --- |
| `dag = ["networkx>=3.0"]` | REMOVE | LangGraph replaces every hand-rolled DAG primitive per KDR-001; the extras group has no remaining consumer. | [task 02](task_02_dependency_swap.md) |

### `[dependency-groups].dev`

| Dependency | Verdict | Reason | Target task |
| --- | --- | --- | --- |
| `import-linter>=2.0` | KEEP | Enforces the four-layer contract per [architecture.md §3](../../architecture.md); contracts themselves are rewritten in [task 12](task_12_import_linter_rewrite.md). | [task 12](task_12_import_linter_rewrite.md) |
| `pytest>=8.0` | KEEP | CI gate stack per [architecture.md §6](../../architecture.md); paired with `import-linter` as the enforcement path for the [architecture.md §3](../../architecture.md) four-layer contract. | — |
| `pytest-asyncio>=0.23` | KEEP | Async arm of the same CI gate stack per [architecture.md §6](../../architecture.md); required once LangGraph + LiteLLM nodes land in M2 (both expose async call paths per [architecture.md §4.2](../../architecture.md)). | — |
| `python-dotenv>=1.0` | KEEP | Loads `.env` at the provider-driver boundary per [architecture.md §7](../../architecture.md) "Secrets are read from environment at the provider driver boundary" — covers `GEMINI_API_KEY` (KDR-007) and the Ollama / `claude` CLI probes from [architecture.md §8.4](../../architecture.md). | — |
| `ruff>=0.5` | KEEP | Lint arm of the CI gate stack per [architecture.md §6](../../architecture.md); paired with `import-linter` for layer enforcement and with `pytest` for behaviour checks. | — |

### New dependencies to add (task 02)

| Dependency | Verdict | Reason | Target task |
| --- | --- | --- | --- |
| `langgraph>=0.2` | ADD | DAG + checkpoint + interrupt substrate per KDR-001 / [architecture.md §6](../../architecture.md). | [task 02](task_02_dependency_swap.md) |
| `langgraph-checkpoint-sqlite>=1.0` | ADD | `SqliteSaver` is the only checkpoint implementation per KDR-009. | [task 02](task_02_dependency_swap.md) |
| `litellm>=1.40` | ADD | Unified Gemini + Qwen/Ollama adapter per KDR-007. | [task 02](task_02_dependency_swap.md) |
| `fastmcp>=0.2` | ADD | MCP server ergonomics per KDR-008 / [architecture.md §4.4](../../architecture.md). | [task 02](task_02_dependency_swap.md) |

Also updated in task 02: `project.description` drops the pydantic-ai reference ("`Composable AI workflow framework built on LangGraph + MCP.`").

---

## 3. Test audit (`tests/`)

| Path | Verdict | Reason | Target task |
| --- | --- | --- | --- |
| `tests/__init__.py` | KEEP | Root test-tree package marker mirroring the [architecture.md §3](../../architecture.md) layer tree; deletion would break pytest discovery for every `ai_workflows.*` layer below. | — |
| `tests/conftest.py` | KEEP | Shared fixtures hosted at the test-tree root per [architecture.md §3](../../architecture.md); the fixture set covers the primitives layer preserved per KDR-005. Task 03 must verify no pydantic-ai fixture leaks survive `llm/` removal. | [task 03](task_03_remove_llm_substrate.md) |
| `tests/test_cli.py` | MODIFY | Reduce to `aiw --help` + `aiw version` assertions per [task 11](task_11_cli_stub_down.md); drop every test of a removed command. | [task 11](task_11_cli_stub_down.md) |
| `tests/test_scaffolding.py` | MODIFY | Scaffolding smoke test references the pre-pivot dependency set; update to assert on the new substrate deps after task 02. | [task 02](task_02_dependency_swap.md) |
| `tests/primitives/__init__.py` | KEEP | Test-tree package marker mirroring the `primitives/` layer in [architecture.md §3](../../architecture.md); required for pytest to discover the primitives test suite. | — |
| `tests/primitives/test_caching.py` | REMOVE | Covers `primitives/llm/caching.py`, which is deleted in task 03. | [task 03](task_03_remove_llm_substrate.md) |
| `tests/primitives/test_cost.py` | MODIFY | Rewrite around the pruned `CostTracker` surface (KDR-007). | [task 08](task_08_prune_cost_tracker.md) |
| `tests/primitives/test_logging.py` | MODIFY | Update to assert the record shape declared in [architecture.md §8.1](../../architecture.md); drop any logfire assertions. | [task 09](task_09_logger_sanity.md) |
| `tests/primitives/test_model_factory.py` | REMOVE | Covers `primitives/llm/model_factory.py`, which is deleted in task 03. | [task 03](task_03_remove_llm_substrate.md) |
| `tests/primitives/test_retry.py` | MODIFY | Rewrite around the three-bucket taxonomy (KDR-006). | [task 07](task_07_refit_retry_policy.md) |
| `tests/primitives/test_storage.py` | MODIFY | Assert the trimmed run-registry + gate-log protocol (KDR-009); add idempotent-migration test. | [task 05](task_05_trim_storage.md) |
| `tests/primitives/test_tiers_loader.py` | MODIFY | Exercise the reshaped `tiers.yaml` (LiteLLM strings + claude_code subprocess spec). | [task 06](task_06_refit_tier_config.md) |
| `tests/primitives/test_tool_registry.py` | REMOVE | Covers the tool registry, which is removed in task 04. | [task 04](task_04_remove_tool_registry.md) |
| `tests/primitives/test_types.py` | REMOVE | Covers `primitives/llm/types.py`, which is deleted in task 03. | [task 03](task_03_remove_llm_substrate.md) |
| `tests/primitives/test_workflow_hash.py` | DECIDE | Fate tied to the module itself — deleted under task 10 Option B, kept as-is under Option A. | [task 10](task_10_workflow_hash_decision.md) |
| `tests/primitives/tools/__init__.py` | REMOVE | Package marker for a subpackage being removed entirely. | [task 04](task_04_remove_tool_registry.md) |
| `tests/primitives/tools/conftest.py` | REMOVE | Fixtures for deleted tools. | [task 04](task_04_remove_tool_registry.md) |
| `tests/primitives/tools/test_fs.py` | REMOVE | Covers `primitives/tools/fs.py` (removed). | [task 04](task_04_remove_tool_registry.md) |
| `tests/primitives/tools/test_git.py` | REMOVE | Covers `primitives/tools/git.py` (removed). | [task 04](task_04_remove_tool_registry.md) |
| `tests/primitives/tools/test_http.py` | REMOVE | Covers `primitives/tools/http.py` (removed). | [task 04](task_04_remove_tool_registry.md) |
| `tests/primitives/tools/test_shell.py` | REMOVE | Covers `primitives/tools/shell.py` (removed). | [task 04](task_04_remove_tool_registry.md) |
| `tests/primitives/tools/test_stdlib.py` | REMOVE | Covers `primitives/tools/stdlib.py` (removed). | [task 04](task_04_remove_tool_registry.md) |
| `tests/components/__init__.py` | REMOVE | Mirrors the removed `ai_workflows/components/` package (architecture.md §3 layer collapse). | [task 12](task_12_import_linter_rewrite.md) |
| `tests/workflows/__init__.py` | KEEP | Test-tree package marker mirroring the `workflows/` layer in [architecture.md §3](../../architecture.md); placeholder for M2+ workflow tests, paired 1:1 with `ai_workflows/workflows/__init__.py`. | — |

---

## 4. Migration audit (`migrations/`)

| Path | Verdict | Reason | Target task |
| --- | --- | --- | --- |
| `migrations/001_initial.sql` | MODIFY | Declares `tasks`, `artifacts`, `llm_calls`, `human_gate_states`, `workflow_dir_hash` on `runs` — all pre-pivot checkpoint scaffolding that must be dropped or replaced. Survives only as history; the reshape lands as a new yoyo migration under task 05. | [task 05](task_05_trim_storage.md) |
| `migrations/001_initial.rollback.sql` | MODIFY | Same lifecycle as `001_initial.sql` — task 05 adds the matching `down` migration for the new reconciliation step. | [task 05](task_05_trim_storage.md) |
| `migrations/00N_reconciliation.sql` (new) | ADD | Drops the pre-pivot checkpoint columns/tables and ensures the `gate_responses` table exists per [task 05](task_05_trim_storage.md) deliverable (KDR-009). | [task 05](task_05_trim_storage.md) |
| `migrations/00N_reconciliation.rollback.sql` (new) | ADD | Matching `down` path for the reconciliation migration per task 05 ACs. | [task 05](task_05_trim_storage.md) |

---

## 5. Cross-references summary

Every `Target task` value above corresponds to a file in this directory:

- [task_02_dependency_swap.md](task_02_dependency_swap.md)
- [task_03_remove_llm_substrate.md](task_03_remove_llm_substrate.md)
- [task_04_remove_tool_registry.md](task_04_remove_tool_registry.md)
- [task_05_trim_storage.md](task_05_trim_storage.md)
- [task_06_refit_tier_config.md](task_06_refit_tier_config.md)
- [task_07_refit_retry_policy.md](task_07_refit_retry_policy.md)
- [task_08_prune_cost_tracker.md](task_08_prune_cost_tracker.md)
- [task_09_logger_sanity.md](task_09_logger_sanity.md)
- [task_10_workflow_hash_decision.md](task_10_workflow_hash_decision.md)
- [task_11_cli_stub_down.md](task_11_cli_stub_down.md)
- [task_12_import_linter_rewrite.md](task_12_import_linter_rewrite.md)

Task 13 ([milestone_closeout](task_13_milestone_closeout.md)) is the gate that confirms every row above has landed; it is not itself a target task for any row.

## 6. Deferred items confirmed out of scope

For transparency on what this audit intentionally did *not* list:

- **Langfuse / LangSmith / OTel exporter** — all three are parked in [nice_to_have.md §1, §3, §8](../../nice_to_have.md). No dependency added, no task assigned. Observability stays `StructuredLogger` per [architecture.md §8.1](../../architecture.md).
- **Instructor / pydantic-ai structured-output wrapper** — parked in [nice_to_have.md §2](../../nice_to_have.md); `ValidatorNode` uses LiteLLM `response_format` + LangGraph `ModelRetry` when it lands in M2.
- **Typer swap / Docker Compose / mkdocs / DeepAgents** — parked in [nice_to_have.md §4–§7](../../nice_to_have.md); no M1 row created for any of them.
- **`workflow_dir_hash` column on `runs`** — currently in `migrations/001_initial.sql`; its reintroduction elsewhere (or final removal) is decided by [task 10](task_10_workflow_hash_decision.md) per the scope note in [task 05](task_05_trim_storage.md).
