# The device problem, and what would fix it

Written to be read aloud to a supervisor or forwarded to whoever administers
the workstation. No prior knowledge of the project assumed.

---

## What the project needs

Gremlin tests Android apps by actually driving them: it launches the app, looks
at the screen, decides what to tap, taps it, and watches what breaks. So a run
needs a real Android system to drive. There are only two kinds:

1. **An emulator** — a virtual Android phone running on the workstation.
2. **A physical phone** — connected by USB cable, or over the network.

Everything else in the project already runs inside Docker on the lab
workstation, with no software installed on the host and no administrator
rights used. The model, the engine, the toolchain, and the console are all
containerised and working. **The device is the one remaining piece.**

## Why the emulator does not currently work

An Android emulator is a virtual machine. To run at usable speed it needs the
CPU's hardware virtualisation support, which Linux exposes as a single special
file, `/dev/kvm`. Without it the emulator has to simulate the CPU in software,
which is roughly ten to twenty times slower — the phone takes many minutes just
to boot, and a test run times out before it does anything useful.

That file exists on the workstation and the account can read and write it. The
problem is narrower: **a Docker container cannot see any host device unless the
container is explicitly told to map it in**, using `--device`. And on this
machine, the Docker daemon runs an authorisation plugin
(`openpolicyagent/opa-docker-authz-v2`) which refuses that option:

```
$ docker run --rm --device /dev/kvm alpine true
Error response from daemon: authorization denied by plugin
openpolicyagent/opa-docker-authz-v2:0.9: request rejected by administrative policy
```

This is an administrative decision, correctly enforced. It is not something the
project can or should work around, and no amount of configuration inside the
container changes it.

## What is being asked for

**Permission for this account to map one device, `/dev/kvm`, into its own
containers.** In Docker terms, allowing `--device /dev/kvm` in the
authorisation policy.

What this is *not*:

- **Not** `--privileged`. Privileged mode disables essentially all container
  isolation. This request is the opposite: one specific device, nothing else.
- **Not** root, sudo, or any change to the account's host permissions.
- **Not** access to the host filesystem, other containers, or other users'
  data. `/dev/kvm` is the kernel's interface for creating virtual machines; it
  grants nothing beyond that.
- **Not** a change to the account's group membership. The account can already
  use `/dev/kvm` directly. The restriction is purely at the Docker API layer.

Adding the account to the `kvm` group would *not* help, because the request is
blocked before it reaches the kernel.

## If that cannot be granted

Two fallbacks, both worse:

**A physical phone over USB.** Reaching a USB device from inside a container
needs the same `--device` permission that is blocked, so the phone cannot be
reached from the container directly. The workaround is to run Android's `adb`
tool *on the host* and have the container talk to it over a local network port.
`adb` is a single self-contained binary that unpacks into a home directory and
needs no root — but it does mean one small process running outside Docker,
which is a departure from the "everything in a container" instruction. **This
is the thing to ask about**: whether that one exception is acceptable.

**A physical phone over wifi.** Android supports debugging over the network
with no cable and no special Docker permissions at all — this would need
nothing granted. But the workstation is on ethernet and the phone would be on
wifi, so it only works if those two networks route to each other. Frequently
they do not.

## Suggested message

> I'm running my final-year project on the lab workstation, fully inside Docker
> as instructed — nothing is installed on the host and I'm not using sudo.
>
> One piece doesn't work: the project has to drive an Android app, and the
> Android emulator needs hardware virtualisation, `/dev/kvm`. My account can
> use that file directly, but the Docker authorisation policy refuses to map it
> into a container:
>
>     docker run --rm --device /dev/kvm alpine true
>     -> authorization denied by plugin openpolicyagent/opa-docker-authz-v2
>
> Would it be possible to allow `--device /dev/kvm` for my account? To be
> clear about the scope: this is not `--privileged` and not root — it is one
> device mapping, and `/dev/kvm` grants nothing beyond creating virtual
> machines. Without it the emulator falls back to software emulation and is too
> slow to finish a run.
>
> If that isn't possible, the alternative is a physical phone, which would need
> me to run Android's `adb` tool on the host (no root, unpacks into my home
> directory) so the container can reach it over a local port. I'd rather ask
> than do that unannounced, since it means one process outside Docker.
>
> Happy to explain the project or show what's running.
