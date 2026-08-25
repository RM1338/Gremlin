"""Guard rails on POST /api/fix — the console's Tier-2 trigger.

The fix itself needs a phone, a rebuild and minutes; what this checks is
everything around it: that the endpoint refuses a prompt-only backend, a busy
device, a missing run and an out-of-range bug number, and that a fix it does
accept writes its verdict under the bug's own number.

Run from the project root:  python -m tests.fix_endpoint_test
"""

import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ["FIX_BACKEND"] = "claude"  # read at import time by fix_backend

from fastapi.testclient import TestClient

from gremlin import dashboard
from gremlin.gates import GateResult

client = TestClient(dashboard.app)


def _write_trace(run_dir: Path, n_bugs: int, source_root: str = ".") -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "trace.json").write_text(json.dumps({"source_root": source_root, "bugs": [
        {"severity": "crash", "kind": f"kind-{i}", "log_line": "boom",
         "context": [], "screenshot": "shot.png", "step": i,
         "trace": [], "dedup_key": f"key-{i}"}
        for i in range(1, n_bugs + 1)
    ]}))


@dataclass
class _FakeOutcome:
    branch: str = "gremlin/fix-test"
    verified: bool = True
    note: str = "ok"
    guard_violations: list = field(default_factory=list)
    gates: list = field(default_factory=lambda: [GateResult("signal-gone", True, "gone")])


run_dir = Path("runs/_fix_endpoint_test")
dashboard._cfg.run_dir = run_dir

# --- no run yet: nothing to fix ---------------------------------------------
if (run_dir / "trace.json").exists():
    (run_dir / "trace.json").unlink()
assert client.post("/api/fix", json={"bug": 1}).status_code == 404

# --- the run says where its source is, and it has to still be there ---------
# The failure this encodes: a restarted console falls back to a default project
# path that does not exist, and the endpoint answered 500 with no explanation.
_write_trace(run_dir, 1, source_root="/nonexistent/project")
r = client.post("/api/fix", json={"bug": 1})
assert r.status_code == 400 and "not on disk" in r.json()["error"], r.json()

_write_trace(run_dir, 2)

# --- bug number has to name a bug in this run -------------------------------
for bad in ({}, {"bug": 0}, {"bug": 3}, {"bug": "1"}):
    r = client.post("/api/fix", json=bad)
    assert r.status_code == 400, (bad, r.status_code)

# --- a prompt-only backend edits nothing, so there is nothing to trigger -----
dashboard.backend_name = lambda: "prompt"
r = client.post("/api/fix", json={"bug": 1})
assert r.status_code == 400 and "prompt" in r.json()["error"], r.json()
dashboard.backend_name = lambda: "claude"

# --- the device is not shared with a run ------------------------------------
dashboard._run_started = True
assert client.post("/api/fix", json={"bug": 1}).status_code == 409
dashboard._run_started = False

# --- a dirty tree is refused in the response, not minutes later --------------
def _dirty(_cfg):
    raise dashboard.DirtyTreeError("working tree is dirty")

dashboard._require_clean_tree = _dirty
assert client.post("/api/fix", json={"bug": 1}).status_code == 409
dashboard._require_clean_tree = lambda _cfg: None

# --- accepted: runs off-thread, verdict lands under the bug's OWN number -----
phases: list[str] = []

def _fake_fix(cfg, bug, baseline, backend=None, on_phase=None):
    # Gate 3 replays these, so it needs the whole run's bugs — not just the one
    # being fixed, and not merely their keys.
    assert [b.dedup_key for b in baseline] == ["key-1", "key-2"], baseline
    on_phase("patching")
    return _FakeOutcome()

dashboard.fix_one = _fake_fix
# Under `with`, TestClient runs the lifespan — which is what gives _broadcast an
# event loop to push into. Without it the fan-out is a no-op and nothing arrives.
with TestClient(dashboard.app) as live, live.websocket_connect("/ws") as ws:
    r = live.post("/api/fix", json={"bug": 2})
    assert r.status_code == 200 and r.json()["bug"] == 2, r.json()
    for _ in range(2):
        phases.append(ws.receive_json()["phase"])
assert phases == ["patching", "done"], phases

verdict = json.loads((run_dir / "reports" / "bug_002.fix.json").read_text())
assert verdict["verified"] is True and verdict["gates"][0]["name"] == "signal-gone", verdict
assert not (run_dir / "reports" / "bug_001.fix.json").exists(), "wrote under the wrong bug"

# --- and the flag is released ------------------------------------------------
for _ in range(50):
    if not dashboard._fixing:
        break
    time.sleep(0.05)
assert dashboard._fixing is False, "the device stayed locked after the fix ended"

print("fix endpoint guard rails: OK")
