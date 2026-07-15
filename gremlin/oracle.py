"""The oracle: what counts as a bug.

Gremlin never asks a model whether a screen looks broken — that judgment is
unreliable and unfalsifiable. Instead it watches `adb logcat` and matches against
a small set of exact signals the Flutter framework prints when it fails. Either
the string is in the log or it isn't; detection is ground truth.

A background thread streams logcat into a ring buffer. After each action the
explorer calls `drain()`, which returns the signals that appeared since the last
drain — so a failure is attributed to the action that just executed, not merely
to "somewhere in the run".
"""

from __future__ import annotations

import re
import subprocess
import threading
from collections import deque
from dataclasses import dataclass, field

from .device import Device


# Severity ranks so the dashboard and dedup can order findings.
CRASH = "crash"
LAYOUT = "layout"
HANG = "hang"

# Each signal: (severity, kind, compiled pattern). Order matters only for the
# first-match-wins scan within a single line.
_SIGNAL_SPECS: list[tuple[str, str, re.Pattern]] = [
    (CRASH, "native-crash", re.compile(r"FATAL EXCEPTION")),
    (CRASH, "dart-exception", re.compile(r"Unhandled Exception", re.IGNORECASE)),
    (LAYOUT, "renderflex-overflow", re.compile(r"A RenderFlex overflowed by", re.IGNORECASE)),
    # Flutter prints this as an uppercase banner: "EXCEPTION CAUGHT BY RENDERING LIBRARY".
    (LAYOUT, "render-error", re.compile(r"Exception caught by rendering library", re.IGNORECASE)),
    (HANG, "jank", re.compile(r"Skipped \d+ frames")),
    # Gremlin probe marker (see gremlin_probe.dart). Modern Flutter (Impeller)
    # doesn't reliably print framework/Dart errors to logcat, so an app under
    # test can opt in and forward them here. A marker line that also contains a
    # specific phrase above (e.g. an overflow) is already classified by that
    # phrase — this catch-all only fires for errors none of those matched.
    (CRASH, "dart-exception", re.compile(r"GREMLIN_BUG")),
]

# In a debug build the framework names the offending widget's source location.
# e.g. "... library_screen.dart:42:15" or "package:scribe/screens/x.dart:10".
_DART_LOCATION_RE = re.compile(r"([\w./]+\.dart):(\d+)(?::(\d+))?")

# How many following log lines to scan for the source location after a match —
# Flutter prints the "relevant error-causing widget" a few lines below the error.
_CONTEXT_AHEAD = 20
_CONTEXT_BEHIND = 2


@dataclass
class Signal:
    severity: str
    kind: str
    line: str  # the matched log line
    context: list[str] = field(default_factory=list)  # surrounding lines
    dart_file: str | None = None
    dart_line: int | None = None

    def key(self) -> str:
        """Dedup key: same signal kind at the same source location is one bug.

        When there is no source location (e.g. jank), fall back to the log line
        with digits stripped, so "Skipped 30 frames" and "Skipped 47 frames"
        collapse into a single finding instead of inflating the bug count.
        """
        if self.dart_file:
            loc = f"{self.dart_file}:{self.dart_line}"
        else:
            loc = re.sub(r"\d+", "N", self.line)[:80]
        return f"{self.kind}|{loc}"

    def summary(self) -> str:
        loc = f" ({self.dart_file}:{self.dart_line})" if self.dart_file else ""
        return f"[{self.severity}] {self.kind}{loc}"


class Oracle:
    def __init__(self, device: Device, package: str | None = None) -> None:
        self.device = device
        self.package = package  # scope logcat to this app's PID, so other apps' noise is ignored
        self._proc: subprocess.Popen | None = None
        self._thread: threading.Thread | None = None
        self._lines: deque[str] = deque(maxlen=8000)
        self._lock = threading.Lock()
        self._cursor = 0  # index into the logical line stream already drained
        self._total = 0  # total lines ever appended

    def _resolve_pid(self) -> str | None:
        if not self.package:
            return None
        out = self.device._shell("pidof", self.package).strip()
        return out.split()[0] if out else None

    def start(self) -> None:
        """Clear the log and begin streaming in the background."""
        # Clear so nothing from before this run is attributed to it.
        subprocess.run(self.device._base() + ["logcat", "-c"], capture_output=True)
        cmd = self.device._base() + ["logcat", "-v", "brief"]
        # Scope to the app's process so background apps (music, system) can't have
        # their jank/errors misattributed to the app under test.
        pid = self._resolve_pid()
        if pid:
            cmd += ["--pid", pid]
        # logcat can emit non-UTF-8 bytes; decode leniently so the reader thread
        # never dies mid-stream and drops later signals.
        self._proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            bufsize=1,
            text=True,
            errors="replace",
        )
        self._thread = threading.Thread(target=self._reader, daemon=True)
        self._thread.start()

    def _reader(self) -> None:
        assert self._proc and self._proc.stdout
        for line in self._proc.stdout:
            with self._lock:
                self._lines.append(line.rstrip("\n"))
                self._total += 1

    def drain(self) -> list[Signal]:
        """Return signals that appeared since the last drain."""
        with self._lock:
            lines = list(self._lines)
            total = self._total
            buffered_start = total - len(lines)
            # Scan only lines newer than the cursor that are still in the buffer.
            scan_from = max(self._cursor, buffered_start)
            offset = scan_from - buffered_start
            new_lines = lines[offset:]
            self._cursor = total

        signals: list[Signal] = []
        for i, line in enumerate(new_lines):
            for severity, kind, pattern in _SIGNAL_SPECS:
                if pattern.search(line):
                    ahead = new_lines[i : i + _CONTEXT_AHEAD]
                    behind = new_lines[max(0, i - _CONTEXT_BEHIND) : i]
                    dart_file, dart_line = self._extract_location(ahead)
                    signals.append(
                        Signal(
                            severity=severity,
                            kind=kind,
                            line=line,
                            context=behind + ahead,
                            dart_file=dart_file,
                            dart_line=dart_line,
                        )
                    )
                    break  # one signal per line
        return signals

    @staticmethod
    def _extract_location(lines: list[str]) -> tuple[str | None, int | None]:
        for ln in lines:
            m = _DART_LOCATION_RE.search(ln)
            if m:
                return m.group(1), int(m.group(2))
        return None, None

    def stop(self) -> None:
        if self._proc:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self._proc.kill()
            self._proc = None
