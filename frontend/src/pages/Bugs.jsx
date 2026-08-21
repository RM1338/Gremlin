import { useState } from "react";
import { Bug, Check, Copy, Doc, Wrench, Spark2, X } from "../lib/icons.jsx";
import Mascot from "../lib/Mascot.jsx";
import { sevClass, screenUrl, Pager, Lightbox } from "../lib/ui.jsx";
import { usePaged } from "../lib/usePaged.js";
import { useStore } from "../lib/useStore.js";
import { startFix } from "../lib/store.js";

// What the server is doing between the click and the verdict. Minutes, not
// seconds — so the stage names are the progress bar.
const PHASES = {
  starting: "Starting…",
  patching: "The agent is patching the source…",
  guard: "Guarding the diff against symptom-silencers…",
  rebuild: "Rebuilding and installing the APK…",
  replay: "Replaying the trace that caused the bug…",
  probe: "Re-exploring the app for new breakage…",
};

// The three gates the Tier-2 autofix must clear, in pipeline order. Names match
// gremlin/gates.py so the UI stays honest about what actually runs.
const GATES = [
  ["signal-gone", "The bug's log signal no longer fires on replay"],
  ["screen-looks-same", "The screen still renders — no widget deleted or blanked"],
  ["no-new-breakage", "A fresh re-exploration surfaces no new signals"],
];

export default function Bugs() {
  const st = useStore();
  const bugs = st.trace?.bugs || [];
  // One bug card plus its gap, measured on real reports rather than guessed:
  // 350-390px, because a card carries a screenshot, the matched log line and
  // the repro steps. 168 was optimistic and put three on a page with room for
  // one, which is why every card came out with its content cut.
  const pg = usePaged(bugs, 400);

  return (
    <>
      <div className="page-head">
        <h1 className="page-title">Bugs</h1>
        <p className="page-desc">Crashes, layout overflows and jank the oracle caught by draining logcat scoped to the app pid. Each bug carries a three-tier remediation ladder — the <b>report</b>, a portable <b>fix prompt</b>, and the <b>autofix</b> pipeline.</p>
      </div>

      <div className="page-body">
      {bugs.length === 0 ? (
        <div className="empty-state">
          <div className="icon"><Mascot size={132} state="success" /></div>
          <h3>No bugs — clean run</h3>
          <p>Gremlin explored the app end-to-end without tripping the oracle. Plant a defect to see detection light up.</p>
        </div>
      ) : (
        <div className="bug-list" ref={pg.ref}>
          {pg.slice.map((b, i) => <BugCard key={pg.from + i} bug={b} n={pg.from + i + 1} backend={st.fixBackend} />)}
        </div>
      )}
      <Pager {...pg} total={bugs.length} unit="bugs" onPage={pg.setPage} />
      </div>
    </>
  );
}

function BugCard({ bug: b, n, backend }) {
  const [tier, setTier] = useState(0);
  const [zoom, setZoom] = useState(null);
  const shot = b.screenshot ? b.screenshot.split("/").pop() : null;
  const sev = sevClass(b.severity);

  return (
    <div className={"card bug " + sev}>
      <div className="bug-id">
        <div className="bug-headrow">
          <span className={"sev-pill " + sev}><Bug /> {b.severity}</span>
          <span className="bug-step">found at step {b.step} · {b.kind}</span>
        </div>
        <div className="bug-title">{b.title || b.kind}</div>
        {b.dart_file && <div className="bug-loc">at <b>{b.dart_file}:{b.dart_line}</b></div>}
        {shot && (
          <div className="bug-shot zoomable" title="Click to see the full frame"
               onClick={() => setZoom(screenUrl(shot))}>
            <img loading="lazy" src={screenUrl(shot)} alt="screen at failure" />
          </div>
        )}
      </div>

      <div className="tier-col">
        <div className="tier-tabs" role="tablist">
          <TierTab n={0} label="Report" active={tier} set={setTier} icon={<Doc />} />
          <TierTab n={1} label="Fix prompt" active={tier} set={setTier} icon={<Spark2 />} />
          <TierTab n={2} label="Autofix" active={tier} set={setTier} icon={<Wrench />} />
        </div>

        <div className="tier-body">
          {tier === 0 && <Tier0 bug={b} />}
          {tier === 1 && <Tier1 bug={b} />}
          {tier === 2 && <Tier2 bug={b} n={n} backend={backend} />}
        </div>
      </div>
      <Lightbox src={zoom} caption={b.title || b.kind} onClose={() => setZoom(null)} />
    </div>
  );
}

function TierTab({ n, label, active, set, icon }) {
  return (
    <button className={"tier-tab t" + n + (active === n ? " active" : "")} onClick={() => set(n)} role="tab" aria-selected={active === n}>
      <span className="tn">T{n}</span>{icon}<span className="tl">{label}</span>
    </button>
  );
}

