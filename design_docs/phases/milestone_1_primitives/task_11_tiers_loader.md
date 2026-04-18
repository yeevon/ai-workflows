# Task 11 — Tiers Loader

**Issues:** P-21, P-22, P-23, P-24, P-25

## What to Build

Load and validate `tiers.yaml` and `pricing.yaml` at run start. Snapshot the loaded config — no hot-reload mid-run. Support `--profile` overlay for local dev.

## Deliverables

### `tiers.yaml` (canonical)
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

### `tiers.local.yaml` (gitignored, for desktop dev)
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
    provider: Literal["anthropic", "ollama", "openai_compat"]
    model: str
    max_tokens: int
    temperature: float
    base_url: str | None = None
    api_key_env: str | None = None


def load_tiers(profile: str | None = None) -> dict[str, TierConfig]:
    """Load tiers.yaml, apply profile overlay if given, expand env vars."""
    ...


def build_client(tier_name: str, tiers: dict[str, TierConfig]) -> LLMClient:
    """Instantiate the correct adapter for the given tier."""
    ...
```

**Env var expansion:** `${VAR:-default}` syntax in `base_url` is expanded at load time using `os.environ`.

**Profile overlay:** `--profile local` loads `tiers.local.yaml` and deep-merges it over `tiers.yaml`. Only declared keys are overridden.

**Snapshot:** Tiers are loaded once at run start and passed around as immutable config. No re-reading during a run.

## Acceptance Criteria

- [ ] `load_tiers()` returns a validated dict of `TierConfig` objects
- [ ] `${OLLAMA_BASE_URL:-default}` expands correctly from env
- [ ] Profile overlay overrides only declared keys, leaves others intact
- [ ] `build_client("sonnet", tiers)` returns an `AnthropicClient` instance
- [ ] `build_client("local_coder", tiers)` returns an `OllamaClient` instance
- [ ] Unknown tier name raises `UnknownTierError` with the name

## Dependencies

- Tasks 03, 04, 05 (adapters)
