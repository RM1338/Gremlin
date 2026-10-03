"""What ensure_installed() may build, and what it must refuse to.

The rule: only a sandbox gets an app built and pushed into it uninvited, only
when the package is genuinely absent, and never when there is no project to
build it from. A container starting empty is why the console used to launch a
package that was not there at all.

Run from the project root:  python -m tests.sandbox_install_test
"""

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gremlin import sandbox

CFG = SimpleNamespace(package="com.example.app", serial=sandbox.SERIAL,
                      scribe_root="/nope/not/a/project", platform="flutter")
calls = []


class FakeDevice:
    def __init__(self, serial=None):
        calls.append(("device", serial))

    def list_third_party_packages(self):
        return INSTALLED


# ensure_installed imports Device from .device at call time, so patch it there.
import gremlin.device
gremlin.device.Device = FakeDevice

# --- already installed: no build, no install, no complaint ------------------
INSTALLED = ["com.example.app"]
sandbox.ensure_installed(CFG)          # must not raise, must not build

# --- absent, and no project to build from: refuse, and say how to fix it -----
INSTALLED = []
try:
    sandbox.ensure_installed(CFG)
    raise AssertionError("should have refused: no project at scribe_root")
except RuntimeError as e:
    assert "is not installed on localhost:5555" in str(e), e
    assert "adb -s" in str(e), "the refusal has to name the manual way out"

# --- absent, with a project: builds and installs, reporting each step --------
built = []
seen = []
tmp = Path(__file__).resolve().parent / "_fixture_app"
(tmp / "android").mkdir(parents=True, exist_ok=True)


class FakePlatform:
    def build(self, root):
        built.append(Path(root))
        return Path(root) / "app-debug.apk"


import gremlin.platforms
gremlin.platforms.by_name = lambda name: FakePlatform()
sandbox.subprocess = SimpleNamespace(
    run=lambda *a, **k: seen.append(a[0]) or SimpleNamespace(returncode=0),
    CalledProcessError=Exception, TimeoutExpired=Exception)

notes = []
sandbox.ensure_installed(
    SimpleNamespace(package="com.example.app", serial=sandbox.SERIAL,
                    scribe_root=str(tmp), platform="flutter"),
    on_status=notes.append)

assert built == [tmp], built
assert seen and seen[0][:2] == ["adb", "-s"] and "install" in seen[0], seen
assert len(notes) >= 2 and any("building" in n for n in notes), notes

import shutil
shutil.rmtree(tmp)
print("sandbox install: OK")

# --- which devices count as Gremlin's own -----------------------------------
# The sandbox always; an emulator only when it has no window; a phone never.
from gremlin import emulator
_real = emulator.has_window
try:
    emulator.has_window = lambda s: False
    assert sandbox.owns_device("emulator-5554")
    emulator.has_window = lambda s: True
    assert not sandbox.owns_device("emulator-5554")
    emulator.has_window = lambda s: None   # cannot tell: treat as someone's
    assert not sandbox.owns_device("emulator-5554")
    assert sandbox.owns_device(sandbox.SERIAL)
    assert not sandbox.owns_device("RZCY607P0TL")
finally:
    emulator.has_window = _real
print("owns_device: OK")
