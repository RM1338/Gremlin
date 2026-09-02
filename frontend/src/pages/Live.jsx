import Mascot from "../lib/Mascot.jsx";
import { mascotState, mascotLine } from "../lib/mascotState.js";
import { useNavigate } from "react-router-dom";
import { Bolt, Check, Screens, Steps, Bug, Clock } from "../lib/icons.jsx";
import { pad3, sevClass } from "../lib/ui.jsx";
import { useStore } from "../lib/useStore.js";
import { formatDuration } from "../lib/notify.js";

// A run is framed as the thing being driven. A handset bezel around a
// 1280x800 browser screenshot reads as a bug in the console, not as a style
// choice — so a web run gets a window with a title bar and its address in it.
function Viewport({ st, cur }) {
  // While a run is on, what is actually being driven decides the frame. Before
  // one starts there is nothing being driven, so the mode the user picked does
  // — otherwise the console shows a handset to someone about to test a website.
  // The mode the user picked is what Start actually launched, so it is the
  // authority. The server's platform only gets a say when it disagrees *and*
  // has had a chance to be right — i.e. once a run is under way and has
  // reported a platform of its own.
  const web = st.running
    ? (st.platform ? st.platform === "web" : st.mode === "web")
    : st.mode === "web";
  const shell = web ? "browser" : "phone";
  const empty = st.running
    ? <><div className="spinner" />{st.status || "waiting for first frame…"}</>
    : web
      ? "enter an address above, then press Start run — the page appears here"
      : "pick an app above, then press Start run — the screen appears here";

  const frame = cur?.frame
    ? <img src={`data:image/png;base64,${cur.frame}`} alt={web ? "page" : "device"}
           onLoad={(e) => {
             // The shell is shaped by whatever is actually being driven: a
             // sandbox boots at 1080x1920, a phone is often 1080x2340, and a
             // browser viewport is landscape. A fixed shape cropped them all.
             const { naturalWidth: w, naturalHeight: h } = e.target;
             // Two variables, not one. `--shot-aspect` is published on the root
             // element from the last run's frames, so a browser window sharing
             // that name inherited the previous *phone* run's 1080/1920 and
             // rendered as a tall black column.
             if (w && h) e.target.closest(`.${shell}`)
               ?.style.setProperty(web ? "--web-aspect" : "--shot-aspect", `${w}/${h}`);
           }} />
    : <div className={`${shell}-empty`}>{empty}</div>;

  if (!web) return <div className="phone"><div className="phone-screen">{frame}</div></div>;

  return (
    <div className="browser">
      <div className="browser-bar">
        <span className="browser-dot" /><span className="browser-dot" /><span className="browser-dot" />
        <div className="browser-url" title={st.targetUrl}>{st.targetUrl || "about:blank"}</div>
      </div>
      <div className="browser-screen">{frame}</div>
    </div>
  );
}


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
      <div className={"live" + (done ? " done" : "")
        + ((st.running && st.platform ? st.platform === "web" : st.mode === "web") ? " web" : "")}>
        <div className="live-main">
          {done ? <Summary s={st.summary} /> : <Viewport st={st} cur={cur} />}
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
