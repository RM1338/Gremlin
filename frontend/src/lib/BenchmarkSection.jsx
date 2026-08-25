import { useEffect, useRef } from "react";
import { useStore } from "./useStore.js";
import { evalArms, loadState } from "./store.js";

/* The measured results, rendered wherever a page asks for them.
 *
 * Laid out as: what it found (three numbers), how far it got (one chart), what
 * it caught (one table), then the raw samples folded away. Everything else —
 * heading, method, how to reproduce it — belongs to the page around this, so
 * the results themselves stay one column of decreasing importance rather than
 * a grid of competing cards.
 *
 * Two questions live here, and they are not the same question:
 *   1. Does a reasoning agent beat random tapping?  vision vs monkey
 *   2. Is the *vision model* what does the work?    vision vs coverage-only
 * The second is the ablation (docs/KNOWN_ISSUES.md, G4) and is the one that
 * decides whether the model earns its place. It renders only once that arm has
 * been run, so the page never implies a result nobody measured.
 */

const SERIES = {
  vision: { name: "Gremlin", sub: "vision model + coverage memory", color: "var(--series-gremlin)" },
  coverage: { name: "No model", sub: "coverage + a11y grounding only", color: "var(--brand-2)" },
  monkey: { name: "Monkey", sub: "random taps, Android's own", color: "var(--series-monkey)" },
};

