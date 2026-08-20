// DOM overflow/layout audit for the Gremlin console.
// Drives the system Chrome via puppeteer-core, logs in (client-side session),
// visits every route, and reports elements whose content overflows their box
// plus any page-level horizontal scroll. Also writes a screenshot per route.
//
//   node scripts/dom_audit.mjs [width] [height]
//
// Needs the console running (`npm run dev` in frontend/) and Chrome on the box.
// Override either with CHROME=/path/to/chrome or BASE_URL=http://host:port.
import { createRequire } from "node:module";
import { mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const ROOT = dirname(dirname(fileURLToPath(import.meta.url)));
// puppeteer-core is a devDependency of the console, not of the repo root, so
// resolve it from there rather than relying on where node was invoked. Recent
// versions ship ESM only, so resolve the path with createRequire but load it
// with a dynamic import — require() of an ESM module throws ERR_REQUIRE_ESM.
const require = createRequire(join(ROOT, "frontend/"));
const puppeteer = (await import(
  pathToFileURL(require.resolve("puppeteer-core")).href
)).default;

const W = Number(process.argv[2] || 1920);
const H = Number(process.argv[3] || 1080);
const BASE = process.env.BASE_URL || "http://localhost:5173";
const OUT = process.env.OUT_DIR || join(ROOT, "runs/dom_audit");
mkdirSync(OUT, { recursive: true });

const ROUTES = [
  ["overview", "/app"],
  ["live", "/app/live"],
  ["trace", "/app/trace"],
  ["bugs", "/app/bugs"],
  ["benchmark", "/app/benchmark"],
  ["settings", "/app/settings"],
  ["setup", "/app/setup"],
];

// Runs in the page: find real overflow. An element overflows if its content is
// wider/taller than its box AND it isn't an intentional scroll container.
const PROBE = () => {
  const bad = [];
  const desc = (el) => {
    const cls = (el.className && el.className.baseVal !== undefined ? el.className.baseVal : el.className) || "";
    const txt = (el.textContent || "").trim().replace(/\s+/g, " ").slice(0, 40);
    return `${el.tagName.toLowerCase()}${cls ? "." + String(cls).trim().split(/\s+/).join(".") : ""}${txt ? ` «${txt}»` : ""}`;
  };
  for (const el of document.querySelectorAll("*")) {
    const cs = getComputedStyle(el);
    if (cs.display === "none" || cs.visibility === "hidden") continue;
    const oxw = el.scrollWidth - el.clientWidth;
    // A real defect: content spills horizontally out of a box that is NEITHER a
    // scroll container (auto/scroll) NOR intentionally clipped (hidden). That is
    // exactly the "text overflowing" class — it visibly escapes and can push the
    // page. overflow:hidden bleeds (decorative sparklines, cover thumbs) are
    // contained by definition and excluded.
    if (oxw > 1 && cs.overflowX === "visible") bad.push({ axis: "x", by: oxw, sel: desc(el) });
  }
  const doc = document.scrollingElement;
  const pageScrollX = doc.scrollWidth - doc.clientWidth;
  return { bad, pageScrollX, vw: window.innerWidth };
};

const browser = await puppeteer.launch({
  executablePath: process.env.CHROME || "/usr/bin/google-chrome",
  headless: "new",
  args: ["--no-sandbox", "--disable-gpu", `--window-size=${W},${H}`],
});
const page = await browser.newPage();
await page.setViewport({ width: W, height: H });

// Seed a client-side session on the right origin, then navigate into the app.
await page.goto(BASE + "/", { waitUntil: "networkidle0" });
await page.evaluate(() => {
  localStorage.setItem("gremlin-session", JSON.stringify({ name: "Audit", email: "audit@example.com", at: Date.now() }));
});

let total = 0;
for (const [name, route] of ROUTES) {
  await page.goto(BASE + route, { waitUntil: "networkidle0" });
  await new Promise((r) => setTimeout(r, 500)); // let animations/data settle
  const res = await page.evaluate(PROBE);
  await page.screenshot({ path: `${OUT}/${name}.png` });
  const flags = res.bad.length + (res.pageScrollX > 1 ? 1 : 0);
  total += flags;
  console.log(`\n=== ${name} (${route}) @ ${W}x${H} ===`);
  if (res.pageScrollX > 1) console.log(`  ⚠ PAGE scrolls horizontally by ${res.pageScrollX}px (vw=${res.vw})`);
  if (res.bad.length === 0) console.log("  ✓ no element overflow");
  else res.bad.slice(0, 25).forEach((b) => console.log(`  ⚠ overflow-${b.axis} +${b.by}px  ${b.sel}`));
}
console.log(`\nTOTAL FLAGS: ${total}  ·  shots in ${OUT}`);
await browser.close();
process.exit(total > 0 ? 1 : 0);
