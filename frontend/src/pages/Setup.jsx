import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Bolt, Check } from "../lib/icons.jsx";

/* Three ways to get a device, and they are genuinely different guides — not one
   guide with asides. A Mac user reading "load the binder module" is reading
   something that cannot work on their machine, so the track is chosen first and
   the wrong instructions are never shown at all. */

function Code({ children }) {
  return <pre className="setup-code">{children}</pre>;
}
function Path({ children }) { return <span className="setup-path">{children}</span>; }

const PREREQS = {
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
};

const MODEL_KEY = {
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
};

const LAUNCH = {
  t: "Launch the console and pick an app",
  body: (
    <>
      <p>Start the runner and open the console:</p>
      <Code>.venv/bin/python -m gremlin.dashboard   # http://127.0.0.1:8000</Code>
      <p>Use the <b>app picker</b> in the top bar to choose what to test — your Flutter or React Native projects (full support, including Tier-2 fixes) or any app already installed on the device (explore-only) — then press <b>Start run</b>.</p>
    </>
  ),
};

// ---- Track 1: a real phone over USB ---------------------------------------
const PHONE = [
  PREREQS,
  MODEL_KEY,
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
  LAUNCH,
];

// ---- Track 2: the Android emulator (macOS + Windows + Linux) ---------------
// This is the only track that works on macOS and Windows, because the sandbox
// needs a Linux kernel feature those platforms do not have. It is therefore
// written to be followed by someone who has never opened Android Studio.
const EMULATOR = [
  {
    t: "Check your machine can run it",
    body: (
      <>
        <p>The emulator is a virtual machine, so it needs hardware virtualization and real disk space. Check both before installing anything.</p>
        <h4>Apple Silicon Mac (M1/M2/M3/M4)</h4>
        <p>Nothing to enable — virtualization is always on. Use <b>arm64-v8a</b> system images and the emulator runs at native speed.</p>
        <h4>Intel Mac</h4>
        <p>Also fine: modern Android Studio uses Apple's Hypervisor.framework. The old Intel HAXM installer is deprecated — don't go looking for it.</p>
        <h4>Windows</h4>
        <p>Virtualization must be enabled in <b>BIOS/UEFI</b> (Intel VT-x, or AMD-V / SVM Mode). Reboot into your firmware settings to check. Then enable Windows' hypervisor:</p>
        <ul className="setup-list">
          <li>Press Start, type <b>Turn Windows features on or off</b>.</li>
          <li>Tick <b>Windows Hypervisor Platform</b>. Also tick <b>Virtual Machine Platform</b> if you use WSL2.</li>
          <li>Reboot when it asks.</li>
        </ul>
        <p className="note">Intel HAXM no longer ships and is not needed. On AMD, WHPX has always been the only option.</p>
        <h4>Disk</h4>
        <p>Budget <b>~10 GB</b>: Android Studio ~3 GB, one system image ~1.5 GB, the AVD's own data ~2-6 GB as it fills up. A full disk is the single most common reason an emulator refuses to boot.</p>
      </>
    ),
  },
  {
    t: "Install the Android SDK",
    body: (
      <>
        <p>Two ways. Android Studio is the easy one and gives you a GUI device manager; command-line tools are smaller if you never want the IDE.</p>
        <h4>macOS — Android Studio</h4>
        <Code>{`brew install --cask android-studio
# …or download from https://developer.android.com/studio`}</Code>
        <p>Open it once and let the setup wizard finish. It installs the SDK to <Path>~/Library/Android/sdk</Path>.</p>
        <h4>Windows — Android Studio</h4>
        <Code>{`winget install Google.AndroidStudio
# …or download the .exe from https://developer.android.com/studio`}</Code>
        <p>Run the wizard with the defaults. The SDK lands in <Path>{String.raw`%LOCALAPPDATA%\Android\Sdk`}</Path>.</p>
        <h4>Either OS — no IDE</h4>
        <p>Install just the command-line tools, then use <code>sdkmanager</code>. On macOS: <code>brew install android-commandlinetools</code>. On Windows, download "Command line tools only" from the Studio page and unzip it to <Path>{String.raw`%LOCALAPPDATA%\Android\Sdk\cmdline-tools\latest`}</Path>.</p>
      </>
    ),
  },
  {
    t: "Add the SDK to your PATH",
    body: (
      <>
        <p>Gremlin shells out to <code>adb</code>, <code>emulator</code> and <code>avdmanager</code>, so they have to be findable. This is the step people skip and then spend an hour on.</p>
        <h4>macOS (zsh)</h4>
        <Code>{`cat >> ~/.zshrc <<'EOF'
export ANDROID_HOME="$HOME/Library/Android/sdk"
export PATH="$ANDROID_HOME/platform-tools:$ANDROID_HOME/emulator:$ANDROID_HOME/cmdline-tools/latest/bin:$PATH"
EOF
source ~/.zshrc`}</Code>
        <h4>Windows (PowerShell, permanent)</h4>
        <Code>{String.raw`setx ANDROID_HOME "$env:LOCALAPPDATA\Android\Sdk"
setx PATH "$env:PATH;$env:LOCALAPPDATA\Android\Sdk\platform-tools;$env:LOCALAPPDATA\Android\Sdk\emulator"`}</Code>
        <p className="note"><code>setx</code> only affects <b>new</b> terminals — close and reopen PowerShell before testing. Prefer a GUI? Start → "Edit the system environment variables" → <b>Environment Variables</b> → edit <b>Path</b>.</p>
        <p>Verify on both:</p>
        <Code>{`adb version
emulator -version`}</Code>
      </>
    ),
  },
  {
    t: "Install a system image",
    body: (
      <>
        <p>Pick the image that matches your CPU — the wrong architecture is emulated instruction-by-instruction and is unusably slow.</p>
        <ul className="setup-list">
          <li><b>Apple Silicon</b> → <code>arm64-v8a</code></li>
          <li><b>Intel Mac / Windows</b> → <code>x86_64</code></li>
        </ul>
        <h4>From Android Studio</h4>
        <p><Path>Settings → Languages &amp; Frameworks → Android SDK → SDK Platforms</Path>, tick <b>Android 13 (Tiramisu, API 33)</b>. Then the <b>SDK Tools</b> tab: tick <b>Android SDK Platform-Tools</b> and <b>Android Emulator</b>. Apply.</p>
        <h4>From the command line</h4>
        <Code>{`# Apple Silicon
sdkmanager "platform-tools" "emulator" "system-images;android-33;google_apis;arm64-v8a"

# Intel Mac / Windows
sdkmanager "platform-tools" "emulator" "system-images;android-33;google_apis;x86_64"`}</Code>
        <p className="note">Use a <b>google_apis</b> image, not <b>google_apis_playstore</b>: the Play Store variant is not rootable, which blocks some of what the oracle reads from logcat.</p>
      </>
    ),
  },
  {
    t: "Create a virtual device",
    body: (
      <>
        <h4>From Android Studio</h4>
        <p><Path>Tools → Device Manager → Create device</Path>. Pick <b>Pixel 6</b>, choose the API 33 image you just installed, name it <code>gremlin</code>, Finish.</p>
        <h4>From the command line</h4>
        <Code>{`avdmanager create avd -n gremlin -d pixel_6 \
  -k "system-images;android-33;google_apis;arm64-v8a"   # or x86_64

emulator -list-avds        # should print: gremlin`}</Code>
        <p className="note">Screen size matters more here than it looks: RenderFlex overflow is the most common defect Gremlin finds, and whether a row overflows depends on the width. A Pixel 6 is a reasonable default; testing a second, narrower device finds different bugs.</p>
      </>
    ),
  },
  {
    t: "Boot it and check adb sees it",
    body: (
      <>
        <p>You can let Gremlin boot it for you, but boot it by hand once so any error is visible:</p>
        <Code>{`emulator -avd gremlin
# in another terminal:
adb devices`}</Code>
        <Code>{`List of devices attached
emulator-5554   device`}</Code>
        <p className="note"><b>Cold boot takes a minute</b> with acceleration. If it takes twenty, acceleration is off — recheck BIOS virtualization and Windows Hypervisor Platform. Gremlin warns about this when it boots one for you.</p>
      </>
    ),
  },
  {
    t: "Install your app into it",
    body: (
      <>
        <p>An emulator starts with no apps, so the thing you want to test has to get in. If you have the source, build and install:</p>
        <Code>{`flutter build apk --debug && adb install -r build/app/outputs/flutter-apk/app-debug.apk
# React Native:
cd android && ./gradlew assembleRelease && adb install -r app/build/outputs/apk/release/app-release.apk`}</Code>
        <p>Already have an APK? <code>adb install -r yourapp.apk</code>, or just drag the .apk onto the emulator window.</p>
        <p className="note">Tier-2 autofix needs the <b>source tree</b>, not just the APK — it patches your code, rebuilds and replays. An APK-only app gets bug reports and paste-ready prompts, never an automatic fix.</p>
      </>
    ),
  },
  LAUNCH,
];

