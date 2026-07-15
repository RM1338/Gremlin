"""Central configuration for a Gremlin run.

Everything a run needs to know lives here so the rest of the code stays free of
magic strings. Values can be overridden from the CLI later.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


# Where the developer's Flutter projects live; scanned to build the target list.
PROJECTS_ROOT = Path.home() / "Projects"

# Default app under test (used when no target is picked). Overridden per-run by
# gremlin.targets once a Flutter project is selected in the CLI or the console.
PACKAGE = "com.scribe.scribe"
ACTIVITY = "com.scribe.scribe/.MainActivity"

# Where the selected project's source lives, so the fixer (Tier 2) can be pointed
# at file:line. Named `scribe_root` in Config for backward-compat; it holds the
# source root of whatever project is currently selected.
SCRIBE_ROOT = Path("/home/ronel/Projects/Scribe")


@dataclass
class Config:
    package: str = PACKAGE
    activity: str = ACTIVITY
    scribe_root: Path = SCRIBE_ROOT

    # adb device serial; None means "the only connected device".
    serial: str | None = None

    # Exploration budget (upper bound). Coverage-driven exploration usually stops
    # earlier, when every reachable control has been tapped; this is the cap so a
    # large or cyclic app can't run forever.
    max_steps: int = 80

    # Downscale screenshots to this width before sending to the vision model,
    # to keep inference cheap (proposal, risk: inference cost).
    vision_width: int = 540

    # Perceptual-hash distance below which two screens are "the same" screen.
    # Used for visited-screen memory and screen-count dedup.
    phash_same_threshold: int = 6

    # Output location for this run's artifacts (screenshots, reports, trace).
    run_dir: Path = field(default_factory=lambda: Path("runs/latest"))

    def ensure_dirs(self) -> None:
        (self.run_dir / "screens").mkdir(parents=True, exist_ok=True)
        (self.run_dir / "reports").mkdir(parents=True, exist_ok=True)
