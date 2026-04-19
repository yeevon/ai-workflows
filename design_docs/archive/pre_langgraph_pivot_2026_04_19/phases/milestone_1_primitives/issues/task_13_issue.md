# Task 13 — `claude_code` Subprocess Design-Validation Spike — Audit Issues

**Source task:** [../task_13_claude_code_spike.md](../task_13_claude_code_spike.md)
**Audited on:** 2026-04-19 (cycle 1)
**Audit scope:** Full scope. Inspected the task file, the M1 README, the
M1 exit-criteria audit, every sibling task_NN_issue.md (for consistency),
pyproject.toml, CHANGELOG.md, .github/workflows/ci.yml, both claimed
files (`scripts/spikes/claude_code_poc.py`,
`scripts/m1_smoke.py`), the new M4 task
(`design_docs/phases/milestone_4_orchestration/task_00_claude_code_launcher.md`),
the updated M4 README, and the M1 exit-criteria audit file after the
spike's RESOLVED flips. Verified AC-1..AC-8 against the git diff and the
live CLI. Re-ran the three CI gates locally (`uv run pytest`,
`uv run lint-imports`, `uv run ruff check .`) plus two targeted probes
(direct `--temperature` rejection; import + introspection of
`pydantic_ai.models.Model`) to pressure-test the findings.
**Status:** ✅ PASS. All eight ACs answered with concrete observed
evidence. No OPEN HIGH / MEDIUM issues. One 🟢 LOW noted as a forward-
looking improvement for the M4 Task 00 builder; it does not block
sealing Task 13.

---

## AC grading

| AC | Verdict | Evidence |
| --- | --- | --- |
| **AC-1 — CLI surface** | ✅ PASS | Findings § AC-1 names the canonical argv and documents every flag from live CLI output (`claude` v2.1.114). Gotcha on `--bare` vs. Max-sub auth called out. Exit-code caveat (`is_error` field is the truth-bearer) captured. Wall-time budget documented. |
| **AC-2 — Token usage** | ✅ PASS | `usage` field shape documented; 1:1 mapping to `TokenUsage` spelled out; `modelUsage` sub-agent split and "one record per sub-model" decision explicit; `modelUsage`-absent fallback covered. |
| **AC-3 — Model ABC vs. bypass** | ✅ PASS | Confirm-subclass decision with three orthogonal justifications (round-trip observed; ABC signature confirmed via live import during audit — see § Audit verification; silent tool-drop risk). Sketched prototype present. `supports_tool_registry` capability flag introduced. Streaming explicitly deferred with rationale. |
| **AC-4 — Flag mapping** | ✅ PASS | Per-field table lists `model`, `system_prompt`, `max_tokens`, `temperature` with live-observed status. Direct `--temperature` rejection verified in audit (see § Audit verification) — no longer an inference. Three concrete actions carried over to M4 Task 00 (validator, tiers.yaml edit, new `system_prompt` field). |
| **AC-5 — Error taxonomy** | ✅ PASS | Seven failure modes mapped to Task 10's 3-bucket taxonomy. Directly observed: invalid model id, unknown flag, auth lost (`--bare` accident). Inferred (rate-limit, 5xx, timeout): flagged explicitly as "not directly observed on Max-sub single-token prompt" so the M4 builder doesn't mistake inference for proof. Pattern-match-on-`result`-text fragility called out as an M4 follow-up if/when the CLI gains a structured error-code field. |
| **AC-6 — Propagation output** | ✅ PASS | Confirm-path. New task [`design_docs/phases/milestone_4_orchestration/task_00_claude_code_launcher.md`](../../milestone_4_orchestration/task_00_claude_code_launcher.md) created, sequenced first in the M4 README, Carry-over from M1 Task 13 spike section encodes every decision. M1-EXIT-ISS-02 flipped ✅ RESOLVED with pointer. |
| **AC-7 — H-1 ruff reorder bundled** | ✅ PASS | `uv run ruff check .` returns "All checks passed!" `scripts/m1_smoke.py` has imports above `load_dotenv()`; the comment above the `load_dotenv()` call explains *why* the ordering is correct (env-var reads in `ai_workflows.*` are in function bodies, not at module import). No `# noqa: E402` added and no `scripts/` ruff exclusion — matches the AC's "import reorder, not a suppression." |
| **AC-8 — No production code changed** | ✅ PASS | `git diff --stat HEAD -- ai_workflows/ tiers.yaml pricing.yaml design_docs/phases/milestone_4_orchestration/task_0{1..6}_*.md` returns empty. The only files modified are: a new spike script (`scripts/spikes/claude_code_poc.py`, ruff-excluded), a new M4 task file, an import reorder in the existing `scripts/m1_smoke.py`, a ruff exclude in `pyproject.toml`, the M4 README ordering, the task 13 spec itself (Findings), the M1 audit file (flips), and `CHANGELOG.md`. All align with the spec. |

## Gate summary

