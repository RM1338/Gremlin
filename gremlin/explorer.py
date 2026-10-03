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
_SCROLL_TRIES = 3    # consecutive fruitless scrolls before a screen is called done

from .config import Config
from .device import Device
from .grounding import Element
from .models import Action, Bug
from .oracle import Oracle
from .policy import decide, decide_coverage_only
from .screen_memory import ScreenMemory
from .vision import ModelError


class DeviceLost(RuntimeError):
    """The device stopped answering mid-run: an emulator crash, a cable pulled."""


# Optional callback so the dashboard can watch a run live. Given (event, payload).
EventSink = Callable[[str, dict], None]


class Explorer:
    def __init__(self, cfg: Config, on_event: EventSink | None = None) -> None:
        self.cfg = cfg
        # Which driver, and which source of truth about failure. These two go
        # together — a browser page is driven and confesses over the DevTools
        # protocol, a device is driven and confesses to logcat — so they are
        # chosen once, here, and every other line of this class is unchanged
        # between them.
        if cfg.platform == "web":
            from .web import WebDriver, WebOracle
            self.dev = WebDriver(cfg)
            self.oracle = WebOracle(self.dev, platform=cfg.platform)
        else:
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
        # A sign-in / sign-up wall: coverage taps each field (which only focuses
        # it) and never types, so the run loops here until the step budget. When
        # cfg.login is set, `_advance_login` fills one credential field per step
        # (re-grounded each time — the keyboard reflows the screen) and taps
        # submit once every field is in.
        self._login_filled: dict[int, set] = {}  # screen_id -> credential names filled
        self._login_submitted: set[int] = set()  # screens whose form we've submitted
        self._signup_navs = 0                     # times we've followed a sign-up link
        self._mailbox = None       # set in run() when GREMLIN_LOGIN_EMAIL=auto
        self._fresh_signup = False # inbox is new -> register before trying to sign in
        # Scrolls spent on a screen without finding anything new. One scroll per
        # screen was enough for a phone app, where a screen is a screenful; it
        # is badly wrong for a long web page, which is one "screen" that has to
        # be walked down several viewports before its controls have been seen.
        # The budget resets whenever a scroll actually reveals a control, so a
        # long page keeps going and a static one stops after _SCROLL_TRIES.
        self._scrolls: dict[int, int] = {}
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

    def _provision_inbox(self) -> None:
        """GREMLIN_LOGIN_EMAIL=auto: get a real disposable inbox and let the
        OTP/verification fields be filled from the code it receives.

        On failure the run still proceeds — the email credential is dropped so
        no login is attempted, rather than typing the literal string "auto"."""
        if self.cfg.login.get("email") != "auto":
            return
        import secrets
        from .mailbox import Mailbox
        last = None
        for attempt in range(3):
            try:
                self._mailbox = Mailbox()
                break
            except Exception as e:
                last = e
                time.sleep(2)
        if self._mailbox is None:
            print(f"  !! GREMLIN_LOGIN_EMAIL=auto but no disposable inbox could be "
                  f"created after 3 tries ({last}). The login wall will NOT be "
                  f"cleared — set a literal GREMLIN_LOGIN_EMAIL or check outbound "
                  f"HTTPS to api.mail.tm.")
            self.cfg.login.clear()
            return
        self.cfg.login["email"] = self._mailbox.address
        self.cfg.login.setdefault("otp", "auto")
        self.cfg.login.setdefault("code", "auto")
        # A brand-new inbox has no account yet: give the sign-up form a name and
        # a complexity-safe password, and prefer the register path over sign-in.
        self.cfg.login.setdefault("name", "Gremlin QA")
        self.cfg.login.setdefault("password", "Gr3mlin-" + secrets.token_hex(4))
        self._fresh_signup = True
        print(f"  .. disposable inbox: {self._mailbox.address}")

    def run(self) -> list[Bug]:
        self.cfg.ensure_dirs()
        self._provision_inbox()
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
                except DeviceLost as e:
                    # Same reasoning: the bugs already found are real, so end the
                    # run and report them rather than dying with a traceback.
                    self._run_note = str(e)
                    print(f"  !! device lost at step {step}: {e}")
                    break
                if self._done:
                    # _done is set by two different things now: coverage running
                    # out of frontier, and the user pressing stop. Only the first
                    # is "complete".
                    if self._complete:
                        left = self._untapped_left()
                        print(f"  ✓ coverage complete at step {step}: " + (
                            "every reachable control tapped" if not left else
                            f"nothing left here, but {left} control(s) seen on "
                            "other screens were never tapped"))
                    else:
                        print(f"  ■ stopped at step {step}: {self._run_note}")
                    break
        finally:
            self.oracle.stop()
            # The browser is a process we started; leaving it running would leak
            # one per run. Android's driver owns nothing to release.
            close = getattr(self.dev, "close", None)
            if close:
                close()

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
            left = self._untapped_left()
            note = (f"Coverage complete — tapped every reachable control ({controls_tapped} across {self.memory.count} screens)."
                    if not left else
                    f"Coverage stopped — {controls_tapped} controls tapped across {self.memory.count} screens; "
                    f"{left} seen on screens it left were never tapped.")
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
        if not shot:
            # adb returns nothing at all once the device is gone; without this
            # the empty bytes reached the image decoder and the run died there.
            raise DeviceLost(f"{self.cfg.serial or 'the device'} returned no "
                             "screenshot; it has stopped responding")
        shot_path = self.cfg.run_dir / "screens" / f"step_{step:03d}.png"
        shot_path.write_bytes(shot)
        h = self.memory.phash(shot)

        # ---- Decide ----
        elements = self.dev.elements()
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
        # A driver that can name its own screens does; one that cannot passes
        # None and the perceptual hash decides, exactly as before.
        screen_key = getattr(self.dev, "screen_key", None)
        # `is_new` comes from the same identity that assigns the screen id. It
        # used to be a separate perceptual-hash check made before recording,
        # which disagreed with a driver-supplied key and reported every scroll
        # of one web page as a screen never seen before.
        screen_id, is_new = self.memory.observe(
            shot, decision.screen_name or None,
            key=screen_key() if screen_key else None)

        # Register this screen's clickable controls and find the untapped ones.
        seen = self._seen_elems.setdefault(screen_id, set())
        tapped = self._tapped.setdefault(screen_id, set())
        clickable = [e for e in elements if e.clickable]
        known = len(seen)
        for e in clickable:
            seen.add(self._elem_key(e))
        untapped = self._frontier(clickable, tapped)
        # Scrolling earned its keep: give this screen its scroll budget back, so
        # a page that keeps revealing controls keeps being walked down.
        if len(seen) > known:
            self._scrolls[screen_id] = 0

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

    def _frontier(self, clickable: list[Element], tapped: set) -> list[Element]:
        """This screen's untapped controls, in the order coverage takes them.

        Controls that leave the screen go last. The app bar's back arrow sits
        top-left, so in screen order it came first: coverage tapped it, left a
        page whose other controls were never tapped, and never returned, since
        the button that opens the page had already been tapped. On the bench
        fixture that hid "Trigger crash" from every coverage-only run.
        """
        untapped = [e for e in clickable if self._elem_key(e) not in tapped]
        return sorted(untapped, key=self._leaves_screen)

    def _untapped_left(self) -> int:
        """Controls seen on some screen and never tapped there. Stopping while
        this is non-zero is "nothing left to tap here", not full coverage."""
        return sum(len(seen - self._tapped.get(sid, set()))
                   for sid, seen in self._seen_elems.items())

    # Labels of controls whose only job is to leave the current screen.
    _LEAVE_LABELS = ("back", "navigate up", "close", "dismiss")

    @classmethod
    def _leaves_screen(cls, e: Element) -> bool:
        return (e.label or "").strip().lower() in cls._LEAVE_LABELS

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

        # Auth wall first: fill and submit a login/registration screen once, so
        # coverage doesn't loop forever tapping fields it never types into.
        act = self._advance_login(elements, screen_id)
        if act is not None:
            return act

        # Guardrail: on an auth screen the deterministic filler is the ONLY thing
        # allowed to act. Everything else here is a field (tapping just focuses
        # it) or a link that leaves the flow — letting the model pick, or
        # coverage tap "Sign in" / "Forgot password", is exactly how a run
        # wanders off a half-filled sign-up form. Scroll to look for fields still
        # below the fold, then give up on this screen.
        if self.cfg.login and self._in_login_flow(elements, screen_id):
            if self._scrolls.get(screen_id, 0) < _SCROLL_TRIES:
                self._scrolls[screen_id] = self._scrolls.get(screen_id, 0) + 1
                self.dev.scroll("down")
                return Action("scroll", direction="down", reason="login: reveal more fields")
            self.dev.back()
            return Action("back", reason="login: nothing left to try on this screen")

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
        # it wants (search boxes), then scroll to reveal more, then leave.
        if (decision.verb == "type" and decision.text
                and screen_id not in self._typed):
            self._typed.add(screen_id)
            self.dev.type_text(decision.text)
            return Action("type", text=decision.text, reason=decision.reason)
        if self._scrolls.get(screen_id, 0) < _SCROLL_TRIES:
            self._scrolls[screen_id] = self._scrolls.get(screen_id, 0) + 1
            self.dev.scroll("down")
            return Action("scroll", direction="down", reason="coverage: reveal more controls")
        self.dev.back()
        return Action("back", reason="coverage: screen fully covered, backing out")

    # Button labels that submit a login/registration form.
    _SUBMIT_WORDS = (
        "sign in", "signin", "log in", "login", "sign up", "signup", "register",
        "create", "continue", "next", "verify", "submit", "get started", "done",
        "confirm",
    )
    _SIGNUP_WORDS = ("sign up", "signup", "create account", "create an account",
                     "register", "get started", "new account")
    _SIGNIN_WORDS = ("sign in", "signin", "log in", "login")
    # A link that goes the *wrong* way — "Already have an account? Sign in" on a
    # sign-up screen, and its mirror. Never follow these while navigating.
    _DECOY_WORDS = ("already have", "have an account", "already registered",
                    "don't have an account", "dont have an account")

    # Order to test credential names against a field label — longer/more specific
    # first, so "username" wins a "Username" field before "name" can claim it.
    _MATCH_ORDER = ("email", "phone", "username", "name", "password", "otp", "code")
    # Priority for handing a leftover (unlabelled) field a credential on a
    # multi-field form. OTP/code are never placed this way.
    _SPARE_ORDER = ("email", "password", "name", "phone", "username")
    _CONFIRM_WORDS = ("confirm", "repeat", "re-enter", "re-type", "verify password",
                      "password again")

    @staticmethod
    def _hit(label: str, words) -> bool:
        low = label.lower()
        return any(w in low for w in words)

    def _assign_fields(self, fields_els: list[Element]) -> list:
        """(element, credential-name, value) for each fillable field. Match by
        label first; then, on a multi-field form, hand any leftover field the
        next unused credential top-to-bottom so a form never submits half-empty.

        The credential NAME is carried so the caller can track "email is filled"
        across a screen reflow, when the field's label has become the value."""
        login = self.cfg.login
        used: set[str] = set()
        placed: dict[int, tuple] = {}
        for e in fields_els:
            label = e.label.lower()
            for name in self._MATCH_ORDER:
                if name in used or name not in login:
                    continue
                if name in label or (name == "email" and "@" in label):
                    placed[id(e)] = (e, name, login[name]); used.add(name); break
            else:
                if "password" in login and self._hit(label, self._CONFIRM_WORDS):
                    placed[id(e)] = (e, "confirm", login["password"])
        if len(fields_els) >= 2:
            spare = [n for n in self._SPARE_ORDER if n in login and n not in used]
            for e in fields_els:
                if id(e) in placed or not spare:
                    continue
                n = spare.pop(0)
                placed[id(e)] = (e, n, login[n]); used.add(n)
        return [placed[id(e)] for e in fields_els if id(e) in placed]

    def _advance_login(self, elements: list[Element], screen_id: int) -> "Action | None":
        """One deterministic step toward clearing a sign-in / sign-up screen, or
        None when there is nothing (more) to do here.

        Re-grounded on every call, deliberately: filling a field pops the
        keyboard and reflows the screen, so a plan captured up front taps stale
        coordinates — which is how a queued "fill email" lands on the "Sign in"
        link. Each call we look at the CURRENT elements, fill the next unfilled
        credential field, and tap submit only once every field is in.
        """
        if not self.cfg.login:
            return None
        editable = [e for e in elements if getattr(e, "editable", False)]
        buttons = [e for e in elements if e.clickable and not getattr(e, "editable", False)]
        real = [b for b in buttons if not self._hit(b.label, self._DECOY_WORDS)]
        primary = max(real, key=lambda e: e.bounds[2] - e.bounds[0], default=None)

        # A fresh inbox has no account: from a sign-IN screen, follow the
        # sign-UP link first. Capped, so a misread link can't burn the budget.
        if self._fresh_signup and primary is not None and self._hit(primary.label, self._SIGNIN_WORDS):
            link = next((b for b in real if self._hit(b.label, self._SIGNUP_WORDS)), None)
            if link is not None and self._signup_navs < 3:
                self._signup_navs += 1
                self._tapped.setdefault(screen_id, set()).add(self._elem_key(link))
                self.dev.tap(link.cx, link.cy)
                return Action("tap", x=link.cx, y=link.cy, target_label=link.label,
                              reason="login: go to sign-up")
            self._fresh_signup = False  # no link, or out of tries — just fill this screen

        assigned = self._assign_fields(editable)
        if not assigned:
            return None
        filled = self._login_filled.setdefault(screen_id, set())

        for el, name, value in assigned:
            if name in filled:
                continue
            filled.add(name)
            if value == "auto":  # OTP field, GREMLIN_LOGIN_EMAIL=auto
                value = self._mailbox.wait_for_code() if self._mailbox else None
                if not value:
                    print("  !! no verification code arrived; leaving the OTP field blank")
                    continue
            self._tapped.setdefault(screen_id, set()).add(self._elem_key(el))
            self.dev.tap(el.cx, el.cy)
            clear = getattr(self.dev, "clear_text", None)
            if clear:  # Android only; a browser field is set fresh anyway
                clear()
            self.dev.type_text(value)
            return Action("type", x=el.cx, y=el.cy, target_label=el.label,
                          text=value, reason=f"login: fill {el.label!r}")

        # Every credential field is in — submit once.
        if screen_id in self._login_submitted:
            return None
        submit = primary if (primary is not None and self._hit(primary.label, self._SUBMIT_WORDS)) \
            else next((b for b in real if self._hit(b.label, self._SUBMIT_WORDS)), None)
        if submit is None:
            return None  # button may be below the fold; the guardrail scrolls
        self._login_submitted.add(screen_id)
        self._fresh_signup = False
        self._tapped.setdefault(screen_id, set()).add(self._elem_key(submit))
        self.dev.tap(submit.cx, submit.cy)
        return Action("tap", x=submit.cx, y=submit.cy, target_label=submit.label,
                      reason="login: submit credentials")

    def _in_login_flow(self, elements: list[Element], screen_id: int) -> bool:
        """Is this an auth screen we should keep the model and coverage off?
        Scoped so an ordinary content screen that happens to have a search box
        is still explored normally."""
        if not any(getattr(e, "editable", False) for e in elements):
            return False
        if screen_id in self._login_filled or screen_id in self._login_submitted:
            return True
        if self._fresh_signup:
            return True
        if any("password" in e.label.lower()
               for e in elements if getattr(e, "editable", False)):
            return True
        return any(self._hit(b.label, self._SIGNIN_WORDS + self._SIGNUP_WORDS)
                   for b in elements if b.clickable)

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
            # Which source tree this run was about. Tier 2 has to patch the app
            # that was actually explored, and it may run long after the console
            # was restarted or a different target picked — so the run carries its
            # own answer rather than trusting whatever global state survives.
            "source_root": str(self.cfg.scribe_root),
            "platform": self.cfg.platform,
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
