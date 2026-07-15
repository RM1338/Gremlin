import { Link } from "react-router-dom";
import Mascot from "../lib/Mascot.jsx";
import { Bolt, Eye, Brain, Bug, Route, Bars, Check } from "../lib/icons.jsx";
import { isAuthed } from "../lib/auth.js";

const FEATURES = [
  { ic: <Eye />, h: "Sees like a user", p: "A vision model reads each screen from a real screenshot and picks the next tap, type, scroll or back — grounded on the accessibility tree, not brittle coordinates." },
  { ic: <Brain />, h: "Reasons about coverage", p: "It remembers where it has been and deliberately heads for sections it hasn't visited, reaching 10× more screens than a random monkey." },
  { ic: <Bug />, h: "Catches real crashes", p: "A logcat oracle scoped to the app pid flags native crashes, Dart exceptions, layout overflows and jank — with the exact file:line." },
  { ic: <Route />, h: "Every bug is reproducible", p: "Each failure ships with the full action trace from launch, so the replayer re-runs the exact path that broke it." },
  { ic: <Bars />, h: "Benchmarked, not hand-waved", p: "Head-to-head against adb monkey on equal budget — the coverage gap is measured, not claimed." },
  { ic: <Bolt />, h: "Free to run", p: "The exploration policy runs on Gemini's free tier, so a full 40-step scan costs you nothing." },
];

const STEPS = [
  { n: "01", h: "Observe", p: "Screenshot + a11y element tree" },
  { n: "02", h: "Decide", p: "Vision model picks one verb" },
  { n: "03", h: "Act", p: "tap · type · scroll · back" },
  { n: "04", h: "Check", p: "Oracle drains scoped logcat" },
];

export default function Landing() {
  const authed = isAuthed();
  return (
    <div className="site">
      <nav className="site-nav">
        <div className="brand"><Mascot size={30} float={false} /> Gremlin<span className="dot">.</span></div>
        <div className="links">
          <a href="#features">Features</a>
          <a href="#how">How it works</a>
          <a href="#proof">Benchmark</a>
        </div>
        <div className="spacer" />
        {authed
          ? <Link className="btn btn-primary" to="/app"><Bolt /> Open console</Link>
          : <><Link className="btn btn-ghost" to="/signin">Sign in</Link><Link className="btn btn-primary" to="/signup">Get started</Link></>}
      </nav>

      <header className="hero-x">
        <div className="mesh" /><div className="grid" />
        <div className="inner">
          <div className="hero-mascot-x"><Mascot size={128} /></div>
          <div className="eyebrow" style={{ justifyContent: "center", display: "flex" }}><Bolt /> Autonomous UI-testing agent</div>
          <h1>Ship apps that <em>don't break</em> in the wild.</h1>
          <p>Gremlin is an AI agent that drives your real Android app like a curious user — exploring every screen,
            catching the crashes your tests miss, and handing you a reproducible trace for each one.</p>
          <div className="cta">
            <Link className="btn btn-primary btn-lg" to={authed ? "/app" : "/signup"}><Bolt /> {authed ? "Open the console" : "Start free"}</Link>
            <a className="btn btn-ghost btn-lg" href="#how">See how it works</a>
          </div>
        </div>
        <div className="hero-preview">
          <div className="bar"><i /><i /><i /></div>
          <img src="/preview.png" alt="Gremlin console preview"
            onError={(e) => { e.currentTarget.parentElement.style.display = "none"; }} />
        </div>
      </header>

      <section className="section" id="features">
        <h2 className="section-title">Testing that thinks</h2>
        <p className="section-lede">Random tap-fuzzers pound the first screen and call it a day. Gremlin reasons about where to go next.</p>
        <div className="features">
          {FEATURES.map((f) => (
            <div className="feature" key={f.h}>
              <div className="ic">{f.ic}</div>
              <h3>{f.h}</h3><p>{f.p}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="section" id="how">
        <h2 className="section-title">One closed loop</h2>
        <p className="section-lede">Observe → decide → act → check, repeated until the budget runs out. The model only decides where to go; a deterministic oracle decides what broke.</p>
        <div className="steps-row">
          {STEPS.map((st) => (
            <div className="step-card" key={st.n}><div className="n">{st.n}</div><h4>{st.h}</h4><p>{st.p}</p></div>
          ))}
        </div>
      </section>

      <section className="section" id="proof">
        <div className="card" style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: 30, alignItems: "center", padding: 36 }}>
          <div>
            <div className="eyebrow"><Bars /> Measured, not claimed</div>
            <h2 style={{ fontSize: 30, letterSpacing: "-.03em", margin: "6px 0 10px" }}>10× the coverage of a random monkey</h2>
            <p className="note" style={{ fontSize: 15, maxWidth: "52ch" }}>On an equal 25-action budget against <code>adb shell monkey</code>, Gremlin reached 10 distinct screens to the monkey's 1 — because it plans, and the monkey guesses.</p>
            <ul style={{ color: "var(--ink-dim)", fontSize: 14, lineHeight: 1.9, marginTop: 14 }}>
              <li><Check style={{ width: 14, height: 14, color: "var(--brand)", verticalAlign: "-2px" }} /> Scoped logcat — no noise from other apps</li>
              <li><Check style={{ width: 14, height: 14, color: "var(--brand)", verticalAlign: "-2px" }} /> Perceptual-hash de-dupe of visited screens</li>
              <li><Check style={{ width: 14, height: 14, color: "var(--brand)", verticalAlign: "-2px" }} /> Anti-loop escape when stuck</li>
            </ul>
          </div>
          <div className="callout" style={{ textAlign: "center" }}>
            <div className="big">10×</div><div className="lbl">more screens</div>
          </div>
        </div>
      </section>

      <section className="cta-band">
        <div className="box">
          <h2>Point it at your app.</h2>
          <p>Plug in a device, press start, and watch it explore.</p>
          <Link className="btn btn-primary btn-lg" to={authed ? "/app" : "/signup"}><Bolt /> {authed ? "Open the console" : "Create your account"}</Link>
        </div>
      </section>

      <footer className="site-foot">
        <Mascot size={24} float={false} /> <b>Gremlin</b>
        <span className="spacer" />
        <span>Built for developers · runs locally against your device</span>
      </footer>
    </div>
  );
}
