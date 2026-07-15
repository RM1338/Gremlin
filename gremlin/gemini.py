"""Gemini backend for the exploration policy — the hot path, free tier.

The per-step "where do I go next?" decision runs dozens of times per run, so it
lives on Google's free Gemini tier instead of billing Claude. This is a plain
REST call (stdlib only, no SDK) that sends the screenshot inline as base64 and
asks for a JSON action back.

Set a key once (free from https://aistudio.google.com/apikey):

    export GEMINI_API_KEY=...

The Tier-2 fixer deliberately does NOT use this — it needs Claude's agentic
Edit/Write tools, and it runs rarely. Only exploration moved here.
"""

from __future__ import annotations

import io
import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

from PIL import Image

from ._env import load_dotenv

_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

load_dotenv()
# 2.5-flash-lite is the model with free-tier quota that's broadly granted; other
# flash models often show a limit-0 free quota depending on project/region.
MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash-lite")


class GeminiError(RuntimeError):
    pass


def _downscale_png(path: Path, width: int) -> bytes:
    """Shrink the screenshot before upload to keep vision inference cheap/fast."""
    img = Image.open(path).convert("RGB")
    if img.width > width:
        h = round(img.height * width / img.width)
        img = img.resize((width, h), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class GeminiQuotaError(GeminiError):
    """A 429 that retrying won't fix soon (daily free-tier quota exhausted)."""


def _parse_429(body: str) -> tuple[bool, float | None]:
    """Return (is_daily, retry_delay_seconds) from a 429 error body."""
    is_daily = False
    delay = None
    try:
        err = json.loads(body).get("error", {})
        for det in err.get("details", []):
            t = det.get("@type", "")
            if t.endswith("QuotaFailure"):
                for v in det.get("violations", []):
                    if "PerDay" in v.get("quotaId", ""):
                        is_daily = True
            if t.endswith("RetryInfo"):
                m = re.match(r"(\d+(?:\.\d+)?)s", str(det.get("retryDelay", "")))
                if m:
                    delay = float(m.group(1))
    except (ValueError, KeyError):
        pass
    return is_daily, delay


def generate(prompt: str, image_path: Path | None = None, vision_width: int = 540,
             timeout: float = 60.0, max_retries: int = 4) -> str:
    """One Gemini turn. Returns the model's text.

    Retries transient per-minute 429s (respecting the server's retry delay) so a
    brief rate-limit doesn't kill a run. A per-*day* quota exhaustion is raised
    immediately as GeminiQuotaError — retrying can't fix it before midnight PT.
    """
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise GeminiError(
            "GEMINI_API_KEY is not set. Get a free key at "
            "https://aistudio.google.com/apikey and put it in a .env file."
        )

    parts: list[dict] = [{"text": prompt}]
    if image_path is not None:
        import base64
        png = _downscale_png(Path(image_path), vision_width)
        parts.append({
            "inline_data": {"mime_type": "image/png",
                            "data": base64.b64encode(png).decode()}
        })

    body = json.dumps({
        "contents": [{"parts": parts}],
        "generationConfig": {"temperature": 0.4, "maxOutputTokens": 512},
    }).encode()

    url = _ENDPOINT.format(model=MODEL) + f"?key={key}"
    for attempt in range(max_retries + 1):
        req = urllib.request.Request(url, data=body,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read())
            break
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")
            if e.code == 429:
                is_daily, delay = _parse_429(detail)
                if is_daily:
                    raise GeminiQuotaError(
                        f"Gemini free-tier DAILY quota for {MODEL} is exhausted. It "
                        f"resets at ~midnight Pacific. To keep working now, switch "
                        f"provider (e.g. Groq) or enable billing on the project."
                    ) from e
                if attempt < max_retries:
                    wait = min(delay or (2 ** attempt), 30)
                    time.sleep(wait)
                    continue
            raise GeminiError(f"Gemini HTTP {e.code}: {detail[:300]}") from e
        except urllib.error.URLError as e:
            if attempt < max_retries:
                time.sleep(2 ** attempt)
                continue
            raise GeminiError(f"Gemini unreachable: {e.reason}") from e

    try:
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except (KeyError, IndexError) as e:
        # Usually a safety block or an empty candidate — surface it.
        raise GeminiError(f"Gemini returned no usable text: {json.dumps(data)[:300]}") from e
