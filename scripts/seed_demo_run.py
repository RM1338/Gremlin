"""Fabricate a complete run under runs/latest, for working on the console.

The console is mostly empty until a run has happened, which makes it impossible
to judge — or design — without a device attached. This writes a plausible run:
a trace, three bugs across all three severities, the Tier-0/1/2 artifacts the
Bugs page renders, an eval table, and placeholder screenshots.

    python scripts/seed_demo_run.py

Everything lands under runs/, which is git-ignored. It is demo data and is
labelled as such in the payload, so it can never be mistaken for a real result.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
RUN = ROOT / "runs" / "latest"
SCREENS = RUN / "screens"
REPORTS = RUN / "reports"

W, H = 360, 760
SCREEN_NAMES = [
    "Home", "Library", "Recording detail", "Search", "Settings",
    "Account", "Export sheet", "Playback",
]


def _mock_screen(path: Path, title: str, seed: int, broken: bool = False) -> None:
    """A stand-in phone screenshot: a title bar, some list rows, a nav bar."""
    rnd = random.Random(seed)
    img = Image.new("RGB", (W, H), (18, 21, 28))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 96], fill=(29, 34, 45))
    d.text((20, 52), title, fill=(238, 241, 246))
    y = 120
    while y < H - 120:
        h = rnd.choice((64, 64, 88))
        d.rounded_rectangle([16, y, W - 16, y + h], radius=10, fill=(23, 27, 36))
        d.rectangle([32, y + 18, 32 + rnd.randint(90, 200), y + 26], fill=(90, 100, 115))
        d.rectangle([32, y + 38, 32 + rnd.randint(50, 130), y + 44], fill=(60, 68, 80))
        y += h + 12
    if broken:  # a band bleeding off the right edge, like an overflow
        d.rectangle([120, 300, W + 60, 348], fill=(246, 171, 61))
    d.rectangle([0, H - 72, W, H], fill=(29, 34, 45))
    for i in range(4):
        d.ellipse([34 + i * 84, H - 50, 58 + i * 84, H - 26], fill=(70, 79, 92))
    img.save(path)


TRACE = [
    ("tap", "Library", "open the library, unvisited"),
    ("tap", "Recent recording", "a list item leads to a detail screen"),
    ("scroll", "down", "reveal controls below the fold"),
    ("back", None, "screen fully covered, backing out"),
    ("tap", "Search", "search is untried"),
    ("type", "hello", "fill the field to reach results"),
    ("tap", "Settings", "last untapped section"),
    ("tap", "Export", "opens a sheet with an unfitting row"),
]

BUGS = [
    dict(severity="layout", kind="renderflex-overflow", step=8,
         log_line="I/flutter (12043): A RenderFlex overflowed by 42 pixels on the right.",
         dart_file="lib/screens/export_sheet.dart", dart_line=64,
         verified=True),
    dict(severity="crash", kind="dart-exception", step=6,
         log_line="E/flutter (12043): Unhandled Exception: Null check operator used on a null value",
         dart_file="lib/screens/search_screen.dart", dart_line=112,
         verified=False),
    dict(severity="hang", kind="jank", step=3,
         log_line="I/Choreographer(12043): Skipped 47 frames!  The application may be doing too much work on its main thread.",
         dart_file=None, dart_line=None, verified=None),
]


def main() -> None:
    SCREENS.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)

    for i, name in enumerate(SCREEN_NAMES, 1):
        _mock_screen(SCREENS / f"step_{i:03d}.png", name, i)
    for i, b in enumerate(BUGS, 1):
        _mock_screen(SCREENS / f"bug_{i:03d}.png", f"{b['kind']}", 90 + i,
                     broken=b["severity"] == "layout")
        b["screenshot"] = f"runs/latest/screens/bug_{i:03d}.png"

    trace = [
        {"verb": v, **({"target_label": t} if v == "tap" else {}),
         **({"text": t} if v == "type" else {}),
         **({"direction": t} if v == "scroll" else {}),
         **({"x": 180, "y": 300} if v == "tap" else {}), "reason": r}
        for v, t, r in TRACE
    ]

    bugs = []
    for i, b in enumerate(BUGS, 1):
        loc = f" @ {b['dart_file']}:{b['dart_line']}" if b["dart_file"] else ""
        bugs.append({
            "severity": b["severity"], "kind": b["kind"], "title": f"{b['kind']}{loc}",
            "log_line": b["log_line"],
            "context": [b["log_line"], "I/flutter (12043):     at _RenderLayoutBuilder.performLayout"],
            "dart_file": b["dart_file"], "dart_line": b["dart_line"],
            "screenshot": b["screenshot"], "step": b["step"],
            "dedup_key": f"{b['kind']}|{b['dart_file']}:{b['dart_line']}",
            "trace": trace[: b["step"]],
        })
        (REPORTS / f"bug_{i:03d}.md").write_text(
            f"# Bug: {bugs[-1]['title']}\n\n**Severity:** {b['severity']}\n\n"
            f"## Matched log line\n\n```\n{b['log_line']}\n```\n")
        (REPORTS / f"bug_{i:03d}.prompt.md").write_text(
            f"I have a Flutter app bug found by automated UI exploration.\n\n"
            f"**Signal (ground truth from `adb logcat`):**\n```\n{b['log_line']}\n```\n\n"
            f"Please fix the root cause so this log signal no longer appears.\n")
        if b["verified"] is not None:
            (REPORTS / f"bug_{i:03d}.fix.json").write_text(json.dumps({
                "verified": b["verified"],
                "branch": f"gremlin/fix-{b['kind']}-1755600000",
                "note": ("verified — patch cleared all three gates; left on branch for review"
                         if b["verified"] else "reverted — failed gate(s): screen-looks-same"),
                "guard_violations": [],
                "gates": [
                    {"name": "signal-gone", "passed": True,
                     "detail": "target signal absent on replay"},
                    {"name": "screen-looks-same", "passed": b["verified"],
                     "detail": ("perceptual distance 18 (<= 32)" if b["verified"]
                                else "screen changed too much (distance 41) — widget likely removed")},
                    {"name": "no-new-breakage", "passed": b["verified"],
                     "detail": "no new signals introduced" if b["verified"] else "not reached"},
                ],
            }, indent=2))

    (RUN / "trace.json").write_text(json.dumps({
        "package": "com.gremlin.gremlin_bench",
        "demo": True,  # so this can never be mistaken for a measured result
        "steps": len(trace), "distinct_screens": len(SCREEN_NAMES),
        "summary": {
            "steps": len(trace), "screens": len(SCREEN_NAMES), "bugs": len(bugs),
            "duration_sec": 148.6,
            "verbs": {"tap": 5, "scroll": 1, "type": 1, "back": 1},
            "sections": ["Export", "Library", "Recent recording", "Search", "Settings"],
            "bugs_by_severity": {"layout": 1, "crash": 1, "hang": 1},
            "controls_tapped": 19, "controls_seen": 19, "complete": True,
            "note": "Coverage complete — tapped every reachable control (19 across 8 screens).",
            "ended_early": False,
        },
        "trace": trace, "bugs": bugs,
    }, indent=2))

    # Demo benchmark in the real (schema 2) shape, so the page's spread, sample
    # table and detection rates are exercised by the seeder rather than only by a
    # measured run. Every payload still carries demo:true — the pill on the page
    # is what keeps this from being read as a result.
    def _arm(name, screens, secs, keys_per_seed):
        runs = [{"explorer": name, "actions": 30, "distinct_screens": sc,
                 "distinct_bugs": len(ks), "duration_sec": d, "seed": i,
                 "bug_keys": ks, "error": ""}
                for i, (sc, d, ks) in enumerate(zip(screens, secs, keys_per_seed))]
        import statistics as st
        agg = lambda xs: {"n": len(xs), "mean": round(st.fmean(xs), 2),
                          "sd": round(st.stdev(xs), 2) if len(xs) > 1 else 0.0,
                          "min": min(xs), "max": max(xs),
                          "median": round(st.median(xs), 2)}
        union = sorted({k for ks in keys_per_seed for k in ks})
        return {"runs": runs, "completed": len(runs), "failed": 0,
                "screens": agg(screens), "bugs": agg([len(k) for k in keys_per_seed]),
                "duration_sec": agg(secs), "bugs_union": union}

    OVER = "renderflex-overflow|lib/screens/settings.dart:N"
    CRASH = "dart-exception|lib/screens/profile.dart:N"
    JANK = "frame-skip|Choreographer"
    arms = {
        "gremlin-vision": _arm("gremlin-vision", [8, 9, 7, 8, 8], [148.6, 151.2, 139.9, 146.0, 150.1],
                               [[OVER, CRASH, JANK], [OVER, CRASH, JANK], [OVER, CRASH],
                                [OVER, CRASH, JANK], [OVER, CRASH, JANK]]),
        "gremlin-coverage": _arm("gremlin-coverage", [7, 7, 6, 8, 7], [61.2, 59.8, 63.0, 60.1, 62.4],
                                 [[OVER, CRASH], [OVER, CRASH], [OVER],
                                  [OVER, CRASH, JANK], [OVER, CRASH]]),
        "monkey": _arm("monkey", [3, 2, 3, 4, 2], [44.0, 43.1, 45.2, 44.8, 43.9],
                       [[OVER], [], [OVER], [OVER], []]),
    }
    detection = {}
    for key in sorted({k for a in arms.values() for k in a["bugs_union"]}):
        detection[key] = {n: {"found_in": sum(1 for r in a["runs"] if key in r["bug_keys"]),
                              "of": a["completed"]}
                          for n, a in arms.items()}

    (RUN / "eval.json").write_text(json.dumps({
        "schema": 2, "demo": True,
        "generated_at": "2026-08-25T21:00:00+0530",
        "app": {"package": "com.gremlin.gremlin_bench", "platform": "flutter",
                "source_root": "~/Projects/gremlin-bench-flutter", "commit": "demo000"},
        "device": {"serial": "localhost:5555", "kind": "sandbox", "width": 1080,
                   "height": 1920, "android": "13", "sdk": "33", "model": "redroid"},
        "vision_model": {"provider": "gemini", "model": "gemini-2.0-flash"},
        "protocol": {"actions": 30, "repeats": 5, "seeds": [0, 1, 2, 3, 4]},
        "arms": arms, "detection_rates": detection,
        "package": "com.gremlin.gremlin_bench", "platform": "flutter",
        "actions": 30, "seed": 0,
        "results": [{"explorer": n, "actions": 30,
                     "distinct_screens": a["screens"]["mean"],
                     "distinct_bugs": a["bugs"]["mean"],
                     "duration_sec": a["duration_sec"]["mean"]}
                    for n, a in arms.items()],
    }, indent=2))

    print(f"seeded demo run in {RUN}")
    print(f"  {len(SCREEN_NAMES)} screens, {len(bugs)} bugs, eval with 3 arms")
    print("  DEMO DATA — every payload carries \"demo\": true")


if __name__ == "__main__":
    main()
