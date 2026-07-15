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
        return out.stdout.decode("utf-8", "replace")

    def _raw(self, *args: str, timeout: float = 15.0) -> bytes:
        """Run `adb <args>` and return raw stdout bytes (for binary output)."""
        out = subprocess.run(
            self._base() + list(args),
            capture_output=True,
            timeout=timeout,
        )
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
