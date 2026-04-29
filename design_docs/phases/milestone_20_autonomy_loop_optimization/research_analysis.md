# Research Brief — Milestone 20: Autonomy Loop Optimization
## Multi-Agent LLM Orchestration Best Practices, Post-Opus-4.6

**Audience:** ai-workflows maintainers (Builder→Auditor loops, 9 sub-agents, slash-command orchestrators)
**Scope:** Patterns and findings published or current as of Q1–Q2 2026, after Anthropic's Claude Opus 4.6 release (Feb 5, 2026) and Opus 4.7 release (Apr 16, 2026)
**Method:** Cross-comparison of Anthropic's official engineering posts, Claude Code/Agent SDK docs, LangGraph/LangChain guidance, and independent practitioners (Nate B. Jones, MindStudio, Vellum, Caylent, MintMCP, ClaudeFa.st, and others)

---

## Executive Summary

Three structural shifts have happened in agent engineering since the Opus 4.6 release that directly affect every existing item in the M20 task pool:

1. **Adaptive thinking is now the recommended thinking mode.** `thinking: {type: "enabled", budget_tokens: N}` is *deprecated* on Opus 4.6 / Sonnet 4.6 and *rejected with a 400 error* on Opus 4.7. The new mechanism is `thinking: {type: "adaptive"}` paired with an `effort` parameter (`low | medium | high | max`, plus `xhigh` exclusive to Opus 4.7). The `MAX_THINKING_TOKENS` lever and "thinking: max"-style prompting from older guidance is obsolete.
2. **Server-side compaction is now first-class.** Anthropic shipped a beta `compact_20260112` strategy in `context_management.edits` (header `compact-2026-01-12`) plus a sibling `clear_tool_uses_20250919` strategy and a Memory tool. This is the new primitive set; "summarize the conversation manually" is no longer the only option, and several M20 compaction items can be replaced by configuration.
3. **The Sonnet–Opus gap collapsed for everyday agentic coding.** Sonnet 4.6 scores 79.6% on SWE-bench Verified vs Opus 4.6's 80.8% (a 1.2-point gap) at one-fifth the price. Opus 4.6's strongholds shifted upmarket: GPQA Diamond (91.3% vs Sonnet's 74.1%), 1M-token MRCR v2 (76% vs Sonnet 4.5's 18.5% — true qualitative shift), BrowseComp (84.0%), and ARC-AGI-2. Opus 4.7 widens the SWE-bench lead to 87.6% but uses a different tokenizer that consumes 1.0–1.35× more tokens per byte. The cost case for "default Sonnet, escalate to Opus only on demand" is now overwhelming for almost all builder/auditor work, and the user's intuition behind T06 / T07 is validated.

These shifts cascade into the rest of this brief.

---

## LENS 1 — Agent Orchestration Patterns (Post-Opus-4.6)

### 1.1 The orchestrator-worker pattern is the validated reference architecture

Anthropic's "How we built our multi-agent research system" — still the canonical published reference — reports that **a multi-agent system with Opus as the lead and Sonnet subagents outperformed a single-agent Opus by 90.2%** on their internal research eval. Three factors explained 95% of the variance: token usage (80%), tool-call count, and model choice. The takeaway, repeated in every subsequent Anthropic engineering post ("Effective context engineering for AI agents", "Building agents with the Claude Agent SDK", "Effective harnesses for long-running agents"): **agents work mainly because they spend enough tokens, and isolating sub-tasks into independent context windows is the cheapest way to "spend more tokens" without paying the context-rot penalty.**

For ai-workflows, this directly maps to:
- **Lead orchestrator** = the slash-command (e.g. `/triage`, `/check`, `/ship`, `/sweep`) running on Sonnet 4.6 or Opus 4.6.
- **Specialized sub-agents** (architect, auditor, builder, dependency-auditor, roadmap-selector, security-reviewer, sr-dev, sr-sdet, task-analyzer) = workers in the Anthropic sense.

**Caveat that contradicts pre-4.6 hype:** Anthropic's own post explicitly warns that *"most coding tasks involve fewer truly parallelizable tasks than research, and LLM agents are not yet great at coordinating and delegating to other agents in real time."* The implication for ai-workflows: parallelism is a tool to apply *selectively* (independent terminal gates, fragment files), not a goal in itself. The brief returns to this in Section 1.4.

### 1.2 Sub-agents in Claude Code: what is and isn't recommended

The Claude Code / Agent SDK docs are now explicit on a set of patterns that didn't exist in last year's writeups:

