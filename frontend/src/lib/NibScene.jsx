import { useEffect, useRef, useState } from "react";
import Mascot, { Bug } from "./Mascot.jsx";

/* The "Meet Nib" set piece, and the only place Nib animates on the site.
 *
 * The scene's CSS lives in index.css, not in a <style> element here. An inline
 * <style> renders its own source as visible text the moment anything stops
 * treating it as a stylesheet, which is exactly what it did on the landing
 * page. The measurements below are handed over as custom properties instead.
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
    <div className={`nibscene ${live || still ? "live" : ""}`} ref={host} aria-hidden="true"
         style={{ "--floor": `${FLOOR}px`, "--mark-w": `${MARK_W}px`,
                  "--paw-x": `${PAW_X}px`, "--paw-y": `${PAW_Y}px`, "--bug": `${BUG_PX}px` }}>

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
