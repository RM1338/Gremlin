"""Android emulator control, so a run needs no physical phone.

Everything above the device layer talks to adb and nothing else, and an emulator
is just another adb serial (`emulator-5554`). So this module has exactly one
job — get an emulator booted and hand back its serial — and the explorer, the
oracle and the replayer are none the wiser. That is also why this is *not* a
per-toolkit feature: a booted emulator serves a Flutter run and a React Native
run identically.

    from gremlin.emulator import Emulator, list_avds

    print(list_avds())                  # ['Pixel_7_API_34', ...]
    emu = Emulator.start("Pixel_7_API_34")
    Device(serial=emu.serial)           # ... drive it like any other device
    emu.stop()

The Android SDK ships `emulator` and `avdmanager` as separate packages from the
platform-tools that provide `adb`, so a machine with adb may still have neither.
`sdk_status()` reports exactly what is missing and how to install it, rather
than failing at the point of use with a bare FileNotFoundError.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path


# Where the SDK usually lands, in the order we should believe it.
_SDK_CANDIDATES = (
    "~/Android/Sdk",           # Android Studio on Linux
    "~/Library/Android/sdk",   # Android Studio on macOS
    "~/AppData/Local/Android/Sdk",
    "/usr/lib/android-sdk",    # Debian/Ubuntu package
    "/opt/android-sdk",
)

# How long to wait for a cold boot before giving up. A first boot of a fresh AVD
# on a machine without KVM genuinely can take minutes, so this is generous.
BOOT_TIMEOUT = 300.0

# Software emulation is roughly an order of magnitude slower to boot, and a cold
# first boot is the worst case of all, so the accelerated timeout is nowhere near
# enough. Overridable, because how bad this gets depends entirely on the host.
SOFTWARE_BOOT_TIMEOUT = float(os.environ.get("GREMLIN_SOFTWARE_BOOT_TIMEOUT", 1800.0))


def kvm_available() -> bool:
    """Whether hardware acceleration can actually be used from this process.

    Existing is not enough: in a container /dev/kvm is only present when the host
    allowed it to be mapped in, and readable only if the process is in the owning
    group. Both fail quietly and separately, so test the access rather than the
    path.
    """
    return os.access("/dev/kvm", os.R_OK | os.W_OK)


def sdk_root() -> Path | None:
    """The Android SDK directory, from the environment or the usual places."""
    for var in ("ANDROID_HOME", "ANDROID_SDK_ROOT"):
        raw = os.environ.get(var)
        if raw and Path(raw).expanduser().is_dir():
            return Path(raw).expanduser()
    for cand in _SDK_CANDIDATES:
        p = Path(cand).expanduser()
        if p.is_dir():
            return p
    return None


def _sdk_tool(name: str) -> str | None:
    """Absolute path to an SDK tool, whether or not it is on PATH.

    `emulator` and `avdmanager` live in fixed subdirectories of the SDK, and are
    frequently not exported to PATH even on a working Android Studio install.
    """
    found = shutil.which(name)
    if found:
        return found
    root = sdk_root()
    if root is None:
        return None
    # avdmanager moved into cmdline-tools; the old tools/bin location lingers.
    relative = {
        "emulator": ["emulator/emulator"],
        "avdmanager": ["cmdline-tools/latest/bin/avdmanager",
                       "cmdline-tools/bin/avdmanager",
                       "tools/bin/avdmanager"],
        "sdkmanager": ["cmdline-tools/latest/bin/sdkmanager",
                       "cmdline-tools/bin/sdkmanager",
                       "tools/bin/sdkmanager"],
    }.get(name, [])
    for rel in relative:
        p = root / rel
        if p.is_file() and os.access(p, os.X_OK):
            return str(p)
    return None


@dataclass(frozen=True)
class SdkStatus:
    """What emulator tooling this machine has, and what to do about the gaps."""
    sdk: Path | None
    emulator: str | None
    avdmanager: str | None
    avds: tuple[str, ...]

    @property
    def can_boot(self) -> bool:
        return bool(self.emulator and self.avds)

    @property
    def problem(self) -> str | None:
        """A one-line explanation of why we cannot boot, or None if we can."""
        if self.sdk is None:
            return ("No Android SDK found. Install Android Studio, or set "
                    "ANDROID_HOME to an existing SDK.")
        if self.emulator is None:
            return (f"SDK at {self.sdk} has no emulator package. Install it with: "
                    f"sdkmanager --install emulator")
        if not self.avds:
            return ("No AVDs defined. Create one in Android Studio's Device Manager, "
                    "or with: avdmanager create avd -n gremlin "
                    "-k 'system-images;android-34;google_apis;x86_64'")
        return None


def sdk_status() -> SdkStatus:
    """Everything the UI needs to explain the emulator option to a developer."""
    return SdkStatus(
        sdk=sdk_root(),
        emulator=_sdk_tool("emulator"),
        avdmanager=_sdk_tool("avdmanager"),
        avds=tuple(list_avds()),
    )


def list_avds() -> list[str]:
    """Names of the virtual devices defined on this machine."""
    emu = _sdk_tool("emulator")
    if emu is None:
        return []
    try:
        out = subprocess.run([emu, "-list-avds"], capture_output=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return []
    names = []
    for line in out.stdout.decode("utf-8", "replace").splitlines():
        line = line.strip()
        # The emulator prints incidental warnings to stdout on some installs;
        # an AVD name never contains whitespace.
        if line and " " not in line and not line.startswith("("):
            names.append(line)
    return names


def _headless_gpu() -> str:
    """The renderer for a windowless emulator: the real GPU wherever there is one.

    Every software renderer the emulator ships (swiftshader_indirect, swangle,
    lavapipe) segfaulted its RenderThread two steps into the Flutter bench
    fixture, every run, and disabling guest Vulkan did not change that. `host`
    renders through the machine's GPU without needing a window, and ran the
    same fixture to coverage-complete. SwiftShader remains the fallback where
    there is no GPU render node, and GREMLIN_EMULATOR_GPU overrides both.
    """
    override = os.environ.get("GREMLIN_EMULATOR_GPU")
    if override:
        return override
    has_gpu = any(Path("/dev/dri").glob("renderD*")) if Path("/dev/dri").is_dir() else False
    return "host" if has_gpu else "swiftshader_indirect"


def _avd_dir(avd: str) -> Path:
    home = os.environ.get("ANDROID_AVD_HOME") or Path.home() / ".android" / "avd"
    return Path(home) / f"{avd}.avd"


def _pid_alive(pid: int) -> bool:
    """Running, and not a zombie: a zombie has exited and holds nothing."""
    try:
        stat = Path(f"/proc/{pid}/stat").read_text()
    except OSError:
        return False
    # The state follows the parenthesised command name, which may contain spaces.
    return stat.rsplit(")", 1)[-1].split()[0] != "Z"


def clear_stale_lock(avd: str) -> bool:
    """Remove an AVD's lock left by an emulator that is no longer running.

    A crashed emulator leaves `hardware-qemu.ini.lock` naming its pid. While
    that pid exists the emulator refuses the AVD ("Running multiple emulators
    with the same AVD ..."), and a zombie still exists: the console that
    started the emulator reaps it only when it next polls, so one crash made
    the AVD unbootable until the console was restarted. Returns whether a
    lock was cleared.
    """
    lock = _avd_dir(avd) / "hardware-qemu.ini.lock"
    try:
        pid = int(lock.read_text().strip("\0 \n"))
    except (OSError, ValueError, IndexError):
        return False
    if _pid_alive(pid):
        return False
    for name in ("hardware-qemu.ini.lock", "multiinstance.lock"):
        try:
            (_avd_dir(avd) / name).unlink()
        except OSError:
            pass
    return True


def running_emulators() -> list[str]:
    """Serials of emulators currently visible to adb."""
    return [s for s, _ in _adb_devices() if s.startswith("emulator-")]


def has_window(serial: str) -> bool | None:
    """Whether a running emulator has a desktop window; None if we cannot tell.

    The emulator names its own discovery file, which is keyed by its pid, and
    the pid's command line says whether it was started with -no-window. A
    caller that needs isolation treats None as "has one".
    """
    try:
        out = subprocess.run(["adb", "-s", serial, "emu", "avd", "discoverypath"],
                             capture_output=True, text=True, timeout=10).stdout
        pid = re.search(r"pid_(\d+)\.ini", out).group(1)
        argv = Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0")
    except (OSError, subprocess.TimeoutExpired, AttributeError):
        return None
    return b"-no-window" not in argv


def _adb_devices() -> list[tuple[str, str]]:
    """(serial, state) for every device adb can see."""
    try:
        out = subprocess.run(["adb", "devices"], capture_output=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return []
    devices = []
    for line in out.stdout.decode("utf-8", "replace").splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 2:
            devices.append((parts[0], parts[1]))
    return devices


@dataclass
class Emulator:
    """A booted emulator, and the handle needed to shut it down again."""
    serial: str
    avd: str
    process: subprocess.Popen | None = None

    @classmethod
    def start(cls, avd: str | None = None, *, timeout: float = BOOT_TIMEOUT,
              headless: bool = True, reuse: bool = True) -> "Emulator":
        """Boot `avd` (or the first one defined) and wait until it is usable.

        Returns once the system reports `sys.boot_completed` *and* the package
        manager answers, because adb accepts a connection well before the device
        can install or launch anything — booting on the first signal alone makes
        the first action of a run flaky.

        With `reuse`, an already-running emulator is adopted instead of booting a
        second one, which is what a developer re-running Gremlin actually wants.
        """
        status = sdk_status()
        if status.emulator is None or not status.avds:
            raise RuntimeError(status.problem or "Cannot start an emulator.")

        avd = avd or status.avds[0]
        if avd not in status.avds:
            raise RuntimeError(f"No such AVD: {avd!r}. Available: {', '.join(status.avds)}")

        if reuse:
            for serial in running_emulators():
                # A windowed emulator is not adopted for a headless boot: reusing
                # it would hand the run a device someone can click on.
                if headless and has_window(serial) is not False:
                    continue
                if _is_booted(serial):
                    return cls(serial=serial, avd=avd, process=None)

        clear_stale_lock(avd)
        before = {s for s, _ in _adb_devices()}
        cmd = [status.emulator, "-avd", avd, "-no-snapshot-save", "-no-boot-anim"]
        if headless:
            # No window, by default. The emulator is the sandbox's stand-in, and
            # a window on the desktop is an input path into the device under
            # test: a stray click mid-run lands taps the trace never recorded,
            # and the run stops being reproducible. Only Gremlin's adb verbs
            # should reach it; a window is for debugging the emulator itself.
            cmd += ["-no-window", "-gpu", _headless_gpu()]

        if not kvm_available():
            # QEMU emulates the guest CPU instruction by instruction. That is far
            # too slow to use by hand, but Gremlin spends seconds in a vision-model
            # call between one tap and the next, so the emulator is idle for most
            # of a run and its slowness is largely hidden. Worth attempting on a
            # host that refuses to map /dev/kvm, where the alternative is no
            # emulator at all — but treat it as a fallback, not a target.
            cmd += ["-accel", "off"]
            # An unaccelerated guest is slow enough that the emulator's simulated
            # network latency becomes a real share of each step.
            cmd += ["-netdelay", "none", "-netspeed", "full"]
            if timeout == BOOT_TIMEOUT:
                timeout = SOFTWARE_BOOT_TIMEOUT

        # The emulator explains its own refusals ("not enough disk space", "no
        # KVM permission") on stdout and then exits. Keeping that output is the
        # difference between a fixable message and a bare exit status, so it
        # goes to a temp file we can quote back if the boot fails.
        log = tempfile.NamedTemporaryFile(mode="w+", suffix=".emulator.log", delete=False)
        proc = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT)

        try:
            serial = _await_new_serial(before, proc, timeout=timeout, log=log.name)
            _await_boot(serial, proc, deadline=time.monotonic() + timeout, log=log.name)
        except (RuntimeError, TimeoutError):
            proc.kill()
            raise
        finally:
            log.close()
        return cls(serial=serial, avd=avd, process=proc)

    def stop(self) -> None:
        """Shut the emulator down. Safe to call on an adopted emulator."""
        subprocess.run(["adb", "-s", self.serial, "emu", "kill"],
                       capture_output=True, timeout=30)
        if self.process is not None:
            try:
                self.process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                self.process.kill()

    def __enter__(self) -> "Emulator":
        return self

    def __exit__(self, *exc) -> None:
        self.stop()


def _why_it_died(log_path: str | None) -> str:
    """The emulator's own explanation for refusing to start, if it gave one."""
    if not log_path:
        return ""
    try:
        text = Path(log_path).read_text(errors="replace")
    except OSError:
        return ""
    # It prints its refusal as a FATAL line, sometimes preceded by the failed
    # compatibility check that explains it.
    reasons = [l.strip() for l in text.splitlines()
               if re.search(r"^\s*(FATAL|ERROR)\s*\|", l) or "Error:" in l]
    if not reasons:
        return ""
    # Dedup while keeping order; the same reason is often logged twice.
    seen, unique = set(), []
    for r in reasons:
        cleaned = re.sub(r"^\s*\w+\s*\|\s*", "", r)
        if cleaned not in seen:
            seen.add(cleaned)
            unique.append(cleaned)
    return "\n  " + "\n  ".join(unique[:4])


def _await_new_serial(before: set[str], proc: subprocess.Popen,
                      *, timeout: float, log: str | None = None) -> str:
    """Wait for a serial that wasn't there before we launched the emulator.

    Diffing against the pre-launch set is how we stay correct when the developer
    already has a phone plugged in or another emulator running — the console
    port the emulator picks is not predictable.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(
                f"The emulator exited (status {proc.returncode}) before adb saw it."
                + (_why_it_died(log) or
                   "\n  No reason given; run `emulator -avd <name>` by hand to see why.")
            )
        new = {s for s, _ in _adb_devices() if s.startswith("emulator-")} - before
        if new:
            return sorted(new)[0]
        time.sleep(1.0)
    raise TimeoutError(f"No emulator appeared in adb within {timeout:.0f}s.")


def _await_boot(serial: str, proc: subprocess.Popen | None, *, deadline: float,
                log: str | None = None) -> None:
    """Block until the emulator is genuinely ready to be driven."""
    while time.monotonic() < deadline:
        if proc is not None and proc.poll() is not None:
            raise RuntimeError(
                f"The emulator exited (status {proc.returncode}) while booting."
                + _why_it_died(log))
        if _is_booted(serial):
            return
        time.sleep(2.0)
    raise TimeoutError(f"{serial} did not finish booting within the timeout.")


def _is_booted(serial: str) -> bool:
    """True once the device reports a completed boot and a live package manager."""
    if _getprop(serial, "sys.boot_completed").strip() != "1":
        return False
    # `pm` answering is the real readiness signal; boot_completed fires earlier.
    try:
        out = subprocess.run(["adb", "-s", serial, "shell", "pm", "path", "android"],
                             capture_output=True, timeout=15)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return b"package:" in out.stdout


def _getprop(serial: str, prop: str) -> str:
    try:
        out = subprocess.run(["adb", "-s", serial, "shell", "getprop", prop],
                             capture_output=True, timeout=15)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return out.stdout.decode("utf-8", "replace")


def is_emulator(serial: str | None) -> bool:
    """Whether a serial names an emulator rather than a physical device."""
    return bool(serial and serial.startswith("emulator-"))
