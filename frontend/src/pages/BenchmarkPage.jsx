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
        <h2 className="section-title">Run it yourself</h2>
        <p className="section-lede">
          The harness is in the repo and takes a target. Nothing here is a figure you have to take
          on trust.
        </p>
        <pre className="setup-code">{`python -m gremlin.eval --project ~/Projects/your-app \\
    --actions 30 --repeats 5 --coverage-only --monkey`}</pre>
        <p className="note" style={{ maxWidth: "62ch" }}>
          Results land in <code>runs/eval/&lt;package&gt;/eval.json</code>, mirrored to <code>runs/latest/</code>,
          which is what this page reads. <Link to="/app/setup">Setup</Link> covers getting a device
          first — a phone, an emulator, or the container.
        </p>
      </section>

      <SiteFooter />
    </div>
  );
}
