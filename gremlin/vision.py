"""Provider dispatcher for the exploration policy's vision calls.

Which backend answers each step is chosen by the `LLM_PROVIDER` env var
(default "gemini"); "groq" is the alternative when Gemini's free quota is spent.
Provider-specific errors are normalized to ModelError / ModelQuotaError so the
explorer can end a run gracefully regardless of backend.
"""

from __future__ import annotations

import os
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


def generate(prompt: str, image_path: Path | None = None, vision_width: int = 540) -> str:
    """Route one vision turn to the configured provider."""
    if provider() == "groq":
        from . import groq
        try:
            return groq.generate(prompt, image_path=image_path, vision_width=vision_width)
        except groq.GroqError as e:
            raise ModelError(str(e)) from e

    from . import gemini
    try:
        return gemini.generate(prompt, image_path=image_path, vision_width=vision_width)
    except gemini.GeminiQuotaError as e:
        raise ModelQuotaError(str(e)) from e
    except gemini.GeminiError as e:
        raise ModelError(str(e)) from e
