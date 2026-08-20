import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import Mascot from "../lib/Mascot.jsx";
import { Bolt, Screens, Steps, Bug, Check } from "../lib/icons.jsx";
import { CountUp, Spark, Lightbox, screenUrl } from "../lib/ui.jsx";
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

  const [zoom, setZoom] = useState(null);
  const shots = (st.screens || []).filter((n) => n.startsWith("step_")).sort();
  const sum = t.summary || {};

  async function start() { try { await startRun(); nav("/app/live"); } catch {} }

  return (
    <>
      <div className="page-body">
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
        </div>
        <div className="hero-mascot"><Mascot size={132} state={mascotState(st)} className="hero-nib" /></div>
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
          <p className="note" style={{ marginTop: 12, fontSize: 12.5 }}>Every action is recorded to a <code>trace.json</code> the replayer re-executes verbatim, so a bug found at step 19 is reproducible from launch.</p>
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
              {/* The action mix says what KIND of run it was — thirty taps and
                  nothing else is a different run from a mix of four verbs, and
                  the totals above cannot show that. */}
              <VerbMix verbs={sum.verbs} />
              <div className={"pill " + (bugs ? "" : "brand")} style={{ marginTop: 12 }}>
                {bugs ? `${bugs} to triage` : <><Check /> clean run</>}
              </div>
            </>
          ) : <p className="note">No run yet. Press <b>Start a run</b> to watch Gremlin explore.</p>}
        </div>

        <div className="card">
          <div className="section-head"><h3>This machine</h3><a onClick={() => nav("/app/setup")}>Setup →</a></div>
          <KV k="Device" v={st.serial || st.devices?.[0]?.serial || "none attached"} />
          <KV k="Target" v={st.selected?.name || t.package || "—"} />
          <KV k="Toolkit" v={st.selected?.platform_label || "—"} />
          <KV k="Tier-2 backend" v={st.fixBackend} />
          <KV k="Coverage" v={sum.controls_tapped != null
            ? `${sum.controls_tapped} of ${sum.controls_seen} controls` : "—"} />
        </div>
      </div>

      {/* Whatever height is left goes to the frames the last run actually saw.
          It is the one thing on this page that is evidence rather than a
          summary, and it collapses to nothing on a short window. */}
      {shots.length > 0 && (
        <div className="card ov-screens">
          <div className="section-head">
            <h3>Screens reached</h3>
            <a onClick={() => nav("/app/trace")}>View the trace →</a>
          </div>
          <div className="ov-strip">
            {shots.map((n, i) => (
              <div className="ov-shot" key={n} title={`step ${i + 1} — click to enlarge`}
                   onClick={() => setZoom({ src: screenUrl(n), cap: `step ${String(i + 1).padStart(3, "0")}` })}>
                <img loading="lazy" src={screenUrl(n)} alt="" />
              </div>
            ))}
          </div>
        </div>
      )}
      <Lightbox src={zoom?.src} caption={zoom?.cap} onClose={() => setZoom(null)} />
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
function KV({ k, v }) {
  return <div className="ov-kv"><span>{k}</span><span className="v">{v}</span></div>;
}

/* The same four verbs the Live summary shows, as one bar. */
function VerbMix({ verbs }) {
  const order = ["tap", "type", "scroll", "back"];
  const total = Object.values(verbs || {}).reduce((a, b) => a + b, 0);
  if (!total) return null;
  return (
    <>
      <div className="verbbar" style={{ marginTop: 14 }}>
        {order.filter((v) => verbs[v]).map((v) => (
          <span key={v} className={v} style={{ width: `${(verbs[v] / total) * 100}%` }} title={`${v}: ${verbs[v]}`} />
        ))}
      </div>
      <div className="chips" style={{ marginTop: 8 }}>
        {order.filter((v) => verbs[v]).map((v) => <span className="chip" key={v}>{v} · {verbs[v]}</span>)}
      </div>
    </>
  );
}

function Node({ n, t, d }) { return <div className="pl-node"><div className="n">{n}</div><div className="t">{t}</div><div className="d">{d}</div></div>; }