| Gate | Command | Result |
| --- | --- | --- |
| pytest | `uv run pytest -x -q` | 345 passed, 1 skipped, 2 warnings (pre-existing sqlite3 datetime deprecation — not a Task 13 regression). |
| import-linter | `uv run lint-imports` | 2 contracts kept, 0 broken. |
| ruff | `uv run ruff check .` | All checks passed. |
| spike-specific: live CLI round-trip | `uv run python scripts/spikes/claude_code_poc.py` | Three success probes returned `is_error: false`; two failure probes matched the documented error shapes; one `--system-prompt` probe returned "BANANA" as specified. |
| spike-specific: `pydantic_ai.models.Model` import + shape check | `uv run python -c "from pydantic_ai.models import Model; ..."` | Abstract methods: `{"request", "model_name", "system"}`. `request()` signature matches the sketch (argument name is `model_request_parameters`, not `request_parameters`, but semantically identical). |
| spike-specific: direct `--temperature` rejection | `claude -p --model haiku --temperature 0.5 ... "hello"` | `error: unknown option '--temperature'` — direct confirmation of the AC-4 inference. |

## Audit verification — probes beyond the PoC

The audit ran three extra probes that weren't in the original PoC, to
convert two "inferred" findings into "directly observed" findings. The
spec for Task 13 only required the PoC scope, so these are audit-added
rigour, not pre-spike deliverables:

1. **`pydantic_ai.models.Model` introspection** — confirmed the ABC
   exists, is abstract, exposes `request`, `model_name`, and `system` as
   abstract methods, and that `request()`'s signature matches the
   sketched prototype (tightens AC-3 from "pseudocode sketch" toward
   "sketch validated against the real ABC").
2. **Direct `--temperature` probe** — confirmed the CLI emits
   `error: unknown option '--temperature'` on exit 1, matching the
   `--max-tokens` shape. AC-4's finding for `temperature` was
   originally inferred from `claude --help` having no such flag; the
   audit upgraded it to direct observation. The finding text was
   amended in `task_13_claude_code_spike.md:AC-4 flag table` during
   the audit (not a new finding — just a rigour upgrade).
3. **`git diff --stat` against protected production files** — confirmed
   zero bytes changed in `ai_workflows/`, `tiers.yaml`, `pricing.yaml`,
   and M4 `task_01..06`. AC-8 holds.

## Additions beyond spec — audited and justified

| Addition | Rationale |
| --- | --- |
| `pyproject.toml`: `[tool.ruff]` `extend-exclude = ["scripts/spikes"]` | The spike file said "if import-ordering forces it, a per-file ignore plus a comment"; the implementation chose a directory-level exclude so future spikes can be added without re-editing ruff config each time. Comment in pyproject.toml explains the exclusion is scoped to throwaway design-validation code. Justified — does not hide lint drift from any production path. |
| M4 README task-order renumbering | The new `task_00_claude_code_launcher` shifts `task_01..06` positions in the listing (the file names stay the same). Unavoidable consequence of "sequenced before task_01_planner." |
| Amending M1-EXIT-ISS-01 ("H-1") to ✅ RESOLVED alongside M1-EXIT-ISS-02 | Task 13 AC-7 explicitly bundles H-1; flipping M1-EXIT-ISS-02 only would leave M1-EXIT-ISS-01 OPEN on a fix that already landed. The flip is symmetrical with the Task 13 scope. |

## Issue log — cross-task follow-up

| ID | Severity | Owner / next touch | Status |
| --- | --- | --- | --- |
| M1-T13-ISS-01 | 🟢 LOW | M4 Task 00 builder | OPEN — suggests the launcher use `--setting-sources ""` (no-arg form in `claude --help`: `--setting-sources <sources>  Comma-separated list of setting sources to load (user, project, local).`) in addition to `--tools ""` and `--no-session-persistence`, to make the subprocess fully hermetic. The spike mentioned this as optional; the M4 builder should decide whether to default-on or leave it to caller config. Not blocking Task 13 seal. |

## 🔴 HIGH

_None._

## 🟡 MEDIUM

_None._

## 🟢 LOW

### M1-T13-ISS-01 — Launcher may want `--setting-sources ""` for full hermeticity

**Where:** `design_docs/phases/milestone_4_orchestration/task_00_claude_code_launcher.md` § Carry-over → CLI surface.

The spike documents `--tools ""` + `--no-session-persistence` as the
hermetic-invocation flag set. `claude --help` also exposes
`--setting-sources <sources>` which can be passed with an empty string
(or a curated whitelist) to prevent user / project settings from
leaking into the subprocess. For a production orchestrator that wants
perfectly reproducible subprocess calls, this is worth considering.

**Action / Recommendation:** the M4 Task 00 builder should try passing
`--setting-sources ""` in an exploration probe and decide whether to
default it on. If the CLI accepts an empty string, bake it into the
canonical argv. If it rejects, pass `--setting-sources user` (inherit
only user-level settings, not project `CLAUDE.md` or `.mcp.json`). Add
to the launcher's AC-1 equivalent as a checkbox. Does not block the
Task 13 seal — the current hermetic flags are sufficient for the
design-validation PoC and leave the decision open for the
implementation.

---

**Bottom line:** Task 13 is ✅ PASS, cycle 1 clean. No re-implement
pass needed. `/clean-implement m1 task 13` terminates here with stop
condition 3 (CLEAN).
