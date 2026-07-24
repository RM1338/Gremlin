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

### Sharing the workstation

Nothing in this setup stops, removes, or restarts anyone else's containers.
`docker run --rm` removes only the throwaway container that command creates,
and `docker compose ... down` acts only on this project (`name: gremlin` in the
compose file), never on containers it did not start.

The way to disturb someone here is not containers, it is **VRAM**. The compose
file asks for 90% of the card, so if another user's job is already on the GPU,
starting `vllm` will disrupt it. The probe reports this under "GPU on the
host". If it says the GPU is already in use, either wait, or take a small
share and tell whoever owns the job:

```bash
# in .env
VLLM_MODEL=Qwen/Qwen3-VL-8B-Instruct
VLLM_GPU_FRAC=0.35
```

A port clash (8000, 8080, 5173) is harmless by comparison — compose fails to
start and nothing else is affected. Change `VLLM_PORT`, `CONSOLE_PORT` or
`VITE_PORT` in `.env` if the probe flags one.

## 1. Configure

```bash
cp .env.example .env
echo "LLM_PROVIDER=local" >> .env
printf 'UID=%s\nGID=%s\n' "$(id -u)" "$(id -g)" >> .env
```

The `UID`/`GID` lines make files the container writes into the repo come out
owned by you instead of by root.

## 2. Start the model

Two backends are available and they serve the same API, so `gremlin/local.py`
talks to either without a code change. Pick by what the host driver allows.

**Ollama — start here.** It ships CUDA 12 builds, so it runs on drivers that
current vLLM images have moved past, and its GGUF weights are a fraction of
the size. Slower per request, which matters for published benchmark numbers
but not for getting the pipeline working:

```bash
docker compose up -d ollama
docker compose exec ollama ollama pull qwen2.5vl:7b
# then in .env:
#   LOCAL_BASE_URL=http://ollama:11434/v1
#   LOCAL_MODEL=qwen2.5vl:7b
```

**vLLM — faster, and the right target for benchmarking.** It is fussier about
the driver: the `latest` image now requires CUDA 13, which needs a 580+ driver.
On an older driver, pin a CUDA-12 build with `VLLM_IMAGE` in `.env`. If an
image asks for a CUDA *minor* version slightly above the driver, set
`NVIDIA_DISABLE_REQUIRE=1` — CUDA is minor-version compatible. That will not
rescue a CUDA 13 image on a 12.x driver.

Check what the driver supports with `nvidia-smi` (top right).

### vLLM specifically

```bash
docker compose up -d vllm
docker compose logs -f vllm
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
docker compose run --rm gremlin
```

You are now inside the container, in `/workspace`. Log in once:

```bash
claude
```

Follow the browser flow. The login is stored under your home directory on the
workstation, so it survives rebuilding the image — you will not have to repeat
this.

Claude Code is not just your interface here: `gremlin/llm.py:31` shells out to
`claude -p` to apply Tier-2 fixes, so the run itself fails without this login.

There is no browser inside the container, so `claude` prints a URL and waits for
you to paste the code back. Open the URL in the workstation's own browser; do
not expect the localhost callback to find its way in.

Claude Code's state lives in `~/.gremlin/claude` on the workstation, so create
that before the first shell:

```bash
mkdir -p ~/.gremlin/claude ~/.gremlin/gitstate && chmod 700 ~/.gremlin
```

**If the login will not stick** — `/login` reappears, or the session warns that
transcript writes are failing with `EACCES` — the directory behind
`/home/gremlin/.claude` is not writable by the container's user. Check both
halves from inside the container:

```bash
id -u; ls -ld /home/gremlin/.claude
```

The owner shown there must match that uid. It will not if the mount is still a
named volume: Docker creates a volume's mount point root-owned when the path is
absent from the image, and nothing unprivileged can write into it afterwards.
The host directories above avoid that, because your own account creates them.

Note that the container's uid comes from the `UID`/`GID` build args and is baked
in at build time, so changing it means `docker compose build gremlin`, not just
a new `run`.

## 4. Run it

Steps 1-3 above are what `scripts/gremlin.sh` automates, so once you have read
them you never need to do them by hand again:

```bash
bash scripts/gremlin.sh              # a connected phone if there is one,
                                     # otherwise an emulator
bash scripts/gremlin.sh --emulator   # force the emulator
bash scripts/gremlin.sh --usb        # force a USB phone via the host bridge
bash scripts/gremlin.sh doctor       # check the machine, change nothing
```

It creates the `~/.gremlin` directories, writes `.env` if absent, starts Ollama
and waits for it, pulls the model named in `.env` if it is missing, builds the
image, picks a device, runs the exploration and prints where the reports
landed. It is idempotent — running it twice does the work once. Flags it does
not recognise go to `run.py`, so `bash scripts/gremlin.sh --emulator --steps 40`
does what you would expect.

Every Docker call it makes goes through `docker compose`, which the `name:`
field scopes to this project. It never stops, removes or prunes anything it did
not create, and it needs no sudo.

