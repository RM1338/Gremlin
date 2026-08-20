import { useEffect, useRef, useState } from "react";
import Mascot, { Bug } from "./Mascot.jsx";

/* The "Meet Nib" set piece, and the only place Nib animates on the site.
 *
 * It plays one short story rather than looping decoration: Nib holds his mark,
 * shifting his weight about on it, defects fly in at him, he swats every one
 * out of the air, and he is pleased with himself for a moment before it starts
 * again. That is the product's loop in three beats — encounter, clear, report.
 *
 * The scene only runs while it is on screen, and not at all under
 * prefers-reduced-motion, where it settles on the final frame instead.
 */

// fx/fy: where each defect enters, as an offset from the paw it ends on. Kept
// inside the stage so nothing can push the page sideways on a narrow screen.
const BUGS = [
  { fx: 250, fy: -96, dur: 2.0, delay: 0.15 },
  { fx: 300, fy: 44, dur: 2.4, delay: 0.5 },
  { fx: 230, fy: 118, dur: 2.1, delay: 0.95 },
  { fx: 310, fy: -34, dur: 2.6, delay: 1.3 },
];

/* Nib is 168 wide, so 200 tall, sitting 34 above the stage floor. The swatting
   paw is at (200,132) in his 240x286 viewBox, which puts it 56 right of centre
   and 142 up from the floor. Every defect flies to exactly that point. */
const MARK_W = 168, MARK_H = Math.round(168 * 1.19), FLOOR = 34;
const PAW_X = Math.round((200 / 240) * MARK_W - MARK_W / 2);
const PAW_Y = Math.round(FLOOR + MARK_H - (132 / 286) * MARK_H);
const BUG_PX = 40;

const CHEER_MS = 2100;  // how long he gets to enjoy it
const RESET_MS = 700;

export default function NibScene() {
  const [run, setRun] = useState(0);      // bumping this restarts every animation
  const [phase, setPhase] = useState("swat"); // swat -> done
  const [cleared, setCleared] = useState([]);
  const host = useRef(null);
  const timers = useRef([]);

  const still = typeof window !== "undefined" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // only play while visible — an off-screen loop is just a battery drain
  const [live, setLive] = useState(false);
  useEffect(() => {
    if (!host.current || still) return;
    const io = new IntersectionObserver(([e]) => setLive(e.isIntersecting), { threshold: 0.25 });
    io.observe(host.current);
    return () => io.disconnect();
  }, [still]);

  useEffect(() => {
    if (!live || still) return;
    setPhase("swat");
    setCleared([]);
  }, [live, run, still]);

  // Every defect accounted for -> he gets his moment. Deliberately two effects:
  // one that owns the phase and one that owns the reset timer. Combined, setting
  // the phase changed this effect's own deps and its cleanup cancelled the very
  // timer it had just scheduled, so the scene played once and stopped.
  useEffect(() => {
    if (phase === "swat" && cleared.length === BUGS.length) setPhase("done");
  }, [cleared, phase]);

  useEffect(() => {
    if (phase !== "done") return;
    const t = setTimeout(() => setRun((r) => r + 1), CHEER_MS + RESET_MS);
    return () => clearTimeout(t);
  }, [phase]);

  const state = phase === "swat" && !still ? "chaos" : "success";

  return (
    <div className={`nibscene ${live || still ? "live" : ""}`} ref={host} aria-hidden="true">
      <style>{`
        .nibscene { position: relative; height: 268px; display: grid; place-items: center;
          overflow: hidden; }
        .nibscene .stage { position: relative; width: 100%; max-width: 560px; height: 100%; }
        .nibscene .nib-mark {
          position: absolute; left: 50%; bottom: ${FLOOR}px;
          margin-left: ${-MARK_W / 2}px; width: ${MARK_W}px;
        }
        /* He holds his mark and shifts about on it. Long and uneven on purpose —
           a short even cycle reads as a machine idling, not as someone waiting. */
        .nibscene.live .nib-mark { animation: nib-shift 9.5s ease-in-out infinite; }
        @keyframes nib-shift {
          0%,100% { transform: translate(0, 0) }
          17%     { transform: translate(-13px, -3px) }
          38%     { transform: translate(7px, 2px) }
          59%     { transform: translate(-5px, -6px) }
          78%     { transform: translate(11px, -1px) }
        }

        /* Each defect flies from off-stage to the paw and pops on arrival. The
           flight time IS the timer — no second schedule to drift out of sync. */
        .nibscene .swarmer {
          position: absolute; left: 50%; bottom: ${PAW_Y - BUG_PX / 2}px;
          margin-left: ${PAW_X - BUG_PX / 2}px;
          width: ${BUG_PX}px; height: ${BUG_PX}px; opacity: 0;
          transition: opacity .18s, scale .18s;
        }
        .nibscene.live .swarmer { animation: bug-in var(--dur) cubic-bezier(.5,.1,.6,.9) var(--delay) both; }
        .nibscene .swarmer.gone { opacity: 0 !important; scale: 2.1; }
        @keyframes bug-in {
          0%   { opacity: 0; transform: translate(var(--fx), var(--fy)) }
          12%  { opacity: 1 }
          55%  { transform: translate(calc(var(--fx) * .34), calc(var(--fy) * .5 - 26px)) }
          100% { opacity: 1; transform: translate(0, 0) }
        }

        .nibscene .ground {
          position: absolute; left: 18%; right: 18%; bottom: 38px; height: 1px;
          background: var(--hair-soft);
        }
        @media (prefers-reduced-motion: reduce) {
          .nibscene .swarmer { display: none; }
          .nibscene.live .nib-mark { animation: none; }
        }
      `}</style>

      <div className="stage">
        <div className="ground" />

        {!still && BUGS.map((b, i) => (
          <svg
            key={`${run}-${i}`}
            viewBox="-17 -17 34 34"
            className={`swarmer${cleared.includes(i) ? " gone" : ""}`}
            style={{ "--fx": `${b.fx}px`, "--fy": `${b.fy}px`, "--dur": `${b.dur}s`, "--delay": `${b.delay}s` }}
            onAnimationEnd={() => setCleared((c) => (c.includes(i) ? c : [...c, i]))}
          >
            <Bug />
          </svg>
        ))}

        <div className="nib-mark" key={run}>
          <Mascot size={MARK_W} state={state} bugs={false} />
        </div>
      </div>
    </div>
  );
}
