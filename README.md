<div align="center">

<img src="docs/media/banner.gif" alt="Gremlin — autonomous UI testing for Flutter" width="820" />

**An autonomous agent that plays a Flutter app like a confused user, files a reproducible bug report every time the framework screams, and — opt-in — patches the bug and replays the exact taps to prove it is gone.**

</div>

---

## The one idea

Flutter reports its own failures out loud. A layout that does not fit prints `A RenderFlex overflowed by 42 pixels`. An uncaught Dart error prints a stack trace. A native crash prints `FATAL EXCEPTION`. So Gremlin never has to *judge* whether a screen is broken — a judgment a language model is unreliable at. It only has to *reach* the screens where the framework confesses.

> The model decides **where to go**. The log decides **what is broken**.

## Two ideas worth stealing

1. **Oracle vs. policy split.** Detection is exact (string match on `logcat`); exploration is the intelligent part (a vision model choosing where to tap). The model is never asked "does this look wrong?" — that question has no checkable answer and invites hallucinated bugs.

2. **A fix is not a fix until the taps that broke it are replayed.** Every bug report carries the exact tap sequence that produced it, so a proposed patch can be graded with no human in the room: cold-start, replay the trace, check the signal is gone. And because "make the log line disappear" is not the same as "fix the bug," a patch must clear three gates (signal gone · screen still looks like itself · nothing new broke), not one.

## How it works

```
Observe ──▶ Decide ──▶ Act ──▶ Check ──┐
screenshot  vision +   tap/type  read the │
            memory     /back     log      │
   ▲                                       │
   └───────────── clean ───────────────────┘
                  failure signal ─▶ bug report (screenshot + log line + trace)
```

Exploration is **coverage-driven**: Gremlin tracks every control it has tapped on each screen and works through the untapped ones, so it does not loop on the same button, and it stops early once a screen is exhausted.

## The three output tiers

Detection always runs. What you do with a bug is your choice — and most developers never need an autonomous agent.

- **Tier 0 — Report.** A markdown file per bug: screenshot, matched log line with context, source location, reproduction steps. Always produced, no model involved, nothing to trust.
- **Tier 1 — Portable prompt.** The same report rendered as a self-contained prompt with the relevant source inlined. Paste it into whichever assistant you already use. Grants nothing write access. This is the default, because it works for everyone.
- **Tier 2 — Autofix.** Opt-in. A coding agent edits the source on a scratch branch; Gremlin guards the diff, rebuilds, replays the exact trace, and applies the three gates. A patch that clears all three is left on its branch for a human to read; a patch that fails any gate is reverted and the report survives.

## Pluggable fix backends

Tier 2 needs *some* coding agent to turn a prompt into an edit, and not everyone uses the same one. The backend is selected by `FIX_BACKEND`, the same way the vision policy is selected by `LLM_PROVIDER`. The guard, rebuild, replay, and gates around it are identical no matter which agent writes the diff — that machinery, not the choice of agent, is what makes a fix trustworthy.

| `FIX_BACKEND` | What it does |
|---|---|
| `prompt` *(default)* | Writes the portable Tier-1 prompt and touches no source. Works for every developer. |
| `claude` | Headless Claude Code (`claude -p`), the reference agent. |
| `codex` | OpenAI Codex CLI (`codex exec`). |
| `copilot` | GitHub Copilot CLI (`copilot -p`). |
| `command` | A user-defined template in `FIX_CMD`, e.g. `FIX_CMD='my-agent --repo {cwd} --prompt-file {prompt_file}'` — the universal escape hatch for any agent. |

```bash
# Hand a paste-ready prompt to whatever you use (no agent required):
python -m gremlin.autofix --project ~/Projects/MyApp                      # backend defaults to prompt

# Or let an agent apply and grade a fix directly:
python -m gremlin.autofix --project ~/Projects/MyApp --backend claude --kind renderflex-overflow
```

Example of a verified Tier-2 run:

```
[VERIFIED ✓] renderflex-overflow  (branch gremlin/fix-renderflex-overflow-...)
    gate signal-gone        pass — target signal absent on replay
    gate screen-looks-same  pass — perceptual distance 18 (<= 32)
    gate no-new-breakage    pass — no new signals introduced
    verified — patch cleared all three gates; left on branch for review
```

## The Gremlin probe (for modern Flutter)

Modern Flutter renders with Impeller, and on many devices the framework no longer forwards its own error text (overflow warnings, uncaught Dart exceptions) to `logcat` — the on-screen red box still appears, but the console line Gremlin's oracle greps for never arrives. To make detection reliable, an app under test can opt in with a tiny hook in `main()`:

```dart
import 'gremlin_probe.dart';

void main() {
  installGremlinProbe();   // forwards framework/Dart errors to logcat, one line each
  runApp(const MyApp());
}
```

It installs `FlutterError.onError` and `PlatformDispatcher.onError` and prints a single, greppable line per error (plus the source location). It is the same hook crash-reporting SDKs install, so it composes with Sentry or Crashlytics — it only adds a print, it swallows nothing. Native crashes are caught with or without it, because Android logs those itself. A ready-to-copy `gremlin_probe.dart` lives in the bundled demo fixture at [`fixtures/gremlin_bench/lib/`](fixtures/gremlin_bench/lib/gremlin_probe.dart).

