"""Device layer: a thin, deterministic wrapper over adb.

Exposes the four verbs the whole project is built on — screenshot, tap, type,
back — plus scroll and a launcher. Every higher layer (the explorer and the
replayer both) drives the device through exactly this surface, which is what
makes a recorded trace reproduce by construction.
"""

from __future__ import annotations

import subprocess
import time


# adb's `input text` uses these as separators/metacharacters, so they must be
# escaped or substituted before they reach the shell.
_TEXT_SUBSTITUTIONS = {
    " ": "%s",
}
_TEXT_ESCAPE = set("()<>|;&*\\~\"'`$")


def choose_serial(explicit: str | None = None) -> str | None:
    """Which device to drive when nobody said, or None for "adb decides".

    Returns the explicit choice untouched, and None when adb has exactly one
    candidate and can pick for itself. The interesting case is several attached:
    the sandbox is chosen, and only the sandbox, because it is disposable and a
    phone is not. Guessing at the first serial adb happens to list would point a
    tapping agent at real hardware someone is holding.

    Raises when several are attached and none is the sandbox, because at that
    point there is no safe answer and picking one would be worse than stopping.
    """
    if explicit:
        return explicit
    try:
        out = subprocess.run(["adb", "devices"], capture_output=True,
                             timeout=10).stdout.decode("utf-8", "replace")
    except Exception:
        return None
    attached = [ln.split("\t")[0] for ln in out.splitlines()[1:]
                if "\t" in ln and ln.split("\t")[1].strip() == "device"]
    if len(attached) <= 1:
        return None  # adb has no ambiguity to resolve
    from .sandbox import SERIAL as SANDBOX_SERIAL
    if SANDBOX_SERIAL in attached:
        return SANDBOX_SERIAL
    raise RuntimeError(
        f"several devices are attached ({', '.join(attached)}) and none is the "
        f"sandbox. Set GREMLIN_SERIAL, or pass --serial, to say which one you "
        f"mean — this drives taps, so it will not choose for you."
    )


