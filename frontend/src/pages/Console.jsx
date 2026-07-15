import { useEffect, useRef, useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import Mascot from "../lib/Mascot.jsx";
import { Home, Live, List, Bug, Bars, Bolt, Moon, LogOut, Chevron, Check, Screens, Book } from "../lib/icons.jsx";
import { useStore } from "../lib/useStore.js";
import { loadState, connectWS, startRun, loadTargets, selectTarget } from "../lib/store.js";
import { getUser, signOut, initials } from "../lib/auth.js";
import { formatDuration } from "../lib/notify.js";

const TITLES = { "/app": "Overview", "/app/live": "Live run", "/app/trace": "Trace", "/app/bugs": "Bugs", "/app/benchmark": "Benchmark", "/app/setup": "Setup" };

export default function Console() {
  const st = useStore();
  const nav = useNavigate();
  const loc = useLocation();
  const user = getUser();
  const [toast, setToast] = useState(null);
  const wasRunning = useRef(false);

  useEffect(() => { loadState(); loadTargets(); connectWS(); }, []);

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

  async function onStart() {
    try { await startRun(); nav("/app/live"); }
    catch (e) { setToast(e.message); setTimeout(() => setToast(null), 5000); }
  }
  function toggleTheme() {
    const next = document.documentElement.dataset.theme === "light" ? "dark" : "light";
    document.documentElement.dataset.theme = next;
    localStorage.setItem("gremlin-theme", next);
    setToast(null); setToast(`${next[0].toUpperCase() + next.slice(1)} theme`); setTimeout(() => setToast(null), 1500);
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
          <span className="logo"><Mascot size={38} float={false} /></span>
          <div><div className="brand-name">Gremlin<span className="dot">.</span></div><div className="brand-sub">agent console</div></div>
        </div>

        <div className="nav-label">Explore</div>
        {link("/app", <Home />, "Overview")}
        {link("/app/live", <Live />, "Live run", <span className={"pulse " + runState} style={{ marginLeft: "auto" }} />)}
        {link("/app/trace", <List />, "Trace", <span className="count">{steps}</span>)}
        {link("/app/bugs", <Bug />, "Bugs", <span className="count">{bugs}</span>)}
        <div className="nav-label">Evidence</div>
        {link("/app/benchmark", <Bars />, "Benchmark")}
        <div className="nav-label">Help</div>
        {link("/app/setup", <Book />, "Setup")}

        <div className="sidebar-foot">
          <div className="status-chip">
            <span className={"pulse " + runState} />
            <span className="label">{st.running ? "Running…" : st.done ? "Run complete" : "Idle"}</span>
            <span className="val">{st.package}</span>
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
          <TargetPicker targets={st.targets} selected={st.selected} disabled={st.running} onPick={selectTarget}
            defaultOpen={new URLSearchParams(loc.search).has("apps")} />
          <button className="btn btn-primary" onClick={onStart} disabled={st.running || (st.selected && !st.selected.installed)}>
            {st.running ? <><span className="pulse live" /> Running…</> : <><Bolt /> Start run</>}
          </button>
          <button className="icon-btn" onClick={toggleTheme} title="Toggle theme"><Moon /></button>
        </header>
        <main className="view"><div className="view-inner"><Outlet /></div></main>
      </div>

      {toast && <div className="toast"><Check /> {toast}</div>}
    </div>
  );
}

function TargetPicker({ targets, selected, disabled, onPick, defaultOpen = false }) {
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
    return <div className="tp-btn tp-empty" title="No apps detected (is a device connected?)"><Screens /> no app detected</div>;
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
            {projects.length > 0 && <div className="tp-head">Your Flutter projects</div>}
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
