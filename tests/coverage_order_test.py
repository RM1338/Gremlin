"""Coverage must not leave a screen before tapping what is on it.

The app bar's back arrow is top-left, so in screen order it came first: the
coverage arm tapped it, left a page with "Trigger crash" still untapped, and
never returned. Run from the project root:  python tests/coverage_order_test.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gremlin.config import Config
from gremlin.explorer import Explorer
from gremlin.grounding import Element
from gremlin.policy import decide_coverage_only


class FakeDev:
    def __init__(self):
        self.calls = []

    def tap(self, x, y):
        self.calls.append(("tap", x, y))

    def scroll(self, direction="down"):
        self.calls.append(("scroll", direction))

    def back(self):
        self.calls.append(("back",))


BACK = Element(0, "Back", 74, 210, clickable=True, bounds=(0, 160, 148, 260))
CRASH = Element(1, "Trigger crash", 540, 1200, clickable=True, bounds=(300, 1150, 780, 1250))


def _next_tap(exp, screen, screen_id=0):
    tapped = exp._tapped.setdefault(screen_id, set())
    exp._seen_elems.setdefault(screen_id, set()).update(exp._elem_key(e) for e in screen)
    untapped = exp._frontier(screen, tapped)
    return exp._choose_and_execute(decide_coverage_only(screen), screen, untapped, screen_id)


def test_back_is_tapped_last():
    exp = Explorer(Config(package="com.x", activity="com.x/.Main", platform="flutter"))
    exp.dev = FakeDev()
    first = _next_tap(exp, [BACK, CRASH])
    assert first.target_label == "Trigger crash", first
    assert _next_tap(exp, [BACK, CRASH]).target_label == "Back"


def test_untapped_left_is_reported():
    exp = Explorer(Config(package="com.x", activity="com.x/.Main", platform="flutter"))
    exp._seen_elems = {0: {("label", "Back"), ("label", "Trigger crash")}}
    exp._tapped = {0: {("label", "Back")}}
    assert exp._untapped_left() == 1
    exp._tapped[0].add(("label", "Trigger crash"))
    assert exp._untapped_left() == 0


if __name__ == "__main__":
    test_back_is_tapped_last()
    test_untapped_left_is_reported()
    print("coverage order: OK")
