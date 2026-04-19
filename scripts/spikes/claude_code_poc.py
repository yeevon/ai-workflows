"""M1 Task 13 — `claude_code` subprocess PoC (spike artefact, throwaway).

Purpose
-------
Validates the five architectural assumptions the M1 scaffolding has baked
into `tiers.yaml` + `model_factory.py` about running `opus` / `sonnet` /
`haiku` via the `claude` CLI. See
``design_docs/phases/milestone_1_primitives/task_13_claude_code_spike.md``.

This file is a spike artefact. It is:

* Not shipped with the package.
* Not unit-tested.
* Excluded from ruff / import-linter via a ``scripts/spikes/`` rule added
  in the same commit (spikes are throwaway; linter debt is noise).
* Safe to delete once the findings in the task file are populated and the
  downstream propagation output is written.

Operation
---------
Runs ``claude -p --output-format json --model <m>`` against opus / sonnet
/ haiku with a short prompt (mirroring ``scripts/m1_smoke.py``), captures
stdout + stderr + exit code + wall time + token-usage (if emitted), and
exercises two failure modes (invalid model id; invalid flag). Dumps a
single structured ``json.dumps(..., indent=2)`` blob so the output can be
pasted verbatim into the task file's § Findings.
"""

from __future__ import annotations

import json
import subprocess
import time
from dataclasses import asdict, dataclass, field
from typing import Any

PROMPT = "Reply in one short sentence: what is 2 + 2?"

# Aliases the CLI accepts via `--model`. The CLI also accepts the full
# model ID string (claude-opus-4-7 etc.), but the aliases are what a
# human would type and they route to the same thing.
TIER_ALIASES = ("opus", "sonnet", "haiku")

# Full model IDs as declared in tiers.yaml. The PoC probes both forms so
# we can report whether the factory should pass an alias or the full ID.
TIER_MODEL_IDS = {
    "opus": "claude-opus-4-7",
    "sonnet": "claude-sonnet-4-6",
    "haiku": "claude-haiku-4-5-20251001",
}


@dataclass
class Probe:
    """Single CLI invocation result, as observed."""

    label: str
    argv: list[str]
    exit_code: int
    wall_seconds: float
    stdout_head: str
    stderr_head: str
    parsed_json: dict[str, Any] | None = None
    usage: dict[str, Any] | None = None
    extracted_text: str | None = None
    notes: list[str] = field(default_factory=list)


def _trim(text: str, limit: int = 2000) -> str:
    """Keep output blobs paste-able. Head + tail so nothing silently vanishes."""
    if len(text) <= limit:
        return text
    half = limit // 2
    return f"{text[:half]}\n... [{len(text) - limit} bytes elided] ...\n{text[-half:]}"


