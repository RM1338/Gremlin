import { Link } from "react-router-dom";
import { SiteNav, SiteFooter, PageHead } from "../lib/SiteChrome.jsx";

/* Build notes rather than marketing posts. Each entry is something that was
 * actually decided or measured, dated when it happened. */
const POSTS = [
  {
    date: "2026-08-18",
    tag: "Design",
    h: "Why the model is never asked whether a screen looks broken",
    p: "The question has no checkable answer, so any answer is unfalsifiable — which is exactly the shape of a hallucinated defect. Splitting the agent into a policy that chooses and an oracle that only matches the framework's own log is what makes a finding something you can argue with.",
  },
  {
    date: "2026-08-14",
    tag: "Benchmark",
    h: "The ablation arm is the one that matters",
    p: "Comparing an agent to random tapping flatters it. The honest comparison is against yourself with the model removed, because that isolates what the vision model contributes from what the accessibility grounding and coverage memory were doing anyway.",
  },
  {
    date: "2026-08-09",
    tag: "Remediation",
    h: "Three gates a model-authored fix has to pass",
    p: "The signal has to be gone, the screen has to still look like itself, and nothing new can have broken. A patch that silences a symptom fails the second gate more often than you would like, which is the point of having it.",
  },
  {
    date: "2026-08-02",
    tag: "Grounding",
    h: "Taps land on elements, not coordinates",
    p: "A renamed widget breaks a coordinate script and does not break a run grounded on the accessibility tree. The tree also gives the agent something to remember, which is what stops it pressing the same button forty times.",
  },
];

export default function Blog() {
  return (
    <div className="site">
      <SiteNav />
      <PageHead
        eyebrow="Blog"
        title="Build notes"
        lede="What was decided, what was measured, and what has not been measured yet. Posted when there is something to post."
      />
      <div className="section">
        <div className="posts">
          {POSTS.map((p) => (
            <article className="post" key={p.h}>
              <div className="post-meta">
                <time>{new Date(p.date).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" })}</time>
                <span className="pill">{p.tag}</span>
              </div>
              <h2>{p.h}</h2>
              <p>{p.p}</p>
            </article>
          ))}
        </div>
        <div className="proof-box">
          <p>More as it happens. If you want a specific one written up, <Link to="/contact">say which</Link>.</p>
        </div>
      </div>
      <SiteFooter />
    </div>
  );
}
