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
  return (
    <>
      <div className="page-head">
        <h1 className="page-title">Setup</h1>
        <p className="page-desc">Connect your Android phone and run your first scan. Takes about five minutes the first time.</p>
      </div>

      <div className="setup-callout">
        <div className="eyebrow"><Bolt /> Before you start</div>
        <p className="note" style={{ fontSize: 14 }}>Gremlin drives a <b>real device</b> over USB — it doesn't build or install your app, so whatever you test must already be installed on the phone. Use a <b>throwaway account</b> with no real data: the agent taps, types and scrolls freely, so treat the run like a stranger poking at your app.</p>
      </div>

      <ol className="setup-steps">
        {STEPS.map((s, i) => (
          <li className="setup-step" key={i}>
            <div className="setup-num">{i + 1}</div>
            <div className="setup-content">
              <h3>{s.t}</h3>
              {s.body}
            </div>
          </li>
        ))}
      </ol>

      <div className="setup-done">
        <div className="setup-num done"><Check /></div>
        <div>
          <h3 style={{ margin: 0 }}>That's it</h3>
          <p className="note" style={{ margin: "4px 0 0" }}>Watch the run on the <b>Live run</b> page; when it finishes you'll get a desktop notification and a summary. Trouble connecting? Almost always the USB mode (set it to File transfer) or the debugging authorization dialog.</p>
        </div>
      </div>
    </>
  );
}
