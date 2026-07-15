"""Core data types shared across the explorer, replayer, and reporter.

An Action is one of the four verbs plus its arguments. A Trace is the full
ordered list of actions from app launch — it is what makes a bug reproducible
and what the replayer re-executes verbatim.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class Action:
    verb: str  # "tap" | "type" | "back" | "scroll"
    x: int | None = None
    y: int | None = None
    text: str | None = None
    direction: str | None = None
    target_label: str | None = None  # what the tapped element was called
    reason: str = ""  # the model's one-sentence justification

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None and v != ""}


@dataclass
class Bug:
    severity: str
    kind: str
    log_line: str
    context: list[str]
    dart_file: str | None
    dart_line: int | None
    screenshot: str  # path to the screenshot at the moment of failure
    step: int  # which step in the trace produced it
    trace: list[Action] = field(default_factory=list)  # actions from launch to here
    dedup_key: str = ""

    def title(self) -> str:
        loc = f" @ {self.dart_file}:{self.dart_line}" if self.dart_file else ""
        return f"{self.kind}{loc}"
