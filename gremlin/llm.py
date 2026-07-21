"""Shared LLM backend: headless Claude Code (`claude -p`).

Both the exploration policy and the Tier 2 fixer talk to a model through here.
Using the already-authenticated `claude` CLI means no separate API key and no
separate billing, and it unifies the two callers on one backend.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path


class LLMError(RuntimeError):
    pass


def run_claude(
    prompt: str,
    cwd: Path | None = None,
    allowed_tools: str = "Read",
    timeout: float = 120.0,
) -> str:
    """Run a headless Claude turn and return its final text output.

    Image inputs are passed by referencing the file path in the prompt; Claude
    reads it with its Read tool (hence the default allowed_tools="Read").
    """
    cmd = ["claude", "-p", prompt, "--allowedTools", allowed_tools]
    try:
        out = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(cwd) if cwd else None,
        )
    except subprocess.TimeoutExpired as e:
        raise LLMError(f"claude -p timed out after {timeout}s") from e
    if out.returncode != 0:
        raise LLMError(f"claude -p exited {out.returncode}: {out.stderr[:400]}")
    return out.stdout.strip()


_JSON_OBJ_RE = re.compile(r"\{.*\}", re.DOTALL)


def extract_json(text: str) -> dict:
    """Pull the first JSON object out of a model reply, tolerating fences/prose."""
    # Reasoning models (Qwen3, gpt-oss) emit a <think>…</think> preamble before
    # the answer. It is prose about the answer, and it frequently contains a
    # draft JSON object — so scanning the raw reply would pick up the model's
    # first guess rather than its conclusion. Drop the thinking first.
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    # An unterminated block means the reply was cut off mid-thought; there is no
    # answer after it to find.
    text = re.sub(r"<think>.*", "", text, flags=re.DOTALL)
    # Strip a ```json ... ``` fence if present.
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    candidate = fenced.group(1) if fenced else None
    if candidate is None:
        m = _JSON_OBJ_RE.search(text)
        if not m:
            raise LLMError(f"no JSON object in model reply: {text[:200]!r}")
        candidate = m.group(0)
    try:
        return json.loads(candidate)
    except json.JSONDecodeError as e:
        raise LLMError(f"bad JSON from model: {candidate[:200]!r}") from e
