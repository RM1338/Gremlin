"""Bug reports — Tier 0 and Tier 1.

Tier 0 is a markdown file per bug: the screenshot, the matched log line with its
surrounding context, the source location, and the reproduction steps drawn from
the action trace. It is always produced and involves no model, so there is
nothing to trust.

Tier 1 renders the same report as a self-contained prompt with the relevant
source excerpt inlined, ready to paste into whichever assistant you already use.
It grants nothing write access, which is why most people will run this tier.
"""

from __future__ import annotations

import re
from pathlib import Path

from .config import Config
from .models import Action, Bug
from . import platforms


def _repro_steps(trace: list[Action]) -> str:
    if not trace:
        return "_(bug present at launch — no actions required)_"
    lines = []
    for i, a in enumerate(trace, 1):
        if a.verb == "tap":
            what = f"Tap **{a.target_label or f'({a.x},{a.y})'}**"
        elif a.verb == "type":
            what = f"Type `{a.text}`"
        elif a.verb == "scroll":
            what = f"Scroll {a.direction}"
        else:
            what = "Press **back**"
        lines.append(f"{i}. {what}")
    return "\n".join(lines)


def _source_excerpt(scribe_root: Path, dart_file: str | None, dart_line: int | None,
                    span: int = 12, platform: str | None = None) -> tuple[str, str] | None:
    """Return (relative_path, excerpt) around the failing line, if resolvable."""
    if not dart_file or not dart_line:
        return None
    plat = platforms.by_name(platform)
    # Log paths carry a toolkit-specific prefix ("package:myapp/…" for Flutter,
    # "./src/…" for React Native); the Platform knows how to strip it.
    rel = plat.normalize_source_path(dart_file)
    path = scribe_root / rel
    if not path.exists():
        # Fall back to a basename search in the places this toolkit keeps source.
        name = Path(rel).name
        matches = [m for g in plat.source_globs
                   for m in scribe_root.glob(g.format(name=name))]
        if not matches:
            return None
        path = matches[0]
        rel = str(path.relative_to(scribe_root))
    lines = path.read_text(errors="replace").splitlines()
    lo = max(0, dart_line - span)
    hi = min(len(lines), dart_line + span)
    numbered = []
    for n in range(lo, hi):
        marker = ">>" if n + 1 == dart_line else "  "
        numbered.append(f"{marker} {n + 1:4} | {lines[n]}")
    return rel, "\n".join(numbered)


def tier0_markdown(bug: Bug, cfg: Config) -> str:
    loc = f"`{bug.dart_file}:{bug.dart_line}`" if bug.dart_file else "_(not reported in log)_"
    context = "\n".join(bug.context) if bug.context else bug.log_line
    return f"""# Bug: {bug.title()}

| | |
|---|---|
| **Severity** | {bug.severity} |
| **Signal** | `{bug.kind}` |
| **Source** | {loc} |
| **Found at step** | {bug.step} |
| **Screenshot** | `{bug.screenshot}` |

## Matched log line

```
{bug.log_line}
```

## Reproduction steps

{_repro_steps(bug.trace)}

## Log context

```
{context}
```
"""


def tier1_prompt(bug: Bug, cfg: Config) -> str:
    plat = platforms.by_name(cfg.platform)
    excerpt = _source_excerpt(cfg.scribe_root, bug.dart_file, bug.dart_line,
                              platform=cfg.platform)
    src_block = ""
    if excerpt:
        rel, code = excerpt
        src_block = (f"\n\nThe relevant source (`{rel}`, `>>` marks the failing line):"
                     f"\n\n```{plat.fence}\n{code}\n```")
    return f"""I have a {plat.label} app bug found by automated UI exploration.

**Signal (ground truth from `adb logcat`):**
```
{bug.log_line}
```

**Severity:** {bug.severity}  ·  **Source:** {bug.dart_file}:{bug.dart_line}

**How to reproduce (from a cold app start):**
{_repro_steps(bug.trace)}{src_block}

Please fix the root cause so this log signal no longer appears. Do NOT merely
silence it — {plat.fix_guidance} The screen must keep looking and behaving as
intended.
"""


def write_reports(bugs: list[Bug], cfg: Config) -> list[Path]:
    """Write Tier 0 and Tier 1 files for every bug. Returns the paths written."""
    written: list[Path] = []
    reports_dir = cfg.run_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    for i, bug in enumerate(bugs, 1):
        t0 = reports_dir / f"bug_{i:03d}.md"
        t0.write_text(tier0_markdown(bug, cfg))
        t1 = reports_dir / f"bug_{i:03d}.prompt.md"
        t1.write_text(tier1_prompt(bug, cfg))
        written += [t0, t1]
    return written
