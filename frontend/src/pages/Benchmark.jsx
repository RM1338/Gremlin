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
  const data = st.evalData || {};
  const isDemo = data.demo === true;
  // Present only on schema 2 — the shape that reports several seeds per arm
  // rather than one. Everything keyed off these degrades to the old single-
  // sample rendering rather than inventing a spread that was never measured.
  const proto = data.schema >= 2 ? data.protocol : null;
  const env = data.schema >= 2 ? data.device : null;
  const rates = data.schema >= 2 ? data.detection_rates : null;
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
    <div ref={rootRef} className="page-root">
      <div className="page-head" style={{ display: "flex", alignItems: "center", gap: 18 }}>
        <Mascot size={112} state="measure" />
        <div style={{ flex: 1 }}>
        <h1 className="page-title">Benchmark</h1>
        <p className="page-desc">
          Equal action budget, same cold start. Coverage is distinct screens reached,
          deduplicated by perceptual hash.
        </p>
        </div>
      </div>

      <div className="page-body">
      {isDemo && (
        <div className="pill" style={{ marginBottom: 18, color: "var(--layout)", borderColor: "var(--layout)" }}>
          Demo data — not a measured result
        </div>
      )}

      {env && (
        <div className="bench-env">
          {[["App", `${data.app?.package || "—"}${data.app?.commit ? ` @ ${data.app.commit}` : ""}`],
            ["Device", `${env.kind}${env.model ? ` · ${env.model}` : ""}${env.width ? ` · ${env.width}×${env.height}` : ""}`],
            ["Android", env.android ? `${env.android} (API ${env.sdk})` : "—"],
            ["Vision model", data.vision_model?.model || data.vision_model?.provider || "—"],
            ["Budget", `${proto?.actions} actions × ${proto?.repeats} seeds`],
            ["Measured", (data.generated_at || "").replace("T", " ").slice(0, 16)]].map(([k, v]) => (
            <div className="bench-env-cell" key={k}><span className="k">{k}</span><span className="v">{v}</span></div>
          ))}
        </div>
      )}

      {!g ? (
        <div className="empty-state">
          <div className="icon"><Mascot size={132} state="measure" /></div>
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
                          sd={arms[k].sd?.screens} n={arms[k].n}
                          max={Math.max(...present.map((j) => arms[j].distinct_screens), 1)}
                          color={SERIES[k].color} />
                ))}
              </div>
              <p className="note" style={{ margin: "14px 0 0", fontSize: 12 }}>
                {proto
                  ? <>Each arm run {proto.repeats}× (seeds {proto.seeds?.[0]}–{proto.seeds?.[proto.seeds.length - 1]}),
                      bars show the mean and the whisker one standard deviation.
                      {g.failed ? ` ${g.failed} run(s) failed and are excluded — n is what was measured.` : ""}</>
                  : <>One run is one sample. A result worth citing needs several seeds and a reported
                      spread — re-run with <code>--repeats 5</code> and this page will show it.</>}
              </p>
              <div className="legend">
                {present.map((k) => (
                  <div className="li" key={k}>
                    <span className="sw" style={{ background: SERIES[k].color }} />
                    {SERIES[k].name} — {SERIES[k].sub}
                  </div>
                ))}
              </div>
            </div>

            <div className="col">
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
                      v={fmtArm(arms[k])} />
                ))}
              </div>
            </div>
          </div>

          {rates && Object.keys(rates).length > 0 && (
            <div className="card" style={{ marginTop: 18 }}>
              <div className="chart-title">Per-defect detection rate</div>
              <div className="chart-sub">
                How many seeds each arm found each defect in. A defect found in one seed of five is
                luck; one found in five of five is a capability — and a mean bug count cannot tell
                them apart.
              </div>
              <div className="bench-table-wrap">
                <table className="bench-table">
                  <thead>
                    <tr>
                      <th>Defect</th>
                      {present.map((k) => <th key={k}>{SERIES[k].name}</th>)}
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(rates).map(([key, row]) => (
                      <tr key={key}>
                        <td className="defect">{key}</td>
                        {present.map((k) => {
                          const cell = row[armKey(k, arms)] || { found_in: 0, of: 0 };
                          const pct = cell.of ? cell.found_in / cell.of : 0;
                          return (
                            <td key={k}>
                              <span className={"rate" + (pct === 1 ? " full" : pct === 0 ? " none" : "")}>
                                {cell.found_in}/{cell.of}
                              </span>
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {proto && (
            <div className="card" style={{ marginTop: 18 }}>
              <div className="chart-title">Every run</div>
              <div className="chart-sub">
                The individual samples behind the means above. Spread is the finding, not noise to
                be averaged away.
              </div>
              <div className="bench-table-wrap">
                <table className="bench-table">
                  <thead>
                    <tr><th>Arm</th><th>Seed</th><th>Screens</th><th>Bugs</th><th>Seconds</th><th>Outcome</th></tr>
                  </thead>
                  <tbody>
                    {present.flatMap((k) => (arms[k].runs || []).map((r) => (
                      <tr key={k + r.seed}>
                        <td className="defect">{SERIES[k].name}</td>
                        <td>{r.seed}</td>
                        <td>{r.error ? "—" : r.distinct_screens}</td>
                        <td>{r.error ? "—" : r.distinct_bugs}</td>
                        <td>{r.error ? "—" : r.duration_sec}</td>
                        <td>{r.error ? <span className="rate none">{r.error}</span> : <span className="rate full">ok</span>}</td>
                      </tr>
                    )))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

        </>
      )}
      </div>
    </div>
  );
}

/* Which key this arm has in the detection table — the table is keyed by the
   explorer name the harness wrote, not by the UI's short role name. */
function armKey(role, arms) { return arms[role]?.explorer; }

function fmtArm(a) {
  const s = a.sd?.screens != null ? `${a.distinct_screens} ± ${a.sd.screens}` : a.distinct_screens;
  const b = a.sd?.bugs != null ? `${a.distinct_bugs} ± ${a.sd.bugs}` : a.distinct_bugs;
  return `${s} screens · ${b} bugs${a.n ? ` · n=${a.n}` : ""}`;
}

function fmtDelta(n) {
  if (n === 0) return "none — the model changed nothing";
  return n > 0 ? `+${n} screens with the model` : `${n} screens with the model`;
}

function BarRow({ name, val, max, color, sd, n }) {
  const pct = Math.max(4, (val / max) * 100);
  // One standard deviation each way, drawn on the same scale as the bar. Absent
  // when there is only one sample, because there is nothing to draw.
  const err = sd != null && sd > 0 ? (sd / max) * 100 : 0;
  return (
    <div className="bar-row">
      <div className="bar-name"><span className="swatch" style={{ background: color }} />{name}</div>
      <div className="bar-track">
        <div className="bar-fill" data-w={`${pct}%`} style={{ background: color }} />
        {err > 0 && (
          <div className="bar-err" title={`± ${sd} over ${n} seeds`}
               style={{ left: `${Math.max(0, pct - err)}%`, width: `${Math.min(100, err * 2)}%` }} />
        )}
      </div>
      <div className="bar-val">{sd != null && sd > 0 ? `${val} ± ${sd}` : val}</div>
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
