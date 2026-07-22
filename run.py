"""Gremlin entrypoint: point it at a Flutter or React Native app and let it explore.

    python run.py                       # test the default / only detected app
    python run.py --list                # list detected app projects
    python run.py --project ~/Projects/MyApp
    python run.py --package com.foo.bar --activity com.foo.bar/.MainActivity
    python run.py --steps 40

No phone? Run it on an emulator instead — Gremlin boots one and drives it
exactly as it would a physical device:

    python run.py --avds                # list the AVDs on this machine
    python run.py --emulator            # boot the first AVD and use it
    python run.py --avd Pixel_7_API_34  # boot a specific one
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from gremlin.config import Config, PROJECTS_ROOT
from gremlin.explorer import Explorer
from gremlin.reporter import write_reports
from gremlin.targets import find_projects, target_for_project
from gremlin import emulator as emu


def _resolve_config(args) -> Config:
    """Pick the target app from the CLI flags, deriving package/activity/source."""
    if args.package:
        activity = args.activity or f"{args.package}/.MainActivity"
        root = Path(args.project).expanduser() if args.project else PROJECTS_ROOT
        cfg = Config(package=args.package, activity=activity, scribe_root=root)
        # A bare package has no source to identify the toolkit from; it is
        # resolved from the installed APK once a device exists (see main).
        cfg.platform = ""
        return cfg

    if args.project:
        t = target_for_project(Path(args.project))
        if t is None:
            sys.exit(f"'{args.project}' is not an app project Gremlin recognises "
                     f"(no Flutter pubspec, no React Native package.json + android/).")
        print(f"target: {t.name}  [{t.package}]  {t.toolkit.label}  src={t.source_root}")
        return t.to_config()

    # No explicit target: scan the projects root.
    targets = find_projects(args.projects_root)
    if len(targets) == 1:
        t = targets[0]
        print(f"target: {t.name}  [{t.package}]  {t.toolkit.label}  src={t.source_root}")
        return t.to_config()
    if len(targets) > 1:
        print("Multiple app projects found — pick one with --project or --package:")
        for t in targets:
            print(f"  --project {t.source_root}   ({t.name}, {t.toolkit.label}, {t.package})")
        sys.exit(1)
    # None found: fall back to the built-in default so nothing breaks.
    print("No app projects detected; using the default target.")
    return Config()


def _resolve_device(args) -> "emu.Emulator | None":
    """Boot an emulator if one was asked for, or if nothing else is connected.

    Returns the Emulator so the caller can shut it down, or None when we are
    driving a device that was already there — which we must not kill.
    """
    if not (args.emulator or args.avd):
        return None
    status = emu.sdk_status()
    if status.problem:
        sys.exit(f"Cannot start an emulator: {status.problem}")
    name = args.avd or status.avds[0]
    if emu.kvm_available():
        print(f"booting emulator {name} (this takes a minute on a cold start)...")
    else:
        # Otherwise this looks like a hang. Say so up front, with the reason.
        print(f"booting emulator {name} WITHOUT hardware acceleration — /dev/kvm "
              "is not available here, so the guest CPU is emulated in software.")
        print("  A cold boot can take 20-30 minutes. Once up, it stays up: "
              "re-run with the emulator still running and Gremlin adopts it.")
    try:
        started = emu.Emulator.start(name, headless=args.headless)
    except (RuntimeError, TimeoutError) as e:
        # The emulator refusing to start is an environment problem the developer
        # can fix (disk, KVM, a missing image) — report it, don't stack-trace.
        sys.exit(f"emulator {name} did not start: {e}")
    print(f"emulator ready: {started.serial}")
    return started


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Gremlin — autonomous UI testing for Flutter and React Native")
    ap.add_argument("--steps", type=int, default=None, help="exploration step budget")
    ap.add_argument("--serial", default=None, help="adb device serial")
    ap.add_argument("--project", default=None, help="path to an app project to test")
    ap.add_argument("--package", default=None, help="test an installed package directly (device-only)")
    ap.add_argument("--activity", default=None, help="launcher activity for --package")
    ap.add_argument("--projects-root", type=Path, default=PROJECTS_ROOT,
                    help="where to scan for app projects")
    ap.add_argument("--list", action="store_true", help="list detected app projects and exit")
    ap.add_argument("--emulator", action="store_true",
                    help="boot an emulator for this run instead of using a connected device")
    ap.add_argument("--avd", default=None, help="which AVD to boot (implies --emulator)")
    ap.add_argument("--avds", action="store_true", help="list available AVDs and exit")
    ap.add_argument("--headless", action="store_true",
                    help="boot the emulator with no window (for CI or over SSH)")
    ap.add_argument("--keep-emulator", action="store_true",
                    help="leave the emulator running after the run finishes")
    args = ap.parse_args()

    if args.avds:
        status = emu.sdk_status()
        if status.problem:
            print(status.problem)
            return
        print(f"AVDs available (SDK at {status.sdk}):")
        for name in status.avds:
            print(f"  {name}")
        running = emu.running_emulators()
        if running:
            print(f"\ncurrently running: {', '.join(running)}")
        return

    if args.list:
        targets = find_projects(args.projects_root)
        if not targets:
            print(f"No app projects found under {args.projects_root}")
            return
        print(f"App projects under {args.projects_root}:")
        for t in targets:
            print(f"  {t.name:20} {t.toolkit.label:14} {t.package:28} {t.source_root}")
        return

    cfg = _resolve_config(args)
    if args.steps is not None:
        cfg.max_steps = args.steps

    started = _resolve_device(args)
    # An explicit --serial always wins; otherwise a booted emulator is the device.
    cfg.serial = args.serial or (started.serial if started else None)

    try:
        _run(cfg)
    finally:
        if started and not args.keep_emulator:
            print(f"shutting down emulator {started.serial}")
            started.stop()


def _run(cfg: Config) -> None:
    if not cfg.platform:
        cfg.platform = _identify(cfg)

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


def _identify(cfg: Config) -> str:
    """Work out the toolkit of an app we only know by package name."""
    from gremlin.device import Device
    from gremlin import platforms

    found = platforms.detect_platform_on_device(Device(cfg.serial), cfg.package)
    if found is None:
        print(f"could not identify the UI toolkit of {cfg.package}; "
              f"assuming {platforms.DEFAULT.label}.")
        return platforms.DEFAULT.name
    print(f"identified {cfg.package} as a {found.label} app.")
    return found.name


if __name__ == "__main__":
    main()
