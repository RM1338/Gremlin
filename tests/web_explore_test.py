"""End-to-end: explore a broken page and catch what it confesses.

Runs the real `Explorer` against a real Chrome against a real HTTP server, on
the coverage policy so it needs no model and no quota — which makes this the
one test in the suite that exercises the whole web path deterministically and
for free.

The fixture is written here rather than kept in the repo: the demo apps live in
repositories of their own, and a page with four planted defects is small enough
to state inline, where the assertions can be read against it.
"""
import http.server
import json
import shutil
import socketserver
import sys
import tempfile
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gremlin import platforms, web
from gremlin.explorer import Explorer
from gremlin.oracle import extract_location


PAGE = """<!doctype html>
<meta charset="utf-8">
<title>Bench</title>
<style>
  body { font: 16px system-ui; margin: 2rem; }
  button { display: block; margin: .6rem 0; padding: .6rem 1rem; font-size: 1rem; }
  section { display: none; } section.on { display: block; }
</style>

<section id="home" class="on">
  <h1>Bench</h1>
  <button onclick="go('crash')">Null crash</button>
  <button onclick="go('reject')">Promise reject</button>
  <button onclick="go('net')">Bad request</button>
  <button onclick="go('warn')">Console error</button>
  <button onclick="go('clean')">Settings</button>
</section>

<section id="crash"><h1>Crash</h1><button onclick="home()">Back</button></section>
<section id="reject"><h1>Reject</h1><button onclick="home()">Back</button></section>
<section id="net"><h1>Net</h1><button onclick="home()">Back</button></section>
<section id="warn"><h1>Warn</h1><button onclick="home()">Back</button></section>
<section id="clean"><h1>Settings</h1><button onclick="home()">Back</button></section>

<script>
function show(id) {
  for (const s of document.querySelectorAll('section')) s.classList.remove('on');
  document.getElementById(id).classList.add('on');
}
function home() { show('home'); }
function go(id) {
  show(id);
  if (id === 'crash')  { window.nothing.here = 1; }
  if (id === 'reject') { Promise.reject(new Error('planted rejection')); }
  if (id === 'net')    { fetch('http://127.0.0.1:9/missing'); }
  if (id === 'warn')   { console.error('Each child in a list should have a unique "key" prop.'); }
}
</script>
"""


def _serve(root: Path):
    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(root), **kw)

        def log_message(self, *a):
            pass

    httpd = socketserver.TCPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, httpd.server_address[1]


def test_web_exploration_finds_planted_defects():
    root = Path(tempfile.mkdtemp(prefix="gremlin-web-"))
    run_dir = Path(tempfile.mkdtemp(prefix="gremlin-run-"))
    (root / "index.html").write_text(PAGE)
    httpd, port = _serve(root)
    try:
        cfg = web.config_for(f"http://127.0.0.1:{port}/index.html",
                             policy="coverage", max_steps=14, run_dir=run_dir)
        assert cfg.platform == "web"
        assert cfg.package == "127.0.0.1"

        bugs = Explorer(cfg).run()
        kinds = {b.kind for b in bugs}
        print("  found:", sorted(kinds))

        # The two that are unambiguously the page's fault.
        assert "uncaught-exception" in kinds, kinds
        assert "unhandled-rejection" in kinds, kinds
        # The React warning must be classified as itself, not as a bare console
        # error — that ordering is what makes the report say something useful.
        assert "react-warning" in kinds, kinds
        assert "request-failed" in kinds, kinds

        # Exploration, not just detection: the coverage policy should have moved
        # off the first screen and tapped more than one control.
        trace = json.loads((run_dir / "trace.json").read_text())
        assert trace["steps"]
        assert len(bugs) >= 4, [b.kind for b in bugs]

        # G16: one URL, six views. Keyed by URL alone this was 1 screen.
        assert trace["distinct_screens"] == 6, trace["distinct_screens"]
    finally:
        httpd.shutdown()
        shutil.rmtree(root, ignore_errors=True)
        shutil.rmtree(run_dir, ignore_errors=True)


def test_route_keeps_hash_routes_and_drops_anchors():
    assert web.route_of("http://a.dev/x?q=1#pricing") == "http://a.dev/x?q=1"
    assert web.route_of("http://a.dev/#/cart") == "http://a.dev/#/cart"
    assert web.route_of("http://a.dev/#!/cart") == "http://a.dev/#!/cart"
    assert web.route_of("http://a.dev/") == "http://a.dev/"


TYPEWRITER = """<!doctype html>
<h1 id="hero"></h1><h1>About</h1>
<p style="height:3000px">tall</p>
<script>
const words = "I build things that break";
let i = 0;
setInterval(() => { hero.textContent = words.slice(0, i++ % words.length); }, 40);
</script>
"""


def test_screen_key_ignores_typewriter_and_scroll():
    """A churning hero headline or a scroll must not mint new screens."""
    root = Path(tempfile.mkdtemp(prefix="gremlin-web-"))
    (root / "index.html").write_text(TYPEWRITER)
    httpd, port = _serve(root)
    d = web.WebDriver(web.config_for(f"http://127.0.0.1:{port}/index.html#top"))
    try:
        d.prepare()
        d.relaunch(d.origin, d.start_url)
        keys = set()
        for _ in range(4):
            keys.add(d.screen_key())
            d.scroll("down")
        assert keys == {f"http://127.0.0.1:{port}/index.html | About"}, keys
    finally:
        d.close()
        httpd.shutdown()
        shutil.rmtree(root, ignore_errors=True)


