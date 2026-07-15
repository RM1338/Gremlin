"""The three gates, plus a diff-level guard against cheap fixes.

The fixer's reward is "make the log line disappear," which is NOT the same as
"fix the bug." Wrapping an overflowing Row in a SingleChildScrollView silences
the signal without correcting the layout; wrapping build() in try/catch hides an
exception; deleting the widget silences everything. An unconstrained fixer finds
these because they are easier than the real fix. So a patch must clear three
gates, not one, and a static guard rejects the most obvious cheats before we
even bother replaying.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass

import imagehash
from PIL import Image


@dataclass
class GateResult:
    name: str
    passed: bool
    detail: str


# ---- Gate 1: the signal is gone on replay -----------------------------------

def signal_gone(replay_keys: set[str], target_key: str) -> GateResult:
    gone = target_key not in replay_keys
    return GateResult(
        "signal-gone",
        gone,
        "target signal absent on replay" if gone else "signal still fires — no fix at all",
    )


# ---- Gate 2: the screen still looks like itself -----------------------------

def _phash(png: bytes) -> imagehash.ImageHash:
    return imagehash.phash(Image.open(io.BytesIO(png)))


def _is_mostly_blank(png: bytes) -> bool:
    """A deleted-widget / collapsed-layout 'fix' often leaves a near-empty screen."""
    img = Image.open(io.BytesIO(png)).convert("L").resize((64, 64))
    extrema = img.getextrema()  # (min, max) luminance
    return (extrema[1] - extrema[0]) < 12  # almost no contrast → blank


def screen_looks_same(pre_png: bytes, post_png: bytes,
                      recognizable_within: int = 20) -> GateResult:
    """Pass if the post-fix screen is recognizably the same screen.

    A real fix nudges the layout slightly (phash distance small-to-moderate). A
    deleted widget or a collapsed/blanked screen changes it drastically or leaves
    it empty — this is the gate that catches the cheap fix.
    """
    if _is_mostly_blank(post_png):
        return GateResult("screen-looks-same", False, "post-fix screen is blank/collapsed")
    dist = abs(_phash(pre_png) - _phash(post_png))
    ok = dist <= recognizable_within
    return GateResult(
        "screen-looks-same",
        ok,
        f"perceptual distance {dist} (<= {recognizable_within})"
        if ok else f"screen changed too much (distance {dist}) — widget likely removed",
    )


# ---- Gate 3: nothing new broke ----------------------------------------------

def no_new_breakage(post_fix_keys: set[str], baseline_keys: set[str]) -> GateResult:
    """Pass if a re-exploration surfaces no signal that was absent before the fix."""
    new = post_fix_keys - baseline_keys
    return GateResult(
        "no-new-breakage",
        not new,
        "no new signals introduced" if not new else f"patch introduced: {', '.join(sorted(new))}",
    )


# ---- Static guard: reject the obvious cheats before replaying ---------------

@dataclass
class GuardResult:
    ok: bool
    violations: list[str]


def guard_patch_diff(diff: str, max_changed_lines: int = 60) -> GuardResult:
    """Reject a patch that looks like a symptom-silencer rather than a fix."""
    added = [l[1:] for l in diff.splitlines() if l.startswith("+") and not l.startswith("+++")]
    removed = [l[1:] for l in diff.splitlines() if l.startswith("-") and not l.startswith("---")]
    violations: list[str] = []

    changed = len(added) + len(removed)
    if changed > max_changed_lines:
        violations.append(f"patch too large ({changed} lines > {max_changed_lines})")

    added_text = "\n".join(added)
    # Wrapping build()/a widget in try/catch hides exceptions instead of fixing them.
    if re.search(r"\btry\s*\{", added_text) or re.search(r"\bcatch\s*\(", added_text):
        violations.append("adds try/catch — likely hiding an exception, not fixing it")

    # Silencing an overflow by making it scroll away, added as the whole fix.
    if any("SingleChildScrollView" in a for a in added) and len(added) <= 3:
        violations.append("wraps content in SingleChildScrollView — silences overflow, doesn't fix layout")

    # Deletion-heavy patches tend to be "remove the widget that complained".
    if removed and len(added) == 0:
        violations.append("pure deletion — removes the offending widget rather than fixing it")

    return GuardResult(not violations, violations)
