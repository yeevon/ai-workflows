# Analysis Summary — Post-Research Review

Digest of `search_analysis.md`. Tiered by urgency. Decisions requiring user sign-off listed separately at the end.

---

## Verdict

**Architecture is sound. Scope is premature.**

The three-layer split (Primitives / Components / Workflows) is independently validated by AutoGen v0.4. The typed Component taxonomy (Worker, Planner, Validator, Fanout, Orchestrator, AgentLoop, HumanGate) is a real differentiator versus LangGraph (untyped nodes) and Haystack (uniform @component). The YAML+prompts+Pydantic workflow format is correct.

But: **you are a solo developer with 1.5 real workflows committing to infrastructure that took LangGraph / LlamaIndex / Haystack years to get right.** The analysis's strongest claim — which I agree with — is that Pydantic AI + pydantic-graph + pydantic-evals would cover 80% of Milestone 1 in ~500 lines of glue.

---

## Critical Findings (Fix Before Milestone 1 Code Ships)

### 1. Task-to-task data flow (C-14) is unresolved and load-bearing
Without a defined model for how Task B receives Task A's output, the Orchestrator is incomplete. Every future workflow reinvents this wheel.

**Recommended model (Haystack pattern):** each task declares typed Pydantic input and output schemas. The Orchestrator type-checks the DAG at load time — rejecting plans where Task B expects an input Task A doesn't produce. Task outputs stored as artifacts in SQLite, referenced by ID in downstream inputs.

### 2. Workflow versioning on resume
Currently snapshots `workflow.yaml` only. If `prompts/*.txt` or `custom_tools.py` change between run and resume, behavior is undefined.

**Fix:** snapshot the entire workflow directory. Store a content hash in the runs table. On resume: hash mismatch raises unless `--force-workflow-version-mismatch`. 20 lines.

### 3. Budget caps are NOT "out of scope" — they are safety
You are paying Claude Max out of pocket. A runaway AgentLoop at Opus rates can burn $50 overnight. This was deferred as P-35.

**Fix:** `max_run_cost_usd` in workflow config, checked after every LLM call in `CostTracker`, raises `BudgetExceeded`. 30 lines. Must be in M1.

### 4. The sanitizer is theater
Regex-matching "IGNORE PREVIOUS INSTRUCTIONS" does not defend against adversarial content in a JVM repo. Simon Willison's writing on this is unambiguous — pattern matching fails to novel phrasing trivially.

**What's actually the defense:** `tool_result` `ContentBlock` wrapping (data, not instructions) + tool allowlists + CWD restriction + HumanGate on destructive operations. You already have all of these.

**Fix:** Keep the ContentBlock wrapping. Delete the regex sanitizer or rebrand it as `forensic_logger` for post-hoc analysis only — NOT a security control. The current framing creates false confidence.

### 5. Prompt caching strategy is naive
"Cache last system block" fails the common case: if the last system block has templated `{{variable}}` substitutions, the hash differs every call → 100% cache miss.

**Fix (Anthropic 2026 pattern):** up to 4 breakpoints — (a) last tool definition block (1h TTL), (b) last truly static system block (1h TTL), (c) top-level automatic cache on conversation history (5m TTL). Validate via `cache_read_input_tokens > 0` assertions in integration tests on turn 2+.

### 6. `LLMClient` capability descriptor missing
Without `client.capabilities: ClientCapabilities` (booleans for `supports_prompt_caching`, `supports_parallel_tool_calls`, `supports_structured_output`, `max_context`, `supports_thinking`), components will either `isinstance()` check provider classes (layering violation) or assume features silently.

**Fix:** add a `ClientCapabilities` Pydantic model. Every adapter declares its capabilities. Components check capabilities, never class.

### 7. SDK retry double-amplification
Anthropic, OpenAI, Ollama SDKs all do internal retries by default. Combined with `retry_on_rate_limit()`, you get 3 × 3 = 9 attempts and double-counted rate-limit pressure.

**Fix (Temporal pattern):** set `max_retries=0` on every underlying SDK client at adapter construction. Your `retry_on_rate_limit()` is the single authority. Critical — must land with the adapters.

### 8. Retry error taxonomy underspecified
429/529-only is correct for rate limits but misses: `APIConnectionError` (transient network), `overloaded_error` (should retry), `invalid_request_error` (must NOT retry), and **validation errors from tool output** (Pydantic AI's `ModelRetry` pattern — feed the validation error back to the LLM as a turn, don't hard-fail).

**Fix:** classify errors: retryable-transient (429, 529, connection), retryable-semantic (validation, parse — via ModelRetry), non-retryable (auth, invalid request). Each class has distinct handling.