def test_config_for_derives_origin():
    cfg = web.config_for("https://example.com/app/start?x=1")
    assert cfg.package == "example.com"
    assert cfg.activity == "https://example.com/app/start?x=1"
    assert web.origin_of("http://localhost:5173/a/b") == "localhost"


def test_source_location_survives_the_url():
    """A web report's whole advantage is a real file:line — check it lands."""
    w = platforms.by_name("web")
    cases = {
        "Uncaught TypeError: x at http://127.0.0.1:8765/index.html:33:7":
            ("index.html", 33),
        "Uncaught Err at https://site.dev/assets/app.jsx:120:4":
            ("assets/app.jsx", 120),
        "console.error: boom at http://localhost:5173/src/lib/api.ts:8:3":
            ("src/lib/api.ts", 8),
        # Generated output names a line no developer can edit; better to report
        # no location than a wrong one.
        "Uncaught X at http://h/dist/main.bundle.js:1:99": (None, None),
    }
    for line, want in cases.items():
        assert extract_location([line], w) == want, (line, extract_location([line], w))


def test_favicon_noise_is_not_a_bug():
    """Every site 404s a favicon; that must not be a finding on every run."""
    w = platforms.by_name("web")
    noise = "console.error: Failed to load resource: the server responded with a status of 404"
    # The driver drops it before it is ever logged, but if that guard is removed
    # this asserts the consequence: it *would* classify, so the guard is load-bearing.
    assert w.classify(noise) is not None


class _FakeMsg:
    """The shape Playwright hands to a console listener."""
    def __init__(self, type_, text, line=None):
        self.type, self.text = type_, text
        self.location = {"url": "http://h/app.js", "lineNumber": line,
                         "columnNumber": 0} if line is not None else None


def _driver_capturing():
    d = web.WebDriver.__new__(web.WebDriver)      # no browser needed
    d._lines, d._lock = [], __import__("threading").Lock()
    return d


def test_console_warn_is_not_a_defect():
    """A deprecation notice is not a bug; treating it as one cried wolf."""
    d = _driver_capturing()
    d._on_console(_FakeMsg("warning", "this API is deprecated", 12))
    d._on_console(_FakeMsg("log", "just chatting", 12))
    assert d.drain_lines() == []
    d._on_console(_FakeMsg("error", "real failure", 12))
    assert len(d.drain_lines()) == 1


def test_console_line_numbers_are_one_based():
    """DevTools counts console locations from zero; stack traces from one.

    Left uncorrected, every console-sourced finding pointed one line above the
    code that logged it — quietly wrong in a way no test would notice.
    """
    d = _driver_capturing()
    d._on_console(_FakeMsg("error", "boom", 41))   # zero-based 41 == line 42
    line, = d.drain_lines()
    assert ":42:" in line, line


def test_resource_404_never_reaches_the_oracle():
    d = _driver_capturing()
    d._on_console(_FakeMsg("error", "Failed to load resource: 404 (Not Found)", 0))
    assert d.drain_lines() == []


def test_web_target_is_never_installed_on_a_device():
    """A website is not an APK. Installing one is not a thing that can happen.

    The console kept a sandbox serial from an earlier device run, so a web
    target went down the install path and failed with "<domain> is not
    installed in the sandbox".
    """
    from gremlin import device, sandbox
    cfg = web.config_for("https://debtcalculatorpro.com")
    cfg.serial = "localhost:5555"
    called = []
    real = device.Device.list_third_party_packages
    device.Device.list_third_party_packages = lambda self: called.append(1) or []
    try:
        sandbox.ensure_installed(cfg)          # must return without touching adb
    finally:
        device.Device.list_third_party_packages = real
    assert called == [], "a web run reached the device layer"


def test_mailto_link_is_not_a_broken_request():
    """A contact link must not be a finding on every site that has one."""
    class _Req:
        def __init__(self, url): self.url, self.failure = url, "net::ERR_ABORTED"
    d = _driver_capturing()
    d._on_request_failed(_Req("mailto:someone@example.com"))
    d._on_request_failed(_Req("tel:+100"))
    assert d.drain_lines() == []
    d._on_request_failed(_Req("https://example.com/api/x"))
    assert len(d.drain_lines()) == 1


if __name__ == "__main__":
    test_route_keeps_hash_routes_and_drops_anchors()
    test_config_for_derives_origin()
    test_mailto_link_is_not_a_broken_request()
    test_web_target_is_never_installed_on_a_device()
    test_console_warn_is_not_a_defect()
    test_console_line_numbers_are_one_based()
    test_resource_404_never_reaches_the_oracle()
    test_source_location_survives_the_url()
    test_favicon_noise_is_not_a_bug()
    test_screen_key_ignores_typewriter_and_scroll()
    test_web_exploration_finds_planted_defects()
    print("ok")
