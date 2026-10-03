#!/usr/bin/env bash
# Bring the whole thing up: model server, console build, console.
#
#   bash scripts/start.sh            # http://127.0.0.1:8000
#   bash scripts/start.sh --port 9000
#
# Everything after that happens in the browser — pick a device, pick an app,
# start a run. A headless run is still `python run.py`.

set -euo pipefail
cd "$(dirname "$0")/.."

say() { printf '\n\e[1m==> %s\e[0m\n' "$*"; }
die() { printf '\n\e[31merror: %s\e[0m\n' "$*" >&2; exit 1; }

[ -f .env ] || die "no .env — copy .env.example and fill it in"
[ -x .venv/bin/python ] || die "no .venv — python -m venv .venv && .venv/bin/pip install -r requirements.txt"

set -a; . ./.env; set +a

say "model backend"
if [ "${LLM_PROVIDER:-}" = "local" ]; then
  if ! curl -sf -m 2 "${LOCAL_BASE_URL%/v1}/api/tags" >/dev/null; then
    command -v ollama >/dev/null || die "LOCAL_BASE_URL is not answering and ollama is not installed"
    say "starting ollama"
    ollama serve >/tmp/gremlin-ollama.log 2>&1 &
    for _ in $(seq 20); do curl -sf -m 1 "${LOCAL_BASE_URL%/v1}/api/tags" >/dev/null && break; sleep 1; done
  fi
  ollama list 2>/dev/null | grep -q "^${LOCAL_MODEL%% *}[[:space:]]" \
    || echo "    warning: $LOCAL_MODEL not pulled — run: ollama pull $LOCAL_MODEL"
  echo "    $LLM_PROVIDER  $LOCAL_MODEL  $LOCAL_BASE_URL"
else
  echo "    $LLM_PROVIDER (remote)"
fi

say "device"
adb start-server >/dev/null 2>&1 || true
attached=$(adb devices -l | sed -n '2,$p' | grep .) || true
if [ -n "$attached" ]; then
  printf '%s\n' "$attached" | sed 's/^/    /'
  # An unauthorised phone looks connected but refuses every command, so a run
  # would fail minutes later for a reason only the phone's screen explains.
  printf '%s' "$attached" | grep -q unauthorized \
    && echo "    -> accept the 'Allow USB debugging?' prompt on the phone"
else
  avds=$("${ANDROID_HOME:-$HOME/Android/Sdk}/emulator/emulator" -list-avds 2>/dev/null | grep . | paste -sd, -) || true
  if [ -n "$avds" ]; then
    echo "    none attached — emulator available ($avds): boot it from the console,"
    echo "    or a headless run boots it by itself (python run.py --emulator)"
  else
    echo "    none attached — plug in a phone, or start an emulator from the console"
  fi
fi

# The console is a built SPA; rebuild only when a source file is newer than it.
say "console"
if [ ! -f frontend/dist/index.html ] \
   || [ -n "$(find frontend/src frontend/public frontend/index.html frontend/package.json \
                -newer frontend/dist/index.html -print -quit 2>/dev/null)" ]; then
  [ -d frontend/node_modules ] || (cd frontend && npm install)
  (cd frontend && npm run build)
else
  echo "    build up to date"
fi

# --port belongs to the dashboard; we only read it to know where to point the
# browser. Opening happens in the background because the server never returns.
port=8000
prev=""
for a in "$@"; do [ "$prev" = "--port" ] && port=$a; prev=$a; done
if command -v xdg-open >/dev/null; then
  ( for _ in $(seq 30); do
      curl -sf -m 1 -o /dev/null "http://127.0.0.1:$port/" && break; sleep 1
    done
    xdg-open "http://127.0.0.1:$port/" >/dev/null 2>&1 ) &
fi

say "starting console"
exec .venv/bin/python -m gremlin.dashboard "$@"
