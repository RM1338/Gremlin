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
`binder_linux` loaded. It is ephemeral by design — do not add a data volume to
make it persist, because "fresh instance per run" is the property that makes a
benchmark reproducible.

Unless a sandbox is in use, the device is real hardware someone is holding. A
run holds the screen awake and drives taps for minutes at a time, so don't start
one against an app that is not the target, and don't leave `svc power stayon`
set after a run ends.

## Model backend

`LLM_PROVIDER` selects the vision backend: `gemini`, `groq`, or `local`.
`local` is any server speaking the OpenAI chat-completions shape — Ollama,
vLLM, llama.cpp:

```
LOCAL_BASE_URL=http://localhost:11434/v1
LOCAL_MODEL=qwen3-vl:32b
```

Swapping between them is configuration, never code.

Tier-2 fixes shell out to a coding agent selected by `FIX_BACKEND` (default
`prompt`, which writes a paste-ready prompt and edits nothing). The `claude`
backend needs the Claude Code CLI installed and logged in.

## Console

The console is the React app in `frontend/`, served by `gremlin/dashboard.py`.
It must be built before first use:

```
cd frontend && npm install && npm run build
python -m gremlin.dashboard
```

Runs do not need it — `python run.py` works on its own.

## Conventions

- Backends normalise their own errors to `vision.ModelError` /
  `ModelQuotaError` so the explorer can end a run gracefully.
- Never commit `.env`, run artifacts under `runs/`, `frontend/dist/`, or
  anything under `.claude/`.
