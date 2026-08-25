# Known issues and open risks

A working ledger of defects, methodological holes, and evaluation gaps found by
reading the codebase against `PROPOSAL.md`. Each entry says what is wrong, which
success metric it threatens, and what the fix looks like.

Severity is about the *project*, not the code: an issue that quietly invalidates
a benchmark number ranks above one that crashes loudly.

Status key: `open` · `fixed` · `accepted` (known, deliberately not fixed)

---

## G1 — The oracle goes deaf after a mid-run relaunch

**Severity:** high · **Status:** fixed · **Threatens:** M3, M8, every run's recall

`Oracle.start()` (`gremlin/oracle.py:92`) resolves the app's PID once via
`_resolve_pid()` and pins the log stream with `logcat --pid <pid>`. But
`Explorer._ensure_on_app()` (`gremlin/explorer.py:219`) may `relaunch()` the app
mid-run when a tap strands the agent in a share sheet, a permission dialog or a
file picker. `relaunch` is force-stop + start, so the app comes back with a
**new PID**, and the oracle keeps filtering on the dead one.

From that moment the oracle sees nothing at all, for the rest of the run.

The failure is silent, which is the dangerous part: the run completes normally,
reports whatever it found before the relaunch, and an app with defects after
that point looks clean. Longer runs are likelier to hit it, so this bites
hardest exactly where M8 (≥60 min unattended) is measured.

**A second, worse trigger.** Our own relaunch is the obvious cause, but not the
common one. **Any crash the oracle successfully detects kills the app process**,
after which Android may restart it under a new PID. For a tool whose entire job
is finding crashes, the stale pin is a *consequence of success* — the oracle
goes deaf immediately after its first real find, which is precisely when it
matters most. So the check cannot be limited to the relaunch path.

**Fixed 19 Aug 2026.** `Oracle` now records the PID it is pinned to.
`Oracle.restart()` respawns the stream and clears the buffered lines and cursor,
which belong to a process that no longer exists and would otherwise corrupt
`drain()`'s cursor arithmetic. `Oracle.ensure_attached()` re-resolves the PID and
restarts only when it has actually changed; it deliberately does **nothing** when
the app is momentarily down, because restarting then would resolve no PID and
silently drop the filter, letting every other app's noise into the run.

`Explorer._reattach_oracle()` calls it on **every step**, not only after a
relaunch, and drains the new stream once so restart noise is not attributed to
the next action. Cost is one `pidof` per step — a few percent of a step — and it
buys back every signal after the first crash.

Verified offline with a fake device across six cases: unchanged PID does
nothing; a downed app keeps the pin; a changed PID restarts the stream; an
unscoped stream is a no-op; restart clears buffer and cursor; and a signal
arriving after a process change is still detected.

---

## G2 — Gate 3 can pass by not looking

**Severity:** high · **Status:** open · **Threatens:** M4, M5, the safety claim

Gates 1 and 2 are deterministic: replay a fixed trace, compare a hash. Gate 3
(`gremlin/fixer.py`, the `probe_cfg` / `Explorer(probe_cfg)` block) instead runs
a fresh **stochastic** 15-step exploration and passes when no signal appears
that was absent from the baseline.

A short random re-exploration may simply never revisit the screens the patch
touched. "Nothing new broke" and "we did not go and look" produce an identical
pass. The gate that is supposed to catch collateral damage is the one gate that
cannot be relied on to have checked anything.

**The same root cause fails in the other direction, and that half is worse.**
Observed 21 Aug 2026, on the first real autofix attempt (sandbox, coverage
policy, `FIX_BACKEND=claude`). The agent's patch for `renderflex-overflow` was
correct and idiomatic — one line, `Container(width: 250, ...)` to
`Expanded(child: Container(...))` inside the `Row`:

```
gate signal-gone        pass — target signal absent on replay
gate screen-looks-same  pass — perceptual distance 16 (<= 32)
gate no-new-breakage    FAIL — patch introduced: dart-exception|lib/main.dart:127
```

`lib/main.dart:127` is **planted bug 2**, the crash-on-tap, which exists in the
unpatched app and has nothing to do with a `Row`. The baseline run had simply
never tapped that button, so it held only two keys; the probe tapped it and the
gate read a pre-existing defect as a regression. A correct fix was reverted.

The gate's premise is that the baseline enumerates the app's defects. It does
not — it enumerates *what one stochastic run happened to find*. Any probe that
explores more thoroughly than the baseline reads as breakage, so this is not a
rare coincidence: it is the expected outcome whenever the baseline run was
incomplete, which is most runs.

**Fix.** Make gate 3 deterministic like the others: replay the *other* bugs'
recorded traces from the same run — they already exist in `trace.json` — and
assert no new signal keys appear. Where a run has only one bug, fall back to
replaying the fixed trace with a longer settle, or keep the exploration but
report coverage alongside the verdict so a pass with low coverage is visibly
weak rather than silently equal to a strong one.

