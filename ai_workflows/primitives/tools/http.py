"""HTTP stdlib tool — single ``http_fetch`` covering GET/POST/etc.

Produced by M1 Task 06 (P-18). There is intentionally *one* HTTP tool,
not a matrix of ``http_get`` / ``http_post`` / ``http_delete``: the method
is a parameter, and the model receives the same return shape regardless
of verb. This keeps the registry surface narrow and the forensic log
analysis uniform.
"""

from __future__ import annotations

import httpx
from pydantic_ai import RunContext

from ai_workflows.primitives.llm.types import WorkflowDeps

__all__ = ["http_fetch"]


_TRUNCATION_SUFFIX = "\n... [truncated]"


def http_fetch(
    ctx: RunContext[WorkflowDeps],
    url: str,
    method: str = "GET",
    max_chars: int = 50_000,
    timeout: int = 30,
) -> str:
    """Perform ``method url`` and return ``"HTTP {code}\\n{body}"`` as a string.

    The body is truncated at ``max_chars`` with a marker suffix; network
    errors (timeouts, DNS, TLS) are caught and returned as ``"Error: …"``
    strings so the LLM can react without catching an exception. ``ctx`` is
    accepted for stdlib convention — the function does not consult it.
    """
    _ = ctx
    try:
        response = httpx.request(method, url, timeout=timeout)
    except httpx.TimeoutException as e:
        return f"Error: HTTP timeout fetching {url}: {e}"
    except httpx.HTTPError as e:
        return f"Error: HTTP error fetching {url}: {type(e).__name__}: {e}"
    except (ValueError, OSError) as e:
        return f"Error: {type(e).__name__}: {e}"

    body = response.text
    if len(body) > max_chars:
        body = body[:max_chars] + _TRUNCATION_SUFFIX
    return f"HTTP {response.status_code}\n{body}"
