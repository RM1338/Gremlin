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

if [ -e .env ]; then
  echo ".env already exists — leaving it alone. Current settings:"
  grep -vE '^\s*#|^\s*$' .env | sed 's/^/   /'
  exit 0
fi

cp .env.example .env

# How much of the GPU to claim. On a machine where another service may want the
# card, taking all of it is the antisocial default; 0.60 of a 32 GB card is
# ~19.5 GB, which runs the 8B with room for context and leaves the rest free.
frac=0.60
total=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>/dev/null | head -1 || echo "")
others=$(nvidia-smi --query-compute-apps=pid --format=csv,noheader 2>/dev/null | grep -c . || true)
if [ "${others:-0}" -gt 0 ]; then
  frac=0.35
  echo "NOTE: another process is on the GPU — taking a smaller share ($frac)."
fi

{
  echo ""
  echo "# ---- Written by scripts/lab_env.sh ----"
  echo "LLM_PROVIDER=local"
  # Keeps files the container writes into the repo owned by you, not root.
  printf 'UID=%s\n' "$(id -u)"
  printf 'GID=%s\n' "$(id -g)"
  echo "VLLM_GPU_FRAC=$frac"
} >> .env

echo "Wrote .env:"
grep -vE '^\s*#|^\s*$' .env | sed 's/^/   /'
echo
[ -n "$total" ] && echo "GPU has ${total} MiB total; this run may use up to ~$(awk "BEGIN{printf \"%d\", $total*$frac}") MiB."
echo "Next:  docker compose -f docker/compose.yml up -d vllm"
