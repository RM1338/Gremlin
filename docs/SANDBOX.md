# Running the app in a sandbox instead of on a device

A design note on replacing "connect your phone" / "boot an emulator" with a
containerised Android instance — what it is under the hood, what it buys this
project specifically, where it breaks, and what it would mean for distributing
Gremlin to other people.

Written 19 Aug 2026. Kernel facts in here were checked on the development
laptop; the build timing is measured, not estimated.

---

## 1. What Gremlin actually demands of a "device"

Everything else in this document follows from this list. Read back from
`gremlin/device.py`, `gremlin/grounding.py` and `gremlin/oracle.py`, a run needs:

| Primitive | Used for |
|---|---|
| an `adb` transport | everything |
| `screencap` | Observe |
| `input tap` / `text` / `swipe` / `keyevent` | Act |
| `uiautomator dump` | grounding — real elements with labels and centres |
| **`logcat --pid`** | **the oracle — this *is* the detection** |
| `pm`, `am`, `dumpsys`, `pidof` | targeting and lifecycle |

The logcat requirement is the one that constrains the design. Gremlin's whole
claim is that detection is an exact match against the framework's own runtime
confession, so **any substitute for a device must produce a real logcat stream
from a real Android framework.**

That rules out the tempting cheap options. A desktop Flutter build, a web
preview, a headless widget-test harness, or a screenshot-diffing service cannot
host Gremlin, because none of them produce the signal the oracle reads. The
sandbox must be a genuine Android userspace. Only three mechanisms provide one.

---

## 2. The three mechanisms

### 2.1 Full-system virtualisation — SDK emulator, Cuttlefish, Genymotion

QEMU (or crosvm) boots a *guest kernel* plus the Android userspace on emulated
virtio hardware. With KVM, guest CPU instructions execute natively on the host
CPU; without it QEMU falls back to TCG dynamic binary translation, which is the
10–20× slowdown that made cold boots take 20–30 minutes on the lab machine where
`/dev/kvm` was denied.

Cost: a full system image (~10 GB), a guest kernel, emulated devices. Highest
fidelity, highest price.

### 2.2 Containerised Android — redroid, Waydroid

The Android userspace is *just Linux processes*: `init`, `zygote`,
`system_server`, `SurfaceFlinger`, `logd`. There is no reason they cannot run in
ordinary namespaces and cgroups on the **host kernel** — no guest kernel, no
QEMU, no instruction translation, near-native CPU speed.

The catch is that Android's framework depends on kernel features mainline does
not enable by default — chiefly **binder**, the IPC driver that carries every
framework call (`system_server` ↔ apps, all of it), plus historically ashmem
(modern Android uses memfd instead).

**Verified on the development laptop** (kernel 7.0.0-28-generic):

```
CONFIG_ANDROID_BINDER_IPC=m
CONFIG_ANDROID_BINDERFS=m
```

Built as modules and not currently loaded — there is no `/dev/binder` yet. A
single `sudo modprobe binder_linux` enables it.

**Note what that implies: this needs root once, so it would never have solved
the university lab's problem.** It is available now only because development
moved to a machine we own. Do not propose it as a lab workaround.

Critically, **every one of Gremlin's six primitives survives containerisation**:

- `logcat` reads from **logd, a userspace daemon over a socket** — not a kernel
  device. It works unchanged, so the oracle's entire mechanism is preserved.
- `uiautomator dump`, `input tap` and `screencap` travel over binder to the
  accessibility, input and SurfaceFlinger services, all of which are present.
- adb is exposed over TCP (5555), so `Device(serial="localhost:5555")` needs
  **zero code changes** — `Config.serial` already exists and is already plumbed.

### 2.3 Cloud device farms — Genymotion Cloud, AWS Device Farm, BrowserStack

Someone else's hardware, adb over the network, billed per hour. Works with
Gremlin unchanged where raw adb is exposed; several vendors only offer Appium,
which is not a fit.

**Firebase Test Lab is a batch service** — upload an APK, collect results. It
does not provide a persistent adb session for a live per-step loop. This matters
for `PROPOSAL.md`: the planned Robo Test comparison must be a *results-on-the-
same-APKs* comparison, **not** a same-harness one. State that explicitly in the
paper before a reviewer raises it.

---

## 3. Why a container fits this project specifically

Beyond convenience, it improves the science in four ways.

**Disk.** ~2–3 GB image against 12–15 GB for the emulator plus a system image.
On the current laptop (~18 GB free) that is the difference between viable and
not.

**Reproducibility.** A container starts from a byte-identical image every run. A
phone accumulates state — notifications, app data, OS updates, battery saver
engaging mid-run. An AVD accumulates snapshot drift. "Fresh instance per run" is
a *methodological* claim that can be made in the paper, not merely a
convenience, and it is what lets a third party reproduce a benchmark number.

**Parallelism.** N containers are N independent adb serials. M2 wants ≥5 seeds;
those become parallel rather than serial. On 15 GB RAM, expect 3–4 concurrent.

