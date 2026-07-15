import { useEffect, useRef } from "react";
import Mascot from "../lib/Mascot.jsx";
import { Bars } from "../lib/icons.jsx";
import { useStore } from "../lib/useStore.js";

export default function Benchmark() {
  const st = useStore();
  const g = st.evalData?.find((e) => e.explorer === "gremlin");
  const m = st.evalData?.find((e) => e.explorer === "monkey");
  const rootRef = useRef(null);
  useEffect(() => {
    const id = requestAnimationFrame(() => {
      rootRef.current?.querySelectorAll(".bar-fill").forEach((b) => (b.style.width = b.dataset.w));
    });
    return () => cancelAnimationFrame(id);
  });

  return (
    <div ref={rootRef}>
      <div className="page-head">
        <h1 className="page-title">Benchmark</h1>
        <p className="page-desc">Gremlin vs. <code>adb shell monkey</code> — equal action budget, same throwaway account. Coverage is measured as distinct screens reached.</p>
      </div>

      {!g || !m ? (
        <div className="empty-state">
          <div className="icon"><Mascot size={80} float={false} /></div>
          <h3>No benchmark yet</h3><p>Run the eval to compare Gremlin against a random monkey.</p>
        </div>
      ) : (() => {
        const max = Math.max(g.distinct_screens, m.distinct_screens, 1);
        const mult = m.distinct_screens ? Math.round(g.distinct_screens / m.distinct_screens) : g.distinct_screens;
        return (
          <>
            <div className="bench-grid">
              <div className="card chart">
                <div className="chart-title">Distinct screens reached</div>
                <div className="chart-sub">{g.actions} actions each · higher is better</div>
                <div className="bars">
                  <BarRow name="Gremlin" val={g.distinct_screens} max={max} color="var(--series-gremlin)" />
                  <BarRow name="Monkey" val={m.distinct_screens} max={max} color="var(--series-monkey)" />
                </div>
                <div className="legend">
                  <div className="li"><span className="sw" style={{ background: "var(--series-gremlin)" }} /> Gremlin — vision-driven agent</div>
                  <div className="li"><span className="sw" style={{ background: "var(--series-monkey)" }} /> Monkey — random taps</div>
                </div>
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
                <div className="callout">
                  <div className="big">{mult}×</div>
                  <div className="lbl">more screens than random</div>
                  <p>The monkey pounds the same first screen; Gremlin reasons about which sections it hasn't visited and navigates there deliberately.</p>
                </div>
                <div className="card">
                  <div className="chart-title" style={{ marginBottom: 12 }}>Head to head</div>
                  <KV k="Actions" v={`${g.actions} vs ${m.actions}`} />
                  <KV k="Distinct screens" v={`${g.distinct_screens} vs ${m.distinct_screens}`} />
                  <KV k="Distinct bugs" v={`${g.distinct_bugs} vs ${m.distinct_bugs}`} />
                </div>
              </div>
            </div>
            <p className="note" style={{ marginTop: 18 }}>Honest baseline: <b>0 bugs</b> on a clean build is expected — the coverage gap, not a bug count, is the signal. Bug detection is demonstrated separately with a planted defect.</p>
          </>
        );
      })()}
    </div>
  );
}

function BarRow({ name, val, max, color }) {
  const pct = Math.max(4, (val / max) * 100);
  return (
    <div className="bar-row">
      <div className="bar-name"><span className="swatch" style={{ background: color }} />{name}</div>
      <div className="bar-track"><div className="bar-fill" data-w={`${pct}%`} style={{ background: `linear-gradient(90deg, color-mix(in srgb, ${color} 78%, #000), ${color})` }} /></div>
      <div className="bar-val">{val}</div>
    </div>
  );
}
function KV({ k, v }) { return <div className="kv"><span className="note" style={{ margin: 0 }}>{k}</span><span style={{ font: "600 13px var(--mono)" }}>{v}</span></div>; }
