import { useEffect, useRef, useState } from "react";

export const pad3 = (n) => String(n).padStart(3, "0");
export const sevClass = (s) => (s === "crash" ? "crash" : s === "layout" ? "layout" : "hang");

/* Animated count-up for a number. */
export function CountUp({ to, dur = 900, suffix = "" }) {
  const [v, setV] = useState(0);
  const raf = useRef(0);
  useEffect(() => {
    const t0 = performance.now();
    const tick = (t) => {
      const p = Math.min(1, (t - t0) / dur);
      setV(Math.round(to * (1 - Math.pow(1 - p, 3))));
      if (p < 1) raf.current = requestAnimationFrame(tick);
    };
    raf.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf.current);
  }, [to, dur]);
  return <>{v}{suffix}</>;
}

export function Spark() {
  return (
    <svg className="spark" viewBox="0 0 110 60" fill="none" stroke="var(--brand)" strokeWidth="2" opacity=".6">
      <path d="M0 50 Q20 48 30 38 T55 30 T80 16 T110 8" />
    </svg>
  );
}

/* Screenshot served by the FastAPI runner (falls back to a static /screens dir). */
export function screenUrl(name) { return `/api/screen/${name}`; }
