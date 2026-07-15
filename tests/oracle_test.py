"""Verify the oracle: (1) matching logic against known Flutter output, and
(2) a live logcat stream while we tap through the app under test.

Run from the project root:  python -m tests.oracle_test   (or python tests/oracle_test.py)
"""

import sys
from pathlib import Path

# Make `import gremlin` work whether run as a module or a bare script.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gremlin.config import Config
from gremlin.device import Device
from gremlin.oracle import Oracle, _SIGNAL_SPECS, _DART_LOCATION_RE

# ---- (1) offline matching check --------------------------------------------
# Real-shaped Flutter log excerpts, one per signal.
SAMPLES = {
    "native-crash": "E/AndroidRuntime(12043): FATAL EXCEPTION: main",
    "dart-exception": "E/flutter (12043): [ERROR:flutter/.../dart_error.cc] Unhandled Exception: Null check operator used on a null value",
    "renderflex-overflow": "I/flutter (12043): A RenderFlex overflowed by 42 pixels on the right.",
    "render-error": "I/flutter (12043): ══╡ EXCEPTION CAUGHT BY RENDERING LIBRARY ╞══",
    "jank": "I/Choreographer(12043): Skipped 47 frames!  The application may be doing too much work on its main thread.",
}

print("=== (1) offline matching ===")
passed = 0
for expected_kind, sample in SAMPLES.items():
    hit = None
    for severity, kind, pattern in _SIGNAL_SPECS:
        if pattern.search(sample):
            hit = kind
            break
    ok = hit == expected_kind
    passed += ok
    print(f"  {'OK ' if ok else 'FAIL'} {expected_kind:22} -> matched {hit}")
print(f"  {passed}/{len(SAMPLES)} signals matched")

loc_sample = "I/flutter (12043): Row  lib/screens/library_screen.dart:42:15"
m = _DART_LOCATION_RE.search(loc_sample)
print(f"  location extraction: {m.group(1)}:{m.group(2)}" if m else "  location: FAIL")

# ---- (2) live stream check -------------------------------------------------
print("\n=== (2) live logcat while tapping the app ===")
cfg = Config()
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
