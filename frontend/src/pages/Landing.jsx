import { Link } from "react-router-dom";
import Mascot from "../lib/Mascot.jsx";
import NibScene from "../lib/NibScene.jsx";
import { SiteNav, SiteFooter, DotField, FaqList, USE_CASES } from "../lib/SiteChrome.jsx";
import { Bolt, Eye, Bug, Route, Bars, Check, Brain, Clock, Doc } from "../lib/icons.jsx";
import { isAuthed } from "../lib/auth.js";

/* The page is built around the one idea the product actually rests on: the
 * model decides where to go, the log decides what is broken.
 *
 * Nothing here claims a number that has not been measured. The benchmark
 * section renders whatever the last real run produced and says plainly when
 * there is nothing yet, because a landing page asserting "10x more screens"
 * before the ablation has run is the fastest way to lose a reader who checks.
 */

const STACK = ["Flutter", "React Native", "Android", "adb + logcat", "Local models", "Real devices", "Emulators"];

const MODES = [
  {
    // the two halves get two different characters: an adventurer scouting ground
    // nobody has mapped, and the detective reading back what it proved.
    state: "explorer",
    tag: "The policy",
    h: "It explores like a curious user",
    p: "A vision model reads the screen and picks the next tap, type, scroll or back — grounded on the accessibility tree, not guessed pixel coordinates. It tracks every control it has already tried and deliberately heads for the ones it hasn't, so it never loops on one button.",
  },
  {
    state: "trace",
    tag: "The oracle",
    h: "The log decides what broke",
    p: "Detection never asks a model whether a screen looks wrong — that question has no checkable answer. It matches the framework's own words in logcat: a RenderFlex overflow, an unhandled exception, a native crash. Either the string is there or it isn't.",
  },
];

const CARDS = [
  { ic: <Route />, h: "Traces that replay", p: "Each failure carries the exact action trace from launch, and the replayer re-runs it with no model in the loop. A repro you can hand to someone else." },
  { ic: <Doc />, h: "Reports you can check", p: "Every finding cites the log line that produced it, with source file and line. Nothing is inferred, so there is nothing to take on trust." },
  { ic: <Check />, h: "Fixes that must earn it", p: "A model-authored patch passes only if the signal is gone, the screen still looks like itself, and nothing new broke. Otherwise it is reverted." },
];

const FEATURES = [
  { ic: <Eye />, h: "Grounded in the real tree", p: "Taps land on actual elements with real labels and centres, so a renamed widget doesn't break the run the way it breaks a script." },
  { ic: <Bug />, h: "Findings you can check", p: "Every report cites the log line that produced it, with the source file and line." },
  { ic: <Bars />, h: "Measured against a baseline", p: "The same action budget as Android's own Monkey, and against Gremlin with the model removed — so the model's contribution is a number, not a claim." },
  { ic: <Brain />, h: "Your model, your hardware", p: "The policy speaks the OpenAI chat-completions shape, so a local model or a hosted one is a config change." },
  { ic: <Clock />, h: "Runs on a budget", p: "Give it an action count and a wall clock. It spends both on the screens it has not seen." },
  { ic: <Bolt />, h: "Three-tier remediation", p: "Report, deterministic retry, then a model-authored fix behind guard, rebuild and replay gates." },
];

const STEPS = [
  { n: "01", h: "Point it at a build", p: "An APK or a device already running your app. No instrumentation, no test IDs to add." },
  { n: "02", h: "Give it a budget", p: "An action count and a time limit. Pick a model, local or hosted." },
  { n: "03", h: "Read the trace", p: "Findings arrive with the log line that proved them and a path that replays them." },
];

const SECURITY = [
  ["Screenshots never have to leave the building", "Point the provider at a local model and every frame stays on your hardware."],
  ["No training on your runs", "Artifacts stay in your own runs directory. Nothing is uploaded to train anything."],
  ["Short-lived, repo-scoped tokens", "Tier-2 fixes use credentials you enter when prompted, scoped to the one repo."],
  ["Everything is reproducible", "Each run is a directory of frames, traces and logs you can re-read without the tool."],
];

