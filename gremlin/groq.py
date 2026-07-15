"""Groq backend for the exploration policy — an alternative free tier.

Groq's free tier is far more generous than Gemini's and serves a vision model
(Llama 4 Scout) over an OpenAI-compatible API. Use it when Gemini's daily quota
is spent: set `LLM_PROVIDER=groq` and `GROQ_API_KEY` (free at
https://console.groq.com/keys).

Same shape as gemini.generate: stdlib REST, screenshot sent inline, JSON back.
"""

from __future__ import annotations

import base64
import io
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

from PIL import Image

from ._env import load_dotenv

load_dotenv()
MODEL = os.environ.get("GROQ_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")
_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"


class GroqError(RuntimeError):
    pass


def _downscale_data_url(path: Path, width: int) -> str:
    img = Image.open(path).convert("RGB")
    if img.width > width:
        h = round(img.height * width / img.width)
        img = img.resize((width, h), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def generate(prompt: str, image_path: Path | None = None, vision_width: int = 540,
             timeout: float = 60.0, max_retries: int = 4) -> str:
    """One Groq turn. Returns the model's text. Retries transient 429s."""
    key = os.environ.get("GROQ_API_KEY")
    if not key:
        raise GroqError(
            "GROQ_API_KEY is not set. Get a free key at "
            "https://console.groq.com/keys and put it in a .env file."
        )

    content: list[dict] = [{"type": "text", "text": prompt}]
    if image_path is not None:
        content.append({"type": "image_url",
                        "image_url": {"url": _downscale_data_url(Path(image_path), vision_width)}})

    body = json.dumps({
        "model": MODEL,
        "messages": [{"role": "user", "content": content}],
        "temperature": 0.4,
        "max_tokens": 512,
    }).encode()

    # A real User-Agent is required: Groq is behind Cloudflare, which blocks the
    # default urllib agent with a 403 (error 1010).
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {key}",
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Gremlin/1.0",
    }
    for attempt in range(max_retries + 1):
        req = urllib.request.Request(_ENDPOINT, data=body, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read())
            break
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")
            if e.code == 429 and attempt < max_retries:
                retry_after = e.headers.get("retry-after")
                wait = min(float(retry_after) if retry_after else 2 ** attempt, 30)
                time.sleep(wait)
                continue
            raise GroqError(f"Groq HTTP {e.code}: {detail[:300]}") from e
        except urllib.error.URLError as e:
            if attempt < max_retries:
                time.sleep(2 ** attempt)
                continue
            raise GroqError(f"Groq unreachable: {e.reason}") from e

    try:
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError) as e:
        raise GroqError(f"Groq returned no usable text: {json.dumps(data)[:300]}") from e
