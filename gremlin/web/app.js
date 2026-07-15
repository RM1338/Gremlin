/* ============================================================================
   Gremlin console — client-side SPA. Hash-routed, live over one WebSocket.
   ============================================================================ */

const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const el = (t, cls, html) => { const n = document.createElement(t); if (cls) n.className = cls; if (html != null) n.innerHTML = html; return n; };
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const sevClass = (s) => (s === "crash" ? "crash" : s === "layout" ? "layout" : "hang");
const pad3 = (n) => String(n).padStart(3, "0");

/* ---- Store ---------------------------------------------------------------- */
const S = {
  running: false,
  done: false,
  package: "com.scribe.scribe",
  trace: null,          // trace.json
  eval: null,           // eval.json
  screens: [],          // available screenshot filenames
  live: { steps: [], bugs: [], current: null, screenCount: 0 },
};

/* ---- Mascot: a mischievous little gremlin ------------------------------- */
function mascot(size = 200, floating = true) {
  return `<svg viewBox="0 0 200 200" width="${size}" height="${size}" class="${floating ? "mascot-float" : ""}" aria-label="Gremlin">
    <defs>
      <linearGradient id="gskin" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stop-color="#5cf0ba"/><stop offset="1" stop-color="#1f9d72"/>
      </linearGradient>
      <radialGradient id="gglow" cx="50%" cy="40%" r="60%">
        <stop offset="0" stop-color="#35e6a3" stop-opacity=".35"/><stop offset="1" stop-color="#35e6a3" stop-opacity="0"/>
      </radialGradient>
    </defs>
    <circle cx="100" cy="104" r="86" fill="url(#gglow)"/>
    <!-- ears -->
    <path d="M40 70 L14 34 Q46 44 58 74 Z" fill="url(#gskin)"/>
    <path d="M160 70 L186 34 Q154 44 142 74 Z" fill="url(#gskin)"/>
    <path d="M40 70 L22 42 Q44 52 54 74 Z" fill="#0c3d2b" opacity=".5"/>
    <path d="M160 70 L178 42 Q156 52 146 74 Z" fill="#0c3d2b" opacity=".5"/>
    <!-- head/body -->
    <path d="M52 96 Q52 52 100 52 Q148 52 148 96 L148 128 Q148 172 100 172 Q52 172 52 128 Z" fill="url(#gskin)"/>
    <!-- belly -->
    <ellipse cx="100" cy="132" rx="34" ry="30" fill="#0e5a40" opacity=".45"/>
    <!-- eyes -->
    <g class="mascot-eye">
      <ellipse cx="80" cy="100" rx="17" ry="18" fill="#06120d"/>
      <ellipse cx="120" cy="100" rx="17" ry="18" fill="#06120d"/>
      <circle cx="85" cy="95" r="6.5" fill="#eafff6"/>
      <circle cx="125" cy="95" r="6.5" fill="#eafff6"/>
      <circle cx="80" cy="100" r="4" fill="#35e6a3"/>
      <circle cx="120" cy="100" r="4" fill="#35e6a3"/>
    </g>
    <!-- grin -->
    <path d="M78 138 Q100 156 122 138" fill="none" stroke="#06120d" stroke-width="5" stroke-linecap="round"/>
    <path d="M86 140 l5 7 5-7 M104 140 l5 7 5-7" fill="none" stroke="#06120d" stroke-width="3" stroke-linecap="round"/>
    <!-- brows: mischief -->
    <path d="M64 80 l26 6" stroke="#06120d" stroke-width="5" stroke-linecap="round"/>
    <path d="M136 80 l-26 6" stroke="#06120d" stroke-width="5" stroke-linecap="round"/>
  </svg>`;
}

/* ---- Icons ---------------------------------------------------------------- */
const I = {
  screens: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="14" rx="2"/><path d="M8 20h8"/></svg>',
  steps: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 18h4v-6H4zM10 18h4V6h-4zM16 18h4v-9h-4z"/></svg>',
  bug: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="7" y="7" width="10" height="11" rx="5"/><path d="M7 11H3M21 11h-4M12 7V4M12 18v3"/></svg>',
  bolt: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M13 2L4 14h6l-1 8 9-12h-6z"/></svg>',
  check: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M20 6L9 17l-5-5"/></svg>',
};

/* ============================================================================
   Data
   ============================================================================ */
