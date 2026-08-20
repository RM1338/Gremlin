import { useState } from "react";
import { Bolt, Check } from "../lib/icons.jsx";

/* A step-by-step "connect your phone and run" guide. Static content, but it's
   the thing new users need most, so it lives in the console. */

function Code({ children }) {
  return <pre className="setup-code">{children}</pre>;
}
function Path({ children }) { return <span className="setup-path">{children}</span>; }

const STEPS = [
  {
    t: "Install the prerequisites (on your computer)",
    body: (
      <>
        <p>You need <b>adb</b> (Android platform-tools) on your PATH, Python 3.11+, and this repo's virtualenv.</p>
        <Code>{`# Ubuntu/Debian
sudo apt install android-tools-adb
# macOS
brew install android-platform-tools

# then, in the Gremlin repo:
python -m venv .venv && .venv/bin/pip install -r requirements.txt`}</Code>
        <p className="note">Verify adb works: <code>adb version</code> should print a version.</p>
      </>
    ),
  },
  {
    t: "Add a free model key",
    body: (
      <>
        <p>The exploration policy runs on a free LLM tier. Put your key in a <code>.env</code> file at the repo root (it's git-ignored):</p>
        <Code>{`# Gemini (default) — https://aistudio.google.com/apikey
GEMINI_API_KEY=your-key

# …or Groq, if Gemini's daily free quota runs out
# LLM_PROVIDER=groq
# GROQ_API_KEY=your-key   (https://console.groq.com/keys)`}</Code>
      </>
    ),
  },
  {
    t: "Enable Developer Options on your phone",
    body: (
      <>
        <p>Open <Path>Settings → About phone</Path> and tap <b>Build number</b> seven times. You'll see "You are now a developer!"</p>
        <p className="note">On Samsung it's <Path>Settings → About phone → Software information → Build number</Path>.</p>
      </>
    ),
  },
  {
    t: "Turn on USB debugging",
    body: (
      <>
        <p>Go to <Path>Settings → Developer options</Path> and enable:</p>
        <ul className="setup-list">
          <li><b>USB debugging</b> — required, this is how Gremlin drives the phone.</li>
          <li><b>Stay awake</b> — recommended, keeps the screen on while charging so runs don't pause.</li>
        </ul>
      </>
    ),
  },
  {
    t: "Connect over USB and authorize",
    body: (
      <>
        <p>Plug the phone into your computer with a USB cable. Then:</p>
        <ul className="setup-list">
          <li>Pull down the notification and set USB mode to <b>File transfer / MTP</b> (not "Charging only").</li>
          <li>A dialog <b>"Allow USB debugging?"</b> appears on the phone — check <b>Always allow from this computer</b> and tap <b>Allow</b>.</li>
        </ul>
        <p className="note">No cable? You can also use wireless debugging (<Path>Developer options → Wireless debugging</Path>) and <code>adb connect &lt;ip&gt;:&lt;port&gt;</code>, but USB is simplest and most reliable.</p>
      </>
    ),
  },
  {
    t: "Verify the connection",
    body: (
      <>
        <p>Run:</p>
        <Code>adb devices</Code>
        <p>You should see your phone listed with status <b>device</b>:</p>
        <Code>{`List of devices attached
R58N70XXXXX     device`}</Code>
        <p className="note">If it says <b>unauthorized</b>, re-accept the dialog on the phone. If <b>offline</b> or nothing shows, reseat the cable, try a different port, and run <code>adb kill-server && adb devices</code>.</p>
      </>
    ),
  },
  {
    t: "Launch the console and pick an app",
    body: (
      <>
        <p>Start the runner and open the console:</p>
        <Code>.venv/bin/python -m gremlin.dashboard   # http://127.0.0.1:8000</Code>
        <p>Use the <b>app picker</b> in the top bar to choose what to test — your Flutter projects (full support) or any app installed on the phone (explore-only) — then press <b>Start run</b>.</p>
      </>
    ),
  },
];

export default function Setup() {
  // Seven steps of prose do not fit a viewport, and the console does not
  // scroll — so the guide is a rail plus one step at a time. Which is also how
  // people follow instructions: one thing, then the next.
  const [i, setI] = useState(0);
  const step = STEPS[i];

  return (
    <>
      <div className="page-head">
        <h1 className="page-title">Setup</h1>
        <p className="page-desc">Connect your Android phone and run your first scan. Takes about five minutes the first time.</p>
      </div>

      <div className="page-body">
        <div className="setup-callout">
          <div className="eyebrow"><Bolt /> Before you start</div>
          <p className="note">Gremlin drives a <b>real device</b> over USB — it doesn't build or install your app, so whatever you test must already be installed on the phone. Use a <b>throwaway account</b> with no real data: the agent taps, types and scrolls freely, so treat the run like a stranger poking at your app.</p>
        </div>

        <div className="setup-split">
          <ol className="setup-rail">
            {STEPS.map((t, n) => (
              <li key={n}>
                <button className={"setup-railbtn" + (n === i ? " active" : "") + (n < i ? " done" : "")}
                        onClick={() => setI(n)}>
                  <span className="setup-num">{n < i ? <Check /> : n + 1}</span>
                  <span className="setup-railtitle">{t.t}</span>
                </button>
              </li>
            ))}
          </ol>

          <div className="setup-panel">
            <h3>{step.t}</h3>
            <div className="setup-content">{step.body}</div>
            <div className="setup-nav">
              <button className="btn" onClick={() => setI(i - 1)} disabled={i === 0}>← Back</button>
              <span className="setup-count">Step {i + 1} of {STEPS.length}</span>
              {i < STEPS.length - 1
                ? <button className="btn btn-primary" onClick={() => setI(i + 1)}>Next →</button>
                : <span className="setup-fin"><Check /> That's it — start a run from the top bar.</span>}
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
