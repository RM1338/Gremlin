"""Tier 2: find, fix, prove.

Given a bug report, the fixer shells out to a coding agent on a scratch branch,
guards the diff against the obvious cheats, rebuilds the app, replays the exact
trace that produced the bug, and applies three gates. A patch that clears all
three is left on its branch for a human to read; a patch that fails any gate is
reverted and the report survives with the failed attempt attached.

Safety, non-negotiable: operate on a scratch branch cut from a clean tree, never
on a dirty working directory, one commit per bug, no push, no merge. The final
judgment is always a human reading a small, pre-tested diff.
"""

from __future__ import annotations

import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from pathlib import Path

from .config import Config
from .explorer import Explorer
from .fix_backend import FixBackendError, apply_fix
from .gates import (
    GateResult,
    guard_patch_diff,
    no_new_breakage,
    screen_looks_same,
    signal_gone,
)
from .models import Bug
from .replayer import replay
from .reporter import tier1_prompt
from . import platforms


@dataclass
class FixOutcome:
    bug: Bug
    branch: str
    verified: bool
    gates: list[GateResult] = field(default_factory=list)
    guard_violations: list[str] = field(default_factory=list)
    note: str = ""


class DirtyTreeError(RuntimeError):
    pass


def _git(cfg: Config, *args: str, check: bool = True) -> str:
    out = subprocess.run(
        ["git", "-C", str(cfg.scribe_root), *args],
        capture_output=True, text=True,
    )
    if check and out.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {out.stderr.strip()}")
    return out.stdout.strip()


def _require_clean_tree(cfg: Config) -> None:
    """Refuse to work on a dirty tree, and say exactly which tree that is.

    Naming it matters more than it looks. `cfg.scribe_root` points at whichever
    app is selected, but git resolves it to the *enclosing repository*, which is
    not always the app's own — an app inside a monorepo reports the monorepo's
    tree. Reporting a hardcoded project name for someone else's uncommitted work
    is how a developer ends up hunting a tree they never touched. (The demo
    fixtures were moved out of this repo for exactly this reason; see
    `fixtures/README.md`.)
    """
    status = _git(cfg, "status", "--porcelain")
    if not status:
        return
    root = Path(_git(cfg, "rev-parse", "--show-toplevel", check=False) or cfg.scribe_root)
    changed = status.splitlines()
    shown = "\n".join(f"    {line.strip()}" for line in changed[:5])
    if len(changed) > 5:
        shown += f"\n    ... and {len(changed) - 5} more"
    note = ""
    if root.resolve() != Path(cfg.scribe_root).resolve():
        # The surprising case, and the one worth spelling out: the fix would be
        # committed to the outer repository, not to the app's own.
        note = (f"\n  note: the app at {cfg.scribe_root} is inside the {root.name} "
                f"repository, so this is {root.name}'s tree — a fix here would be "
                f"committed to {root.name}, not to the app alone.")
    raise DirtyTreeError(
        f"{root.name} has {len(changed)} uncommitted change(s); refusing to run "
        f"the fixer, which only operates on a clean tree. Commit or stash first."
        f"\n  repo: {root}\n{shown}{note}"
    )


def rebuild_and_install(cfg: Config) -> None:
    """Rebuild the APK and install it, so replay tests the patched code.

    How to build is the toolkit's business (`flutter build apk` vs a gradle
    assemble), so the Platform owns it; installing it is the same adb call
    either way.
    """
    apk = platforms.by_name(cfg.platform).build(cfg.scribe_root)
    install = ["adb"]
    if cfg.serial:
        install += ["-s", cfg.serial]
    subprocess.run(install + ["install", "-r", str(apk)], check=True)