def _run(label: str, argv: list[str], *, timeout_seconds: float = 120.0) -> Probe:
    """Launch the CLI, capture everything, classify failure modes."""
    start = time.monotonic()
    try:
        completed = subprocess.run(  # noqa: S603 — controlled argv, spike-only
            argv,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        elapsed = time.monotonic() - start
        exit_code = completed.returncode
        stdout = completed.stdout
        stderr = completed.stderr
    except subprocess.TimeoutExpired as exc:
        elapsed = time.monotonic() - start
        exit_code = -1
        stdout = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr = exc.stderr.decode() if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        stderr += f"\n[spike] subprocess.TimeoutExpired after {timeout_seconds}s"
    except FileNotFoundError as exc:
        return Probe(
            label=label,
            argv=argv,
            exit_code=127,
            wall_seconds=time.monotonic() - start,
            stdout_head="",
            stderr_head=f"FileNotFoundError: {exc}",
            notes=["claude CLI missing on PATH"],
        )

    probe = Probe(
        label=label,
        argv=argv,
        exit_code=exit_code,
        wall_seconds=round(elapsed, 3),
        stdout_head=_trim(stdout),
        stderr_head=_trim(stderr),
    )

    # Try to parse stdout as JSON. `claude -p --output-format json` emits a
    # single JSON object on success; on malformed-flag failures it may emit
    # a text error or an empty stdout.
    stripped = stdout.strip()
    if stripped.startswith("{"):
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError as exc:
            probe.notes.append(f"stdout looked like JSON but failed to parse: {exc}")
        else:
            probe.parsed_json = parsed
            # CLI JSON shape (v1+): usage lives at top level under "usage"
            # with input_tokens / output_tokens / cache_* subfields, and
            # assistant text lives under "result" as a plain string.
            usage = parsed.get("usage") if isinstance(parsed, dict) else None
            if isinstance(usage, dict):
                probe.usage = usage
            extracted = parsed.get("result") if isinstance(parsed, dict) else None
            if isinstance(extracted, str):
                probe.extracted_text = extracted
    return probe


def _success_call(alias_or_id: str, *, label: str) -> Probe:
    """Clean single-shot: disable tools, bare mode, JSON output, no plugins."""
    argv = [
        "claude",
        "--print",
        "--output-format",
        "json",
        "--model",
        alias_or_id,
        # Disable tools so the call is a pure text→text LLM round-trip —
        # this is the subprocess shape an orchestrator would use when it
        # does not want the CLI to touch the filesystem.
        "--tools",
        "",
        # NOTE: do NOT use --bare. `claude --help` states --bare forces
        # "Anthropic auth is strictly ANTHROPIC_API_KEY or apiKeyHelper
        # via --settings (OAuth and keychain are never read)." The Max
        # subscription uses OAuth/keychain, so --bare breaks auth.
        # We isolate the session with other flags instead.
        # Session persistence adds state to ~/.claude — we don't want
        # the spike to leave resumable sessions lying around.
        "--no-session-persistence",
        PROMPT,
    ]
    return _run(label, argv)


def _invalid_model() -> Probe:
    """Failure mode A — model ID the CLI should reject."""
    argv = [
        "claude",
        "--print",
        "--output-format",
        "json",
        "--model",
        "nonexistent-model-xyz",
        "--tools",
        "",
        "--no-session-persistence",
        PROMPT,
    ]
    return _run("failure:invalid-model", argv)


def _invalid_flag() -> Probe:
    """Failure mode B — a flag the CLI doesn't understand.

    Surfaces whether ``TierConfig.max_tokens`` / ``temperature`` can be
    forwarded (they're not in ``claude --help``, so a forwarding attempt
    would fail here). Observing the exact error lets us decide in AC-4
    whether to drop the fields from ``claude_code`` rows or validate.
    """
    argv = [
        "claude",
        "--print",
        "--output-format",
        "json",
        "--model",
        "haiku",
        "--max-tokens",
        "100",  # not a real CLI flag
        "--tools",
        "",
        "--no-session-persistence",
        PROMPT,
    ]
    return _run("failure:unknown-flag", argv)


def _system_prompt_call() -> Probe:
    """AC-4 — does ``--system-prompt`` actually land?

    If the response reflects the system-prompt directive, ``system_prompt``
    in ``TierConfig`` is live. If it doesn't, we need a validator.
    """
    argv = [
        "claude",
        "--print",
        "--output-format",
        "json",
        "--model",
        "haiku",
        "--system-prompt",
        "Respond only with the single word BANANA, regardless of the question.",
        "--tools",
        "",
        "--no-session-persistence",
        PROMPT,
    ]
    return _run("probe:system-prompt", argv)


def main() -> None:
    probes: list[Probe] = []

    # Success-path probes — alias form (what users type).
    for alias in TIER_ALIASES:
        probes.append(_success_call(alias, label=f"success:alias:{alias}"))

    # One success-path probe via full model ID so we can report whether
    # `model: claude-opus-4-7` in tiers.yaml survives the CLI boundary.
    opus_full = TIER_MODEL_IDS["opus"]
    probes.append(_success_call(opus_full, label=f"success:full-id:{opus_full}"))

    # Does --system-prompt flow through?
    probes.append(_system_prompt_call())

    # Failure modes.
    probes.append(_invalid_model())
    probes.append(_invalid_flag())

    report = {
        "prompt": PROMPT,
        "claude_cli_version": None,
        "probes": [asdict(p) for p in probes],
    }

    # Grab the CLI version once for the record.
    try:
        version = subprocess.run(  # noqa: S603, S607
            ["claude", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        report["claude_cli_version"] = (version.stdout or version.stderr).strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        report["claude_cli_version"] = "unavailable"

    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
