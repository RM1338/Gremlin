"""Smoke test: drive the app under test through the device + grounding layers.

Wakes the device, relaunches the configured app, captures a screenshot, and
prints the grounded element list. Confirms the foundation works end to end
before the agent loop is built on top of it.

Run from the project root:  python -m tests.smoke_test   (or python tests/smoke_test.py)
"""

import sys
from pathlib import Path

# Make `import gremlin` work whether run as a module or a bare script.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gremlin.config import Config
from gremlin.device import Device, choose_serial
from gremlin.grounding import dump_elements

cfg = Config()
cfg.ensure_dirs()

# With a phone and the sandbox both attached, adb refuses to choose and every
# call below fails. `choose_serial` picks the sandbox and never a phone.
try:
    cfg.serial = choose_serial(cfg.serial)
except RuntimeError as e:
    sys.exit(str(e))
if cfg.serial:
    print(f"several devices attached; driving {cfg.serial}")

dev = Device(cfg.serial)
print("preparing device (wake + stay-on)...")
dev.prepare()
print("screen size:", dev.screen_size())

print(f"relaunching {cfg.package}...")
dev.relaunch(cfg.package, cfg.activity)

shot = dev.screenshot()
out = cfg.run_dir / "screens" / "smoke.png"
Path(out).write_bytes(shot)
print(f"screenshot: {len(shot)} bytes -> {out}")

els = dump_elements(dev)
print(f"\ngrounded {len(els)} elements:")
for e in els:
    print("  ", e.describe(), "@", (e.cx, e.cy))
