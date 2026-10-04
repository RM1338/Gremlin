#!/usr/bin/env bash
# Run the model-vs-no-model benchmark over every built app in bench/apps.tsv.
#
#   bash scripts/bench_eval.sh [actions] [repeats]     # defaults: 50 actions, 3 runs
#
# Needs Gremlin's headless emulator up (python run.py --emulator --keep-emulator,
# or the console) and the local model served by Ollama. The vision arm is locked
# to LLM_PROVIDER=local with the hosted keys blanked, so a local outage ends the
# run instead of silently falling back to Gemini or Groq and mixing backends.
#
# The package and launch activity come from each APK, not the project: debug
# builds and flavors change the package (migraineLogTest, authpass ...debug).
set -euo pipefail
cd "$(dirname "$0")/.."

ACTIONS=${1:-50}
REPEATS=${2:-3}
SERIAL=${GREMLIN_SERIAL:-emulator-5554}
BENCH=${GREMLIN_PROJECTS_ROOT:-$HOME/Projects}/bench
AAPT=$(ls -d "${ANDROID_HOME:-$HOME/Android/Sdk}"/build-tools/*/ | tail -1)aapt
MODEL=${LOCAL_MODEL:-qwen3-vl:4b-instruct}

grep -v '^#' bench/apps.tsv | cut -f1,4 | while IFS=$'\t' read -r app subdir; do
  [ -n "$app" ] || continue
  proj="$BENCH/$app/${subdir#.}"
  apk=$(find "$proj" -path '*flutter-apk*' -name '*debug.apk' 2>/dev/null | head -1)
  if [ -z "$apk" ]; then echo "== $app: no APK, skipped (run scripts/bench_build.py)"; continue; fi
  pkg=$("$AAPT" dump badging "$apk" | grep -oP "^package: name='\K[^']+")
  act=$("$AAPT" dump badging "$apk" | grep -oP "^launchable-activity: name='\K[^']+")
  adb -s "$SERIAL" install -r "$apk" >/dev/null
  echo "== $app ($pkg)  $(date +%T)"
  GREMLIN_APP_ROOT="$proj" LLM_PROVIDER=local LOCAL_BASE_URL=http://127.0.0.1:11434/v1 \
  LOCAL_MODEL="$MODEL" GEMINI_API_KEY= GROQ_API_KEY= \
    python -u -m gremlin.eval --package "$pkg" --activity "$pkg/$act" --serial "$SERIAL" \
      --actions "$ACTIONS" --repeats "$REPEATS" --coverage-only --out "runs/eval/real/$app" \
    | sed -n '/^arm /,/^wrote/p'
done
