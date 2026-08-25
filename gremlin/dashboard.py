"""Gremlin console — a modern, multi-page web app for watching the agent work.

Not a single dashboard but a small site: an Overview landing page, a Live run
view that streams the agent's observe→decide→act→check loop over a WebSocket, a
Trace timeline, a Bugs gallery, and a Gremlin-vs-monkey Benchmark. The chrome is
a static SPA served here; live data arrives over ``/ws`` and the
finished artifacts (``trace.json``, ``eval.json``, screenshots) over ``/api``.
The console is the React app in ``frontend/``; build it before first use.

    python -m gremlin.dashboard [--steps N]

Then open http://127.0.0.1:8000.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import threading
import traceback
from contextlib import asynccontextmanager
from dataclasses import replace
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .autofix import _load_bugs, _persist_outcome, outcome_payload
from .config import Config, PROJECTS_ROOT
from .device import Device
from .explorer import Explorer
from .fix_backend import backend_name, edits_source
from .fixer import (DirtyTreeError, FixMergeError, fix_one, merge_fix,
                    _require_clean_tree)
from .targets import all_targets
from . import emulator, platforms, sandbox, settings

# The React console, built with `cd frontend && npm run build`.
_DIST = Path(__file__).parent.parent / "frontend" / "dist"

_clients: set[WebSocket] = set()
_loop: asyncio.AbstractEventLoop | None = None
_run_started = False
_cfg = Config()
_target_name: str | None = None  # friendly name of the selected app, for the UI
# An emulator this dashboard booted, so it can be shut down again. None when we
# are driving a device that was already attached — which we must never kill.
_emulator: "emulator.Emulator | None" = None
# A sandbox container this dashboard booted. Same contract as _emulator: we only
# ever stop what we started.
_sandbox: "sandbox.Sandbox | None" = None
# The Explorer of the run in flight, so /api/stop can ask it to wind down. None
# whenever nothing is running.
_explorer: "Explorer | None" = None
# True while a Tier-2 fix holds the device. A fix replays taps and re-explores,
# so it and a run cannot share the phone; each refuses while the other has it.
_fixing = False


@asynccontextmanager
async def _lifespan(app: FastAPI):
    # Capture the running loop so the explorer thread can push to websockets.
    global _loop
    _loop = asyncio.get_running_loop()
    yield


app = FastAPI(lifespan=_lifespan)
if (_DIST / "assets").exists():
    app.mount("/assets", StaticFiles(directory=_DIST / "assets"), name="assets")


# ---- live fan-out ----------------------------------------------------------
def _broadcast(message: dict) -> None:
    """Thread-safe fan-out to all connected browsers (called from the run thread)."""
    if _loop is None:
        return
    data = json.dumps(message)
    for ws in list(_clients):
        asyncio.run_coroutine_threadsafe(_safe_send(ws, data), _loop)


async def _safe_send(ws: WebSocket, data: str) -> None:
    try:
        await ws.send_text(data)
    except Exception:
        _clients.discard(ws)


def _on_event(event: str, payload: dict) -> None:
    # Enrich step events with the actual frame so the browser can render it live.
    if event == "step":
        shot = payload.get("screenshot")
        if shot and Path(shot).exists():
            payload = dict(payload)
            payload["frame"] = base64.b64encode(Path(shot).read_bytes()).decode()
    _broadcast({"event": event, **payload})


def _start_run() -> None:
    global _run_started
    if _run_started or _fixing:
        return
    _run_started = True

    def worker() -> None:
        global _explorer
        try:
            if sandbox.is_sandbox(_cfg.serial):
                # A container starts empty, so there is nothing to explore until
                # the target is built and pushed into it. The CLI has always done
                # this; the console used to launch a package that was not there.
                # It happens on the run thread because a cold Gradle build is
                # minutes long and /start must not block on it.
                sandbox.ensure_installed(
                    _cfg, on_status=lambda m: _on_event("status", {"note": m}))
            _explorer = Explorer(_cfg, on_event=_on_event)
            bugs = _explorer.run()
            from .reporter import write_reports

            if bugs:
                write_reports(bugs, _cfg)
        except BaseException as e:
            # Any unexpected failure has to reach the browser. Without this the
            # thread died silently, no `done` was ever emitted, and the console
            # sat on "waiting for first frame" for as long as you left it —
            # while the phone stayed awake. An ugly summary beats a hang.
            traceback.print_exc()
            _on_event("done", {
                "steps": 0, "screens": 0, "bugs": 0, "duration_sec": 0,
                "verbs": {}, "sections": [], "bugs_by_severity": {},
                "complete": False, "ended_early": True,
                "note": f"The run failed: {type(e).__name__}: {e}"[:400],
            })
        finally:
            global _run_started
            _run_started = False
            _explorer = None

    threading.Thread(target=worker, daemon=True).start()


# ---- pages -----------------------------------------------------------------
_BUILD_HINT = """<!doctype html><meta charset=utf-8>
<title>Gremlin — console not built</title>
<body style="font:16px/1.6 system-ui;max-width:40rem;margin:4rem auto;padding:0 1rem">
<h1>The console has not been built yet.</h1>
<p>Build it once, then reload this page:</p>
<pre style="background:#f4f4f5;padding:1rem;border-radius:6px">cd frontend &amp;&amp; npm install &amp;&amp; npm run build</pre>
<p>Runs themselves need none of this — <code>python run.py</code> works without the console.</p>
</body>"""


def _serve_app() -> HTMLResponse:
    """Serve the built React SPA, or tell the developer how to build it."""
    index = _DIST / "index.html"
    if not index.exists():
        return HTMLResponse(_BUILD_HINT, status_code=503)
    return HTMLResponse(index.read_text())


@app.get("/")
async def index() -> HTMLResponse:
    return _serve_app()


@app.post("/start")
async def start(request: Request):
    """Start a run. An optional JSON body selects which app to test:
    {"name","package","activity","source_root"}."""
    global _target_name
    if _fixing:
        return JSONResponse(
            {"error": "a Tier-2 fix is using the device — wait for it to finish"},
            status_code=409)
    if not _run_started:
        try:
            body = await request.json()
        except Exception:
            body = None
        if body and body.get("package"):
            pkg = body["package"]
            _cfg.package = pkg
            # Device-only apps arrive without an activity; resolve it now.
            activity = body.get("activity")
            if not activity:
                activity = Device(_cfg.serial).resolve_launcher(pkg) or f"{pkg}/.MainActivity"
            _cfg.activity = activity
            _cfg.scribe_root = Path(body["source_root"]) if body.get("source_root") else PROJECTS_ROOT
            _target_name = body.get("name")
            # A project target knows its own toolkit; a device-only one has to be
            # identified from the installed APK, which costs a pull — so it
            # happens here, on selection, not while listing targets.
            plat = body.get("platform")
            if not plat:
                found = platforms.detect_platform_on_device(Device(_cfg.serial), pkg)
                plat = found.name if found else platforms.DEFAULT.name
            _cfg.platform = plat
    if not _cfg.package:
        return JSONResponse(
            {"error": "no app selected — pick one from the target list first"},
            status_code=400)
    _start_run()
    return {"started": True, "package": _cfg.package, "activity": _cfg.activity,
            "platform": _cfg.platform}


@app.get("/api/settings")
async def api_settings() -> JSONResponse:
    """Current runtime settings, plus what is actually installed on this box."""
    return JSONResponse(settings.read())


@app.post("/api/settings")
async def api_settings_save(request: Request) -> JSONResponse:
    """Persist a settings patch to .env, to this process, and to the live Config.

    Refused while a run is in flight: the explorer holds this Config object, so
    editing the step budget or the policy underneath it would change the rules
    of a run already in progress.
    """
    if _run_started:
        return JSONResponse(
            {"error": "a run is in progress — stop it before changing settings"},
            status_code=409)
    try:
        patch = await request.json()
    except Exception:
        return JSONResponse({"error": "expected a JSON object"}, status_code=400)
    if not isinstance(patch, dict):
        return JSONResponse({"error": "expected a JSON object"}, status_code=400)

    # A secret sent back as the empty string means "leave it alone", not "clear
    # it" — the UI never receives the value, so it cannot echo it back.
    patch = {k: ("" if v is None else str(v)) for k, v in patch.items()}
    secret_keys = {f.key for f in settings.FIELDS if f.kind == "secret"}
    patch = {k: v for k, v in patch.items() if v != "" or k not in secret_keys}

    problems = settings.validate(patch)
    if problems:
        return JSONResponse({"error": problems[0], "problems": problems}, status_code=400)

    settings.write(patch)

    # Fields marked `applied` live on the Config the next run will use.
    if "GREMLIN_MAX_STEPS" in patch and patch["GREMLIN_MAX_STEPS"].isdigit():
        _cfg.max_steps = int(patch["GREMLIN_MAX_STEPS"])
    if "GREMLIN_POLICY" in patch:
        _cfg.policy = patch["GREMLIN_POLICY"]
    if "GREMLIN_PLATFORM" in patch:
        # Empty means "go back to detecting it", which is the default behaviour.
        _cfg.platform = patch["GREMLIN_PLATFORM"] or platforms.DEFAULT.name

    return JSONResponse(settings.read())


@app.post("/api/stop")
async def api_stop() -> JSONResponse:
    """Ask the run in flight to end after the current step.

    Deliberately not a kill: the explorer finishes the action it is mid-way
    through, then stops the oracle, writes the trace and emits `done` like any
    other ending. That is also what releases the device — a killed thread would
    leave the phone's screen pinned awake.
    """
    if not _run_started or _explorer is None:
        return JSONResponse({"stopping": False, "error": "no run in progress"}, status_code=409)
    _explorer.stop()
    return JSONResponse({"stopping": True})


def _run_project() -> "tuple[Config, list] | JSONResponse":
    """The project this run explored, and its bugs — or why we cannot say.

    The run records its own source root, because the module-level _cfg only says
    what was last selected: after a console restart that is a default which may
    not exist, and after picking another target it is the wrong app entirely.
    """
    trace = _cfg.run_dir / "trace.json"
    if not trace.exists():
        return JSONResponse({"error": "no run to fix — this run has no trace.json"},
                            status_code=404)
    recorded = _read_json(trace) or {}
    cfg = replace(_cfg, scribe_root=Path(recorded["source_root"]),
                  platform=recorded.get("platform") or _cfg.platform) \
        if recorded.get("source_root") else _cfg
    if not Path(cfg.scribe_root).is_dir():
        return JSONResponse(
            {"error": f"the app's source is not on disk at {cfg.scribe_root} — "
                      f"start a run against the project you want to fix, so the "
                      f"run records where its source lives."}, status_code=400)
    return cfg, _load_bugs(trace)


@app.post("/api/fix/merge")
async def api_fix_merge(request: Request) -> JSONResponse:
    """Merge a verified fix into the app's base branch: {"bug": N}.

    Only ever a verified one. The gates are what make a patch worth taking, so a
    reverted or unattempted bug has nothing to offer here — and the verdict is
    read back off disk rather than trusted from the browser.
    """
    if _run_started or _fixing:
        return JSONResponse({"error": "the device is busy — wait for it to finish"},
                            status_code=409)
    resolved = _run_project()
    if isinstance(resolved, JSONResponse):
        return resolved
    cfg, bugs = resolved
    try:
        body = await request.json()
    except Exception:
        body = {}
    n = body.get("bug")
    if not isinstance(n, int) or not 1 <= n <= len(bugs):
        return JSONResponse({"error": f"'bug' must be 1..{len(bugs)}"}, status_code=400)

    outcome = _read_json(cfg.run_dir / "reports" / f"bug_{n:03d}.fix.json") or {}
    if not outcome.get("verified") or not outcome.get("branch"):
        return JSONResponse(
            {"error": "there is no verified fix for this bug to merge"}, status_code=400)
    try:
        base = await asyncio.to_thread(merge_fix, cfg, outcome["branch"])
    except (FixMergeError, DirtyTreeError) as e:
        return JSONResponse({"error": str(e)}, status_code=409)
    except RuntimeError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    return JSONResponse({"merged": outcome["branch"], "into": base,
                         "repo": str(cfg.scribe_root)})


@app.post("/api/fix")
async def api_fix(request: Request) -> JSONResponse:
    """Attempt the Tier-2 autofix for one bug of the current run: {"bug": N}.

    N is the bug's 1-based position in the run, the same number the report files
    use. The work is minutes long — the agent patches, the APK rebuilds, the
    trace replays, a probe re-explores — so this only reports that it started;
    the phases and the verdict arrive over ``/ws`` as ``fix`` events.
    """
    global _fixing
    if _run_started or _fixing:
        return JSONResponse({"error": "the device is busy — stop the run first"},
                            status_code=409)

    backend = backend_name()
    if not edits_source(backend):
        return JSONResponse(
            {"error": f"FIX_BACKEND is '{backend}', which only writes a prompt and "
                      f"edits nothing. Set it to claude, codex or copilot in Settings."},
            status_code=400)

    resolved = _run_project()
    if isinstance(resolved, JSONResponse):
        return resolved
    cfg, bugs = resolved
    try:
        body = await request.json()
    except Exception:
        body = {}
    n = body.get("bug")
    if not isinstance(n, int) or not 1 <= n <= len(bugs):
        return JSONResponse({"error": f"'bug' must be 1..{len(bugs)}"}, status_code=400)
    bug = bugs[n - 1]

    # The fixer refuses a dirty tree anyway, but it does so inside the thread —
    # and this is the failure a developer hits most, so answer it in the response
    # rather than as a verdict five seconds later.
    try:
        _require_clean_tree(cfg)
    except DirtyTreeError as e:
        return JSONResponse({"error": str(e)}, status_code=409)
    except RuntimeError as e:
        # Not a git repository, or git itself failed. A 500 told the developer
        # nothing; the reason is short and worth showing.
        return JSONResponse({"error": str(e)}, status_code=400)

    # Gate 3 calls anything not already known a NEW break and replays the other
    # bugs' traces, so it needs every bug in the run, not just the one being fixed.
    _fixing = True

    def worker() -> None:
        global _fixing
        try:
            outcome = fix_one(
                cfg, bug, bugs, backend=backend,
                on_phase=lambda ph: _broadcast({"event": "fix", "bug": n, "phase": ph}),
            )
            _persist_outcome(cfg.run_dir, n, outcome)
            _broadcast({"event": "fix", "bug": n, "phase": "done", **outcome_payload(outcome)})
        except BaseException as e:
            # Same reasoning as the run thread: a silent death here would leave
            # the console waiting on a verdict that is never coming.
            traceback.print_exc()
            _broadcast({"event": "fix", "bug": n, "phase": "done", "verified": False,
                        "gates": [], "guard_violations": [], "branch": None,
                        "note": f"the fix failed: {type(e).__name__}: {e}"[:400]})
        finally:
            _fixing = False

    threading.Thread(target=worker, daemon=True).start()
    return JSONResponse({"fixing": True, "bug": n, "backend": backend,
                         "title": bug.title()})


@app.get("/api/targets")
async def api_targets() -> JSONResponse:
    """App projects (full capability) plus installed apps, flagged by source."""
    targets = all_targets(PROJECTS_ROOT, dev=Device(_cfg.serial))
    return JSONResponse({
        "projects_root": str(PROJECTS_ROOT),
        "targets": [t.to_dict() for t in targets],
        "selected": _cfg.package,
    })


@app.get("/api/devices")
async def api_devices() -> JSONResponse:
    """What we can run on: attached devices, plus emulators we could boot.

    This is what lets a developer with no phone on their desk still drive a run —
    an emulator is just another adb serial to everything downstream.
    """
    status = emulator.sdk_status()
    attached = [{"serial": s, "state": st,
                 "emulator": emulator.is_emulator(s), "sandbox": sandbox.is_sandbox(s)}
                for s, st in emulator._adb_devices()]
    box = sandbox.status()
    return JSONResponse({
        "attached": attached,
        "avds": list(status.avds),
        "running_emulators": emulator.running_emulators(),
        "selected": _cfg.serial,
        # Non-null when we cannot offer emulator boot, and says how to fix it.
        "emulator_problem": status.problem,
        # The third way to get a device: a container, no phone and no AVD needed.
        "sandbox": {
            "serial": sandbox.SERIAL,
            "running": box.container == "running",
            "can_start": box.can_start,
            "problem": box.problem,   # e.g. binder not loaded, with the fix
            "note": box.note,         # e.g. the first start downloads the image
            # Whether that problem is one the console can fix itself, with a
            # button and the desktop's own password dialog, instead of handing
            # the developer a modprobe line to paste into a terminal.
            "can_setup": box.binder != "ok" and sandbox.can_self_setup(),
            "setup_cmd": f"sudo {sandbox.SETUP_SCRIPT}",
        },
    })


@app.post("/api/sandbox/setup")
async def api_sandbox_setup() -> JSONResponse:
    """Make this host able to run the sandbox: binder now, and after reboot.

    Root, so it goes through pkexec and the user authorises it in their desktop's
    normal password dialog. That is the only privileged thing Gremlin ever does,
    it is never silent, and the script it runs is in the repo to be read.
    """
    try:
        out = await asyncio.to_thread(sandbox.setup)
    except RuntimeError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    box = sandbox.status()
    return JSONResponse({"ok": True, "log": out, "can_start": box.can_start,
                         "problem": box.problem})


@app.post("/api/devices/select")
async def api_select_device(request: Request) -> JSONResponse:
    """Point subsequent runs at a specific adb serial (null = the only device)."""
    body = await request.json()
    _cfg.serial = body.get("serial") or None
    return JSONResponse({"selected": _cfg.serial})


@app.post("/api/emulator/start")
async def api_emulator_start(request: Request) -> JSONResponse:
    """Boot an AVD and select it, so the next run has something to drive."""
    global _emulator
    if _run_started:
        return JSONResponse({"error": "a run is already in progress"}, status_code=409)
    try:
        body = await request.json()
    except Exception:
        body = {}
    try:
        # Booting blocks for up to a few minutes, so it must not hold the event
        # loop — every other endpoint (including the run's websocket) shares it.
        started = await asyncio.to_thread(
            emulator.Emulator.start, body.get("avd"), headless=bool(body.get("headless")))
    except (RuntimeError, TimeoutError) as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    _emulator = started
    _cfg.serial = started.serial
    return JSONResponse({"serial": started.serial, "avd": started.avd})


@app.post("/api/emulator/stop")
async def api_emulator_stop() -> JSONResponse:
    """Shut down an emulator this dashboard booted."""
    global _emulator
    if _emulator is None:
        return JSONResponse({"error": "no emulator started from here"}, status_code=404)
    await asyncio.to_thread(_emulator.stop)
    _emulator, _cfg.serial = None, None
    return JSONResponse({"stopped": True})


@app.post("/api/sandbox/start")
async def api_sandbox_start(request: Request) -> JSONResponse:
    """Boot a containerised Android instance and select it for the next run.

    Geometry is a boot parameter rather than a fixed property of the machine,
    which is what makes a form-factor sweep cheap — overflow defects are screen-
    size dependent, so the same app is worth exploring at several widths.
    """
    global _sandbox
    if _run_started or _fixing:
        return JSONResponse({"error": "the device is busy"}, status_code=409)
    try:
        body = await request.json()
    except Exception:
        body = {}
    try:
        # The first start pulls a couple of GB, so this cannot hold the event
        # loop any more than an emulator boot can.
        started = await asyncio.to_thread(
            sandbox.Sandbox.start, body.get("width"), body.get("height"), body.get("dpi"))
    except (RuntimeError, TimeoutError) as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    _sandbox = started
    _cfg.serial = started.serial
    return JSONResponse({"serial": started.serial, "width": started.width,
                         "height": started.height, "dpi": started.dpi})


@app.post("/api/sandbox/stop")
async def api_sandbox_stop() -> JSONResponse:
    """Tear the container down. Its state is discarded — that is the point."""
    global _sandbox
    await asyncio.to_thread(sandbox.stop)
    if _cfg.serial == sandbox.SERIAL:
        _cfg.serial = None
    _sandbox = None
    return JSONResponse({"stopped": True})


@app.get("/api/state")
async def api_state() -> JSONResponse:
    """Everything the SPA needs at load: run summary, eval, screenshot index."""
    run_dir = _cfg.run_dir
    trace = _read_json(run_dir / "trace.json")
    ev = _read_json(run_dir / "eval.json")
    screens_dir = run_dir / "screens"
    screens = sorted(p.name for p in screens_dir.glob("*.png")) if screens_dir.exists() else []
    _attach_remediation(trace, run_dir)
    return JSONResponse(
        {
            "running": _run_started,
            "fixing": _fixing,
            "package": _cfg.package,
            "target_name": _target_name,
            "trace": trace,
            "eval": ev,
            "screens": screens,
            "fix_backend": _fix_backend_name(),
            # Frame filenames repeat every run, so the client tags their URLs
            # with this to keep one run's screenshots out of the next one's page.
            "run_id": _run_id(run_dir),
            # Every frame in a run shares the device's shape, so the UI can size
            # its phone bezel and thumbnails from the device actually driven
            # rather than from one hardcoded handset.
            "screen_aspect": _screen_aspect(screens, screens_dir),
        }
    )


def _screen_aspect(screens: list[str], screens_dir: Path) -> str | None:
    """"W/H" of this run's frames, read from the first one. None if unknowable."""
    if not screens:
        return None
    try:
        from PIL import Image
        with Image.open(screens_dir / screens[0]) as im:
            return f"{im.width}/{im.height}"
    except Exception:
        return None


