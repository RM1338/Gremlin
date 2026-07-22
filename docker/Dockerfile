# Gremlin development container.
#
# Holds everything a run needs *except* the model: Python for the engine, Node
# for the console, adb to drive the device, and the Claude Code CLI — which is
# not optional, because gremlin/llm.py shells out to `claude -p` for Tier-2
# fixes. Inference lives in the separate `vllm` service; see docker/compose.yml.
#
# Built and run by an unprivileged user. Nothing here needs host root.

FROM node:22-bookworm

# adb drives the device or emulator; the rest is the Python toolchain and the
# git/curl that Claude Code and the fixer's guard-rebuild-replay loop rely on.
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 \
        python3-venv \
        python3-pip \
        android-tools-adb \
        git \
        curl \
        ca-certificates \
        unzip \
        less \
    && rm -rf /var/lib/apt/lists/*

RUN npm install -g @anthropic-ai/claude-code

# Match the host user's ids so files written into the bind-mounted repo stay
# owned by you rather than by root. The stock node:22 image already occupies
# uid 1000, so it is removed first.
ARG UID=1000
ARG GID=1000
RUN userdel -r node 2>/dev/null || true; \
    groupadd -g "${GID}" gremlin 2>/dev/null || true; \
    useradd -u "${UID}" -g "${GID}" -m -s /bin/bash gremlin

# Debian marks the system Python externally-managed (PEP 668), so the engine's
# dependencies go in their own venv. Putting it on PATH makes `python` and
# `pip` resolve to it without any activate step.
ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m venv "$VIRTUAL_ENV" && chown -R "${UID}:${GID}" "$VIRTUAL_ENV"
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Copied separately from the source so the dependency layer survives edits to
# the engine and only rebuilds when requirements.txt itself changes.
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt && rm /tmp/requirements.txt

USER gremlin
WORKDIR /workspace

# Keeps the Claude Code login on a named volume, so authenticating once
# survives every later rebuild of this image.
ENV CLAUDE_CONFIG_DIR=/home/gremlin/.claude

CMD ["bash"]
