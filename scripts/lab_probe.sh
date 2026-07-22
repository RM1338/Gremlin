#!/usr/bin/env bash
# Read-only survey of a lab workstation before Gremlin is containerised.
#
# Installs nothing, writes nothing outside /tmp, needs no sudo. It answers the
# four questions that decide whether the GPU compose stack can run at all:
# can this user reach the Docker daemon, can a container see the GPU, is there
# room for the model weights, and is /dev/kvm available for the emulator.
#
#   bash scripts/lab_probe.sh
#
# The one heavyweight step (a ~250 MB CUDA base image, needed to prove GPU
# passthrough actually works rather than merely looking configured) is skipped
# unless the nvidia runtime is already registered.

set -uo pipefail

hr() { printf '\n\033[1m== %s ==\033[0m\n' "$1"; }
ok() { printf '  \033[32mPASS\033[0m %s\n' "$1"; }
no() { printf '  \033[31mFAIL\033[0m %s\n' "$1"; }
info() { printf '       %s\n' "$1"; }

hr "Identity"
info "user   : $(id -un) (uid=$(id -u) gid=$(id -g))"
info "host   : $(hostname)"
info "groups : $(id -nG)"
if id -nG | tr ' ' '\n' | grep -qx docker; then
  ok "in the 'docker' group — daemon socket reachable without sudo"
else
  info "not in the 'docker' group; if docker still works this is rootless mode"
fi

hr "Docker"
if ! command -v docker >/dev/null 2>&1; then
  no "docker not on PATH — nothing below will work"
  exit 1
fi
info "client : $(docker version --format '{{.Client.Version}}' 2>/dev/null || echo '?')"
if server=$(docker version --format '{{.Server.Version}}' 2>/dev/null); then
  ok "daemon reachable, server $server"
else
  no "daemon NOT reachable as this user:"
  docker version 2>&1 | sed 's/^/       /' | head -5
  exit 1
fi
info "rootless   : $(docker info --format '{{.SecurityOptions}}' 2>/dev/null | grep -q rootless && echo yes || echo 'no (normal daemon)')"
info "storage    : $(docker info --format '{{.Driver}}' 2>/dev/null)"
info "docker root: $(docker info --format '{{.DockerRootDir}}' 2>/dev/null)"
info "runtimes   : $(docker info --format '{{range $k,$v := .Runtimes}}{{$k}} {{end}}' 2>/dev/null)"

# Compose is what actually brings the two-service stack up.
if docker compose version >/dev/null 2>&1; then
  ok "compose v2 present: $(docker compose version --short 2>/dev/null)"
else
  no "'docker compose' missing — the stack is defined as a compose file"
fi

hr "Who else is using this machine"
# A shared workstation is the normal case, and the two ways to disturb someone
# else's work are taking a port they hold or taking VRAM they are mid-way
# through using. Neither is caused by starting containers; both are caused by
# starting *these* containers without looking first.
running=$(docker ps -q 2>/dev/null | wc -l)
if [ "$running" -gt 0 ]; then
  info "$running container(s) already running — leave them alone:"
  docker ps --format '  {{.Names}}  {{.Image}}  ({{.Status}})' 2>/dev/null | sed 's/^/     /'
  info ""
  info "Nothing in docker/compose.yml touches them: compose only ever acts on"
  info "its own project ('gremlin'), and 'down' is scoped to that project too."
else
  ok "no other containers running"
fi
# Our compose binds these on the loopback interface. A clash is a startup error
# rather than damage, but it is better seen now.
for p in 8000 8080 5173; do
  if command -v ss >/dev/null 2>&1 && ss -ltn 2>/dev/null | grep -q ":$p "; then
    no "port $p is already in use — change it in .env before starting"
  fi
done

