"""Brute accuracy check for the web platform: a page seeded with ten real
defects and a dozen traps, explored end to end by the real Explorer against
real Chrome on the coverage policy (no model, no quota, no cost).

It scores three things and prints them as a table:

  * recall     — every planted defect is reported
  * precision  — nothing else is (the traps stay silent)
  * location   — the reported file:line matches the line that actually broke

The smaller `web_explore_test.py` proves the path runs; this one tries to
break the oracle's judgement with the cases that have caused false findings
before (favicon 404, mailto links, console.warn, target=_blank, 4xx fetch).
"""
import http.server
import re
import shutil
import socketserver
import sys
import tempfile
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gremlin import web
from gremlin.explorer import Explorer


# Every line that ends in //PLANT:<kind> is a seeded defect; the test reads the
# expected line numbers straight out of this string, so a miscount here can't
# make the check lie. Each bad statement is on ONE line so the line the browser
# blames equals the line the marker sits on.
PAGE = """<!doctype html>
<meta charset="utf-8">
<title>Accuracy Bench</title>
<style>
  body { font: 15px system-ui; margin: 1.5rem; }
  button, a { display: block; margin: .35rem 0; }
</style>
<h1>Accuracy Bench</h1>

<button onclick="crashNull()">Crash: null deref</button>
<button onclick="crashRef()">Crash: undefined function</button>
<button onclick="crashThrow()">Crash: explicit throw</button>
<button onclick="rejectSync()">Reject: sync promise</button>
<button onclick="rejectAsync()">Reject: async function</button>
<button onclick="badRequest()">Net: connection refused</button>
<button onclick="serverError()">Net: 500 from server</button>
<button onclick="reactKey()">React: missing list key</button>
<button onclick="reactHook()">React: invalid hook call</button>
<button onclick="genericError()">Console: generic error</button>

<button onclick="warnOnly()">Trap: console.warn</button>
<button onclick="logOnly()">Trap: console.log/info</button>
<button onclick="resourceNoise()">Trap: failed-resource echo</button>
<button onclick="fetch404()">Trap: 404 fetch</button>
<button onclick="fetchOk()">Trap: 200 fetch</button>
<button onclick="alertTrap()">Trap: alert dialog</button>
<a href="mailto:someone@example.com">Trap: mailto link</a>
<a href="tel:+15551234567">Trap: tel link</a>
<a href="/other.html" target="_blank">Trap: new-tab link</a>

<script>
function crashNull()    { const o = null; o.x = 1; }                                                                //PLANT:uncaught-exception
function crashRef()     { return notDefinedAnywhere(); }                                                            //PLANT:uncaught-exception
function crashThrow()   { throw new Error('planted explicit throw'); }                                              //PLANT:uncaught-exception
function rejectSync()   { Promise.reject(new Error('planted sync rejection')); }                                    //PLANT:unhandled-rejection
async function rejectAsync() { throw new Error('planted async rejection'); }                                        //PLANT:unhandled-rejection
function badRequest()   { fetch('http://127.0.0.1:9/gone').catch(() => {}); }                                        //PLANT:request-failed
function serverError()  { fetch('/boom'); }                                                                         //PLANT:server-error
function reactKey()     { console.error('Each child in a list should have a unique "key" prop.'); }                 //PLANT:react-warning
function reactHook()    { console.error('Invalid hook call. Hooks can only be called inside of a function component.'); } //PLANT:react-warning
function genericError() { console.error('planted generic console failure EXK42'); }                                 //PLANT:console-error

function warnOnly()      { console.warn('this API is deprecated and will be removed'); }
function logOnly()       { console.log('just some debug output'); console.info('and some info'); }
function resourceNoise() { console.error('Failed to load resource: the server responded with a status of 404 (Not Found)'); }
function fetch404()      { fetch('/definitely-missing'); }
function fetchOk()       { fetch('/ok'); }
function alertTrap()     { alert('harmless alert'); }
</script>
"""

OTHER = "<!doctype html><meta charset=utf-8><title>Other</title><p>a perfectly fine other page"


def _expected_lines() -> dict[str, list[int]]:
    out: dict[str, list[int]] = {}
    for n, line in enumerate(PAGE.splitlines(), 1):
        m = re.search(r"//PLANT:(\S+)", line)
        if m:
            out.setdefault(m.group(1), []).append(n)
    return out