function Tier0({ bug: b }) {
  const steps = b.trace || [];
  return (
    <div className="tier-pane">
      <div className="tier-lede">Ground truth from <code>adb logcat</code>, scoped to the app's pid.</div>
      {b.log_line && <pre className="signal">{b.log_line}</pre>}
      {steps.length > 0 && (
        <>
          <div className="tier-sub">Reproduction — from a cold start</div>
          <ol className="repro">
            {steps.map((s, i) => (
              <li key={i}><span className={"verb " + (s.verb || "tap")}>{s.verb}</span>{s.target_label ? <b>{s.target_label}</b> : null}{s.reason ? <span className="why"> — {s.reason}</span> : null}</li>
            ))}
          </ol>
        </>
      )}
    </div>
  );
}

function Tier1({ bug: b }) {
  const [copied, setCopied] = useState(false);
  const prompt = b.tier1_prompt;
  if (!prompt) return <div className="tier-pane"><div className="tier-empty">Fix prompt not available for this run.</div></div>;
  const copy = async () => {
    try { await navigator.clipboard.writeText(prompt); setCopied(true); setTimeout(() => setCopied(false), 1800); } catch {}
  };
  return (
    <div className="tier-pane">
      <div className="tier-lede">A portable, self-contained prompt — signal, repro, and the failing source — ready to paste into any coding agent.</div>
      <div className="prompt-wrap">
        <button className={"copy-btn" + (copied ? " ok" : "")} onClick={copy}>{copied ? <><Check /> Copied</> : <><Copy /> Copy prompt</>}</button>
        <pre className="prompt">{prompt}</pre>
      </div>
    </div>
  );
}

function Tier2({ bug: b, n, backend }) {
  const st = useStore();
  const fix = b.tier2_fix;
  const busy = st.fixingBug !== null;          // one device, one fix at a time
  const mine = st.fixingBug === n;             // ...and this card's fix is the one
  const canRun = backend && backend !== "prompt";
  const gateByName = {};
  (fix?.gates || []).forEach((g) => { gateByName[g.name] = g; });
  const status = fix ? (fix.verified ? "verified" : "reverted") : "pending";
  const statusText = fix ? (fix.verified ? "Verified — patch cleared all gates" : "Reverted — a gate failed") : "Not yet applied";

  return (
    <div className="tier-pane">
      <div className="tier-lede">The autofix drives a coding agent to patch the source, rebuilds the APK, replays the trace, and grades the patch against three gates. A guard rejects cheap symptom-silencers first.</div>

      <div className="fix-meta">
        <span className={"fix-status " + status}><span className="dot" />{statusText}</span>
        <span className="fix-backend">backend <b>{backend || "prompt"}</b></span>
      </div>

      <div className="gate-ladder">
        <GateRow name="static guard" desc="Rejects try/catch swallows, deleted widgets, scroll-view hacks" state={fix ? (fix.guard_violations?.length ? "fail" : "pass") : "pending"} />
        {GATES.map(([name, desc]) => {
          const g = gateByName[name];
          const state = g ? (g.passed ? "pass" : "fail") : "pending";
          return <GateRow key={name} name={name} desc={g?.detail || desc} state={state} />;
        })}
      </div>

      {fix?.branch && <div className="tier-sub" style={{ marginTop: 12 }}>Patch left on branch <code>{fix.branch}</code> for review.</div>}

      {mine && <div className="fix-progress"><span className="spin" />{PHASES[st.fixPhase] || "Working…"}</div>}
      {st.fixError?.bug === n && !busy && <div className="fix-error">{st.fixError.msg}</div>}

      {!mine && (
        <div className="fix-actions">
          <button className="btn btn-primary" disabled={busy || st.running || !canRun}
                  onClick={() => startFix(n)}>
            <Wrench /> {fix ? "Try again" : "Attempt fix"}
          </button>
          <span className="fix-hint">
            {!canRun
              ? <>Set <code>FIX_BACKEND</code> to a coding agent in Settings first — <code>prompt</code> only writes the T1 prompt.</>
              : st.running ? "The device is busy with a run."
              : busy ? "Another fix is using the device."
              : "Takes several minutes. The patch is reverted unless every gate passes."}
          </span>
        </div>
      )}
    </div>
  );
}

function GateRow({ name, desc, state }) {
  const icon = state === "pass" ? <Check /> : state === "fail" ? <X /> : <span className="pending-dot" />;
  return (
    <div className={"gate " + state}>
      <span className="gi">{icon}</span>
      <div className="gmain"><div className="gname">{name}</div><div className="gdesc">{desc}</div></div>
    </div>
  );
}
