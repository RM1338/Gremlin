"""Verify the oracle: (1) matching logic against known framework output for
every supported toolkit, and (2) a live logcat stream while we tap through the
app under test.

Run from the project root:  python -m tests.oracle_test   (or python tests/oracle_test.py)
"""

import sys
from pathlib import Path

# Make `import gremlin` work whether run as a module or a bare script.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gremlin.config import Config
from gremlin.device import Device, choose_serial
from gremlin.oracle import Oracle
from gremlin import platforms

# ---- (1) offline matching check --------------------------------------------
# Real-shaped log excerpts, one per signal, per toolkit.
SAMPLES = {
    "flutter": {
        "native-crash": "E/AndroidRuntime(12043): FATAL EXCEPTION: main",
        "dart-exception": "E/flutter (12043): [ERROR:flutter/.../dart_error.cc] Unhandled Exception: Null check operator used on a null value",
        "renderflex-overflow": "I/flutter (12043): A RenderFlex overflowed by 42 pixels on the right.",
        "render-error": "I/flutter (12043): ══╡ EXCEPTION CAUGHT BY RENDERING LIBRARY ╞══",
        "jank": "I/Choreographer(12043): Skipped 47 frames!  The application may be doing too much work on its main thread.",
    },
    "react-native": {
        "native-crash": "E/AndroidRuntime(9871): FATAL EXCEPTION: main",
        "js-exception": "E/AndroidRuntime(9871): com.facebook.react.common.JavascriptException: TypeError: undefined is not an object",
        "unhandled-rejection": "W/ReactNativeJS(9871): Possible Unhandled Promise Rejection (id: 0): TypeError: Network request failed",
        "bundle-error": "E/ReactNativeJS(9871): Unable to resolve module ./MissingScreen from src/App.jsx",
        "react-warning": 'W/ReactNativeJS(9871): Warning: Each child in a list should have a unique "key" prop.',
        "jank": "I/Choreographer(9871): Skipped 63 frames!  The application may be doing too much work on its main thread.",
    },
}

print("=== (1) offline matching ===")
total = failures = 0
for plat_name, samples in SAMPLES.items():
    plat = platforms.by_name(plat_name)
    print(f"  -- {plat.label} --")
    for expected_kind, sample in samples.items():
        sig = plat.classify(sample)
        hit = sig.kind if sig else None
        ok = hit == expected_kind
        total += 1
        failures += not ok
        print(f"    {'OK ' if ok else 'FAIL'} {expected_kind:22} -> matched {hit}")
print(f"  {total - failures}/{total} signals matched")

# Location extraction must find real app source and skip vendored/generated code.
LOCATIONS = [
    ("flutter", "I/flutter (12043): Row  lib/screens/library_screen.dart:42:15",
     "lib/screens/library_screen.dart", 42),
    ("flutter", "I/flutter (12043): Column package:scribe/screens/home.dart:88:12",
     "lib/screens/home.dart", 88),
    ("react-native", "E/ReactNativeJS(9871):     at CardScreen (src/screens/CardScreen.jsx:42:15)",
     "src/screens/CardScreen.jsx", 42),
    # node_modules and the Metro bundle must be skipped in favour of app code.
    ("react-native", "E/ReactNativeJS(9871): at f (node_modules/react/i.js:9:1) at G (App.tsx:7:3)",
     "App.tsx", 7),
]


class _NoDevice:
    """The oracle only needs a device to stream; matching is pure."""
    serial = None

    def _shell(self, *a, **k):
        return ""

    def _base(self):
        return ["adb"]


for plat_name, line, want_file, want_line in LOCATIONS:
    got_file, got_line = Oracle(_NoDevice(), platform=plat_name)._extract_location([line])
    ok = (got_file, got_line) == (want_file, want_line)
    failures += not ok
    print(f"  {'OK ' if ok else 'FAIL'} location [{plat_name}] -> {got_file}:{got_line}")

if failures:
    print(f"\n{failures} offline check(s) FAILED")
    sys.exit(1)

# ---- (2) live stream check -------------------------------------------------
# Everything above is pure and runs anywhere; the rest needs a real device.
if "--offline" in sys.argv:
    print("\n(offline mode: skipping the live logcat check)")
    sys.exit(0)

print("\n=== (2) live logcat while tapping the app ===")
cfg = Config()
# A phone and the sandbox can both be attached; pick the disposable one and
# never guess at hardware (see gremlin.device.choose_serial).
try:
    cfg.serial = choose_serial(cfg.serial)
except RuntimeError as e:
    sys.exit(str(e))

dev = Device(cfg.serial)
dev.prepare()
dev.relaunch(cfg.package, cfg.activity)

oracle = Oracle(dev)
oracle.start()
print("oracle streaming. tapping around to generate log traffic...")

import time
for label, coords in [
    ("open settings", (900, 2229)),
    ("back", None),
    ("open schedule", (540, 2229)),
    ("back", None),
    ("tap a recording", (540, 806)),
    ("back", None),
]:
    if coords is None:
        dev.back()
    else:
        dev.tap(*coords)
    time.sleep(1.0)
    signals = oracle.drain()
    print(f"  after {label:18}: {len(signals)} signal(s)")
    for s in signals:
        print("     ->", s.summary())

oracle.stop()
print("\ndone. (0 signals on clean screens is expected — we haven't planted a bug yet.)")