### 9. `ContentBlock` needs a discriminated union
Flat `content: list[ContentBlock]` with `ContentBlock = TextBlock | ToolUseBlock | ToolResultBlock` needs `Field(discriminator='type')` and a literal `type` field on each variant. Otherwise Pydantic v2 tries each variant in order, produces confusing errors, and performance tanks on long messages.

**Fix:** add `type: Literal["text"]` / `"tool_use"` / `"tool_result"` to each block class. Add `Field(discriminator='type')` on the union. Test with a message containing 50 tool-use blocks.

### 10. Migration framework
Manual SQL scripts in `migrations/` with no version table, no rollback path.

**Fix:** `yoyo-migrations` (single file, adds a `_migrations` tracking table and rollback paths) or `sqlite-utils.Database.migrate()`. 10 minutes now; a day of archaeology later.

---

## Important Findings (Fix Before Milestone 3 Ships)

### 11. Evaluation layer is entirely missing
You cannot answer "did my prompt change regress quality?" without this. Single biggest unforced error.

**Fix:** `pydantic-evals` (matches your Pydantic stack) in M3 alongside the first workflow. `Case + Dataset + LLMJudge + span-based evaluators`. Ten cases per workflow catches 80% of regressions. `aiw eval <workflow>` command. Writes results to SQLite.

### 12. OTel GenAI observability
One `logfire.configure()` + `logfire.instrument_anthropic()` emits standardized spans compatible with Langfuse, Phoenix, Braintrust, Logfire. OTel GenAI semantic conventions are experimental but broadly adopted.

**Fix:** Logfire in M3. Two lines. Enables every downstream obs/eval tool for free.

### 13. Send-equivalent for runtime fan-out
Your Planner generates the DAG up front. It cannot handle "search returned K docs, spawn K summarizers" unless K is known at plan time. LangGraph and LlamaIndex both handle this; you don't.

**Fix:** either (a) allow Workers to return a DAG fragment the Orchestrator splices in, or (b) adopt LangGraph's `Send` pattern where a conditional edge returns a runtime-sized list of worker payloads. Defer to M4-5 when it's first needed — but design the Plan schema to permit it.

### 14. Debugging affordances missing
When task 7 of 12 fails, the user currently gets a "structured failure report" and... no way to iterate. No `aiw inspect <run_id> --task 7` to print the full prompt+tool-calls+output+validator-result. No `aiw rerun-task <run_id> <task_id>` to replay a single task with edited prompts.

**Fix:** both CLI features in M3. Both are pure queries over existing SQLite state. Without them, debugging is "read the log and guess."

### 15. HumanGate timeout wrong for overnight batches
30min default doesn't fit the actual use case (submit a plan review, go to bed, review in the morning).

**Fix:** default `timeout=None` for `strict_review=True` gates (wait forever, user resumes). 30min for non-strict. Or declare per workflow.

### 16. Ollama flakiness handling
Design assumes `OllamaClient` is always reachable. In practice: OOM on model swaps, laptop sleep, VPN drops mid-call.

**Fix:** startup health check that fails fast with actionable error, explicit `ConnectionError → pause and surface` (not retry forever), distinct retry backoff for LAN vs cloud endpoints.

---

## Operational Gaps (Address Any Time)

- **Log rotation / disk usage:** `~/.ai-workflows/runs/<run_id>/` accumulates forever. Add `aiw gc --older-than 30d --keep-artifacts`.
- **Multi-run observability:** No way to answer "has Opus's planning accuracy drifted?" or "which workflow has highest cost?" across runs. `aiw stats --last 30d` is a one-afternoon SQL query. Pays back hundreds of hours/year.
- **AgentLoop subagent context isolation:** Not defined. Anthropic's pattern is fresh context per subagent. Decide: isolated (Anthropic) vs shared thread (chat model). Default should be isolated.

---

## Correctly Deferred (Keep as-is)

