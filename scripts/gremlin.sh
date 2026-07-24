#!/usr/bin/env bash
# One command that takes you from a clean checkout to bug reports.
#
# Run this ON THE HOST. It does the setup, starts the model, picks a device and
# runs the exploration, then tells you where the reports landed.
#
#   bash scripts/gremlin.sh                 # auto: a connected phone if there
#                                           # is one, otherwise an emulator
#   bash scripts/gremlin.sh --emulator      # force the emulator
#   bash scripts/gremlin.sh --usb           # force a USB phone via the host
#                                           # adb bridge
#   bash scripts/gremlin.sh --serial NAME   # a device you attached yourself
#   bash scripts/gremlin.sh doctor          # check the machine, change nothing
#
# Anything it does not recognise is passed through to run.py, so the usual
# flags still work:
#
#   bash scripts/gremlin.sh --emulator --steps 40
#
# The model backend — ollama or vllm — is read from LOCAL_BASE_URL in .env, so
# there is nothing extra to keep in sync. Override it only when that URL cannot
# say which it is (a server reached by bare IP):
#
#   GREMLIN_BACKEND=vllm bash scripts/gremlin.sh
#
# Safety on a shared host: every Docker call here goes through `docker compose`,
# which is scoped to the `gremlin` project by the `name:` field in compose.yml.
# Nothing here stops, removes or prunes anything it did not create, and nothing
# needs sudo.

set -uo pipefail
cd "$(dirname "$0")/.."

ADB_DIR=${GREMLIN_ADB_DIR:-$HOME/.gremlin/adb}

# --- output -----------------------------------------------------------------
# Only colour a real terminal, so redirecting to a log file stays readable.
if [ -t 1 ]; then
  B=$'\e[1m'; DIM=$'\e[2m'; R=$'\e[31m'; Y=$'\e[33m'; G=$'\e[32m'; X=$'\e[0m'
else
  B=""; DIM=""; R=""; Y=""; G=""; X=""
fi
step() { printf '\n%s==> %s%s\n' "$B" "$*" "$X"; }
info() { printf '    %s\n' "$*"; }
warn() { printf '%s    warning: %s%s\n' "$Y" "$*" "$X" >&2; }
die()  { printf '%s\nerror: %s%s\n' "$R" "$*" "$X" >&2; exit 1; }

# --- argument parsing -------------------------------------------------------
# Device selection is ours; everything else belongs to run.py. Collecting the
# rest verbatim means this wrapper never has to track run.py's flags.
MODE=auto
SERIAL=""
PASSTHRU=()

while [ $# -gt 0 ]; do
  case "$1" in
    doctor)     MODE=doctor; shift ;;
    --emulator) MODE=emulator; shift ;;
    --usb)      MODE=usb; shift ;;
    --serial)   MODE=serial; SERIAL=${2:-}; [ -n "$SERIAL" ] || die "--serial needs a value"; shift 2 ;;
    # Print the header comment as the help text, stopping at the first line
    # that is not a comment — so editing the header never desyncs --help.
    -h|--help)  awk 'NR>1 && /^#/ {sub(/^# ?/,""); print; next} NR>1 {exit}' "$0"; exit 0 ;;
    *)          PASSTHRU+=("$1"); shift ;;
  esac
done

# --- preflight --------------------------------------------------------------
preflight() {
  step "Checking the machine"

  command -v docker >/dev/null 2>&1 || die "docker is not installed or not on PATH."
  docker compose version >/dev/null 2>&1 || die "the docker compose plugin is missing (v2 required)."
  docker info >/dev/null 2>&1 || die "cannot reach the Docker daemon. Your account may not be in the 'docker' group."
  info "docker ok"

  # Model weights and images land under the Docker root, not $HOME, so this is
  # the number that matters — and it is the one that has bitten this project.
  local root avail
  root=$(docker info --format '{{.DockerRootDir}}' 2>/dev/null)
  avail=$(df -BG --output=avail "$root" 2>/dev/null | tail -1 | tr -dc '0-9')
  if [ -n "$avail" ]; then
    if [ "$avail" -lt 15 ]; then
      warn "only ${avail} GB free under $root — an image pull or an emulator boot may fail."
    else
      info "disk ok (${avail} GB free under $root)"
    fi
  fi

  # Informational only. A GPU already in use is somebody else's job, and the
  # polite response is a smaller share, which lab_env.sh already handles.
  if command -v nvidia-smi >/dev/null 2>&1; then
    local busy
    busy=$(nvidia-smi --query-compute-apps=pid --format=csv,noheader 2>/dev/null | grep -cxE '[0-9]+' || true)
    [ "${busy:-0}" -gt 0 ] && warn "$busy process(es) already on the GPU — leaving VRAM settings alone."
    info "gpu visible"
  else
    info "no nvidia-smi — CPU-only inference will be slow but works"
  fi

  # The emulator needs no privilege to run in software, but if the door happens
  # to be open there is no reason to take the slow path. This is the one test
  # that settles it, and it costs a second.
  if docker run --rm --device /dev/kvm alpine true >/dev/null 2>&1; then
    info "${G}/dev/kvm CAN be mapped into a container${X} — hardware acceleration is available."
    info "  use: docker compose -f compose.yml -f docker/compose.emulator.yml run --rm gremlin"
  else
    info "/dev/kvm cannot be mapped in — the emulator will run in software (slow, but it works)"
  fi
}