// ---- Track 3: the containerised sandbox (Linux only) ----------------------
const SANDBOX = [
  {
    t: "Check this is a Linux machine",
    body: (
      <>
        <p>The sandbox runs <b>redroid</b>: Android's userspace as ordinary processes on <i>your</i> kernel. No guest kernel, no QEMU — which is why it needs 2-3 GB instead of the emulator's 12-15 GB and starts in seconds.</p>
        <p>The price is that it needs <b>binder</b>, the Android IPC driver, from the host kernel. That is a Linux feature. macOS and Windows run Docker inside a LinuxKit VM that does not ship it, so there is no version of this that works there — <b>use the emulator track instead</b>.</p>
        <p className="note">You also need Docker Engine. On Linux: <code>curl -fsSL https://get.docker.com | sh</code>, or your distro's package.</p>
      </>
    ),
  },
  {
    t: "Let Gremlin set up the host",
    body: (
      <>
        <p>Open the <b>device picker</b> in the top bar. Under <b>Sandbox</b>, if the prerequisites are missing you'll see <b>Set up this computer</b>. Click it and authorise the prompt.</p>
        <p>That runs <code>scripts/sandbox-setup.sh</code> as root through <b>pkexec</b> — your desktop's normal password dialog, the same one a software updater uses. It:</p>
        <ul className="setup-list">
          <li>loads <code>binder_linux</code> with the device nodes Android needs, or mounts <b>binderfs</b> when the module is already loaded without them (Ubuntu marks it <code>[permanent]</code>, so it cannot be reloaded before a reboot);</li>
          <li>writes the <Path>/etc/modules-load.d</Path>, <Path>/etc/modprobe.d</Path> and <Path>/etc/fstab</Path> entries so it survives reboots — once, not every session;</li>
          <li>starts and enables the Docker daemon.</li>
        </ul>
        <p className="note">Over SSH, or with no polkit agent, the button is replaced by the command to run yourself: <code>sudo scripts/sandbox-setup.sh</code>. The script is in the repo and is worth reading before you authorise it.</p>
      </>
    ),
  },
  {
    t: "Start it and run",
    body: (
      <>
        <p>Device picker → <b>Sandbox</b> → <b>Android container</b>. The first start downloads the redroid image (~2-3 GB); later ones take seconds.</p>
        <p>Pick your app and press <b>Start run</b> — the container starts empty, so Gremlin builds your project and installs it before exploring. From the terminal it is the default when nothing else is attached:</p>
        <Code>{`python run.py --project ~/Projects/MyApp   # no device → sandbox
python run.py --sandbox                    # sandbox even with a phone plugged in
python run.py --keep-sandbox               # leave it up for the next run`}</Code>
        <p className="note">It is <b>ephemeral on purpose</b> — no data volume, so every run starts from a byte-identical image. That is what makes a benchmark number reproducible, and it is why stopping the sandbox throws its state away.</p>
      </>
    ),
  },
];

