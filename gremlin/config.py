"""Central configuration for a Gremlin run.

Everything a run needs to know lives here so the rest of the code stays free of
magic strings. Values can be overridden from the CLI later.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from ._env import load_dotenv

# The paths below are read from the environment at import time, so .env has to
# be loaded before that happens. The model backends load it for their own keys,
# but they are imported lazily and far too late for these. Real environment
# variables still win — load_dotenv() only ever setdefault()s.
load_dotenv()


# Where the developer's Flutter projects live; scanned to build the target list.
# Overridable because the containerised install has no developer home to scan —
# there the repo's own fixtures are the projects, and compose points this at
# /workspace/fixtures.
PROJECTS_ROOT = Path(os.environ.get("GREMLIN_PROJECTS_ROOT", Path.home() / "Projects"))

# There is no default app under test, and that is deliberate. This used to be
# `com.scribe.scribe`, the app Gremlin was first written against — which meant a
# fresh install with nothing selected advertised a target that existed on one
# laptop in the world, and "falling back to the default so nothing breaks" broke
# things later and less legibly than refusing would have. Empty means "nobody has
# picked yet"; gremlin.targets fills it in from the CLI or the console.
PACKAGE = ""
ACTIVITY = ""

# Where the selected project's source lives, so the fixer (Tier 2) can be pointed
# at file:line. Named `scribe_root` in Config for backward-compat; it holds the
# source root of whatever project is currently selected.
SCRIBE_ROOT = Path(os.environ.get("GREMLIN_APP_ROOT", PROJECTS_ROOT))


@dataclass
class Config:
    package: str = PACKAGE
    activity: str = ACTIVITY
    scribe_root: Path = SCRIBE_ROOT

    # Which UI toolkit built the app under test — a `platforms.Platform.name`,
    # e.g. "flutter" or "react-native". It selects the log vocabulary the oracle
    # matches against and the rules the Tier-2 fixer works under. Empty means
    # "not identified"; the default is kept for backward compatibility.
    platform: str = "flutter"

    # Which policy chooses the next action. "vision" asks the configured vision
    # model; "coverage" is the no-LLM ablation arm that always takes the next
    # untapped control (docs/KNOWN_ISSUES.md, G4). Comparing the two is what
    # establishes whether the model is load-bearing at all — until that number
    # exists, every claim about the model's contribution is unmeasured.
    policy: str = "vision"

    # adb device serial; None means "the only connected device". An emulator
    # looks like "emulator-5554" and a sandbox container like "localhost:5555";
    # both are driven exactly like a physical phone.
    serial: str | None = os.environ.get("GREMLIN_SERIAL") or None

    # AVD to boot for this run when no device is connected. None means "use
    # whatever adb already sees".
    avd: str | None = None

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
        """Make this run's directory, and empty it of the LAST run's artifacts.

        `runs/latest` is reused by every run and nothing ever cleared it, so a
        short run inherited a long one's screenshots. The console then zipped
        step N of this trace against a frame from a different run — and, once
        the machine changed, a different device: 360x760 placeholders written by
        scripts/seed_demo_run.py sitting beside 1080x2340 phone captures, with
        nothing in the filename to tell them apart.

        Only the files a run writes are removed, by pattern. Anything else
        parked in here is left alone, and eval.json in particular survives — the
        benchmark writes that, and it is evidence from a different exercise.
        """
        screens = self.run_dir / "screens"
        reports = self.run_dir / "reports"
        screens.mkdir(parents=True, exist_ok=True)
        reports.mkdir(parents=True, exist_ok=True)
        for pattern in ("step_*.png", "bug_*.png"):
            for stale in screens.glob(pattern):
                stale.unlink()
        for pattern in ("bug_*.md", "bug_*.json"):
            for stale in reports.glob(pattern):
                stale.unlink()
        stale_trace = self.run_dir / "trace.json"
        if stale_trace.exists():
            stale_trace.unlink()
