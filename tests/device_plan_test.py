"""Which device a run gets, and in what order of precedence.

The rule that matters: nothing may boot a container over a device someone
explicitly asked for, and nothing may pay a second boot for a container that is
already up. Everything else is "no device? use the sandbox".

Run from the project root:  python -m tests.device_plan_test
"""

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from run import _device_plan

def args(**kw):
    return SimpleNamespace(**{"emulator": False, "avd": None, "serial": None,
                              "sandbox": False, **kw})

PHONE = ["R58M12345"]

# --- nothing attached: the sandbox is the answer, not an error --------------
assert _device_plan(args(), [], False) == "start-sandbox"

# --- a phone is there: use it, don't boot anything --------------------------
assert _device_plan(args(), PHONE, False) == "attached"

# --- --sandbox overrides a connected phone, --serial overrides --sandbox ----
assert _device_plan(args(sandbox=True), PHONE, False) == "start-sandbox"
assert _device_plan(args(sandbox=True, serial="R58M12345"), PHONE, False) == "attached"

# --- a container already up is adopted, never restarted ---------------------
# It boots in about a minute and holds the installed app; re-running --keep-sandbox
# has to be cheap or nobody uses it.
assert _device_plan(args(), [], True) == "adopt-sandbox"
assert _device_plan(args(sandbox=True), ["localhost:5555"], True) == "adopt-sandbox"

# --- the emulator flags still win outright ---------------------------------
assert _device_plan(args(emulator=True), [], True) == "emulator"
assert _device_plan(args(avd="Pixel_7_API_34"), PHONE, False) == "emulator"

print("device plan: OK")
