# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# Gremlin

An autonomous UI-testing agent for Android apps. It explores a running app on a
device or emulator, decides what to tap from a screenshot, detects defects, and
escalates through a three-tier remediation ladder — T0 report, T1 deterministic
retry, T2 model-authored fix behind guard/rebuild/replay gates.

## Where this runs

Natively on the developer's machine: a virtualenv, the Android SDK's `adb`, and
a phone on USB, an emulator, or a sandbox container. Gremlin itself is never
containerised — run `python run.py` directly.

The sandbox (`gremlin/sandbox.py`) containerises the *device*, not Gremlin:
redroid on the host kernel, adb on `localhost:5555`, Linux only because it needs
binder. It is ephemeral by design — do not add a data volume to make it
persist, because "fresh instance per run" is the property that makes a
benchmark reproducible.

Unless a sandbox or Gremlin's own emulator is in use, the device is real
hardware someone is holding. A run holds the screen awake and drives taps for
minutes at a time, so don't start one against an app that is not the target,
and don't leave `svc power stayon` set after a run ends.

### Which device a run gets

`run.py:_device_plan` is the single place precedence is decided, and
`tests/device_plan_test.py` pins it: `--emulator`/`--avd` > `--serial` > an
already-running sandbox > `--sandbox` > an attached device > the sandbox if it
can start > an AVD. An attached phone always wins over booting anything.

The emulator stands in for the sandbox where the kernel has no binder (Arch's
stock and Omarchy kernels do not), so it is treated the same way:

- **Always headless.** The console can only boot `-no-window`; `run.py` needs
  `--show-emulator` for a window. A window is an input path into the device
  under test, and a headless boot refuses to adopt a windowed emulator
  (`emulator.has_window`).
- **`-gpu host` by default.** Every software renderer the emulator ships
  segfaults its RenderThread a few steps into the Flutter bench fixture.
  `GREMLIN_EMULATOR_GPU` overrides.
- **Only Gremlin-owned devices get apps installed** (`sandbox.owns_device`: the
  sandbox, or a windowless emulator). A missing package on a phone means the
  target is wrong, and building someone's project uninvited is not the fix.

## Commands

```
python -m venv .venv && .venv/bin/pip install -r requirements.txt

.venv/bin/python run.py --list                                   # detected app projects
.venv/bin/python run.py --project ~/Projects/gremlin-bench-flutter
.venv/bin/python run.py --project <dir> --policy coverage        # no model, no quota
.venv/bin/python run.py --url http://localhost:5173              # web, no device
.venv/bin/python -m gremlin.autofix --project <dir>              # Tier 1/2
.venv/bin/python -m gremlin.eval --project <dir> --actions 30 --monkey
bash scripts/start.sh                                            # console + model + device check
```

`--policy coverage` is the no-model ablation arm, and the right way to
exercise the device path without spending Gemini/Groq quota.

**Tests are plain scripts, not pytest** — there is no test runner or linter
configured. Run one with `.venv/bin/python tests/<name>_test.py`; each file's
`__main__` block lists what it runs. `oracle_test` and `smoke_test` need a
device attached; `web_*` tests launch a real browser; the rest are offline.

The demo apps are **not in this repo**. They live as separate git repos under
`~/Projects` (`GREMLIN_PROJECTS_ROOT`), one per fixture, because Tier 2 commits
and reverts against the repo enclosing the app — see `fixtures/README.md`.

## Architecture

The design rests on one split: **the model decides where to go; the runtime's
own log decides what is broken.** The vision model is never asked whether a
screen looks wrong.

- **Explorer loop** (`explorer.py`): observe (screenshot + elements) → decide
  (`policy.decide`, or `decide_coverage_only`) → act → check (drain the
  oracle). Exploration is coverage-driven: tapped controls are tracked per
  screen id, so screen identity (`screen_memory.py`) directly controls whether
  the agent loops. Model outages (`ModelError`) and a dead device
  (`DeviceLost`) end a run early but keep and report what was found.
- **Oracle** (`oracle.py`): exact string classification of log lines into
  `Signal`s, deduplicated by source location. Android feeds it `logcat`
  pinned to the app's pid, re-resolved every step because a detected crash
  restarts the app under a new pid.
- **Platforms** (`platforms.py`): one `Platform` record per toolkit (Flutter,
  React Native, web) holding its signal vocabulary, source-location grammar
  and build command. Adding a toolkit should touch only this file.
- **Drivers**: `device.Device` (adb) and `web.WebDriver` (Playwright) expose the
  same verbs, so `Explorer` never knows which it has. The web driver renders
  DevTools events as log-shaped lines on purpose, so classification, dedup,
  reporter, trace and console are shared rather than duplicated. A driver may
  supply `screen_key()` to replace perceptual-hash screen identity (web uses
  route + visible `<h1>`).
- **Tier 2** (`fixer.py` + `gates.py` + `replayer.py`): a coding agent
  (`fix_backend.py`) patches a scratch branch; the diff is guarded, the app
  rebuilt, the recorded trace replayed, and three gates must pass — signal
  gone, screen still looks like itself, nothing new broke.
- **Console** (`dashboard.py` + `frontend/`): FastAPI serving the built React
  app, with a WebSocket for live runs. It runs the explorer on a thread, so a
  code change needs a console restart to take effect.

## Model backend

`LLM_PROVIDER` selects the vision backend: `gemini`, `groq`, or `local`.
`local` is any server speaking the OpenAI chat-completions shape — Ollama,
vLLM, llama.cpp:

```
LOCAL_BASE_URL=http://localhost:11434/v1
LOCAL_MODEL=qwen3-vl:32b
```

Swapping between them is configuration, never code. `GEMINI_API_KEY` and
`GROQ_API_KEY` accept comma-separated key lists with failover.

Tier-2 fixes shell out to a coding agent selected by `FIX_BACKEND` (default
`prompt`, which writes a paste-ready prompt and edits nothing). The `claude`
backend needs the Claude Code CLI installed and logged in.

## Web

`python run.py --url ...` drives a browser through `gremlin/web.py`. It tries
the system Chrome (`channel="chrome"`) first and falls back to Playwright's
Chromium (`python -m playwright install chromium`). Tier 2 does not cover web
yet: a page is served, not built, so the rebuild/replay gates have nothing to
rebuild.

## Console

The console is the React app in `frontend/`, served by `gremlin/dashboard.py`.
It must be built before first use:

```
cd frontend && npm install && npm run build
python -m gremlin.dashboard
```

Runs do not need it — `python run.py` works on its own.

## Conventions

- `docs/KNOWN_ISSUES.md` is the ledger of defects and methodological holes
  (G1, G2, …), each tied to the success metric it threatens. When fixing one,
  update its status there with what was measured, not just what changed.
- Backends normalise their own errors to `vision.ModelError` /
  `ModelQuotaError` so the explorer can end a run gracefully.
- Comments explain *why* — usually the failure that motivated the code. Match
  that when editing.
- Never commit `.env`, run artifacts under `runs/`, `frontend/dist/`, or
  anything under `.claude/`.