export default function Landing() {
  const authed = isAuthed();
  return (
    <div className="site">
      <SiteNav />

      <header className="hero-x">
        <DotField />
        <div className="inner">
          <div className="eyebrow"><Bolt /> Autonomous UI testing for Flutter and React Native</div>
          <h1>It breaks your app <em>on purpose.</em></h1>
          <p>
            Gremlin drives a real Android device like a curious user &mdash; exploring every screen it
            can reach, and filing a reproducible report the moment the framework admits something
            went wrong.
          </p>
          <div className="cta">
            <Link className="btn btn-primary btn-lg" to={authed ? "/app" : "/signup"}>
              <Bolt /> Start free
            </Link>
            <Link className="btn btn-ghost btn-lg" to="/use-cases">See use cases &rarr;</Link>
          </div>
        </div>

        <div className="hero-preview">
          <div className="bar"><i /><i /><i /><span>gremlin &mdash; run 0184 &middot; com.example.shop</span></div>
          <div className="shot">
            <div className="shot-side">
              {["Overview", "Live", "Trace", "Bugs", "Benchmark"].map((r, i) => (
                <span key={r} className={i === 2 ? "on" : ""}>{r}</span>
              ))}
            </div>
            <div className="shot-main">
              <div className="shot-row"><b>step 19</b> tap &middot; Checkout &middot; (540, 1284)</div>
              <div className="shot-row bad"><b>RenderFlex overflowed</b> by 42 px &middot; cart_summary.dart:118</div>
              <div className="shot-row"><b>step 20</b> back</div>
              <div className="shot-row"><b>step 21</b> tap &middot; Promo code</div>
              <div className="shot-bars">
                {[38, 62, 44, 81, 55, 70, 33, 58, 76, 41, 66, 49].map((h, i) => (
                  <i key={i} style={{ height: h + "%" }} />
                ))}
              </div>
            </div>
          </div>
        </div>
      </header>

      <section className="strip">
        <p>Works with the stack your app already ships on</p>
        <div className="strip-row">{STACK.map((s) => <span key={s}>{s}</span>)}</div>
      </section>

      {/* the companion section — Nib's only appearance, and the only animation */}
      <section className="section meet" id="nib">
        <div className="meet-copy">
          <div className="eyebrow">Meet Nib</div>
          <h2>Someone has to go looking for them</h2>
          <p>
            Nib is the character on the front of a very literal program. It walks into your app
            with no map, tries the controls a person would try, and gets rid of every defect it
            can provoke &mdash; one at a time, each with the receipt that proves it was there.
          </p>
          <p className="fine">
            Two modes, because the product has two halves: the policy that decides where to go,
            and the oracle that decides what broke.
          </p>
          <Link className="btn btn-ghost" to="/about">The thinking behind it &rarr;</Link>
        </div>
        <NibScene />
      </section>

      <section className="section" id="modes">
        <h2 className="section-title">One agent, two jobs</h2>
        <p className="section-lede">
          Most AI testing tools ask a model &ldquo;does this look broken?&rdquo; &mdash; a question with no
          checkable answer, which is why they hallucinate defects. Gremlin splits the work in two
          and only lets the model do the half where being wrong is cheap.
        </p>
        <div className="modes">
          {MODES.map((m) => (
            <article className="mode" key={m.tag}>
              <div className="mode-face"><Mascot size={104} state={m.state} bugs={false} /></div>
              <span className="pill brand">{m.tag}</span>
              <h3>{m.h}</h3>
              <p>{m.p}</p>
            </article>
          ))}
        </div>
        <p className="split-line">
          The model decides <em>where to go</em>. The log decides <em>what is broken</em>.
        </p>
      </section>

      <section className="section">
        <h2 className="section-title">What comes out of a run</h2>
        <p className="section-lede">Three things, each one checkable without trusting the tool.</p>
        <div className="features">
          {CARDS.map((c) => (
            <article className="feature" key={c.h}>
              <div className="ic">{c.ic}</div>
              <h3>{c.h}</h3>
              <p>{c.p}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="section" id="uses">
        <h2 className="section-title">What teams point it at</h2>
        <p className="section-lede">Six jobs it already does, all of them the same loop underneath.</p>
        <div className="usegrid">
          {USE_CASES.map((u) => (
            <Link className="usecard" key={u.slug} to={"/use-cases#" + u.slug}>
              <h3>{u.h}</h3>
              <p>{u.p}</p>
              <span className="see">See how &rarr;</span>
            </Link>
          ))}
        </div>
      </section>

      <section className="section">
        <h2 className="section-title">Everything else it does</h2>
        <div className="features">
          {FEATURES.map((f) => (
            <article className="feature" key={f.h}>
              <div className="ic">{f.ic}</div>
              <h3>{f.h}</h3>
              <p>{f.p}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="section">
        <h2 className="section-title">Get started in minutes</h2>
        <p className="section-lede">No test IDs to add, no page objects to write, no scripts to maintain.</p>
        <div className="steps-row three">
          {STEPS.map((s) => (
            <article className="step-card" key={s.n}>
              <span className="n">{s.n}</span>
              <h4>{s.h}</h4>
              <p>{s.p}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="section" id="proof">
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
            The second arm is the honest one: it isolates what the vision model actually
            contributes, rather than crediting it for what the coverage bookkeeping does.
          </p>
          <Link className="btn btn-primary" to="/benchmark">See the numbers &rarr;</Link>
        </div>
      </section>

      <section className="section">
        <h2 className="section-title">Where your app&rsquo;s screens go</h2>
        <p className="section-lede">Nowhere, if you don&rsquo;t want them to.</p>
        <div className="sec-grid">
          {SECURITY.map(([h, p]) => (
            <div className="sec-item" key={h}>
              <Check />
              <div><b>{h}</b><span>{p}</span></div>
            </div>
          ))}
        </div>
      </section>

      <section className="section faq">
        <h2 className="section-title">Questions</h2>
        <FaqList />
      </section>

      <section className="cta-band">
        <div className="box">
          <h2>Point Gremlin at your app</h2>
          <p>Free while it is in beta. Bring a build and a budget.</p>
          <div className="cta">
            <Link className="btn btn-primary btn-lg" to={authed ? "/app" : "/signup"}><Bolt /> Start free</Link>
            <Link className="btn btn-ghost btn-lg" to="/contact">Talk to us &rarr;</Link>
          </div>
        </div>
      </section>

      <SiteFooter />
    </div>
  );
}
