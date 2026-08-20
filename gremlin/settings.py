"""Runtime settings, as the console sees them.

Everything here is already configurable — it just lived in `.env` and a text
editor. This module makes that same file readable and writable from the console
without inventing a second place for configuration to live: `.env` stays the
source of truth, and the writer preserves the file's comments and ordering so a
hand-edited file survives a round trip through the UI.

Three kinds of field, and the difference matters:

  live     read from os.environ at the moment it is used, so a write here takes
           effect on the next run with no restart (FIX_BACKEND, LLM_PROVIDER).
  applied  held on the dashboard's Config object; the caller patches it live.
  restart  read once at import time (PROJECTS_ROOT), so it needs a restart.

Secrets are write-only. They are reported as set/unset and never returned.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from ._env import load_dotenv

load_dotenv()

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


@dataclass(frozen=True)
class Field:
    key: str
    group: str
    label: str
    help: str
    kind: str = "text"            # text | choice | secret | int
    choices: tuple = ()
    default: str = ""
    effect: str = "live"          # live | applied | restart
    depends_on: tuple = ()        # (key, value) — only meaningful when set

    def as_dict(self) -> dict:
        return {"key": self.key, "group": self.group, "label": self.label,
                "help": self.help, "kind": self.kind, "choices": list(self.choices),
                "effect": self.effect,
                "depends_on": list(self.depends_on) if self.depends_on else None}


FIELDS: tuple[Field, ...] = (
    # ---- Tier 2: who writes the patch --------------------------------------
    Field("FIX_BACKEND", "remediation", "Coding agent",
          "Which agent turns a bug's Tier-1 prompt into a source edit. The "
          "guard, rebuild, replay and three gates around it are identical "
          "whichever one you pick — that machinery, not the agent, is what "
          "makes a fix trustworthy.",
          kind="choice", choices=("prompt", "claude", "codex", "copilot", "command"),
          default="prompt"),
    Field("FIX_CMD", "remediation", "Custom command",
          "Template for FIX_BACKEND=command. {cwd}, {prompt_file} and {prompt} "
          "are substituted, e.g. myagent --repo {cwd} --prompt-file {prompt_file}",
          depends_on=("FIX_BACKEND", "command")),

    # ---- the vision policy --------------------------------------------------
    Field("LLM_PROVIDER", "vision", "Vision backend",
          "Who decides what to tap from a screenshot. `local` is any server "
          "speaking the OpenAI chat-completions shape — Ollama, vLLM, llama.cpp.",
          kind="choice", choices=("gemini", "groq", "local"), default="gemini"),
    Field("LOCAL_BASE_URL", "vision", "Local base URL",
          "OpenAI-compatible endpoint, e.g. http://localhost:11434/v1",
          depends_on=("LLM_PROVIDER", "local")),
    Field("LOCAL_MODEL", "vision", "Local model",
          "Model name as the server knows it, e.g. qwen3-vl:4b",
          depends_on=("LLM_PROVIDER", "local")),
    Field("GEMINI_MODEL", "vision", "Gemini model",
          "Gemini is both the provider and the model. 2.5-flash-lite is the one "
          "with broadly-granted free-tier quota; other flash models often show a "
          "limit-0 free quota depending on project and region.",
          default="gemini-2.5-flash-lite", depends_on=("LLM_PROVIDER", "gemini")),
    Field("GROQ_MODEL", "vision", "Groq model",
          "Groq is an inference provider, not a model — it serves open weights, "
          "so the model is named separately. Groq retires hosted models without "
          "notice; list what it currently serves with GET /openai/v1/models.",
          default="qwen/qwen3.6-27b", depends_on=("LLM_PROVIDER", "groq")),
    Field("GEMINI_API_KEY", "vision", "Gemini API key",
          "Stored in .env on this machine. Never sent anywhere but Google.",
          kind="secret", depends_on=("LLM_PROVIDER", "gemini")),
    Field("GROQ_API_KEY", "vision", "Groq API key",
          "Stored in .env on this machine. Never sent anywhere but Groq.",
          kind="secret", depends_on=("LLM_PROVIDER", "groq")),

    # ---- the app under test -------------------------------------------------
    Field("GREMLIN_PROJECTS_ROOT", "app", "Projects root",
          "Scanned for app projects. This directory and its immediate children "
          "only — point it at the folder that CONTAINS your apps.",
          effect="restart"),
    Field("GREMLIN_PLATFORM", "app", "Toolkit override",
          "Gremlin identifies Flutter or React Native from the project, and "
          "from the APK for a device-only app. Set this only when that guess is "
          "wrong — it picks the log vocabulary the oracle matches against.",
          kind="choice", choices=("", "flutter", "react-native"), effect="applied"),

    # ---- run defaults -------------------------------------------------------
    Field("GREMLIN_MAX_STEPS", "run", "Step budget",
          "Upper bound on actions per run. Coverage-driven exploration usually "
          "stops earlier, when every reachable control has been tapped.",
          kind="int", default="80", effect="applied"),
    Field("GREMLIN_POLICY", "run", "Exploration policy",
          "`vision` asks the model what to tap. `coverage` takes the next "
          "untapped control and never calls a model — it is the ablation arm "
          "the benchmark measures the model against.",
          kind="choice", choices=("vision", "coverage"), default="vision",
          effect="applied"),
)

GROUPS = (
    ("remediation", "Autofix", "Who writes the patch when you run Tier 2."),
    ("vision", "Vision model",
     "Who decides what to tap next. The backend is the PROVIDER — Groq serves "
     "open weights on its own hardware, Gemini is both provider and model, and "
     "`local` is any OpenAI-compatible server. The model is named separately."),
    ("app", "App under test", "Where Gremlin looks, and what it assumes it found."),
    ("run", "Run defaults", "What a run does when you press Start."),
)


def _value(f: Field) -> str:
    return os.environ.get(f.key, f.default)


def read() -> dict:
    """Current values, the field catalogue, and what is actually installed."""
    values, secrets = {}, {}
    for f in FIELDS:
        if f.kind == "secret":
            secrets[f.key] = bool(os.environ.get(f.key, "").strip())
        else:
            values[f.key] = _value(f)
    return {
        "fields": [f.as_dict() for f in FIELDS],
        "groups": [{"key": k, "label": l, "help": h} for k, l, h in GROUPS],
        "values": values,
        "secrets": secrets,          # set/unset only; never the value itself
        "capabilities": capabilities(),
        "env_path": str(ENV_PATH),
    }


def capabilities() -> dict:
    """What is actually available on this machine, so the UI can say so.

    A settings page that lets you pick an agent you have not installed is a
    settings page that fails three minutes later, inside a run.
    """
    agents = {name: bool(shutil.which(name)) for name in ("claude", "codex", "copilot")}
    local = None
    if os.environ.get("LLM_PROVIDER", "").strip().lower() == "local":
        local = _probe_local(os.environ.get("LOCAL_BASE_URL", ""))
    return {"agents": agents, "local": local}


def _probe_local(base_url: str) -> dict:
    """Is the local model server answering? Cheap, and never raises."""
    if not base_url:
        return {"ok": False, "detail": "no LOCAL_BASE_URL set"}
    url = base_url.rstrip("/") + "/models"
    try:
        with urlopen(url, timeout=2.5) as r:
            return {"ok": 200 <= r.status < 300, "detail": f"{url} → {r.status}"}
    except URLError as e:
        return {"ok": False, "detail": f"{url} unreachable ({e.reason})"}
    except Exception as e:  # a non-HTTP endpoint, a proxy, anything
        return {"ok": False, "detail": f"{url} → {type(e).__name__}"}


def validate(patch: dict) -> list[str]:
    """Reasons this patch would not work, in the developer's words."""
    by_key = {f.key: f for f in FIELDS}
    problems = []
    for key, raw in patch.items():
        f = by_key.get(key)
        if f is None:
            problems.append(f"{key} is not a setting Gremlin knows about")
            continue
        v = (raw or "").strip()
        if f.kind == "choice" and v not in f.choices:
            problems.append(f"{f.label}: '{v}' is not one of {', '.join(c or '(auto)' for c in f.choices)}")
        if f.kind == "int" and v and not v.isdigit():
            problems.append(f"{f.label}: '{v}' is not a whole number")
    # A key is an opaque ASCII token. Pasting something else in — an error
    # message, a whole curl command — is a very easy mistake to make, and it is
    # only ever discovered later, as a UnicodeEncodeError from deep inside
    # http.client while a phone sits awake waiting for a first frame.
    for key, raw in patch.items():
        f = by_key.get(key)
        if f is None or f.kind != "secret":
            continue
        v = (raw or "").strip()
        if not v:
            continue
        if not v.isascii() or any(c.isspace() for c in v):
            problems.append(
                f"{f.label}: that does not look like a key — it has spaces or "
                f"non-ASCII characters in it. Paste the token on its own.")
        elif len(v) > 200:
            problems.append(f"{f.label}: {len(v)} characters is too long for a key")

    # The one cross-field rule worth enforcing: an agent that is not installed
    # cannot write a patch, and finding that out mid-run is the bad way.
    backend = (patch.get("FIX_BACKEND") or os.environ.get("FIX_BACKEND", "prompt")).strip()
    if backend in ("claude", "codex", "copilot") and not shutil.which(backend):
        problems.append(f"'{backend}' is not on PATH — install its CLI, or pick another agent")
    if backend == "command":
        cmd = patch.get("FIX_CMD", os.environ.get("FIX_CMD", "")).strip()
        if not cmd:
            problems.append("the 'command' agent needs a command template")
    return problems


def write(patch: dict) -> None:
    """Persist to .env and to this process, so the next run sees it.

    Rewrites in place: an existing key keeps its line and its comment block, and
    only new keys are appended. A .env someone has commented carefully should
    come back out of the UI still readable.
    """
    lines = ENV_PATH.read_text().splitlines() if ENV_PATH.exists() else []
    remaining = dict(patch)

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key = stripped.split("=", 1)[0].strip()
        if key in remaining:
            lines[i] = f"{key}={remaining.pop(key)}"

    if remaining:
        if lines and lines[-1].strip():
            lines.append("")
        lines.append("# ---- set from the console ----")
        lines += [f"{k}={v}" for k, v in remaining.items()]

    ENV_PATH.write_text("\n".join(lines) + "\n")

    # os.environ is what every live read actually consults, so update it too —
    # writing only the file would leave the running dashboard on stale values.
    for k, v in patch.items():
        if v == "":
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
