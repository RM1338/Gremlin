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
# Groq retires hosted models without notice — `llama-4-scout`, the previous
# default here, now 404s as `model_not_found`, which stops a run at step 1. This
# is the vision-capable model Groq currently serves; if it disappears too, list
# what's available with `GET /openai/v1/models` and set GROQ_MODEL.
MODEL = os.environ.get("GROQ_MODEL", "qwen/qwen3.6-27b")
_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"


class GroqError(RuntimeError):
    pass


def _is_reasoning_model(name: str) -> bool:
    """Whether this model thinks before answering, and so accepts an effort dial."""
    return any(tag in name.lower() for tag in ("qwen3", "gpt-oss", "deepseek-r1"))


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

    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": content}],
        "temperature": 0.4,
        # A reasoning model spends this budget thinking *before* it answers, and
        # 512 tokens is enough to think and then get truncated with no answer at
        # all — which reaches the caller as an empty reply. The decision we want
        # is a two-line JSON object; the headroom is purely for the thinking.
        "max_tokens": 2048,
    }
    # Turn thinking off where the model allows it. Picking which button to tap
    # next needs no deliberation, and a reasoning model left to think will spend
    # the whole token budget on it and return no answer at all. Groq accepts
    # only "none" or "default" here — other vendors use low/medium/high, so this
    # stays overridable.
    if _is_reasoning_model(MODEL):
        payload["reasoning_effort"] = os.environ.get("GROQ_REASONING_EFFORT", "none")
    body = json.dumps(payload).encode()

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
            # The model being busy is transient; only a 4xx that is not a rate
            # limit says the request itself is wrong.
            if e.code in (500, 502, 503, 504) and attempt < max_retries:
                time.sleep(min(2 ** attempt, 30))
                continue
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
