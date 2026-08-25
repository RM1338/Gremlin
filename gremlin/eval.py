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

    # the full ablation: model vs no-model vs random, 5 seeds each
    python -m gremlin.eval --project ~/Projects/gremlin-bench-flutter --actions 30 \
        --coverage-only --monkey --repeats 5

Every arm is repeated over several seeds and reported as mean ± sd, with a
per-defect detection rate ("found in 4 of 5 seeds"). A single run per arm is an
anecdote: the exploration is stochastic, and one lucky seed reads exactly like a
capability.

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
import statistics
from dataclasses import dataclass, asdict, field, replace
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
    # Which repetition this was, and what it actually found. One run is an
    # anecdote: exploration is stochastic, so the only honest report is several
    # seeds with the spread shown. `bug_keys` is what makes a per-defect
    # detection rate possible — "found in 4 of 5 seeds" says far more than a
    # mean, because a defect found half the time is a different claim from one
    # found always, and both average to the same bug count.
    seed: int = 0
    bug_keys: list[str] = field(default_factory=list)
    error: str = ""


def _stats(xs: "list[float]") -> dict:
    """mean/sd/min/max/median over the repetitions of one arm.

    Sample standard deviation (n-1), and 0.0 for a single sample rather than
    None — a lone run has no measurable spread, and pretending otherwise is how
    a single lucky seed becomes a headline number.
    """
    if not xs:
        return {"n": 0}
    return {
        "n": len(xs),
        "mean": round(statistics.fmean(xs), 2),
        "sd": round(statistics.stdev(xs), 2) if len(xs) > 1 else 0.0,
        "min": min(xs), "max": max(xs),
        "median": round(statistics.median(xs), 2),
    }


def run_gremlin(cfg: Config, label: str = "gremlin", seed: int = 0) -> Result:
    t0 = time.time()
    explorer = Explorer(cfg)
    bugs = explorer.run()
    return Result(label, cfg.max_steps, explorer.memory.count, len(bugs),
                  round(time.time() - t0, 1), seed=seed,
                  bug_keys=sorted(explorer.bugs))


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
                  round(time.time() - t0, 1), seed=seed,
                  bug_keys=sorted(bug_keys))


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

    sys.exit("A benchmark needs a target: pass --project <path> or --package <id>.\n"
             "  There is no default to fall back to, and silently measuring the "
             "wrong app is worse than not measuring (docs/KNOWN_ISSUES.md, G10).")


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
    ap.add_argument("--seed", type=int, default=0,
                    help="first seed; repeats use seed, seed+1, …")
    ap.add_argument("--repeats", type=int, default=5,
                    help="repetitions per arm (default 5). Exploration is "
                         "stochastic, so one run per arm is an anecdote — M2 asks "
                         "for at least 5 and the report shows the spread.")
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

    seeds = list(range(args.seed, args.seed + args.repeats))
    plan = [("gremlin-vision", "vision", "vision")]
    if args.coverage_only:
        plan.append(("gremlin-coverage", "coverage", "coverage"))

    results: list[Result] = []
    for label, policy, subdir in plan:
        for seed in seeds:
            print(f"\n=== {label}: {args.actions} actions, seed {seed} "
                  f"({seeds.index(seed) + 1}/{len(seeds)}) ===")
            # Each repetition gets its own directory. Sharing one would have the
            # later seeds overwrite the earlier ones' screenshots and trace, and
            # the evidence for a benchmark number is part of the number.
            arm_cfg = replace(cfg, run_dir=base / subdir / f"seed-{seed}", policy=policy)
            try:
                results.append(run_gremlin(arm_cfg, label, seed=seed))
            except KeyboardInterrupt:
                raise
            except BaseException as e:
                # One arm dying (a quota, a flaky device) must not throw away the
                # seeds that did complete. Record it as a failed sample so the
                # report can say n=4 of 5 rather than silently averaging four.
                print(f"  ! seed {seed} failed: {type(e).__name__}: {e}")
                results.append(Result(label, args.actions, 0, 0, 0.0, seed=seed,
                                      error=f"{type(e).__name__}: {e}"[:200]))

    if args.monkey:
        for seed in seeds:
            print(f"\n=== monkey: {args.actions} actions, seed {seed} ===")
            try:
                results.append(run_monkey(
                    replace(cfg, run_dir=base / "monkey" / f"seed-{seed}"),
                    args.actions, seed=seed))
            except KeyboardInterrupt:
                raise
            except BaseException as e:
                print(f"  ! seed {seed} failed: {type(e).__name__}: {e}")
                results.append(Result("monkey", args.actions, 0, 0, 0.0, seed=seed,
                                      error=f"{type(e).__name__}: {e}"[:200]))

    _report(results, cfg, args, base)


# ---- reporting --------------------------------------------------------------

def _aggregate(runs: "list[Result]") -> dict:
    """One arm's repetitions, as samples plus the spread over them."""
    ok = [r for r in runs if not r.error]
    union: set[str] = set()
    for r in ok:
        union |= set(r.bug_keys)
    return {
        "runs": [asdict(r) for r in runs],
        "completed": len(ok),
        "failed": len(runs) - len(ok),
        "screens": _stats([r.distinct_screens for r in ok]),
        "bugs": _stats([r.distinct_bugs for r in ok]),
        "duration_sec": _stats([r.duration_sec for r in ok]),
        # Every distinct defect this arm found in ANY seed. Higher than the mean
        # per-run count, and the honest answer to "what can this arm find at all".
        "bugs_union": sorted(union),
    }


