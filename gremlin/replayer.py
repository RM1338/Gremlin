"""The replayer: drive the device from a recorded trace, with no model.

This is the device layer driven from a recorded trace instead of from the
policy — the same four verbs, zero inference, fully deterministic. Because it
shares its execution path with the explorer, a trace that reproduced a bug once
reproduces it again by construction. That property is what lets the fixer grade
a patch without a human in the room.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from .config import Config
from .device import Device
from .models import Action
from .oracle import Oracle, Signal


@dataclass
class ReplayResult:
    signals: list[Signal] = field(default_factory=list)
    final_screenshot: bytes = b""  # the failing screen, re-reached deterministically

    def has(self, dedup_key: str) -> bool:
        """Did a signal with this dedup key appear during replay?"""
        return any(s.key() == dedup_key for s in self.signals)

    def keys(self) -> set[str]:
        return {s.key() for s in self.signals}

    def stable_keys(self) -> set[str]:
        """Identities that survive the patch having moved lines around."""
        return {s.stable_key() for s in self.signals}


def _execute(dev: Device, a: Action) -> None:
    if a.verb == "tap" and a.x is not None and a.y is not None:
        dev.tap(a.x, a.y)
    elif a.verb == "type" and a.text is not None:
        dev.type_text(a.text)
    elif a.verb == "scroll":
        dev.scroll(a.direction or "down")
    else:
        dev.back()


def replay(cfg: Config, trace: list[Action], settle: float = 0.7) -> ReplayResult:
    """Cold-start the app and re-execute the trace, collecting every signal."""
    dev = Device(cfg.serial)
    dev.prepare()
    dev.relaunch(cfg.package, cfg.activity)

    oracle = Oracle(dev, package=cfg.package, platform=cfg.platform)
    oracle.start()
    time.sleep(1.0)
    oracle.drain()  # discard launch noise

    result = ReplayResult()
    for a in trace:
        _execute(dev, a)
        time.sleep(settle)
        result.signals.extend(oracle.drain())

    # Let any page-transition animation finish before grading the final screen,
    # otherwise the capture can land on a mid-transition/blank frame and the
    # "screen looks same" gate misreads a good fix as a collapsed one.
    time.sleep(settle + 0.6)
    result.final_screenshot = dev.screenshot()
    oracle.stop()
    return result
