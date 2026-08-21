# Gremlin

**Project Proposal**

> Fields marked «FILL» need your personal/team details — I've left them blank rather than guess.

| | | | |
|---|---|---|---|
| **TITLE OF THE PROJECT** | Gremlin — An Autonomous UI-Testing Agent with Log-Grounded Bug Detection and Replay-Verified Autofix for Cross-Platform Mobile Applications | | |
| **Team Name** | «FILL» | | |
| *Proposal Version:* | 1.0 | *Date:* | 18 July 2026 |
| *Team Leader Name:* | Ronel Abraham Mathew | *Reg. No.:* | «FILL» |
| *Year & Department:* | «FILL» | *Gender:* | «FILL» |
| *KMail ID:* | «FILL» | *Phone:* | «FILL» |
| *Project Guide(s):* | «FILL» | *Dept.:* | «FILL» |
| *Project Category:* | ☑ Research ☑ Academic | | |
| *Timelines:* | 18 Jul 2026 – 14 Nov 2026 (17 weeks) | | |
| *Repo:* | https://github.com/RM1338/Gremlin (public) | | |

---

## 1. EXECUTIVE SUMMARY

Mobile UI testing is expensive because it is written by hand. A team must author and then perpetually maintain an automated test for every screen, and those tests break whenever the UI changes. The result, in practice, is that most defects reaching users are not logic errors but *visible* failures — layout overflows, uncaught exceptions, render crashes — on screens no one wrote a test for.

The recent industry response is to point a large language model at a screenshot and ask "does this look broken?" This fails for a structural reason: the question has no checkable answer, so the model hallucinates defects and testers stop trusting the tool.

**Gremlin inverts the division of labour.** It exploits the fact that mobile UI frameworks *confess their own failures to the system log*: a Flutter layout that does not fit prints `A RenderFlex overflowed by 42 pixels`; a React Native error surfaces as a `JavascriptException`. Detection therefore requires no judgment at all — it is an exact string match on `adb logcat`, and it is ground truth. The language model is used only for the part it is genuinely good at and that has no correctness requirement: *deciding where to tap next*.

> **The model decides where to go. The log decides what is broken.**

A working prototype exists and has been demonstrated end-to-end on a physical Android device. It explores an app unattended, files a reproducible bug report for every failure, and — opt-in — patches the defect and **replays the exact tap sequence that caused it** to prove the fix holds. Because a patch is graded by re-execution rather than by opinion, "verified" means something falsifiable.

This proposal covers three extensions: **(i)** generalising the engine beyond Flutter to React Native via a platform abstraction; **(ii)** migrating the vision policy from a rate-limited third-party API to a **locally hosted Qwen3-VL-32B**, which is required for reproducible benchmarking and for testing proprietary source code that cannot be transmitted off-site; and **(iii)** building a public benchmark that measures the agent against Android's own Monkey and against Google's Firebase Robo Test.

**Success is measured as:** zero hallucinated bug reports (every finding carries its log line), ≥2× the distinct screens reached versus the Monkey baseline at equal action budget, and ≥60% of layout-class defects yielding a patch that clears all three verification gates.

---

## 2. PROJECT GOAL

This project aims to **make mobile UI defect detection and repair autonomous and trustworthy, by grounding detection in the framework's own runtime log rather than in a language model's judgment.**

By the end of the project, we will deliver:

1. A **functional open-source tool** (MIT, already public) that explores Flutter *and* React Native Android apps unattended and files reproducible bug reports.
2. A **replay-verified autofix pipeline** in which every proposed patch is graded by re-executing the failing trace against three gates.
3. **GremlinBench** — a public, reproducible benchmark of deliberately defective apps plus an open-source app corpus, with results against Monkey and Firebase Robo Test baselines.
4. A **research paper** submitted to a software-engineering venue (ICSE/FSE/ASE tool or short track).

---

## 3. INTRODUCTION

### 3.1 Introduction

Automated mobile testing has three established families, each with a structural limitation.

**Scripted automation** (Appium, Espresso, Maestro) executes exactly what a human wrote. Coverage is therefore bounded by author effort, and the scripts are brittle: a renamed widget breaks the test, not the app. Industry surveys consistently identify test maintenance, not test authoring, as the dominant cost.

