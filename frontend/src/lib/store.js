/* Central store for run data + the live WebSocket. One module-level state object,
   exposed to React via useSyncExternalStore. Also owns run-complete notifications. */

import { notifyRunComplete } from "./notify.js";

let state = {
  loading: true,
  running: false,
  done: false,
  package: "com.scribe.scribe",
  trace: null,
  evalData: null,
  screens: [],
  summary: null, // set when a run finishes this session
  live: { steps: [], bugs: [], current: null, screenCount: 0 },
  targets: [],        // detected Flutter projects
  projectsRoot: "",
  selected: null,     // the chosen target object
};

const listeners = new Set();
const set = (patch) => { state = { ...state, ...patch }; listeners.forEach((l) => l()); };

export function subscribe(cb) { listeners.add(cb); return () => listeners.delete(cb); }
export function getSnapshot() { return state; }

export async function loadState() {
  try {
    const r = await fetch("/api/state");
    if (!r.ok) throw new Error("bad status");
    const d = await r.json();
    set({
      loading: false, running: d.running, package: d.package || state.package,
      trace: d.trace, evalData: d.eval, screens: d.screens || [],
    });
  } catch {
    // Static deploy (no backend): fall back to a bundled recorded run if present.
    try {
      const r = await fetch("/sample-state.json");
      const d = await r.json();
      set({ loading: false, running: false, trace: d.trace, evalData: d.eval, screens: d.screens || [], package: d.package || state.package });
    } catch { set({ loading: false }); }
  }
}

export async function loadTargets() {
  try {
    const r = await fetch("/api/targets");
    const d = await r.json();
    const targets = d.targets || [];
    // Keep the current selection if still present, else the server's selected
    // package, else an installed Flutter project, else any installed app.
    const cur = state.selected && targets.find((t) => t.package === state.selected.package);
    const selected = cur
      || targets.find((t) => t.package === d.selected)
      || targets.find((t) => t.source === "project" && t.installed)
      || targets.find((t) => t.installed)
      || targets[0] || null;
    set({ targets, projectsRoot: d.projects_root, selected });
  } catch { /* no backend / no device */ }
}

export function selectTarget(t) { set({ selected: t }); }

export async function startRun(target) {
  if (state.running) return;
  const t = target || state.selected;
  // Ask for notification permission up front, while we have a user gesture.
  if ("Notification" in window && Notification.permission === "default") {
    try { await Notification.requestPermission(); } catch {}
  }
  set({ running: true, done: false, summary: null, selected: t || state.selected, live: { steps: [], bugs: [], current: null, screenCount: 0 } });
  try {
    await fetch("/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(t || {}),
    });
  } catch { set({ running: false }); throw new Error("Could not reach the runner. Is `python -m gremlin.dashboard` running?"); }
}

let ws = null;
export function connectWS() {
  if (ws) return;
  const proto = location.protocol === "https:" ? "wss" : "ws";
  ws = new WebSocket(`${proto}://${location.host}/ws`);
  ws.onmessage = (e) => {
    const m = JSON.parse(e.data);
    if (m.event === "step") onStep(m);
    else if (m.event === "bug") onBug(m);
    else if (m.event === "done") onDone(m);
  };
  ws.onclose = () => { ws = null; setTimeout(connectWS, 1500); };
  ws.onerror = () => { try { ws.close(); } catch {} };
}

function onStep(m) {
  const live = { ...state.live, current: m, steps: [...state.live.steps, m], screenCount: m.distinct_screens };
  set({ running: true, live });
}
function onBug(m) {
  set({ live: { ...state.live, bugs: [...state.live.bugs, m] } });
}
async function onDone(m) {
  set({ running: false, done: true, summary: m });
  notifyRunComplete(m);
  await loadState();
}
