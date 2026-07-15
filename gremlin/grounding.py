"""Grounding: turn the on-screen accessibility tree into tappable elements.

Before the policy falls back to guessing raw pixel coordinates, it asks here
for a list of real elements with their centers and labels. On Scribe the Flutter
semantics tree comes back populated (verified 2026-07-10), so the model can pick
an element by index and we tap its center — removing a whole class of near-miss
taps. When the tree is empty (a third-party APK without semantics), callers fall
back to pure-vision pixel taps.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass

from .device import Device


_BOUNDS_RE = re.compile(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]")


@dataclass
class Element:
    index: int
    label: str  # human-readable: content-desc or text
    cx: int  # center x
    cy: int  # center y
    clickable: bool
    bounds: tuple[int, int, int, int]

    def describe(self) -> str:
        kind = "button" if self.clickable else "text"
        return f"[{self.index}] {kind}: {self.label!r}"


def _parse_bounds(raw: str) -> tuple[int, int, int, int] | None:
    m = _BOUNDS_RE.match(raw or "")
    if not m:
        return None
    x1, y1, x2, y2 = (int(g) for g in m.groups())
    return x1, y1, x2, y2


def dump_elements(device: Device) -> list[Element]:
    """Dump the current screen's accessibility tree as a flat element list.

    Returns only nodes that carry a label or are clickable — the things worth
    offering to the policy. Empty list means the tree gave us nothing usable and
    the caller should fall back to pixel coordinates.
    """
    # `uiautomator dump` writes to a file on the device; stream it back to stdout.
    device._shell("uiautomator", "dump", "/sdcard/gremlin_ui.xml", timeout=20)
    xml = device._shell("cat", "/sdcard/gremlin_ui.xml", timeout=10)

    start = xml.find("<?xml")
    if start == -1:
        return []
    try:
        root = ET.fromstring(xml[start:])
    except ET.ParseError:
        return []

    elements: list[Element] = []
    for node in root.iter("node"):
        label = (node.get("content-desc") or node.get("text") or "").strip()
        clickable = node.get("clickable") == "true"
        if not label and not clickable:
            continue
        bounds = _parse_bounds(node.get("bounds", ""))
        if not bounds:
            continue
        x1, y1, x2, y2 = bounds
        # A zero-area node cannot be tapped meaningfully.
        if x2 <= x1 or y2 <= y1:
            continue
        # Flutter labels often pack a title and subtitle with a newline; keep the
        # first line, it is the actionable name.
        label = label.split("\n")[0].strip()
        elements.append(
            Element(
                index=len(elements),
                label=label or "(unlabeled)",
                cx=(x1 + x2) // 2,
                cy=(y1 + y2) // 2,
                clickable=clickable,
                bounds=bounds,
            )
        )
    return elements