def fix_one(cfg: Config, bug: Bug, baseline_keys: set[str],
            do_rebuild: bool = True, backend: str | None = None,
            on_phase: Callable[[str], None] | None = None) -> FixOutcome:
    """Attempt a fix for one bug and grade it against the three gates.

    `backend` selects the coding agent that writes the patch (see fix_backend);
    None uses the FIX_BACKEND env default. The guard, rebuild, replay and gates
    are identical regardless of which agent produced the diff.

    `on_phase` is called with the name of each stage as it begins. A whole fix is
    minutes long, so a caller with a UI needs to say which minute it is in.
    """
    phase = on_phase or (lambda _p: None)
    _require_clean_tree(cfg)
    base = _git(cfg, "rev-parse", "--abbrev-ref", "HEAD")
    branch = f"gremlin/fix-{bug.kind}-{int(time.time())}"
    _git(cfg, "checkout", "-b", branch)

    outcome = FixOutcome(bug=bug, branch=branch, verified=False)
    try:
        # --- Patch: let the configured coding agent edit the source here ---
        prompt = tier1_prompt(bug, cfg)
        phase("patching")
        try:
            apply_fix(prompt, cwd=cfg.scribe_root, backend=backend, timeout=300)
        except FixBackendError as e:
            outcome.note = f"fix backend error: {e}"
            _git(cfg, "checkout", ".", check=False)
            _git(cfg, "checkout", base)
            _git(cfg, "branch", "-D", branch, check=False)
            return outcome

        diff = _git(cfg, "diff")
        if not diff.strip():
            outcome.note = "coding agent made no changes"
            _git(cfg, "checkout", base)
            _git(cfg, "branch", "-D", branch, check=False)
            return outcome

        # --- Static guard: reject the obvious symptom-silencers ---
        phase("guard")
        guard = guard_patch_diff(diff)
        if not guard.ok:
            outcome.guard_violations = guard.violations
            outcome.note = "patch rejected by static guard (likely reward hacking)"
            _git(cfg, "checkout", ".")
            _git(cfg, "checkout", base)
            _git(cfg, "branch", "-D", branch, check=False)
            return outcome

        _git(cfg, "commit", "-am", f"gremlin: fix {bug.title()}")

        # --- Rebuild so replay exercises the patched code ---
        if do_rebuild:
            phase("rebuild")
            rebuild_and_install(cfg)

        # --- Gate 1 + 2: replay the trace, check signal + screen ---
        phase("replay")
        result = replay(cfg, bug.trace)
        g1 = signal_gone(result.keys(), bug.dedup_key)
        pre_png = Path(bug.screenshot).read_bytes()
        # A layout fix legitimately reflows the screen (an overflowing Row becomes
        # a fitting one), so strict pixel-similarity would reject a correct fix.
        # The blank/collapsed check still guards against a deleted widget; we only
        # relax the distance ceiling for layout-class bugs. Crash/exception fixes
        # keep the strict default — fixing those shouldn't change the screen.
        recognizable = 32 if bug.severity == "layout" else 20
        g2 = screen_looks_same(pre_png, result.final_screenshot,
                               recognizable_within=recognizable)

        # --- Gate 3: short re-exploration, no new signals ---
        # Run the probe in its own run_dir: the Explorer writes trace.json, and
        # pointing it at the source run would clobber the very trace we're fixing.
        probe_cfg = replace(cfg, run_dir=cfg.run_dir / "gate3-verify",
                            max_steps=min(cfg.max_steps, 15))
        probe = Explorer(probe_cfg)
        phase("probe")
        probe.run()
        g3 = no_new_breakage(set(probe.bugs.keys()), baseline_keys)

        outcome.gates = [g1, g2, g3]
        outcome.verified = all(g.passed for g in outcome.gates)

        if outcome.verified:
            outcome.note = "verified — patch cleared all three gates; left on branch for review"
        else:
            failed = ", ".join(g.name for g in outcome.gates if not g.passed)
            outcome.note = f"reverted — failed gate(s): {failed}"
            _git(cfg, "checkout", base)  # leave the branch but return to base
    finally:
        # Always return the working tree to the base branch; never leave it dirty.
        _git(cfg, "checkout", base, check=False)

    return outcome
