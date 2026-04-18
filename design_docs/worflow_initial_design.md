# ai-workflows — Initial Project Design

A reusable framework for building AI workflows out of composable components. Workflows like "refactor a JVM codebase," "generate documentation," or "review a pull request" are all expressed as compositions of the same underlying building blocks rather than as one-off scripts.

---

## Table of Contents

1. [Motivation](#motivation)
2. [Design Goals](#design-goals)
3. [Architecture](#architecture)
4. [Layer 1: Primitives](#layer-1-primitives)
5. [Layer 2: Components](#layer-2-components)
6. [Layer 3: Workflows](#layer-3-workflows)
7. [Repo Structure](#repo-structure)
8. [Workflow Authoring Model](#workflow-authoring-model)
9. [Key Design Decisions](#key-design-decisions)
10. [Build Order](#build-order)
11. [Success Criteria](#success-criteria)
12. [Open Questions](#open-questions)
13. [Appendix: Glossary](#appendix-glossary)

---

## Motivation

Most AI automation starts as a one-shot script — a Python file that pipes a prompt, parses a result, writes a file. Scripts work for exactly one task, and the moment a second task needs 80% of the same scaffolding (retries, cost tracking, tier routing, tool use, validation), the code gets copy-pasted and diverges.

`ai-workflows` reframes the problem: instead of building a script per task, build a **platform** where each new task is a composition of components that already exist. Components compound in value. Scripts decay.

Concretely, this project should let a new workflow be expressed primarily as:

- A YAML file describing which components to wire together
- A small set of task-specific prompts
- Optionally, a handful of custom tools

...rather than a fresh Python file that reimplements orchestration, retries, and cost tracking from scratch.

---

## Design Goals

1. **Composability over cleverness** — prefer small, boring components that combine well over smart monoliths.
2. **Workflows are mostly configuration** — new workflows should require new code only when truly novel behavior is needed.
3. **Cost and behavior observable from day one** — every LLM call logged, tagged, and priced. No black boxes.
4. **Local and cloud LLMs are peers** — Ollama and Claude are different adapters of the same interface. Tier escalation depends on this.
5. **Humans are a first-class step** — any workflow can insert a human review gate between any two steps.
6. **Fail loud, fail cheap** — validation gates between steps; cheap tiers attempted first; escalation paths explicit.
7. **Layering is enforced, not hoped for** — the project shouldn't drift back into script-soup, and lint rules guard that.

---

## Architecture

Three layers with a strict dependency rule: **higher layers depend on lower layers, never sideways, never upward.**

```
┌─────────────────────────────────────────────┐
│  Workflows    (JVM modernization, code       │
│               review, doc gen, ...)          │
├─────────────────────────────────────────────┤
│  Components   (planners, workers, routers,   │
│               validators, orchestrators)     │
├─────────────────────────────────────────────┤
│  Primitives   (LLM clients, tools, tiers,    │
│               storage, logging, retries)     │
└─────────────────────────────────────────────┘
```

A workflow composes components. A component uses primitives. A primitive knows nothing about what's above it.

This is the single most important property of the project. Without it, ai-workflows becomes what it's trying to replace.

---

## Layer 1: Primitives

The foundation. No business logic. These are the plumbing every layer above depends on, so they need to be boring, well-tested, and stable.

### LLM Client Adapters

A single `LLMClient` protocol, multiple implementations:

```python
class LLMClient(Protocol):
    async def generate(
        self,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.1,
    ) -> Response: ...
```

Implementations:

- `AnthropicClient` (Claude Opus, Sonnet, Haiku)
- `OllamaClient` (local models — Qwen2.5-Coder, Llama, DeepSeek)
- `OpenAICompatClient` (OpenRouter, DeepSeek API, Gemini via compat layer)

Every other layer talks to `LLMClient`, never a vendor SDK directly. This is what makes tier escalation possible and what lets you swap providers without rewriting workflows.

### Tool Registry

Tools are named functions with JSON schemas. Register once, use anywhere:

```python
@tool(name="read_file", description="Read a file from disk")
def read_file(path: str) -> str: ...
```

Shipping with the project:

- `read_file`, `write_file`, `list_dir`, `grep`
- `run_command` (sandboxed shell execution)
- `http_get`, `http_fetch`
- `git_diff`, `git_log`, `git_apply`

Workflows register their own specialized tools (e.g., `run_gradle_build`, `openrewrite_apply`) in their own directory.

### Tier Definitions

A tier is a named LLM config. They live in `tiers.yaml`:

```yaml
tiers:
  opus:
    provider: anthropic
    model: claude-opus-4-7
    max_tokens: 8192
    temperature: 0.1

  sonnet:
    provider: anthropic
    model: claude-sonnet-4-6
    max_tokens: 8192

  haiku:
    provider: anthropic
    model: claude-haiku-4-5-20251001
    max_tokens: 4096

  local_coder:
    provider: ollama
    model: qwen2.5-coder:32b
    base_url: http://localhost:11434
```

Components reference tiers by **name**, never by model string. Model upgrades are a YAML change, not a code change.

### Storage

A structured run log backed by SQLite (swappable later):

- Every LLM call: inputs, outputs, tokens, cost, tier, workflow ID, component
- Every tool invocation: tool name, input, output, duration
- Intermediate artifacts: plans, diffs, human review decisions
- Final outputs

SQLite is the right default — zero deps, inspectable with `sqlite3`, good enough for single-machine use. Cloud backends plug in via the same interface.

### Cost Tracking

Every LLM call is tagged with `{workflow_id, component, tier, run_id}` at the primitive layer. This means the project can answer on day one:

- What did this workflow run cost?
- Which component is burning the most budget?
- How has cost per workflow trended over time?

### Retry / Rate-Limit / Backoff

One decorator every LLM call goes through. Components do not implement retry logic themselves. Handles:

- Exponential backoff for 429 / 529
- Distinguishing retryable from non-retryable errors
- Per-tier rate limit tracking
- Circuit breaker on sustained failures

---

## Layer 2: Components

Reusable patterns. Each component does one thing, takes typed inputs (Pydantic models), returns typed outputs. Components are **pure in intent** — same input should yield equivalent output — even though the LLM call inside is nondeterministic.

### Core Component Set

| Component | Responsibility | Used By |
|---|---|---|
| **Planner** | Takes a goal + context, produces a structured task list | Any multi-step workflow |
| **Orchestrator** | Executes a plan, respects dependencies, collects results | Any multi-step workflow |
| **Worker** | Executes one subtask (tier + tools + prompt template) | Orchestrator |
| **Router** | Classifies an item into a category (which tier, which branch) | Orchestrator, Fan-out |
| **Fanout** | Runs a worker over a list in parallel with concurrency limits | Batch work |
| **Validator** | Takes output + criteria, returns pass/fail with reason | Escalation gates |
| **Escalator** | Try cheap tier → validate → escalate on failure | Cost-optimized workflows |
| **AgentLoop** | Tool-using loop until termination | Investigation, research |
| **Synthesizer** | Takes many outputs, produces one consolidated result | Research, audit workflows |
| **HumanGate** | Pauses workflow, renders review, waits for approval | High-stakes decisions |

### Component Contract

Every component has:

- A **typed interface** — Pydantic input and output models
- A **config schema** — what YAML fields it accepts (prompts, tier, retries, validators)
- **Standalone tests** — mocks the LLM, verifies control flow
- **Standalone docs** — what it does, when to use it, example usage

### The Power of This Layer

Most new workflows don't need new components. They need new **configs and prompts** for existing components. This is the compound-interest property of the project: every component added lowers the cost of every future workflow.

### When to Add a New Component

Strict rule: **add a component only when a second workflow reveals duplication.** First time you need something, write it inline in the workflow. Second time, extract it to components. This prevents speculative abstraction, which is how platforms die.

---

## Layer 3: Workflows

A workflow is a composition of components configured for a specific task. A workflow directory contains:

```
workflows/jvm_modernization/
├── workflow.yaml          # component wiring
├── prompts/
│   ├── orchestrator.txt
│   └── worker.txt
├── custom_tools.py        # workflow-specific tools (e.g., gradle runner)
├── schemas/               # Pydantic models for this workflow's I/O
└── run.py                 # thin entry point
```

### Initial Planned Workflows

- **test_coverage_gap_fill** — characterization test generation across many files (the Pipeline 1 pattern)
- **slice_refactor** — orchestrated cross-codebase refactor of a bounded context (the Pipeline 2 pattern)
- **jvm_modernization** — composition of the two above, plus driver scripts, for the full modernization plan
- **code_review** — PR diff → per-file review comments → PR-level summary
- **doc_generation** — explore a codebase → produce a doc outline → fan-out section generation
- **migration_audit** — inventory → classify → synthesize report
- **incident_postmortem** — logs + chat ingestion → timeline → analysis → human gate

None of these need to exist on day one. They are targets that validate the architecture.

---

## Repo Structure

```
ai-workflows/
├── pyproject.toml
├── README.md
├── .gitignore
├── .python-version
├── tiers.yaml                      # shared tier definitions
├── cli.py                          # `aiw run <workflow> [args]`
├── ai_workflows/
│   ├── primitives/
│   │   ├── __init__.py
│   │   ├── llm/
│   │   │   ├── base.py             # LLMClient protocol
│   │   │   ├── anthropic.py
│   │   │   ├── ollama.py
│   │   │   └── openai_compat.py
│   │   ├── tools/
│   │   │   ├── registry.py
│   │   │   ├── fs.py
│   │   │   ├── shell.py
│   │   │   ├── http.py
│   │   │   └── git.py
│   │   ├── tiers.py
│   │   ├── storage.py
│   │   ├── cost.py
│   │   ├── retry.py
│   │   └── logging.py
│   ├── components/
│   │   ├── __init__.py
│   │   ├── planner.py
│   │   ├── orchestrator.py
│   │   ├── worker.py
│   │   ├── router.py
│   │   ├── fanout.py
│   │   ├── validator.py
│   │   ├── escalator.py
│   │   ├── agent_loop.py
│   │   ├── synthesizer.py
│   │   └── human_gate.py
│   └── workflows/
│       ├── test_coverage_gap_fill/
│       ├── slice_refactor/
│       ├── jvm_modernization/
│       └── ...
├── tests/
│   ├── primitives/
│   ├── components/
│   └── workflows/
└── docs/
    ├── architecture.md
    ├── writing-a-component.md
    └── writing-a-workflow.md
```

---

## Workflow Authoring Model

A workflow YAML describes which components to instantiate, their configs, and how data flows between them.

Example sketch for `jvm_modernization`:

```yaml
name: jvm_modernization
description: Refactor three JVM codebases with dependency awareness

inputs:
  slice_name: str
  goals: str
  repos:
    A: path
    B: path
    C: path

components:
  planner:
    type: planner
    tier: opus
    prompt: prompts/orchestrator.txt
    tools: [read_file, grep, run_gradle_build]
    output_schema: schemas/plan.py:Plan

  tier_router:
    type: router
    rules:
      - match: { change_type: [format, rename, junit_migration] }
        tier: deterministic
      - match: { change_type: [classify, summarize] }
        tier: local_coder
      - default:
        tier: sonnet

  executor:
    type: orchestrator
    plan_source: planner
    dispatch_via: tier_router
    parallelism: 5
    validator:
      - run_command: "./gradlew build"
        must_succeed: true

  review:
    type: human_gate
    after: planner
    before: executor
    render: plan_review_template.html

flow:
  - planner
  - review
  - executor
```

Running it:

```bash
aiw run jvm_modernization \
  --slice OrderService \
  --goals "Extract discount calculation. Move validation from C to B." \
  --repos.A /repos/a --repos.B /repos/b --repos.C /repos/c
```

The CLI resolves component references, loads prompts, wires flows, and dispatches. The workflow author writes YAML and prompts — not orchestration code.

---

## Key Design Decisions

Decisions that are painful to change later, made up front.

### Language: Python

Python is the default. The LLM ecosystem tooling, Pydantic models, async libraries, and Anthropic/Ollama SDKs all favor Python. TypeScript would give a cleaner path to a web UI for `human_gate` later, but that can be a separate service rather than a language rewrite.

### Config Format: YAML with Pydantic Validation

YAML for human editing; Pydantic models load and validate it. This gives both readable configs and type safety. Known YAML footguns (the "Norway problem," number coercion) are caught by Pydantic at load time.

### Async from Day One

Fan-out and parallel orchestration are the whole point. Every LLM call, tool call, and component method is async. Sync wrappers can be added for scripts that need them; the core is async.

### Storage: SQLite Default

One file, zero dependencies, inspectable with standard tools. Good enough for single-machine use for a long time. The storage interface is abstracted, so Postgres or a cloud backend plugs in later without touching components.

### Layering Enforced by Lint

An import-linter config or ruff rule fails CI if `workflows/` reaches into internals, or if `primitives/` imports from `components/`. Without this, the layering decays within months. With it, it's permanent.

### Local LLMs Are First-Class

The `OllamaClient` adapter implements the exact same `LLMClient` protocol as `AnthropicClient`. Tier escalation and router rules treat them identically. The moment local and cloud diverge in the abstraction, the escalation story gets muddled.

### Prompts Live in Files, Not Strings

Prompts are versioned files next to the workflow that uses them. This enables:

- Git history on prompt changes
- A/B testing two prompt versions by swapping a config line
- Review workflow changes without wading through Python

### Human Review Is a Component, Not a Pattern

`HumanGate` is a first-class component. Any workflow can drop it between any two steps. Initial implementation can be CLI-based ("review this plan, type y/n"); a web UI ships later without workflows needing to change.

---

## Build Order

Resist building all components up front. Build narrowly, let real workflows reveal what's needed.

### Milestone 1: Primitives (Week 1)

- `LLMClient` protocol
- `AnthropicClient` + `OllamaClient` adapters
- Tool registry with stdlib tools
- `tiers.yaml` loader
- SQLite storage with run log
- Cost tracking
- Retry decorator

**Exit**: you can make an LLM call from a Python REPL, it gets logged, cost tracked, retried on 429.

### Milestone 2: Minimum Components (Week 2)

- `Worker`
- `Validator`
- `Fanout`

**Exit**: these three components can be composed to recreate Pipeline 1's shape.

### Milestone 3: First Workflow — `test_coverage_gap_fill` (Few Days)

Port Pipeline 1 to use the components above. **This is the forcing function** — real use will reveal what the component APIs actually need to be. Expect to refactor components here; that's the point.

### Milestone 4: Orchestration Components (Week 3)

- `Planner`
- `Orchestrator`
- `AgentLoop`

**Exit**: these can be composed to recreate Pipeline 2's shape.

### Milestone 5: Second Workflow — `slice_refactor` (Few Days)

Port Pipeline 2. Second use of components reveals shared patterns, tightens APIs.

### Milestone 6: `jvm_modernization` Workflow

Compose the two workflows above plus driver scripts into the full modernization plan. At this point the project has proven itself on the target use case.

### Milestone 7: Fill Out Components as Needed

`Router`, `Escalator`, `Synthesizer`, `HumanGate` — each added only when a new workflow demands it. Do not speculatively build.

---

## Success Criteria

The project has succeeded when:

1. A new workflow for a well-understood task can be authored in **under a day**, primarily as YAML and prompts.
2. **Cost and latency per workflow** is visible without writing new code — a CLI command or dashboard shows it.
3. Swapping model providers or upgrading to a new model is a **tiers.yaml edit**, not a code change across workflows.
4. **Prompt A/B testing** can be done by duplicating a workflow config and swapping the prompt file path.
5. The layering rule is **enforced by CI**, not by vigilance.
6. At least three distinct workflows share the same component set, with clear evidence of shared code paying off.

---

## Open Questions

Things deliberately left undecided, to be resolved by building.

1. **How strict should plan schemas be?** Strict Pydantic schemas catch planner errors early but make prompt engineering harder. Leaning toward strict + a retry loop on parse failure.
2. **How does `HumanGate` render reviews?** CLI-first is simple. A web UI is nicer but pulls in a server dependency. Start CLI, design the interface so a web frontend is additive.
3. **What's the story for long-running workflows?** A slice refactor might take 20 minutes. Does the CLI block that whole time? Probably acceptable initially; a queue/worker split can come later.
4. **Should workflows be packageable?** e.g., `pip install ai-workflows-jvm-modernization` as a plugin. Defer — just a subdirectory for now.
5. **How are workflow outputs versioned?** Run ID directory structure? Content-addressed? Start simple (timestamped run directories), revisit if it matters.
6. **Windows support?** Not a priority. Linux/macOS is the default target; Windows probably works via WSL.

---

## Appendix: Glossary

- **Primitive** — a low-level building block that knows nothing about workflows or components (e.g., LLM client adapter, tool, retry decorator).
- **Component** — a reusable pattern composed of primitives, with typed I/O and standalone tests (e.g., Worker, Planner, Orchestrator).
- **Workflow** — a task-specific composition of components, expressed mostly in YAML and prompts.
- **Tier** — a named LLM configuration (model + max_tokens + temperature), referenced by name across all components.
- **Run** — one execution of a workflow, with a run_id used to tag every LLM call and artifact.
- **Escalation** — the pattern of trying a cheap tier first, validating the output, and falling through to a stronger tier on failure.
- **Fan-out** — running the same worker in parallel over many inputs with a concurrency limit.
- **Gate** — a component (usually `HumanGate` or `Validator`) that must pass before execution continues.

---

## Design Decisions Log (Post-Grill, 2026-04-17)

All decisions below were resolved through an exhaustive design review. See `grill_me_results.md` for full reasoning. See `issues.md` for status of all issues.

### Tooling & Environment

- **Python floor:** 3.12 (`requires-python = ">=3.12"`); `.python-version` targets 3.13.
- **Build backend:** `hatchling`. **Dependency manager:** `uv`.
- **CLI framework:** `typer`. **Logging:** `structlog`.
- **Import linter:** `import-linter` PyPI package — enforces the three-layer rule at CI time.
- **Test framework:** `pytest` + `pytest-asyncio` with `asyncio_mode = "auto"`.
- **Pydantic:** v2 pinned from day one.

### LLM Client & Types

- **`Message` type:** flat `Message(role, content: list[ContentBlock])`. Content blocks carry everything — text, tool use, tool results.
- **`Response` type:** normalized-only — `Response(content, stop_reason, usage: TokenUsage)`. Raw provider payload never leaves the adapter.
- **`LLMClient`:** a `Protocol` (structural subtyping), not a base class.
- **Streaming:** deferred. `generate()` always returns a complete `Response`. A `stream_generate()` variant can be added later for `HumanGate` display only.
- **Prompt caching:** automatic in `AnthropicClient` (marks last system message block as cacheable). Invisible to callers.
- **Explicit context tagging:** `run_id`, `workflow_id`, `component` are required keyword arguments on every `generate()` call. No `contextvars`.

### Infrastructure

- **Two-machine setup:** Orchestrator runs on work laptop. Ollama (`local_coder` tier) runs on home desktop. `base_url` is env-var configurable (`OLLAMA_BASE_URL`). `--profile local` loads `tiers.local.yaml` overlay for desktop dev.
- **Storage:** SQLite + WAL mode at `~/.ai-workflows/runs.db`. Artifacts at `~/.ai-workflows/runs/<run_id>/`. `workflow.yaml` snapshotted into run dir at start.
- **Retry:** `retry_on_rate_limit()` utility function. Only 429/529. Max 3 attempts (configurable per tier). Exponential backoff + jitter.
- **Pricing:** `pricing.yaml` alongside `tiers.yaml`. Local model cost recorded as `0.0`, excluded from aggregations.

### Tool Registry & Security

- **Injected `ToolRegistry`:** one instance per workflow run, not a global singleton. Test isolation is free.
- **`run_command` guards:** CWD restriction (refuses `..` traversal) + `allowed_executables` allowlist per workflow YAML + `dry_run: bool` flag.
- **Prompt injection:** all tool outputs are wrapped as `tool_result` `ContentBlock`s (data, not instructions). A sanitizer in `primitives/tools/sanitizer.py` strips injection patterns before any tool result enters message history.
- **Tool output size:** no hard truncation. Optional `max_chars` param per tool call. Cost tracker surfaces abuse.

### Tier Routing Strategy

| Operation | Tier | Notes |
| --- | --- | --- |
| Exploration reads | `local_coder` (Qwen) | Full file content; summarization via prompt, not AST |
| Reads for modification | `sonnet` | Full context needed for editing |
| Non-refactor edits, file writes | `haiku` or `local_coder` | Bounded, single-call |
| Planning | `opus` | Pay for accuracy upfront |
| Semantic validation | `haiku` | Cheap quality checks |

### Components

- **`BaseComponent` ABC:** shared logging, cost tagging, explicit `run_id` threading.
- **Prompt templates:** simple `{{variable}}` substitution only. No Jinja2.
- **Worker `max_turns`:** Sonnet — soft cap 15 (configurable up to 20). Haiku/Qwen/Flash — single-call (`max_turns=1`, fixed).
- **Worker soft cap behavior:** returns `status="incomplete"`. Orchestrator decides: re-trigger with context, or spawn mini-Planner to decompose.
- **Fanout:** max concurrency 5, hard cap 8. Total queue unlimited (waves). Input order preserved.
- **Failure policy:** one auto-mitigation attempt. Double failure = full hard stop. Completed tasks preserved.
- **Validator:** two types (`structural` shell command, `semantic` Haiku LLM check). Both in interface from day one. Implementations built per workflow.

### Planner & Orchestration

- **Planner output:** DAG with `depends_on: [task_id]` from day one. `networkx` for topological sort.
- **Two-phase planning:** Phase 1 — Qwen exploration writes per-module summary docs to `runs/<run_id>/exploration/`. Phase 2 — Opus reads those docs + direct tool access (`read_file`, `grep`, `list_dir`, `git_log`). Phase 1 skipped on resume if docs exist.
- **Plan validation:** max 3 parse-failure retries (with failure reason in context), then abort.
- **Checkpoint/resume:** from Milestone 1. Task states in SQLite. `aiw resume <run_id>` uses snapshotted `workflow.yaml`.
- **AgentLoop:** stays in Layer 2, weaker documented guarantee. Orchestrator mandates a Validator gate after every AgentLoop step. Failures produce a structured `AgentLoopFailure` artifact.

### HumanGate

- **Render:** raw JSON to `runs/<run_id>/gates/{gate_id}.json`. Terminal shows pretty-printed plan with task summaries and dependency tree.
- **Timeout:** configurable (default 30 min). Hard stop on expiry → `timed_out` in SQLite. Resume re-renders.
- **Decisions:** approve / reject / edit-then-approve.
- **`strict_review: true`:** blocks `--skip-gate` flag entirely. For government or regulated workflows.
