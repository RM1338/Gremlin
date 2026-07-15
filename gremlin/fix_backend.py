"""Pluggable Tier-2 fix backend.

Tier 2 needs some coding agent to turn a bug's Tier-1 prompt into an actual
source edit on a scratch branch. Which agent is a per-developer choice: not
everyone has an autonomous CLI agent, and those who do use different ones. So
the backend is selected by the `FIX_BACKEND` env var, exactly like the vision
policy is selected by `LLM_PROVIDER`.

The important part: the guard, rebuild, replay and three gates around this call
are identical no matter which backend writes the diff. That machinery — not the
choice of agent — is what makes a proposed fix trustworthy. A backend only has
to edit the source in `cwd`; Gremlin grades the result the same way regardless.

Backends:
  prompt   (default) — make no edits. The caller emits the portable Tier-1
                       prompt for the developer to run in whatever tool they use.
  claude              — headless Claude Code (`claude -p`), the reference agent.
  codex               — OpenAI Codex CLI (`codex exec`).
  copilot             — GitHub Copilot CLI (`copilot -p`).
  command             — a user-defined command template in `FIX_CMD`, e.g.
                        FIX_CMD='myagent --repo {cwd} --prompt-file {prompt_file}'
                        The universal escape hatch for any agent we don't name.
"""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import tempfile
from pathlib import Path

from ._env import load_dotenv
from .llm import LLMError, run_claude

# Load .env now so FIX_BACKEND / FIX_CMD are set before they are first read.
load_dotenv()

DEFAULT_BACKEND = "prompt"


class FixBackendError(RuntimeError):
    """The configured backend is unknown, missing, or failed to run."""


def backend_name() -> str:
    return os.environ.get("FIX_BACKEND", DEFAULT_BACKEND).strip().lower()


def edits_source(backend: str | None = None) -> bool:
    """True if this backend actually writes code, vs. only emitting a prompt."""
    return (backend or backend_name()) not in ("prompt", "none", "")


def apply_fix(prompt: str, cwd: Path, backend: str | None = None,
              timeout: float = 300.0) -> None:
    """Have the configured agent edit the source in `cwd` to fix the bug.

    Returns nothing; the caller inspects `git diff` to see what changed. Raises
    FixBackendError if the backend is unknown or its CLI is not installed.
    """
    backend = backend or backend_name()
    if not edits_source(backend):
        return  # prompt-only: nothing to execute here
    runner = _RUNNERS.get(backend)
    if runner is None:
        raise FixBackendError(
            f"unknown FIX_BACKEND '{backend}'. "
            f"Use one of: {', '.join(['prompt', *_RUNNERS])}."
        )
    runner(prompt, cwd, timeout)


# ---- individual backends ----------------------------------------------------

def _run_claude(prompt: str, cwd: Path, timeout: float) -> None:
    try:
        run_claude(prompt, cwd=cwd, allowed_tools="Read,Edit,Write", timeout=timeout)
    except LLMError as e:
        raise FixBackendError(str(e)) from e


def _run_codex(prompt: str, cwd: Path, timeout: float) -> None:
    # Codex CLI, non-interactive; --full-auto lets it edit files without asking.
    _run_argv(["codex", "exec", "--full-auto", prompt], cwd, timeout, "codex")


def _run_copilot(prompt: str, cwd: Path, timeout: float) -> None:
    # GitHub Copilot CLI programmatic mode; flags may vary by CLI version.
    _run_argv(["copilot", "-p", prompt, "--allow-all-tools"], cwd, timeout, "copilot")


def _run_command(prompt: str, cwd: Path, timeout: float) -> None:
    template = os.environ.get("FIX_CMD")
    if not template:
        raise FixBackendError(
            "FIX_BACKEND=command needs a FIX_CMD template, e.g. "
            "FIX_CMD='myagent --repo {cwd} --prompt-file {prompt_file}'"
        )
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
        f.write(prompt)
        prompt_file = f.name
    try:
        cmd = template.format(
            cwd=str(cwd), prompt_file=prompt_file, prompt=shlex.quote(prompt),
        )
        subprocess.run(cmd, shell=True, cwd=str(cwd), check=True, timeout=timeout)
    except subprocess.CalledProcessError as e:
        raise FixBackendError(f"FIX_CMD failed (exit {e.returncode})") from e
    except subprocess.TimeoutExpired as e:
        raise FixBackendError(f"FIX_CMD timed out after {timeout}s") from e
    finally:
        os.unlink(prompt_file)


def _run_argv(argv: list[str], cwd: Path, timeout: float, tool: str) -> None:
    if shutil.which(argv[0]) is None:
        raise FixBackendError(
            f"'{tool}' CLI not found on PATH. Install it, pick another "
            f"FIX_BACKEND, or use FIX_BACKEND=command with your own FIX_CMD."
        )
    try:
        out = subprocess.run(
            argv, cwd=str(cwd), capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired as e:
        raise FixBackendError(f"{tool} timed out after {timeout}s") from e
    if out.returncode != 0:
        raise FixBackendError(f"{tool} exited {out.returncode}: {out.stderr[:400]}")


_RUNNERS = {
    "claude": _run_claude,
    "codex": _run_codex,
    "copilot": _run_copilot,
    "command": _run_command,
}
