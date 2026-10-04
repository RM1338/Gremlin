# Status — 4 Oct 2026

Where the work stands, what was left half-finished, and what remains. Defect
and method holes live in `docs/KNOWN_ISSUES.md` (G1…G16); this file is the
work plan around them.

## Done

**Running on a laptop without binder** (Arch / Omarchy kernels have none, so
the redroid sandbox cannot start):

- With no device attached, `run.py` boots an AVD when the sandbox cannot run.
- The emulator is always headless — the console cannot open a window and
  `run.py` needs `--show-emulator` — because a window is an input path into
  the device under test. A headless boot will not adopt a windowed emulator.
- `-gpu host` by default: every software renderer the emulator ships
  segfaulted in its RenderThread a few steps into the Flutter bench fixture.
- A crashed emulator's stale AVD lock is cleared; a device that dies mid-run
  ends the run with its reports instead of a traceback.
- The target app is built and installed on Gremlin-owned devices (sandbox or
  headless emulator), never on a phone.
- Sandbox setup is not offered on a kernel with no binder at all.

**Exploration**

- G16 fixed: web screens are keyed by route plus visible `<h1>`, so a
  single-page app's views count (1 → 6 on the test fixture).
- Coverage taps "Back" last. It used to take it first, leave the page and
  never return, then claim full coverage (2 → 3 of 3 planted defects).

**Local model** — `qwen3-vl:4b-instruct` on Ollama, RTX 3050 6 GB, ~1.3 s per
decision, 3/3 defects on the bench fixture. The thinking variant
(`qwen3-vl:4b`) took 76 s a step and is unusable; `qwen2.5vl:3b` returned
malformed actions. G4 measured on the fixture: model = no model there, which
is G15 (the fixture is too small to need decisions), not a verdict.

**Benchmark apps (G15)** — `bench/apps.tsv` lists ten offline Flutter apps from
F-Droid at the commits F-Droid built; `scripts/bench_build.py` builds them the
way their recipes do. Nine build with a clean tree. Chrono is parked.

## Half-finished

- **The nine-app benchmark run.** `scripts/bench_eval.sh` (50 actions, 3 runs
  per arm, local model vs no model, app data cleared before every run) was
  started and stopped when the session ended, after four runs of the first
  app. Blood Pressure Monitor, distinct screens per run: no model 12, 20;
  local model 11, 13 (one model run missing). Too few to conclude anything —
  but the model is not ahead there, which is the question G4 asks.
- **Chrono** is parked: D8 in its AGP 7.4.2 crashes with a
  NullPointerException dexing `lifecycle-livedata` 2.8.5. Needs a JDK / AGP
  trial, or a replacement app.
- **Gradle heap.** `~/.gradle/gradle.properties` set
  `org.gradle.jvmargs=-Xmx4g` for the benchmark builds; it was removed in the
  cleanup below. `bench_build.py` documents it as a prerequisite.

## Removed after this work (reinstall to resume)

To give the disk back, everything installed only for the benchmark and the
local model was deleted: Ollama and its models, the benchmark app sources and
APKs (`~/Projects/bench`), the Flutter versions they pinned (3.16.9, 3.27.3,
3.32.0, 3.35.7, 3.38.8, 3.41.9, 3.44.8, 3.47.2), JDK 21, the Gradle
distributions only they used, CMake 3.10.2, and the user-level Gradle heap
setting. Gremlin's own toolchain (Android SDK, the `gremlin` AVD, Flutter
3.47.6, JDK 17, `.venv`) and the bench fixture were kept. `.env` is back on
Gemini.

To resume the benchmark:

```
# local model (~2.2 GB binary + 3.3 GB model)
#   Ollama from github.com/ollama/ollama/releases into ~/.local/share/ollama-bin
ollama serve &  ollama pull qwen3-vl:4b-instruct
# in .env: LLM_PROVIDER=local, LOCAL_BASE_URL=http://localhost:11434/v1,
#          LOCAL_MODEL=qwen3-vl:4b-instruct

# Gradle heap for the larger apps, in ~/.gradle/gradle.properties:
#   org.gradle.jvmargs=-Xmx4g -XX:MaxMetaspaceSize=1g
sdkmanager "cmake;3.10.2.4988404"            # AuthPass
python scripts/bench_build.py                # ~20-25 GB of SDKs and builds
python run.py --emulator --keep-emulator ... # or boot the AVD headless
bash scripts/bench_eval.sh 50 3              # ~5-6 h
```

Check free disk first: the builds peaked at 134 GB of a 136 GB disk before
intermediates were cleaned per app.

## Remaining

In the order they unblock each other:

1. **Finish the nine-app benchmark** and record it under G4 / G15. It answers
   whether the model earns its cost on apps with real navigation.
2. **Grow the set to 30–50 apps** (proposal Obj. 2b). Needs a disk plan:
   group apps by Flutter version, and budget ~2 GB per pinned SDK.
3. **G2 — make Gate 3 deterministic** (replay other bugs' traces instead of a
   random 15-step probe). Starts Obj. 3, due 30 Oct.
4. **G3** — strengthen the static guard; build the adversarial patch suite
   (M5: ≥95% of cheating patches rejected).
5. **G12** — finish replacing gate 2's magic thresholds.
6. **G6, G7** — replay determinism on real apps; validate the perceptual-hash
   screen threshold that M2 is stated in.
7. **G5** — document the probe requirement in the paper.
8. **Native Android platform record** — most F-Droid apps are Kotlin/Java;
   one `Platform` entry would open them to the benchmark (M7).
9. **Fine-tuning a local model** — only if step 1 shows the model matters:
   log decisions with outcomes from real-app runs, LoRA-tune a 3–4B VLM
   off-laptop, serve it locally.
10. **KNOWN_ISSUES note** — on a machine without a GPU the emulator falls back
    to SwiftShader, which crashes on the bench fixture.
