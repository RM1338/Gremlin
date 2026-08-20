"""Tier 2 entrypoint: turn the bugs from a completed run into fixes.

Reads a run's trace.json and reconstructs each bug with its reproduction trace.
What happens next depends on the fix backend (see gremlin.fix_backend):

  --backend prompt   (default) writes the portable Tier-1 prompt for each bug and
                     points you at it — no source is touched. Works for every
                     developer, with or without an autonomous coding agent.
  --backend claude   (or codex / copilot / command) runs that agent on a scratch
                     branch, guards the diff, rebuilds, replays the exact taps
                     that caused the bug, and applies the three gates.

    python -m gremlin.autofix [--run runs/latest] [--project PATH]
                              [--backend prompt|claude|codex|copilot|command]
                              [--kind KIND] [--no-rebuild]

The autofix path refuses to touch a dirty working tree.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .config import Config
from .fix_backend import backend_name, edits_source
from .fixer import DirtyTreeError, fix_one
from .models import Action, Bug
from .reporter import write_reports
from .targets import target_for_project


def _load_bugs(trace_path: Path) -> list[Bug]:
    data = json.loads(trace_path.read_text())
    bugs: list[Bug] = []
    for b in data.get("bugs", []):
        trace = [Action(**a) for a in b.get("trace", [])]
        bugs.append(
            Bug(
                severity=b["severity"], kind=b["kind"],
                log_line=b.get("log_line", ""), context=b.get("context", []),
                dart_file=b.get("dart_file"), dart_line=b.get("dart_line"),
                screenshot=b["screenshot"], step=b["step"],
                trace=trace, dedup_key=b.get("dedup_key", b.get("title", "")),
            )
        )
    return bugs


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="runs/latest", help="run directory with trace.json")
    ap.add_argument("--project", default=None,
                    help="path to the app project whose source the fixer may edit "
                         "(must match the app the run explored); defaults to the built-in target")
    ap.add_argument("--no-rebuild", action="store_true", help="skip the rebuild (debug only)")
    ap.add_argument("--kind", default=None,
                    help="only attempt bugs of this signal kind (e.g. renderflex-overflow)")
    ap.add_argument("--backend", default=None,
                    help="coding agent for the fix: prompt (default) | claude | codex | "
                         "copilot | command. Overrides the FIX_BACKEND env var.")
    args = ap.parse_args()
    backend = (args.backend or backend_name()).lower()

    if args.project:
        t = target_for_project(Path(args.project))
        if t is None:
            sys.exit(f"'{args.project}' is not an app project Gremlin recognises "
                     f"(no Flutter pubspec, no React Native package.json + android/).")
        cfg = t.to_config()
        print(f"fix target: {t.name}  [{t.package}]  {t.toolkit.label}  src={t.source_root}")
    else:
        cfg = Config()
    cfg.run_dir = Path(args.run)
    all_bugs = _load_bugs(cfg.run_dir / "trace.json")
    bugs = all_bugs
    # The "no new breakage" gate compares a post-fix re-exploration against every
    # bug already known from this run — so the baseline must be ALL bugs, computed
    # before any --kind filter, or the run's other pre-existing bugs look "new".
    baseline_keys = {b.dedup_key for b in bugs}
    if args.kind:
        bugs = [b for b in bugs if b.kind == args.kind]
    # The reports are numbered by position in the RUN, and --kind filters that
    # list — so enumerating the filtered one wrote the crash's gate ladder into
    # bug_001.fix.json, where the console showed it under the layout bug. Keep
    # each bug's own number.
    numbers = {id(b): n for n, b in enumerate(all_bugs, 1)}
    if not bugs:
        print("no bugs in this run to fix.")
        return

    # Prompt-only backend: emit the portable Tier-1 prompt for each bug and stop.
    # This is the default because it needs no coding agent and touches no source.
    if not edits_source(backend):
        written = write_reports(bugs, cfg)
        prompts = [p for p in written if p.name.endswith(".prompt.md")]
        print(f"backend '{backend}': wrote {len(prompts)} portable fix prompt(s) — "
              f"paste one into whichever coding agent you use:\n")
        for bug, p in zip(bugs, prompts):
            print(f"  {bug.title():40} -> {p}")
        print("\nTo let an agent apply the fix directly and grade it, re-run with "
              "--backend claude|codex|copilot|command.")
        return

    print(f"attempting Tier 2 autofix for {len(bugs)} bug(s) via backend '{backend}'...\n")
    # Tier 1 reports back the portable prompt; write them too so the ladder is
    # complete even on an autofix run.
    write_reports(bugs, cfg)
    try:
        for bug in bugs:
            outcome = fix_one(cfg, bug, baseline_keys,
                              do_rebuild=not args.no_rebuild, backend=backend)
            _persist_outcome(cfg.run_dir, numbers[id(bug)], outcome)
            mark = "VERIFIED ✓" if outcome.verified else "reverted"
            print(f"[{mark}] {bug.title()}  (branch {outcome.branch})")
            for g in outcome.gates:
                print(f"    gate {g.name:18} {'pass' if g.passed else 'FAIL'} — {g.detail}")
            if outcome.guard_violations:
                for v in outcome.guard_violations:
                    print(f"    guard: {v}")
            print(f"    {outcome.note}\n")
    except DirtyTreeError as e:
        print(f"refusing: {e}")


def _persist_outcome(run_dir: Path, index: int, outcome) -> None:
    """Write a bug's Tier-2 result to ``reports/bug_NNN.fix.json`` so the dashboard
    can render the gate ladder for a real autofix run."""
    reports = run_dir / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    payload = {
        "verified": outcome.verified,
        "branch": outcome.branch,
        "note": outcome.note,
        "guard_violations": list(outcome.guard_violations),
        "gates": [{"name": g.name, "passed": g.passed, "detail": g.detail} for g in outcome.gates],
    }
    (reports / f"bug_{index:03d}.fix.json").write_text(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
