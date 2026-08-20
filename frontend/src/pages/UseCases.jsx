import { Link } from "react-router-dom";
import { SiteNav, SiteFooter, PageHead, USE_CASES } from "../lib/SiteChrome.jsx";
import { Bolt } from "../lib/icons.jsx";

/* One long page rather than six thin ones: every use case is the same loop with
 * a different budget, and six near-identical routes would say so six times. */
const DETAIL = {
  regression: {
    when: "You ship nightly and want to know what today broke that yesterday didn't.",
    how: ["Same seed, same action budget, same cold start, every night.", "Findings are keyed by log signature, so last night's list diffs cleanly against tonight's.", "Anything that appears twice has a trace attached both times."],
  },
  "pre-release": {
    when: "A release candidate is cut and nobody has time to walk every screen by hand.",
    how: ["Point it at the RC build with a wider budget than the nightly.", "It heads for controls the nightly runs have never reached.", "You get a list you can triage in one sitting, each item with a repro."],
  },
  flaky: {
    when: "A report says it happens sometimes and nobody can make it happen on demand.",
    how: ["Feed it the captured trace instead of letting it explore.", "The replayer re-runs that exact path from a cold start with no model involved.", "Loop it until the intermittent one shows itself, then keep the frames."],
  },
  coverage: {
    when: "Your suite covers the happy path and nothing else, and you know it.",
    how: ["Coverage bookkeeping records every control the agent has already tried.", "The policy is pushed toward the ones no run has touched.", "What comes back is a map of where your tests were not."],
  },
  triage: {
    when: "A bug lands in the tracker with a screenshot and no steps.",
    how: ["Every Gremlin finding already carries the log line, source file and line.", "The action trace from launch is attached, so the steps are not a guess.", "Hand the trace to whoever picks it up and they can reproduce it first try."],
  },
  fixes: {
    when: "Someone has a patch and you want to know whether it actually fixed it.",
    how: ["Re-run the captured trace against the patched build.", "The signal is gone or it isn't — that gate is not a judgement call.", "Two more gates check the screen still looks like itself and nothing new broke."],
  },
};

export default function UseCases() {
  return (
    <div className="site">
      <SiteNav />
      <PageHead
        eyebrow="Use cases"
        title="Six jobs, one loop"
        lede="Explore, detect, replay. Everything below is that loop with a different budget pointed at a different question."
      />
      <div className="section">
        {USE_CASES.map((u) => {
          const d = DETAIL[u.slug];
          return (
            <article className="usecase" id={u.slug} key={u.slug}>
              <div className="usecase-head">
                <h2>{u.h}</h2>
                <p>{u.p}</p>
              </div>
              <div className="usecase-body">
                <div className="when"><h4>When you reach for it</h4><p>{d.when}</p></div>
                <div className="how">
                  <h4>How it runs</h4>
                  <ul>{d.how.map((h) => <li key={h}>{h}</li>)}</ul>
                </div>
              </div>
            </article>
          );
        })}
      </div>
      <section className="cta-band">
        <div className="box">
          <h2>Try it on one of these</h2>
          <p>Free while it is in beta.</p>
          <div className="cta">
            <Link className="btn btn-primary btn-lg" to="/signup"><Bolt /> Start free</Link>
            <Link className="btn btn-ghost btn-lg" to="/contact">Talk to us &rarr;</Link>
          </div>
        </div>
      </section>
      <SiteFooter />
    </div>
  );
}