# --- model backend ----------------------------------------------------------
# Read one key out of .env. Used for both the backend choice and the model tag,
# so a quoted value is unquoted in exactly one place.
env_value() {
  grep -E "^\s*$1=" .env 2>/dev/null | tail -1 | cut -d= -f2- | tr -d '"'"'"' '
}

# Which service answers the exploration steps: `ollama` or `vllm`.
#
# Derived from LOCAL_BASE_URL rather than asked for separately, because that is
# the address the engine actually dials. A separate switch could disagree with
# it, and the failure would arrive as connection-refused at the first step of a
# run rather than here. GREMLIN_BACKEND overrides when the URL is ambiguous —
# a server reached by bare IP, say.
backend() {
  if [ -n "${GREMLIN_BACKEND:-}" ]; then echo "$GREMLIN_BACKEND"; return; fi
  case "$(env_value LOCAL_BASE_URL)" in
    *vllm*|*:8000*)             echo vllm ;;
    *ollama*|*:11434*|*:11435*) echo ollama ;;
    # Unrecognised, including empty: keep the historical default rather than
    # guessing, but say so — starting the wrong one claims VRAM on a shared card.
    *)                          echo ollama ;;
  esac
}

# Block until the backend answers. Both are slow to become ready for different
# reasons — ollama has to start, vLLM has to fetch and load tens of GB of
# weights — so this waits rather than racing, and says what it is waiting for.
await_backend() {
  local svc=$1 probe=$2 tries=$3 gap=$4 i
  for i in $(seq 1 "$tries"); do
    eval "$probe" >/dev/null 2>&1 && return 0
    # A minute of silence looks like a hang; it usually is not.
    [ $((i % (60 / gap))) -eq 0 ] && info "still waiting for $svc ($((i * gap / 60))m)"
    sleep "$gap"
  done
  return 1
}

# --- setup ------------------------------------------------------------------
setup() {
  step "Preparing host state"
  # Bind mounts whose host directory is absent are created root-owned, and
  # without sudo they can then be neither written nor deleted. Creating them
  # here is what stops that.
  mkdir -p "$HOME/.gremlin/claude" "$HOME/.gremlin/gitstate" "$ADB_DIR"
  chmod 700 "$HOME/.gremlin"
  info "~/.gremlin ready"

  if [ ! -e .env ]; then
    bash scripts/lab_env.sh >/dev/null 2>&1 || warn "lab_env.sh did not complete — check .env by hand."
    info ".env created"
  else
    info ".env already present, left alone"
  fi

  step "Starting the model backend"
  BACKEND=$(backend)
  info "backend: $BACKEND  (from LOCAL_BASE_URL; override with GREMLIN_BACKEND)"

  # Both services sit behind compose profiles so neither starts by accident.
  # Naming the profile is what makes `up` reach them.
  docker compose --profile "$BACKEND" up -d "$BACKEND" \
    || die "could not start the $BACKEND service."

  case "$BACKEND" in
    ollama)
      await_backend ollama "docker compose exec -T ollama ollama list" 60 2 \
        || die "ollama did not become ready. Check: docker compose logs ollama"

      # Read the tag from .env so this never drifts from what the engine asks
      # for. Only meaningful for ollama: under vLLM, LOCAL_MODEL is the
      # --served-model-name alias, which is not a pullable tag.
      local model
      model=$(env_value LOCAL_MODEL)
      model=${model:-qwen2.5vl:7b}

      if docker compose exec -T ollama ollama list 2>/dev/null | grep -q "^${model}[[:space:]]"; then
        info "model $model already pulled"
      else
        info "pulling $model — first time only, this is a large download"
        docker compose exec -T ollama ollama pull "$model" \
          || die "could not pull $model. Check the tag in .env and your network."
      fi
      ;;
    vllm)
      # No pull step: vLLM fetches VLLM_MODEL itself on first start, into the
      # hf-cache volume. That download is why the wait here is measured in tens
      # of minutes rather than seconds, and why it only happens once.
      local checkpoint
      checkpoint=$(env_value VLLM_MODEL)
      info "vLLM loads ${checkpoint:-Qwen/Qwen3-VL-8B-Instruct}; a first start downloads the weights."
      info "watch it with: docker compose logs -f vllm"
      # Mirrors the healthcheck in compose.yml, so "ready" means the same thing
      # to this script as it does to compose.
      await_backend vllm "docker compose exec -T vllm curl -sf http://localhost:8000/health" 600 4 \
        || die "vLLM did not become ready within 40 minutes. Check: docker compose logs vllm"
      ;;
    *)
      die "unknown backend '$BACKEND'. Set GREMLIN_BACKEND to 'ollama' or 'vllm'."
      ;;
  esac

  step "Building the dev image"
  # Cheap when nothing changed; this is what picks up a UID/GID change.
  docker compose build gremlin || die "image build failed."
  info "image ready"

  # Tier 2 shells out to `claude -p`; without a login the run still finds and
  # reports bugs, it just cannot author fixes. Worth a warning, not a failure.
  if [ ! -e "$HOME/.gremlin/claude/.credentials.json" ] \
     && [ -z "$(ls -A "$HOME/.gremlin/claude" 2>/dev/null)" ]; then
    warn "Claude Code is not logged in — Tier 2 auto-fix will be skipped."
    warn "To enable it: docker compose run --rm gremlin claude"
  fi
}

