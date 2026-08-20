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
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import Config, PROJECTS_ROOT
from .device import Device
from .explorer import Explorer
from .targets import all_targets
from . import emulator, platforms

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
# The Explorer of the run in flight, so /api/stop can ask it to wind down. None
# whenever nothing is running.
_explorer: "Explorer | None" = None


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
    if _run_started:
        return
    _run_started = True

    def worker() -> None:
        global _explorer
        try:
            _explorer = Explorer(_cfg, on_event=_on_event)
            bugs = _explorer.run()
            from .reporter import write_reports

            if bugs:
                write_reports(bugs, _cfg)
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
async def start(request: Request) -> dict:
    """Start a run. An optional JSON body selects which app to test:
    {"name","package","activity","source_root"}."""
    global _target_name
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
    _start_run()
    return {"started": True, "package": _cfg.package, "activity": _cfg.activity,
            "platform": _cfg.platform}


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
    attached = [{"serial": s, "state": st, "emulator": emulator.is_emulator(s)}
                for s, st in emulator._adb_devices()]
    return JSONResponse({
        "attached": attached,
        "avds": list(status.avds),
        "running_emulators": emulator.running_emulators(),
        "selected": _cfg.serial,
        # Non-null when we cannot offer emulator boot, and says how to fix it.
        "emulator_problem": status.problem,
    })


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
            "package": _cfg.package,
            "target_name": _target_name,
            "trace": trace,
            "eval": ev,
            "screens": screens,
            "fix_backend": _fix_backend_name(),
        }
    )


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
    return FileResponse(path, media_type="image/png")


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
