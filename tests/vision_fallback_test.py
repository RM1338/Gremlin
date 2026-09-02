"""A quota wall on one key must roll onto the next key, then the next backend —
not end the run. This is the safety net for a live demo on a free tier.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gremlin import vision


class _Env:
    """Minimal monkeypatch: set os.environ keys, restore on exit."""
    def __init__(self):
        import os
        self.os = os
        self.saved = {}

    def set(self, k, v):
        if k not in self.saved:
            self.saved[k] = self.os.environ.get(k)
        if v is None:
            self.os.environ.pop(k, None)
        else:
            self.os.environ[k] = v

    def __enter__(self):
        return self

    def __exit__(self, *a):
        for k, v in self.saved.items():
            if v is None:
                self.os.environ.pop(k, None)
            else:
                self.os.environ[k] = v


def test_key_list_parsing():
    with _Env() as e:
        e.set("GEMINI_API_KEY", "a, b ;c\nd")
        assert vision._keys("GEMINI_API_KEY") == ["a", "b", "c", "d"]
        e.set("GEMINI_API_KEY", "")
        assert vision._keys("GEMINI_API_KEY") == []


def test_candidate_order_keys_then_other_backend():
    with _Env() as e:
        e.set("LLM_PROVIDER", "gemini")
        e.set("GEMINI_API_KEY", "g1,g2")
        e.set("GROQ_API_KEY", "q1")
        e.set("LOCAL_BASE_URL", "")
        assert vision._candidates() == [
            ("gemini", "g1"), ("gemini", "g2"), ("groq", "q1")
        ]


def test_rolls_past_quota_to_a_working_key(monkeypatch=None):
    calls = []

    def fake_one(prov, key, *a, **k):
        calls.append((prov, key))
        if key == "g1":
            raise vision.ModelQuotaError("daily quota exhausted")
        if key == "g2":
            raise vision.ModelError("500 busy")
        return "ok from " + str(key)

    with _Env() as e:
        e.set("LLM_PROVIDER", "gemini")
        e.set("GEMINI_API_KEY", "g1,g2")
        e.set("GROQ_API_KEY", "q1")
        orig = vision._one
        vision._one = fake_one
        try:
            assert vision.generate("hi") == "ok from q1"
        finally:
            vision._one = orig
    assert calls == [("gemini", "g1"), ("gemini", "g2"), ("groq", "q1")]


def test_all_exhausted_raises_last_error():
    def fake_one(prov, key, *a, **k):
        raise vision.ModelQuotaError(f"{prov} {key} dead")

    with _Env() as e:
        e.set("LLM_PROVIDER", "gemini")
        e.set("GEMINI_API_KEY", "g1")
        e.set("GROQ_API_KEY", "")
        orig = vision._one
        vision._one = fake_one
        try:
            raised = None
            try:
                vision.generate("hi")
            except vision.ModelError as ex:
                raised = ex
            assert isinstance(raised, vision.ModelQuotaError)
        finally:
            vision._one = orig


if __name__ == "__main__":
    test_key_list_parsing()
    test_candidate_order_keys_then_other_backend()
    test_rolls_past_quota_to_a_working_key()
    test_all_exhausted_raises_last_error()
    print("ok")
