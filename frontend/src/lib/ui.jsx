import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

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

/* Pager for the paged lists. The console does not scroll, so this is how a long
   trace or bug list is moved through. Hidden entirely when everything fits —
   a control that can only be pressed to no effect is noise. */
export function Pager({ page, pages, from, per, total, unit, onPage }) {
  if (pages <= 1) return null;
  const to = Math.min(from + per, total);
  return (
    <div className="pager">
      <button className="btn" onClick={() => onPage(page - 1)} disabled={page === 0}>← Prev</button>
      <span className="pager-count">{from + 1}–{to} of {total} {unit}</span>
      <button className="btn" onClick={() => onPage(page + 1)} disabled={page >= pages - 1}>Next →</button>
    </div>
  );
}

/* Full-size view of one screenshot. Escape or a click anywhere closes it —
   there is nothing to do in here but look. */
export function Lightbox({ src, caption, onClose }) {
  useEffect(() => {
    if (!src) return;
    const onKey = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [src, onClose]);
  if (!src) return null;
  // Rendered into <body>. Inside the page it inherits whatever containing block
  // the view's animation and the scrolling pane establish, and `position:fixed`
  // then resolves against THAT — which is why the frame came out at natural
  // size and you only saw the part you clicked.
  return createPortal((
    <div className="lightbox" onClick={onClose} role="dialog" aria-label="Screenshot">
      <button className="lb-x" onClick={onClose} aria-label="Close">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M6 6l12 12M18 6L6 18" /></svg>
      </button>
      <img src={src} alt={caption || "screenshot"} onClick={(e) => e.stopPropagation()} style={{ cursor: "default" }} />
      {caption && <div className="lb-cap">{caption}</div>}
    </div>
  ), document.body);
}