Determinism fixes both directions at once: a replayed trace cannot wander onto a
screen the baseline never reached, so it can neither miss real damage nor invent
it. If the stochastic probe is kept for any reason, the minimum honest version
is to re-probe the **base** build whenever the gate is about to fail and drop
any signal that reproduces there — a pre-existing defect is not breakage. That
costs a probe run only on the failure path.

---

## G3 — The static guard is a speed bump, not a guard

**Severity:** medium · **Status:** open · **Threatens:** M5

`guard_patch_diff()` (`gremlin/gates.py`) greps the diff text for `try {` and
`catch (`, flags `SingleChildScrollView`, and rejects pure deletions.

Three problems:

1. **Trivially evaded.** Reformatting defeats the regexes. A cheat written as
   `try\n{` passes.
2. **The scroll-view check is scoped away.** It only fires when
   `len(added) <= 3`, so padding a scroll-wrap cheat to four added lines walks
   straight through.
3. **False positives.** A legitimate fix that genuinely needs error handling is
   rejected as reward hacking.

**Fix.** Reframe rather than harden. The *gates* are the defence; the guard is
an optimisation that avoids paying for a rebuild on obvious cases. Say so in the
docstring, drop the claim that it prevents cheating, and let the adversarial
suite (G9) measure what actually gets through. Structural matching on the parsed
diff would beat regex if it is worth the effort, but the gates matter more.

---

## G4 — The vision model may not be load-bearing, and it has never been measured

**Severity:** high · **Status:** harness built, **measurement pending** · **Threatens:** M2, and the motivation for Objective 2

`Explorer._choose_and_execute()` honours the model's chosen action **only** when
it targets an as-yet-untapped control; otherwise it takes `untapped[0]` itself.
When a screen is exhausted the fallback ladder (type once, scroll once, back
out) is also hard-coded. So the model's real contribution is: the *ordering* of
untapped controls, the text typed into fields, and screen names.

If coverage bookkeeping plus accessibility-tree grounding is what actually beats
the Monkey, then M2 is won without the model — and Objective 2's case for a
locally hosted large checkpoint collapses, because nothing in the loop needs it.

This is not yet a known problem. It is an **unmeasured** one, which is worse.

**Fix.** Run the three-arm ablation before any further model work:

| Arm | Policy |
|---|---|
| A | `adb shell monkey` (existing baseline) |
| B | Coverage-only — no LLM: always `untapped[0]`, canned text |
| C | Full Gremlin (coverage + vision policy) |