def _run_id(run_dir: Path) -> str:
    """A token that changes whenever this run directory is rewritten."""
    t = run_dir / "trace.json"
    return str(int(t.stat().st_mtime)) if t.exists() else ""


def _fix_backend_name() -> str:
    """The coding agent that Tier 2 would use to write the patch (FIX_BACKEND)."""
    try:
        from .fix_backend import backend_name
        return backend_name()
    except Exception:
        return "prompt"


def _attach_remediation(trace, run_dir: Path) -> None:
    """Enrich each bug in ``trace`` with its remediation ladder artifacts.

    Tier 0 (``bug_NNN.md``) and Tier 1 (``bug_NNN.prompt.md``) are written for
    every bug by the reporter; Tier 2 (``bug_NNN.fix.json``) exists only once the
    autofix pipeline has run. Bugs and report files share a 1-based order.
    """
    if not trace or not isinstance(trace.get("bugs"), list):
        return
    reports = run_dir / "reports"
    for i, bug in enumerate(trace["bugs"], 1):
        base = reports / f"bug_{i:03d}"
        t1 = base.with_suffix(".prompt.md")
        t0 = reports / f"bug_{i:03d}.md"
        fix = reports / f"bug_{i:03d}.fix.json"
        bug["tier1_prompt"] = t1.read_text() if t1.exists() else None
        bug["tier0_report"] = t0.read_text() if t0.exists() else None
        bug["tier2_fix"] = _read_json(fix)


