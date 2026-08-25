"""A containerised Android instance, so a run needs no phone and no emulator.

redroid runs Android's userspace — `init`, `zygote`, `system_server`, `logd` —
as ordinary Linux processes on the host kernel. No guest kernel, no QEMU, no
instruction translation, and ~2-3 GB instead of the emulator's 12-15 GB.

The reason this works for Gremlin specifically is `logd`: the oracle's entire
mechanism is `logcat --pid`, and logcat reads from a userspace daemon over a
socket, not from a kernel device. It survives containerisation untouched. So do
`screencap`, `input tap` and `uiautomator dump`, which travel over binder to
services that are all present. adb is exposed on TCP 5555, so everything
downstream sees an ordinary serial and `Config.serial` needs no change.

Two costs are deliberate, not bugs (see docs/SANDBOX.md §4):

  - **Linux only.** binder is a kernel feature; macOS and Windows Docker run a
    LinuxKit VM that does not ship it. Those users bring a phone or an AVD.
  - **Ephemeral by design.** No data volume, so every run starts from a
    byte-identical image. A phone accumulates state and an AVD accumulates
    snapshot drift; "fresh instance per run" is a claim worth being able to make.

Geometry is a boot parameter, which matters more here than it looks: the
dominant defect class is RenderFlex overflow, and overflow is screen-size
dependent. Sweeping form factors costs a container restart.

    python -m gremlin.sandbox status | start [--width W --height H --dpi D] | stop
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from .emulator import _adb_devices, _await_boot

# One container, one name — so a stale one from a killed run can be found and
# replaced rather than leaking and holding port 5555.
CONTAINER = "gremlin-sandbox"
PORT = 5555
SERIAL = f"localhost:{PORT}"
IMAGE = os.environ.get("REDROID_IMAGE", "redroid/redroid:13.0.0-latest")
BOOT_TIMEOUT = 180.0

# A mid-size phone. Overridable per start, which is the point of the parameter.
DEFAULT_GEOMETRY = (1080, 1920, 420)


def _docker(*args: str, timeout: float = 60.0) -> subprocess.CompletedProcess:
    return subprocess.run(["docker", *args], capture_output=True, text=True,
                          timeout=timeout)


# Where binder devices can appear. A loaded module is NOT enough: with an empty
# `devices` parameter and no binderfs mount it exposes nothing at all, which is
# the default on a stock Ubuntu kernel (CONFIG_ANDROID_BINDER_DEVICES="").
BINDER_NODE = Path("/dev/binder")
BINDERFS = Path("/dev/binderfs")


def binder_state() -> str:
    """"ok" | "no-devices" | "no-module" — how far binder is from usable."""
    if BINDER_NODE.exists() or (BINDERFS / "binder-control").exists():
        return "ok"
    return "no-devices" if Path("/sys/module/binder_linux").exists() else "no-module"


@dataclass(frozen=True)
class SandboxStatus:
    """What this machine can run, and what to do about the gaps."""
    docker: bool          # the client binary exists
    daemon: bool          # ...and the daemon answers
    binder: str           # binder_state() — the hard requirement
    image: bool           # the redroid image is already pulled
    container: str | None  # our container's state, if one exists

    @property
    def can_start(self) -> bool:
        return self.docker and self.daemon and self.binder == "ok"

    @property
    def problem(self) -> str | None:
        """One line saying why we cannot start, or None if we can."""
        if not self.docker:
            return ("Docker is not installed. The sandbox is a container; install "
                    "Docker Engine, or use a phone or an emulator instead.")
        if not self.daemon:
            return ("Docker is installed but its daemon is not reachable. Start it "
                    "with: sudo systemctl start docker")
        if self.binder == "no-module":
            # Deliberately no longer a command to paste. The console can do this
            # itself (see `setup()`), and on macOS/Windows no command exists —
            # binder is a Linux kernel feature, so those users need the emulator
            # instructions on the Setup page instead of a line that cannot work.
            return ("The kernel's binder driver is not loaded — Android's IPC "
                    "cannot work without it. Gremlin can set this up for you. "
                    "On macOS and Windows there is no binder at all: use a phone "
                    "or an emulator — the Setup page has step-by-step "
                    "instructions for both.")
        if self.binder == "no-devices":
            # The trap: `modprobe binder_linux` on its own looks like it worked
            # and leaves nothing behind, because distro kernels ship
            # CONFIG_ANDROID_BINDER_DEVICES="". Reloading with devices= is the
            # obvious fix and frequently impossible — Ubuntu marks the module
            # [permanent], so it cannot be unloaded before a reboot. Mounting
            # binderfs asks nothing of the module and always works.
            return ("binder_linux is loaded but exposes no devices — the kernel "
                    'ships CONFIG_ANDROID_BINDER_DEVICES="" and binderfs is not '
                    "mounted, so there is no binder node for Android to use. "
                    "Gremlin can mount it for you.")
        return None

    @property
    def note(self) -> str | None:
        """Something worth saying that is not a blocker."""
        if self.can_start and not self.image:
            return f"First start downloads {IMAGE} (~2-3 GB); later starts are seconds."
        return None


def status() -> SandboxStatus:
    """Everything the UI needs to explain the sandbox option to a developer."""
    have_docker = shutil.which("docker") is not None
    daemon = False
    image = False
    container = None
    if have_docker:
        daemon = _docker("info", timeout=20).returncode == 0
        if daemon:
            image = _docker("image", "inspect", IMAGE, timeout=20).returncode == 0
            out = _docker("inspect", "-f", "{{.State.Status}}", CONTAINER, timeout=20)
            container = out.stdout.strip() if out.returncode == 0 else None
    return SandboxStatus(docker=have_docker, daemon=daemon, binder=binder_state(),
                         image=image, container=container)


SETUP_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "sandbox-setup.sh"


def can_self_setup() -> bool:
    """True when the console can fix the prerequisites without a terminal.

    pkexec asks for the password in the desktop's own dialog, which is the whole
    point — the user clicks a button instead of being handed a modprobe command.
    It needs a polkit agent, so this is false over SSH and on a headless box,
    and there the UI falls back to showing the command.
    """
    return (SETUP_SCRIPT.exists() and shutil.which("pkexec") is not None
            and bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")))


def setup(timeout: float = 300.0) -> str:
    """Run the one-time host setup as root, via a graphical password prompt.

    Returns what it did. Raises RuntimeError with the script's own message when
    it could not — every one of those is a real environment problem (no binder in
    this kernel, no Docker) that no amount of retrying fixes.
    """
    if not SETUP_SCRIPT.exists():
        raise RuntimeError(f"the setup script is missing at {SETUP_SCRIPT}")
    if shutil.which("pkexec") is None:
        raise RuntimeError(
            f"pkexec is not installed, so the password prompt cannot be shown. "
            f"Run it yourself: sudo {SETUP_SCRIPT}")
    try:
        out = subprocess.run(["pkexec", str(SETUP_SCRIPT)],
                             capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as e:
        raise RuntimeError("the setup prompt timed out") from e
    if out.returncode == 126:
        # polkit's own code for "the user dismissed the dialog". Not a failure
        # worth a red banner — they said no.
        raise RuntimeError("cancelled — the password prompt was dismissed")
    if out.returncode != 0:
        detail = (out.stderr or out.stdout).strip() or f"exit {out.returncode}"
        raise RuntimeError(detail[:600])
    return out.stdout.strip()


def is_sandbox(serial: str | None) -> bool:
    """Whether a serial names a container rather than a device or an emulator."""
    return bool(serial and serial.split(":")[0] in ("localhost", "127.0.0.1"))


def running() -> bool:
    """True when our container is up *and* adb has actually attached to it."""
    return status().container == "running" and any(
        s == SERIAL and st == "device" for s, st in _adb_devices())


@dataclass
class Sandbox:
    """A booted Android container, and the handle needed to shut it down."""
    serial: str
    width: int
    height: int
    dpi: int

    @classmethod
    def start(cls, width: int | None = None, height: int | None = None,
              dpi: int | None = None, *, timeout: float = BOOT_TIMEOUT) -> "Sandbox":
        """Boot a fresh container and return once it is ready to be driven."""
        st = status()
        if st.problem:
            raise RuntimeError(st.problem)
        w, h, d = (width or DEFAULT_GEOMETRY[0], height or DEFAULT_GEOMETRY[1],
                   dpi or DEFAULT_GEOMETRY[2])

        # Any earlier container is holding port 5555 and carries state we do not
        # want. Replace it rather than failing on a name clash.
        stop()

        argv = [
            "run", "-d", "--rm", "--name", CONTAINER,
            # binder is a kernel driver; reaching it needs the privilege. This is
            # exactly why the sandbox is fine locally and wrong for multi-tenant
            # hosting (docs/SANDBOX.md §5).
            "--privileged",
            "-p", f"{PORT}:5555",
        ]
        # Where the host keeps binder decides what the container needs to see.
        # A privileged container already shares /dev, so static nodes need
        # nothing; a binderfs mount has to be handed over explicitly.
        if (BINDERFS / "binder-control").exists():
            argv += ["-v", f"{BINDERFS}:/dev/binderfs"]
        argv += [
            IMAGE,
            f"androidboot.redroid_width={w}",
            f"androidboot.redroid_height={h}",
            f"androidboot.redroid_dpi={d}",
            # No host GPU passthrough: SwiftShader renders in software. Slower,
            # but it runs on any machine and needs no driver matching.
            "androidboot.redroid_gpu_mode=guest",
            # ashmem was removed from the kernel in 5.18; Android falls back to
            # memfd, but only when told to. Without this it fails at boot on any
            # current kernel — which is every kernel this will ever run on.
            "androidboot.use_memfd=true",
        ]
        # The first run pulls a couple of GB, so this cannot use the short timeout.
        out = _docker(*argv, timeout=1800)
        if out.returncode != 0:
            raise RuntimeError(f"could not start the sandbox: {out.stderr.strip()[:400]}")

        deadline = time.monotonic() + timeout
        _connect(deadline)
        _await_boot(SERIAL, None, deadline=deadline)
        return cls(serial=SERIAL, width=w, height=h, dpi=d)

    def stop(self) -> None:
        stop()

    def __enter__(self) -> "Sandbox":
        return self

    def __exit__(self, *exc) -> None:
        self.stop()


def stop() -> None:
    """Remove the container and detach adb. Safe when nothing is running."""
    subprocess.run(["adb", "disconnect", SERIAL], capture_output=True, timeout=30)
    _docker("rm", "-f", CONTAINER, timeout=60)


def ensure_installed(cfg, on_status=None) -> None:
    """Put the app in the sandbox, because a container starts with no apps in it.

    Sandbox only, and that restriction is the whole safety argument: a container
    is guaranteed fresh, so a missing package there means "not installed yet".
    On a phone or an emulator it more likely means the target is wrong, and
    building someone's project uninvited is not the answer to that.

    Raises RuntimeError with something worth reading; the caller decides whether
    that becomes a `sys.exit` or a line in the browser.
    """
    from .device import Device
    from . import platforms

    say = on_status or (lambda _m: None)
    if cfg.package in Device(cfg.serial).list_third_party_packages():
        return
    root = Path(cfg.scribe_root)
    if not (root / "android").is_dir():
        raise RuntimeError(
            f"{cfg.package} is not installed in the sandbox, and there is no app "
            f"project at {root} to build it from. "
            f"Install it yourself: adb -s {cfg.serial} install -r <apk>")
    say(f"{cfg.package} is not in the sandbox \u2014 building {root.name}\u2026")
    try:
        apk = platforms.by_name(cfg.platform).build(root)
        say(f"installing {apk.name} into the sandbox\u2026")
        subprocess.run(["adb", "-s", cfg.serial, "install", "-r", str(apk)],
                       check=True, timeout=600)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired,
            FileNotFoundError) as e:
        raise RuntimeError(
            f"could not install {cfg.package} into the sandbox: {e}") from e
    say(f"installed {cfg.package} into {cfg.serial}")


def _connect(deadline: float) -> None:
    """Attach adb to the container, retrying while adbd finishes coming up.

    `adb connect` reports success on a bare TCP accept, so a single call can
    "succeed" against a socket that dies moments later. Retrying until the
    serial actually shows up in `adb devices` is what makes this reliable.
    """
    last = ""
    while time.monotonic() < deadline:
        out = subprocess.run(["adb", "connect", SERIAL], capture_output=True,
                             text=True, timeout=30)
        last = (out.stdout + out.stderr).strip()
        if any(s == SERIAL for s, _ in _adb_devices()):
            return
        time.sleep(2.0)
    raise TimeoutError(f"adb could not attach to the sandbox on {SERIAL}: {last}")


if __name__ == "__main__":
    import argparse
    import sys

    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("action", choices=("status", "start", "stop"))
    ap.add_argument("--width", type=int)
    ap.add_argument("--height", type=int)
    ap.add_argument("--dpi", type=int)
    args = ap.parse_args()

    if args.action == "status":
        st = status()
        print(f"docker    {'yes' if st.docker else 'no'}")
        print(f"daemon    {'up' if st.daemon else 'down'}")
        print(f"binder    {'ok' if st.binder == 'ok' else st.binder.upper()}")
        print(f"image     {IMAGE} {'pulled' if st.image else 'not pulled'}")
        print(f"container {st.container or 'none'}")
        print(f"\n{st.problem or st.note or 'ready — python -m gremlin.sandbox start'}")
        sys.exit(0 if st.can_start else 1)

    if args.action == "stop":
        stop()
        print("sandbox stopped.")
        sys.exit(0)

    try:
        sb = Sandbox.start(args.width, args.height, args.dpi)
    except (RuntimeError, TimeoutError) as e:
        sys.exit(f"sandbox did not start: {e}")
    print(f"sandbox up on {sb.serial} at {sb.width}x{sb.height} @{sb.dpi}dpi\n"
          f"install an app:  adb -s {sb.serial} install -r app-debug.apk\n"
          f"run against it:  GREMLIN_SERIAL={sb.serial} python run.py")
