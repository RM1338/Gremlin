"""Checks on the sandbox layer that need no Docker and no kernel module.

What matters here is what a developer is told when it cannot start — the binder
message is the whole difference between "it's broken" and "run one command" —
and that a start actually carries the geometry it was asked for, since geometry
is the reason to prefer a container over a phone.

Run from the project root:  python -m tests.sandbox_test
"""

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gremlin import sandbox
from gremlin.sandbox import SandboxStatus

# --- what to tell the developer, in order of what blocks first --------------
no_docker = SandboxStatus(docker=False, daemon=False, binder="no-module", image=False, container=None)
assert "Docker is not installed" in no_docker.problem
assert not no_docker.can_start

no_daemon = SandboxStatus(docker=True, daemon=False, binder="ok", image=True, container=None)
assert "daemon is not reachable" in no_daemon.problem

# Two binder failures that need DIFFERENT advice. Telling someone who has already
# run modprobe to run modprobe is how an hour gets lost, so they are distinct.
no_module = SandboxStatus(docker=True, daemon=True, binder="no-module", image=True, container=None)
assert "binder driver is not loaded" in no_module.problem and not no_module.can_start

no_devices = SandboxStatus(docker=True, daemon=True, binder="no-devices", image=True, container=None)
assert "exposes no devices" in no_devices.problem, no_devices.problem
assert not no_devices.can_start

# Neither may hand out a shell command any more. The console fixes this itself
# through pkexec, and a pasted `modprobe` is the wrong answer twice over: on
# macOS and Windows there is no binder to load at all, so the command cannot
# work and only wastes the reader's time. Both must point at the real options.
for st in (no_module, no_devices):
    assert "sudo " not in st.problem, st.problem
    assert "Gremlin can" in st.problem, st.problem
# Only the no-module case is reachable on a Mac or a Windows box, and that is
# the one that has to name the way out that exists there.
assert "emulator" in no_module.problem and "Setup page" in no_module.problem
# Not "reload the module": Ubuntu marks binder_linux [permanent], so unloading
# it is impossible before a reboot. Whatever we suggest has to be takeable.
assert "modprobe -r" not in no_devices.problem

ready = SandboxStatus(docker=True, daemon=True, binder="ok", image=True, container=None)
assert ready.problem is None and ready.can_start and ready.note is None

# Not a blocker — a heads-up that the first start is a download, not a hang.
cold = SandboxStatus(docker=True, daemon=True, binder="ok", image=False, container=None)
assert cold.problem is None and cold.can_start and "2-3 GB" in cold.note

# --- a container is a device like any other, told apart by its serial -------
assert sandbox.is_sandbox("localhost:5555")
assert sandbox.is_sandbox("127.0.0.1:5555")
assert not sandbox.is_sandbox("emulator-5554")
assert not sandbox.is_sandbox("R58M12345")
assert not sandbox.is_sandbox(None)

# --- start: replaces any stale container, and boots at the asked geometry ---
calls, stopped = [], []
sandbox.status = lambda: ready
sandbox.stop = lambda: stopped.append(True)
sandbox._connect = lambda deadline: None
sandbox._await_boot = lambda serial, proc, deadline: None
sandbox._docker = lambda *a, **kw: (calls.append(a) or SimpleNamespace(returncode=0, stdout="", stderr=""))

# Static /dev/binder: a privileged container already shares /dev, so nothing is
# mounted in. Forced rather than read off the host, so the check means the same
# thing on a machine that happens to use binderfs.
sandbox.BINDERFS = Path("/nonexistent/binderfs")
sb = sandbox.Sandbox.start(720, 1280, 320)
assert stopped == [True], "a stale container was left holding port 5555"
argv = calls[0]
assert "androidboot.redroid_width=720" in argv, argv
assert "androidboot.redroid_height=1280" in argv, argv
assert "androidboot.redroid_dpi=320" in argv, argv
assert "--privileged" in argv and "-p" in argv
# ashmem is gone from every kernel this can run on; without memfd it dies at boot.
assert "androidboot.use_memfd=true" in argv, argv
# Ephemeral on purpose: no data volume, so every run starts from the same image.
assert "-v" not in argv, "the sandbox must not persist state"
assert (sb.serial, sb.width, sb.height, sb.dpi) == ("localhost:5555", 720, 1280, 320)

# Defaults still produce a real phone-shaped screen.
calls.clear()
sb = sandbox.Sandbox.start()
assert (sb.width, sb.height, sb.dpi) == sandbox.DEFAULT_GEOMETRY

# binderfs instead: the container cannot reach it unless it is handed over, and
# it is the only thing that may ever be mounted in.
calls.clear()
sandbox.BINDERFS = Path(__file__).parent          # any dir whose child exists
(Path(__file__).parent / "binder-control").mkdir(exist_ok=True)
try:
    sandbox.Sandbox.start()
finally:
    (Path(__file__).parent / "binder-control").rmdir()
argv = calls[0]
mounts = [argv[i + 1] for i, a in enumerate(argv) if a == "-v"]
assert mounts == [f"{Path(__file__).parent}:/dev/binderfs"], mounts

# --- and it refuses rather than starting something that cannot work ---------
sandbox.status = lambda: no_devices
try:
    sandbox.Sandbox.start()
except RuntimeError as e:
    assert "binderfs" in str(e)
else:
    raise AssertionError("started despite binder being unavailable")

print("sandbox: OK")
