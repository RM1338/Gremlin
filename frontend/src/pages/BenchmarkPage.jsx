import { Link } from "react-router-dom";
import { SiteNav, SiteFooter, PageHead } from "../lib/SiteChrome.jsx";
import BenchmarkSection from "../lib/BenchmarkSection.jsx";

/* The benchmark as a page of its own, alongside Blog and Pricing.
 *
 * It started inside the console, on a fixed-height layout that does not scroll,
 * where the per-defect and per-seed tables overlapped everything beneath them.
 * It was also behind sign-in, which hid the one thing a reader wants before
 * trying anything. A public page has room for the tables and an audience for
 * them — and, unlike a landing-page section, somewhere to put the method.
 */

const METHOD = [
  ["Equal action budget", "Every arm gets the same number of actions from the same cold start. An agent that explores longer is not a better agent, it is a longer run."],
  ["Screens deduplicated perceptually", "Distinct screens are counted by perceptual hash, so a list that scrolled by two pixels is the same screen and does not inflate anyone's coverage."],
  ["Several seeds, spread reported", "Exploration is stochastic. Each arm runs over consecutive seeds and is reported as mean ± standard deviation, because one lucky seed reads exactly like a capability."],
  ["Failed runs excluded, not zeroed", "If a seed dies — a model quota, a flaky device — it is recorded and left out of the mean rather than averaged in as a zero. The reported n is what was actually measured."],
  ["Defects counted per seed", "A defect found in one seed of five and one found in five of five both add the same +1 to a mean. The per-defect table keeps them apart."],
  ["Environment recorded", "Device, screen geometry, Android version, vision model and app commit ship with the numbers. Overflow defects are screen-size dependent, so a result without its geometry is not comparable to anything."],
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

      <BenchmarkSection />

      <section className="section">
        <h2 className="section-title">How it is measured</h2>
        <p className="section-lede">
          The rules the harness follows, and why each one is there.
        </p>
        <div className="sec-grid">
          {METHOD.map(([h, p]) => (
            <div className="sec-item" key={h}>
              <div><b>{h}</b><span>{p}</span></div>
            </div>
          ))}
        </div>
      </section>

      <section className="section">
        <h2 className="section-title">Run it yourself</h2>
        <p className="section-lede">
          The harness is in the repo and takes a target. Nothing here is a number you have to
          take from us.
        </p>
        <pre className="setup-code">{`python -m gremlin.eval --project ~/Projects/your-app \\
    --actions 30 --repeats 5 --coverage-only --monkey`}</pre>
        <p className="note" style={{ maxWidth: "60ch" }}>
          Results land in <code>runs/eval/&lt;package&gt;/eval.json</code> and are mirrored to
          <code> runs/latest/</code>, which is what this page reads. <Link to="/app/setup">Setup</Link> covers
          getting a device first — a phone, an emulator, or the container.
        </p>
      </section>

      <SiteFooter />
    </div>
  );
}
