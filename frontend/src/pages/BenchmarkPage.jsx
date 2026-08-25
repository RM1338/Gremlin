import { Link } from "react-router-dom";
import { SiteNav, SiteFooter, PageHead } from "../lib/SiteChrome.jsx";
import BenchmarkResults from "../lib/BenchmarkSection.jsx";

/* The benchmark as a page of its own, alongside Blog and Pricing.
 *
 * It started inside the console, on a fixed-height layout that does not scroll,
 * where the tables overlapped everything beneath them; and it was behind
 * sign-in, which hid the one thing a reader wants before trying anything.
 *
 * The order is deliberate: the numbers first, the method under them, the
 * command to reproduce it last. A methodology section above the result is a
 * page nobody scrolls.
 */

const METHOD = [
  ["Equal budget, same cold start",
   "Every arm gets the same number of actions from a freshly launched app. An agent that explores for longer is not a better agent, it is a longer run."],
  ["Screens deduplicated perceptually",
   "Distinct screens are counted by perceptual hash, so a list that scrolled two pixels is the same screen and inflates nobody's coverage."],
  ["Several seeds, spread reported",
   "Exploration is stochastic, so each arm runs over consecutive seeds and is reported as mean ± standard deviation. One lucky seed reads exactly like a capability."],
  ["Failed runs excluded, never zeroed",
   "A seed that dies — a model quota, a flaky device — is recorded and left out of the mean rather than averaged in as a zero. The reported n is what was measured."],
];

const TOOLS = ["Gremlin", "Android Monkey", "Appium / Espresso", "Maestro"];

/* Capability, stated plainly, with no performance claim attached to any column
   we have not measured. Each row is something a reader can verify from the
   tools' own documentation. */
const COMPARE = [
  ["Tests to write first", "None", "None", "One per flow", "One flow file per journey"],
  ["Chooses what to tap", "Vision model, over untapped controls", "Uniformly at random", "You do, in code", "You do, in YAML"],
  ["Reaches screens nobody listed", "Yes — that is the job", "By accident, if at all", "No", "No"],
  ["How a defect is judged", "The framework's own log line", "Only if it crashes", "Your assertions", "Your assertions"],
  ["Survives a renamed widget", "Grounded on the a11y tree", "n/a", "Breaks if the selector changes", "Breaks if the selector changes"],
  ["Repro you can hand over", "Recorded trace, replays with no model", "The seed, sometimes", "The test", "The flow"],
  ["Proposes a fix", "Patch behind three gates", "No", "No", "No"],
];

export default function BenchmarkPage() {
  return (
    <div className="site">
      <SiteNav />
      <PageHead
        eyebrow="Evidence"
        title="Benchmark"
        lede="Three arms, one action budget, the same cold start — so the vision model's contribution is a number rather than a claim."
      />

      <BenchmarkResults />

      <section className="section bench-method">
        <h2 className="section-title">How it is measured</h2>
        <div className="bench-method-list">
          {METHOD.map(([h, p]) => (
            <div key={h}><b>{h}</b><p>{p}</p></div>
          ))}
        </div>
      </section>

      <section className="section">
        <h2 className="section-title">How it compares</h2>
        <p className="section-lede">
          What each tool can do, not how fast it does it. Only the Monkey column is measured above —
          the rest is capability, which is the honest thing to compare when nobody has run the
          others on this app.
        </p>
        <div className="bench-table-wrap">
          <table className="bench-table compare">
            <thead>
              <tr>
                <th></th>
                {TOOLS.map((t) => <th key={t}>{t}</th>)}
              </tr>
            </thead>
            <tbody>
              {COMPARE.map(([q, ...cells]) => (
                <tr key={q}>
                  <td className="q">{q}</td>
                  {cells.map((c, i) => <td key={i}>{c}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="note" style={{ maxWidth: "68ch" }}>
          Scripted and declarative tools are not competitors so much as a different job: they check
          flows you already know about. The comparison that matters for Gremlin is the one measured
          above — against random tapping, and against itself with the model removed.
        </p>
      </section>

      <section className="section">
        <h2 className="section-title">Run it yourself</h2>
        <p className="section-lede">
          Nothing here is a figure you have to take on trust. <Link to="/app/setup">Setup</Link> covers
          getting a device first.
        </p>
        <pre className="setup-code">{`python -m gremlin.eval --project ~/Projects/your-app \\
    --actions 30 --repeats 5 --coverage-only --monkey`}</pre>
      </section>

      <SiteFooter />
    </div>
  );
}
