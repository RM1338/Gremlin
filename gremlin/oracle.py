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
from . import platforms
from .platforms import CRASH, LAYOUT, HANG  # noqa: F401  (re-exported)

# How many following log lines to scan for the source location after a match —
# a framework prints the "relevant error-causing widget", or the JS stack, a few
# lines below the error itself.
_CONTEXT_AHEAD = 20
_CONTEXT_BEHIND = 2


@dataclass
class Signal:
    severity: str
    kind: str
    line: str  # the matched log line
    context: list[str] = field(default_factory=list)  # surrounding lines
    source_file: str | None = None
    source_line: int | None = None

    # The oracle used to be Flutter-only and named these `dart_*`. Reports and
    # run artifacts on disk still use those keys, so they stay readable here.
    @property
    def dart_file(self) -> str | None:
        return self.source_file

    @property
    def dart_line(self) -> int | None:
        return self.source_line

    def key(self) -> str:
        """Dedup key: same signal kind at the same source location is one bug.

        When there is no source location (e.g. jank), fall back to the log line
        with digits stripped, so "Skipped 30 frames" and "Skipped 47 frames"
        collapse into a single finding instead of inflating the bug count.
        """
        if self.source_file:
            loc = f"{self.source_file}:{self.source_line}"
        else:
            loc = re.sub(r"\d+", "N", self.line)[:80]
        return f"{self.kind}|{loc}"

    def summary(self) -> str:
        loc = f" ({self.source_file}:{self.source_line})" if self.source_file else ""
        return f"[{self.severity}] {self.kind}{loc}"


class Oracle:
    def __init__(self, device: Device, package: str | None = None,
                 platform: "platforms.Platform | str | None" = None) -> None:
        self.device = device
        self.package = package  # scope logcat to this app's PID, so other apps' noise is ignored
        # Which vocabulary of failure to match. A string is a platform id from a
        # Config; None keeps the historical Flutter default.
        self.platform = (platform if isinstance(platform, platforms.Platform)
                         else platforms.by_name(platform))
        self._proc: subprocess.Popen | None = None
        self._thread: threading.Thread | None = None
        self._lines: deque[str] = deque(maxlen=8000)
        self._lock = threading.Lock()
        self._cursor = 0  # index into the logical line stream already drained
        self._total = 0  # total lines ever appended
        self._pid: str | None = None  # the pid the stream is currently pinned to

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
        self._pid = pid
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
            match = self.platform.classify(line)  # first match wins, one per line
            if match is None:
                continue
            ahead = new_lines[i : i + _CONTEXT_AHEAD]
            behind = new_lines[max(0, i - _CONTEXT_BEHIND) : i]
            source_file, source_line = self._extract_location(ahead)
            signals.append(
                Signal(
                    severity=match.severity,
                    kind=match.kind,
                    line=line,
                    context=behind + ahead,
                    source_file=source_file,
                    source_line=source_line,
                )
            )
        return signals

    def _extract_location(self, lines: list[str]) -> tuple[str | None, int | None]:
        """First source location in these lines that points at real app code.

        React Native stacks are full of frames inside `node_modules` and inside
        the generated Metro bundle; pointing a report at those would be worse
        than pointing it nowhere, so they are skipped rather than accepted as a
        first match.
        """
        for ln in lines:
            for m in self.platform.location_re.finditer(ln):
                raw = m.group(1)
                if platforms.is_ignored_source(raw):
                    continue
                return self.platform.normalize_source_path(raw), int(m.group(2))
        return None, None

    def restart(self) -> None:
        """Re-attach the stream to the app's current process.

        Clears the buffered lines along with the log itself: everything in them
        belongs to a process that no longer exists, and the cursor arithmetic in
        drain() is only meaningful against one continuous stream.
        """
        old_thread = self._thread
        self.stop()
        if old_thread is not None:
            old_thread.join(timeout=2.0)
        with self._lock:
            self._lines.clear()
            self._cursor = 0
            self._total = 0
        self.start()

    def ensure_attached(self) -> bool:
        """Re-attach if the app is now a different process. True if it did.

        The stream is scoped to the app's pid so that other processes cannot
        contaminate a run — but that pin goes stale the moment the app's process
        is replaced, and then it matches nothing at all. The oracle does not
        error; it simply stops seeing anything, for the rest of the run, and the
        app is reported clean rather than unwatched.

        Two things replace the process. The explorer force-stops and relaunches
        in `_ensure_on_app` when a tap strands it in another app. And — the case
        that matters more — **any crash the oracle successfully detects kills the
        process**, after which Android may restart it. For a tool whose whole
        job is finding crashes, a stale pin is a consequence of success, not an
        edge case (docs/KNOWN_ISSUES.md, G1).
        """
        if not self.package or self._pid is None:
            return False  # an unscoped stream has no pin to go stale
        current = self._resolve_pid()
        if current is None or current == self._pid:
            # None means the app is not up at this instant. Restarting now would
            # resolve no pid and silently drop the filter, letting every other
            # app's noise into the run — worse than waiting for the next step.
            return False
        self.restart()
        return True

    def stop(self) -> None:
        if self._proc:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self._proc.kill()
            self._proc = None
