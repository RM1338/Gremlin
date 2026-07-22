"""Local backend for the exploration policy — a self-hosted vision model.

This is Objective 2 of the proposal: the same policy, answered by a checkpoint
we host ourselves instead of a rate-limited third-party API. That buys three
things a hosted model cannot give — reproducible benchmark numbers against a
pinned checkpoint, no daily quota, and screenshots of proprietary apps that
never leave the building.

vLLM serves an OpenAI-compatible `/v1/chat/completions`, the same shape Groq
speaks, so this file is deliberately the Groq backend with the vendor bits
removed: no API key, no Cloudflare user-agent, and a base URL instead of a
fixed endpoint. Point it at the server with `LOCAL_BASE_URL`.
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

# Defaults match docker/compose.yml, where the model service is reachable under
# its compose hostname and is served under a stable alias so that swapping the
# underlying checkpoint never touches Gremlin's configuration.
BASE_URL = os.environ.get("LOCAL_BASE_URL", "http://vllm:8000/v1").rstrip("/")
MODEL = os.environ.get("LOCAL_MODEL", "gremlin-vision")


class LocalError(RuntimeError):
    pass


def _is_reasoning_model(name: str) -> bool:
    """Whether this model thinks before answering, and so needs that suppressed.

    Matching the family name alone is too blunt here. Qwen3-VL ships as both an
    Instruct and a Thinking variant: the Instruct one answers directly, so
    sending it a thinking-suppression flag is at best redundant and at worst a
    400 from a server that does not accept the field.
    """
    n = name.lower()
    if "thinking" in n:
        return True
    # A vision-language Instruct checkpoint — answers directly.
    if "-vl" in n or "vl:" in n or "vl-" in n:
        return False
    return any(tag in n for tag in ("qwen3", "gpt-oss", "deepseek-r1"))


def _downscale_data_url(path: Path, width: int) -> str:
    img = Image.open(path).convert("RGB")
    if img.width > width:
        h = round(img.height * width / img.width)
        img = img.resize((width, h), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def generate(prompt: str, image_path: Path | None = None, vision_width: int = 540,
             timeout: float = 120.0, max_retries: int = 3) -> str:
    """One turn against the local server. Returns the model's text.

    The timeout is generous compared to the hosted backends: a local server
    queues requests instead of scaling out, so a step can wait behind another.
    """
    content: list[dict] = [{"type": "text", "text": prompt}]
    if image_path is not None:
        content.append({"type": "image_url",
                        "image_url": {"url": _downscale_data_url(Path(image_path), vision_width)}})

    payload: dict = {
        "model": MODEL,
        "messages": [{"role": "user", "content": content}],
        "temperature": 0.4,
        # Headroom for a reasoning preamble, not for the answer itself — the
        # decision we want back is a two-line JSON object.
        "max_tokens": 2048,
    }
    # Same trap as the Groq backend: a thinking model left to think will spend
    # the entire budget deliberating over which button to tap and return no
    # answer at all. vLLM exposes the switch through the chat template rather
    # than through Groq's `reasoning_effort` field. Not every server accepts
    # the field, so LOCAL_SUPPRESS_THINKING forces it on ("1") or off ("0")
    # when the guess is wrong.
    suppress = os.environ.get("LOCAL_SUPPRESS_THINKING", "auto").strip().lower()
    if suppress == "auto":
        suppress_thinking = _is_reasoning_model(MODEL)
    else:
        suppress_thinking = suppress in ("1", "true", "yes")
    if suppress_thinking:
        payload["chat_template_kwargs"] = {"enable_thinking": False}
    body = json.dumps(payload).encode()

    headers = {"Content-Type": "application/json"}
    # Some deployments front vLLM with a token; it is optional by default.
    key = os.environ.get("LOCAL_API_KEY")
    if key:
        headers["Authorization"] = f"Bearer {key}"

    endpoint = f"{BASE_URL}/chat/completions"
    for attempt in range(max_retries + 1):
        req = urllib.request.Request(endpoint, data=body, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read())
            break
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")
            # A local server has no daily quota; a 429 here is just a full
            # queue, so it is always worth retrying.
            if e.code == 429 and attempt < max_retries:
                time.sleep(2 ** attempt)
                continue
            raise LocalError(f"local model HTTP {e.code}: {detail[:300]}") from e
        except urllib.error.URLError as e:
            if attempt < max_retries:
                time.sleep(2 ** attempt)
                continue
            # By far the most common failure, and worth naming precisely: the
            # weights take many minutes to load, and until they have, the port
            # is open but refusing.
            raise LocalError(
                f"local model unreachable at {endpoint}: {e.reason}. "
                "Is the vllm service up and finished loading? "
                "Check with: docker compose -f docker/compose.yml logs -f vllm"
            ) from e

    try:
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError) as e:
        raise LocalError(f"local model returned no usable text: {json.dumps(data)[:300]}") from e
