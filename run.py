"""Gremlin entrypoint: point it at a Flutter app and let it explore.

    python run.py                       # test the default / only detected app
    python run.py --list                # list detected Flutter projects
    python run.py --project ~/Projects/MyApp
    python run.py --package com.foo.bar --activity com.foo.bar/.MainActivity
    python run.py --steps 40
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from gremlin.config import Config, PROJECTS_ROOT
from gremlin.explorer import Explorer
from gremlin.reporter import write_reports
from gremlin.targets import find_flutter_projects, target_for_project


def _resolve_config(args) -> Config:
    """Pick the target app from the CLI flags, deriving package/activity/source."""
    if args.package:
        activity = args.activity or f"{args.package}/.MainActivity"
        root = Path(args.project).expanduser() if args.project else PROJECTS_ROOT
        return Config(package=args.package, activity=activity, scribe_root=root)

    if args.project:
        t = target_for_project(Path(args.project))
        if t is None:
            sys.exit(f"'{args.project}' is not a Flutter project (no pubspec with `sdk: flutter`).")
        print(f"target: {t.name}  [{t.package}]  src={t.source_root}")
        return t.to_config()

    # No explicit target: scan the projects root.
    targets = find_flutter_projects(args.projects_root)
    if len(targets) == 1:
        t = targets[0]
        print(f"target: {t.name}  [{t.package}]  src={t.source_root}")
        return t.to_config()
    if len(targets) > 1:
        print("Multiple Flutter projects found — pick one with --project or --package:")
        for t in targets:
            print(f"  --project {t.source_root}   ({t.name}, {t.package})")
        sys.exit(1)
    # None found: fall back to the built-in default so nothing breaks.
    print("No Flutter projects detected; using the default target.")
    return Config()


def main() -> None:
    ap = argparse.ArgumentParser(description="Gremlin — autonomous UI testing for Flutter")
    ap.add_argument("--steps", type=int, default=None, help="exploration step budget")
    ap.add_argument("--serial", default=None, help="adb device serial")
    ap.add_argument("--project", default=None, help="path to a Flutter project to test")
    ap.add_argument("--package", default=None, help="test an installed package directly (device-only)")
    ap.add_argument("--activity", default=None, help="launcher activity for --package")
    ap.add_argument("--projects-root", type=Path, default=PROJECTS_ROOT, help="where to scan for Flutter projects")
    ap.add_argument("--list", action="store_true", help="list detected Flutter projects and exit")
    args = ap.parse_args()

    if args.list:
        targets = find_flutter_projects(args.projects_root)
        if not targets:
            print(f"No Flutter projects found under {args.projects_root}")
            return
        print(f"Flutter projects under {args.projects_root}:")
        for t in targets:
            print(f"  {t.name:20} {t.package:28} {t.source_root}")
        return

    cfg = _resolve_config(args)
    if args.steps is not None:
        cfg.max_steps = args.steps
    if args.serial:
        cfg.serial = args.serial

    print(f"Gremlin exploring {cfg.package} for up to {cfg.max_steps} steps...")
    explorer = Explorer(cfg)
    bugs = explorer.run()

    print(f"\n=== done: {explorer.memory.count} distinct screens, {len(bugs)} bug(s) ===")
    for b in bugs:
        print(f"  [{b.severity}] {b.title()}  (step {b.step})")
    if bugs:
        written = write_reports(bugs, cfg)
        print(f"wrote {len(written)} report file(s) to {cfg.run_dir}/reports/")
    print(f"trace + artifacts in {cfg.run_dir}/")


if __name__ == "__main__":
    main()
