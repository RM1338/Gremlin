# Gremlin development container.
#
# Holds everything a run needs *except* the model: Python for the engine, Node
# for the console, adb to drive the device, and the Claude Code CLI — which is
# not optional, because gremlin/llm.py shells out to `claude -p` for Tier-2
# fixes. Inference lives in the separate `vllm` service; see docker/compose.yml.
#
# Built and run by an unprivileged user. Nothing here needs host root.

FROM node:22-bookworm

# adb drives the device or emulator; the JDK is what the Android SDK and Gradle
# run on; the xz/zip/libglu set is Flutter's documented Linux prerequisite. The
# rest is the Python toolchain and the git/curl that Claude Code and the fixer's
# guard-rebuild-replay loop rely on.
#
# The libx11/libxcb block down to libfreetype6 is the emulator's. It links its
# renderer against the X11 client libraries and resolves them at start-up even
# under -no-window — a missing one does not quietly degrade to headless, it
# aborts ("Could not open libX11-xcb.so.1, give up") and segfaults before adb
# ever sees the process. ALSA, PulseAudio and D-Bus come along the same path.
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 \
        python3-venv \
        python3-pip \
        android-tools-adb \
        openjdk-17-jdk-headless \
        git \
        curl \
        ca-certificates \
        unzip \
        zip \
        xz-utils \
        file \
        libglu1-mesa \
        less \
        libx11-6 \
        libx11-xcb1 \
        libxcb1 \
        libxcomposite1 \
        libxcursor1 \
        libxdamage1 \
        libxext6 \
        libxfixes3 \
        libxi6 \
        libxrandr2 \
        libxrender1 \
        libxtst6 \
        libxkbcommon0 \
        libnss3 \
        libasound2 \
        libpulse0 \
        libdbus-1-3 \
        libgl1 \
        libegl1 \
        libfontconfig1 \
        libfreetype6 \
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

# ---------------------------------------------------------------------------
# Android SDK
#
# gremlin/emulator.py locates `emulator` and `avdmanager` at fixed paths under
# ANDROID_HOME, so the layout matters more than the install method. Pinned
# versions rather than "latest": a run whose toolchain moves underneath it
# cannot produce a reproducible benchmark.
# ---------------------------------------------------------------------------
ENV ANDROID_HOME=/opt/android-sdk \
    ANDROID_SDK_ROOT=/opt/android-sdk \
    ANDROID_AVD_HOME=/opt/android-avd
ARG CMDLINE_TOOLS_VERSION=11076708
ARG ANDROID_API=34
ARG BUILD_TOOLS=34.0.0

RUN set -eux; \
    mkdir -p "$ANDROID_HOME/cmdline-tools"; \
    curl -fsSL -o /tmp/tools.zip \
      "https://dl.google.com/android/repository/commandlinetools-linux-${CMDLINE_TOOLS_VERSION}_latest.zip"; \
    unzip -q /tmp/tools.zip -d "$ANDROID_HOME/cmdline-tools"; \
    # The zip unpacks to `cmdline-tools/`; sdkmanager insists on being under a
    # version directory named `latest`, and refuses to run otherwise.
    mv "$ANDROID_HOME/cmdline-tools/cmdline-tools" "$ANDROID_HOME/cmdline-tools/latest"; \
    rm /tmp/tools.zip
ENV PATH="$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/platform-tools:$ANDROID_HOME/emulator:$PATH"

# google_apis rather than google_apis_playstore: the Play variant refuses
# `adb root`, which the grounding layer needs to read the view hierarchy.
RUN set -eux; \
    yes | sdkmanager --licenses >/dev/null; \
    sdkmanager --install \
      "platform-tools" \
      "emulator" \
      "platforms;android-${ANDROID_API}" \
      "build-tools;${BUILD_TOOLS}" \
      "system-images;android-${ANDROID_API};google_apis;x86_64" >/dev/null

# Baked in at build time so a run never waits on AVD creation. ANDROID_AVD_HOME
# keeps it outside the user's home, which is a volume mount at runtime and
# would otherwise hide it.
RUN set -eux; \
    mkdir -p "$ANDROID_AVD_HOME"; \
    echo no | avdmanager create avd \
      -n gremlin \
      -k "system-images;android-${ANDROID_API};google_apis;x86_64" \
      -d pixel_6 >/dev/null; \
    chown -R "${UID}:${GID}" "$ANDROID_AVD_HOME" "$ANDROID_HOME"

# ---------------------------------------------------------------------------
# Flutter
#
# Tier 2 is only trustworthy because a fix is rebuilt and replayed before it is
# accepted (gremlin/gates.py), and the GremlinBench fixtures are Flutter apps —
# so without a toolchain the ladder stops at Tier 1.
# ---------------------------------------------------------------------------
ENV FLUTTER_HOME=/opt/flutter
ARG FLUTTER_VERSION=3.24.5
RUN set -eux; \
    curl -fsSL -o /tmp/flutter.tar.xz \
      "https://storage.googleapis.com/flutter_infra_release/releases/stable/linux/flutter_linux_${FLUTTER_VERSION}-stable.tar.xz"; \
    tar -xJf /tmp/flutter.tar.xz -C /opt; \
    rm /tmp/flutter.tar.xz; \
    # Flutter writes its version stamp and pub cache inside its own tree, so it
    # has to be writable by the user that runs it, not just readable.
    chown -R "${UID}:${GID}" "$FLUTTER_HOME"
ENV PATH="$FLUTTER_HOME/bin:$PATH"

USER gremlin

# Warmed as the final user so the caches land with the right ownership. Also
# fails the build early if the toolchain is broken, rather than at first use.
RUN flutter config --no-analytics >/dev/null \
    && flutter config --android-sdk "$ANDROID_HOME" >/dev/null \
    && flutter precache --android --no-ios --no-linux --no-web >/dev/null
WORKDIR /workspace

# Keeps the Claude Code login on a named volume, so authenticating once
# survives every later rebuild of this image.
ENV CLAUDE_CONFIG_DIR=/home/gremlin/.claude

# Mount points for the two host directories compose binds here. Created as the
# unprivileged user so they are writable even when nothing is mounted over them
# — a container run without those binds still gets a usable, if ephemeral, home
# rather than a `claude` that cannot save its token.
RUN mkdir -p /home/gremlin/.claude /home/gremlin/.gitstate

CMD ["bash"]
