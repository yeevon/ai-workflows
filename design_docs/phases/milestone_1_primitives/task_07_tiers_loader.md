# Task 07 — Tiers Loader and Workflow Hash

**Issues:** P-21, P-22, P-23, P-24, P-25, CRIT-02

## What to Build

Two things:
1. `tiers.yaml` + `pricing.yaml` loader with env var expansion and profile overlay
2. Workflow directory content hash utility (for CRIT-02 resume safety)

## Deliverables

### `tiers.yaml`

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
    temperature: 0.1

  haiku:
    provider: anthropic
    model: claude-haiku-4-5-20251001
    max_tokens: 4096
    temperature: 0.1

  local_coder:
    provider: ollama
    model: qwen2.5-coder:32b
    base_url: "${OLLAMA_BASE_URL:-http://192.168.1.X:11434}"
    max_tokens: 8192
    temperature: 0.1

  gemini_flash:
    provider: openai_compat
    model: gemini-2.0-flash
    base_url: "https://generativelanguage.googleapis.com/v1beta/openai/"
    api_key_env: GEMINI_API_KEY
    max_tokens: 8192
    temperature: 0.1
```

### `tiers.local.yaml` (gitignored)

```yaml
tiers:
  local_coder:
    base_url: "http://localhost:11434"
```

### `pricing.yaml`

```yaml
pricing:
  claude-opus-4-7:
    input_per_mtok: 15.00
    output_per_mtok: 75.00
    cache_read_per_mtok: 1.50
    cache_write_per_mtok: 18.75
  claude-sonnet-4-6:
    input_per_mtok: 3.00
    output_per_mtok: 15.00
    cache_read_per_mtok: 0.30
    cache_write_per_mtok: 3.75
  claude-haiku-4-5-20251001:
    input_per_mtok: 0.80
    output_per_mtok: 4.00
    cache_read_per_mtok: 0.08
    cache_write_per_mtok: 1.00
  gemini-2.0-flash:
    input_per_mtok: 0.10
    output_per_mtok: 0.40
  qwen2.5-coder:32b:
    input_per_mtok: 0.0
    output_per_mtok: 0.0
```

### `primitives/tiers.py`

```python
class TierConfig(BaseModel):
    provider: Literal["anthropic", "ollama", "openai_compat", "google"]
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

- [ ] `load_tiers()` expands `${OLLAMA_BASE_URL:-default}` from env
- [ ] `--profile local` overlay overrides only declared keys
- [ ] `compute_workflow_hash()` is deterministic (same dir → same hash)
- [ ] Hash changes when any content file changes (test: touch prompt, hash differs)
- [ ] `__pycache__` changes do NOT affect the hash
- [ ] Unknown tier raises `UnknownTierError`
- [ ] `sonnet` tier has `temperature: 0.1` (P-22 oversight fixed)

## Dependencies

- Task 01 (scaffolding)