async function loadState() {
  try {
    const r = await fetch("/api/state");
    const d = await r.json();
    S.running = d.running;
    S.package = d.package || S.package;
    S.trace = d.trace;
    S.eval = d.eval;
    S.screens = d.screens || [];
  } catch (e) { /* offline: keep defaults */ }
  refreshChrome();
}

function refreshChrome() {
  const steps = S.trace?.steps ?? S.live.steps.length;
  const bugs = (S.trace?.bugs?.length ?? 0) || S.live.bugs.length;
  $("#navSteps").textContent = steps;
  $("#navBugs").textContent = bugs;
  $("#footTarget").textContent = S.package;
  const state = S.running ? "live" : S.done ? "done" : "idle";
  const label = S.running ? "Running…" : S.done ? "Run complete" : "Idle";
  ["#navPulse", "#footPulse"].forEach(s => { $(s).className = "pulse " + state; });
  $("#footStatus").textContent = label;
  $("#topStartLabel").textContent = S.running ? "Running…" : "Start run";
  $("#topStart").disabled = S.running;
}

/* ============================================================================
   Animated count-up
   ============================================================================ */
function countUp(node, to, dur = 900) {
  const from = 0, t0 = performance.now();
  function tick(t) {
    const p = Math.min(1, (t - t0) / dur);
    const e = 1 - Math.pow(1 - p, 3);
    node.textContent = Math.round(from + (to - from) * e);
    if (p < 1) requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);
}

/* ============================================================================
   Router
   ============================================================================ */
const ROUTES = {
  "/": { title: "Overview", render: renderOverview },
  "/live": { title: "Live run", render: renderLive },
  "/trace": { title: "Trace", render: renderTrace },
  "/bugs": { title: "Bugs", render: renderBugs },
  "/benchmark": { title: "Benchmark", render: renderBenchmark },
};