@app.get("/api/screen/{name}")
async def api_screen(name: str):
    """Serve a single run screenshot by basename (no path traversal)."""
    safe = Path(name).name
    path = _cfg.run_dir / "screens" / safe
    if not path.exists() or path.suffix != ".png":
        return JSONResponse({"error": "not found"}, status_code=404)
    # Every run writes the same names into the same directory, so this URL
    # returns different bytes after each one. With only an etag the browser is
    # free to guess a freshness lifetime and skip revalidating — which is how a
    # previous run's frame kept showing under this run's bug. no-cache still
    # allows a 304, it just forbids guessing.
    return FileResponse(path, media_type="image/png",
                        headers={"Cache-Control": "no-cache"})


@app.websocket("/ws")
async def ws(ws: WebSocket) -> None:
    await ws.accept()
    _clients.add(ws)
    try:
        while True:
            await ws.receive_text()  # keep the socket open; we only push
    except WebSocketDisconnect:
        _clients.discard(ws)


# SPA fallback: client-side routes (/app, /signin, …) resolve to the app shell on
# a hard refresh. Registered last so /api, /ws and /assets win first.
@app.get("/{full_path:path}")
async def spa(full_path: str):
    if full_path.startswith(("api/", "ws", "assets/")):
        return JSONResponse({"error": "not found"}, status_code=404)
    # Files vite copies from frontend/public land at the dist root, not under
    # /assets — favicon.svg is the one that matters. Without this they fall
    # through to the shell below and the browser gets HTML where it asked for
    # an image, so the tab icon silently never appears.
    candidate = (_DIST / full_path).resolve()
    if (full_path and candidate.is_file()
            and candidate.is_relative_to(_DIST.resolve())):  # no ../ escapes
        return FileResponse(candidate)
    return _serve_app()


def _read_json(path: Path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--steps", type=int, default=None)
    ap.add_argument("--port", type=int, default=8000)
    args = ap.parse_args()
    if args.steps is not None:
        _cfg.max_steps = args.steps
    print(f"Gremlin console on http://127.0.0.1:{args.port}")
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
