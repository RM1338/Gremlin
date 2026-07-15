"""Gremlin console — a modern, multi-page web app for watching the agent work.

Not a single dashboard but a small site: an Overview landing page, a Live run
view that streams the agent's observe→decide→act→check loop over a WebSocket, a
Trace timeline, a Bugs gallery, and a Gremlin-vs-monkey Benchmark. The chrome is
a static SPA (``web/``) served here; live data arrives over ``/ws`` and the
finished artifacts (``trace.json``, ``eval.json``, screenshots) over ``/api``.

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

_WEB = Path(__file__).parent / "web"
# The React console, once built with `cd frontend && npm run build`.
_DIST = Path(__file__).parent.parent / "frontend" / "dist"

_clients: set[WebSocket] = set()
_loop: asyncio.AbstractEventLoop | None = None
_run_started = False
_cfg = Config()
_target_name: str | None = None  # friendly name of the selected app, for the UI


@asynccontextmanager
async def _lifespan(app: FastAPI):
    # Capture the running loop so the explorer thread can push to websockets.
    global _loop
    _loop = asyncio.get_running_loop()
    yield


app = FastAPI(lifespan=_lifespan)
app.mount("/static", StaticFiles(directory=_WEB), name="static")
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
        try:
            explorer = Explorer(_cfg, on_event=_on_event)
            bugs = explorer.run()
            from .reporter import write_reports

            if bugs:
                write_reports(bugs, _cfg)
        finally:
            global _run_started
            _run_started = False

    threading.Thread(target=worker, daemon=True).start()


# ---- pages -----------------------------------------------------------------
# Legacy one-file UI, used only if the React app hasn't been built yet.
_SHELL = """<!doctype html><html lang=en><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>Gremlin — agent console</title>
<link rel=preconnect href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel=stylesheet>
<link rel=stylesheet href="/static/styles.css">
<link rel=icon href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Ctext y='.9em' font-size='90'%3E%F0%9F%91%BE%3C/text%3E%3C/svg%3E">
</head><body>
__BODY__
<script src="/static/app.js"></script>
</body></html>"""


def _serve_app() -> HTMLResponse:
    """Serve the built React SPA if present, else the legacy one-file UI."""
    if (_DIST / "index.html").exists():
        return HTMLResponse((_DIST / "index.html").read_text())
    body = (_WEB / "index.html").read_text()
    return HTMLResponse(_SHELL.replace("__BODY__", body))


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
    _start_run()
    return {"started": True, "package": _cfg.package, "activity": _cfg.activity}


@app.get("/api/targets")
async def api_targets() -> JSONResponse:
    """Flutter projects (full capability) plus installed apps, flagged by source."""
    targets = all_targets(PROJECTS_ROOT, dev=Device(_cfg.serial))
    return JSONResponse({
        "projects_root": str(PROJECTS_ROOT),
        "targets": [t.to_dict() for t in targets],
        "selected": _cfg.package,
    })


@app.get("/api/state")
async def api_state() -> JSONResponse:
    """Everything the SPA needs at load: run summary, eval, screenshot index."""
    run_dir = _cfg.run_dir
    trace = _read_json(run_dir / "trace.json")
    ev = _read_json(run_dir / "eval.json")
    screens_dir = run_dir / "screens"
    screens = sorted(p.name for p in screens_dir.glob("*.png")) if screens_dir.exists() else []
    return JSONResponse(
        {
            "running": _run_started,
            "package": _cfg.package,
            "target_name": _target_name,
            "trace": trace,
            "eval": ev,
            "screens": screens,
        }
    )


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
# a hard refresh. Registered last so /api, /ws, /assets, /static win first.
@app.get("/{full_path:path}")
async def spa(full_path: str):
    if full_path.startswith(("api/", "ws", "assets/", "static/")):
        return JSONResponse({"error": "not found"}, status_code=404)
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
