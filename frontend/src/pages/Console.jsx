import { useEffect, useRef, useState } from "react";
import Logo from "../lib/Logo.jsx";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { Home, Live, List, Bug, Bolt, Doc, Stop, LogOut, Chevron, Check, Screens, Book, Wrench } from "../lib/icons.jsx";
import { useStore } from "../lib/useStore.js";
import { loadState, connectWS, startRun, stopRun, loadTargets, selectTarget,
  loadDevices, selectDevice, startEmulator, stopEmulator,
  startSandbox, stopSandbox, setupSandbox } from "../lib/store.js";
import { getUser, signOut, initials } from "../lib/auth.js";
import { formatDuration } from "../lib/notify.js";

const TITLES = { "/app": "Overview", "/app/live": "Live run", "/app/trace": "Trace", "/app/bugs": "Bugs", "/app/setup": "Setup", "/app/settings": "Settings" };

export default function Console() {
  const st = useStore();
  const nav = useNavigate();
  const loc = useLocation();
  const user = getUser();
  const [toast, setToast] = useState(null);
  const wasRunning = useRef(false);

  useEffect(() => { loadState(); loadDevices(); loadTargets(); connectWS(); }, []);

  // Surface a toast when a run completes (in addition to the OS notification).
  useEffect(() => {
    if (wasRunning.current && !st.running && st.summary) {
      const s = st.summary;
      setToast(`Run complete — ${s.screens} screens, ${s.bugs} bug${s.bugs === 1 ? "" : "s"}, ${formatDuration(s.duration_sec || 0)}`);
      const t = setTimeout(() => setToast(null), 6000);
      return () => clearTimeout(t);
    }
    wasRunning.current = st.running;
  }, [st.running, st.summary]);

  const steps = st.trace?.steps ?? st.live.steps.length;
  const bugs = (st.trace?.bugs?.length ?? 0) || st.live.bugs.length;
  const runState = st.running ? "live" : st.done ? "done" : "idle";

  function flash(msg, ms = 5000) {
    setToast(msg);
    setTimeout(() => setToast(null), ms);
  }

  async function onStart() {
    try { await startRun(); nav("/app/live"); }
    catch (e) { flash(e.message); }
  }
  async function onStop() {
    // The run ends on the step boundary, not on the click, so say so — silence
    // here reads as a button that did nothing.
    try { await stopRun(); flash("Stopping after the current step…"); }
    catch (e) { flash(e.message); }
  }
  function out() { signOut(); nav("/"); }

  const link = (to, icon, label, extra) => (
    <NavLink to={to} end={to === "/app"} className={({ isActive }) => "nav-item" + (isActive ? " active" : "")}>
      {icon}<span>{label}</span>{extra}
    </NavLink>
  );

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <span className="logo"><Logo size={34} /></span>
          <div><div className="brand-name">Gremlin<span className="dot">.</span></div><div className="brand-sub">agent console</div></div>
        </div>

        <div className="nav-label">Explore</div>
        {link("/app", <Home />, "Overview")}
        {link("/app/live", <Live />, "Live run", <span className={"pulse " + runState} style={{ marginLeft: "auto" }} />)}
        {link("/app/trace", <List />, "Trace", <span className="count">{steps}</span>)}
        {link("/app/bugs", <Bug />, "Bugs", <span className="count">{bugs}</span>)}
        <div className="nav-label">Configure</div>
        {link("/app/settings", <Wrench />, "Settings")}
        <div className="nav-label">Evidence</div>
        <a className="nav-item" href="/benchmark" target="_blank" rel="noreferrer">
          <Doc /><span>Benchmark</span>
        </a>
        <div className="nav-label">Help</div>
        {link("/app/setup", <Book />, "Setup")}

        <div className="sidebar-foot">
          <div className="status-chip">
            <span className={"pulse " + runState} />
            <span className="label">{st.running ? "Running…" : st.done ? "Run complete" : "Idle"}</span>
            <span className="val">{st.selected?.package || st.package || "no app selected"}</span>
          </div>
          <div className="side-user">
            <div className="avatar">{initials(user)}</div>
            <div className="who"><div className="n">{user?.name}</div><div className="e">{user?.email}</div></div>
            <span className="out" title="Sign out" onClick={out}><LogOut /></span>
          </div>
        </div>
      </aside>

      <div className="main">
        <header className="topbar">
          <div className="crumb"><span>Gremlin</span><Chevron /><span className="here">{TITLES[loc.pathname] || "Overview"}</span></div>
          <div className="topbar-spacer" />
          <DevicePicker st={st} disabled={st.running} onNotify={flash} />
          <TargetPicker targets={st.targets} selected={st.selected} disabled={st.running} onPick={selectTarget}
            defaultOpen={new URLSearchParams(loc.search).has("apps")} root={st.projectsRoot} />
          {st.running ? (
            <button className="btn btn-danger" onClick={onStop} disabled={st.stopping}>
              {st.stopping ? <><span className="pulse live" /> Stopping…</> : <><Stop /> Stop run</>}
            </button>
          ) : (
            <button className="btn btn-primary" onClick={onStart} disabled={st.selected && !st.selected.installed}>
              <Bolt /> Start run
            </button>
          )}
        </header>
        <main className="view"><div className="view-inner"><Outlet /></div></main>
      </div>

      {toast && <div className="toast"><Check /> {toast}</div>}
    </div>
  );
}

