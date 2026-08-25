"""Gate-3 contract: what "no new breakage" may and may not claim.

The regression this encodes is real (docs/KNOWN_ISSUES.md, G2). A correct
one-line fix was reverted because a probe explored further than the baseline run
had, found a defect the baseline never triggered, and called it a regression.

Run from the project root:  python -m tests.gates_test
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gremlin.gates import no_new_breakage, screen_looks_same
from gremlin.oracle import stable_key

BASELINE = {"renderflex-overflow|...", "dart-exception|lib/main.dart:145"}

# --- a signal the run already knew about is not breakage --------------------
g = no_new_breakage(set(BASELINE), BASELINE, replayed=1)
assert g.passed, g.detail

# --- a genuinely new signal is --------------------------------------------
g = no_new_breakage(BASELINE | {"dart-exception|lib/main.dart:99"}, BASELINE, replayed=1)
assert not g.passed and "lib/main.dart:99" in g.detail, g.detail

# --- fewer signals than baseline is fine: replay need not re-trigger them all
g = no_new_breakage(set(), BASELINE, replayed=2)
assert g.passed, g.detail

# --- a pass must say how hard it looked -------------------------------------
# Two replayed traces and none produce the same verdict; only the detail
# separates a real check from having checked nothing at all.
strong = no_new_breakage(set(), BASELINE, replayed=2)
weak = no_new_breakage(set(), BASELINE, replayed=0)
assert strong.passed and weak.passed
assert "2" in strong.detail, strong.detail
assert "nothing independent to check" in weak.detail, weak.detail
assert strong.detail != weak.detail, "a pass that checked nothing must not read as a pass that did"

# --- the verdict is a plain bool, whatever computed it ----------------------
assert isinstance(g.passed, bool)

# --- the identity the gates compare on must survive the patch --------------
# The second real autofix attempt failed here: the agent's correct fix also
# rewrote a 3-line comment into 1, BadBuildPage's throw moved from line 145 to
# 143, and a pre-existing crash read as one the patch introduced.
CRASH = "I/flutter ( 2800): GREMLIN_BUG Bad state: planted build error: BadBuildPage failed to build"
before = stable_key("dart-exception", CRASH)
# Same defect after the patch: different pid, and two lines higher up the file.
after = stable_key("dart-exception", CRASH.replace("2800", "3912"))
assert before == after, "a bug that only moved must not read as a new one"
assert no_new_breakage({after}, {before}, replayed=1).passed

# ...while still telling two different crashes apart, including in one file.
elsewhere = stable_key("dart-exception",
                       "I/flutter ( 2800): GREMLIN_BUG Bad state: planted crash: button tapped")
assert elsewhere != before
assert not no_new_breakage({before, elsewhere}, {before}, replayed=1).passed

# --- gate 2 must not demand that a broken screen stay broken ---------------
# Two correct fixes were reverted here: replacing a throwing tap handler with a
# SnackBar, and giving a build-error page a real Scaffold. Both legitimately
# changed the screen, because the screen WAS the defect.
import io
from PIL import Image

def png(*bands):
    """A tall image of horizontal bands — stands in for a rendered screen."""
    im = Image.new("RGB", (64, 128))
    h = 128 // len(bands)
    for i, c in enumerate(bands):
        im.paste(Image.new("RGB", (64, h), c), (0, i * h))
    buf = io.BytesIO(); im.save(buf, "PNG"); return buf.getvalue()

crash_frame = png((200, 0, 0), (200, 0, 0))          # Flutter's red error box
fixed_frame = png((255, 255, 255), (30, 90, 180))    # a real screen, nothing alike
blank_frame = png((250, 250, 250), (250, 250, 250))  # widget deleted

# A crash fix: utterly different from the failure frame, and correct.
g = screen_looks_same(crash_frame, fixed_frame, compare_to_pre=False)
assert g.passed, g.detail

# ...but deleting the UI is still caught, which is what this gate is really for.
g = screen_looks_same(crash_frame, blank_frame, compare_to_pre=False)
assert not g.passed and "blank" in g.detail, g.detail

# A layout fix still has a working screen to be recognisable against.
g = screen_looks_same(fixed_frame, fixed_frame, recognizable_within=32, compare_to_pre=True)
assert g.passed, g.detail
g = screen_looks_same(fixed_frame, crash_frame, recognizable_within=0, compare_to_pre=True)
assert not g.passed, "a layout fix that replaces the screen must still fail"

print("gates: OK")
