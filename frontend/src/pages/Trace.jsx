import Mascot from "../lib/Mascot.jsx";
import { pad3, screenUrl } from "../lib/ui.jsx";
import { useStore } from "../lib/useStore.js";

export default function Trace() {
  const st = useStore();
  const trace = st.trace?.trace || [];
  const stepShots = (st.screens || []).filter((n) => n.startsWith("step_")).sort();

  return (
    <>
      <div className="page-head">
        <h1 className="page-title">Trace</h1>
        <p className="page-desc">Every action from app launch, in order — the exact path the replayer re-executes. {trace.length} actions across {st.trace?.distinct_screens ?? 0} distinct screens.</p>
      </div>

      {trace.length === 0 ? (
        <div className="empty-state">
          <div className="icon"><Mascot size={80} float={false} /></div>
          <h3>No trace yet</h3><p>Start a run to record the agent's path.</p>
        </div>
      ) : (
        <div className="timeline">
          {trace.map((a, i) => (
            <div className="tl-item" key={i}>
              <div className={"node" + (a.target_label ? " new" : "")} />
              <div className="tl-row">
                <div className="tl-thumb">{stepShots[i] && <img loading="lazy" src={screenUrl(stepShots[i])} alt="" />}</div>
                <div className="tl-main">
                  <div className="tl-head">
                    <span className="tl-step">STEP {pad3(i + 1)}</span>
                    <span className={"tl-verb " + a.verb}>{a.verb}</span>
                    {a.target_label && <span className="tl-screen">{a.target_label}</span>}
                  </div>
                  <div className="tl-reason">{a.reason || "—"}</div>
                  {a.text && <div className="tl-target">typed <b>"{a.text}"</b></div>}
                  {a.direction && <div className="tl-target">scrolled <b>{a.direction}</b></div>}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </>
  );
}
