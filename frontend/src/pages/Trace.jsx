import { useState } from "react";
import Mascot from "../lib/Mascot.jsx";
import { pad3, screenUrl, Lightbox } from "../lib/ui.jsx";
import { useStore } from "../lib/useStore.js";

export default function Trace() {
  const st = useStore();
  const trace = st.trace?.trace || [];
  // A step's frame is named after the step, so ask for it by name rather than
  // by position in a sorted list. Zipping trace[i] against shots[i] meant one
  // stray file — a leftover from a longer previous run — shifted every frame
  // after it onto the wrong step.
  const shots = new Set(st.screens || []);
  // The trace is the one pane that scrolls: it is the run's log, and paging a
  // log breaks the thing it is for — following a path from start to end.
  const [zoom, setZoom] = useState(null);

  return (
    <>
      <div className="page-head">
        <h1 className="page-title">Trace</h1>
        <p className="page-desc">Every action from app launch, in order — the exact path the replayer re-executes. {trace.length} actions across {st.trace?.distinct_screens ?? 0} distinct screens.</p>
      </div>

      <div className="page-body scrolls">
      {trace.length === 0 ? (
        <div className="empty-state">
          <div className="icon"><Mascot size={132} state="box" /></div>
          <h3>No trace yet</h3><p>Start a run to record the agent's path.</p>
        </div>
      ) : (
        <div className="timeline">
          {trace.map((a, i) => {
            const name = `step_${pad3(i + 1)}.png`;
            const shot = shots.has(name) ? name : null;
            return (
            <div className="tl-item" key={i}>
              <div className={"node" + (a.target_label ? " new" : "")} />
              <div className="tl-row">
                <div className={"tl-thumb" + (shot ? " zoomable" : "")}
                     onClick={shot ? () => setZoom({ src: screenUrl(shot), cap: `step ${pad3(i + 1)} · ${a.verb}` }) : undefined}
                     title={shot ? "Click to see the full frame" : undefined}>
                  {shot && <img loading="lazy" src={screenUrl(shot)} alt="" />}
                </div>
                <div className="tl-main">
                  <div className="tl-head">
                    <span className="tl-step">STEP {pad3(i + 1)}</span>
                    <span className={"tl-verb " + a.verb}>{a.verb}</span>
                    {/* This is the CONTROL the step acted on, not the screen it
                        was on — styled as a screen name it read as a caption for
                        the frame beside it, which is a frame of the screen the
                        control lives on. Different things. */}
                    {a.target_label && <span className="tl-target-chip">→ {a.target_label}</span>}
                  </div>
                  <div className="tl-reason">{a.reason || "—"}</div>
                  {a.text && <div className="tl-target">typed <b>"{a.text}"</b></div>}
                  {a.direction && <div className="tl-target">scrolled <b>{a.direction}</b></div>}
                </div>
              </div>
            </div>
            );
          })}
        </div>
      )}
      </div>
      <Lightbox src={zoom?.src} caption={zoom?.cap} onClose={() => setZoom(null)} />
    </>
  );
}