export default function BenchmarkResults() {
  const st = useStore();
  const ref = useRef(null);

  // Reachable without the console ever having loaded, so it fetches its own
  // data. loadState falls back to a bundled sample on a static deploy.
  useEffect(() => { if (!st.evalData) loadState(); }, []);
  useEffect(() => {
    const id = requestAnimationFrame(() =>
      ref.current?.querySelectorAll(".bar-fill").forEach((b) => (b.style.width = b.dataset.w)));
    return () => cancelAnimationFrame(id);
  });

  const data = st.evalData || {};
  const arms = evalArms(data);
  const v2 = data.schema >= 2;
  const proto = v2 ? data.protocol : null;
  const env = v2 ? data.device : null;
  const rates = v2 ? data.detection_rates : null;
  const present = arms ? ["vision", "coverage", "monkey"].filter((k) => arms[k]) : [];
  const g = arms?.vision, c = arms?.coverage, m = arms?.monkey;

  if (!g) {
    return (
      <section className="section" ref={ref}>
        <div className="bench-pending">
          <b>No results yet.</b> The numbers appear here once the ablation has been run over enough
          seeds to report a spread. The command is below — nothing on this page is a figure you
          have to take on trust.
        </div>
      </section>
    );
  }

  const totalDefects = Object.keys(rates || {}).length;
  const foundByG = Object.values(rates || {}).filter(
    (r) => (r[g.explorer]?.found_in || 0) > 0).length;

  return (
    <section className="section bench" ref={ref}>
      {data.demo === true && (
        <p className="bench-flag">
          Demo data — not a measured result. This is the shape the page takes once a real
          benchmark has run.
        </p>
      )}

      {/* The three claims, in the order a reader cares about them. */}
      <div className="bench-stats">
        {m && (
          <div className="bench-stat">
            <b>{m.distinct_screens ? `${(g.distinct_screens / m.distinct_screens).toFixed(1)}×` : "—"}</b>
            <span>more screens than random tapping</span>
            <p>The monkey pounds the first screen it lands on. Gremlin tracks what it has already
               tapped and heads for what it hasn&rsquo;t.</p>
          </div>
        )}
        {c && (
          <div className="bench-stat">
            <b>{fmtSigned(g.distinct_screens - c.distinct_screens)}</b>
            <span>screens the vision model adds</span>
            <p>Against the identical engine with the model removed. This is the honest comparison:
               it separates the model from the coverage bookkeeping.</p>
          </div>
        )}
        {rates && (
          <div className="bench-stat">
            <b>{foundByG}<i>/{totalDefects}</i></b>
            <span>known defects found</span>
            <p>Every defect any arm reached, and how many of them the full agent caught at least
               once across the seeds.</p>
          </div>
        )}
      </div>

      <div className="card bench-chart">
        <div className="chart-title">Distinct screens reached</div>
        <div className="chart-sub">
          {g.actions} actions per arm, same cold start · screens deduplicated by perceptual hash
        </div>
        <div className="bars">
          {present.map((k) => (
            <BarRow key={k} name={SERIES[k].name} sub={SERIES[k].sub}
                    val={arms[k].distinct_screens} sd={arms[k].sd?.screens} n={arms[k].n}
                    max={Math.max(...present.map((j) => arms[j].distinct_screens), 1)}
                    color={SERIES[k].color} />
          ))}
        </div>
        <p className="bench-caption">
          {proto
            ? <>Each arm run {proto.repeats}× over seeds {proto.seeds?.[0]}&ndash;{proto.seeds?.[proto.seeds.length - 1]};
                the bar is the mean and ± is one standard deviation across those runs.
                {g.failed ? ` ${g.failed} run(s) failed and are excluded — n is what was measured.` : ""}</>
            : <>A single run per arm — no spread to report. Re-run with <code>--repeats 5</code>.</>}
        </p>
      </div>

      {rates && totalDefects > 0 && (
        <div className="card bench-chart">
          <div className="chart-title">Which defects each arm actually found</div>
          <div className="chart-sub">
            Seeds in which the arm detected it. A defect found in one seed of five is luck; one
            found in five of five is a capability — and a mean bug count cannot tell them apart.
          </div>
          <div className="bench-table-wrap">
            <table className="bench-table">
              <thead>
                <tr><th>Defect</th>{present.map((k) => <th key={k}>{SERIES[k].name}</th>)}</tr>
              </thead>
              <tbody>
                {Object.entries(rates).map(([key, row]) => (
                  <tr key={key}>
                    <td className="defect" title={key}>{shorten(key)}</td>
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

      {/* What the run was measured on. It reads as debris unlabelled, but it
          cannot be dropped: overflow defects are screen-size dependent, so the
          same app on a different handset is a different measurement and a number
          without its geometry is not comparable to anything. Labelled pairs,
          folded into the table card's footer rhythm rather than floating. */}
      {env && (
        <dl className="bench-prov">
          {[["App", data.app?.package],
            ["Build", data.app?.commit],
            ["Device", `${env.kind}${env.width ? ` · ${env.width}×${env.height}` : ""}${env.android ? ` · Android ${env.android}` : ""}`],
            ["Vision model", data.vision_model?.model || data.vision_model?.provider],
            ["Budget", proto && `${proto.actions} actions × ${proto.repeats} seeds`],
            ["Measured", (data.generated_at || "").slice(0, 10)],
          ].filter(([, v]) => v).map(([k, v]) => (
            <div key={k}><dt>{k}</dt><dd>{v}</dd></div>
          ))}
        </dl>
      )}

      {proto && (
        <div className="card bench-chart">
          <div className="chart-title">
            Every individual run ({present.reduce((n, k) => n + (arms[k].runs?.length || 0), 0)} samples)
          </div>
          <div className="chart-sub">
            The samples behind the means above. The spread is the finding, not noise to be averaged
            away — so it is on the page, not behind a disclosure.
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
                    <td>{r.error
                      ? <span className="rate none" title={r.error}>failed</span>
                      : <span className="rate full">ok</span>}</td>
                  </tr>
                )))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </section>
  );
}

/* Defect keys are `kind|file:line`, and the file path is the half that blows the
   column width. Keep the kind, keep the basename, drop the directories. */
function shorten(key) {
  const [kind, loc = ""] = key.split("|");
  const tail = loc.split("/").pop();
  return tail && tail !== loc ? `${kind} · ${tail}` : (loc ? `${kind} · ${loc}` : kind);
}

function fmtSigned(n) {
  const v = Number(n.toFixed(1));
  return v > 0 ? `+${v}` : `${v}`;
}

function BarRow({ name, sub, val, max, color, sd, n }) {
  const pct = Math.max(4, (val / max) * 100);
  // The spread used to be drawn as an error bar across the track. It read as a
  // stray line: on a dark fill it nearly vanished, on a short bar it jutted out
  // past the end, so the same statistic looked like two different marks. The
  // "± sd" beside the number says it once and unambiguously.
  return (
    <div className="bar-row bench-bar">
      <div className="bar-name">
        <span className="swatch" style={{ background: color }} />
        <span className="bn"><b>{name}</b><i>{sub}</i></span>
      </div>
      <div className="bar-track">
        <div className="bar-fill" data-w={`${pct}%`} style={{ background: color }} />
      </div>
      <div className="bar-val" title={n ? `mean of ${n} seeds` : undefined}>
        {val}{sd != null && sd > 0 && <i> ± {sd}</i>}
      </div>
    </div>
  );
}
