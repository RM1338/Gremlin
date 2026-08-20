import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import Mascot from "../lib/Mascot.jsx";
import { Bolt, Screens, Steps, Bug } from "../lib/icons.jsx";
import { CountUp, Spark } from "../lib/ui.jsx";
import { useStore } from "../lib/useStore.js";
import { startRun, evalArms } from "../lib/store.js";
import { mascotState, mascotLine } from "../lib/mascotState.js";

const TYPES = [
  "reaching Settings → Profile → Theme…",
  "10 distinct screens, 0 crashes",
  "tap 'Schedule' — an unvisited section",
  "draining logcat for the app pid…",
];

export default function Overview() {
  const st = useStore();
  const nav = useNavigate();
  const t = st.trace || {};
  const steps = t.steps ?? 0, screens = t.distinct_screens ?? 0, bugs = t.bugs?.length ?? 0;
  const arms = evalArms(st.evalData);
  const g = arms?.vision, m = arms?.monkey;
  const mult = g && m && m.distinct_screens ? Math.round(g.distinct_screens / m.distinct_screens) : null;

  async function start() { try { await startRun(); nav("/app/live"); } catch {} }

  return (
    <>
      <section className="hero">
        <div className="hero-grid" />
        <div className="hero-content">
          <div className="eyebrow"><Bolt /> Autonomous UI-testing agent</div>
          <h1>Gremlin explores your app<br /> and <em>breaks it on purpose.</em></h1>
          <p>A vision-driven agent that drives a real device — observe, decide, act, check — reaching screens a random monkey never will, and turning every crash into a reproducible trace.</p>
          <div className="hero-cta">
            <button className="btn btn-primary" onClick={start} disabled={st.running}><Bolt /> {st.running ? "Running…" : "Start a run"}</button>
            <button className="btn btn-ghost" onClick={() => nav("/app/benchmark")}>See the benchmark →</button>
          </div>
          <Terminal />
        </div>
        <div className="hero-mascot"><Mascot size={190} state={mascotState(st)} float /></div>
      </section>

      <div className="stat-grid">
        <StatTile icon={<Screens />} k="Distinct screens" v={screens} foot={m ? <>vs <b>{m.distinct_screens}</b> for random monkey</> : <>no baseline run yet</>} />
        <StatTile icon={<Steps />} k="Actions taken" v={steps} foot="grounded on a11y elements" />
        <StatTile icon={<Bug />} k="Bugs found" v={bugs} foot={bugs ? "with repro traces" : "clean baseline run"} />
        <StatTile icon={<Bolt />} k="Coverage lift" v={mult} suffix="×" foot="vs the monkey baseline" />
      </div>

      <div className="grid-2">
        <div className="card">
          <div className="section-head"><h3>The loop</h3><a onClick={() => nav("/app/trace")}>View last trace →</a></div>
          <div className="pipeline">
            <Node n="01" t="Observe" d="screenshot + a11y tree" /><span className="pl-arrow">→</span>
            <Node n="02" t="Decide" d="Gemini picks a verb" /><span className="pl-arrow">→</span>
            <Node n="03" t="Act" d="tap · type · scroll · back" /><span className="pl-arrow">→</span>
            <Node n="04" t="Check" d="oracle drains logcat" />
          </div>
          <p className="note" style={{ marginTop: 18 }}>Every action is recorded to a <code>trace.json</code> the replayer re-executes verbatim, so a bug found at step 19 is reproducible from launch.</p>
        </div>
        <div className="card">
          <div className="section-head"><h3>Latest run</h3><a onClick={() => nav("/app/live")}>Watch live →</a></div>
          {st.trace ? (
            <>
              <div className="live-stats">
                <div className="live-stat"><div className="v">{steps}</div><div className="k">Steps</div></div>
                <div className="live-stat"><div className="v">{screens}</div><div className="k">Screens</div></div>
                <div className="live-stat"><div className="v">{bugs}</div><div className="k">Bugs</div></div>
              </div>
              <div className={"pill " + (bugs ? "" : "brand")} style={{ marginTop: 14 }}>{bugs ? `${bugs} to triage` : "✓ clean run"}</div>
            </>
          ) : <p className="note">No run yet. Press <b>Start a run</b> to watch Gremlin explore.</p>}
        </div>
      </div>
    </>
  );
}

function StatTile({ icon, k, v, foot, suffix }) {
  return (
    <div className="stat">
      <div className="k">{icon}{k}</div>
      <div className="v">{v == null ? "—" : <CountUp to={v} suffix={suffix || ""} />}</div>
      <div className="foot">{foot}</div>
      <Spark />
    </div>
  );
}
function Node({ n, t, d }) { return <div className="pl-node"><div className="n">{n}</div><div className="t">{t}</div><div className="d">{d}</div></div>; }

function Terminal() {
  const [txt, setTxt] = useState("");
  useEffect(() => {
    let li = 0, ci = 0, del = false, timer;
    const run = () => {
      const line = TYPES[li];
      setTxt(line.slice(0, ci));
      if (!del && ci < line.length) { ci++; timer = setTimeout(run, 32); }
      else if (!del) { del = true; timer = setTimeout(run, 1600); }
      else if (ci > 0) { ci--; timer = setTimeout(run, 14); }
      else { del = false; li = (li + 1) % TYPES.length; timer = setTimeout(run, 300); }
    };
    run();
    return () => clearTimeout(timer);
  }, []);
  return (
    <div style={{ marginTop: 24, borderRadius: 12, border: "1px solid var(--hair)", background: "rgba(0,0,0,.35)", overflow: "hidden", font: "12.5px/1.7 var(--mono)" }}>
      <div style={{ display: "flex", gap: 6, padding: "9px 12px", borderBottom: "1px solid var(--hair)" }}>
        <i style={{ width: 10, height: 10, borderRadius: "50%", background: "#ff5f57" }} />
        <i style={{ width: 10, height: 10, borderRadius: "50%", background: "#febc2e" }} />
        <i style={{ width: 10, height: 10, borderRadius: "50%", background: "#28c840" }} />
      </div>
      <div style={{ padding: "12px 14px", color: "var(--ink-dim)", minHeight: 44 }}>
        <span style={{ color: "var(--brand)" }}>gremlin ~</span> {txt}
        <span style={{ display: "inline-block", width: 8, height: 15, background: "var(--brand)", verticalAlign: -2, marginLeft: 2, animation: "blinkeye 1s step-end infinite" }} />
      </div>
    </div>
  );
}