Equal action budget, ≥5 seeds, distinct screens and distinct bugs. Needs no GPU
and runs on the laptop. Either outcome is publishable: B ≈ C is the more
interesting finding ("semantic grounding and coverage memory beat vision-guided
exploration") and is cheaper to defend; C > B is the evidence Objective 2 needs.

Arm B is a small `--policy` switch in the explorer, not a fork.

**Built 19 Aug 2026.** `Config.policy` selects `"vision"` (default, unchanged)
or `"coverage"`; `policy.decide_coverage_only()` returns a Decision that always
defers to the explorer's own coverage logic, so the arms differ only in who
orders the untapped controls and what text is typed. Grounding, coverage memory
and the stopping rule are held constant, which is what makes this an ablation of
the model rather than of the engine. Verified offline against a fake device: the
arm taps every control once, then types once, scrolls once, and backs out, with
`decide()` never called.

```bash
# single run, no model
python run.py --project ~/Projects/gremlin-bench-flutter --policy coverage

# the three-arm comparison
python -m gremlin.eval --project ~/Projects/gremlin-bench-flutter --actions 30 \
    --coverage-only --monkey
```

**The number still does not exist.** Running this needs a device, and until it
has been run over ≥5 seeds the question G4 asks remains open — the harness is
not the finding. Do not cite the model's contribution until this table exists.

---

## G5 — The probe requirement narrows the headline claim

**Severity:** medium · **Status:** open (document it) · **Threatens:** external validity

"The framework confesses its own failures to the log" is the thesis. Modern
Flutter under Impeller does not, so the app under test must compile in
`installGremlinProbe()`.

Consequence: for the layout and Dart-exception classes, Gremlin can only test
apps **whose source you control and have instrumented**. Native crashes
(`FATAL EXCEPTION`) are caught regardless, because Android logs those itself.
This directly limits the console's device-only target mode, which can explore
any installed third-party app but will mostly only catch native crashes on it.

**The sandbox does not dissolve this** (measured 21 Aug 2026, `docs/SANDBOX.md`
§4). The hope was that a container's software rendering would push Flutter back
to Skia and restore the framework's own logcat forwarding. It does not:
SwiftShader exposes Vulkan, Flutter selects Impeller exactly as on a phone, and
both bugs in the validation run arrived as `GREMLIN_BUG` probe lines. The probe
is required in containers too.

**Fix.** Not a code fix — a framing one. State it as an explicit scope condition
early in the paper rather than as a footnote, and report per-signal-class recall
split by instrumented vs uninstrumented apps so the limit is visible in the
numbers. A reviewer will find this immediately; better to own it.

---

## G6 — Replay assumes the app under test is deterministic

**Severity:** medium · **Status:** open · **Threatens:** M4, M5 on real apps

`replayer._execute()` replays taps as **absolute coordinates**. Any app whose
layout shifts between runs — async-loaded lists, ads, timestamps, animations,
A/B content — can present a different screen at the same coordinates, so the
replay silently exercises the wrong control.

The fixtures are static, so this never bites today. It will the moment
GremlinBench includes real open-source apps, and it will surface as flaky gate
results rather than as an obvious error.

**Fix.** Record the screen phash (and the target element's label) with each
action, and during replay assert the observed screen still matches within
threshold. On divergence, abort the replay and report `replay-diverged` rather
than grading a patch against the wrong screen. Cheap, and it converts a silent
wrong answer into an honest "cannot verify".

---

## G7 — The screen-dedup threshold is unvalidated, and M2 depends on it entirely

**Severity:** medium · **Status:** open · **Threatens:** M2

`Config.phash_same_threshold = 6` decides when two screenshots are "the same
screen". Distinct screens reached is the **headline comparison metric** against
the Monkey, so this single constant sets the number the project is judged on.

Too low and scrolling within one screen inflates the count; too high and
genuinely different screens collapse. It has never been calibrated, and both
arms of the comparison are measured with it, so an error does not cancel out —
Gremlin scrolls deliberately for coverage, the Monkey does not.

**Fix.** Calibrate against hand-labelled ground truth on the fixtures: capture a
labelled set of screen pairs (same/different) and pick the threshold that
maximises agreement. Report a sensitivity analysis in the paper — M2 at
thresholds 4, 6, 8, 10 — so the result is visibly not an artefact of one
constant.

---

## G8 — `config.py` ignored `.env`

**Severity:** medium · **Status:** fixed

`config.py` read `GREMLIN_PROJECTS_ROOT` and `GREMLIN_APP_ROOT` at import time
but never called `load_dotenv()` — only the model backends did. Under compose
these arrived as real environment variables so the bug was invisible; running
natively, `.env` was silently ignored and target discovery fell back to
`~/Projects`, finding nothing.

Fixed by calling `load_dotenv()` at the top of `config.py` before the module
reads the environment. It still uses `setdefault`, so real environment variables
keep winning and the container path is unchanged.

---

## G9 — The evaluation infrastructure does not exist yet

**Severity:** high · **Status:** open · **Threatens:** M2, M3, M4, M5, M8

The engine is built; the science is not. Missing, in rough dependency order:

- **A target flag for the benchmark** (see G10) — nothing else can run without it.
- **The ablation harness** (G4): a no-LLM policy arm.
- **An adversarial patch suite** for M5: a corpus of deliberately-cheating
  patches (scroll-wrap, try/catch, widget deletion, constraint loosening,
  warning suppression) with known-correct verdicts, so "≥95% rejected" is
  measured rather than asserted.
- **A defect corpus beyond the two fixtures** for M3: seeded defects with known
  ground truth, ideally across several form factors.
- ~~**A multi-seed runner** producing mean and variance, not single runs.~~
  **Built 25 Aug 2026.** `gremlin.eval --repeats N` (default 5) runs every arm
  over consecutive seeds and reports mean ± sample sd, min/max/median, and the
  individual samples. A seed that dies (a quota, a flaky device) is recorded as
  a failed sample and **excluded** from the mean rather than counted as a zero,
  so `n` is what was actually measured. It also emits a **per-defect detection
  rate** — "found in 4 of 5 seeds" — which is the number a mean bug count cannot
  express: a defect found once in five and one found five times in five
  contribute the same +1 to an average and are not the same claim.
  `eval.json` gained schema 2, carrying the device, geometry, Android version,
  vision model and app commit alongside the results, because a benchmark without
  its environment is a rumour. **Still owed: actually running it.** No number on
  the Benchmark page is measured yet — the page reads demo data, flagged as such.
- **Firebase Robo Test comparison**: note this is a batch cloud service and does
  not expose a live adb loop, so it is a *results* comparison on the same APKs,
  not a like-for-like harness.

Every remaining success metric except M1 depends on machinery that has not been
written. M1 is satisfied by construction.

---

## G10 — `gremlin.eval` cannot be pointed at a fixture

**Severity:** high · **Status:** fixed · **Threatens:** M2 (blocked it outright)

`eval.main()` (`gremlin/eval.py:91`) builds a bare `Config()` and accepts only
`--actions`, `--monkey` and `--seed`. There is no `--project` or `--package`, so
the benchmark always runs against the hardcoded default package
`com.scribe.scribe` — an app that need not be installed, and is not the fixture
suite the benchmark is supposed to measure.

The harness that produces the project's headline number cannot currently be
aimed at the apps it is meant to measure.

**Fixed 19 Aug 2026.** `eval.py` now takes `--project` / `--package` /
`--activity` / `--serial`, resolving through `targets.target_for_project()` and
identifying the toolkit from the installed APK when only a package is given —
the same path `run.py` uses. Each arm runs in its own directory under
`runs/eval/<package>/`, because the Explorer writes `trace.json` and screenshots
into `cfg.run_dir` and the old shared `runs/latest` had the arms overwriting each
other's evidence. Results are mirrored to `runs/latest/eval.json` so the
console's Benchmark page, which reads that fixed path, keeps working.

Timing per arm is now recorded too, which is a first input to M6.

---

## G13 — The default target was an app that existed on one laptop

**Severity:** medium · **Status:** fixed 25 Aug 2026 · **Threatens:** every first run

`config.PACKAGE` defaulted to `com.scribe.scribe`, the app Gremlin was first
written against. With nothing selected the console's status chip advertised it
as the target, `run.py` printed "No app projects detected; using the default
target" and carried on, and `eval.main()` said much the same before benchmarking
an app that was almost certainly not installed.

Every one of those is the same mistake: treating "nobody has chosen yet" as a
value rather than as a missing value, and then falling back to a fiction so that
the failure happens later, somewhere less legible — a launch that silently does
nothing, or a benchmark measuring an app that is not there.

**Fixed.** `PACKAGE`/`ACTIVITY` are empty, `SCRIBE_ROOT` defaults to the projects
root rather than a `Scribe/` subdirectory that need not exist, and all three
entry points refuse instead of inventing a target: `run.py` and `eval.py` exit
naming the flags that fix it, `/start` returns 400, and the console chip reads
the live selection, falling back to "no app selected".

---

## G11 — Tier 2 refuses to run while the Gremlin repo is dirty

**Severity:** low · **Status:** FIXED 21 Aug 2026 · **Threatens:** developer time

`fixer._require_clean_tree()` runs `git status` against `cfg.scribe_root`, and
the fixtures live **inside this repository**. So any uncommitted change anywhere
in Gremlin — including edits to the agent itself — makes Tier 2 refuse to start
on a fixture, with a message about the app's working tree that points at the
wrong repository.

Correct behaviour for a real app under test in its own repo; confusing for the
bundled fixtures.

**Fixed** by taking the properly-costly option: the fixtures moved to one
repository each (`fixtures/README.md`), so the fixer's tree is the app's own and
Gremlin's state is irrelevant to it. The demo costs one `git clone`, which the
reproducibility claim wanted anyway.

Two things were kept from the cheap option, because the nesting case still
exists for real apps inside monorepos: the error now names the resolved
repository root and lists what is dirty, and it says when the app sits inside a
larger repo that a fix would be committed to. Nesting stays a warning, never a
refusal.

---

## G12 — Gate 2's thresholds are magic numbers

**Severity:** medium · **Status:** partly fixed 21 Aug 2026 · **Threatens:** M4

`screen_looks_same()` passes at a phash distance of ≤20, relaxed to ≤32 for
layout-class bugs (`gremlin/fixer.py`). Neither number is derived from anything.
A correct layout fix that reflows substantially can fail; a subtle cheat that
barely changes the screen can pass.

**The thresholds were the smaller half of the problem.** Measured on two real
autofix attempts against the crash-class fixtures, both of which produced
*correct* patches and both of which the gate reverted at distance 34:

- replacing `throw StateError(...)` in a tap handler with a `SnackBar`
- giving `BadBuildPage` a real `Scaffold` instead of throwing during `build()`

Neither is a cheat, and no threshold could have admitted them, because the gate
was asking the wrong question. `pre_png` is the *failure* frame. For a layout
defect that frame is a working screen — the overflowing `Row` renders, and a fix
reflows it modestly, so "still recognisable" means something. For a crash it is
the defect itself: Flutter's red error box, or the screen an instant before it
threw. Requiring the patched app to still resemble it is requiring the bug back.

**Partly fixed.** The distance comparison now applies only to layout-class bugs
(`compare_to_pre`); crash-class fixes keep the blank/collapsed check, which is
what actually catches a deleted widget, and skip the comparison. The ≤32
threshold for layout is still an unvalidated number — that half stands, and the
calibration below is still owed.

**Fix.** Calibrate the remaining threshold on the fixtures alongside G7, and
report the gate's false-accept and false-reject rates on the adversarial suite
(G9) rather than presenting the number as given.
