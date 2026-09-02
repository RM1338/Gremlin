"""Web platform: drive a page instead of a device, and let Chrome confess.

This is the same agent, pointed at a browser. The bet the project rests on —
*the runtime reports its own failures, so detection is an exact match rather
than a model's judgment* — holds better here than on Android, not worse. Chrome
does not merely print its errors as text we then grep; it reports them as
structured DevTools events: an uncaught exception, a rejected promise, a console
error, a request that failed. Source locations arrive as real URLs with line
numbers rather than being scraped out of a stack trace.

Two decisions shape this file.

**Playwright drives, the model does not.** An agent framework that decides its
own clicks would replace Gremlin's coverage policy and its oracle/policy split,
which is the actual contribution. The driver here is deterministic: it exposes
the same verbs `Device` does and nothing more.

**The events are rendered as lines.** `WebOracle` formats each DevTools event
into one line and hands it to the same `oracle.classify_lines` the adb oracle
uses. That is what lets everything downstream — signal classification, dedup by
source location, the reporter, trace.json, the console — work on web without a
single change. The alternative, a parallel structured path, would have meant
touching every consumer.

The system browser is used (`channel="chrome"`) rather than a downloaded one,
because Playwright's own Chromium is another ~450 MB and this machine is short
of disk.
"""

from __future__ import annotations

import os
import re
import threading
from urllib.parse import urlparse

from .config import Config
from .grounding import Element
from . import oracle as _oracle
from . import platforms


# How many buffered lines to keep. A chatty page can log continuously, and an
# unbounded list would grow for the whole run.
_MAX_LINES = 4000

# Elements offered to the policy in one step. A large page can expose hundreds
# of links; past a few dozen the prompt costs more than the choice is worth.
_MAX_ELEMENTS = 40


def _viewport() -> tuple[int, int]:
    raw = os.environ.get("GREMLIN_WEB_VIEWPORT", "1280x800")
    try:
        w, h = raw.lower().split("x")
        return int(w), int(h)
    except ValueError:
        return 1280, 800


def origin_of(url: str) -> str:
    """The host we consider "inside the app under test"."""
    return (urlparse(url).hostname or url).lower()


def config_for(url: str, **kw) -> Config:
    """Build a Config aimed at a web target.

    `package` and `activity` keep the meanings the explorer already relies on,
    rather than growing two more fields that mean the same things: `package` is
    the origin, which `_ensure_on_app` compares against to notice we have
    wandered off-site, and `activity` is the address `relaunch` returns to.
    """
    return Config(package=origin_of(url), activity=url, platform="web", **kw)


# The DOM query that replaces the accessibility tree. It asks for the same thing
# `grounding.dump_elements` asks Android for: things a user could act on, with a
# label and a place to click. Anything invisible, zero-sized, disabled or
# scrolled out of view is dropped here rather than offered and then missed.
_ELEMENTS_JS = """
() => {
  const SEL = 'a[href],button,input,select,textarea,summary,[role=button],' +
              '[role=link],[role=tab],[role=menuitem],[role=checkbox],' +
              '[role=switch],[onclick],[contenteditable=""],[contenteditable=true]';
  const out = [];
  const seen = new Set();
  for (const el of document.querySelectorAll(SEL)) {
    const r = el.getBoundingClientRect();
    if (r.width <= 1 || r.height <= 1) continue;
    const st = getComputedStyle(el);
    if (st.visibility === 'hidden' || st.display === 'none') continue;
    if (parseFloat(st.opacity) === 0) continue;
    if (el.disabled) continue;
    const label = (el.getAttribute('aria-label') || el.innerText || el.value ||
                   el.getAttribute('placeholder') || el.getAttribute('title') ||
                   el.getAttribute('alt') || el.name || '')
                  .trim().split('\\n')[0].slice(0, 80);
    // Document coordinates, not viewport ones: a control four screens down is
    // still a control, and reporting where it lives on the page rather than
    // where it happens to sit right now is what lets `tap` reach it — and what
    // makes a recorded trace replay the same way from any scroll position.
    const x = Math.round(r.left + scrollX + r.width / 2);
    const y = Math.round(r.top + scrollY + r.height / 2);
    // Nested interactive elements (a > button) resolve to the same click point;
    // offering both would spend two coverage slots on one control.
    const key = x + ',' + y;
    if (seen.has(key)) continue;
    seen.add(key);
    out.push({
      label, x, y,
      bounds: [Math.round(r.left), Math.round(r.top),
               Math.round(r.right), Math.round(r.bottom)],
      typable: ['input', 'textarea'].includes(el.tagName.toLowerCase()),
    });
  }
  return out;
}
"""


