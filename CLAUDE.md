# Gremlin

An autonomous UI-testing agent for Android apps. It explores a running app on a
device or emulator, decides what to tap from a screenshot, detects defects, and
escalates through a three-tier remediation ladder — T0 report, T1 deterministic
retry, T2 model-authored fix behind guard/rebuild/replay gates.

## Where this runs — read this before running anything

This project is developed **inside Docker on a shared university lab
workstation**. The host machine is not ours. Other people's work is running on
it right now.

### Hard rules

1. **Never stop, restart, remove, or exec into a container this project did not
   create.** At time of writing the host also runs `karunya-openmaic-*` (app,
   postgres, tts, redis, minio, image) and `scoratis-*` (ollama, postgres,
   redis, frontend). Some of them look unhealthy or are crash-looping. That is
   not our problem to fix and not our container to touch.

2. **Only ever act through the project's own compose file**, which is scoped to
   the compose project `gremlin`:

   ```
   docker compose <command>
   ```

   Bare `docker stop`, `docker rm`, or `docker kill` are not scoped to this
   project. Do not use them.

3. **Never run any prune.** `docker system prune`, `docker container prune`,
   `docker image prune`, `docker volume prune` — all of these delete other
   people's data. There is no situation in this project that requires one.

4. **There is no sudo.** The account is unprivileged by design. Do not propose
   installing anything on the host, editing host config, or `apt`/`dnf`
   anything. Everything the project needs belongs in `docker/Dockerfile`.

5. **The GPU is shared.** An RTX 5090 (32 GB) serves this project and a
   neighbouring Ollama service. Do not raise `VLLM_GPU_FRAC`, do not remove
   `OLLAMA_KEEP_ALIVE`, and check `nvidia-smi` before starting anything that
   claims VRAM. Leaving the card free when idle is a requirement, not a
   nicety.

6. **Do not write credentials into volumes or the repo.** Every member of the
   host's `docker` group can read any Docker volume on it, and that group is
   not just us. Tokens should be short-lived, repo-scoped, and entered when
   prompted.

If a task seems to require breaking one of these, stop and say so rather than
finding a way around it.

## Model backend

`LLM_PROVIDER` selects the vision backend: `gemini`, `groq`, or `local`. In the
lab it is `local`, pointing at the Ollama service over the compose network:

```
LOCAL_BASE_URL=http://ollama:11434/v1
LOCAL_MODEL=qwen3-vl:32b
```

Both local backends speak the OpenAI chat-completions shape, so swapping
between them is configuration, never code.

Tier-2 fixes shell out to `claude -p` via `gremlin/llm.py`, so the Claude Code
CLI must be installed and logged in inside the container. It is, and the login
lives on a named volume.

## Conventions

- Backends normalise their own errors to `vision.ModelError` /
  `ModelQuotaError` so the explorer can end a run gracefully.
- Never commit `.env`, run artifacts under `runs/`, or anything under
  `.claude/`.
