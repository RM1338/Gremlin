import { Link } from "react-router-dom";
import { SiteNav, SiteFooter, PageHead } from "../lib/SiteChrome.jsx";
import { Bolt } from "../lib/icons.jsx";

const BELIEFS = [
  ["A finding you cannot check is not a finding", "Every defect Gremlin reports cites the log line that produced it, with the file and line. If the string is not there, the finding does not exist."],
  ["The model gets the half where being wrong is cheap", "Choosing where to tap next is a guess either way. Deciding what counts as broken is not, so a model is never asked to."],
  ["A repro beats a description", "A screenshot and a paragraph is a puzzle. An action trace that replays from a cold start is an answer."],
  ["Numbers get published or they get called pending", "The benchmark harness exists and the results do not yet. Saying so is cheaper than losing a reader who checks."],
];

export default function About() {
  return (
    <div className="site">
      <SiteNav />
      <PageHead
        eyebrow="About"
        title="Built because the alternative was writing the scripts by hand"
        lede="Gremlin started as a question about whether an agent could find real defects in a real app without being told where to look, and stayed honest by refusing to let a model decide what counts as one."
      />
      <div className="section">
        <div className="prose">
          <h2>The problem with asking a model what looks broken</h2>
          <p>
            A UI testing agent has two jobs that feel like one: work out where to go next, and work
            out whether what it is looking at is wrong. The first is a search problem, and a vision
            model is genuinely good at it — a wrong guess costs one wasted tap. The second is a
            correctness problem, and a model answering it produces something nobody can argue with,
            because there is no ground truth to check the answer against.
          </p>
          <p>
            So Gremlin does not ask. The policy picks the next action from a screenshot and the
            accessibility tree. The oracle reads the app's own logcat and matches signatures the
            framework itself emits — a RenderFlex overflow, an unhandled exception, a native crash.
            Either the string is there or it is not, and a finding is a quotation rather than an
            opinion.
          </p>
          <h2>What that buys</h2>
          <p>
            Because detection is deterministic, a fix can be graded by re-execution rather than by
            review. Because every action is recorded, a defect found at step 19 replays from a cold
            start with no model in the room. And because the ablation arm removes the model rather
            than the whole agent, the model's contribution ends up being a number rather than a
            claim in a deck.
          </p>
        </div>
        <div className="beliefs">
          {BELIEFS.map(([h, p]) => (
            <div className="belief" key={h}><h3>{h}</h3><p>{p}</p></div>
          ))}
        </div>
      </div>
      <section className="section who">
        <h2 className="section-title">Who is building it</h2>
        <p className="section-lede">One person, in the open, with the benchmark unfinished and said so.</p>
        <div className="who-card">
          <div>
            <b>Ronel</b>
            <span>Building Gremlin — the agent, the console, and the honest bits of this website.</span>
          </div>
          <a className="btn btn-ghost" href="https://www.linkedin.com/in/ronelm"
             target="_blank" rel="noopener noreferrer">Connect on LinkedIn &rarr;</a>
        </div>
      </section>

      <section className="cta-band">
        <div className="box">
          <h2>See whether it holds up on your app</h2>
          <p>That is the only test of any of this.</p>
          <div className="cta">
            <Link className="btn btn-primary btn-lg" to="/signup"><Bolt /> Start free</Link>
            <Link className="btn btn-ghost btn-lg" to="/blog">Read the build notes &rarr;</Link>
          </div>
        </div>
      </section>
      <SiteFooter />
    </div>
  );
}
