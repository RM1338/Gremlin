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
  // A third way to get a device, for a developer with neither phone nor AVD:
  // {serial, running, can_start, problem, note}. null until /api/devices answers.
  sandbox: null,
  booting: null,      // label of the device coming up ("Booting emulator…"), or null
  stopping: false,    // a stop was requested; the run ends after the current step
  // A Tier-2 fix in flight: which bug (1-based, 0 when a refresh found one already
  // running), and the stage it is in. Minutes long, so the stage is the progress.
  fixingBug: null,
  fixPhase: "",
  fixError: null,     // {bug, msg} — why THAT bug's fix could not be started
};

const listeners = new Set();
const set = (patch) => { state = { ...state, ...patch }; listeners.forEach((l) => l()); };

export function subscribe(cb) { listeners.add(cb); return () => listeners.delete(cb); }
export function getSnapshot() { return state; }

// `eval.json` has had two shapes: a bare array of rows, and — since the
// benchmark grew per-target output directories — `{results: [...]}`. Accept
// both, so a run directory written by either version still renders.
export function evalRows(raw) {
  if (!raw) return null;
  const rows = Array.isArray(raw) ? raw : raw.results;
  return Array.isArray(rows) && rows.length ? rows : null;
}

// Arms by role. The vision arm was simply "gremlin" before the no-model
// ablation existed, so both names resolve to it.
export function evalArms(raw) {
  const rows = evalRows(raw);
  if (!rows) return null;
  const by = (n) => rows.find((e) => e.explorer === n) || null;
  return {
    rows,
    vision: by("gremlin-vision") || by("gremlin"),
    coverage: by("gremlin-coverage"),
    monkey: by("monkey"),
  };
}

export async function loadState() {
  try {
    const r = await fetch("/api/state");
    if (!r.ok) throw new Error("bad status");
    const d = await r.json();
    set({
      loading: false, running: d.running, package: d.package || state.package,
      trace: d.trace, evalData: d.eval, screens: d.screens || [],
      fixBackend: d.fix_backend || state.fixBackend,
      // A fix survives a page reload; the server knows, this tab may not.
      fixingBug: d.fixing ? (state.fixingBug ?? 0) : null,
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
      sandbox: d.sandbox ?? null,
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
  set({ booting: "Booting emulator…" });
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
    set({ booting: null });
  }
}

/* Boot a containerised Android instance — the option for a developer with no
   phone and no AVD. Same shape as startEmulator on purpose: it ends with an adb
   serial, and nothing downstream can tell the difference. */
export async function startSandbox({ width, height, dpi } = {}) {
  if (state.booting) return;
  set({ booting: "Starting sandbox…" });
  try {
    const r = await fetch("/api/sandbox/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ width, height, dpi }),
    });
    const d = await r.json();
    if (!r.ok) throw new Error(d.error || "the sandbox did not start");
    set({ serial: d.serial });
    await loadDevices();
    // A fresh container has no apps installed at all, so the old device's list
    // is not merely stale — it is wrong.
    await loadTargets();
    return d;
  } finally {
    set({ booting: null });
  }
}

export async function stopSandbox() {
  try {
    await fetch("/api/sandbox/stop", { method: "POST" });
  } catch { /* no backend */ }
  await loadDevices();
  await loadTargets();
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
  if (state.fixingBug !== null) throw new Error("A Tier-2 fix is using the device. Wait for it to finish.");
  const t = target || state.selected;
  // Ask for notification permission up front, while we have a user gesture.
  if ("Notification" in window && Notification.permission === "default") {
    try { await Notification.requestPermission(); } catch {}
  }
  set({ running: true, done: false, stopping: false, summary: null, selected: t || state.selected, live: { steps: [], bugs: [], current: null, screenCount: 0 } });
  try {
    await fetch("/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(t || {}),
    });
  } catch { set({ running: false }); throw new Error("Could not reach the runner. Is `python -m gremlin.dashboard` running?"); }
}

/* Ask the runner to wind the current run down. The run does NOT end here: the
   explorer finishes the step it is in, then emits `done` over the websocket,
   which is what actually clears `running`. Clearing it optimistically would
   show "Start run" while the phone was still being driven. */
export async function stopRun() {
  if (!state.running || state.stopping) return;
  set({ stopping: true });
  try {
    const r = await fetch("/api/stop", { method: "POST" });
    if (!r.ok) throw new Error((await r.json()).error || "could not stop the run");
  } catch (e) {
    set({ stopping: false });
    throw e;
  }
}

/* Trigger the Tier-2 autofix for one bug, by its 1-based number in the run.
   Like stopRun, the interesting part does not happen here: the server patches,
   rebuilds, replays and re-explores for minutes, reporting each stage over the
   websocket. This call only gets a yes or a reason why not. */
export async function startFix(n) {
  if (state.fixingBug !== null || state.running) return;
  set({ fixingBug: n, fixPhase: "starting", fixError: null });
  try {
    const r = await fetch("/api/fix", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ bug: n }),
    });
    if (!r.ok) throw new Error((await r.json()).error || "could not start the fix");
  } catch (e) {
    set({ fixingBug: null, fixPhase: "", fixError: { bug: n, msg: e.message } });
  }
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
    else if (m.event === "fix") onFix(m);
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
async function onFix(m) {
  if (m.phase !== "done") { set({ fixingBug: m.bug, fixPhase: m.phase }); return; }
  set({ fixingBug: null, fixPhase: "" });
  // The verdict is already on disk as bug_NNN.fix.json; reloading is what puts
  // the gate ladder on the card, and keeps one source of truth for it.
  await loadState();
}

async function onDone(m) {
  set({ running: false, done: true, stopping: false, summary: m });
  notifyRunComplete(m);
  await loadState();
}
