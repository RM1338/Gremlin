"""Provider dispatcher for the exploration policy's vision calls.

Which backend answers each step is chosen by the `LLM_PROVIDER` env var
(default "gemini"); "groq" is the alternative when Gemini's free quota is spent,
and "local" is a self-hosted vision model with no quota at all.
Provider-specific errors are normalized to ModelError / ModelQuotaError so the
explorer can end a run gracefully regardless of backend.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from ._env import load_dotenv

# Load .env now, so LLM_PROVIDER is set before provider() is first read. The
# backends are imported lazily inside generate(), so we can't rely on their
# module-level load_dotenv() having run yet.
load_dotenv()


class ModelError(RuntimeError):
    """Any failure from a vision backend."""


class ModelQuotaError(ModelError):
    """Quota exhausted in a way that retrying won't fix soon (e.g. daily cap)."""


def provider() -> str:
    return os.environ.get("LLM_PROVIDER", "gemini").strip().lower()


def _keys(name: str) -> list[str]:
    """API keys from an env var that may hold several, comma/space/semicolon
    separated. Lets a spent free-tier key roll onto a spare mid-run instead of
    ending the run — set e.g. GEMINI_API_KEY=key1,key2,key3."""
    return [k.strip() for k in re.split(r"[,;\s]+", os.environ.get(name, "")) if k.strip()]


def _candidates() -> list[tuple[str, str | None]]:
    """(provider, api_key) attempts, in order: every key of the configured
    provider first, then any *other* provider that has credentials — so a demo
    survives a quota wall by rolling to the next key, then the next backend."""
    active = provider()
    order = [active] + [p for p in ("gemini", "groq", "local") if p != active]
    out: list[tuple[str, str | None]] = []
    for p in order:
        if p == "local":
            if os.environ.get("LOCAL_BASE_URL"):
                out.append(("local", None))
        elif p == "gemini":
            out += [("gemini", k) for k in _keys("GEMINI_API_KEY")]
        elif p == "groq":
            out += [("groq", k) for k in _keys("GROQ_API_KEY")]
    # Nothing configured: fall through with one bare attempt so the backend
    # raises its own "set a key" message rather than us inventing one.
    return out or [(active, None)]


def _one(prov: str, key: str | None, prompt: str,
         image_path: Path | None, vision_width: int) -> str:
    if prov == "local":
        from . import local
        try:
            return local.generate(prompt, image_path=image_path, vision_width=vision_width)
        except local.LocalError as e:
            raise ModelError(str(e)) from e

    if prov == "groq":
        from . import groq
        try:
            return groq.generate(prompt, image_path=image_path,
                                 vision_width=vision_width, api_key=key)
        except groq.GroqError as e:
            raise ModelError(str(e)) from e

    from . import gemini
    try:
        return gemini.generate(prompt, image_path=image_path,
                               vision_width=vision_width, api_key=key)
    except gemini.GeminiQuotaError as e:
        raise ModelQuotaError(str(e)) from e
    except gemini.GeminiError as e:
        raise ModelError(str(e)) from e


def generate(prompt: str, image_path: Path | None = None, vision_width: int = 540) -> str:
    """Route one vision turn to the configured provider, rolling onto the next
    key/backend if one is quota-blocked or erroring. Raises the last failure
    only when every candidate is exhausted, so the explorer still ends cleanly."""
    plan = _candidates()
    last: ModelError | None = None
    for i, (prov, key) in enumerate(plan):
        try:
            return _one(prov, key, prompt, image_path, vision_width)
        except ModelError as e:
            last = e
            if i + 1 < len(plan):
                print(f"  .. vision: {prov} unavailable ({e}); trying the next key/backend")
    raise last or ModelError("no vision backend is configured")