def _serve(root: Path):
    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(root), **kw)

        def log_message(self, *a):
            pass

        def do_GET(self):
            if self.path == "/boom":
                self.send_response(500)
                self.end_headers()
                self.wfile.write(b"deliberate server error")
                return
            if self.path == "/ok":
                self.send_response(200)
                self.send_header("content-type", "application/json")
                self.end_headers()
                self.wfile.write(b"{}")
                return
            return super().do_GET()          # real files, and 404 for the rest

    httpd = socketserver.ThreadingTCPServer(("127.0.0.1", 0), Handler)
    httpd.daemon_threads = True
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, httpd.server_address[1]


def test_web_accuracy_against_planted_defects_and_traps():
    root = Path(tempfile.mkdtemp(prefix="gremlin-webacc-"))
    run_dir = Path(tempfile.mkdtemp(prefix="gremlin-webacc-run-"))
    (root / "index.html").write_text(PAGE)
    (root / "other.html").write_text(OTHER)
    httpd, port = _serve(root)
    try:
        cfg = web.config_for(f"http://127.0.0.1:{port}/index.html",
                             policy="coverage", max_steps=45, run_dir=run_dir)
        bugs = Explorer(cfg).run()

        expected = _expected_lines()
        planted_kinds = {
            "uncaught-exception": 3, "unhandled-rejection": 2,
            "react-warning": 2, "console-error": 1,
            "request-failed": 1, "server-error": 1,
        }
        by_kind: dict[str, list] = {}
        for b in bugs:
            by_kind.setdefault(b.kind, []).append(b)

        print("\n  === web accuracy ===")
        print(f"  reported {len(bugs)} finding(s); expected {sum(planted_kinds.values())}\n")

        # ---- recall: every planted kind, at the planted multiplicity ----
        recall_ok = True
        for kind, want in sorted(planted_kinds.items()):
            got = len(by_kind.get(kind, []))
            mark = "OK " if got >= want else "MISS"
            if got < want:
                recall_ok = False
            print(f"  [{mark}] recall  {kind:<20} found {got}/{want}")

        # ---- precision: nothing outside the planted set ----
        strays = [b for b in bugs if b.kind not in planted_kinds]
        overshoot = [f"{k} x{len(by_kind[k])}" for k in by_kind
                     if k in planted_kinds and len(by_kind[k]) > planted_kinds[k]]
        print()
        print(f"  [{'OK ' if not strays else 'FAIL'}] precision  unexpected kinds: "
              f"{[b.kind for b in strays] or 'none'}")
        print(f"  [{'OK ' if not overshoot else 'WARN'}] precision  over-count: "
              f"{overshoot or 'none'}")

        # ---- location: file:line matches the line that actually threw ----
        located = hit = 0
        for kind, lines in expected.items():
            if kind in ("request-failed", "server-error"):
                continue  # these signals carry no source location by design
            for b in by_kind.get(kind, []):
                located += 1
                ok = b.dart_file and b.dart_file.endswith("index.html") and b.dart_line in lines
                hit += bool(ok)
                print(f"  [{'OK ' if ok else 'off'}] loc     {kind:<20} "
                      f"{b.dart_file}:{b.dart_line}  (want index.html:{lines})")
        print(f"\n  line-match: {hit}/{located}")

        # ---- verdicts ----
        assert recall_ok, f"missed a planted defect: {by_kind.keys()}"
        assert not strays, f"false positive on a trap: {[b.title() for b in strays]}"
        assert len(bugs) == sum(planted_kinds.values()), \
            f"expected exactly {sum(planted_kinds.values())} findings, got {len(bugs)}: " \
            f"{[b.title() for b in bugs]}"
        # Location extraction is best-effort by design (generated code is skipped
        # rather than guessed), so this is a floor, not a demand for perfection.
        assert hit >= located * 0.75, f"line accuracy {hit}/{located} below 75%"
    finally:
        httpd.shutdown()
        shutil.rmtree(root, ignore_errors=True)
        shutil.rmtree(run_dir, ignore_errors=True)


if __name__ == "__main__":
    test_web_accuracy_against_planted_defects_and_traps()
    print("\nok")
