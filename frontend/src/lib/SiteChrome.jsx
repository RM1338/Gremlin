import { useEffect, useState } from "react";
import { Link, NavLink, useLocation } from "react-router-dom";
import Logo from "./Logo.jsx";
import { isAuthed } from "./auth.js";

/* One nav and one footer for every marketing page, so a route added later
 * cannot end up with its own slightly different header. */

export const USE_CASES = [
  { slug: "regression", h: "Nightly regression sweeps", p: "Run the same budget every night and diff what broke against last night." },
  { slug: "pre-release", h: "Pre-release smoke runs", p: "Point it at a release build and let it walk every screen before you ship it." },
  { slug: "flaky", h: "Reproducing flaky reports", p: "Replay a captured trace from a cold start until the intermittent one shows itself." },
  { slug: "coverage", h: "Finding the screens nobody tests", p: "Coverage bookkeeping heads for controls no run has touched yet." },
  { slug: "triage", h: "Triage with a real repro", p: "Every finding arrives with the log line and the exact path back to it." },
  { slug: "fixes", h: "Grading candidate fixes", p: "Re-run the captured trace against a patch and keep only what survives." },
];

/* The router does neither of these on its own: a new route keeps the old scroll
 * position, and a #hash in a link to another page is ignored entirely. Lives in
 * the nav because the nav is the one thing every marketing page renders. */
function useHashScroll() {
  const { pathname, hash } = useLocation();
  useEffect(() => {
    const r = requestAnimationFrame(() => {
      const el = hash && document.querySelector(hash);
      if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
      else if (!hash) window.scrollTo(0, 0);
    });
    return () => cancelAnimationFrame(r);
  }, [pathname, hash]);
}

/* Sections rise into place as you reach them.
 *
 * Two deliberate choices. The `rv` class is added by script rather than sitting
 * in the markup, so with JS off nothing is ever left invisible — it simply does
 * not animate. And this sweeps on scroll rather than using IntersectionObserver:
 * a fast flick can carry a short section past between two observer samples, and
 * a section stranded at opacity 0 is a far worse bug than a missing animation.
 * A position check that runs on every scroll cannot skip one. */
function useReveal() {
  const { pathname } = useLocation();
  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    let pending = [...document.querySelectorAll(".section, .strip, .cta-band .box, .site-head .inner")];
    if (!pending.length) return;
    pending.forEach((e) => e.classList.add("rv"));

    const sweep = () => {
      pending = pending.filter((e) => {
        if (e.getBoundingClientRect().top > window.innerHeight * 0.9) return true;
        e.classList.add("rv-in");
        return false;
      });
      if (!pending.length) window.removeEventListener("scroll", sweep);
    };
    const raf = requestAnimationFrame(sweep); // whatever is already on screen
    window.addEventListener("scroll", sweep, { passive: true });
    return () => { cancelAnimationFrame(raf); window.removeEventListener("scroll", sweep); };
  }, [pathname]);
}

const FAQ = [
  ["Does it need my source code?", "Not to find defects. Exploration and detection work against a running build. Source is only needed for Tier-2, where a fix has to be written and rebuilt."],
  ["How is this different from a monkey tester?", "A monkey taps at random coordinates. Gremlin reads the accessibility tree, so a tap lands on a real control with a real label, and it remembers which controls it has already tried."],
  ["Does a model decide what counts as a bug?", "No. That is the whole design. The model chooses where to go; the framework's own log decides what broke. A model is never asked whether a screen looks wrong."],
  ["Which frameworks are supported?", "Flutter and React Native today, through a platform layer that normalises the accessibility tree and the log signatures for each."],
  ["Can it run without internet?", "Yes. With a local vision model the whole loop — explore, detect, replay — runs on your own hardware."],
  ["What does a finding actually contain?", "The log line and its source file and line, the frames either side of it, and the full action trace from launch so it can be replayed."],
  ["Will it change my code?", "Only at Tier 2, only if you enable it, and only if the patch passes the guard, rebuild and replay gates. Otherwise it is reverted."],
  ["Is there a benchmark?", "There is a harness: three arms, one action budget, the same cold start. Results are pending and will be published here once they have been run over enough seeds."],
];

export function FaqList() {
  return (
    <div className="faq-list">
      {FAQ.map(([q, a]) => (
        <details key={q}>
          <summary>{q}</summary>
          <p>{a}</p>
        </details>
      ))}
    </div>
  );
}

export function SiteNav() {
  const authed = isAuthed();
  useHashScroll();
  useReveal();

  const [scrolled, setScrolled] = useState(false);
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 4);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <nav className={`site-nav${scrolled ? " scrolled" : ""}`}>
      <Link className="brand" to="/">
        <Logo size={26} /> Gremlin<span className="badge-beta">Beta</span>
      </Link>

      <div className="links">
        <div className="has-menu">
          <NavLink to="/use-cases">Use Cases <span className="caret">▾</span></NavLink>
          <div className="menu">
            {USE_CASES.map((u) => (
              <Link key={u.slug} to={`/use-cases#${u.slug}`}>
                <b>{u.h}</b><span>{u.p}</span>
              </Link>
            ))}
          </div>
        </div>
        <NavLink to="/pricing">Pricing</NavLink>
        <NavLink to="/benchmark">Benchmark</NavLink>
        <NavLink to="/blog">Blog</NavLink>
        <NavLink to="/about">About</NavLink>
        <NavLink to="/contact">Contact</NavLink>
      </div>

      {/* one grid item, not three — otherwise the third column takes the first
          of them and the rest wrap onto a second row */}
      <div className="nav-actions">
        {authed
          ? <Link className="btn btn-primary" to="/app">Open console</Link>
          : <>
              <Link className="nav-account" to="/signin">Account</Link>
              <Link className="btn btn-primary" to="/signup">Get started</Link>
            </>}
      </div>
    </nav>
  );
}

const FOOT = [
  ["Product", [["Use cases", "/use-cases"], ["Pricing", "/pricing"], ["How it thinks", "/#modes"], ["Benchmark", "/#proof"]]],
  ["Company", [["About", "/about"], ["Blog", "/blog"], ["Contact", "/contact"]]],
  ["Start", [["Get started", "/signup"], ["Sign in", "/signin"], ["Console", "/app"]]],
];

export function SiteFooter() {
  return (
    <footer className="site-foot">
      <div className="foot-inner">
        <div className="foot-brand">
          <div className="brand"><Logo size={24} /> Gremlin</div>
          <p>Autonomous UI testing, grounded in the log.</p>
        </div>
        {FOOT.map(([h, links]) => (
          <div className="foot-col" key={h}>
            <h5>{h}</h5>
            {links.map(([label, to]) => <Link key={label} to={to}>{label}</Link>)}
          </div>
        ))}
      </div>
      <div className="foot-rule">
        <span>© {new Date().getFullYear()} Gremlin</span>
        <span className="spacer" />
        <span>Beta — nothing here claims a number that has not been measured.</span>
      </div>
    </footer>
  );
}

/* The background texture, in place of the old teal glow: two dot lattices at
 * different scales drifting past each other, masked to a soft pool so the page
 * has depth without anything to read. */
export function DotField({ soft = false }) {
  return <div className={`dotfield${soft ? " soft" : ""}`} aria-hidden="true" />;
}

export function PageHead({ eyebrow, title, lede, children }) {
  return (
    <header className="site-head">
      <DotField soft />
      <div className="inner">
        {eyebrow && <div className="eyebrow">{eyebrow}</div>}
        <h1>{title}</h1>
        {lede && <p>{lede}</p>}
        {children}
      </div>
    </header>
  );
}