**Parameterised screen geometry — the strongest fit.** redroid takes
`androidboot.redroid_width` / `_height` / `_dpi` as boot parameters. Gremlin's
dominant defect class is **RenderFlex overflow, which is inherently
screen-size-dependent.** A container makes it cheap to sweep form factors
systematically and report defect recall *per geometry* — "this layout overflows
below 360 dp width". Neither a single phone nor a handful of hand-made AVDs
gives that. It is a real experimental capability and a genuine differentiator
against Robo Test.

---

## 4. Where it breaks

Honest list. Test these early rather than discovering them during a benchmark.

**ARM-only APKs will not run.** redroid x86_64 executes x86 native code. Our own
fixtures can target x86_64 fine, but real-world APKs from F-Droid or Play are
frequently arm64-only, and the translation layers (libhoudini, ndk-translation)
are proprietary and licensing-murky.

This is **the biggest threat to the "corpus of real open-source Android apps"
plan in Objective 2.** Mitigation is real, though: the corpus is open-source by
definition, so those apps can be built from source targeting x86_64. Verify this
in the first hour of corpus work, not the last week.

**Software rendering changes what gets logged.** SwiftShader by default, so
Flutter may fall back from Impeller to Skia. This cuts both ways and interacts
directly with G5 in `KNOWN_ISSUES.md`: if Skia restores the framework's own
logcat error forwarding, the probe requirement partly evaporates inside
containers — a nice result. But it also means **signals observed in a container
may not match signals observed on a phone**, which is a validity question to be
measured rather than assumed.

**Jank becomes meaningless.** `Skipped N frames` inside a container sharing a
laptop CPU with the vision model measures host load, not the app. The `HANG`
signal class should be excluded from containerised runs or reported separately;
otherwise it contaminates M3 with noise that has nothing to do with the app
under test.

**Ecological validity.** No sensors, no vendor skin, no thermal behaviour, no
real GPU driver quirks. A reviewer will ask. The defensible answer is the hybrid
in §10.

**Linux only.** binder is unavailable on macOS and Windows — Docker Desktop runs
a LinuxKit VM whose kernel does not ship the Android modules, and users cannot
easily rebuild it. A bundled sandbox is a **Linux-only feature**; Mac and Windows
users still need a phone or the emulator. Advertise it that way.

---

## 5. What this means for distributing Gremlin

Three models, and the answers differ sharply between them.

### Model A — publish the tool (what Gremlin is today)

User installs it, brings their own phone or emulator. We host nothing. No
infrastructure, no security surface, no running cost. "Deploying to the public"
means PyPI and GitHub.

### Model B — publish the tool *with* a bundled sandbox

One compose command yields Gremlin plus redroid on the user's own machine. No
phone required. We still host nothing. This is a packaging improvement and the
natural next step. Linux only, per §4.

### Model C — hosted SaaS

Users upload an APK, we run the exploration, we return the reports. **Every hard
problem lives here, and one of them is structural rather than an engineering
task.**

redroid is cheap precisely because it runs Android's userspace on the *host*
kernel. That requires binder and generally `--privileged` or close to it, and it
**shares one kernel with every other container on the host.** Now add the
defining property of a public service: *the APK is arbitrary code supplied by a
stranger.*

Privileged containers, plus untrusted code, plus a shared kernel, plus
multi-tenancy is a bad combination. A container escape compromises the host and
therefore every other customer's app and reports. This is not hypothetical
caution — it is exactly why commercial device farms use physically isolated real
devices or full hardware virtualisation rather than containers.

So Model C's isolation boundary must be **a VM per tenant** (Cuttlefish or the
SDK emulator inside a per-tenant VM, using nested virtualisation), not a
container. That is roughly 5–10× the cost per concurrent session and undoes most
of what made the sandbox attractive.

> **redroid is excellent for our benchmark and for Model B. It is the wrong tool
> for multi-tenant hosting.**

---

## 6. Concurrency: can one person test several apps at once?

At the Android layer, trivially yes — N containers, N adb serials, and
`Config.serial` already exists, so `device.py` needs no changes.

**Gremlin itself is the blocker, not the sandbox.** In `gremlin/dashboard.py`,
`_cfg`, `_run_started`, `_target_name` and `_emulator` are **module-level
globals**, with an explicit `if _run_started: return` guard. The console supports
exactly one run, ever. Worse, `Config.run_dir` defaults to `runs/latest` for
everything, so two concurrent runs would overwrite each other's screenshots,
`trace.json` and reports.

Concurrency therefore needs a real refactor:

- run IDs, with per-run `Config` and per-run `run_dir`
- a job registry replacing the module globals
- per-run WebSocket topics instead of one global broadcast set

Not enormous, but it properly touches the dashboard rather than adding a flag.

**The real ceiling is the GPU, not the containers.** Each exploration step is one
VLM inference. Four apps in parallel means four inference streams against one
card; they serialise, and every run gets slower. Containers are cheap, inference
is not.

