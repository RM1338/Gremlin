"""A model that says "click" must not be read as a model with no opinion.

`Explorer._choose_and_execute` honours the model's choice only for verb "tap".
Any synonym falls through to the coverage fallback, which silently converts the
vision arm into the coverage arm and destroys the ablation it exists to measure.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gremlin.policy import canonical_verb, canonical_index


def test_synonyms_normalise():
    for said in ("click", "Click", "PRESS", "touch", "select", "tap-element"):
        assert canonical_verb(said) == "tap", said
    for said in ("input", "enter", "write"):
        assert canonical_verb(said) == "type", said
    assert canonical_verb("swipe") == "scroll"
    assert canonical_verb("go-back") == "back"


def test_canonical_verbs_survive_unchanged():
    for said in ("tap", "type", "scroll", "back"):
        assert canonical_verb(said) == said


def test_unknown_verb_is_left_alone():
    """Not a synonym: pass it through so the coverage fallback still catches it."""
    assert canonical_verb("teleport") == "teleport"
    assert canonical_verb("") == ""
    assert canonical_verb(None) == ""


def test_index_coercion():
    """The explorer compares the index numerically; anything else must be None."""
    assert canonical_index(0) == 0
    assert canonical_index(3) == 3
    assert canonical_index("2") == 2
    assert canonical_index(2.0) == 2
    assert canonical_index([1]) == 1        # qwen2.5vl does this
    assert canonical_index(["0"]) == 0
    for junk in (None, [], [1, 2], "first", "", 2.5, True, {"i": 1}):
        assert canonical_index(junk) is None, junk


def test_bad_index_cannot_crash_the_comparison():
    """The failure this exists to prevent: TypeError three steps into a seed."""
    elements = list(range(5))
    for junk in ([0], "1", None, [], 2.5, True):
        i = canonical_index(junk)
        assert i is None or (0 <= i < len(elements)) or i >= len(elements)


if __name__ == "__main__":
    test_synonyms_normalise()
    test_canonical_verbs_survive_unchanged()
    test_unknown_verb_is_left_alone()
    test_index_coercion()
    test_bad_index_cannot_crash_the_comparison()
    print("ok")
