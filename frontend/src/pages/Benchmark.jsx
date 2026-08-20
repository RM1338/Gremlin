import { useEffect, useRef } from "react";
import Mascot from "../lib/Mascot.jsx";
import { useStore } from "../lib/useStore.js";
import { evalArms } from "../lib/store.js";

// Two questions live on this page, and they are not the same question.
//
//   1. Does a reasoning agent beat random tapping?   gremlin-vision vs monkey
//   2. Is the *vision model* what does the work?     gremlin-vision vs
//                                                    gremlin-coverage (no model)
//
// The second is the ablation (docs/KNOWN_ISSUES.md, G4) and is the one that
// decides whether the model earns its place. It only renders once that arm has
// actually been run, so the page never implies a result that was not measured.
const SERIES = {
  vision: { name: "Gremlin", sub: "vision model + coverage", color: "var(--series-gremlin)" },
  coverage: { name: "Gremlin, no model", sub: "coverage + a11y grounding only", color: "var(--brand-2)" },
  monkey: { name: "Monkey", sub: "random taps", color: "var(--series-monkey)" },
};

export default function Benchmark() {
  const st = useStore();
  const arms = evalArms(st.evalData);
  const isDemo = st.evalData?.demo === true;
  const rootRef = useRef(null);
  useEffect(() => {
    const id = requestAnimationFrame(() => {
      rootRef.current?.querySelectorAll(".bar-fill").forEach((b) => (b.style.width = b.dataset.w));
    });
    return () => cancelAnimationFrame(id);
  });

  const present = arms ? ["vision", "coverage", "monkey"].filter((k) => arms[k]) : [];
  const g = arms?.vision, c = arms?.coverage, m = arms?.monkey;

  return (
    <div ref={rootRef}>
      <div className="page-head">
        <h1 className="page-title">Benchmark</h1>
        <p className="page-desc">
          Equal action budget, same cold start. Coverage is distinct screens reached,
          deduplicated by perceptual hash.
        </p>
      </div>

      {isDemo && (
        <div className="pill" style={{ marginBottom: 18, color: "var(--layout)", borderColor: "var(--layout)" }}>
          Demo data — not a measured result
        </div>
      )}

      {!g ? (
        <div className="empty-state">
          <div className="icon"><Mascot size={80} state="idle" /></div>
          <h3>No benchmark yet</h3>
          <p>
            Run <code>python -m gremlin.eval --project &lt;app&gt; --coverage-only --monkey</code> to
            compare the agent against random tapping, and against itself with the model removed.
          </p>
        </div>
      ) : (
        <>
          <div className="bench-grid">
            <div className="card chart">
              <div className="chart-title">Distinct screens reached</div>
              <div className="chart-sub">{g.actions} actions each · higher is better</div>
              <div className="bars">
                {present.map((k) => (
                  <BarRow key={k} name={SERIES[k].name} val={arms[k].distinct_screens}
                          max={Math.max(...present.map((j) => arms[j].distinct_screens), 1)}
                          color={SERIES[k].color} />
                ))}
              </div>
              <div className="legend">
                {present.map((k) => (
                  <div className="li" key={k}>
                    <span className="sw" style={{ background: SERIES[k].color }} />
                    {SERIES[k].name} — {SERIES[k].sub}
                  </div>
                ))}
              </div>
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              {m && (
                <div className="callout">
                  <div className="big">
                    {m.distinct_screens ? `${(g.distinct_screens / m.distinct_screens).toFixed(1)}×` : "—"}
                  </div>
                  <div className="lbl">more screens than random</div>
                  <p>
                    The monkey pounds the same first screen. Gremlin tracks which controls it has
                    already tapped and works through the ones it hasn't.
                  </p>
                </div>
              )}

              {c && (
                <div className="card">
                  <div className="chart-title" style={{ marginBottom: 6 }}>Does the model earn its place?</div>
                  <p className="note" style={{ marginTop: 0 }}>
                    The same engine with the vision model removed — accessibility grounding and
                    coverage memory only.
                  </p>
                  <KV k="Screens, with model" v={g.distinct_screens} />
                  <KV k="Screens, without" v={c.distinct_screens} />
                  <KV k="Difference" v={fmtDelta(g.distinct_screens - c.distinct_screens)} />
                  {g.duration_sec != null && c.duration_sec != null && (
                    <KV k="Time cost of the model" v={`${(g.duration_sec - c.duration_sec).toFixed(0)}s`} />
                  )}
                </div>
              )}

              <div className="card">
                <div className="chart-title" style={{ marginBottom: 12 }}>All arms</div>
                {present.map((k) => (
                  <KV key={k} k={SERIES[k].name}
                      v={`${arms[k].distinct_screens} screens · ${arms[k].distinct_bugs} bugs`} />
                ))}
              </div>
            </div>
          </div>

          <p className="note" style={{ marginTop: 18 }}>
            One run is one sample. A result worth citing needs at least five seeds and a reported
            spread — the multi-seed runner is not built yet, so read this as a smoke test, not a
            finding.
          </p>
        </>
      )}
    </div>
  );
}

function fmtDelta(n) {
  if (n === 0) return "none — the model changed nothing";
  return n > 0 ? `+${n} screens with the model` : `${n} screens with the model`;
}

function BarRow({ name, val, max, color }) {
  const pct = Math.max(4, (val / max) * 100);
  return (
    <div className="bar-row">
      <div className="bar-name"><span className="swatch" style={{ background: color }} />{name}</div>
      <div className="bar-track">
        <div className="bar-fill" data-w={`${pct}%`}
             style={{ background: color }} />
      </div>
      <div className="bar-val">{val}</div>
    </div>
  );
}

function KV({ k, v }) {
  return (
    <div className="kv">
      <span className="note" style={{ margin: 0 }}>{k}</span>
      <span style={{ font: "600 13px var(--mono)" }}>{v}</span>
    </div>
  );
}