- **Sub-agents are isolation primitives, not intelligence multipliers.** "Sub-agents do not make Claude smarter. … All the intermediate noise — file reads, search results, exploratory tool calls — stays inside the subagent's context and never touches the main conversation." (Sathish Raju, Apr 2026; mirrors Anthropic's `code.claude.com/docs/en/sub-agents`.) The benefit is *context preservation* — the parent gets only the final message verbatim.
- **Spawn rule.** Sub-agents cannot spawn other sub-agents (Claude Code's Plan agent uses this restriction by design to prevent infinite nesting). For ai-workflows, this means the slash-command orchestrator is the *only* layer that fans out; sub-agents themselves stay flat.
- **Tool restriction is a security and focus boundary.** Anthropic's docs and PubNub's production writeup converge: every sub-agent should declare an explicit `tools:` list. A code-review agent should not have `Bash`; a doc agent should not have file write. This dovetails with M20-T10 (common-rules extraction).
- **Worktree isolation is now first-class.** As of Claude Code v2.1.49 (Feb 19, 2026), `--worktree`/`-w` ships natively, and `isolation: worktree` in a sub-agent's frontmatter automatically gives each invocation its own branch and directory, with auto-cleanup on no-change exit. This is the recommended foundation for parallel-builders (M20-T17/T18/T19).
- **Built-in helper sub-agents.** Claude Code now ships `Explore` (read-only, Haiku), `Plan` (read-only research/architecture), and `general-purpose` (full tools). These exist precisely so that custom agents don't have to redo discovery work. The implication for ai-workflows: avoid redefining what Claude Code already has under different names; lean on `Explore` for the cheap recon stage.

### 1.3 Sub-agent return-value contract: structured + bounded + persisted

Every credible source converges on three rules for sub-agent outputs:

1. **Bounded length.** MindStudio's "How to Use Sub-Agents for Codebase Analysis" and Anthropic's own multi-agent writeup both specify token caps in the spawn prompt (1,000–2,000 tokens for read-only sub-agents). Without a cap, "you've just moved the context problem from the main agent to the orchestrator's input buffer" (Builder.io, Apr 2026).
2. **Structured schema.** The Claude Agent SDK now natively supports `outputFormat: { type: "json_schema", schema: ... }` with retry-on-mismatch. For ai-workflows this is the right primitive for the T01 verdict/file/section schema.
3. **Persisted to disk, not just returned in-message.** A live GitHub Copilot CLI issue (#2137, Apr 2026) documents the failure mode: *"When a background sub-agent completes and its result is read via read_agent, the result exists only in the active conversation context. If a conversation compaction occurs before the result is integrated into a persistent file, the detailed sub-agent output is permanently lost."* The fix in production agentic systems is to require sub-agents to write their findings to a file *and* return a 3-line pointer (verdict / file / section). M20-T01 is exactly this pattern; the field is converging on it.

### 1.4 Parallel sub-agent dispatch — when, when not, how

**When parallel works (consensus across ClaudeFa.st, AddyOsmani, MindStudio, Anthropic):**
- ≥3 *unrelated* tasks
- No shared state between them
- Clear, non-overlapping file boundaries
- Independent verification (the security-reviewer doesn't need the sr-dev's draft to evaluate)

**When parallel fails:**
- Sequential dependencies (B needs A's output)
- Same-file edits (merge conflict guaranteed even with worktrees, because semantic conflicts ≠ git conflicts)
- Tasks that share too much context — the parent ends up re-broadcasting the same 50 KB to every sub-agent and *negates* the token-isolation benefit

**Mechanics for ai-workflows:** Anthropic's docs and ClaudeLog both emphasize that **the orchestrator must be told explicitly to parallelize, in the same message, and Claude Code caps practical concurrency around 7 sub-agents.** Patterns that work in production (per addyosmani.com's Apr 2026 piece):
- Spawn all parallel sub-agents in one parent message ("In parallel, dispatch sr-dev, sr-sdet, and security-reviewer with the following scopes…")
- Each sub-agent writes its verdict to a *fragment file* (e.g. `.cycle/sr-dev.verdict.md`, `.cycle/security.verdict.md`)
- A single follow-up parent turn aggregates the three fragment files

This is exactly M20-T05 ("Parallel terminal gate"). The literature strongly supports it.

**New since Opus 4.6 — Agent Teams (experimental).** Anthropic shipped `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` alongside Opus 4.6. Teams add what plain sub-agents lack: peer-to-peer messaging, shared task list with dependency tracking, file locking. The Anthropic guidance: *"Use sub-agents when you need quick, focused workers that report back. Use Agent Teams when teammates need to share findings, challenge each other's assumptions, or coordinate on cross-cutting changes."* For Builder→Auditor specifically, sub-agents remain the right primitive — there is no cross-talk requirement. Agent Teams would only become relevant if M20 ever moves to adversarial-debate auditing (multiple Auditors challenging each other), which is *not* a current task. **Recommendation: do not adopt Agent Teams in M20**; note the pattern for a future milestone if the project ever needs adversarial debate (e.g., a future hostile-spec analyzer).

### 1.5 Builder→Auditor mapped to canonical patterns

ai-workflows' Builder→Auditor loop is a textbook implementation of Anthropic's **evaluator-optimizer** pattern (one of the six in "Building effective agents"). LangGraph documents it as a `ChatAnthropic(model="claude-sonnet-4-6")` reference. Two lessons from the published implementations that are not yet in M20:

1. **The evaluator should run in a *fresh* context.** Anthropic's cookbook example reinitializes the evaluator each loop. A sub-agent Auditor on each cycle (rather than re-prompting the same context) is structurally correct. ai-workflows already does this.
2. **Iteration cap with explicit reasons.** The cookbook's `loop()` returns a status code (`PASS | NEEDS_REVISION | MAX_ITERATIONS`). Production loops also enforce a hard cap (typically 3–5) to prevent the "checkbox cargo cult" failure mode that M20-T20 is targeted at. The cap should be enforced by the orchestrator, not by the agents themselves (the agents will always claim to need another pass).

---

## LENS 2 — Context-Window Management for Sustained Loops

### 2.1 Anthropic's three-primitive model

The Apr 2026 Claude cookbook ("Context engineering: memory, compaction, and tool clearing") finally distinguishes the three layers cleanly:

| Primitive | What it does | Best for |
|---|---|---|
| **Compaction** | Summarizes the conversation when it nears the context limit; replaces all messages before a `compaction` block with a single summary | Conversations where back-and-forth context matters but old detail can be lossy-compressed |
| **Tool-result clearing** (`clear_tool_uses_20250919`) | Drops content of older tool results, keeps the metadata that the call happened | Heavy tool-use loops where file reads and grep outputs accumulate but are re-fetchable |
| **Memory** (Memory tool) | Writes structured notes to persistent external storage; agent re-reads on demand | Cross-session and cross-task continuity |

ai-workflows' "cycle_summary.md" (T03) and "iter_<N>_shipped.md" (T04) are an in-repo, file-based implementation of the **Memory** primitive. This is the right pattern; the three Anthropic primitives are not mutually exclusive. **What's new and superseding:** server-side compaction can now be *added on top* of the file-based memory pattern at the API level, controlled by:

```python
context_management={
  "edits": [{
    "type": "compact_20260112",
    "trigger": {"type": "input_tokens", "value": 100000},
    "pause_after_compaction": True
  }]
}
```

Whether this matters for ai-workflows depends on whether the loops are running through the Claude Code CLI (which has its own `/compact` and `/clear` plus auto-compact at ~92%) or through the Agent SDK. For the CLI case, the relevant operational guidance is the Anthropic best-practices doc: **"Use `/clear` between unrelated tasks. Use `/compact <focus>` proactively at 60–70% capacity rather than waiting for the 92% trigger, because the auto-summarizer is generic; manual compaction lets you steer what survives."**

### 2.2 Cache invalidation: the most expensive footgun in long loops

Multiple production reports in 2026 (Anthropic Claude Code issues #27048, #34629, #42338, #43657; Vellum's Opus 4.7 piece; Claude Code Camp's Mar 2026 deep dive) document that **the prompt-cache hierarchy is `tools → system → messages` and changes at any level invalidate that level and everything after it.** The practical rules:

- **Cache breakpoints must sit on the last *stable* block, not the last block.** If your last block is a per-request timestamp, the breakpoint walks backwards finding nothing previously written and forces a full re-cache. Several issues in Claude Code's own issue tracker were exactly this bug: a 1-byte newline difference invalidating a 500K-token prefix.
- **Adding or removing an MCP tool mid-session invalidates the entire conversation cache** because tool definitions sit between the system prompt and the messages. This is why Claude Code locks the tool list at startup. ai-workflows should treat sub-agent tool lists as *write-once-per-session*; never let an orchestrator dynamically add/remove tools to a running sub-agent.
- **Tool-result clearing invalidates the cached prefix at the point of the clear.** Use `clear_at_least` to make sure each clearing event recovers more tokens than the cache rebuild costs.
- **Switching the model mid-session also invalidates** (cache is keyed by model). For ai-workflows' "default-Sonnet + --expert Opus override" (T07), this means: do *not* switch model mid-loop on the same context; instead, escalate by spawning a fresh sub-agent in the heavier model.

A useful empirical figure (Anthropic + AWS docs, repeatedly confirmed): cache reads cost **0.1× base input price**, 5-min cache writes cost **1.25×**, 1-hour cache writes cost **2×**. The break-even on a 5-minute cache is roughly 2 reads; on a 1-hour cache, ~9 reads. For an autonomous Builder→Auditor loop running 10 cycles in 30 minutes, the 1-hour TTL (`extended-cache-ttl-2025-04-11` header) is almost always the right choice for the system prompt and `non_negotiables.md`.

### 2.3 Pre-feed vs. on-demand: the post-Opus-4.6 calculus has shifted

Pre-Opus-4.6 conventional wisdom — "shove everything you can into a 200 K context window upfront and let the model sort it out" — was already dubious. It is now actively wrong, for two empirical reasons:

1. **Context rot.** Anthropic's "Effective context engineering for AI agents" (Sep 2025, restated in the Apr 2026 cookbook) describes context as a *finite resource with diminishing marginal returns*. Models remain capable at long contexts but show **reduced precision for retrieval and long-range reasoning** as the n² attention budget gets stretched. This degradation is gradient, not cliff — but it starts long before the 200 K limit.
2. **Progressive disclosure works.** Anthropic's Skills (released Oct 2025, expanded through 2026) demonstrate the on-demand pattern at scale: at session start, only ~100 tokens of metadata per Skill enter context; the full SKILL.md (<5 K tokens) loads only when triggered; bundled resources load only when needed. This is the explicit endorsement of **"smaller files with descriptive names + a small index, not one big file."**

For ai-workflows MD files specifically, the consensus pattern (HumanLayer, Builder.io, MindStudio, Anthropic Claude Code docs) is:

- **CLAUDE.md as a thin index**, not a knowledge dump. Pointers to `agent_docs/*.md` with one-line descriptions.
- **One topic per file**, named for what it is (`building_the_project.md`, `running_tests.md`, `code_conventions.md`, `service_architecture.md`).
- **Section anchors in every doc** (`## Section Name {#anchor}` or just consistent `##` headings) so a sub-agent prompt can request *just* the section it needs.
- **Pointers, not copies.** Don't paste code snippets into agent docs — they go stale and re-inflate context. Instead say "see `src/foo.py:42–60` for canonical pattern."
- **Agentic memory pattern** (Cole Medin's claude-memory-compiler, the Open Brain project): keep "atomic" notes, one idea per entry, so retrieval is precise. The Zettelkasten principle.

Nate B. Jones, in his Aug 2025 piece "Stop Burning Tokens: The Contract-First Prompting Blueprint No One Talks About" and his Apr 2026 piece "Your Claude Sessions Cost 10x What They Should," frames this as a four-level hierarchy of token waste: (1) raw PDFs stuffed into context, (2) conversation sprawl, (3) plugin/MCP overhead before you even type, (4) pre-loading context the model didn't need. Nicholas Rhodes's follow-up ("I found 350,000 tokens hiding in plain sight," Apr 2026, citing Jones) adds a fifth that is highly relevant to ai-workflows' background loops: **automated task bloat — the prompts you wrote six months ago are doing what they were told, including every wasteful habit you had at the time.** A Cowork scheduled task he audited had 11,800 tokens of waste per run from missing tool declarations forcing repeated tool-search round-trips, redundant screenshots where `get_page_text` would do, and multi-step navigation that a single JS call could replace. The cure he proposes is a periodic *audit prompt* that re-reviews skills and scheduled tasks for these patterns — exactly the kind of thing M20-T20 ("checkbox-cargo-cult catch") already gestures at.

The ai-workflows-relevant rule that emerges: **pre-feed only what the sub-agent will *certainly* use; let it pull the rest on demand from the searchable MD index.** The cost of an over-pre-fed sub-agent is real (token waste, attention dilution, slower TTFT); the cost of an under-pre-fed sub-agent is one extra `Read` call. The asymmetry favours under-pre-feeding, post-Opus-4.6.

### 2.4 What this implies for the existing T02, T03, T04, T11, T12 items

- **T02 (orchestrator-side scope discipline)** is correct and supported. Add an explicit token budget per sub-agent spawn (the literature's 1–2 K return cap for read-only sub-agents).
- **T03 (cycle_summary.md per Auditor)** maps to Anthropic's note-taking primitive. Keep, but consider also leveraging server-side `compact_20260112` if the agent loops run through the SDK rather than the CLI.
- **T04 (iter_<N>_shipped.md)** = cross-task memory. Same recommendation.
- **T11 (CLAUDE.md slim, move threat-model + KDR table into the agents that read them)** is *strongly* supported. The HumanLayer and Builder.io guides both explicitly recommend this. The threat model belongs in `.claude/agents/security-reviewer.md` (or a referenced `agent_docs/threat_model.md`); the KDR table belongs adjacent to the dependency-auditor.
- **T12 (Skills extraction)** aligns directly with Anthropic's Agent Skills pattern (progressive disclosure, ~100 tokens of metadata at startup, full skill loads only on trigger). The ai-workflows Skills should each have a tight `description:` so Claude can route accurately, and the SKILL.md body should reference helper files rather than inlining them.

---

## LENS 3 — Model-Tier Dispatch (Haiku 4.5 / Sonnet 4.6 / Opus 4.6 / Opus 4.7)

### 3.1 Pricing and benchmark snapshot (April 2026)

| Model | Input / Output ($/M tok) | SWE-bench Verified | GPQA Diamond | Context | Notable |
|---|---|---|---|---|---|
| Haiku 4.5 | $1 / $5 | 73.3% | 73.8% | 200 K | 80–120 t/s, sub-500 ms TTFT, no `effort` param, manual thinking only |
| Sonnet 4.6 | $3 / $15 | 79.6% | 74.1% | 200 K (1 M beta) | Adaptive thinking; default `effort: high` (CC default `medium` after Mar 3 2026) |
| Opus 4.6 | $5 / $25 | 80.8% | 91.3% | 1 M (premium >200K) | Adaptive thinking; effort `low/medium/high/max`; 76% on 8-needle 1M MRCR v2 (vs Sonnet 4.5's 18.5%) |
| Opus 4.7 (Apr 16 2026) | $5 / $25 | 87.6% | — | 1 M | Adaptive-only; new `xhigh` effort; tokenizer 1.0–1.35× more tokens; tool errors 1/3 of 4.6 |

### 3.2 Where each tier earns its keep

**Haiku 4.5 is sufficient for:**
- Rule-based dispatch / file routing (the "is this a Python or YAML file" decision)
- Simple verification (does this file contain a TODO? does the diff have ≥1 added test?)
- High-volume classification, triage, extraction
- Built-in `Explore` sub-agent role (Anthropic ships Haiku as Claude Code's default `Explore` model)
- The "executor" tier in an Opus-or-Sonnet-orchestrator + Haiku-executor pattern (when each executor task is genuinely well-bounded)

Real production data (Caylent, Kilo Code, Verdent guides): Haiku 4.5 had **zero tool-calling failures** in side-by-side tests with GPT-5 Mini and GLM-4.6 on the same task; was 30–60% faster; cost roughly 1/3 of Sonnet on identical workflows. The OSWorld 50.7% number tells you it is *not* a frontier reasoner, but for ai-workflows' file-routing and gate-output-parsing roles this doesn't matter.

**Sonnet 4.6 is sufficient for:**
- Code generation up to and including most multi-file refactors
- Structured analysis with state tracking
- Orchestration / loop control
- All of M20's Builder role
- Most of M20's Auditor role on routine tasks (the 1.2-point SWE-bench gap to Opus is dwarfed by intra-prompt variance)
- Computer-use / GUI-agent workflows (72.5% on OSWorld vs Opus's 72.7% — statistically indistinguishable)

**Opus 4.6 is required for:**
- PhD-level scientific reasoning (the 17-point GPQA Diamond gap is the largest delta in the Claude lineup)
- Long-context reliability on 200K–1M contexts (8-needle MRCR v2: 76% vs Sonnet 4.5's 18.5% — a true qualitative jump, not benchmark noise)
- Novel problem solving (ARC-AGI-2: 68.8%, ~doubled vs Opus 4.5)
- Multi-file drift detection across 10+ files where small inconsistencies must be reconciled
- Hostile-spec analysis (where the spec itself contains adversarial framing or contradictions Claude must resolve)
- Agent Teams (Opus-only feature) when ai-workflows eventually wants peer-to-peer agent debate
- BrowseComp / agentic search at the frontier (84.0%)

**Opus 4.7 (Apr 16, 2026):** Worth flagging because of its explicit improvement on instruction-following and self-verification ("does proofs on systems code before starting work" — Vercel team observation). Tool errors dropped to ~1/3 of 4.6 levels. **Caveat from Mindstudio's Apr 2026 testing:** Opus 4.7 *regressed* on agentic search vs 4.6 (the regression is conspicuous by its absence from Anthropic's marketing) and is less generous in interpreting under-specified instructions ("scopes its work to what was asked rather than going above and beyond"). **For ai-workflows, Opus 4.7 is the better Auditor model than 4.6** — strict instruction-following plus better self-verification is exactly the Auditor profile. For the Builder role, 4.7's tighter literalism may actually be a small handicap.

### 3.3 Adaptive thinking + `effort` — the new dial

The most underweighted post-Opus-4.6 development for M20 is that **`thinking: max` is no longer a meaningful directive on its own.** The new mental model:

- `thinking: {type: "adaptive"}` lets the model decide *whether and how much* to think per turn.
- `effort` (`low | medium | high | max`, plus `xhigh` on 4.7) is a *behavioural signal*, not a strict token cap. Lower effort → fewer tool calls, fewer comments, shorter explanations; higher effort → deeper exploration.
- API default `effort` is `high`. Claude Code's default since Mar 3, 2026 is `medium` — which is the cause of the widely-reported "Claude Code felt off in March" episode (Stella Laurenzo's analysis of 6,852 sessions, 67% drop in reasoning tokens; Boris Cherny acknowledged the issue on HN). The fix users had to apply was an explicit `/effort high` (persistent) or `/effort max` (current-session-only, Opus 4.6+).

**For ai-workflows orchestrator runs, the recommended defaults are:**
- Builder turn (Sonnet 4.6): `effort: high` (medium is the right default for a chat session, not for autonomous code-writing where retries cost more than tokens)
- Auditor turn (Opus 4.6 or 4.7): `effort: high` for routine, `max` for hostile-spec / multi-file drift
- Sub-agent on Haiku: no `effort` param available — use prompt-level brevity directives

**Reduce `thinking: max` usage** (the user's stated optimization theme #6) translates concretely to: stop hardcoding the old `budget_tokens=32000` style anywhere in the agent prompts, migrate to adaptive, and reserve `effort: max` for the small set of Auditor invocations that need it (hostile-spec, multi-file drift, deep architectural reasoning).

### 3.4 Haiku-as-orchestrator: reality check

There is a recurring temptation — and several open-source routers (claude-router, KanseiLink) endorse it — to put Haiku at the top of the dispatch tree because routing decisions are cheap. The empirical evidence does **not** support this for ai-workflows-style workloads. Caylent's deep dive, Caylent's multi-agent guide, ClaudeFa.st's sub-agent best practices, and SolidNumber's SmartRouter writeup all converge on the same rule: **orchestrator agents never downgrade to Haiku.** The reason is that even a small input ("ship the next task") can trigger a complex multi-agent workflow, and the orchestrator needs the reasoning depth to (a) decompose correctly, (b) decide which sub-agent to spawn, (c) interpret returned summaries. SolidNumber's production data: routing errors at the orchestrator level have a cascading cost that dwarfs the per-token savings.

**The validated tier pattern post-Opus-4.6 is:**
- **Orchestrator: Sonnet 4.6** (the "default-Sonnet" half of M20-T07)
- **Sub-agents that do real reasoning (Builder, Auditor, sr-dev, sr-sdet, security-reviewer, architect): Sonnet 4.6 by default; Opus 4.6/4.7 on `--expert` override**
- **Sub-agents that do mechanical work (file routing, dependency lookups, simple "did the test pass" checks): Haiku 4.5**
- **Avoid Haiku for: roadmap-selector (needs prioritization reasoning), task-analyzer (needs to understand intent), auditor (needs to detect subtle wrongness)**

**Specific anti-pattern to avoid:** A live GitHub bug report (anthropics/claude-code #52502, Apr 23, 2026) documents that an "Opus orchestrator + Haiku-pinned sub-agents" Max-20x setup is depleting weekly limits 2–3× faster than expected. The user attributes it to one of (a) Opus orchestration billed as if it did the sub-agent work, (b) Haiku invocations silently routed to a more expensive model, or (c) a metering bug. Whatever the cause, **mixing tiers introduces accounting opacity** that ai-workflows should treat as a real risk: explicit per-cycle metering would be a worthwhile T-item addition.

### 3.5 Empirical Builder-Sonnet × Auditor-Opus shadow-audit (M20-T06)

This is exactly the right experiment to run, and Lens 3 is the lens that justifies it. The hypothesis to test on the 5 tasks:
- **H1 (cost):** Builder-Sonnet + Auditor-Opus < Builder-Opus + Auditor-Opus by ≥3× on token cost (per benchmarks: Sonnet input is 1/1.67× Opus, output is 1/1.67× Opus, and Sonnet typically writes shorter code → real-world ≈ 3–5×)
- **H2 (quality):** Auditor-Opus catches regressions Sonnet-Auditor would miss on the hostile/multi-file tasks; on routine tasks the two are within noise
- **H3 (latency):** Builder-Sonnet finishes 30–50% faster wall-clock (Sonnet TTFT 500–800 ms vs Opus 1–2 s; Sonnet token rate 40–60 t/s vs Opus 20–30 t/s)

If H1+H3 hold and H2 is bounded to a small set of identifiable task types, the GO decision for T07 (default-Sonnet + `--expert` override) is essentially mechanical. The literature suggests H1 and H3 will hold cleanly; H2 is the empirical question worth answering.

---

## SYNTHESIS — Mapping Findings to the M20 Task Pool

For each existing M20 task: **SUPPORT** (literature corroborates; ship as planned), **MODIFY** (literature suggests refinement), or **DROP** (newer best practice supersedes). Plus new candidates.

### T01 — Sub-agent return-value schema (3-line verdict/file/section)
**SUPPORT, with one addition.** The 3-line schema is exactly the Builder.io / MindStudio / Anthropic-multi-agent guidance ("structured, bounded, persisted"). **Modify:** make the schema enforced via the Claude Agent SDK's native `outputFormat: json_schema` rather than a free-text contract — this gets you automatic validation and retry, and the SDK fails closed on schema mismatch (which doubles as part of T08's "fail-closed on missing output").

### T02 — Sub-agent input prune (orchestrator-side scope discipline)
**SUPPORT, extend.** The literature (Anthropic, MindStudio, Haystack) is unanimous that pre-feeding bloat is the dominant token-waste source. **Extend:** add an explicit per-spawn token budget for sub-agent *output* (1–2 K for read-only sub-agents, 4 K for code-writing). Without an output cap the input prune just pushes the bloat downstream.

### T03 — In-task cycle compaction (cycle_summary.md per Auditor)
**SUPPORT.** This is Anthropic's note-taking / Memory primitive applied to a per-cycle granularity. **Modify slightly:** the cookbook recommends "maximize recall first, then iteratively prune for precision" when designing the summarization prompt. The cycle_summary.md template should ask for: state-as-of-now, what changed this cycle, open issues, decisions made (with rationale), files touched. The Anthropic compaction default summary prompt is a reasonable starting template.

### T04 — Cross-task iteration compaction (iter_<N>_shipped.md)
**SUPPORT.** Same primitive at coarser granularity. No changes recommended.

### T05 — Parallel terminal gate (sr-dev + sr-sdet + security-reviewer in one message; fragment files)
**STRONGLY SUPPORT.** This is the canonical parallel-fanout-with-fragment-aggregation pattern. **Extend:** require each gate to write to a deterministic fragment path (`.cycle/{agent}.verdict.md`) and have the orchestrator parse the three files in the next turn rather than relying on three return values arriving in a single response. This handles partial failure cleanly (T08).

### T06 — Shadow-Audit empirical study (Sonnet Builder × Opus Auditor on 5 tasks)
**STRONGLY SUPPORT.** The benchmark literature pre-judges this study to GO. The study is still worth running (in case ai-workflows' specific tasks live in the small set where Opus-4.6's deep reasoning matters at the Builder level), but the prior is that H1/H3 hold by wide margins. **Modify:** consider running 6 cells, not 2, to also test (Sonnet-Builder × Sonnet-Auditor) and (Opus-4.7-Builder × Opus-4.7-Auditor) — the Opus-4.7 cell is informative because Opus 4.7's stricter instruction-following may behave like a different Auditor than Opus 4.6.

### T07 — Dynamic model dispatch (conditional on T06 GO; default-Sonnet + --expert override)
**STRONGLY SUPPORT.** This is the validated production pattern. **Modify:** specify what `--expert` should do explicitly:
- Default: Sonnet 4.6, `effort: high`, adaptive thinking on
- `--expert`: Opus 4.6 (or 4.7 once stable for ai-workflows' workloads), `effort: max`, adaptive thinking on
- `--cheap` (new flag worth considering): Haiku 4.5 for the file-router and gate-output-parser roles
- **Never switch model mid-context** — escalate by spawning a fresh sub-agent.

### T08 — Gate-output integrity (parse raw stdout, fail-closed on missing output)
**SUPPORT.** Reinforced by the broader literature on prompt-injection defence (when sub-agent output is parsed naively, malformed or attacker-influenced output can subvert the gate). **Extend:** combine with structured-output enforcement (T01 modification) — the SDK's schema retry is the first line of defence; raw-stdout parsing with fail-closed is the second.

### T09 — Task-integrity safeguards (non-empty-diff check + independent gate re-run)
**SUPPORT.** No-change exits are a real failure mode in evaluator-optimizer loops (the model claims it's done without doing anything; ClaudeFa.st docs and Anthropic's own postmortems mention this). **Extend:** also assert non-empty *test* diffs when a feature is being added, since a Builder can satisfy a non-empty-diff check by editing a comment.

### T10 — Common-rules extraction (`.claude/agents/_common/non_negotiables.md`)
**SUPPORT.** This is exactly the AGENTS.md / progressive-disclosure pattern recommended by the Linux Foundation, Builder.io, HumanLayer, and Claude Code docs. **Extend:** make `non_negotiables.md` referenced explicitly by each agent's frontmatter, and keep it under 500 tokens (the "altitude" guidance from Anthropic's context-engineering post). If it grows past that, split into per-domain non-negotiables.

### T11 — CLAUDE.md slim (move threat-model + KDR table into the agents that read them)
**STRONGLY SUPPORT.** This is the most universally-recommended pattern in the 2026 literature (HumanLayer, Builder.io, Anthropic Claude Code best-practices, MindStudio). The threat-model into `security-reviewer.md`, the KDR table into `dependency-auditor.md`. CLAUDE.md should become a one-page index with pointers.

### T12 — Skills extraction (per-agent capabilities — test-quality eval, dep-audit shortcuts)
**SUPPORT.** Anthropic's Agent Skills is the explicit endorsement of this pattern. **Modify:** structure each Skill with the canonical SKILL.md frontmatter (`name:`, `description:` — keep description tight, this is the routing key) plus a body that references helper files rather than inlining them. Test by deliberately *omitting* the Skill and confirming Claude underperforms — that proves the Skill is doing real work.

### T13–T16 — New commands (/triage, /check, /ship, /sweep)
**SUPPORT.** These are slash-command orchestrators in the Claude Code idiom and exactly what the platform is built for. **Modify:** structure them as Skills (`.claude/skills/triage/`, etc.) so each command is auto-discoverable, has frontmatter routing, and can be invoked manually or auto-triggered. The 2026 unification of slash-commands and Skills is documented in the Claude Code docs ("Files in `.claude/commands/` still work, but the recommended approach is `.claude/skills/`").

### T17–T19 — Parallel-builders foundation (spec format extension + worktree spawn + close-out)
**STRONGLY SUPPORT.** Native worktree support shipped in Claude Code v2.1.49 (Feb 19, 2026); `isolation: worktree` is now a sub-agent frontmatter field with auto-cleanup. **Modify:** lean on the native primitive rather than building a custom worktree spawner. The recommended pattern from MindStudio / The Prompt Shelf / Verdent: per-feature naming convention, `--worktree feat-{ticket}` form, PR-per-agent close-out, explicit `git worktree remove` on success. **Constraint to call out:** parallelism beyond 4–5 worktrees on shared infrastructure (databases, ports) requires per-worktree isolation of those resources — this is the "five pillars" issue discussed in the parallel-development guides. ai-workflows should bound concurrency at 3–4 builders unless a per-worktree DB/port story exists.

### T20 — Carry-over checkbox-cargo-cult catch
**SUPPORT.** This is a known failure mode in evaluator-optimizer loops and in long-running automated tasks (Nicholas Rhodes / Nate Jones "automated task bloat" point: build-and-forget pipelines accumulate cruft that "looks correct" but isn't efficient or rigorous). **Extend:** the check should run periodically (not only at iteration boundaries) and should specifically inspect whether: (a) a checkbox got marked done without a corresponding diff/test/file artifact, (b) two consecutive cycles produced near-identical outputs (the loop is spinning), (c) the Auditor is rubber-stamping (every verdict is PASS). Each of those is a documented failure mode.

---

## NEW TASK CANDIDATES (suggested additions to M20)

### T21 — Migrate to adaptive thinking + `effort` parameter
**Why:** `thinking: {type: "enabled", budget_tokens: N}` is deprecated on Opus 4.6 / Sonnet 4.6 and rejected with 400 on Opus 4.7. Any ai-workflows code that hardcodes `budget_tokens` will break on the next model migration. **Action:** Replace all `budget_tokens` configurations with `thinking: {type: "adaptive"}` plus per-role `effort` settings (Builder: `high`; Auditor: `high` routine / `max` hostile-spec; sub-agents on Haiku: no `effort`, prompt-level brevity).

### T22 — Per-cycle token + cost telemetry per agent
**Why:** Current ai-workflows has no per-agent cost breakdown. The GitHub bug #52502 (Apr 2026) shows even Anthropic's own usage dashboard is opaque about which model in a multi-agent stack consumed what. **Action:** Wrap each sub-agent invocation with a small wrapper that captures `cache_read_input_tokens`, `cache_creation_input_tokens`, `input_tokens`, `output_tokens`, model name, effort level. Persist to `.cycle/{agent}.usage.json` alongside the verdict. Aggregate into iter_<N>_shipped.md. This is the basis for evidence-based decisions on T07's defaults.

### T23 — Cache-breakpoint discipline
**Why:** The literature shows wrongly-placed cache breakpoints can 5–20× a session's input cost (anthropics/claude-code issues #34629, #42338, #43657). **Action:** Pin the orchestrator's cache breakpoint on the *last stable block* (the loaded non_negotiables + agent system prompt + tool definitions), explicitly *before* the dynamic per-cycle context. Verify with a one-shot test: send the same orchestrator prompt twice and confirm `cache_read_input_tokens` ≈ the static prefix size on call 2. If it's 0, the breakpoint is wrong.

### T24 — MD-file discoverability audit (search-by-section)
**Why:** Lens 2.3 — sub-agents pull on demand; the MD files must be structured for that. **Action:** For every file in `agent_docs/` and `.claude/agents/*.md`, ensure: (a) one topic per file, (b) ≤500-token sections with `##` heading anchors, (c) a top-of-file 3-line summary, (d) no inline code (link to `src/foo.py:42` instead). This is one-time work that pays off every time a sub-agent has to find something.

### T25 — Periodic skill/scheduled-task efficiency audit (citing Nate Jones / Nicholas Rhodes pattern)
**Why:** Build-and-forget agents accumulate token waste invisibly because correct output and efficient output look identical from outside. **Action:** Run a quarterly audit prompt over each Skill and slash-command in ai-workflows that asks: are there redundant tool round-trips? Are we screenshotting where text-extraction would work? Are we re-reading files we already have in memory? Are we declaring tools so ToolSearch isn't needed? Treat the output as a normal PR review.

### T26 — Adopt Anthropic's two-prompt long-running pattern for multi-cycle Builder runs
**Why:** Anthropic's "Effective harnesses for long-running agents" (2026) shows that long-running agents fail in two reproducible ways without an *initializer* + *coding-agent* split: (1) trying to one-shot the work and running out of context mid-implementation, (2) leaving features half-implemented and undocumented for the next session. **Action:** For multi-cycle Builder runs (≥3 cycles), introduce a one-shot initializer prompt that produces a `iter_<N>_plan.md` and `iter_<N>_progress.md`, then have each subsequent Builder cycle update *only* the progress file. This is a slightly stronger pattern than T03/T04 alone.

### T27 — Tool-result clearing for long Auditor runs
**Why:** Anthropic's `clear_tool_uses_20250919` strategy is the right primitive for the Auditor's heavy file-read pattern. The Auditor reads many files per cycle to verify; once it has formed its verdict, the raw file contents are dead weight. **Action:** Configure `context_management.edits` with `clear_tool_uses_20250919` and a `keep` window of the most recent 3–5 tool results, so that older grep/read outputs are dropped while the Auditor's reasoning is preserved. Set `clear_at_least` high enough that the cache invalidation pays for itself.

---

## CONTRADICTIONS WITH PRE-OPUS-4.6 CONVENTIONAL WISDOM (call-outs)

The following beliefs were widely held in 2024–early 2025 and are now superseded:

1. **"Pre-load everything into the 200 K context, the model can handle it."** Superseded by context rot and the n² attention budget framing (Anthropic, Sep 2025; Apr 2026 cookbook). Smaller, on-demand loads outperform.
2. **"Set `budget_tokens` high for hard problems."** Superseded by adaptive thinking. Manual `budget_tokens` is deprecated on 4.6 and rejected on 4.7.
3. **"Opus is required for serious code-writing."** Superseded by Sonnet 4.6's 1.2-point SWE-bench gap to Opus 4.6 at 1/5 the cost. Sonnet is now the default for Builder roles, with Opus reserved for genuinely hard reasoning (GPQA-class, multi-file drift, hostile spec).
4. **"More agents in parallel = more throughput."** Anthropic's own data (multi-agent systems use ~15× tokens vs chat) plus the coding-task observation (*"most coding tasks involve fewer truly parallelizable tasks than research"*) say: parallelize selectively, where work is genuinely independent. Over-parallelization burns tokens for negative gain.
5. **"Big CLAUDE.md is good — give the agent everything."** Strongly superseded. Every 2026 source recommends a thin index + per-topic referenced files. The HumanLayer guide and Anthropic's own best-practices doc are explicit on this.
6. **"Haiku as orchestrator is the cheap optimization."** Empirically wrong for non-trivial workflows. Haiku as executor + Sonnet as orchestrator is the validated tier.
7. **"Conversation history accumulates and that's fine."** Superseded by mandatory compaction primitives. Long autonomous loops *will* hit context-window pressure; planning for compaction (server-side or file-based memory) is now table stakes, not a future optimization.
8. **"The Task tool / sub-agents make Claude smarter."** Superseded by the more accurate framing: sub-agents *isolate context* and let you spend more total tokens without paying the rot penalty. Same model, more compute, parallelism. The 90% gain in the Anthropic research system was almost entirely explained by token throughput, not by model capability uplift from the architecture itself.

---

## RISK FLAGS (worth tracking, not yet actionable)

- **Opus 4.7 tokenizer change.** 1.0–1.35× more tokens per byte than 4.6. Direct cost implication for any switch. Wait for Opus 4.7 to settle before making it the default `--expert` model; 4.6 remains the safer choice through Q2 2026.
- **Claude Code default-effort drift.** The Mar 3 → Apr 7, 2026 episode where the Claude Code default `effort` was lowered to `medium` and quality regressed shows that ai-workflows should *explicitly* set `effort` rather than relying on Claude Code's defaults, which can change without warning.
- **Cache-invalidation bugs in Claude Code resume.** Issues #27048, #34629, #42338, #43657 document that `--continue`/`--resume` can blow up the cache. ai-workflows should prefer fresh-session invocations for the orchestrator over `--continue`, and rely on the file-based memory pattern (T03/T04) for continuity.
- **Anthropic's metering opacity.** Bug #52502 (Apr 23, 2026) suggests Opus-orchestrator + Haiku-pinned-subagent setups burn weekly limits faster than expected, with no per-model breakdown in the dashboard. T22 (per-cycle telemetry) addresses this from ai-workflows' side; the upstream issue may also resolve.

---

## Sources Consulted (representative, not exhaustive)

**Anthropic official engineering and docs:** "How we built our multi-agent research system" (anthropic.com/engineering/multi-agent-research-system); "Building effective agents" (anthropic.com/research/building-effective-agents); "Effective context engineering for AI agents" (Sep 29, 2025); "Effective harnesses for long-running agents" (anthropic.com/engineering/effective-harnesses-for-long-running-agents); "Equipping agents for the real world with Agent Skills"; "Building agents with the Claude Agent SDK"; "Writing effective tools for AI agents"; "Introducing Claude Opus 4.6" (Feb 5, 2026); Claude Code docs (`code.claude.com/docs/en/sub-agents`, `agent-teams`, `common-workflows`, `best-practices`); Claude API Docs (`platform.claude.com/docs/en/build-with-claude/prompt-caching`, `compaction`, `context-editing`, `adaptive-thinking`, `effort`, `extended-thinking`, agent-sdk pages); Claude Cookbooks (`tool-use-automatic-context-compaction`, `tool-use-context-engineering`); "What's new in Claude Opus 4.7" (`platform.claude.com/docs/en/about-claude/models/whats-new-claude-4-7`).

**LangChain / LangGraph:** `docs.langchain.com/oss/python/langgraph/workflows-agents`; LangChain Deep Agents vs Claude Agent SDK comparison (Apr 16, 2026); langchain.com/langgraph; multiple practitioner posts citing 2026 LangGraph 1.1 patterns.

**Independent practitioners (post-Opus-4.6):** Nate B. Jones (natebjones.com; substack including "Stop Burning Tokens: The Contract-First Prompting Blueprint" and "Your Claude Sessions Cost 10x What They Should") and the OB1/Open Brain repository (github.com/NateBJones-Projects/OB1) — Zettelkasten-style atomic-note pattern for searchable agent context; Nicholas Rhodes ("I found 350,000 tokens hiding in plain sight," Apr 2026, citing Jones); Vellum benchmark coverage of Opus 4.6 and 4.7; Caylent ("Claude Haiku 4.5 Deep Dive: Cost, Capabilities, and the Multi-Agent Opportunity"); MindStudio guides (sub-agents for codebase analysis, Claude Code Agent Teams, git worktrees, context compounding); Builder.io ("Subagents: When and How to Use Them", "How to Write a Good CLAUDE.md File", AGENTS.md); HumanLayer ("Writing a good CLAUDE.md"); ClaudeFa.st (sub-agent best practices, agent teams setup); AddyOsmani.com ("The Code Agent Orchestra"); Verdent guides (Claude Opus 4.7 vs 4.6 comparison; Claude Code worktree); Simon Willison's coverage of the Anthropic multi-agent post; Constellation Research; ZenML LLMOps Database case study; PubNub production sub-agent setup; "Claude Code Felt Off for a Month" (DEV Community postmortem, citing Anthropic's own postmortem on the Mar 26 cache-invalidation bug); Pasquale Pillitteri's documentation of the Mar 3, 2026 Claude Code default-effort change and Boris Cherny's HN response; Anthropic Claude Code GitHub issues #27048, #34629, #42338, #43657, #52502; arXiv 2601.06007 ("Don't Break the Cache: An Evaluation of Prompt Caching for Long-Horizon Agentic Tasks").

**Cross-reference: Anthropic AGENTS.md / progressive-disclosure standard:** open standard at agentskills.io; progressive-disclosure deep dives (mcpjam.com, leehanchung.github.io, github.com/travisvn/awesome-claude-skills).