## Layout

| Module | Role |
|---|---|
| `gremlin/device.py` | adb wrapper: screenshot, tap, type, back, scroll, launch |
| `gremlin/grounding.py` | `uiautomator dump` to tappable elements with coordinates |
| `gremlin/oracle.py` | background `logcat` watcher; exact signal matching |
| `gremlin/screen_memory.py` | perceptual-hash visited-screen memory |
| `gremlin/platforms.py` | one `Platform` record per UI toolkit — the only toolkit-specific knowledge |
| `gremlin/targets.py` | detect app projects to package / activity / source / platform per app |
| `gremlin/emulator.py` | boot and manage an Android emulator, so a run needs no physical phone |
| `gremlin/policy.py` | the exploration prompt and JSON action parsing |
| `gremlin/vision.py` + `gemini.py` + `groq.py` | pluggable free vision backend (Gemini / Groq) |
| `gremlin/explorer.py` | the observe / decide / act / check loop |
| `gremlin/reporter.py` | Tier 0 markdown and Tier 1 portable fix prompt |
| `gremlin/replayer.py` | deterministic trace replay, no model |
| `gremlin/gates.py` | the three gates plus the static anti-cheat guard |
| `gremlin/fix_backend.py` | pluggable Tier-2 coding agent (claude / codex / copilot / command) |
| `gremlin/fixer.py` | Tier-2 fix, guard, rebuild, replay, gate |
| `gremlin/autofix.py` | Tier-2 CLI entrypoint |
| `gremlin/dashboard.py` | FastAPI backend: serves the React console + live WebSocket + JSON APIs |
| `frontend/` | React console (landing, auth, Overview / Live / Trace / Bugs / Benchmark) |
| `gremlin/eval.py` | Gremlin vs. `adb shell monkey` baseline |
| `fixtures/gremlin_bench/` | a deliberately broken Flutter app — the reproducible demo and self-test |
| `fixtures/gremlin_bench_rn/` | the React Native mirror of the above — proves the platform abstraction |
| `tests/` | offline oracle checks and a device smoke test |

## Install

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env      # then add a free API key (see below)
```

The **exploration policy** runs on a free LLM tier. Default is Gemini (`GEMINI_API_KEY`, from https://aistudio.google.com/apikey); if its daily free quota runs out, set `LLM_PROVIDER=groq` with a `GROQ_API_KEY` (https://console.groq.com/keys), whose free tier is more generous. Rate limits are retried with backoff; a spent daily quota ends a run early with partial results rather than crashing.

Requires `adb` on `PATH` with a device attached, and — for Tier 2 — `flutter`.

## Connect your phone

Gremlin drives a **real device** over USB (it does not build or install the app), so the app you test must already be on the phone. The console's **Setup** page has the full walkthrough; the short version:

1. On the phone: **Settings → About phone**, tap **Build number** seven times to unlock Developer Options.
2. **Settings → Developer options → USB debugging = ON** (also enable *Stay awake*).
3. Plug in via USB, set the USB mode to **File transfer / MTP**.
4. Accept the **Allow USB debugging?** prompt (tick *Always allow*).
5. Verify: `adb devices` lists it as `device`.

Use a **throwaway account** with no real data — the agent taps, types, and scrolls freely.

## Usage

```bash
# choose which Flutter app to test — the target is auto-detected from the project
.venv/bin/python run.py --list                       # list detected Flutter projects
.venv/bin/python run.py --project ~/Projects/MyApp   # test a specific project
.venv/bin/python run.py --package com.foo.bar        # test an installed package directly

# explore and write bug reports
.venv/bin/python run.py --steps 40

# turn the bugs into fixes (prompt by default; --backend for an agent)
.venv/bin/python -m gremlin.autofix --project ~/Projects/MyApp
.venv/bin/python -m gremlin.autofix --project ~/Projects/MyApp --backend claude

# build the React console once, then serve it
cd frontend && npm install && npm run build && cd ..
.venv/bin/python -m gremlin.dashboard                # open http://127.0.0.1:8000

# compare against the Monkey (see caution)
.venv/bin/python -m gremlin.eval --actions 30 --monkey
```

## The console

The console is a React app in `frontend/`. `python -m gremlin.dashboard` serves the built `frontend/dist/` if present, and falls back to a legacy one-file UI otherwise. It has a landing page, a demo sign-in (client-side session — swap in real auth for production), and the console pages (Overview / Live run / Trace / Bugs / Benchmark) with run-complete notifications. A **target picker** in the top bar lists auto-detected Flutter projects (full capability) and every app installed on the device (explore-only).

## Caution

Automated exploration taps real controls. On a signed-in app with real data it can delete things. Prefer an emulator or a throwaway account for long unattended runs. Tier 2 operates only on a **clean** working tree, one commit per bug, on a scratch branch — it never pushes or merges; the final judgment is always a human reading a small, pre-tested diff.

## Scope

Gremlin verifies the app does not *visibly fail*; it does not verify the app is *correct*. Semantic assertions about behaviour are out of scope. Single-platform (Android): iOS has no `adb` and no equivalently chatty log.
