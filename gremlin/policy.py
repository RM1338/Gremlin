"""The policy: decide where to go next.

The model gets the current screenshot, the grounded element list, and a summary
of screens already visited. It returns one action and one sentence of reasoning.
Its goal is to maximize distinct screens reached — so it should prefer actions
that lead somewhere new, and it must plan a few steps ahead (reaching a gated
screen may require typing into a field first).

Crucially, the policy only decides WHERE to go. Whether anything broke is the
oracle's job, never the model's.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .grounding import Element
from .vision import generate as vision_generate
from .llm import extract_json


@dataclass
class Decision:
    verb: str
    index: int | None
    text: str | None
    direction: str | None
    reason: str
    screen_name: str


_PROMPT = """\
You are Gremlin, an agent exploring an Android app to reach as many DISTINCT \
screens as possible, like a curious user poking at everything.

The attached image is the current screen.

Screens you have already visited: {visited}

Your recent actions (most recent last): {recent}
{stuck}
Tappable/visible elements on THIS screen (choose one by its index for a tap):
{elements}

Choose ONE next action. Prefer actions that lead to a screen you have NOT seen \
yet; avoid re-tapping things that keep you on the same screen or that just take \
you back to a screen you already visited. If the last few actions have been \
bouncing between the same two screens, do something different: press `back` to \
leave this area, or tap an element you have not tried. To get past a login or a \
text field, tap the field, then on a later step `type` into it.

Reply with ONLY a JSON object, no prose, no code fence:
{{
  "screen_name": "<2-4 word name for the current screen>",
  "verb": "tap" | "type" | "back" | "scroll",
  "index": <element index, required for tap, else null>,
  "text": "<text to type, required for type, else null>",
  "direction": "up" | "down" (required for scroll, else null),
  "reason": "<one short sentence: why this action explores something new>"
}}
"""


def decide(
    screenshot_path: Path,
    elements: list[Element],
    visited_summary: str,
    vision_width: int = 540,
    recent: str = "(none yet)",
    stuck: str = "",
) -> Decision:
    element_lines = (
        "\n".join(f"  {e.describe()}" for e in elements) or "  (no grounded elements)"
    )
    prompt = _PROMPT.format(
        visited=visited_summary,
        recent=recent,
        stuck=stuck,
        elements=element_lines,
    )
    reply = vision_generate(prompt, image_path=screenshot_path, vision_width=vision_width)
    data = extract_json(reply)
    return Decision(
        verb=str(data.get("verb", "back")),
        index=data.get("index"),
        text=data.get("text"),
        direction=data.get("direction"),
        reason=str(data.get("reason", "")),
        screen_name=str(data.get("screen_name", "screen")),
    )
