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
  fixBackend: "prompt", // coding agent Tier 2 would use (FIX_BACKEND)
  summary: null, // set when a run finishes this session
  live: { steps: [], bugs: [], current: null, screenCount: 0 },
  targets: [],        // detected app projects (Flutter + React Native)
  projectsRoot: "",
  selected: null,     // the chosen target object
  // What we can run on. A phone on USB and a booted emulator are both just an
  // adb serial, so they live in one list and the developer picks either.
  devices: [],        // [{serial, state, emulator}]
  avds: [],           // AVD names we could boot
  serial: null,       // chosen adb serial; null = "whatever adb sees"
  emulatorProblem: null, // why we can't offer an emulator, if we can't
  booting: false,     // an AVD is starting up
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
      fixBackend: d.fix_backend || state.fixBackend,
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

export async function loadDevices() {
  try {
    const r = await fetch("/api/devices");
    const d = await r.json();
    set({
      devices: d.attached || [],
      avds: d.avds || [],
      serial: d.selected ?? null,
      emulatorProblem: d.emulator_problem ?? null,
    });
  } catch { /* no backend */ }
}

export async function selectDevice(serial) {
  set({ serial });
  try {
    await fetch("/api/devices/select", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ serial }),
    });
  } catch { /* keep the optimistic selection; loadDevices will reconcile */ }
  // The app list is per-device: a different device has different apps installed.
  await loadTargets();
}

export async function startEmulator(avd, { headless = false } = {}) {
  if (state.booting) return;
  set({ booting: true });
  try {
    const r = await fetch("/api/emulator/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ avd, headless }),
    });
    const d = await r.json();
    if (!r.ok) throw new Error(d.error || "the emulator did not start");
    set({ serial: d.serial });
    await loadDevices();
    // A freshly booted emulator has none of the developer's apps installed yet,
    // so re-read the target list rather than showing the old device's apps.
    await loadTargets();
    return d;
  } finally {
    set({ booting: false });
  }
}

export async function stopEmulator() {
  try {
    await fetch("/api/emulator/stop", { method: "POST" });
  } catch { /* already gone */ }
  await loadDevices();
  await loadTargets();
}

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
