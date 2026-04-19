# Task 07 — Tiers Loader and Workflow Hash

**Status:** ✅ Complete (2026-04-18) — see
[issues/task_07_issue.md](issues/task_07_issue.md).

**Issues:** P-21, P-22, P-23, P-24, P-25, CRIT-02

## What to Build

Two things:
1. `tiers.yaml` + `pricing.yaml` loader with env var expansion and profile overlay
2. Workflow directory content hash utility (for CRIT-02 resume safety)

## Deliverables

### `tiers.yaml`

> **Provider strategy:** Claude tiers (`opus`, `sonnet`, `haiku`) run via the
> `claude` CLI using the developer's Claude Max subscription — no Anthropic API
> key required. The `claude_code` provider type is defined here; its
> implementation (subprocess launcher) lands in M4 with the Orchestrator
> component. `gemini_flash` is the paid-API overflow tier, used only when both
> `haiku` and `local_coder` cannot handle a task. `local_coder` (Qwen) is free
> and private.

```yaml
tiers:
  # Orchestration tier — drives multi-step workflows, long-horizon planning.
  # Uses Claude Max subscription via `claude` CLI (no API key).
  opus:
    provider: claude_code
    model: claude-opus-4-7
    max_tokens: 8192
    temperature: 0.1

  # Implementation tier — large/complex code generation, multi-file edits.
  # Uses Claude Max subscription via `claude` CLI.
  sonnet:
    provider: claude_code
    model: claude-sonnet-4-6
    max_tokens: 8192
    temperature: 0.1

  # Fast Claude tier — simple single-turn tasks, classification, routing.
  # Uses Claude Max subscription via `claude` CLI.
  haiku:
    provider: claude_code
    model: claude-haiku-4-5-20251001
    max_tokens: 4096
    temperature: 0.1

  # Local coding tier — free, private, runs on LAN Ollama instance.
  # First choice for coding tasks; zero API cost.
  local_coder:
    provider: ollama
    model: qwen2.5-coder:32b
    base_url: "${OLLAMA_BASE_URL:-http://192.168.1.100:11434/v1}"
    max_tokens: 8192
    temperature: 0.1

  # Overflow / last-resort tier — paid Gemini API (GEMINI_API_KEY).
  # Used only when both haiku AND local_coder cannot handle the task.
  gemini_flash:
    provider: openai_compat
    model: gemini-2.0-flash
    base_url: "https://generativelanguage.googleapis.com/v1beta/openai/"
    api_key_env: GEMINI_API_KEY
    max_tokens: 4096
    temperature: 0.1
```

### `tiers.local.yaml` (gitignored)

```yaml
tiers:
  local_coder:
    base_url: "http://localhost:11434/v1"
```

### `pricing.yaml`

```yaml
pricing:
  # Claude tiers: billed via Max subscription, not per-token API.
  # Record as $0 for cost-tracker purposes; budget cap applies to API tiers only.
  claude-opus-4-7:
    input_per_mtok: 0.0
    output_per_mtok: 0.0
  claude-sonnet-4-6:
    input_per_mtok: 0.0
    output_per_mtok: 0.0
  claude-haiku-4-5-20251001:
    input_per_mtok: 0.0
    output_per_mtok: 0.0
  # Gemini overflow tier — billed per token (verify at console.cloud.google.com)
  gemini-2.0-flash:
    input_per_mtok: 0.10
    output_per_mtok: 0.40
  # Local models: zero cost, excluded from budget-cap enforcement
  qwen2.5-coder:32b:
    input_per_mtok: 0.0
    output_per_mtok: 0.0
```

### `primitives/tiers.py`

```python
class TierConfig(BaseModel):
    provider: Literal["claude_code", "ollama", "openai_compat", "google"]
    # claude_code → subprocess `claude` CLI (Max subscription, no API key)
    # ollama      → local Ollama server (Qwen, free)
    # openai_compat → Gemini via openai-compat endpoint (GEMINI_API_KEY, paid)
    # google      → native Google SDK (reserved, not used in default tiers)
    model: str
    max_tokens: int
    temperature: float
    base_url: str | None = None
    api_key_env: str | None = None
    max_retries: int = 3  # number of retries by OUR retry layer; SDK is always 0


def load_tiers(profile: str | None = None) -> dict[str, TierConfig]: ...
def load_pricing() -> dict[str, ModelPricing]: ...
```

### `primitives/workflow_hash.py` (CRIT-02)

```python
import hashlib
from pathlib import Path

def compute_workflow_hash(workflow_dir: str) -> str:
    """
    Return a deterministic hash of every file in the workflow directory.

    Covers workflow.yaml, prompts/, schemas/, custom_tools.py — anything
    whose change should invalidate a resume.

    Algorithm: SHA-256 over sorted (path, content) pairs.
    """
    h = hashlib.sha256()
    root = Path(workflow_dir)
    for path in sorted(root.rglob("*")):
        if path.is_file() and not _is_ignored(path):
            rel = path.relative_to(root).as_posix()
            h.update(rel.encode())
            h.update(b"\0")
            h.update(path.read_bytes())
            h.update(b"\0\0")
    return h.hexdigest()
```

**Ignored patterns:** `__pycache__/`, `*.pyc`, `.DS_Store`, `*.log`. Everything else contributes to the hash.

Stored in the `runs.workflow_dir_hash` column. On `aiw resume <run_id>`:

1. Read stored hash from run record
2. Compute current hash from workflow directory
3. If different: print diff summary, refuse unless `--force-workflow-version-mismatch`

## Acceptance Criteria

- [x] `load_tiers()` expands `${OLLAMA_BASE_URL:-default}` from env
- [x] `--profile local` overlay overrides only declared keys
- [x] `compute_workflow_hash()` is deterministic (same dir → same hash)
- [x] Hash changes when any content file changes (test: touch prompt, hash differs)
- [x] `__pycache__` changes do NOT affect the hash
- [x] Unknown tier raises `UnknownTierError`
- [x] `sonnet` tier has `temperature: 0.1` (P-22 — restored to original tier name)

## Dependencies

- Task 01 (scaffolding)

## Carry-over from prior audits

Forward-deferred items owned by this task. Treat each entry like an
additional acceptance criterion and tick it when resolved.

- [x] **M1-T03-ISS-12** — `TierConfig.max_retries` field decision. Resolved
  as option (a): the field is kept and wired through `load_tiers()` so it
  roundtrips from YAML → `TierConfig` (see
  `test_tier_config_max_retries_roundtrips_through_load_tiers` and
  `test_tier_config_max_retries_default_is_three` in
  [tests/primitives/test_tiers_loader.py](../../../../tests/primitives/test_tiers_loader.py)).
  Task 10 (`retry_on_rate_limit`) will read this per-tier at retry time;
  SDK clients remain `max_retries=0` per CRIT-06. The decision and
  rationale are pinned in the `TierConfig` docstring in
  [ai_workflows/primitives/tiers.py](../../../../ai_workflows/primitives/tiers.py).
  Source: [issues/task_03_issue.md](issues/task_03_issue.md) — LOW.