/* Where the run happens: a phone on USB, or an emulator we boot on demand.
   Both are just an adb serial downstream, so they share one menu. */
function DevicePicker({ st, disabled, onNotify }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  useEffect(() => {
    const close = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);

  const { devices, avds, serial, emulatorProblem, booting, sandbox } = st;
  const current = devices.find((d) => d.serial === serial) || null;
  // An emulator we booted is stoppable; a phone on USB is not ours to kill.
  const runningEmu = devices.find((d) => d.emulator && d.serial === serial);
  // A phone that hasn't had its USB-debugging dialog accepted can't be driven.
  const unauthorized = devices.filter((d) => d.state === "unauthorized");

  const kind = (d) => d.sandbox ? "Sandbox" : d.emulator ? "Emulator" : "Phone (USB)";
  const label = booting
    || (current ? kind(current)
    : devices.length === 1 ? kind(devices[0])
    : devices.length === 0 ? "No device" : "Pick device");

  async function pickDevice(d) {
    setOpen(false);
    if (d.state === "unauthorized") {
      onNotify("That phone hasn't authorised USB debugging — accept the dialog on the device, then reconnect.");
      return;
    }
    await selectDevice(d.serial);
  }

  async function boot(avd) {
    setOpen(false);
    onNotify(`Booting ${avd} — a cold start takes a minute…`, 60000);
    try {
      await startEmulator(avd);
      onNotify(`Emulator ${avd} is ready.`);
    } catch (e) {
      onNotify(`Emulator did not start: ${e.message}`, 12000);
    }
  }

  async function bootSandbox() {
    setOpen(false);
    onNotify(sandbox?.note
      ? "Starting the sandbox — the first start downloads the image, so give it a few minutes…"
      : "Starting the sandbox — about a minute…", 300000);
    try {
      await startSandbox();
      onNotify("Sandbox ready — fresh Android, no phone involved.");
    } catch (e) {
      onNotify(`Sandbox did not start: ${e.message}`, 15000);
    }
  }

  async function fixSandbox() {
    setOpen(false);
    onNotify("Authorise the setup in your desktop's password dialog…", 120000);
    try {
      const d = await setupSandbox();
      onNotify(d.can_start
        ? "Host is set up — the sandbox can start now, and after a reboot too."
        : `Setup ran, but the sandbox still cannot start: ${d.problem}`, 12000);
    } catch (e) {
      onNotify(e.message, 15000);
    }
  }

  async function shutdownSandbox() {
    setOpen(false);
    await stopSandbox();
    onNotify("Sandbox stopped — its state is gone, which is the point.");
  }

  async function shutdown() {
    setOpen(false);
    await stopEmulator();
    onNotify("Emulator shut down.");
  }

  return (
    <div className="target-picker" ref={ref}>
      <button className="tp-btn" onClick={() => !disabled && !booting && setOpen((o) => !o)}
        disabled={disabled || booting} title="Choose a phone or an emulator to run on">
        <span className={"pulse " + (booting ? "live" : devices.length ? "live" : "idle")} />
        <span className="tp-name">{label}</span>
        <Chevron style={{ transform: "rotate(90deg)", width: 13, height: 13, opacity: 0.6 }} />
      </button>
      {open && (
        <div className="tp-menu">
          <div className="tp-scroll">
            <div className="tp-head">Connected</div>
            {devices.length === 0 && <div className="tp-none">Nothing attached — start a sandbox or boot an emulator below.</div>}
            {devices.map((d) => (
              <div key={d.serial} className={"tp-item" + (d.serial === serial ? " sel" : "")}
                onClick={() => pickDevice(d)}>
                <span className={"pulse " + (d.state === "device" ? "live" : "idle")} />
                <div className="tp-item-main">
                  <div className="tp-item-name">{kind(d)}</div>
                  <div className="tp-item-pkg">{d.serial}</div>
                </div>
                {d.state !== "device" && <span className="tp-badge">{d.state}</span>}
                {d.serial === serial && <Check style={{ width: 15, height: 15, color: "var(--brand)", flex: "none" }} />}
              </div>
            ))}

            <div className="tp-head">Sandbox</div>
            {sandbox?.running ? (
              <div className="tp-item" onClick={shutdownSandbox}>
                <span className="pulse live" />
                <div className="tp-item-main">
                  <div className="tp-item-name">Stop sandbox</div>
                  <div className="tp-item-pkg">{sandbox.serial}</div>
                </div>
              </div>
            ) : sandbox?.can_start ? (
              <div className="tp-item" onClick={bootSandbox}>
                <span className="pulse idle" />
                <div className="tp-item-main">
                  <div className="tp-item-name">Android container</div>
                  <div className="tp-item-pkg">{sandbox.note || "no phone needed · fresh every start"}</div>
                </div>
              </div>
            ) : sandbox?.can_setup ? (
              /* The blocker is one this machine can fix, so offer the fix rather
                 than the command. pkexec puts the password prompt in the
                 desktop's own dialog — nobody has to open a terminal. */
              <div className="tp-item" onClick={fixSandbox}>
                <span className="pulse idle" />
                <div className="tp-item-main">
                  <div className="tp-item-name">Set up this computer</div>
                  <div className="tp-item-pkg">asks for your password once · survives reboots</div>
                </div>
              </div>
            ) : (
              <div className="tp-none">
                {sandbox?.problem || "Checking for Docker…"}
                {sandbox?.problem && sandbox?.setup_cmd &&
                  <div className="tp-cmd">{sandbox.setup_cmd}</div>}
              </div>
            )}

            <div className="tp-head">Emulators</div>
            {emulatorProblem
              ? <div className="tp-none">{emulatorProblem}</div>
              : avds.map((avd) => (
                  <div key={avd} className="tp-item" onClick={() => boot(avd)}>
                    <span className="pulse idle" />
                    <div className="tp-item-main">
                      <div className="tp-item-name">{avd}</div>
                      <div className="tp-item-pkg">{runningEmu ? "boot another" : "boot this"}</div>
                    </div>
                  </div>
                ))}
            {runningEmu && (
              <div className="tp-item" onClick={shutdown}>
                <span className="pulse idle" />
                <div className="tp-item-main"><div className="tp-item-name">Shut down emulator</div></div>
              </div>
            )}
            {unauthorized.length > 0 && (
              <div className="tp-none">
                {unauthorized.length} phone(s) awaiting USB-debugging authorisation — accept the dialog on the device.
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function TargetPicker({ targets, selected, disabled, onPick, defaultOpen = false, root }) {
  const [open, setOpen] = useState(defaultOpen);
  const [q, setQ] = useState("");
  const ref = useRef(null);
  useEffect(() => {
    const close = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);
  useEffect(() => { if (!open) setQ(""); }, [open]);

  if (!targets || targets.length === 0) {
    // Say where we looked. "No apps detected" on its own sent someone hunting a
    // device problem when the real answer was that GREMLIN_PROJECTS_ROOT pointed
    // at a directory the fixtures had been moved out of — a scan that found
    // nothing, reported as if nothing existed.
    return (
      <div className="tp-btn tp-empty"
           title={`No app projects under ${root || "the projects root"}, and nothing installed on the device. `
                  + `Change GREMLIN_PROJECTS_ROOT in Settings, or install an app on the device.`}>
        <Screens /> no app detected
      </div>
    );
  }

  const needle = q.trim().toLowerCase();
  const match = (t) => !needle || t.name.toLowerCase().includes(needle) || t.package.toLowerCase().includes(needle);
  const projects = targets.filter((t) => t.source === "project" && match(t));
  const devices = targets.filter((t) => t.source === "device" && match(t));

  const pick = (t) => { onPick(t); setOpen(false); };
  const item = (t) => (
    <div key={t.package} className={"tp-item" + (selected?.package === t.package ? " sel" : "")} onClick={() => pick(t)}>
      <span className={"pulse " + (t.installed ? "live" : "idle")} />
      <div className="tp-item-main">
        <div className="tp-item-name">{t.name}</div>
        {t.name !== t.package && <div className="tp-item-pkg">{t.package}</div>}
      </div>
      {t.platform_label && <span className="tp-tag">{t.platform_label}</span>}
      {t.source === "device" && <span className="tp-tag">explore-only</span>}
      {!t.installed && <span className="tp-badge">not installed</span>}
      {selected?.package === t.package && <Check style={{ width: 15, height: 15, color: "var(--brand)", flex: "none" }} />}
    </div>
  );

  return (
    <div className="target-picker" ref={ref}>
      <button className="tp-btn" onClick={() => !disabled && setOpen((o) => !o)} disabled={disabled}>
        <span className={"pulse " + (selected?.installed ? "live" : "idle")} />
        <span className="tp-name">{selected?.name || "Select app"}</span>
        <Chevron style={{ transform: "rotate(90deg)", width: 13, height: 13, opacity: 0.6 }} />
      </button>
      {open && (
        <div className="tp-menu">
          <input className="tp-search" autoFocus placeholder="Search apps…" value={q} onChange={(e) => setQ(e.target.value)} />
          <div className="tp-scroll">
            {projects.length > 0 && <div className="tp-head">Your app projects</div>}
            {projects.map(item)}
            {devices.length > 0 && <div className="tp-head">Installed on device</div>}
            {devices.map(item)}
            {projects.length === 0 && devices.length === 0 && <div className="tp-none">No apps match "{q}"</div>}
          </div>
        </div>
      )}
    </div>
  );
}