# --- device selection -------------------------------------------------------
# Returns the run.py flags for the chosen device on stdout.
choose_device() {
  local visible=""
  if command -v adb >/dev/null 2>&1; then
    # Scoped to the shared socket so this never inspects another user's server.
    visible=$(ADB_SERVER_SOCKET="localfilesystem:$ADB_DIR/adb.sock" \
              adb devices 2>/dev/null | awk 'NR>1 && $2=="device" {print $1}' | head -1)
  fi

  case "$MODE" in
    serial)
      echo "--serial $SERIAL"
      ;;
    usb)
      command -v adb >/dev/null 2>&1 \
        || die "adb is not on this host, and a USB phone needs it here — the bus cannot enter the container. See scripts/host_adb.sh."
      bash scripts/host_adb.sh start >/dev/null 2>&1
      visible=$(ADB_SERVER_SOCKET="localfilesystem:$ADB_DIR/adb.sock" \
                adb devices 2>/dev/null | awk 'NR>1 && $2=="device" {print $1}' | head -1)
      [ -n "$visible" ] \
        || die "no authorised phone. Plug it in, enable USB debugging, accept the prompt on its screen, then: bash scripts/host_adb.sh status"
      echo "--serial $visible"
      ;;
    emulator)
      echo "--emulator --headless --keep-emulator"
      ;;
    auto)
      if [ -n "$visible" ]; then
        echo "--serial $visible"
      else
        echo "--emulator --headless --keep-emulator"
      fi
      ;;
  esac
}

# --- main -------------------------------------------------------------------
preflight
[ "$MODE" = doctor ] && { printf '\n%sdoctor only — nothing was changed.%s\n' "$DIM" "$X"; exit 0; }

setup

step "Selecting a device"
DEVICE_ARGS=$(choose_device) || exit 1
info "run.py $DEVICE_ARGS"

# The bridge is only correct while the host server is up; setting it otherwise
# breaks every adb call in the container, because adb will not start a server
# on a Unix socket by itself.
COMPOSE_ENV=()
if [ -S "$ADB_DIR/adb.sock" ]; then
  export GREMLIN_ADB_DIR="$ADB_DIR"
  COMPOSE_ENV=(-e "ADB_SERVER_SOCKET=localfilesystem:/run/adb/adb.sock")
  info "using the host adb bridge at $ADB_DIR/adb.sock"
fi

case "$DEVICE_ARGS" in
  *--emulator*)
    printf '\n%s    A software-emulated first boot takes 20-30 minutes. It is kept\n' "$DIM"
    printf '    running afterwards, so later runs reuse it instead of rebooting.%s\n' "$X"
    ;;
esac

step "Running Gremlin"
# shellcheck disable=SC2086
docker compose run --rm "${COMPOSE_ENV[@]+"${COMPOSE_ENV[@]}"}" gremlin \
  python run.py $DEVICE_ARGS "${PASSTHRU[@]+"${PASSTHRU[@]}"}"
rc=$?

if [ $rc -eq 0 ]; then
  step "Done"
  info "reports:   runs/latest/reports/*.md"
  info "evidence:  runs/latest/screens/, runs/latest/trace.json"
  info "console:   docker compose run --rm --service-ports gremlin python -m gremlin.dashboard"
  info "           then open http://localhost:${CONSOLE_PORT:-8080}"
else
  step "Run failed (exit $rc)"
  info "model logs:  docker compose logs ${BACKEND:-ollama}"
  info "check again: bash scripts/gremlin.sh doctor"
fi
exit $rc