This is the first strong argument for vLLM over Ollama in this project — not
single-run latency, but **continuous batching**. vLLM interleaves concurrent
requests efficiently; Ollama handles concurrency far more crudely. If concurrent
runs ever matter, that is the reason to go back to vLLM, and it is a better
justification than raw speed.

---

## 7. Model roles

Gremlin already has two, though the code does not name them as such:

| Role | Where | Frequency | Needs |
|---|---|---|---|
| **Policy** (vision) | `vision.py` → gemini / groq / local | 40–80× per run, latency-critical | small, fast |
| **Repair** (code) | `fix_backend.py` → claude / codex / … | 1× per bug, agentic | tool use, strong |

A third **reasoning** role would slot in cleanly as a dispatcher module
mirroring `vision.py`, called rarely — when the explorer is stuck, to set a
high-level goal ("reach checkout"), or to triage and cluster bugs at end of run.
Once or twice per run, so a slower, larger model is affordable there in a way it
never is on the per-step path.

**But do not build it yet.** Per G4 in `KNOWN_ISSUES.md`, it has never been
established that the *vision* model is load-bearing at all —
`Explorer._choose_and_execute` overrides the model's choice whenever it does not
target an untapped control. Adding a second model before measuring the first
buys complexity against an unknown baseline. Run the ablation first; if
coverage-only ≈ full Gremlin, a reasoning layer is solving a problem we do not
have.

---

## 8. Taps and swipes

Identical — that is the point. `adb -s localhost:5555 shell input tap 540 1200`
reaches the container's `adbd`, which hands it to InputManager, which injects it
into the framework over binder. `device.py` cannot tell the difference.

Two consequences do bite:

**Traces become geometry-bound.** Actions are absolute coordinates and redroid's
resolution is a boot parameter, so a trace recorded at 1080×1920 will not replay
correctly against a container booted at 720×1280. Since replay is what makes
Tier 2 trustworthy, **record the screen geometry in `trace.json` and refuse to
replay a trace against a mismatched device.** This extends G6 and becomes
essential the moment form-factor sweeping starts.

**Fixed sleeps get fragile.** `device.py` hardcodes 0.6 s after a tap, 0.4 s
after typing, 0.7 s settle. Generous on an idle container, potentially too short
on a host running several sessions. Anything concurrent will want a
poll-until-stable check instead.

---

## 9. Time and cost

**Per run, from measured components.** A step costs roughly screenshot 0.5–1 s +
`uiautomator dump` 1–2 s (the slow one) + inference 2–5 s + hardcoded sleeps
~1.5 s ≈ **6–10 s**. An 80-step run is **8–13 minutes**.

**Tier 2 is much heavier.** The GremlinBench fixture's Gradle build was measured
at **151.6 s** on this laptop. One fix attempt is therefore agent edit
(0.5–5 min) + rebuild ~2.5 min + install ~20 s + replay (trace length × ~1.3 s)
+ gate-3 exploration ~2 min → **6–10 minutes per bug**. For M4 across a corpus,
the rebuild dominates, which is why preserving Gradle cache state matters more
than it appears.

**Build effort**, as shape rather than false precision:

| Work | Size |
|---|---|
| redroid compose service + docs | small — `--serial` plumbing already exists |
| geometry in traces + replay guard (G6) | small, needed anyway |
| exclude jank signals in containers | trivial, but required for M3 hygiene |
| multi-run refactor of the dashboard | the real one; only if concurrency is a goal |
| Model C per-tenant VM infrastructure | a different project — weeks, plus running cost |

---

## 10. Recommendation

**Aim at Model B. Treat the sandbox as a benchmark instrument first and a
distribution convenience second.**

It solves the disk constraint, makes GremlinBench reproducible by strangers,
unlocks the form-factor sweep, and costs no infrastructure. Say plainly in the
README that it is Linux-only and that macOS/Windows users bring a device.

**Skip Model C.** It is a business rather than a feature, and its multi-tenancy
security requirements would force us off the very architecture that makes the
sandbox attractive in the first place.

For the paper, use a **hybrid**: containers as the primary harness (reproducible,
parallel, geometry-swept) and the physical phone as a validation arm on a
subset, reporting the agreement rate between them. That is a stronger
methodology than either alone, and it converts a hardware limitation into a
defensible design choice.

### Implementation order

1. `sudo modprobe binder_linux`, confirm `/dev/binderfs`, pull a redroid image.
2. `adb connect localhost:5555`, run `tests/smoke_test.py` against it —
   this validates screencap, grounding and the four verbs in one shot.
3. Confirm the oracle sees signals: run the Flutter fixture and check whether
   the probe is still required under software rendering (§4).
4. Record geometry in `trace.json` and guard replay (G6).
5. Exclude the jank class for containerised runs.
6. Only then consider the multi-run refactor, and only if concurrency is a goal.