hr "GPU on the host"
if command -v nvidia-smi >/dev/null 2>&1; then
  nvidia-smi --query-gpu=name,memory.total,driver_version,compute_cap \
             --format=csv,noheader 2>/dev/null | sed 's/^/       /'
  # The number that decides whether starting vLLM is antisocial: if someone
  # else's job already holds VRAM, claiming 90% of the card will disrupt it.
  used=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits 2>/dev/null | head -1)
  procs=$(nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader 2>/dev/null)
  if [ -n "$procs" ]; then
    no "the GPU is ALREADY IN USE by someone else (${used} MiB held):"
    echo "$procs" | sed 's/^/       /'
    info ""
    info "Do not start vllm at the default settings — it claims 90% of VRAM"
    info "and would disrupt that work. Either wait, or set a small share in"
    info ".env, e.g. VLLM_GPU_FRAC=0.35 with VLLM_MODEL=Qwen/Qwen3-VL-8B-Instruct,"
    info "and confirm with whoever owns the running job first."
  else
    ok "no other process is using the GPU (${used:-0} MiB held) — safe to claim it"
  fi
  drv=$(nvidia-smi --query-gpu=driver_version --format=csv,noheader 2>/dev/null | head -1 | cut -d. -f1)
  # Blackwell (RTX 50xx, sm_120) needs a 570+ driver and a CUDA 12.8+ runtime.
  if [ -n "${drv:-}" ] && [ "$drv" -ge 570 ] 2>/dev/null; then
    ok "driver $drv is new enough for Blackwell / RTX 5090"
  else
    no "driver ${drv:-unknown} may predate Blackwell support (want >= 570)"
  fi
else
  no "nvidia-smi not found on the host — no usable GPU from here"
fi

hr "GPU inside a container"
# This is the step that most often fails: the driver is fine, but
# nvidia-container-toolkit was never installed, so containers cannot see the GPU.
if docker info --format '{{range $k,$v := .Runtimes}}{{$k}} {{end}}' 2>/dev/null | grep -q nvidia; then
  ok "nvidia runtime is registered with the daemon"
  info "verifying real passthrough (pulls a ~250 MB CUDA base image)..."
  if docker run --rm --gpus all nvidia/cuda:12.8.0-base-ubuntu24.04 \
       nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/tmp/gremlin_gpu_err; then
    ok "a container CAN see the GPU — vLLM will work"
  else
    no "passthrough failed despite the runtime being present:"
    sed 's/^/       /' /tmp/gremlin_gpu_err | head -8
  fi
else
  no "no nvidia runtime — containers cannot reach the GPU"
  info "nvidia-container-toolkit is missing. Installing it needs root, so this"
  info "is the one thing you must ask your professor / lab admin to run."
fi

hr "Disk"
# Model weights are the dominant cost: a 32B checkpoint is tens of GB, and it
# lands in the HF cache volume under the Docker root, not in your home dir.
root=$(docker info --format '{{.DockerRootDir}}' 2>/dev/null || echo /var/lib/docker)
df -h "$root" "$HOME" 2>/dev/null | sed 's/^/       /'
avail=$(df -BG --output=avail "$root" 2>/dev/null | tail -1 | tr -dc '0-9')
if [ -n "${avail:-}" ] && [ "$avail" -ge 120 ] 2>/dev/null; then
  ok "${avail} GB free under the Docker root — room for 32B weights"
elif [ -n "${avail:-}" ] && [ "$avail" -ge 40 ] 2>/dev/null; then
  info "${avail} GB free — enough for an 8B model, tight for a quantised 32B"
else
  no "only ${avail:-?} GB free under $root — too little for local weights"
fi

hr "Android emulator prerequisites"
if [ -e /dev/kvm ]; then
  ok "/dev/kvm exists"
  if [ -r /dev/kvm ] && [ -w /dev/kvm ]; then
    ok "and this user can read+write it — emulator can run in a container"
  else
    no "but this user cannot access it (needs the 'kvm' group; that needs root)"
  fi
else
  no "/dev/kvm missing — no hardware acceleration for the emulator"
fi
if command -v adb >/dev/null 2>&1; then
  info "host adb: $(adb version 2>/dev/null | head -1)"
  adb devices 2>/dev/null | sed 's/^/       /'
else
  info "no host adb (fine — the container ships its own)"
fi

hr "Network"
for url in https://registry-1.docker.io/v2/ https://huggingface.co https://api.anthropic.com; do
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 8 "$url" 2>/dev/null)
  # Any HTTP answer proves reachability; 401/403 from an auth-gated root is fine.
  if [ "$code" != "000" ]; then ok "$url reachable (HTTP $code)"; else no "$url unreachable — proxy?"; fi
done
[ -n "${HTTPS_PROXY:-${https_proxy:-}}" ] && info "proxy set: ${HTTPS_PROXY:-$https_proxy}"

printf '\n\033[1mDone.\033[0m Send this whole output back to Claude.\n'
