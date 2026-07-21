"""Evaluation: Gremlin vs. the Monkey.

The project's claim is that a seeing, reasoning agent explores better than random
tapping. That claim is testable and the baseline ships with Android, so we run
it. Both explorers get the same action budget from the same cold start, and are
measured on distinct screens reached (coarse perceptual-hash dedup) and distinct
bugs found.

    python -m gremlin.eval --actions 30              # Gremlin only (safe)
    python -m gremlin.eval --actions 30 --monkey     # also run the Monkey baseline

CAUTION: `--monkey` fires random taps through the app. On a signed-in Scribe
with real recordings it can delete data. Only enable it on an account/device you
don't mind disturbing (an emulator or a throwaway login).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from dataclasses import dataclass, asdict

from .config import Config
from .device import Device
from .explorer import Explorer
from .oracle import Oracle
from .screen_memory import ScreenMemory


@dataclass
class Result:
    explorer: str
    actions: int
    distinct_screens: int
    distinct_bugs: int


def run_gremlin(cfg: Config) -> Result:
    explorer = Explorer(cfg)
    bugs = explorer.run()
    return Result("gremlin", cfg.max_steps, explorer.memory.count, len(bugs))


def run_monkey(cfg: Config, actions: int, burst: int = 5, throttle_ms: int = 400,
               seed: int = 0) -> Result:
    """Run the Android Monkey, sampling the screen between bursts to count
    distinct screens the way we do for Gremlin. Bugs are read from the oracle."""
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
    return Result("monkey", actions, mem.count, len(bug_keys))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--actions", type=int, default=30)
    ap.add_argument("--monkey", action="store_true", help="also run the Monkey baseline")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    cfg = Config()
    cfg.max_steps = args.actions

    results: list[Result] = []
    print(f"=== Gremlin: {args.actions} actions ===")
    results.append(run_gremlin(cfg))

    if args.monkey:
        print(f"\n=== Monkey: {args.actions} actions (seed {args.seed}) ===")
        results.append(run_monkey(cfg, args.actions, seed=args.seed))

    print("\n| explorer | actions | distinct screens | distinct bugs |")
    print("|----------|---------|------------------|---------------|")
    for r in results:
        print(f"| {r.explorer:8} | {r.actions:7} | {r.distinct_screens:16} | {r.distinct_bugs:13} |")

    out = cfg.run_dir / "eval.json"
    out.write_text(json.dumps([asdict(r) for r in results], indent=2))
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