const TRACKS = [
  { id: "phone", label: "I have an Android phone", sub: "USB · any OS", steps: PHONE },
  { id: "emulator", label: "No phone — use an emulator", sub: "macOS · Windows · Linux", steps: EMULATOR },
  { id: "sandbox", label: "No phone — use the sandbox", sub: "Linux only · fastest", steps: SANDBOX },
];

export default function Setup() {
  // Prose does not fit a viewport and the console does not scroll — so the guide
  // is a rail plus one step at a time. Which is also how people follow
  // instructions: one thing, then the next.
  const nav = useNavigate();
  const [track, setTrack] = useState("phone");
  const [i, setI] = useState(0);
  const steps = TRACKS.find((t) => t.id === track).steps;
  const step = steps[Math.min(i, steps.length - 1)];

  function pickTrack(id) { setTrack(id); setI(0); }

  return (
    <>
      <div className="page-head">
        <h1 className="page-title">Setup</h1>
        <p className="page-desc">Get a device Gremlin can drive, then run your first scan. About five minutes with a phone; longer if you're installing an emulator.</p>
      </div>

      <div className="page-body">
        <div className="setup-tracks">
          {TRACKS.map((t) => (
            <button key={t.id} className={"setup-track" + (t.id === track ? " active" : "")}
                    onClick={() => pickTrack(t.id)}>
              <span className="setup-track-l">{t.label}</span>
              <span className="setup-track-s">{t.sub}</span>
            </button>
          ))}
        </div>

        <div className="setup-callout">
          <div className="eyebrow"><Bolt /> Before you start</div>
          <p className="note">{track === "phone"
            ? <>Gremlin drives a <b>real device</b> over USB. Use a <b>throwaway account</b> with no real data: the agent taps, types and scrolls freely, so treat the run like a stranger poking at your app.</>
            : <>A virtual device has no real data in it, which is the main reason to prefer one. It also starts with <b>no apps</b> — Gremlin builds and installs your project itself when it runs against the sandbox.</>}</p>
        </div>

        <div className="setup-split">
          <ol className="setup-rail">
            {steps.map((t, n) => (
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
              <span className="setup-count">Step {i + 1} of {steps.length}</span>
              {i < steps.length - 1
                ? <button className="btn btn-primary" onClick={() => setI(i + 1)}>Next →</button>
                : <button className="btn btn-primary" onClick={() => nav("/app")}>Finish</button>}
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