By hand, inside a container shell, the same thing is:

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

then `docker compose up -d --force-recreate vllm`.

Pin the image tag in `.env` (`VLLM_IMAGE=vllm/vllm-openai:X.Y.Z`) once you have
a working combination. Benchmark numbers against a floating `latest` are not
reproducible, which is half the point of hosting the model yourself.

## Pushing your work

`~/Gremlin` on the host and `/workspace` in the container are the same
directory, so it does not matter which side you commit from.

**From the host**, if it has git, there is nothing to configure — use it as
normal.

**From inside the container**, set your identity once. It persists, because
`GIT_CONFIG_GLOBAL` points at the `git-state` volume rather than at a path
that dies with the container:

```bash
git config --global user.name  "Your Name"
git config --global user.email "you@example.com"
git push        # prompts for username + token
```

For the password, GitHub wants a **personal access token**, not your account
password: https://github.com/settings/tokens — a fine-grained token, scoped to
this one repository, with Contents: read and write, and a short expiry.

### Do not store that token on a shared machine

Git can cache credentials so you stop being prompted. On a workstation you
share, think before you do:

> Anyone in the `docker` group can read any Docker volume, and on this machine
> that group is not just you. A token written into a volume — or into
> `~/.git-credentials` — is readable by every other person with Docker access.

So prefer being prompted, and keep the token short-lived and scoped to this
repository. If the typing genuinely gets in the way, cache it in memory for a
session only, which never writes it to disk:

```bash
git config --global credential.helper 'cache --timeout=3600'
```

Avoid `credential.helper store`, which writes the token to disk in plain text.
If a token is ever exposed, revoke it at the same settings page — revoking and
reissuing costs a minute.

## Devices

### When the host forbids /dev/kvm

An emulator needs `/dev/kvm`, and mapping a device into a container is a
privilege managed hosts often refuse — on `knuth` an `opa-docker-authz` policy
rejects `--device` outright. Nothing in the container can work around that, and
it should not try to.

Use a real phone over **wireless adb** instead. It needs no device mapping and
no USB, so there is nothing for a policy to object to — and testing on real
hardware is a stronger result than an emulator anyway.

On the phone: Settings → Developer options → **Wireless debugging**. Then,
inside the container:

```bash
# First time only — the pairing dialog shows its own port and a 6-digit code.
bash scripts/connect_phone.sh 10.1.2.3:41234 123456

# Every time after — note this is the port on the main Wireless debugging
# screen, which is NOT the pairing port.
bash scripts/connect_phone.sh 10.1.2.3:37000
```

Two ports are involved and confusing them is the usual reason a first attempt
fails. The pairing port and code change every time that dialog is opened; the
connect port is stable while wireless debugging stays on.

The phone must be reachable from the container — same network, and client
isolation off. On a locked-down campus wifi that may not hold.

### Software emulation, when there is no phone either

A dockerised Android emulator does **not** get around this. `budtmo/docker-android`,
Google's `android-emulator-container-scripts` and the rest all ask for
`--device /dev/kvm`, which is the exact call the policy refuses; the rejection
is per-account at the Docker API, so a different image changes nothing.

budtmo's own quick start says so outright — note the flag:

```
docker run -d -p 6080:6080 -e EMULATOR_DEVICE="Samsung Galaxy S10" \
  -e WEB_VNC=true --device /dev/kvm --name android-container \
  budtmo/docker-android:emulator_11.0
```

It is also worth being clear that these images are not a different kind of
virtualisation. Underneath the noVNC view and the Appium wrapper is the same
AOSP emulator, the same QEMU and the same adb that `python run.py --emulator`
drives directly — so they inherit every constraint the plain emulator has, and
add several GB of image to the Docker root plus a supervisord/VNC/Appium stack
between Gremlin and the adb serial it wants to control. Forcing software
emulation inside one gains nothing over the `-accel off` fallback below.

**Retest the door before working around it.** The refusal above is recorded
from experience on `knuth`, not a law of the machine, and one command settles
it on any host:

```bash
docker run --rm --device /dev/kvm alpine ls -l /dev/kvm
```

If that prints the device node, `--device` is permitted: use
`docker/compose.emulator.yml` and skip everything below. A policy rejection is
unmistakable — an authorization-plugin error from the daemon, not a
permission error from the shell.

**Redroid is the one that looks like an exception, and is not.** It runs Android
on the host kernel rather than emulating a machine, so it genuinely needs no
KVM — but that is the trade, not a free lunch: the host kernel must supply
Android's IPC, and Ubuntu ships it as a module that is not loaded.

```
$ grep BINDER /boot/config-$(uname -r)
CONFIG_ANDROID_BINDER_IPC=m
CONFIG_ANDROID_BINDERFS=m
$ lsmod | grep binder        # nothing
$ grep binder /proc/filesystems   # binderfs not registered
```