- Streaming output (deferred ✓)
- MCP server (deferred ✓)
- Router/Escalator/Synthesizer (on-demand ✓)
- Encrypted checkpoint serde (solo-use, low urgency ✓)
- Cross-run memory / Store (workflow #3 problem ✓)
- DSPy (compose later; Milestone 8+ ✓)

---

## Open-Source Tools to Adopt

| Tool | Replaces | Gain |
|---|---|---|
| **`pydantic-ai`** | BaseComponent, Worker, AgentLoop, tool registry | Agent[Deps, Output], RunContext, @agent.tool, ModelRetry — probably the single biggest simplification |
| **`pydantic-graph`** | Orchestrator, DAG scheduler | Typed edges from return types, state persistence, Mermaid rendering, HITL resume |
| **`pydantic-evals`** | (nothing — currently missing) | Case + Dataset + LLMJudge. Matches Pydantic stack |
| **`logfire`** | `structlog` file output | OTel GenAI spans with two lines, zero-config tracing |
| **`yoyo-migrations`** | Manual SQL scripts | `_migrations` table + rollback paths |
| **`networkx`** | (already planned) | Keep — used if DAG is built |

**Not to adopt:** LangGraph (untyped nodes, state model incompatible), CrewAI (LiteLLM-everywhere, hidden hierarchical prompts), LangChain (ecosystem churn), AutoGen (maintenance mode), Temporal (operational overhead disproportionate for solo use).

---

## Strategic Decisions Needing Your Call

These are the architectural pivots. Each meaningfully changes M1's shape. I have a recommendation for each but need your decision before restructuring the phase files.

### Decision A — Adopt `pydantic-ai` ecosystem as substrate?

**Option 1 (recommended):** Adopt. M1 becomes: Anthropic + Ollama + OpenAI-compat clients behind `pydantic_ai.Model`, tier routing + workflow loader + SQLite run log as your layer. `Worker` and `AgentLoop` become thin wrappers over `Agent[Deps, Output]`. Halves M1. Gets evals + graph orchestration + ModelRetry for free.

**Option 2:** Build from scratch as originally planned. Maximum learning, full control, ~3x the code.

**My take:** Option 1. You stated your goal is "flexible framework for the workflows I need," not "learn framework internals from scratch." Pydantic AI is the closest existing framework to what you're building; they've solved the overlap well and don't force architecture you'd regret.

### Decision B — Linear Pipeline in M1–M3, DAG at M4?

**Option 1 (recommended):** Build a linear `Pipeline` in M1. M3's `test_coverage_gap_fill` is linear (explore → generate → validate). Introduce DAG + `Planner` + `Orchestrator` in M4 when `slice_refactor` actually needs it. Haystack shipped linear pipelines first and added cycles in 2.7, years later — this sequencing is battle-tested.

**Option 2:** Commit to DAG from M1 (current plan). Adds `networkx`, topological sort, checkpoint complexity in service of a single-file-at-a-time M3.

**My take:** Option 1. The grilling decision "DAG from day one" was made assuming M3 needed it. It doesn't. Moving DAG to M4 saves 2-3 weeks of scaffolding against a non-existent demand.

### Decision C — Ollama in M1 or M4?

**Option 1 (recommended):** Keep Ollama in `tiers.yaml` and the `OllamaClient` adapter in M1 (costs nothing extra), but **all M1-M3 workflows default to cloud tiers only**. Don't build the two-machine health check, profile overlay, or Ollama-specific retry path until M4 when exploration volume proves the cost saving.

**Option 2:** Build full Ollama infrastructure in M1 as originally planned.

**My take:** Option 1. The adapter is cheap to write; the operational wrapping around it is what balloons. You save $5-20/day at maybe 30min/day of reliability friction — negative ROI at M1 scale. Cloud-first is the path with least friction to shipping M3.

### Decision D — Collapse Primitives + Components into one module?

**Option 1:** Single `ai_workflows/core/` module with clearly named submodules (`core.llm`, `core.tools`, `core.components`). Import-linter boundary drops.

**Option 2 (recommended):** Keep two separate modules as planned. You already set up `import-linter`. The boundary costs almost nothing to maintain and pays off when workflow #3 forces the split anyway.

**My take:** Option 2. Minor gain from collapse; real loss in architectural clarity. Keep the boundary.

---

## Recommended Next Steps (After Your Decisions)

Once you answer A-D:

1. **Direct fixes (no user input needed)** — delete sanitizer, add budget caps, fix caching strategy, disable SDK retries, add `ClientCapabilities`, switch to yoyo-migrations, add workflow dir hash. I can apply all of these now.

2. **Re-sort `issues.md`** — priority tiers at the top (Critical / Important / Deferred / Nice-to-have / Open Questions), original layer-grouped sections retained below.

3. **If you pick Option 1 on Decision A** — rewrite M1 phase tasks around Pydantic AI adoption. Cuts M1 from 16 tasks to ~8.

4. **If you pick Option 1 on Decision B** — swap M1-M3 from DAG Orchestrator to linear Pipeline. Defer Planner/Orchestrator to M4.

5. **Regardless** — add `pydantic-evals` + `logfire` to M3, add `aiw eval` / `aiw rerun-task` / `aiw inspect --task` / `aiw gc` / `aiw stats` to CLI roadmap.
