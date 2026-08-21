"""Evaluation: Gremlin vs. the Monkey, and Gremlin vs. itself without the model.

The project makes two claims that can only be settled by measurement.

The first is that a seeing, reasoning agent explores better than random tapping.
That baseline ships with Android, so we run it.

The second is implicit and, until now, untested: that the *vision model* is what
does the exploring. It may not be. `Explorer._choose_and_execute` overrides the
model whenever its pick is not an untapped control, so coverage bookkeeping and
accessibility-tree grounding may be doing most of the work. The `coverage` arm
runs the identical engine with no model at all, which turns that assumption into
a number (see docs/KNOWN_ISSUES.md, G4).

Every arm gets the same action budget from the same cold start, and is measured
on distinct screens reached (perceptual-hash dedup) and distinct bugs found.

    # aim it at an app — this is required, there is no useful default
    python -m gremlin.eval --project ~/Projects/gremlin-bench-flutter --actions 30

    # the full ablation: model vs no-model vs random
    python -m gremlin.eval --project ~/Projects/gremlin-bench-flutter --actions 30 \
        --coverage-only --monkey

CAUTION: `--monkey` fires random taps through the app. On a signed-in app with
real data it can delete things. Only enable it on a device or account you don't
mind disturbing — a sandbox, an emulator, or a throwaway login.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import dataclass, asdict, replace
from pathlib import Path

from .config import Config
from .device import Device
from .explorer import Explorer
from .oracle import Oracle
from .screen_memory import ScreenMemory
from .targets import target_for_project
from . import platforms


@dataclass
class Result:
    explorer: str
    actions: int
    distinct_screens: int
    distinct_bugs: int
    duration_sec: float = 0.0


def run_gremlin(cfg: Config, label: str = "gremlin") -> Result:
    t0 = time.time()
    explorer = Explorer(cfg)
    bugs = explorer.run()
    return Result(label, cfg.max_steps, explorer.memory.count, len(bugs),
                  round(time.time() - t0, 1))


def run_monkey(cfg: Config, actions: int, burst: int = 5, throttle_ms: int = 400,
               seed: int = 0) -> Result:
    """Run the Android Monkey, sampling the screen between bursts to count
    distinct screens the way we do for Gremlin. Bugs are read from the oracle."""
    t0 = time.time()
    dev = Device(cfg.serial)
    dev.prepare()
    dev.relaunch(cfg.package, cfg.activity)

    oracle = Oracle(dev, package=cfg.package, platform=cfg.platform)
    oracle.start()
    time.sleep(1.0)
    oracle.drain()

    mem = ScreenMemory(cfg.phash_same_threshold)
    bug_keys: set[str] = set()

    fired = 0
    while fired < actions:
        n = min(burst, actions - fired)
        # Stay inside the app package; category LAUNCHER keeps it launchable.
        subprocess.run(
            dev._base() + [
                "shell", "monkey", "-p", cfg.package,
                "-s", str(seed), "--throttle", str(throttle_ms),
                "--pct-syskeys", "0", "-v", str(n),
            ],
            capture_output=True,
        )
        fired += n
        time.sleep(0.5)
        mem.observe(dev.screenshot())
        for sig in oracle.drain():
            bug_keys.add(sig.key())

    oracle.stop()
    return Result("monkey", actions, mem.count, len(bug_keys),
                  round(time.time() - t0, 1))


def _resolve_config(args) -> Config:
    """Pick the app under test, the same way run.py does.

    Without this the benchmark silently measured the built-in default package,
    which need not even be installed — so the harness that produces the headline
    number could not be aimed at the fixtures it is meant to measure (G10).
    """
    if args.package:
        activity = args.activity or f"{args.package}/.MainActivity"
        cfg = Config(package=args.package, activity=activity)
        cfg.platform = ""  # resolved from the installed APK below
        return cfg

    if args.project:
        t = target_for_project(Path(args.project))
        if t is None:
            sys.exit(f"'{args.project}' is not an app project Gremlin recognises "
                     f"(no Flutter pubspec, no React Native package.json + android/).")
        print(f"target: {t.name}  [{t.package}]  {t.toolkit.label}")
        return t.to_config()

    print("No --project or --package given; using the built-in default target. "
          "This is almost certainly not what you want for a benchmark.")
    return Config()


def _identify(cfg: Config) -> str:
    """Work out the toolkit of an app we only know by package name."""
    found = platforms.detect_platform_on_device(Device(cfg.serial), cfg.package)
    if found is None:
        print(f"could not identify the UI toolkit of {cfg.package}; "
              f"assuming {platforms.DEFAULT.label}.")
        return platforms.DEFAULT.name
    print(f"identified {cfg.package} as a {found.label} app.")
    return found.name


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Benchmark Gremlin against the Monkey and against itself "
                    "with the vision model removed.")
    ap.add_argument("--actions", type=int, default=30)
    ap.add_argument("--project", default=None, help="path to the app project to benchmark")
    ap.add_argument("--package", default=None, help="benchmark an installed package directly")
    ap.add_argument("--activity", default=None, help="launcher activity for --package")
    ap.add_argument("--serial", default=None, help="adb device serial (e.g. localhost:5555)")
    ap.add_argument("--monkey", action="store_true", help="also run the Monkey baseline")
    ap.add_argument("--coverage-only", action="store_true",
                    help="also run the no-LLM coverage-only arm (the G4 ablation)")
    ap.add_argument("--seed", type=int, default=0, help="Monkey seed")
    ap.add_argument("--out", default=None,
                    help="where to write results (default: runs/eval/<package>)")
    args = ap.parse_args()

    cfg = _resolve_config(args)
    cfg.max_steps = args.actions
    cfg.serial = args.serial
    if not cfg.platform:
        cfg.platform = _identify(cfg)

    # Each arm needs its own run directory: the Explorer writes screenshots and
    # trace.json into cfg.run_dir, so sharing one would have the arms overwrite
    # each other's evidence — and the default is `runs/latest` for everything.
    base = Path(args.out) if args.out else Path("runs/eval") / cfg.package
    base.mkdir(parents=True, exist_ok=True)

    results: list[Result] = []

    print(f"\n=== gremlin-vision: {args.actions} actions ===")
    results.append(run_gremlin(
        replace(cfg, run_dir=base / "vision", policy="vision"), "gremlin-vision"))

    if args.coverage_only:
        print(f"\n=== gremlin-coverage (no model): {args.actions} actions ===")
        results.append(run_gremlin(
            replace(cfg, run_dir=base / "coverage", policy="coverage"),
            "gremlin-coverage"))

    if args.monkey:
        print(f"\n=== monkey: {args.actions} actions (seed {args.seed}) ===")
        results.append(run_monkey(
            replace(cfg, run_dir=base / "monkey"), args.actions, seed=args.seed))

    print(f"\n| explorer          | actions | distinct screens | distinct bugs | seconds |")
    print(f"|-------------------|---------|------------------|---------------|---------|")
    for r in results:
        print(f"| {r.explorer:17} | {r.actions:7} | {r.distinct_screens:16} "
              f"| {r.distinct_bugs:13} | {r.duration_sec:7} |")

    # One run is not a result. M2 asks for >= 5 seeds, and this writes a single
    # sample — the multi-seed runner that turns these into a mean and variance
    # is still to be built (docs/KNOWN_ISSUES.md, G9).
    payload = json.dumps({
        "package": cfg.package,
        "platform": cfg.platform,
        "actions": args.actions,
        "seed": args.seed,
        "results": [asdict(r) for r in results],
    }, indent=2)
    out = base / "eval.json"
    out.write_text(payload)

    # The console's Benchmark page reads a fixed `runs/latest/eval.json` via
    # dashboard.api_state, so mirror the newest result there. The per-target
    # copy above is the canonical one — this is only so the UI keeps working
    # now that results are no longer written to a single shared directory.
    latest = Config().run_dir
    latest.mkdir(parents=True, exist_ok=True)
    (latest / "eval.json").write_text(payload)
    print(f"\nwrote {out}  (mirrored to {latest / 'eval.json'} for the console)")


if __name__ == "__main__":
    main()
