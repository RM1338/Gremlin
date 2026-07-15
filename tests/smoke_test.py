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
from gremlin.device import Device
from gremlin.grounding import dump_elements

cfg = Config()
cfg.ensure_dirs()

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