class WebDriver:
    """`Device`'s surface, backed by a real browser page.

    Deliberately the same method names and the same return shapes, so
    `Explorer` drives either one without knowing which it has. The verbs mean
    what they mean on a phone: `back` is browser history, `scroll` is a wheel
    event, `type_text` goes to whatever has focus, and `relaunch` returns to the
    start address the way force-stop-and-start returns to a launcher activity.
    """

    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.start_url = cfg.activity
        self.origin = cfg.package
        self._pw = None
        self._browser = None
        self._page = None
        self._size = _viewport()
        self._lines: list[str] = []
        self._lock = threading.Lock()

    # ---- lifecycle -------------------------------------------------------

    def prepare(self) -> None:
        """Launch the browser and start listening for the page's confessions."""
        from playwright.sync_api import sync_playwright

        self._pw = sync_playwright().start()
        w, h = self._size
        headless = os.environ.get("GREMLIN_WEB_HEADFUL", "").lower() not in ("1", "true", "yes")
        # `--headless=new` is not optional here. Playwright starts system Chrome
        # in the *old* headless mode, where `Page.captureScreenshot` fails with
        # "Unable to capture screenshot" — and a driver that cannot screenshot
        # cannot feed the policy anything, so every step would die at Observe.
        # Chrome stops producing frames when it believes its window is hidden,
        # and then `Page.captureScreenshot` fails outright with "Unable to
        # capture screenshot". Off-screen and occluded is exactly the state a
        # headless window is in, so occlusion detection and renderer
        # backgrounding are turned off — without these the failure is
        # intermittent, which is worse than constant.
        args = [
            "--disable-features=CalculateNativeWinOcclusion",
            "--disable-backgrounding-occluded-windows",
            "--disable-renderer-backgrounding",
        ]
        if headless:
            args.insert(0, "--headless=new")
        try:
            self._browser = self._pw.chromium.launch(
                channel="chrome", headless=headless, args=args)
        except Exception:
            # No system Chrome — fall back to whatever Playwright has installed,
            # and say something useful if that is nothing either.
            try:
                self._browser = self._pw.chromium.launch(headless=headless)
            except Exception as e:
                raise RuntimeError(
                    "no browser to drive: install Google Chrome, or run "
                    "`python -m playwright install chromium` (~450 MB)."
                ) from e
        ctx = self._browser.new_context(viewport={"width": w, "height": h})
        # A rejected promise with no handler reaches the console as Chrome's own
        # phrasing, "Uncaught (in promise) ...", which is a string we would then
        # be depending on. The platform fires a real `unhandledrejection` event,
        # so listen for that and emit a line in a shape we define. Unlike the
        # Flutter and React Native probes, this needs no cooperation from the
        # app under test — it is injected before any page script runs.
        #
        # `preventDefault()` is load-bearing: without it Chrome ALSO surfaces the
        # rejection through CDP's `Runtime.exceptionThrown`, which Playwright
        # raises as `pageerror` — so every unhandled rejection was reported
        # twice, once here as `unhandled-rejection` and once as
        # `uncaught-exception` a line or two away. Suppressing the default action
        # drops the duplicate; a real `throw` still fires `pageerror` untouched.
        ctx.add_init_script("""
          addEventListener('unhandledrejection', (e) => {
            e.preventDefault();
            const r = e.reason;
            const where = (r && r.stack) ? ' ' + String(r.stack).split('\\n')[1] : '';
            console.error('Unhandled promise rejection: ' +
                          ((r && (r.message || r)) || 'unknown') + where);
          });
        """)
        self._page = ctx.new_page()
        self._attach(ctx, self._page)

    def _attach(self, ctx, page) -> None:
        """Render every DevTools event this page emits as one oracle line."""
        page.on("pageerror", self._on_pageerror)
        page.on("console", self._on_console)
        page.on("requestfailed", self._on_request_failed)
        page.on("response", self._on_response)
        # A dialog blocks the page until it is answered, which would hang the
        # run at the next screenshot. Dismiss and record it: an unexpected
        # alert is itself worth seeing in the trace.
        page.on("dialog", lambda d: (self._log(
            f"note: {d.type} dialog: {d.message}"), d.dismiss()))
        # target=_blank opens a second page that the explorer has no concept of.
        # Close it and stay on the one being explored.
        ctx.on("page", self._on_popup)

    def _on_pageerror(self, err) -> None:
        """An uncaught exception, with the frame that threw it.

        The stack is the whole point: it is what gives a web report a real
        `file:line` to quote, where an Android stack has to be scraped out of
        logcat and often names generated code instead. Only the top frames are
        kept — the rest is framework and the location extractor takes the first
        match anyway.
        """
        stack = (getattr(err, "stack", "") or "").replace("\n", " ")
        self._log(f"Uncaught {getattr(err, 'message', None) or err} {stack}"[:600])

    def _on_console(self, msg) -> None:
        # Only `console.error` counts. `console.warn` is advisory by definition
        # — deprecation notices, "this API is going away" — and treating it as a
        # defect produced a false positive on a page whose only sin was a
        # deprecation warning. React's correctness warnings are unaffected: it
        # reports "unique key" and "invalid hook call" through console.error.
        if msg.type != "error":
            return
        loc = msg.location or {}
        where = ""
        if loc.get("url"):
            # DevTools numbers console locations from zero while stack traces
            # number from one, so every console-sourced finding pointed one line
            # above the code that logged it.
            where = (f" at {loc['url']}:{loc.get('lineNumber', 0) + 1}"
                     f":{loc.get('columnNumber', 0) + 1}")
        text = msg.text
        # "Failed to load resource: ..." is the console's echo of something the
        # request/response handlers already report properly, and it fires for a
        # missing favicon on essentially every site — left in, it would put one
        # fabricated console-error bug in every web run ever done.
        if text.startswith("Failed to load resource"):
            return
        # The rejection line above is ours and is already in its final shape;
        # prefixing it with "console.error:" would push it past its own anchored
        # pattern and demote a crash to a generic console message.
        prefix = "" if text.startswith("Unhandled promise rejection") else "console.error: "
        self._log(f"{prefix}{text}{where}")

    def _on_request_failed(self, req) -> None:
        """A request the network could not complete — if it was one at all.

        `mailto:` and `tel:` links abort by design: the browser hands them to
        another application and reports ERR_ABORTED. Reporting that as a broken
        request would put a false finding on every site with a contact link,
        which is how a portfolio page came back with one bug that was its own
        email address.
        """
        url = req.url or ""
        if not url.startswith(("http://", "https://")):
            return
        self._log(f"Request failed: {url} {(req.failure or '')}")

    def _on_response(self, resp) -> None:
        if resp.status >= 500:
            self._log(f"HTTP {resp.status} {resp.url}")

    def _on_popup(self, page) -> None:
        if page is self._page:
            return
        try:
            # A `target="_blank"` link is ordinary web design, not a defect.
            # Logged with a prefix no signal matches, so it lands in the run's
            # context without being counted as a finding.
            self._log(f"note: popup opened and was closed: {page.url}")
            page.close()
        except Exception:
            pass

    def _log(self, line: str) -> None:
        with self._lock:
            self._lines.append(line.replace("\n", " ").strip())
            if len(self._lines) > _MAX_LINES:
                del self._lines[: len(self._lines) - _MAX_LINES]

    def drain_lines(self) -> list[str]:
        with self._lock:
            out, self._lines = self._lines, []
        return out

    def close(self) -> None:
        for shut in (getattr(self._browser, "close", None),
                     getattr(self._pw, "stop", None)):
            try:
                if shut:
                    shut()
            except Exception:
                pass
        self._browser = self._page = self._pw = None

    # ---- the verbs -------------------------------------------------------

    def screen_size(self) -> tuple[int, int]:
        return self._size

    def relaunch(self, package: str, activity: str) -> None:
        """Go back to the start address — the web's force-stop-and-restart.

        `wait_until="domcontentloaded"` rather than `load`: a page that never
        finishes loading a third-party script would otherwise stall the whole
        run before step 1, and the agent can act on a page that has content.
        """
        self._page.goto(activity or self.start_url,
                        wait_until="domcontentloaded", timeout=30000)
        self._settle()

    def launch(self, activity: str) -> None:
        self.relaunch(self.origin, activity)

    def screenshot(self) -> bytes:
        """A PNG of the current viewport, with one retry.

        The flags in `prepare` remove the cause of "Unable to capture
        screenshot", but the call is a protocol round-trip to a renderer that
        may be mid-navigation, so it can still lose a race. One retry after a
        short settle is enough; failing here aborts the whole run, because the
        policy has nothing to look at.
        """
        try:
            return self._page.screenshot()
        except Exception:
            self._settle(400)
            return self._page.screenshot()

    def tap(self, x: int, y: int) -> None:
        """Click a point in *document* space, scrolling it into view first.

        Elements are reported page-wide, so a target may be below the fold. The
        browser has no equivalent of "tap what is on screen"; it needs the point
        brought into the viewport, and doing it here means the explorer's
        coverage loop reaches a long page's whole control set instead of only
        its first screenful — which is why a portfolio page reported one screen
        and thirty taps that went nowhere.
        """
        try:
            vx, vy = self._page.evaluate(
                """([x, y]) => {
                    const targetTop = Math.max(0, y - innerHeight / 2);
                    const targetLeft = Math.max(0, x - innerWidth / 2);
                    if (y < scrollY || y > scrollY + innerHeight ||
                        x < scrollX || x > scrollX + innerWidth) {
                        window.scrollTo({left: targetLeft, top: targetTop,
                                         behavior: 'instant'});
                    }
                    return [x - scrollX, y - scrollY];
                }""", [int(x), int(y)])
            self._page.mouse.click(vx, vy)
        except Exception as e:
            self._log(f"note: click at {x},{y} failed: {e}")
        self._settle()

    def type_text(self, text: str) -> None:
        try:
            self._page.keyboard.type(text, delay=20)
        except Exception as e:
            self._log(f"note: typing failed: {e}")
        self._settle(300)

    def back(self) -> None:
        """Browser history, but never out the front door.

        A fresh page starts on `about:blank`, so the app's first screen is the
        *second* history entry and one `back` from it lands on a blank page with
        the run effectively over — the explorer then spends its remaining budget
        being thrown out and relaunched. Leaving the origin is treated the way
        Android treats being bounced into another app: go back to the start.
        """
        try:
            self._page.go_back(wait_until="domcontentloaded", timeout=15000)
        except Exception:
            pass  # no history to go back to is normal, not a failure
        if self.foreground_package() != self.origin:
            self.relaunch(self.origin, self.start_url)
        else:
            self._settle()

    def scroll(self, direction: str = "down") -> None:
        _, h = self._size
        dy = int(h * 0.7) * (-1 if direction == "up" else 1)
        try:
            self._page.mouse.wheel(0, dy)
        except Exception:
            pass
        self._settle(300)

    def foreground_package(self) -> str | None:
        """The current origin, so `_ensure_on_app` can notice an off-site link.

        Same contract as the Android version: return what we are "in" now, and
        the explorer compares it against `cfg.package`.
        """
        try:
            return origin_of(self._page.url)
        except Exception:
            return None

    def screen_key(self) -> str:
        """What makes this page *this* page, for visited-screen memory.

        The URL, and only the URL. Deliberately not pixels (every scroll is a
        different image of the same page) and deliberately not the set of
        control labels either: that was tried, and on a page with animations,
        modals and a "View More" toggle the label set changes almost every step,
        so nearly every step counted as a screen never seen before — which reset
        the per-screen tapped-set and sent the agent round the same three links
        for its whole budget.

        The cost is honest and worth stating: a single-page app that never
        changes its URL counts as one screen. Coverage is unharmed, because the
        controls of every view accumulate against that one id and each is still
        tapped once; it is the *distinct screens* metric that understates, which
        docs/KNOWN_ISSUES.md G16 already says is not quotable for web.
        """
        try:
            return self._page.url.split("#")[0]
        except Exception:
            return self.start_url

    def elements(self) -> list[Element]:
        """The DOM's answer to the accessibility tree."""
        try:
            raw = self._page.evaluate(_ELEMENTS_JS)
        except Exception:
            return []
        out: list[Element] = []
        for item in raw[:_MAX_ELEMENTS]:
            x1, y1, x2, y2 = item["bounds"]
            out.append(Element(
                index=len(out),
                label=item["label"] or "(unlabeled)",
                cx=int(item["x"]),
                cy=int(item["y"]),
                clickable=True,
                bounds=(int(x1), int(y1), int(x2), int(y2)),
            ))
        return out

    # ---- helpers ---------------------------------------------------------

    def _settle(self, ms: int = 600) -> None:
        """Give the page a moment to navigate, render, and log what it will."""
        try:
            self._page.wait_for_timeout(ms)
        except Exception:
            pass


class WebOracle:
    """`Oracle`'s surface, fed by the browser instead of logcat.

    Everything interesting is already shared: the driver has been buffering
    formatted lines since `prepare()`, and `oracle.classify_lines` turns them
    into the same `Signal` objects the adb path produces.
    """

    def __init__(self, driver: WebDriver,
                 platform: "platforms.Platform | str | None" = "web") -> None:
        self.driver = driver
        self.platform = (platform if isinstance(platform, platforms.Platform)
                         else platforms.by_name(platform))

    def start(self) -> None:
        """Listeners are attached at `prepare()`; discard anything before now."""
        self.driver.drain_lines()

    def drain(self) -> list[_oracle.Signal]:
        return _oracle.classify_lines(self.driver.drain_lines(), self.platform)

    def ensure_attached(self) -> bool:
        """Nothing to re-attach: the listeners live on the page, not on a pid.

        This is the one place the web platform is strictly simpler than Android,
        where a crash replaces the process and silently orphans the log stream
        (docs/KNOWN_ISSUES.md, G1). A page that throws is still the same page.
        """
        return False

    def stop(self) -> None:
        pass
