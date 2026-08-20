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
from .vision import generate as vision_generate, ModelError
from .llm import extract_json, LLMError


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


# The text the coverage-only arm types into fields. The vision policy chooses
# text per screen; the ablation arm must not, so one fixed string stands in —
# enough to get past a search box or a login field with no inference at all.
COVERAGE_TEXT = "gremlin"


def decide_coverage_only(_elements: list[Element]) -> Decision:
    """The no-LLM ablation arm (docs/KNOWN_ISSUES.md, G4).

    Returns a Decision that always defers to the explorer's own coverage logic.
    `Explorer._choose_and_execute` takes the next untapped control itself
    whenever the verb is not a usable "tap" pick, and falls back to
    type -> scroll -> back once a screen is exhausted. Naming the verb "type"
    keeps that final ladder intact.

    So the two arms differ in exactly two things: who ORDERS the untapped
    controls, and what text gets typed. Everything else — accessibility-tree
    grounding, coverage memory, the stopping rule — is held constant, which is
    what makes the comparison an ablation of the model rather than of the
    engine.
    """
    return Decision(
        verb="type",
        index=None,
        text=COVERAGE_TEXT,
        direction=None,
        reason="coverage-only policy (no model)",
        screen_name="",
    )


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
    try:
        data = extract_json(reply)
    except LLMError as e:
        # A reply we can't parse is a model problem, not a bug in the run — a
        # reasoning model that thinks past its token budget returns nothing
        # usable. Report it as one, so the explorer ends the run cleanly and
        # keeps the trace instead of dying with a stack trace and losing it.
        raise ModelError(f"unparseable reply from the vision model: {e}") from e
    return Decision(
        verb=str(data.get("verb", "back")),
        index=data.get("index"),
        text=data.get("text"),
        direction=data.get("direction"),
        reason=str(data.get("reason", "")),
        screen_name=str(data.get("screen_name", "screen")),
    )
