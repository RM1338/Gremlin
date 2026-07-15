"""Visited-screen memory via perceptual hashing.

Screens are identified by a coarse perceptual hash of the screenshot, so that
scrolling within one screen doesn't count as a new screen and small animations
don't fool the "have I been here?" check. This memory feeds two things: the
count of distinct screens reached (the headline eval metric) and the summary of
already-visited screens passed into every policy prompt.
"""

from __future__ import annotations

import io

import imagehash
from PIL import Image


class ScreenMemory:
    def __init__(self, same_threshold: int = 6) -> None:
        self.same_threshold = same_threshold
        self._hashes: list[imagehash.ImageHash] = []
        self._names: list[str] = []

    @staticmethod
    def phash(png_bytes: bytes) -> imagehash.ImageHash:
        img = Image.open(io.BytesIO(png_bytes))
        return imagehash.phash(img)

    def seen_index(self, h: imagehash.ImageHash) -> int | None:
        """Return the index of a known screen within threshold, else None."""
        for i, known in enumerate(self._hashes):
            if abs(h - known) <= self.same_threshold:
                return i
        return None

    def observe(self, png_bytes: bytes, name: str | None = None) -> tuple[int, bool]:
        """Record a screen. Returns (screen_id, is_new)."""
        h = self.phash(png_bytes)
        idx = self.seen_index(h)
        if idx is not None:
            return idx, False
        self._hashes.append(h)
        self._names.append(name or f"screen_{len(self._hashes) - 1}")
        return len(self._hashes) - 1, True

    @property
    def count(self) -> int:
        return len(self._hashes)

    def summary(self) -> str:
        if not self._names:
            return "(none yet)"
        return ", ".join(self._names)