class Device:
    def __init__(self, serial: str | None = None) -> None:
        self.serial = serial
        self._size: tuple[int, int] | None = None

    # ---- low-level adb plumbing ------------------------------------------

    def _base(self) -> list[str]:
        cmd = ["adb"]
        if self.serial:
            cmd += ["-s", self.serial]
        return cmd

    def _shell(self, *args: str, timeout: float = 15.0) -> str:
        """Run `adb shell <args>` and return stdout as text."""
        out = subprocess.run(
            self._base() + ["shell", *args],
            capture_output=True,
            timeout=timeout,
        )
        self._check_ambiguous(out.stderr)
        return out.stdout.decode("utf-8", "replace")

    @staticmethod
    def _check_ambiguous(stderr: bytes) -> None:
        """Turn adb's ambiguity into a sentence, at the one place all calls pass.

        With two things attached — a phone and the sandbox, say — adb refuses
        every command with "more than one device/emulator" on *stderr* and an
        empty stdout. Callers then parse the empty string and fail somewhere far
        away with something meaningless: `wm size` produced "not enough values to
        unpack (expected 2, got 1)", which names neither adb nor the real
        problem. Raising here means every adb-backed call reports the same
        actionable message instead of failing in its own private way.
        """
        if b"more than one device" not in (stderr or b""):
            return
        try:
            listing = subprocess.run(["adb", "devices"], capture_output=True,
                                     timeout=10).stdout.decode("utf-8", "replace")
            serials = [ln.split()[0] for ln in listing.splitlines()[1:]
                       if ln.strip() and "\t" in ln]
        except Exception:
            serials = []
        which = ", ".join(serials) if serials else "several"
        raise RuntimeError(
            f"more than one device is attached ({which}) and none was chosen. "
            f"Pass --serial <serial>, or set GREMLIN_SERIAL. "
            f"(Testing a web app? It needs no device at all: run.py --url <address>.)"
        )

    def _raw(self, *args: str, timeout: float = 15.0) -> bytes:
        """Run `adb <args>` and return raw stdout bytes (for binary output)."""
        out = subprocess.run(
            self._base() + list(args),
            capture_output=True,
            timeout=timeout,
        )
        self._check_ambiguous(out.stderr)
        return out.stdout

    # ---- lifecycle -------------------------------------------------------

    def prepare(self) -> None:
        """Keep the screen on and awake for the duration of a run.

        The display sleeping mid-run silently breaks screenshots and taps, so
        we hold it on while the device is on USB power.
        """
        self._shell("svc", "power", "stayon", "usb")
        self._shell("input", "keyevent", "KEYCODE_WAKEUP")

    def screen_size(self) -> tuple[int, int]:
        if self._size is None:
            # `wm size` prints e.g. "Physical size: 1080x2340".
            out = self._shell("wm", "size")
            dims = out.strip().split(":")[-1].strip()
            w, h = dims.split("x")
            self._size = (int(w), int(h))
        return self._size

    def foreground_package(self) -> str | None:
        """Best-effort package name of the app currently in focus."""
        out = self._shell("dumpsys", "window")
        for line in out.splitlines():
            if "mCurrentFocus" in line and "/" in line:
                # e.g. "mCurrentFocus=Window{.. u0 com.scribe.scribe/.MainActivity}"
                token = line.split("/")[0].split()[-1]
                return token or None
        return None

    def list_third_party_packages(self) -> list[str]:
        """User-installed (non-system) package names on the device."""
        try:
            out = self._shell("pm", "list", "packages", "-3")
        except Exception:
            return []
        return sorted(l[len("package:"):].strip() for l in out.splitlines() if l.startswith("package:"))

    def resolve_launcher(self, package: str) -> str | None:
        """The launcher activity component for a package, e.g. `pkg/.Main`."""
        try:
            out = self._shell(
                "cmd", "package", "resolve-activity", "--brief",
                "-a", "android.intent.action.MAIN",
                "-c", "android.intent.category.LAUNCHER", package,
            )
        except Exception:
            return None
        for line in reversed(out.strip().splitlines()):
            line = line.strip()
            if "/" in line and " " not in line:  # a bare component line
                return line
        return None

    def launch(self, activity: str) -> None:
        """Start the app's main activity."""
        self._shell("am", "start", "-n", activity)
        time.sleep(2.5)

    def relaunch(self, package: str, activity: str) -> None:
        """Force-stop and restart the app for a fresh-ish start.

        We deliberately do NOT `pm clear` (that would wipe the user's real
        Scribe data on the physical device); we only force-stop, so app state
        may carry over between runs.
        """
        self._shell("am", "force-stop", package)
        time.sleep(1.0)
        self.launch(activity)

    # ---- the four verbs --------------------------------------------------

    def screenshot(self) -> bytes:
        """Return a PNG of the current screen."""
        return self._raw("exec-out", "screencap", "-p")

    def tap(self, x: int, y: int) -> None:
        self._shell("input", "tap", str(int(x)), str(int(y)))
        time.sleep(0.6)

    def type_text(self, text: str) -> None:
        self._shell("input", "text", self._encode_text(text))
        time.sleep(0.4)

    def clear_text(self, n: int = 80) -> None:
        """Best-effort empty the focused text field before typing into it: move
        the cursor to the end, then send n deletes. A field can arrive holding a
        remembered value (last-used email, keyboard autofill), and `input text`
        only appends — so without this a login field becomes "oldnew@…"."""
        self._shell("input", "keyevent", "123", *(["67"] * n))  # MOVE_END, DEL*n
        time.sleep(0.3)

    def back(self) -> None:
        self._shell("input", "keyevent", "KEYCODE_BACK")
        time.sleep(0.6)

    def scroll(self, direction: str = "down") -> None:
        """Swipe to scroll. Direction is the content's travel direction."""
        w, h = self.screen_size()
        cx = w // 2
        # Swipe from lower-mid to upper-mid to scroll down, and vice versa.
        y1, y2 = (int(h * 0.7), int(h * 0.3))
        if direction == "up":
            y1, y2 = y2, y1
        self._shell("input", "swipe", str(cx), str(y1), str(cx), str(y2), "300")
        time.sleep(0.6)

    # ---- perception ------------------------------------------------------

    def elements(self):
        """The controls on the current screen, from the accessibility tree.

        Lives here so the explorer can ask whatever driver it holds for its own
        elements — adb reads uiautomator, the browser reads the DOM — instead of
        calling an Android-only helper directly. Imported lazily because
        grounding imports this module.
        """
        from .grounding import dump_elements
        return dump_elements(self)

    # ---- helpers ---------------------------------------------------------

    @staticmethod
    def _encode_text(text: str) -> str:
        """Make a string safe for `adb shell input text`."""
        out = []
        for ch in text:
            if ch in _TEXT_SUBSTITUTIONS:
                out.append(_TEXT_SUBSTITUTIONS[ch])
            elif ch in _TEXT_ESCAPE:
                out.append("\\" + ch)
            else:
                out.append(ch)
        return "".join(out)