function route() {
  const path = (location.hash.replace(/^#/, "") || "/");
  const r = ROUTES[path] || ROUTES["/"];
  $$(".nav-item").forEach(n => n.classList.toggle("active", n.dataset.route === path));
  $("#crumbHere").textContent = r.title;
  const view = $("#view");
  view.style.animation = "none"; void view.offsetWidth; view.style.animation = "";
  view.innerHTML = "";
  const inner = el("div", "view-inner");
  view.appendChild(inner);
  r.render(inner);
}

/* ============================================================================
   View: Overview
   ============================================================================ */
function renderOverview(root) {
  const steps = S.trace?.steps ?? 0;
  const screens = S.trace?.distinct_screens ?? 0;
  const bugs = S.trace?.bugs?.length ?? 0;
  const evalG = S.eval?.find(e => e.explorer === "gremlin");
  const evalM = S.eval?.find(e => e.explorer === "monkey");
  const mult = evalG && evalM && evalM.distinct_screens ? (evalG.distinct_screens / evalM.distinct_screens) : null;

  root.innerHTML = `
    <section class="hero">
      <div class="hero-grid"></div>
      <div class="hero-content">
        <div class="eyebrow">${I.bolt} Autonomous UI-testing agent</div>
        <h1>Gremlin explores your app<br>and <em>breaks it on purpose.</em></h1>
        <p>A vision-driven agent that drives a real device — observe, decide, act, check —
           reaching screens a random monkey never will, and turning every crash into a
           reproducible trace.</p>
        <div class="hero-cta">
          <button class="btn btn-primary" id="heroStart">${I.bolt}<span>Start a run</span></button>
          <a class="btn btn-ghost" data-nav="/benchmark">See the benchmark →</a>
        </div>
        <div class="hero-term">
          <div class="bar"><i></i><i></i><i></i></div>
          <div class="body"><span class="prompt">gremlin ~</span> <span id="heroType"></span><span class="caret"></span></div>
        </div>
      </div>
      <div class="hero-mascot">${mascot(200)}</div>
    </section>

    <div class="stat-grid">
      ${statTile(I.screens, "Distinct screens", screens, "vs <b>1</b> for random monkey")}
      ${statTile(I.steps, "Actions taken", steps, "grounded on a11y elements")}
      ${statTile(I.bug, "Bugs found", bugs, bugs ? "with repro traces" : "clean baseline run")}
      ${statTile(I.bolt, "Coverage lift", mult ? mult + "×" : "—", "more screens than monkey")}
    </div>

    <div class="grid-2">
      <div class="card">
        <div class="section-head"><h3>The loop</h3><a data-nav="/trace">View last trace →</a></div>
        <div class="pipeline">
          ${plNode("01", "Observe", "screenshot + a11y tree")}
          <span class="pl-arrow">→</span>
          ${plNode("02", "Decide", "vision model picks a verb")}
          <span class="pl-arrow">→</span>
          ${plNode("03", "Act", "tap · type · scroll · back")}
          <span class="pl-arrow">→</span>
          ${plNode("04", "Check", "oracle drains logcat")}
        </div>
        <p class="note" style="margin-top:18px">Every action is recorded to a <code>trace.json</code> that the replayer
          re-executes verbatim, so a bug found at step 19 is reproducible from launch.</p>
      </div>
      <div class="card">
        <div class="section-head"><h3>Latest run</h3><a data-nav="/live">Watch live →</a></div>
        ${runSummary(steps, screens, bugs)}
      </div>
    </div>
  `;
  root.querySelectorAll(".stat .v[data-to]").forEach(n => {
    const to = n.dataset.to;
    if (/^\d+$/.test(to)) countUp(n, +to); else n.textContent = to;
  });
  $("#heroStart").onclick = startRun;
  typewriter($("#heroType"), [
    "reaching Settings → Profile → Theme…",
    "10 distinct screens, 0 crashes",
    "tap ‘Schedule’ — an unvisited section",
    "draining logcat for the app pid…",
  ]);
}

function statTile(icon, k, v, foot) {
  return `<div class="stat">
    <div class="k">${icon}${k}</div>
    <div class="v" data-to="${v}">${/^\d+$/.test(String(v)) ? "0" : v}</div>
    <div class="foot">${foot}</div>
    <svg class="spark" viewBox="0 0 110 60" fill="none" stroke="var(--brand)" stroke-width="2" opacity=".6"><path d="M0 50 Q20 48 30 38 T55 30 T80 16 T110 8"/></svg>
  </div>`;
}
function plNode(n, t, d) { return `<div class="pl-node"><div class="n">${n}</div><div class="t">${t}</div><div class="d">${d}</div></div>`; }
function runSummary(steps, screens, bugs) {
  if (!S.trace) return `<p class="note">No run yet. Press <b>Start a run</b> to watch Gremlin explore.</p>`;
  return `<div class="live-stats">
    <div class="live-stat"><div class="v">${steps}</div><div class="k">Steps</div></div>
    <div class="live-stat"><div class="v">${screens}</div><div class="k">Screens</div></div>
    <div class="live-stat"><div class="v">${bugs}</div><div class="k">Bugs</div></div>
  </div>
  <div class="pill ${bugs ? "" : "brand"}" style="margin-top:14px">${bugs ? I.bug + " " + bugs + " to triage" : I.check + " clean run"}</div>`;
}

/* Typewriter effect for the hero terminal */
function typewriter(node, lines) {
  let li = 0, ci = 0, deleting = false;
  function step() {
    if (!node.isConnected) return;
    const line = lines[li];
    node.textContent = line.slice(0, ci);
    if (!deleting && ci < line.length) { ci++; setTimeout(step, 32); }
    else if (!deleting) { deleting = true; setTimeout(step, 1600); }
    else if (ci > 0) { ci--; setTimeout(step, 14); }
    else { deleting = false; li = (li + 1) % lines.length; setTimeout(step, 300); }
  }
  step();
}

/* ============================================================================
   View: Live run
   ============================================================================ */
function renderLive(root) {
  root.innerHTML = `
    <div class="page-head">
      <h1 class="page-title">Live run</h1>
      <p class="page-desc">Watch the agent think in real time — the device on the left, its intention and
        the observe→decide→act→check stream on the right.</p>
    </div>
    <div class="live">
      <div>
        <div class="phone"><div class="phone-screen" id="phoneScreen">
          <div class="phone-empty" id="phoneEmpty">
            ${S.running ? '<div class="spinner"></div>waiting for first frame…' : 'press <b>Start run</b> to begin'}
          </div>
        </div></div>
      </div>
      <div class="live-right">
        <div class="intent-card">
          <div class="k">${I.bolt} Current intention</div>
          <div class="v" id="liveIntent">${S.live.current?.intention || "—"}</div>
          <div class="meta" id="liveMeta">${S.live.current ? liveMetaHTML(S.live.current) : "idle"}</div>
        </div>
        <div class="live-stats">
          <div class="live-stat"><div class="v" id="liveScreens">${S.live.screenCount}</div><div class="k">Screens</div></div>
          <div class="live-stat"><div class="v" id="liveStep">${S.live.steps.length}</div><div class="k">Step</div></div>
          <div class="live-stat"><div class="v" id="liveBugs">${S.live.bugs.length}</div><div class="k">Bugs</div></div>
        </div>
        <div class="log">
          <div class="log-head"><span class="pulse ${S.running ? "live" : "idle"}"></span> action stream</div>
          <div class="log-body" id="logBody"></div>
        </div>
        <div id="liveBugFeed"></div>
      </div>
    </div>`;

  // Replay any steps/bugs already seen this session.
  const body = $("#logBody");
  S.live.steps.forEach(s => body.appendChild(logLine(s)));
  body.scrollTop = body.scrollHeight;
  const feed = $("#liveBugFeed");
  S.live.bugs.forEach(b => feed.appendChild(bugCard(b, true)));
  if (S.live.current?.frame) setFrame(S.live.current.frame);
}

function liveMetaHTML(s) {
  return `<span>step ${s.step}</span><span>·</span><span>${esc(s.screen || "")}</span>` +
    (s.is_new ? '<span class="new-badge">· new screen ✦</span>' : "");
}
function logLine(s) {
  const line = el("div", "log-line");
  line.innerHTML = `<span class="step">${pad3(s.step)}</span>
    <span class="verb ${s.verb}">${s.verb}</span>
    <span class="txt">${esc(s.screen || "")}${s.is_new ? ' <span class="new-badge">✦ new</span>' : ""} — ${esc(s.intention || "")}</span>`;
  return line;
}
function setFrame(b64) {
  const scr = $("#phoneScreen");
  if (!scr) return;
  let img = scr.querySelector("img");
  if (!img) { scr.innerHTML = ""; img = el("img"); scr.appendChild(img); }
  img.src = "data:image/png;base64," + b64;
}

/* ============================================================================
   View: Trace timeline
   ============================================================================ */
function renderTrace(root) {
  const trace = S.trace?.trace || [];
  const stepShots = S.screens.filter(n => n.startsWith("step_")).sort();
  root.innerHTML = `
    <div class="page-head">
      <h1 class="page-title">Trace</h1>
      <p class="page-desc">Every action from app launch, in order — the exact path the replayer re-executes.
        ${trace.length} actions across ${S.trace?.distinct_screens ?? 0} distinct screens.</p>
    </div>`;
  if (!trace.length) { root.appendChild(emptyState("No trace yet", "Start a run to record the agent's path.", mascot(80, false))); return; }

  const tl = el("div", "timeline");
  trace.forEach((a, i) => {
    const shot = stepShots[i];
    const item = el("div", "tl-item");
    item.innerHTML = `
      <div class="node ${a.target_label ? "new" : ""}"></div>
      <div class="tl-row">
        <div class="tl-thumb">${shot ? `<img loading="lazy" src="/api/screen/${shot}" alt="">` : ""}</div>
        <div class="tl-main">
          <div class="tl-head">
            <span class="tl-step">STEP ${pad3(i + 1)}</span>
            <span class="tl-verb ${a.verb}">${a.verb}</span>
            ${a.target_label ? `<span class="tl-screen">${esc(a.target_label)}</span>` : ""}
          </div>
          <div class="tl-reason">${esc(a.reason || "—")}</div>
          ${a.text ? `<div class="tl-target">typed <b>“${esc(a.text)}”</b></div>` : ""}
          ${a.direction ? `<div class="tl-target">scrolled <b>${esc(a.direction)}</b></div>` : ""}
        </div>
      </div>`;
    tl.appendChild(item);
  });
  root.appendChild(tl);
}

/* ============================================================================
   View: Bugs
   ============================================================================ */
function renderBugs(root) {
  const bugs = S.trace?.bugs || [];
  root.innerHTML = `
    <div class="page-head">
      <h1 class="page-title">Bugs</h1>
      <p class="page-desc">Crashes, layout overflows and jank the oracle caught by draining logcat scoped to
        the app pid — each with the screen at the moment of failure and a repro trace.</p>
    </div>`;
  if (!bugs.length) {
    const es = emptyState("No bugs — clean run", "Gremlin explored the app end-to-end without tripping the oracle. Plant a defect to see detection light up.", `<div style="color:var(--brand)">${I.check.replace('width="2.5"','width="2"')}</div>`);
    es.querySelector(".icon").innerHTML = `<div style="width:72px;height:72px;border-radius:50%;display:grid;place-items:center;background:color-mix(in srgb,var(--brand) 12%,transparent);color:var(--brand)">${I.check}</div>`;
    root.appendChild(es);
    return;
  }
  const grid = el("div", "grid-2");
  bugs.forEach(b => {
    const c = el("div", "card");
    const shot = b.screenshot ? b.screenshot.split("/").pop() : null;
    c.innerHTML = `
      <div class="bug-card ${sevClass(b.severity)}" style="border:0;padding:0">
        <div class="sev">${I.bug} ${esc(b.severity)}</div>
        <div class="t">${esc(b.title || b.kind)}</div>
        <div class="s">found at step ${b.step} · ${esc(b.kind)}</div>
      </div>
      ${b.dart_file ? `<div class="tl-target" style="margin-top:12px">at <b>${esc(b.dart_file)}:${b.dart_line}</b></div>` : ""}
      ${b.log_line ? `<pre class="note" style="margin-top:10px;white-space:pre-wrap;background:var(--surface-2);padding:12px;border-radius:8px;overflow:auto">${esc(b.log_line)}</pre>` : ""}
      ${shot ? `<div class="tl-thumb" style="width:120px;margin-top:12px"><img loading="lazy" src="/api/screen/${shot}"></div>` : ""}`;
    grid.appendChild(c);
  });
  root.appendChild(grid);
}

/* ============================================================================
   View: Benchmark
   ============================================================================ */
function renderBenchmark(root) {
  const g = S.eval?.find(e => e.explorer === "gremlin");
  const m = S.eval?.find(e => e.explorer === "monkey");
  root.innerHTML = `
    <div class="page-head">
      <h1 class="page-title">Benchmark</h1>
      <p class="page-desc">Gremlin vs. <code style="font-family:var(--mono)">adb shell monkey</code> — equal action
        budget, same throwaway account. Coverage is measured as distinct screens reached.</p>
    </div>`;
  if (!g || !m) { root.appendChild(emptyState("No benchmark yet", "Run the eval to compare Gremlin against a random monkey.", mascot(80, false))); return; }

  const max = Math.max(g.distinct_screens, m.distinct_screens, 1);
  const mult = m.distinct_screens ? (g.distinct_screens / m.distinct_screens) : g.distinct_screens;
  const grid = el("div", "bench-grid");
  grid.innerHTML = `
    <div class="card chart">
      <div class="chart-title">Distinct screens reached</div>
      <div class="chart-sub">${g.actions} actions each · higher is better</div>
      <div class="bars">
        ${barRow("Gremlin", g.distinct_screens, max, "var(--series-gremlin)")}
        ${barRow("Monkey", m.distinct_screens, max, "var(--series-monkey)")}
      </div>
      <div class="legend">
        <div class="li"><span class="sw" style="background:var(--series-gremlin)"></span> Gremlin — vision-driven agent</div>
        <div class="li"><span class="sw" style="background:var(--series-monkey)"></span> Monkey — random taps</div>
      </div>
    </div>
    <div style="display:flex;flex-direction:column;gap:16px">
      <div class="callout">
        <div class="big">${mult}×</div>
        <div class="lbl">more screens than random</div>
        <p>The monkey pounds the same first screen; Gremlin reasons about which sections it hasn't
           visited and navigates there deliberately.</p>
      </div>
      <div class="card">
        <div class="chart-title" style="margin-bottom:12px">Head to head</div>
        ${kv("Actions", `${g.actions} vs ${m.actions}`)}
        ${kv("Distinct screens", `${g.distinct_screens} vs ${m.distinct_screens}`)}
        ${kv("Distinct bugs", `${g.distinct_bugs} vs ${m.distinct_bugs}`)}
      </div>
    </div>`;
  root.appendChild(grid);
  root.appendChild(el("p", "note", 'Honest baseline: <b>0 bugs</b> on a clean Scribe build is expected — the coverage gap, not a bug count, is the signal here. Bug detection is demonstrated separately with a planted defect.'));
  requestAnimationFrame(() => $$(".bar-fill", root).forEach(b => b.style.width = b.dataset.w));
}

function barRow(name, val, max, color) {
  const pct = Math.max(4, (val / max) * 100);
  return `<div class="bar-row">
    <div class="bar-name"><span class="swatch" style="background:${color}"></span>${name}</div>
    <div class="bar-track"><div class="bar-fill" data-w="${pct}%" style="background:linear-gradient(90deg, color-mix(in srgb, ${color} 78%, #000), ${color})"></div></div>
    <div class="bar-val">${val}</div>
  </div>`;
}
function kv(k, v) { return `<div style="display:flex;justify-content:space-between;padding:8px 0;border-top:1px solid var(--hair)"><span class="note" style="margin:0">${k}</span><span style="font:600 13px var(--mono)">${v}</span></div>`; }

/* ---- Shared --------------------------------------------------------------- */
function bugCard(b, live) {
  const c = el("div", "bug-card " + sevClass(b.severity));
  c.innerHTML = `<div class="sev">${I.bug} ${esc(b.severity)}</div>
    <div class="t">${esc(b.title || b.kind)}</div>
    <div class="s">found at step ${b.step}</div>`;
  return c;
}
function emptyState(title, desc, iconHTML) {
  const n = el("div", "empty-state");
  n.innerHTML = `<div class="icon">${iconHTML}</div><h3>${esc(title)}</h3><p>${esc(desc)}</p>`;
  return n;
}

/* ============================================================================
   Actions
   ============================================================================ */
async function startRun() {
  if (S.running) return;
  S.running = true; S.done = false;
  S.live = { steps: [], bugs: [], current: null, screenCount: 0 };
  refreshChrome();
  if (location.hash !== "#/live") location.hash = "#/live"; else route();
  try { await fetch("/start", { method: "POST" }); }
  catch (e) { toast("Could not reach the runner."); S.running = false; refreshChrome(); }
}

function toast(msg) {
  const t = el("div", "toast", `${I.bolt} ${esc(msg)}`);
  document.body.appendChild(t);
  setTimeout(() => t.remove(), 3200);
}

/* ============================================================================
   Live WebSocket
   ============================================================================ */
function connectWS() {
  const ws = new WebSocket(`ws://${location.host}/ws`);
  ws.onmessage = (e) => {
    const m = JSON.parse(e.data);
    if (m.event === "step") onStep(m);
    else if (m.event === "bug") onBug(m);
    else if (m.event === "done") onDone(m);
  };
  ws.onclose = () => setTimeout(connectWS, 1500);
}

function onStep(m) {
  S.running = true;
  S.live.current = m;
  S.live.steps.push(m);
  S.live.screenCount = m.distinct_screens;
  refreshChrome();
  if (location.hash === "#/live" || location.hash === "") {
    const empty = $("#phoneEmpty"); if (empty) empty.remove();
    if (m.frame) setFrame(m.frame);
    const intent = $("#liveIntent"); if (intent) intent.textContent = m.intention || "—";
    const meta = $("#liveMeta"); if (meta) meta.innerHTML = liveMetaHTML(m);
    setNum("#liveScreens", m.distinct_screens);
    setNum("#liveStep", m.step);
    const body = $("#logBody");
    if (body) { body.appendChild(logLine(m)); body.scrollTop = body.scrollHeight; }
  }
}
function onBug(m) {
  S.live.bugs.push(m);
  refreshChrome();
  setNum("#liveBugs", S.live.bugs.length);
  const feed = $("#liveBugFeed");
  if (feed) feed.prepend(bugCard(m, true));
  toast(`Bug found: ${m.title}`);
}
async function onDone(m) {
  S.running = false; S.done = true;
  refreshChrome();
  await loadState();            // pull the freshly written trace.json
  if (["#/trace", "#/bugs", "#/", ""].includes(location.hash)) route();
  toast(`Run complete — ${m.screens} screens, ${m.bugs} bug(s)`);
}
function setNum(sel, v) { const n = $(sel); if (n) n.textContent = v; }

/* ============================================================================
   Boot
   ============================================================================ */
function initTheme() {
  const saved = localStorage.getItem("gremlin-theme");
  if (saved) document.documentElement.dataset.theme = saved;
  $("#themeToggle").onclick = () => {
    const cur = document.documentElement.dataset.theme === "light" ? "light" : "dark";
    const next = cur === "light" ? "dark" : "light";
    document.documentElement.dataset.theme = next;
    localStorage.setItem("gremlin-theme", next);
  };
}

document.addEventListener("click", (e) => {
  const nav = e.target.closest("[data-nav]");
  if (nav) { e.preventDefault(); location.hash = "#" + nav.dataset.nav; }
  const item = e.target.closest(".nav-item");
  if (item) location.hash = "#" + item.dataset.route;
});

window.addEventListener("hashchange", route);

(async function boot() {
  $("#brandLogo").innerHTML = mascot(38, false);
  initTheme();
  $("#topStart").onclick = startRun;
  await loadState();
  route();
  connectWS();
})();
