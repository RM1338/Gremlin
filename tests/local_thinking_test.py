"""A thinking model must be told not to think, or it returns nothing.

Ollama's `qwen3-vl:4b` deliberates until the token budget is gone and answers
with an empty string. The suppression flag is the only thing standing between a
local run and 30 steps of nothing, so the guess about which models need it, and
the payload that carries it, both get a check.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gremlin import local


def test_reasoning_detection():
    assert local._is_reasoning_model("qwen3-vl:4b")          # Ollama's, thinks
    assert local._is_reasoning_model("Qwen3-VL-8B-Thinking")
    assert local._is_reasoning_model("gpt-oss-20b")
    assert not local._is_reasoning_model("Qwen3-VL-8B-Instruct")
    assert not local._is_reasoning_model("llava:13b")


def test_payload_carries_both_spellings(monkeypatch=None):
    """Ollama reads `think`; vLLM reads the chat-template kwarg."""
    sent = {}

    class _Resp:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self):
            return json.dumps(
                {"choices": [{"message": {"content": "{\"verb\": \"tap\"}"}}]}).encode()

    def _fake_urlopen(req, timeout=None):
        sent.update(json.loads(req.data))
        return _Resp()

    real_open, real_model = local.urllib.request.urlopen, local.MODEL
    real_base = local.BASE_URL
    local.urllib.request.urlopen = _fake_urlopen
    local.MODEL = "qwen3-vl:4b"
    local.BASE_URL = "http://localhost:11434/v1"
    try:
        out = local.generate("pick one")
    finally:
        local.urllib.request.urlopen = real_open
        local.MODEL = real_model
        local.BASE_URL = real_base

    assert out == '{"verb": "tap"}'
    assert sent["think"] is False
    assert sent["chat_template_kwargs"] == {"enable_thinking": False}


def test_budget_burned_on_thinking_is_actionable():
    """An empty reply that hit the token cap must name the cause, not stay silent."""
    class _Resp:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self):
            return json.dumps({"choices": [
                {"finish_reason": "length", "message": {"content": ""}}]}).encode()

    real_open, real_model, real_base = (
        local.urllib.request.urlopen, local.MODEL, local.BASE_URL)
    local.urllib.request.urlopen = lambda req, timeout=None: _Resp()
    local.MODEL = "qwen3-vl:4b"
    local.BASE_URL = "http://localhost:11434/v1"
    try:
        local.generate("pick one")
    except local.LocalError as e:
        assert "thinking model" in str(e), e
        assert "qwen2.5vl" in str(e), e
    else:
        raise AssertionError("an empty reply at the token cap must raise")
    finally:
        local.urllib.request.urlopen = real_open
        local.MODEL = real_model
        local.BASE_URL = real_base


if __name__ == "__main__":
    test_reasoning_detection()
    test_payload_carries_both_spellings()
    test_budget_burned_on_thinking_is_actionable()
    print("ok")
