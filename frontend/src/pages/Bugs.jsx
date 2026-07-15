import { Bug, Check } from "../lib/icons.jsx";
import { sevClass, screenUrl } from "../lib/ui.jsx";
import { useStore } from "../lib/useStore.js";

export default function Bugs() {
  const st = useStore();
  const bugs = st.trace?.bugs || [];

  return (
    <>
      <div className="page-head">
        <h1 className="page-title">Bugs</h1>
        <p className="page-desc">Crashes, layout overflows and jank the oracle caught by draining logcat scoped to the app pid — each with the screen at the moment of failure and a repro trace.</p>
      </div>

      {bugs.length === 0 ? (
        <div className="empty-state">
          <div className="icon"><div style={{ width: 72, height: 72, borderRadius: "50%", display: "grid", placeItems: "center", background: "color-mix(in srgb, var(--brand) 12%, transparent)", color: "var(--brand)" }}><Check style={{ width: 34, height: 34 }} /></div></div>
          <h3>No bugs — clean run</h3>
          <p>Gremlin explored the app end-to-end without tripping the oracle. Plant a defect to see detection light up.</p>
        </div>
      ) : (
        <div className="grid-2">
          {bugs.map((b, i) => {
            const shot = b.screenshot ? b.screenshot.split("/").pop() : null;
            return (
              <div className="card" key={i}>
                <div className={"bug-card " + sevClass(b.severity)} style={{ border: 0, padding: 0 }}>
                  <div className="sev"><Bug /> {b.severity}</div>
                  <div className="t">{b.title || b.kind}</div>
                  <div className="s">found at step {b.step} · {b.kind}</div>
                </div>
                {b.dart_file && <div className="tl-target" style={{ marginTop: 12 }}>at <b>{b.dart_file}:{b.dart_line}</b></div>}
                {b.log_line && <pre className="note" style={{ marginTop: 10, whiteSpace: "pre-wrap", background: "var(--surface-2)", padding: 12, borderRadius: 8, overflow: "auto" }}>{b.log_line}</pre>}
                {shot && <div className="tl-thumb" style={{ width: 120, marginTop: 12 }}><img loading="lazy" src={screenUrl(shot)} alt="" /></div>}
              </div>
            );
          })}
        </div>
      )}
    </>
  );
}
