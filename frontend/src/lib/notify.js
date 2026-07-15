/* Run-complete feedback: a real OS notification (even when the tab is in the
   background), a tab-title flash, and a short chime. This is the feedback that
   was missing — a 3-second toast is easy to miss. */

let titleTimer = null;

export function notifyRunComplete(summary) {
  const screens = summary?.screens ?? 0;
  const bugs = summary?.bugs ?? 0;
  const secs = summary?.duration_sec;
  const line = `${screens} screens · ${bugs} bug${bugs === 1 ? "" : "s"}` +
    (secs != null ? ` · ${formatDuration(secs)}` : "");

  // 1. OS notification (works when the tab isn't focused).
  if ("Notification" in window && Notification.permission === "granted") {
    try {
      const n = new Notification("Gremlin run complete", {
        body: line,
        icon: "data:image/svg+xml," + encodeURIComponent(FAVICON),
        tag: "gremlin-run",
      });
      n.onclick = () => { window.focus(); n.close(); };
    } catch {}
  }

  // 2. Flash the tab title until the user comes back.
  if (document.hidden) {
    const original = document.title;
    let on = true;
    clearInterval(titleTimer);
    titleTimer = setInterval(() => {
      document.title = on ? "✅ Run complete" : original;
      on = !on;
    }, 900);
    const restore = () => {
      clearInterval(titleTimer);
      document.title = original;
      document.removeEventListener("visibilitychange", onVis);
    };
    const onVis = () => { if (!document.hidden) restore(); };
    document.addEventListener("visibilitychange", onVis);
  }

  // 3. A short two-note chime.
  chime();
}

function chime() {
  try {
    const Ctx = window.AudioContext || window.webkitAudioContext;
    if (!Ctx) return;
    const ctx = new Ctx();
    const notes = [660, 880];
    notes.forEach((f, i) => {
      const o = ctx.createOscillator();
      const g = ctx.createGain();
      o.type = "sine"; o.frequency.value = f;
      o.connect(g); g.connect(ctx.destination);
      const t = ctx.currentTime + i * 0.16;
      g.gain.setValueAtTime(0.0001, t);
      g.gain.exponentialRampToValueAtTime(0.16, t + 0.02);
      g.gain.exponentialRampToValueAtTime(0.0001, t + 0.24);
      o.start(t); o.stop(t + 0.26);
    });
  } catch {}
}

export function formatDuration(s) {
  s = Math.round(s);
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  return `${m}m ${s % 60}s`;
}

const FAVICON = "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>👾</text></svg>";
