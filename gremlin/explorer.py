"""The explorer: one closed perception-action loop.

Observe (screenshot) -> Decide (vision policy + visited memory) -> Act (one of
the four verbs) -> Check (drain the oracle). Repeat until the step budget runs
out. A clean check loops back to Observe; a failure signal spins off a bug
report carrying the screenshot and the full action trace from launch.

This is the "intelligent" half of the project. Detection is exact and lives in
the oracle; the loop's only job is to REACH the screens where the framework
confesses.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict
from pathlib import Path
from typing import Callable

_STUCK_HINT_AT = 2   # warn the model in the prompt after N steps without a new screen
_DONE_AFTER = 6      # stop once this many steps pass with nothing left to tap anywhere

from .config import Config
from .device import Device
from .grounding import dump_elements, Element
from .models import Action, Bug
from .oracle import Oracle
from .policy import decide, decide_coverage_only
from .screen_memory import ScreenMemory
from .vision import ModelError


# Optional callback so the dashboard can watch a run live. Given (event, payload).
EventSink = Callable[[str, dict], None]


class Explorer:
    def __init__(self, cfg: Config, on_event: EventSink | None = None) -> None:
        self.cfg = cfg
        self.dev = Device(cfg.serial)
        self.oracle = Oracle(self.dev, package=cfg.package, platform=cfg.platform)
        self.memory = ScreenMemory(cfg.phash_same_threshold)
        self.trace: list[Action] = []
        self.bugs: dict[str, Bug] = {}  # dedup_key -> Bug
        self._on_event = on_event
        self._last_phash = None
        self._run_note = ""  # set if the run ended early (e.g. model rate limit)
        # Coverage-driven exploration: the goal is to tap every distinct control.
        # For each screen we track which element keys have been tapped and how
        # many we've discovered, so we always steer toward untapped controls and
        # know when a screen (and the whole app) is fully covered.
        self._steps_since_new = 0
        self._tapped: dict[int, set] = {}       # screen_id -> tapped element keys
        self._seen_elems: dict[int, set] = {}   # screen_id -> all discovered keys
        self._no_frontier_streak = 0            # steps with nothing left to tap
        self._typed: set[int] = set()           # screens where we've typed once
        self._scrolled: set[int] = set()        # screens we've scrolled for coverage
        self._done = False                      # stop the run loop early
        self._complete = False                  # stopped because coverage is done

    def stop(self, note: str = "Stopped by the user.") -> None:
        """Ask the run to end after the current step.

        Called from another thread (the dashboard's request handler). It sets
        the same flag the coverage-complete path uses rather than killing the
        worker, so `run()` still drains the oracle, writes the trace and emits
        `done` — a killed thread would leave the device with the screen pinned
        awake and the partial run unreported.
        """
        self._run_note = note
        self._done = True

    def _emit(self, event: str, payload: dict) -> None:
        if self._on_event:
            try:
                self._on_event(event, payload)
            except Exception:
                pass  # a broken dashboard must never break a run

    def run(self) -> list[Bug]:
        self.cfg.ensure_dirs()
        self._t0 = time.time()
        self.dev.prepare()
        self.dev.relaunch(self.cfg.package, self.cfg.activity)
        self.oracle.start()
        # Discard anything from launch itself so step 1 starts clean.
        time.sleep(1.0)
        self.oracle.drain()

        try:
            for step in range(1, self.cfg.max_steps + 1):
                try:
                    self._step(step)
                except ModelError as e:
                    # A model outage (e.g. rate limit) shouldn't lose the run —
                    # stop early and keep whatever was explored so far.
                    self._run_note = str(e)
                    print(f"  !! model unavailable at step {step}: {e}")
                    break
                if self._done:
                    # _done is set by two different things now: coverage running
                    # out of frontier, and the user pressing stop. Only the first
                    # is "complete".
                    if self._complete:
                        print(f"  ✓ coverage complete at step {step}: every reachable control tapped")
                    else:
                        print(f"  ■ stopped at step {step}: {self._run_note}")
                    break
        finally:
            self.oracle.stop()

        self._write_trace()
        self._emit("done", self._summary())
        return list(self.bugs.values())

    def _summary(self) -> dict:
        """A rich end-of-run digest, reused for the `done` event and trace.json."""
        verbs: dict[str, int] = {}
        for a in self.trace:
            verbs[a.verb] = verbs.get(a.verb, 0) + 1
        sections = sorted({a.target_label for a in self.trace if a.target_label})
        by_severity: dict[str, int] = {}
        for b in self.bugs.values():
            by_severity[b.severity] = by_severity.get(b.severity, 0) + 1
        controls_tapped = sum(len(s) for s in self._tapped.values())
        controls_seen = sum(len(s) for s in self._seen_elems.values())
        note = self._run_note
        if not note and self._complete:
            note = f"Coverage complete — tapped every reachable control ({controls_tapped} across {self.memory.count} screens)."
        return {
            "steps": len(self.trace),
            "screens": self.memory.count,
            "bugs": len(self.bugs),
            "duration_sec": round(time.time() - getattr(self, "_t0", time.time()), 1),
            "verbs": verbs,
            "sections": sections,
            "bugs_by_severity": by_severity,
            "controls_tapped": controls_tapped,
            "controls_seen": controls_seen,
            "complete": self._complete,
            "note": note,
            "ended_early": bool(self._run_note),
        }

    def _step(self, step: int) -> None:
        # Stay on target before observing, so foreign screens are never counted
        # or explored: a tap may have opened a system media/file picker, a
        # permission dialog, a share sheet, or pulled another app forward.
        # Backing out of the app's own root is how we leave it, and that only
        # happens once a branch is exhausted. Re-entering therefore says the
        # exploration is finished, not that it is starting again.
        left_app = self._ensure_on_app()

        # ---- Observe ----
        shot = self.dev.screenshot()
        shot_path = self.cfg.run_dir / "screens" / f"step_{step:03d}.png"
        shot_path.write_bytes(shot)
        h = self.memory.phash(shot)
        is_new = self.memory.seen_index(h) is None  # read-only check before we record

        # ---- Decide ----
        elements = dump_elements(self.dev)
        stuck_hint = ""
        if self._steps_since_new >= _STUCK_HINT_AT:
            stuck_hint = (
                "NOTE: you keep returning to screens you have already seen. Tap an "
                "element you have NOT tried yet, or press back to leave this area.\n"
            )
        if self.cfg.policy == "coverage":
            # The ablation arm: no inference at all. Everything downstream —
            # grounding, coverage bookkeeping, the stopping rule — is identical,
            # so any difference in the result is attributable to the model.
            decision = decide_coverage_only(elements)
        else:
            decision = decide(
                shot_path, elements, self.memory.summary(), self.cfg.vision_width,
                recent=self._recent_summary(), stuck=stuck_hint,
            )
        # The coverage arm names no screens; fall back to ScreenMemory's own
        # positional naming rather than labelling every screen with one string.
        screen_id, _ = self.memory.observe(shot, decision.screen_name or None)

        # Register this screen's clickable controls and find the untapped ones.
        seen = self._seen_elems.setdefault(screen_id, set())
        tapped = self._tapped.setdefault(screen_id, set())
        clickable = [e for e in elements if e.clickable]
        for e in clickable:
            seen.add(self._elem_key(e))
        untapped = [e for e in clickable if self._elem_key(e) not in tapped]

        self._steps_since_new = 0 if is_new else self._steps_since_new + 1

        # ---- Act (coverage-first) ----
        action = self._choose_and_execute(decision, elements, untapped, screen_id)
        self.trace.append(action)

        # Frontier bookkeeping: how much of this screen is covered, and whether
        # there is anything left to tap anywhere (for the coverage-complete stop).
        # The frontier streak is what stops the run. Re-entering the app after
        # backing out of it keeps counting: the loop used to reset here, land on
        # a home screen with something still untapped, tap it, exhaust it, back
        # out of the app again — and never reach the stop. Which is exactly the
        # exit-and-reopen cycle it got stuck in.
        if untapped and not left_app:
            self._no_frontier_streak = 0
        else:
            self._no_frontier_streak += 1
        self._last_phash = h

        self._emit(
            "step",
            {
                "step": step,
                "screen": decision.screen_name,
                "screen_id": screen_id,
                "is_new": is_new,
                "distinct_screens": self.memory.count,
                "intention": action.reason,          # the ACTUAL action's reason
                "verb": action.verb,                 # the ACTUAL executed verb
                "target": action.target_label,
                "coverage": {"tapped": len(tapped), "total": len(seen)},
                "screenshot": str(shot_path),
            },
        )

        # ---- Check ----
        time.sleep(0.7)  # let the framework print any error it's going to print
        for sig in self.oracle.drain():
            self._record_bug(sig, step)

        # ---- Coverage complete? ----
        # Every reachable control has been tapped: we've spent several steps with
        # nothing left to tap even after scrolling and backing out. Stop cleanly.
        if self._no_frontier_streak >= _DONE_AFTER:
            self._done = True
            self._complete = True

    def _ensure_on_app(self) -> bool:
        """Get back into the app under test before observing.

        Returns True if we had actually LEFT the app and had to come back —
        which the caller reads as evidence, not just as housekeeping.

        A tap can open a system media/file picker, a photo gallery, a permission
        dialog or a share sheet — all *different packages*. We first try to
        cancel them with `back` (the natural dismiss, which returns to the exact
        app screen), and only force a full relaunch if we're still stranded.
        These recovery actions are deliberately NOT recorded in the trace: they
        are normalization, not exploration.
        """
        left = False
        for _ in range(3):
            fg = self.dev.foreground_package()
            if fg is None or fg == self.cfg.package:
                self._reattach_oracle()
                return left
            left = True
            self.dev.back()
            time.sleep(0.6)
        if self.dev.foreground_package() not in (None, self.cfg.package):
            self.dev.relaunch(self.cfg.package, self.cfg.activity)
            left = True
        self._reattach_oracle()
        return left

    def _reattach_oracle(self) -> None:
        """Keep the oracle watching the process that is actually running.

        Checked on every step, not only after we relaunch: a crash we detected
        can kill and restart the app on its own, and a stream pinned to the dead
        pid goes silently deaf (docs/KNOWN_ISSUES.md, G1). One `pidof` per step
        is a few percent of a step's cost and buys back every signal after the
        first crash.
        """
        if not self.oracle.ensure_attached():
            return
        # The stream is new and empty. Let the app settle, then discard the
        # relaunch's own noise so it is not attributed to the next action.
        time.sleep(0.8)
        self.oracle.drain()
        print("  .. oracle re-attached (app process changed)")

    def _recent_summary(self, n: int = 5) -> str:
        """A one-line digest of the last n actions, for the policy prompt."""
        if not self.trace:
            return "(none yet)"
        parts = []
        for a in self.trace[-n:]:
            what = a.target_label or a.text or a.direction or ""
            parts.append(f"{a.verb} {what}".strip())
        return " -> ".join(parts)

    @staticmethod
    def _elem_key(e: Element):
        """A stable-ish identity for a control, so we tap each distinct one once.
        Labelled controls key by label; unlabelled ones key by a coarse position
        bucket (list items that share a label collapse to one — you don't need to
        open all 50 recordings, just enough to reach the detail screen)."""
        if e.label and e.label != "(unlabeled)":
            return ("label", e.label)
        return ("pos", e.cx // 40, e.cy // 40)

    def _do_tap(self, el: Element, screen_id: int, reason: str) -> Action:
        self._tapped.setdefault(screen_id, set()).add(self._elem_key(el))
        self.dev.tap(el.cx, el.cy)
        return Action("tap", x=el.cx, y=el.cy, target_label=el.label, reason=reason)

    def _choose_and_execute(self, decision, elements: list[Element],
                            untapped: list[Element], screen_id: int) -> Action:
        """Coverage-first action selection: tap every distinct control on a
        screen before leaving it. The model only chooses the ORDER among untapped
        controls and fills text fields; it can never keep us looping."""
        tapped = self._tapped.setdefault(screen_id, set())

        if untapped:
            # Honour the model's pick if it targets an untapped control (good
            # ordering); otherwise just take the next untapped one ourselves.
            if (decision.verb == "tap" and decision.index is not None
                    and 0 <= decision.index < len(elements)):
                el = elements[decision.index]
                if self._elem_key(el) not in tapped:
                    return self._do_tap(el, screen_id, decision.reason)
            return self._do_tap(untapped[0], screen_id,
                                "coverage: tapping an unvisited control")

        # Nothing left to tap on this screen. Let the model type into a field if
        # it wants (search boxes, logins), then scroll to reveal more, then leave.
        if decision.verb == "type" and decision.text and screen_id not in self._typed:
            self._typed.add(screen_id)
            self.dev.type_text(decision.text)
            return Action("type", text=decision.text, reason=decision.reason)
        if screen_id not in self._scrolled:
            self._scrolled.add(screen_id)
            self.dev.scroll("down")
            return Action("scroll", direction="down", reason="coverage: reveal more controls")
        self.dev.back()
        return Action("back", reason="coverage: screen fully covered, backing out")

    def _record_bug(self, sig, step: int) -> None:
        key = sig.key()
        if key in self.bugs:
            return  # already found this exact bug
        # Capture the screen at the moment of failure.
        fail_shot = self.dev.screenshot()
        fail_path = self.cfg.run_dir / "screens" / f"bug_{len(self.bugs) + 1:03d}.png"
        fail_path.write_bytes(fail_shot)
        bug = Bug(
            severity=sig.severity,
            kind=sig.kind,
            log_line=sig.line,
            context=sig.context,
            dart_file=sig.dart_file,
            dart_line=sig.dart_line,
            screenshot=str(fail_path),
            step=step,
            trace=list(self.trace),  # snapshot of the path that reached the bug
            dedup_key=key,
        )
        self.bugs[key] = bug
        self._emit("bug", {"severity": sig.severity, "title": bug.title(), "step": step})
        print(f"  !! BUG [{sig.severity}] {bug.title()} at step {step}")

    def _write_trace(self) -> None:
        out = {
            "package": self.cfg.package,
            "steps": len(self.trace),
            "distinct_screens": self.memory.count,
            "summary": self._summary(),
            "trace": [a.to_dict() for a in self.trace],
            "bugs": [
                {
                    "severity": b.severity,
                    "kind": b.kind,
                    "title": b.title(),
                    "log_line": b.log_line,
                    "context": b.context,
                    "dart_file": b.dart_file,
                    "dart_line": b.dart_line,
                    "screenshot": b.screenshot,
                    "step": b.step,
                    "dedup_key": b.dedup_key,
                    "trace": [a.to_dict() for a in b.trace],
                }
                for b in self.bugs.values()
            ],
        }
        (self.cfg.run_dir / "trace.json").write_text(json.dumps(out, indent=2))