def _detection_rates(arms: dict) -> dict:
    """Per-defect, in how many seeds did each arm find it.

    This is the per-task table an LLM benchmark reports, and it carries what an
    average cannot: a defect found in 5 of 5 seeds is a reliable detection, one
    found in 1 of 5 is luck, and both contribute the same +1 to a mean bug count.
    """
    every: set[str] = set()
    for a in arms.values():
        every |= set(a["bugs_union"])
    table = {}
    for key in sorted(every):
        table[key] = {
            name: {"found_in": sum(1 for r in a["runs"]
                                   if not r["error"] and key in r["bug_keys"]),
                   "of": a["completed"]}
            for name, a in arms.items()
        }
    return table


def _environment(cfg: Config) -> dict:
    """What this number was measured on. A benchmark without it is a rumour."""
    from . import sandbox
    from . import emulator as emu

    dev = Device(cfg.serial)
    try:
        w, h = dev.screen_size()
    except Exception:
        w = h = 0
    def prop(name: str) -> str:
        try:
            return dev._shell("getprop", name).strip()
        except Exception:
            return ""
    kind = ("sandbox" if sandbox.is_sandbox(cfg.serial)
            else "emulator" if emu.is_emulator(cfg.serial or "") else "device")
    return {
        "serial": cfg.serial or "(only attached)",
        "kind": kind,
        "width": w, "height": h,
        "android": prop("ro.build.version.release"),
        "sdk": prop("ro.build.version.sdk"),
        "model": prop("ro.product.model"),
        # Screen geometry belongs in a benchmark record because the dominant
        # defect class is overflow, and overflow is screen-size dependent: the
        # same app on a narrower device is a different measurement.
        "note": "geometry affects layout-defect counts; compare like with like",
    }


def _model_info(cfg: Config) -> dict:
    """Which vision backend did the exploring — the arm's headline dependency."""
    import os
    provider = os.environ.get("LLM_PROVIDER", "gemini").strip().lower()
    names = {"gemini": os.environ.get("GEMINI_MODEL", ""),
             "groq": os.environ.get("GROQ_MODEL", ""),
             "local": os.environ.get("LOCAL_MODEL", "")}
    return {"provider": provider, "model": names.get(provider, "")}


def _app_info(cfg: Config) -> dict:
    out = {"package": cfg.package, "platform": cfg.platform,
           "source_root": str(cfg.scribe_root)}
    try:
        # The commit is what makes a result re-runnable against the same code.
        rev = subprocess.run(["git", "-C", str(cfg.scribe_root), "rev-parse", "--short", "HEAD"],
                             capture_output=True, text=True, timeout=10)
        if rev.returncode == 0:
            out["commit"] = rev.stdout.strip()
    except Exception:
        pass
    return out


def _report(results: "list[Result]", cfg: Config, args, base: Path) -> None:
    arms: dict = {}
    for r in results:
        arms.setdefault(r.explorer, []).append(r)
    arms = {name: _aggregate(runs) for name, runs in arms.items()}

    print(f"\n{'arm':<20} {'screens (mean±sd)':>20} {'bugs (mean±sd)':>18} {'sec':>8}   n")
    print("-" * 76)
    for name, a in arms.items():
        sc, bg, du = a["screens"], a["bugs"], a["duration_sec"]
        if not sc.get("n"):
            print(f"{name:<20} {'— every run failed —':>20}")
            continue
        print(f"{name:<20} {sc['mean']:>13.1f} ± {sc['sd']:<4.1f} "
              f"{bg['mean']:>11.1f} ± {bg['sd']:<4.1f} {du['mean']:>8.1f}   {sc['n']}")

    rates = _detection_rates(arms)
    if rates:
        print(f"\nper-defect detection rate (seeds in which the arm found it)")
        names = list(arms)
        print(f"{'defect':<44} " + "  ".join(f"{n.replace('gremlin-', ''):>10}" for n in names))
        print("-" * (44 + 12 * len(names)))
        for key, row in rates.items():
            cells = "  ".join(f"{row[n]['found_in']:>4}/{row[n]['of']:<5}" for n in names)
            print(f"{key[:44]:<44} {cells}")

    payload = {
        "schema": 2,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "app": _app_info(cfg),
        "device": _environment(cfg),
        "vision_model": _model_info(cfg),
        "protocol": {
            "actions": args.actions,
            "repeats": args.repeats,
            "seeds": list(range(args.seed, args.seed + args.repeats)),
            "note": "equal action budget per arm, same cold start, phash-dedup screens",
        },
        "arms": arms,
        "detection_rates": rates,
        # Legacy shape, kept so an older console still renders something: one row
        # per arm carrying the MEAN, not a single lucky seed.
        "package": cfg.package,
        "platform": cfg.platform,
        "actions": args.actions,
        "seed": args.seed,
        "results": [
            {"explorer": name, "actions": args.actions,
             "distinct_screens": a["screens"].get("mean", 0),
             "distinct_bugs": a["bugs"].get("mean", 0),
             "duration_sec": a["duration_sec"].get("mean", 0)}
            for name, a in arms.items()
        ],
    }
    text = json.dumps(payload, indent=2)
    out = base / "eval.json"
    out.write_text(text)

    # The console's Benchmark page reads a fixed `runs/latest/eval.json` via
    # dashboard.api_state, so mirror the newest result there. The per-target
    # copy above is the canonical one.
    latest = Config().run_dir
    latest.mkdir(parents=True, exist_ok=True)
    (latest / "eval.json").write_text(text)
    print(f"\nwrote {out}  (mirrored to {latest / 'eval.json'} for the console)")


if __name__ == "__main__":
    main()