**Random/fuzz exploration** (Android Monkey, Firebase Test Lab's Robo Test) needs no authoring and does find crashes. But it is blind. The Monkey taps uniformly at random and cannot form intent, so it revisits the same reachable surface and rarely penetrates multi-step flows. Google documents that Robo Test "finds crashes in surface-level interactions but misses bugs in deeper flows — it can't log in, complete a checkout, or navigate a multi-step flow" [1][2].

**LLM-as-judge visual testing** (the 2024–2026 wave: Applitools Autonomous, testRigor, KaneAI) uses a model to decide whether a screen is correct. This is where the field is currently investing, and it is where the epistemics break. Asking a model "is this screen broken?" produces an unfalsifiable answer; false positives are indistinguishable from true ones without a human, which reintroduces exactly the manual cost the tool was meant to remove.

Gremlin's motivation is the observation that **the third family is solving the wrong half of the problem with the wrong tool**. Detection does not need intelligence — the framework already announces its failures in `logcat`, in fixed strings, with source file and line attached in a debug build. What actually needs intelligence is *navigation*: reaching the screen where the confession happens. That is a task with no ground-truth requirement, where a model's mistake costs one wasted tap rather than one false bug report.

This split — an **exact oracle** paired with a **learned policy** — is the project's core thesis, and it is what makes the output trustworthy enough to act on automatically.

### 3.2 Problem Statement

> Mobile teams ship visible UI defects — layout overflows, uncaught exceptions, render crashes — because hand-written UI tests cover only the screens someone thought to test, random crawlers are too blind to reach the rest, and AI visual-testing tools that ask a model to judge correctness produce unverifiable findings that cannot be trusted or acted on automatically.
>
> **There is no tool that autonomously reaches deep application states, detects failures with ground-truth certainty rather than model opinion, and proves a proposed fix by re-executing the exact interaction that caused the defect.**

---

## 4. CURRENT STATE OF THE ART SOLUTIONS

### National (India)

| Existing Solution | How it works | Strengths | Weakness |
|---|---|---|---|
| **BrowserStack App Automate** (Mumbai/SF) [3] | Cloud farm of real devices; runs *your* Appium/Espresso scripts at scale, plus App Percy for visual diffs | Very large real-device matrix; mature CI integration; strong reliability | Executes only tests you already wrote — zero autonomous discovery. Visual diffing flags *any* pixel change, so it needs a human to triage intended redesigns from real bugs |
| **TestMu AI (formerly LambdaTest) — KaneAI** (Noida/SF) [4][5] | Agentic platform; tester describes a test in natural language, agent generates and self-heals the automation script across web and native mobile | Removes scripting skill barrier; self-healing cuts maintenance; now supports native Android/iOS on real devices | Still *intent-driven* — a human must state what to test, so undiscovered screens stay untested. Correctness is model-judged, so findings need human confirmation. Closed SaaS; source and screenshots leave the org |
| **Testsigma** (Bengaluru) [6] | Cloud, low-code; plain-English test steps compiled to executable tests for web/mobile/API, with AI self-healing locators | Accessible to non-programmers; self-healing reduces the brittleness cost; open-source core available | Authoring-bound like the above — no exploration. Self-healing fixes *tests*, never the *application* defect. No automated repair of app source |

### International

| Existing Solution | How it works | Strengths | Weakness |
|---|---|---|---|
| **Google Firebase Test Lab — Robo Test** [1][2] | Automatically crawls the app's UI graph on cloud devices with no script, capturing screenshots, video and crash logs | Genuinely zero-authoring; free tier; the closest existing analogue to this project | Crawl is heuristic, not reasoned — Google documents it misses deep/multi-step flows and cannot pass login or CAPTCHA. Detects crashes only (no layout-class defects). **Stops at detection — proposes no fix.** Degrades badly on non-native UI toolkits |
| **Meta Sapienz / Assured LLM-based repair** [7][8] | Search-based (multi-objective evolutionary) automated Android test generation deployed at Meta scale; later work pairs LLM-generated code changes with automated verification before any human sees them | Proven at industrial scale; the "verify the LLM's output automatically" principle is directly aligned with this project's gates | Internal to Meta and not available to other organisations. Sapienz targets crash discovery; the repair work is not mobile-UI specific. Enormous compute requirement |
| **Applitools Autonomous / testRigor** [9][10] | Visual AI compares rendered screens against a learned baseline; testRigor adds plain-English tests with AI element location and self-healing | Excellent at genuine visual-regression detection; very low maintenance; mature tooling | Requires a **known-good baseline**, so a defect present from the first run is learned as correct. Judgment-based verdicts need human triage. No autonomous exploration and no source-level repair |

**Gap this project addresses.** Across all six: those that explore do not reason (Robo Test, Monkey); those that reason require a human to state intent (KaneAI, Testsigma, Applitools); those that judge visually cannot prove their verdict; and **none of them repair the application source and then prove the repair by re-executing the failing interaction.** Gremlin occupies that empty quadrant: autonomous exploration + ground-truth detection + replay-verified repair.

---

## 5. PROPOSED SOLUTION

### 5.1 Objectives

**Objective 1 — Cross-platform generalisation.** Factor every toolkit-specific assumption (failure signal strings, source-location grammar, build command, source layout) into a single declarative `Platform` record, and prove the abstraction by adding **React Native** support such that the entire detection, exploration, reporting and repair pipeline works unchanged on a second UI toolkit.

**Objective 2 — Local model migration and reproducible benchmarking.** Replace the rate-limited third-party vision API with a **locally hosted Qwen3-VL-32B** on dedicated GPU hardware, then construct **GremlinBench** — a defect-seeded fixture suite plus a corpus of real open-source Android apps — and publish a controlled comparison against the Android Monkey and Firebase Robo Test.

**Objective 3 — Trustworthy automated repair.** Raise the verified-fix rate on layout- and exception-class defects by strengthening the anti-cheat guard and the three-gate verification, and quantify how often the pipeline correctly *rejects* a plausible-looking but incorrect patch — the property that makes autonomous repair safe to enable.

### 5.2 Methodology

**The core loop.** Gremlin drives a real device over `adb` through exactly four verbs — tap, type, back, scroll — so that any recorded sequence reproduces by construction:

```
Observe ──▶ Decide ──▶ Act ──▶ Check ──┐
screenshot  vision +   tap/type  read   │
    +       coverage   /back/    the    │
 a11y tree  memory     scroll    log    │
   ▲                                    │
   └────────── clean ───────────────────┘
        failure signal ─▶ bug report (screenshot + log line + full trace)
```

**1. Observe.** Capture a screenshot *and* dump the accessibility tree via `uiautomator`, yielding real tappable elements with labels and centre coordinates. Grounding taps in actual elements rather than model-guessed pixel coordinates eliminates an entire class of near-miss failures; pure-vision pixel tapping remains as fallback when the tree is empty.

**2. Decide.** The vision model receives the screenshot, the labelled element list, and a **coverage memory** of which controls on this screen have already been tapped. Exploration is therefore *coverage-driven*, not random: the agent works through untapped controls and declares a screen exhausted rather than looping on one button. Screens are deduplicated by perceptual hash.

**3. Act.** Execute the chosen verb and append it to the trace.

**4. Check.** A background thread streams `logcat`, scoped to the app's PID so other processes cannot contaminate results. After every action the oracle drains only the lines produced *since the last action*, so a failure is attributed to the action that caused it. Matching is exact regular-expression matching against a fixed signal table; the model is never consulted. Findings are deduplicated by `(signal kind, source location)`.

**Handling silent frameworks.** Modern Flutter (Impeller) does not reliably forward framework errors to `logcat`. An app under test may therefore opt in to a ~40-line **probe** that installs the standard framework error hooks and re-emits each error as one greppable line plus its source location. It is the same hook Sentry/Crashlytics install, adds only a print, and swallows nothing. An equivalent probe will be written for React Native's `ErrorUtils` global handler.

**The three output tiers.** Detection always runs; escalation is the developer's choice.

- **Tier 0 — Report.** Markdown per bug: screenshot, matched log line with context, source `file:line`, reproduction steps. No model involved, nothing to trust.
- **Tier 1 — Portable prompt.** The same report rendered as a self-contained prompt with the relevant source inlined, to paste into any assistant. Grants no write access. This is the default.
- **Tier 2 — Autofix (opt-in).** A pluggable coding agent edits source on a scratch branch; Gremlin guards the diff, rebuilds, replays the exact trace, and applies three gates.

**Verification — why a fix is not a fix until it is replayed.** A repair agent's naive reward is "make the log line disappear," which is *not* the same as fixing the bug. Wrapping an overflowing row in a scroll view silences the signal; wrapping the build method in try/catch hides the exception; deleting the widget silences everything. These cheats are *easier* to find than the real fix, so they must be excluded structurally:

- **Static guard (pre-replay).** Rejects patches that add try/catch, wrap content in a scroll view as the entire change, are pure deletions, or exceed a size budget.
- **Gate 1 — Signal gone.** Cold-start, replay the exact trace, confirm the target signal is absent.
- **Gate 2 — Screen still looks like itself.** Perceptual-hash distance between pre- and post-fix screenshots must be small-to-moderate, and the screen must not be blank — this is what catches "deleted the widget."
- **Gate 3 — Nothing new broke.** Re-explore; no signal absent from the baseline may appear.

A patch clearing all three is left **on its branch** for a human to read. A patch failing any gate is reverted and the original report survives. Gremlin never pushes or merges.

**Migration to local inference (Objective 2).** The vision backend is already selected by a single `LLM_PROVIDER` switch behind a stable interface, so migration is additive: serve `Qwen3-VL-32B-Instruct` via vLLM on the requested workstation, exposing the same OpenAI-compatible chat-completions API the current Groq backend consumes. Existing backends remain for machines without a GPU.

### 5.3 Success Metrics

| # | Metric | Target | How measured |
|---|---|---|---|
| M1 | **Report soundness** (no hallucinated bugs) | **100%** — every report traceable to a real log line | Automated audit: each report must cite a line present in the captured log |
| M2 | **Exploration coverage** vs Android Monkey | **≥ 2×** distinct screens at equal action budget | `gremlin.eval`, phash-deduplicated, ≥5 seeds |
| M3 | **Defect recall** on GremlinBench seeded defects | **≥ 90%** of seeded defects found within 80 actions | Known ground truth (defects are planted) |
| M4 | **Repair yield** on layout-class defects | **≥ 60%** produce a patch clearing all three gates | Automated Tier-2 batch run |
| M5 | **Repair safety** (correct rejection) | **≥ 95%** of deliberately-cheating patches rejected | Adversarial patch suite (scroll-wrap, try/catch, deletion) |
| M6 | **Step latency**, local Qwen3-VL-32B | **≤ 5 s** per observe→decide→act step, p50 | Instrumented timing on the workstation |
| M7 | **Cross-platform generality** | React Native support added by **one new `Platform` record**, no changes to explorer/replayer/gates | Diff review at Objective 1 completion |
| M8 | **Unattended run stability** | **≥ 60 min** continuous run without operator intervention | Long-run soak on the device farm |

### 5.4 Innovation / Novelty of the Approach

- **Innovative component 1 — The oracle/policy split (log-grounded detection).** Detection is an exact string match on the framework's own runtime confession; the language model is *never* asked whether a screen is broken. This inverts the prevailing "LLM-as-judge" design and is what makes the output falsifiable and therefore automatable. To our knowledge no shipping mobile tool draws this boundary explicitly.

- **Innovative component 2 — Replay-verified repair with adversarial gating.** Every bug report carries the exact tap trace that produced it, so a patch is graded with no human in the room: cold-start, replay, check. Crucially, the system treats *the repair agent as an adversary that will silence the symptom if allowed to*, and defends with a static cheat-guard plus three independent gates. Verification against symptom-silencing — not just "the error stopped" — is the novel contribution.

- **Innovative component 3 — Toolkit-agnostic failure abstraction.** A single declarative `Platform` record (signal table, source-location grammar, source layout, build command) is the only toolkit-specific knowledge in the system. Demonstrating that Flutter and React Native — architecturally very different renderers — are supported by the *same* engine establishes that log-grounded detection is a general principle rather than a Flutter trick.

- **Innovative component 4 — Coverage-driven, semantics-grounded exploration.** Taps are grounded in the real accessibility tree and guided by per-screen coverage memory, so exploration terminates on exhaustion instead of looping — the specific failure mode that limits random crawlers like Robo Test.

---

## 6. SYSTEM DESIGN / ARCHITECTURE

### Block diagram

```
                        ┌──────────────────────────────────────┐
                        │        React Console (frontend/)     │
                        │  Overview · Live · Trace · Bugs ·    │
                        │  Benchmark · Target picker           │
                        └───────────────┬──────────────────────┘
                                        │ REST + WebSocket
                        ┌───────────────▼──────────────────────┐
                        │      dashboard.py (FastAPI)          │
                        └───────────────┬──────────────────────┘
                                        │
   ┌────────────────────────────────────▼─────────────────────────────────┐
   │                          explorer.py — the loop                      │
   │                                                                      │
   │   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────────┐      │
   │   │grounding │──▶│ policy   │──▶│ device   │──▶│   oracle     │      │
   │   │ a11y tree│   │ + vision │   │ 4 verbs  │   │ logcat match │      │
   │   └──────────┘   └────┬─────┘   └────┬─────┘   └──────┬───────┘      │
   │                       │              │                │              │
   │              ┌────────▼────────┐     │         ┌──────▼───────┐      │
   │              │ screen_memory   │     │         │ platforms.py │      │
   │              │ phash coverage  │     │         │ signal table │      │
   │              └─────────────────┘     │         └──────┬───────┘      │
   └──────────────────────────────────────┼────────────────┼──────────────┘
                                          │                │
              ┌───────────────────────────▼──┐      ┌──────▼──────────┐
              │  ANDROID DEVICE (adb/USB)    │      │  reporter.py    │
              │  Flutter app │ React Native  │      │  Tier 0 + Tier 1│
              └──────────────────────────────┘      └──────┬──────────┘
                              ▲                            │
                              │                     ┌──────▼──────────┐
                              │                     │  fixer.py Tier 2│
                              │                     │  guard→rebuild→ │
                              └─── replayer.py ─────│  replay→3 gates │
                                  (deterministic)   └─────────────────┘

    Vision backend (pluggable):  Gemini │ Groq  ──▶  [PROPOSED] local Qwen3-VL-32B (vLLM)
    Fix backend  (pluggable):    prompt │ claude │ codex │ copilot │ command
```

### Stepwise process flow (input → output)

| Step | Module | Action |
|---|---|---|
| 1 | `targets.py` + `platforms.py` | **Input:** a project directory or installed package. Detect toolkit; derive `applicationId`, launcher activity, source root |
| 2 | `device.py` | Hold the screen awake; cold-start the app via `am start` |
| 3 | `oracle.py` | Clear `logcat`, resolve the app PID, begin the background stream scoped to that PID |
| 4 | `device.py` + `grounding.py` | Screenshot; `uiautomator dump` → labelled elements with centres |
| 5 | `policy.py` + vision backend | Downscale image; send screenshot + element list + coverage memory; receive JSON `{verb, target, reason}` |
| 6 | `device.py` | Execute the verb; append to trace |
| 7 | `oracle.py` | Drain new log lines; match against the platform signal table; extract `file:line` |
| 8 | `screen_memory.py` | Perceptual-hash the screen; update visited set and per-screen coverage |
| 9 | — | Loop to 4 until budget exhausted or all screens exhausted |
| 10 | `reporter.py` | **Output A:** Tier 0 markdown + Tier 1 portable prompt per deduplicated bug |
| 11 | `fixer.py` (opt-in) | Scratch branch → coding agent patch → static guard → rebuild → `replayer.py` → three gates |
| 12 | `dashboard.py` | **Output B:** live run state, trace viewer, bug list with remediation tier, benchmark comparison |

### Key APIs and integrations

| Interface | Role |
|---|---|
| `adb` (shell, logcat, exec-out screencap, uiautomator) | The single device interface — all four verbs and all observation |
| Vision inference — OpenAI-compatible `/v1/chat/completions` | Currently Groq (Llama-4-Scout) / Gemini. **Proposed:** local vLLM serving Qwen3-VL-32B on the same API shape, so the swap is configuration-only |
| Fix backend CLI contract | `claude -p` / `codex exec` / `copilot -p` / arbitrary `FIX_CMD` template |
| `flutter build apk` · `gradlew assembleRelease` | Per-platform rebuild for Tier-2 replay |
| FastAPI + WebSocket | Console backend, live run streaming |
| `git` (branch/diff/revert) | Tier-2 isolation — clean tree required, one branch per bug, never pushes |

---

## 7. DATA REQUIREMENTS

This project is **not dataset-trained** — it uses a pre-trained vision model at inference time only. "Data" here means the *evaluation corpus of applications* the agent is measured on, plus the model weights.

| Sl. No. | Dataset Name | Source / URL | License Type | Size | Remarks |
|---|---|---|---|---|---|
| 1 | **GremlinBench (Flutter)** | Self-authored; its own repository at `~/Projects/gremlin-bench-flutter` | MIT | ~10 apps, <50 MB source | Deliberately defect-seeded apps, one isolated planted defect per screen. Ground truth is known by construction, which is what makes recall (M3) measurable |
| 2 | **GremlinBench-RN (React Native)** | Self-authored (to be built, Objective 1) | MIT | ~10 apps | Mirror of the above for React Native; validates the platform abstraction |
| 3 | **F-Droid open-source app corpus** | https://f-droid.org | GPL/Apache/MIT (per app) | 30–50 apps, ~3 GB APK + source | Real third-party apps for external validity — defects here are *unknown*, so this measures discovery in the wild rather than recall against planted bugs |
| 4 | **Qwen3-VL-32B-Instruct weights** | https://huggingface.co/Qwen | Apache 2.0 | ~64 GB (FP16) / ~20 GB (Q4) | Model weights for local inference. Apache 2.0 permits unrestricted local and commercial use |
| 5 | **Adversarial patch suite** | Self-authored (Objective 3) | MIT | ~50 patches | Hand-written symptom-silencing patches (scroll-wrap, try/catch, deletion) used to measure repair-safety (M5) |
| 6 | **Run artefacts** | Generated locally at `runs/` | N/A (internal) | ~1–2 GB per 100 runs | Screenshots, traces, logs. **Never leaves the machine** — this is precisely why local inference is required |

**Collection strategy.** Corpora 1, 2 and 5 are authored by the team, so ground truth is exact. Corpus 3 is selected from F-Droid by filtering for Flutter/React Native apps that build from source with an unmodified toolchain, sampled across categories to avoid over-fitting to one UI style. No human-subject data, no personal data, and no user telemetry is collected at any point.

---

## 8. HARDWARE REQUIREMENTS

### Equipment Required

- **A GPU workstation capable of serving a 32-billion-parameter vision-language model locally**, which is the central hardware ask of this proposal (justified below).
- **Physical Android test devices** — the agent drives real hardware over USB; emulators do not reproduce the rendering path (Impeller/Vulkan), the timing, or the jank signals faithfully.
- A powered USB hub for sustained multi-device runs (continuous `adb` sessions on multiple phones exceed a laptop's port power budget).

### Why local inference is *required*, not merely preferable

The exploration policy issues **one vision-model call per action**, so a single 80-action run is ~80 calls, and the evaluation plan (8 metrics × ~50 apps × ≥5 seeds, repeated across development iterations) runs to the **order of 10⁵ inference calls**. Four independent constraints make a hosted API unworkable at that volume:

1. **Rate limits truncate experiments.** The current implementation already degrades a run to partial results when the free daily quota is exhausted — this is a documented behaviour of the tool today, not a hypothetical. A benchmark that silently ends early is not a benchmark.
2. **Reproducibility is impossible against a moving target.** Hosted models are updated and deprecated without notice, so a published measurement cannot be re-run months later and cannot be independently verified. A locally pinned Qwen3-VL-32B checkpoint makes every reported number reproducible — a hard requirement for the intended publication.
3. **Source-code confidentiality blocks real-world adoption.** Tier 1 and Tier 2 transmit *the application's own source code* to whichever model is configured. No industrial partner will permit proprietary source to leave the premises, so an API-only tool is permanently confined to toy examples. Local inference removes the blocker entirely and is the single change that makes the tool deployable inside a company.
4. **Recurring cost versus one-time capital.** At the projected call volume, commercial API pricing would consume a recurring budget indefinitely, whereas the workstation is a one-time asset that outlives this project and remains available to the department for subsequent work.

**Sizing.** Qwen3-VL-32B requires ≈64 GB VRAM at FP16, ≈32 GB at Q8, and ≈19–20 GB at Q4 [11][12]. A vision-language model additionally needs headroom for image tokens and KV cache beyond the raw weights. A **32 GB card is therefore the smallest that runs this model at Q8 with usable context**; a 24 GB card is restricted to Q4 with tight context management and measurable quality loss on fine UI detail — a real risk when the model must distinguish small on-screen controls.

### Hardware Components Required

| Sl. No. | Name of hardware component / consumable | Vendor / Source | Unit Price (₹) | Qty | Sub Total (₹) | Remarks |
|---|---|---|---|---|---|---|
| 1 | NVIDIA GeForce RTX 5090, 32 GB GDDR7 | MD Computers / PrimeABGB / EliteHubs | 4,30,000 | 1 | **4,30,000** | **Primary ask.** Smallest card running Qwen3-VL-32B at Q8. *Reduced-scope fallback: RTX 4090 24 GB ≈ ₹2,50,000, Q4 only* |
| 2 | AMD Ryzen 9 7950X (16-core) | MD Computers | 55,000 | 1 | 55,000 | Image pre/post-processing and parallel `adb` sessions are CPU-bound |
| 3 | Motherboard, X670E chipset (PCIe 5.0) | MD Computers | 30,000 | 1 | 30,000 | PCIe 5.0 ×16 required for full GPU bandwidth |
| 4 | DDR5 RAM, 64 GB (2 × 32 GB) | MD Computers | 20,000 | 1 | 20,000 | Model loading + concurrent emulator/device sessions |
| 5 | NVMe SSD, 2 TB Gen4 | MD Computers | 15,000 | 1 | 15,000 | Model weights (~64 GB), APK corpus, and run artefacts. **The current development machine is at 100% disk capacity, which has already blocked builds** |
| 6 | PSU, 1200 W 80+ Platinum | MD Computers | 20,000 | 1 | 20,000 | RTX 5090 transient draw requires substantial headroom |
| 7 | Cabinet + airflow cooling | MD Computers | 15,000 | 1 | 15,000 | Sustained inference is a thermally continuous load |
| 8 | Android test devices (mid-range, Android 13+) | Local retail | 15,000 | 2 | 30,000 | Device farm for parallel runs and cross-device validation. One device already owned |
| 9 | Powered USB 3.0 hub (10-port) + cables | Local retail | 3,000 | 1 | 3,000 | Sustained multi-device `adb` |
| | | | | **TOTAL** | **₹6,18,000** | Reduced-scope with RTX 4090: **₹4,38,000** |

> **Note:** unit prices are indicative retail figures gathered in July 2026 [13] and must be confirmed by formal vendor quotation before procurement. GST-invoiced purchase is recommended to preserve India warranty coverage.

---

## 9. SOFTWARE REQUIREMENTS

**All software in this stack is free and open-source. Recurring software cost is ₹0.**

| Layer | Components | License |
|---|---|---|
| **Core engine** | Python 3.13; Pillow, ImageHash (perceptual hashing); `httpx` | PSF / MIT / BSD |
| **Device control** | Android Platform Tools (`adb`), `uiautomator` | Apache 2.0 |
| **Inference (proposed)** | vLLM serving Qwen3-VL-32B-Instruct; CUDA 12.x; PyTorch | Apache 2.0 / NVIDIA EULA / BSD |
| **Inference (current)** | Groq API (Llama-4-Scout), Google Gemini API — free tiers | Vendor free tier |
| **Repair backends** | Claude Code, OpenAI Codex CLI, GitHub Copilot CLI — all optional and pluggable | Vendor; `prompt` default needs none |
| **Console** | FastAPI, Uvicorn, WebSockets; React 19 + Vite | MIT / BSD |
| **App toolchains** | Flutter SDK; React Native 0.86, Node 24, Gradle, JDK 21 | BSD / MIT / Apache 2.0 |
| **Dev/CI** | Git, GitHub Actions, pytest | GPL / MIT |

**Expected monthly run-cost.**

| Item | Current | After local migration |
|---|---|---|
| Vision inference | ₹0 (free tier, **quota-truncated runs**) | ₹0 |
| Cloud compute | ₹0 (all local) | ₹0 |
| Electricity (workstation, ~600 W sustained, ~6 h/day) | — | ≈ ₹900/month |
| **Total recurring** | **₹0** | **≈ ₹900/month** |

The migration's value is not cost reduction — it is the removal of the quota ceiling, the achievement of reproducibility, and the confidentiality property that makes industrial deployment possible.

---

## 10. WORK PLAN & MILESTONES

| Objectives | Tasks | Days | From | To | Measurable outcomes / milestones |
|---|---|---|---|---|---|
| **Obj. 1** — Cross-platform generalisation | Factor toolkit assumptions into a declarative `Platform` record; author the React Native signal table and source-location grammar; write the RN `ErrorUtils` probe; generalise source-location fields across reporter/models/console; build **GremlinBench-RN** fixture with seeded defects; validate on a physical device | 28 | 18 Jul 2026 | 14 Aug 2026 | **M-1.1** Same engine detects defects in both Flutter and React Native apps. **M-1.2** RN support adds one `Platform` record with zero changes to explorer/replayer/gates (**M7**). **M-1.3** GremlinBench-RN published in-repo |
| **Obj. 2a** — Workstation commissioning | Procure and assemble; install CUDA/vLLM; serve Qwen3-VL-32B-Instruct on an OpenAI-compatible endpoint; add the local provider behind the existing `LLM_PROVIDER` switch; A/B against Groq for decision quality and latency | 21 | 15 Aug 2026 | 4 Sep 2026 | **M-2.1** Local model serving; provider swap is configuration-only. **M-2.2** p50 step latency ≤ 5 s (**M6**). **M-2.3** No regression in exploration coverage versus the hosted model |
| **Obj. 2b** — Benchmark construction | Curate 30–50 F-Droid apps that build from source; automate the harness across Gremlin / Monkey / Firebase Robo Test; run ≥5 seeds per app per explorer; build the report-soundness audit | 28 | 5 Sep 2026 | 2 Oct 2026 | **M-2.4** ≥2× distinct screens vs Monkey (**M2**). **M-2.5** ≥90% recall on seeded defects (**M3**). **M-2.6** 100% report soundness (**M1**). **M-2.7** 60-minute unattended soak (**M8**) |
| **Obj. 3** — Trustworthy repair | Build the adversarial patch suite; strengthen the static cheat-guard and gate thresholds; batch Tier-2 across the whole benchmark; measure yield *and* correct-rejection rate; ablate each gate to quantify its individual contribution | 28 | 3 Oct 2026 | 30 Oct 2026 | **M-3.1** ≥60% repair yield on layout-class defects (**M4**). **M-3.2** ≥95% of cheating patches rejected (**M5**). **M-3.3** Per-gate ablation table |
| **Wrap-up** | Write and submit the paper; documentation, reproduction scripts, tagged release | 15 | 31 Oct 2026 | 14 Nov 2026 | **M-4.1** Paper submitted. **M-4.2** Tagged v1.0 release with one-command reproduction of every published number |

---

## 11. OUTCOME(S)

| | |
|---|---|
| ☑ | **Product** — a working open-source tool, already public at github.com/RM1338/Gremlin (MIT) |
| ☑ | **Publication** — targeting an ICSE/FSE/ASE tool or short track; the oracle/policy split and adversarially-gated replay verification are the contributions |
| ☑ | **Other:** *Public benchmark* — GremlinBench, a reproducible defect-seeded suite for autonomous mobile-testing research |
| ☐ | Startup — plausible longer-term (the confidentiality property is a genuine commercial differentiator) but explicitly out of scope here |
| ☐ | Patent — not pursued; open publication and an open-source release are preferred for research impact |

---

## 12. IMPACT

**End application.** Gremlin drops into any Android team's workflow at whichever level of trust they are willing to extend. At Tier 0 it is a zero-risk bug finder that requires no model to be trusted at all. At Tier 1 it produces a paste-ready prompt for whatever assistant the team already uses. At Tier 2 it delivers a pre-verified patch on a branch for human review. The escalation is deliberate: adoption does not require an organisation to trust an autonomous agent on day one.

**Who benefits, how much, how soon.**

- **Small teams and individual developers — immediately.** These are the teams with no dedicated QA function, for whom writing UI tests is the first thing dropped under deadline. The tool needs *zero* test-authoring effort: point it at an app and it explores. This is the largest beneficiary group in India's app ecosystem, where a very large share of published apps are built by teams of under five people.
- **Indian product companies — within the project timeline.** The local-inference capability means source code never leaves the premises, which is the specific objection that rules out every SaaS competitor in Section 4 for firms handling regulated or client-confidential code.
- **The research community — on publication.** GremlinBench provides a reproducible, ground-truth-seeded benchmark. Current autonomous-testing research is difficult to compare across papers because each uses a private app set; a public suite with known planted defects addresses that directly.

**Quantified expected improvement.** For a team that writes no UI tests today, coverage moves from zero automated screens to autonomous exploration of the reachable UI graph. On seeded benchmarks we target ≥90% detection of visible-failure defects with **zero false reports by construction** — every finding cites a framework-emitted log line. Where the current alternative (Firebase Robo Test) stops at crash detection on surface screens, this system additionally catches layout-class defects, reaches deeper states, and proposes a verified repair.

**Accessibility.** The exploration engine is built on the **Android accessibility tree**. An app that exposes a well-formed semantics tree is explored more effectively, so the tool creates a direct, self-interested incentive for developers to label their controls properly — the same labels screen-reader users depend on. Poor accessibility markup degrades Gremlin's own results, which surfaces an accessibility deficiency as a testing deficiency. Additionally, by removing the requirement to *write code* to get test coverage, the tool lowers the barrier for developers without automation-engineering backgrounds.

**SDG alignment.** *SDG 9 (Industry, Innovation and Infrastructure)* — open, freely available quality-engineering infrastructure for small software firms that cannot fund QA teams. *SDG 4 (Quality Education)* — the tool and benchmark are teaching artefacts for software-testing and applied-AI coursework, and the repository is public and documented. *SDG 8 (Decent Work and Economic Growth)* — automating the most repetitive part of QA shifts human effort toward exploratory and design-level testing.

---

## 13. STRETCH GOALS

1. **iOS support via a substitute oracle.** The current design is Android-bound because it depends on `adb` and a chatty log. A stretch goal is to establish whether the same oracle/policy split survives on iOS using the unified logging system and XCUITest's accessibility APIs — this would test whether "log-grounded detection" is a genuine general principle or an Android artefact.

2. **Semantic assertions from a screen contract.** The tool currently verifies the app does not *visibly fail*; it does not verify the app is *correct*. A stretch goal is a lightweight developer-authored per-screen contract (e.g. "after login, a username is displayed") checked against the accessibility tree — extending the ground-truth principle to behaviour without reintroducing model judgment.

3. **Regression-suite synthesis.** Every verified trace is already a deterministic reproduction. Emitting them as Appium or Maestro tests would let a run *leave behind* a permanent regression suite, converting one-off exploration into durable coverage.

4. **CI integration.** A GitHub Action that explores each pull request's build and comments findings inline, positioning the tool at the point where defects are cheapest to fix.

---

## 14. TEAM ROLES

| Team Member | Role | Contributions | Relevant Skills |
|---|---|---|---|
| Ronel Abraham Mathew | Project Lead / Architect | Core engine (oracle, explorer, grounding, replayer, gates); platform abstraction; local-model migration; benchmark and paper | Python, Android/`adb` internals, Flutter, React Native, LLM inference and serving, React |
| «FILL» | «FILL» | «FILL» | «FILL» |
| «FILL» | «FILL» | «FILL» | «FILL» |

> If submitting solo, delete the empty rows. If you have teammates, natural splits are: (a) React Native platform support + RN fixture suite, (b) benchmark curation and the Monkey/Robo-Test comparison harness, (c) console/frontend and results visualisation.

---

## 15. BUDGET

**The total cost of the project is ₹6,18,000** (six lakh eighteen thousand rupees only).

| Category | Amount (₹) |
|---|---|
| GPU workstation (Items 1–7, Section 8) | 5,85,000 |
| Android test devices and peripherals (Items 8–9) | 33,000 |
| Software licences | 0 — entire stack is free/open-source |
| Cloud/API recurring | 0 — all inference is local |
| **TOTAL** | **₹6,18,000** |

**Reduced-scope alternative: ₹4,38,000**, substituting an RTX 4090 24 GB for the RTX 5090. This restricts the model to Q4 quantisation with constrained context, which is expected to reduce accuracy on fine on-screen detail and therefore weakens metric M6 and possibly M2; it is viable but not preferred.

The workstation is a **one-time capital asset** that remains with the department after project completion and is directly reusable for any subsequent local-LLM research.

---

## 16. REFERENCES

[1] Google, "Run a Robo test (Android) — Firebase Test Lab." https://firebase.google.com/docs/test-lab/android/robo-ux-test

[2] Google, "Test Lab troubleshooting & FAQ." https://firebase.google.com/docs/test-lab/troubleshooting

[3] BrowserStack, "App Automate — automated mobile app testing." https://www.browserstack.com/app-automate

[4] TestMu AI (formerly LambdaTest), "KaneAI — AI Testing Agent & Test Automation." https://www.testmuai.com/kane-ai/

[5] PR Newswire, "LambdaTest Introduces General Availability to KaneAI to Democratize AI-Native Test Automation." https://www.prnewswire.com/ae/news-releases/lambdatest-introduces-general-availability-to-kaneai-to-democratize-ai-native-test-automation-302556542.html

[6] Testsigma, "AI-powered test automation platform." https://testsigma.com

[7] K. Mao, M. Harman, Y. Jia, "Sapienz: Multi-objective Automated Testing for Android Applications," *ISSTA 2016*. https://doi.org/10.1145/2931037.2931054

[8] N. Alshahwan et al., "Automated Unit Test Improvement using Large Language Models at Meta," *FSE 2024*. https://arxiv.org/abs/2402.09171

[9] Applitools, "Applitools Autonomous — AI-powered visual testing." https://applitools.com/platform/autonomous/

[10] testRigor, "AI-Based Test Automation." https://testrigor.com

[11] APXML, "Qwen3-32B: Specifications and GPU VRAM Requirements." https://apxml.com/models/qwen3-32b

[12] Qwen Team, "Qwen3-VL model card." https://huggingface.co/Qwen

[13] GetPC, "RTX 5090 32GB Price in India (July 2026)." https://getpc.co.in/parts/gpu/rtx-5090-32gb

[14] F-Droid, "Free and Open Source Android App Repository." https://f-droid.org

[15] R. A. Mathew, "Gremlin — autonomous UI-testing agent," 2026. https://github.com/RM1338/Gremlin
