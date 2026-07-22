#!/usr/bin/env bash
# Write a .env suited to a shared GPU workstation.
#
# The values that cannot be guessed from a template are the ones that depend on
# who and where you are: the uid/gid that keep bind-mounted files owned by you,
# and how much of a shared card it is polite to take. Everything else stays at
# the documented default.
#
#   bash scripts/lab_env.sh
#
# Refuses to clobber an existing .env — edit that by hand instead.

set -euo pipefail
cd "$(dirname "$0")/.."

[ -e .env ] || cp .env.example .env

# Add a key only if it is not already set, so an existing .env is topped up
# rather than either clobbered or — the earlier bug — left missing the values
# the container cannot start correctly without.
ensure() {
  local key=$1 val=$2
  if grep -qE "^\s*${key}=" .env; then
    printf '   %-16s already set, kept\n' "$key"
  else
    printf '%s=%s\n' "$key" "$val" >> .env
    printf '   %-16s added: %s\n' "$key" "$val"
  fi
}

# How much of the GPU to claim. On a machine where another service may want the
# card, taking all of it is the antisocial default; 0.60 of a 32 GB card is
# ~19.5 GB, which runs the 8B with room for context and leaves the rest free.
frac=0.60
# nvidia-smi prints its failure message on stdout on some builds, so the reply
# is only trusted when it is actually a number — otherwise its complaint would
# be read as a VRAM size, and as a running process.
total=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>/dev/null | head -1 | grep -xE '[0-9]+' || true)
others=$(nvidia-smi --query-compute-apps=pid --format=csv,noheader 2>/dev/null | grep -cxE '[0-9]+' || true)
if [ "${others:-0}" -gt 0 ]; then
  frac=0.35
  echo "NOTE: another process is on the GPU — taking a smaller share ($frac)."
fi

# Prefer whatever the running Ollama actually serves, so LOCAL_MODEL cannot
# drift from the tag that was pulled — a mismatch is a 404 at the first step.
served=$(curl -s --max-time 3 "localhost:${OLLAMA_PORT:-11435}/api/tags" 2>/dev/null \
         | grep -o '"name":"[^"]*"' | head -1 | cut -d'"' -f4 || true)
[ -n "$served" ] && echo "Ollama is serving: $served"

echo "Checking .env:"
ensure LLM_PROVIDER local
ensure LOCAL_BASE_URL "http://ollama:11434/v1"
ensure LOCAL_MODEL "${served:-qwen3-vl:32b}"
# Without these the container runs as uid 1000 while the bind-mounted repo is
# owned by you, and every write into /workspace fails with permission denied.
ensure UID "$(id -u)"
ensure GID "$(id -g)"
ensure VLLM_GPU_FRAC "$frac"
# The emulator reaches /dev/kvm by group, and that group's id is host-specific.
ensure KVM_GID "$(stat -c %g /dev/kvm 2>/dev/null || echo 104)"

echo
echo "Active settings:"
grep -vE '^\s*#|^\s*$' .env | sed 's/^/   /'
echo
[ -n "$total" ] && echo "GPU has ${total} MiB total; a vLLM run may use up to ~$(awk "BEGIN{printf \"%d\", $total*$frac}") MiB."
cat <<'EOF'

Next:
  docker compose build gremlin     # if UID or GID changed just now
  docker compose up -d ollama
EOF
