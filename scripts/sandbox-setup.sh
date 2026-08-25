#!/bin/sh
# Make this machine able to run the Gremlin sandbox, once, for good.
#
# The sandbox is redroid: Android's userspace on your kernel. That needs binder,
# the kernel's IPC driver, to actually expose device nodes — and on a stock
# Ubuntu/Debian kernel it does not, because the distro ships
# CONFIG_ANDROID_BINDER_DEVICES="". So `modprobe binder_linux` on its own looks
# like it worked and leaves nothing behind.
#
# Run as root (the console runs it through pkexec, which asks for your password
# in a normal desktop dialog):
#
#     sudo scripts/sandbox-setup.sh
#
# Idempotent: safe to run again. It says what it changed and changes nothing else.
set -eu

[ "$(id -u)" = 0 ] || { echo "must run as root: sudo $0" >&2; exit 1; }

DEVICES="binder,hwbinder,vndbinder"
changed=0
note() { echo "  $*"; }

echo "Gremlin sandbox setup"

# --- 1. binder devices, right now -------------------------------------------
if [ -e /dev/binder ] || [ -e /dev/binderfs/binder-control ]; then
  note "binder: already usable"
else
  # Load with the parameter if the module is not in yet. If it is already
  # loaded without devices, this is a no-op — Ubuntu marks binder_linux
  # [permanent], so it cannot be unloaded to be re-parameterised before a
  # reboot. binderfs asks nothing of the module and works either way, which is
  # why it is the fallback and not the first choice.
  modprobe binder_linux devices="$DEVICES" 2>/dev/null || true
  if [ ! -e /dev/binder ]; then
    mkdir -p /dev/binderfs
    if mount -t binder binder /dev/binderfs 2>/dev/null; then
      note "binder: mounted binderfs at /dev/binderfs"
    else
      echo "  binder: FAILED — no /dev/binder and binderfs would not mount." >&2
      echo "  This kernel may lack binder entirely (CONFIG_ANDROID_BINDER_IPC=n)." >&2
      echo "  Use a phone or an emulator instead; see the Setup page." >&2
      exit 2
    fi
  else
    note "binder: loaded binder_linux with devices=$DEVICES"
  fi
  changed=1
fi

# --- 2. and after the next reboot -------------------------------------------
# Without this the whole thing evaporates on reboot and the user is back here
# having forgotten the command. Persistence is the actual point of this script.
if [ ! -f /etc/modules-load.d/gremlin-binder.conf ]; then
  echo "binder_linux" > /etc/modules-load.d/gremlin-binder.conf
  note "boot: /etc/modules-load.d/gremlin-binder.conf (load the module)"
  changed=1
fi
if [ ! -f /etc/modprobe.d/gremlin-binder.conf ]; then
  echo "options binder_linux devices=$DEVICES" > /etc/modprobe.d/gremlin-binder.conf
  note "boot: /etc/modprobe.d/gremlin-binder.conf (with device nodes)"
  changed=1
fi
if ! grep -q "^binder[[:space:]]\+/dev/binderfs" /etc/fstab 2>/dev/null; then
  # nofail: a kernel without binder must not drop the machine to an emergency
  # shell over an optional testing tool.
  echo "binder /dev/binderfs binder nofail 0 0" >> /etc/fstab
  note "boot: /etc/fstab entry for binderfs (nofail)"
  changed=1
fi

# --- 3. docker, which the container needs -----------------------------------
if ! command -v docker >/dev/null 2>&1; then
  echo "  docker: NOT INSTALLED — install Docker Engine, then run this again." >&2
  echo "  https://docs.docker.com/engine/install/" >&2
  exit 3
fi
if ! docker info >/dev/null 2>&1; then
  if command -v systemctl >/dev/null 2>&1; then
    systemctl enable --now docker >/dev/null 2>&1 || true
    note "docker: started and enabled at boot"
    changed=1
  fi
fi
docker info >/dev/null 2>&1 || { echo "  docker: daemon still not reachable." >&2; exit 4; }
note "docker: ready"

[ "$changed" = 1 ] && echo "Done — the sandbox can start now." \
                   || echo "Nothing to do — already set up."
