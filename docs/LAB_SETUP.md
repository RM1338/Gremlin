# Running Gremlin in the lab, inside Docker

Written for a workstation where you have a normal user account, a working
Docker, and **no sudo**. Nothing here installs anything on the host or writes
outside your home directory and Docker's own volumes.

The layout is two containers. `vllm` owns the GPU and serves the vision model
over an OpenAI-compatible API; `gremlin` is the shell you work in, holding
Python, Node, adb and the Claude Code CLI. They meet at `http://vllm:8000/v1`.
That single URL is the entire integration — which is what makes the migration
in Objective 2 of `PROPOSAL.md` a configuration change rather than a rewrite.

---

## 0. Check the machine first

```bash
git clone https://github.com/RM1338/Gremlin.git
cd Gremlin
bash scripts/lab_probe.sh
```

### If the machine has no git

Docker is enough on its own — git can run as a container:

```bash
docker run --rm -u "$(id -u):$(id -g)" -v "$PWD":/w -w /w \
  alpine/git clone https://github.com/RM1338/Gremlin.git
cd Gremlin
```

Keep the `-u` flag. Without it the container runs as root and the cloned files
land root-owned in your home directory, where without sudo you can neither edit
nor delete them.

The same trick covers later git work — `alpine/git pull`, `... log`, and so on
with the identical flags. Simpler, though, is to just use the git already
inside the `gremlin` container once you are in a shell there.

Read the output before going further. Three lines decide everything:

| Probe line | If it fails |
|---|---|
| `daemon reachable` | Your account cannot use Docker at all. Ask the admin for the `docker` group. |
| `nvidia runtime is registered` | **The only thing here that needs root.** Without `nvidia-container-toolkit` on the host, no container can see the GPU. Ask your professor to install it — it is a package install, not a config change to your account. |
| `NN GB free under the Docker root` | Model weights land here, not in `$HOME`. An 8B needs ~20 GB, a 32B needs ~70 GB before quantisation. |

`/dev/kvm` failing is not a blocker for the model work — it only affects
running the Android emulator inside the container. See "Devices" below.

## 1. Configure

```bash
cp .env.example .env
echo "LLM_PROVIDER=local" >> .env
printf 'UID=%s\nGID=%s\n' "$(id -u)" "$(id -g)" >> .env
```

The `UID`/`GID` lines make files the container writes into the repo come out
owned by you instead of by root.

## 2. Start the model

```bash
docker compose -f docker/compose.yml up -d vllm
docker compose -f docker/compose.yml logs -f vllm
```

The first start downloads the weights and can take a long while — tens of GB,
then several minutes of loading. Wait for `Application startup complete`, then
`Ctrl-C` out of the logs (that stops following them, not the server).

Confirm it is really answering:

```bash
curl -s localhost:8000/v1/models | python3 -m json.tool
```

You want to see `gremlin-vision` — the stable alias the compose file serves the
checkpoint under, so changing checkpoints later never touches Gremlin's config.

## 3. Get a shell and authenticate Claude Code

```bash
docker compose -f docker/compose.yml run --rm gremlin
```

You are now inside the container, in `/workspace`. Log in once:

```bash
claude
```

Follow the browser flow. The login is stored on a named volume, so it survives
rebuilding the image — you will not have to repeat this.

Claude Code is not just your interface here: `gremlin/llm.py:31` shells out to
`claude -p` to apply Tier-2 fixes, so the run itself fails without this login.

## 4. Run it

```bash
python run.py            # engine
python -m gremlin.dashboard   # console, then open http://localhost:8080
```

---

## Choosing the checkpoint

The default is `Qwen/Qwen3-VL-8B-Instruct`. Start there — it gets the whole
pipeline green in one afternoon, and swapping is one line in `.env`.

**What fits on 32 GB.** The card holds the weights *plus* the KV cache, the
activations, and the vision encoder's image tokens, so usable capacity is well
under the nominal 32 GB:

| Checkpoint | Weights | On a 32 GB card |
|---|---|---|
| Qwen3-VL-8B, FP16 | ~16 GB | comfortable, long context |
| Qwen3-VL-32B, 4-bit AWQ/GPTQ | ~19 GB | fits, ~10 GB left for context |
| Qwen3-VL-32B, 8-bit | ~32 GB | no headroom — fails to allocate |
| Qwen3-VL-32B, FP16 | ~64 GB | does not fit |

So the 32B is a **4-bit deployment** here. That is not a limitation of the
setup — it is just what the arithmetic allows, and 4-bit Qwen3-VL is a strong
model. If a checkpoint does not fit you will know at once: vLLM fails during
load with a CUDA out-of-memory error rather than starting and misbehaving.

To move up once the 8B works:

```bash
# in .env
VLLM_MODEL=Qwen/Qwen3-VL-32B-Instruct-AWQ
VLLM_MAX_LEN=8192
```

then `docker compose -f docker/compose.yml up -d --force-recreate vllm`.

Pin the image tag in `.env` (`VLLM_IMAGE=vllm/vllm-openai:X.Y.Z`) once you have
a working combination. Benchmark numbers against a floating `latest` are not
reproducible, which is half the point of hosting the model yourself.

## Devices

The container reaches a **USB-attached phone** through an adb server on the
host — run `adb start-server` on the host once, and the `ADB_SERVER_SOCKET`
setting in the compose file does the rest. This keeps the USB bus out of the
container, which matters because handing a container USB access needs root.

Running the **emulator inside the container** additionally needs `/dev/kvm`
passed through and your user in the `kvm` group. If the probe flagged that,
treat it as a second, separate ask to the admin — the model work does not
depend on it.

## Blackwell notes

The RTX 5090 is `sm_120` and needs a 570+ driver with a CUDA 12.8+ runtime.
This is why `docker/compose.yml` floats `vllm/vllm-openai:latest` rather than
pinning: older vLLM images predate both Blackwell kernels and the Qwen3-VL
architecture, and fail with either "no kernel image is available for execution"
or an unrecognised model type.
