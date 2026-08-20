import Mascot from "../lib/Mascot.jsx";
import { mascotState, mascotLine } from "../lib/mascotState.js";
import { useNavigate } from "react-router-dom";
import { Bolt, Check, Screens, Steps, Bug, Clock } from "../lib/icons.jsx";
import { pad3, sevClass } from "../lib/ui.jsx";
import { useStore } from "../lib/useStore.js";
import { formatDuration } from "../lib/notify.js";

export default function Live() {
  const st = useStore();
  const cur = st.live.current;
  const done = st.done && st.summary;

  return (
    <>
      <div className="page-head tight" style={{ display: "flex", alignItems: "center", gap: 14 }}>
        <Mascot size={78} state={mascotState(st)} />
        <div style={{ flex: 1 }}>
          <h1 className="page-title">Live run</h1>
          <p className="page-desc">{mascotLine(mascotState(st), st.live.bugs.length)}</p>
        </div>
      </div>

      <div className="page-body">
      {/* Once the run is over the phone is a still of a screen nobody is driving
          any more, so the summary takes that column and gets the wide side of
          the grid. Stacking it ON TOP pushed the action stream off the bottom of
          a page that does not scroll — the log measured 2px tall. */}
      <div className={"live" + (done ? " done" : "")}>
        <div className="live-main">
          {done ? <Summary s={st.summary} /> : (
          <div className="phone"><div className="phone-screen">
            {cur?.frame
              ? <img src={`data:image/png;base64,${cur.frame}`} alt="device" />
              : <div className="phone-empty">{st.running ? <><div className="spinner" />waiting for first frame…</> : "press Start run to begin"}</div>}
          </div></div>
          )}
        </div>

        <div className="live-right">
          <div className="intent-card">
            <div className="k"><Bolt /> {done ? "Last intention" : "Current intention"}</div>
            <div className="v">{cur?.intention || "—"}</div>
            <div className="meta">
              {cur ? <><span>step {cur.step}</span><span>·</span><span>{cur.screen}</span>{cur.is_new && <span className="new-badge">· new screen ✦</span>}</> : "idle"}
            </div>
          </div>

          <div className="live-stats">
            <div className="live-stat"><div className="v">{st.live.screenCount}</div><div className="k">Screens</div></div>
            <div className="live-stat"><div className="v">{st.live.steps.length}</div><div className="k">Step</div></div>
            <div className="live-stat"><div className="v">{st.live.bugs.length}</div><div className="k">Bugs</div></div>
          </div>

          <div className="log">
            <div className="log-head"><span className={"pulse " + (st.running ? "live" : "idle")} /> action stream</div>
            <div className="log-body">
              {st.live.steps.length === 0 && <div className="log-line"><span className="txt" style={{ color: "var(--faint)" }}>no actions yet</span></div>}
              {[...st.live.steps].reverse().map((s, i) => (
                <div className="log-line" key={i}>
                  <span className="step">{pad3(s.step)}</span>
                  <span className={"verb " + s.verb}>{s.verb}</span>
                  <span className="txt">{s.screen}{s.is_new && <span className="new-badge"> ✦ new</span>} — {s.intention}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Only while the run is going. Afterwards the summary beside this
              already says how many there were and links to triage them, and two
              cards competing for the last 200px is what clipped the second one
              in half. */}
          {st.running && st.live.bugs.length > 0 && (
            <div className="live-bugs">
              {[...st.live.bugs].reverse().slice(0, 2).map((b, i) => (
                <div className={"bug-card " + sevClass(b.severity)} key={i}>
                  <div className="sev"><Bug /> {b.severity}</div>
                  <div className="t">{b.title}</div><div className="s">found at step {b.step}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
      </div>
    </>
  );
}

function Summary({ s }) {
  const nav = useNavigate();
  const verbs = s.verbs || {};
  const total = Object.values(verbs).reduce((a, b) => a + b, 0) || 1;
  const order = ["tap", "type", "scroll", "back"];
  return (
    <div className="summary">
      <div className="top">
        <div className="badge">{s.bugs ? <Bug /> : <Check />}</div>
        <div>
          <h3>{s.ended_early ? "Run ended early" : "Run complete"}</h3>
          <div className="s">{s.bugs ? `${s.bugs} issue${s.bugs === 1 ? "" : "s"} to triage` : "Clean run — no bugs tripped the oracle"}</div>
        </div>
      </div>

      {s.note && (
        <div className="note" style={{ margin: "0 0 16px", padding: "12px 14px", borderRadius: 10,
          background: `color-mix(in srgb, var(--${s.ended_early ? "layout" : "brand"}) 10%, transparent)`,
          border: `1px solid color-mix(in srgb, var(--${s.ended_early ? "layout" : "brand"}) 34%, var(--hair))`, color: "var(--ink-dim)" }}>
          {s.ended_early ? "⚠" : "✓"} {s.note}
        </div>
      )}

      <div className="sumtiles">
        <Tile icon={<Screens />} k="Distinct screens" v={s.screens} />
        <Tile icon={<Check />} k="Controls tapped" v={s.controls_tapped ?? "—"} />
        <Tile icon={<Steps />} k="Actions" v={s.steps} />
        <Tile icon={<Bug />} k="Bugs" v={s.bugs} />
        <Tile icon={<Clock />} k="Duration" v={formatDuration(s.duration_sec || 0)} />
      </div>

      <div className="k" style={{ font: "600 10px var(--mono)", letterSpacing: ".1em", textTransform: "uppercase", color: "var(--muted)" }}>Action mix</div>
      <div className="verbbar">
        {order.filter((v) => verbs[v]).map((v) => <span key={v} className={v} style={{ width: `${(verbs[v] / total) * 100}%` }} title={`${v}: ${verbs[v]}`} />)}
      </div>
      <div className="chips">
        {order.filter((v) => verbs[v]).map((v) => <span className="chip" key={v}>{v} · {verbs[v]}</span>)}
      </div>

      {s.sections?.length > 0 && (
        <>
          <div className="k" style={{ font: "600 10px var(--mono)", letterSpacing: ".1em", textTransform: "uppercase", color: "var(--muted)", marginTop: 16, marginBottom: 8 }}>Sections reached</div>
          <div className="chips">{s.sections.slice(0, 14).map((x) => <span className="chip" key={x}>{x}</span>)}</div>
        </>
      )}

      <div style={{ display: "flex", gap: 12, marginTop: 20 }}>
        <button className="btn" onClick={() => nav("/app/trace")}>View full trace →</button>
        {s.bugs > 0 && <button className="btn btn-primary" onClick={() => nav("/app/bugs")}><Bug /> Triage bugs</button>}
      </div>
    </div>
  );
}
function Tile({ icon, k, v }) { return <div className="sumtile"><div className="k">{icon} {k}</div><div className="v">{v}</div></div>; }
