import { Link } from "react-router-dom";
import { SiteNav, SiteFooter, PageHead } from "../lib/SiteChrome.jsx";
import { Check, Bolt } from "../lib/icons.jsx";

/* Beta pricing is honest pricing: two tiers that exist and one that is a
 * conversation. Nothing here invents a per-seat number we have not set. */
const PLANS = [
  {
    name: "Local",
    price: "Free",
    note: "Forever, on your own hardware",
    for: "One developer, one machine, a local vision model.",
    has: ["Unlimited runs on your own device", "Local or hosted model, your choice", "Full trace capture and replay", "Screenshots never leave the machine", "Tier-0 and Tier-1 remediation"],
    cta: ["Start free", "/signup"],
  },
  {
    name: "Team",
    price: "Free in beta",
    note: "Priced before general availability",
    for: "A team sharing runs, history and a benchmark.",
    has: ["Everything in Local", "Shared run history and findings", "Nightly scheduled runs", "Benchmark harness with saved arms", "Tier-2 model-authored fixes behind the three gates"],
    cta: ["Get started", "/signup"],
    best: true,
  },
  {
    name: "Self-hosted",
    price: "Talk to us",
    note: "For estates that cannot use a hosted anything",
    for: "Regulated environments and air-gapped labs.",
    has: ["Runs entirely inside your network", "Bring your own model server", "No outbound calls at all", "Deployment help and a support channel"],
    cta: ["Contact us", "/contact"],
  },
];

export default function Pricing() {
  return (
    <div className="site">
      <SiteNav />
      <PageHead
        eyebrow="Pricing"
        title="Free while it is in beta"
        lede="Gremlin is in beta and the numbers are not set. What is on this page is what exists today, and it will change before general availability rather than quietly after it."
      />
      <div className="section">
        <div className="plans">
          {PLANS.map((p) => (
            <article className={"plan" + (p.best ? " best" : "")} key={p.name}>
              {p.best && <span className="tag">Most teams start here</span>}
              <h3>{p.name}</h3>
              <div className="price">{p.price}</div>
              <div className="note">{p.note}</div>
              <p className="for">{p.for}</p>
              <ul>{p.has.map((h) => <li key={h}><Check /> {h}</li>)}</ul>
              <Link className={"btn btn-lg " + (p.best ? "btn-primary" : "btn-ghost")} to={p.cta[1]}>{p.cta[0]}</Link>
            </article>
          ))}
        </div>
        <div className="proof-box">
          <p>
            <b>What we will not do at pricing time.</b> Charge per finding, which rewards a noisy
            oracle. Charge per screenshot, which pushes you off local models. Both would put the
            product's incentives against yours, and the whole design rests on the opposite.
          </p>
        </div>
      </div>
      <section className="cta-band">
        <div className="box">
          <h2>Start on the free tier</h2>
          <p>No card, no seat count, no call.</p>
          <div className="cta"><Link className="btn btn-primary btn-lg" to="/signup"><Bolt /> Start free</Link></div>
        </div>
      </section>
      <SiteFooter />
    </div>
  );
}
