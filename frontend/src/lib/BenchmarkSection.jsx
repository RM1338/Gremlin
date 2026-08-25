import { useEffect, useRef } from "react";
import { useStore } from "./useStore.js";
import { evalArms, loadState } from "./store.js";

/* The benchmark, as a landing-page section rather than a console page.
 *
 * It used to live behind sign-in, on a fixed-height console page that does not
 * scroll — where a per-defect table and a per-seed table had nowhere to go and
 * overlapped everything under them. It also hid the one thing a reader most
 * wants before trying the tool. A scrolling marketing page has room for both
 * tables and an audience for them, so the page moved rather than the layout
 * being fought.
 *
 * Two questions live here, and they are not the same question:
 *   1. Does a reasoning agent beat random tapping?  vision vs monkey
 *   2. Is the *vision model* what does the work?    vision vs coverage-only
 * The second is the ablation (docs/KNOWN_ISSUES.md, G4) and is the one that
 * decides whether the model earns its place. It renders only once that arm has
 * been run, so the page never implies a result nobody measured.
 */

const SERIES = {
  vision: { name: "Gremlin", sub: "vision model + coverage", color: "var(--series-gremlin)" },
  coverage: { name: "Gremlin, no model", sub: "coverage + a11y grounding only", color: "var(--brand-2)" },
  monkey: { name: "Monkey", sub: "random taps", color: "var(--series-monkey)" },
};

export default function BenchmarkSection() {
  const st = useStore();
  const ref = useRef(null);

  // The landing page is reachable without the console ever having loaded, so it
  // fetches its own data. loadState falls back to a bundled sample-state.json on
  // a static deploy where there is no backend at all.
  useEffect(() => { if (!st.evalData) loadState(); }, []);
  useEffect(() => {
    const id = requestAnimationFrame(() =>
      ref.current?.querySelectorAll(".bar-fill").forEach((b) => (b.style.width = b.dataset.w)));
    return () => cancelAnimationFrame(id);
  });

  const data = st.evalData || {};
  const arms = evalArms(data);
  const isDemo = data.demo === true;
  const proto = data.schema >= 2 ? data.protocol : null;
  const env = data.schema >= 2 ? data.device : null;
  const rates = data.schema >= 2 ? data.detection_rates : null;
  const present = arms ? ["vision", "coverage", "monkey"].filter((k) => arms[k]) : [];
  const g = arms?.vision, c = arms?.coverage, m = arms?.monkey;

  return (
    <section className="section" id="proof" ref={ref}>
      <h2 className="section-title">Measured, not asserted</h2>
      <p className="section-lede">
        Three arms, one action budget, the same cold start &mdash; so the model&rsquo;s contribution is a
        number rather than a claim.
      </p>

      <div className="proof-box">
        <ul>
          <li><b>Android&rsquo;s Monkey</b> &mdash; random taps, the standard baseline.</li>
          <li><b>Gremlin without the model</b> &mdash; accessibility grounding and coverage memory only.</li>
          <li><b>Gremlin</b> &mdash; the full agent.</li>
        </ul>
        <p>
          The second arm is the honest one: it isolates what the vision model actually contributes,
          rather than crediting it for what the coverage bookkeeping does.
        </p>
      </div>

      {!g ? (
        <div className="proof-pending">
          Results are pending. The numbers appear here once the ablation has run over enough seeds
          to report a spread.
        </div>
      ) : (
        <>
          {isDemo && (
            <div className="proof-demo">
              Demo data &mdash; not a measured result. This is what the section renders once a real
              benchmark has been run.
            </div>
          )}

          {env && (
            <div className="bench-env">
              {[["App", `${data.app?.package || "—"}${data.app?.commit ? ` @ ${data.app.commit}` : ""}`],
                ["Device", `${env.kind}${env.width ? ` · ${env.width}×${env.height}` : ""}`],
                ["Android", env.android ? `${env.android} (API ${env.sdk})` : "—"],
                ["Vision model", data.vision_model?.model || data.vision_model?.provider || "—"],
                ["Budget", `${proto?.actions} actions × ${proto?.repeats} seeds`],
                ["Measured", (data.generated_at || "").replace("T", " ").slice(0, 16)]].map(([k, v]) => (
                <div className="bench-env-cell" key={k}><span className="k">{k}</span><span className="v">{v}</span></div>
              ))}
            </div>
          )}

          <div className="bench-cards">
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
                  ? <>Each arm run {proto.repeats}× (seeds {proto.seeds?.[0]}&ndash;{proto.seeds?.[proto.seeds.length - 1]});
                      the whisker is one standard deviation.
                      {g.failed ? ` ${g.failed} run(s) failed and are excluded — n is what was measured.` : ""}</>
                  : <>One run is one sample. A result worth citing needs several seeds and a reported
                      spread — re-run with <code>--repeats 5</code>.</>}
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
                    already tapped and works through the ones it hasn&rsquo;t.
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
                  <KV k="Screens, with model" v={fmt(g.distinct_screens, g.sd?.screens)} />
                  <KV k="Screens, without" v={fmt(c.distinct_screens, c.sd?.screens)} />
                  <KV k="Difference" v={fmtDelta(g.distinct_screens - c.distinct_screens)} />
                  {g.duration_sec != null && c.duration_sec != null && (
                    <KV k="Time cost of the model" v={`${(g.duration_sec - c.duration_sec).toFixed(0)}s`} />
                  )}
                </div>
              )}
            </div>
          </div>

          {rates && Object.keys(rates).length > 0 && (
            <div className="card bench-wide">
              <div className="chart-title">Per-defect detection rate</div>
              <div className="chart-sub">
                How many seeds each arm found each defect in. A defect found in one seed of five is
                luck; one found in five of five is a capability &mdash; and a mean bug count cannot tell
                them apart.
              </div>
              <div className="bench-table-wrap">
                <table className="bench-table">
                  <thead>
                    <tr><th>Defect</th>{present.map((k) => <th key={k}>{SERIES[k].name}</th>)}</tr>
                  </thead>
                  <tbody>
                    {Object.entries(rates).map(([key, row]) => (
                      <tr key={key}>
                        <td className="defect">{key}</td>
                        {present.map((k) => {
                          const cell = row[arms[k]?.explorer] || { found_in: 0, of: 0 };
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
            <details className="bench-runs">
              <summary>Every individual run ({present.reduce((n, k) => n + (arms[k].runs?.length || 0), 0)} samples)</summary>
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
            </details>
          )}
        </>
      )}
    </section>
  );
}

function fmt(v, sd) { return sd != null && sd > 0 ? `${v} ± ${sd}` : `${v}`; }

function fmtDelta(n) {
  if (n === 0) return "none — the model changed nothing";
  return n > 0 ? `+${n.toFixed(1)} screens with the model` : `${n.toFixed(1)} screens with the model`;
}

function BarRow({ name, val, max, color, sd, n }) {
  const pct = Math.max(4, (val / max) * 100);
  // One standard deviation each way, on the bar's own scale. Absent when there
  // is a single sample, because there is nothing to draw.
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