Getting from there to a running Redroid needs `modprobe binder_linux` — root on
the host, which no container flag substitutes for — and then `--privileged`,
which is a far wider request than the single `--device` already refused. So it
is strictly worse than KVM here, not better. Redroid is an excellent option on
a machine where you have root; it is a dead end on this one.

What does work without any permission is dropping acceleration entirely. QEMU
then emulates the guest CPU instruction by instruction, which is unusable by
hand but tolerable here, because Gremlin waits seconds on a vision-model call
between one tap and the next — the emulator is idle for most of a run.

`Emulator.start` detects this and adds `-accel off` on its own when `/dev/kvm`
is unreadable, so `python run.py --emulator --headless` needs no extra flag.
Budget 20-30 minutes for the cold boot, and raise
`GREMLIN_SOFTWARE_BOOT_TIMEOUT` (seconds, default 1800) if that is not enough.
Leave the emulator up afterwards and later runs adopt it rather than re-booting.

Treat this as a fallback for when no phone is reachable, not as the benchmark
configuration — timings taken this way say more about QEMU than about Gremlin.
The clean fix remains asking an admin to permit `--device /dev/kvm` for your
account, a narrow request that is not privileged mode and grants no host access
beyond the KVM interface. See `docs/ADMIN_REQUEST.md`.

### USB

The container reaches a **USB-attached phone** through an adb server on the
host. The USB bus never enters the container, which is the point: handing a
container USB access needs `--device`, the same call the policy refuses.

```bash
# On the HOST, with the phone plugged in and USB debugging on:
bash scripts/host_adb.sh start
```

That starts an adb server listening on a Unix socket at `~/.gremlin/adb/adb.sock`.
Then add both lines to `.env` and start the shell as usual:

```bash
GREMLIN_ADB_DIR=/home/you/.gremlin/adb
ADB_SERVER_SOCKET=localfilesystem:/run/adb/adb.sock
```

Inside the container, `adb devices` now lists exactly what the host lists.

**Why a socket and not TCP.** An earlier version of this document said to run
`adb start-server` and point the container at `tcp:host.docker.internal:5037`.
That cannot work: the server binds `127.0.0.1`, which no container can reach.
Nor can it be narrowed to the Docker bridge —

```
$ adb -L tcp:172.17.0.1:5037 nodaemon server
could not install *smartsocket* listener: listening on specified hostname
currently unsupported
```

— so the only TCP server a container can reach is `adb -a`, binding `0.0.0.0`.
On a shared lab machine that offers everyone on the network an unauthenticated
debugging channel into your phone: install packages, read app data, pull files.
A Unix socket has none of that exposure, is guarded by ordinary directory
permissions, and needs no privilege to set up.

**Unset `ADB_SERVER_SOCKET` when you are not using the bridge.** adb will not
start a server on a Unix socket by itself — it tries and fails with `could not
install *smartsocket* listener` — so leaving the variable set with no server
running breaks every adb command instead of falling back to a local one.

### The emulator on the host

Worth checking before settling for software emulation, because it is the only
option here that is both accelerated and needs nothing from the admin.

The policy that refuses `--device /dev/kvm` governs the **Docker API**. It says
nothing about what you may run in your own shell. So if your account can read
`/dev/kvm` on the host directly:

```bash
ls -l /dev/kvm                 # and check for an ACL: getfacl /dev/kvm
python3 -c "import os; print(os.access('/dev/kvm', os.R_OK|os.W_OK))"
```

then run the emulator natively on the host at full speed and let the container
drive it through the socket bridge above — the emulator is just another adb
serial, so nothing above `gremlin/device.py` can tell the difference.

The host needs the SDK, which installs without root — it is a zip:

```bash
curl -fsSLO https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip
unzip -q commandlinetools-linux-11076708_latest.zip -d "$HOME/android-sdk"
export ANDROID_HOME="$HOME/android-sdk"
"$ANDROID_HOME/cmdline-tools/bin/sdkmanager" --sdk_root="$ANDROID_HOME" \
    platform-tools emulator "system-images;android-34;google_apis;x86_64"
"$ANDROID_HOME/cmdline-tools/bin/avdmanager" --clear-cache create avd -n gremlin \
    -k "system-images;android-34;google_apis;x86_64" --device pixel_6
```

Then, on the host:

```bash
"$ANDROID_HOME/emulator/emulator" -avd gremlin -no-window -no-audio &
bash scripts/host_adb.sh start     # the emulator registers with this server
```

and inside the container `python run.py --serial emulator-5554`. Do **not**
pass `--emulator`; that asks Gremlin to boot one itself, inside the container,
where there is no `/dev/kvm`.

Note this needs disk under `$HOME`, not under the Docker root — a system image
plus AVD is roughly 10-15 GB.

## Blackwell notes

The RTX 5090 is `sm_120` and needs a 570+ driver with a CUDA 12.8+ runtime.
This is why `compose.yml` floats `vllm/vllm-openai:latest` rather than
pinning: older vLLM images predate both Blackwell kernels and the Qwen3-VL
architecture, and fail with either "no kernel image is available for execution"
or an unrecognised model type.
