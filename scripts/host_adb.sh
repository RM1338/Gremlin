#!/usr/bin/env bash
# Share the host's adb server with the container over a Unix socket.
#
# Run this ON THE HOST, not inside the container.
#
#   bash scripts/host_adb.sh start    # start the shared server
#   bash scripts/host_adb.sh status   # what it can see
#   bash scripts/host_adb.sh stop     # shut it down
#
# Why this exists
# ---------------
# A USB phone belongs to the host: handing a container the USB bus needs
# `--device`, which is root-adjacent and is exactly the call a managed host's
# authorization plugin refuses. The way round it is not to move the bus at all
# — the host keeps the phone, runs the adb *server*, and the container runs
# only an adb *client* that talks to it.
#
# The obvious way to connect the two is TCP, and it is the wrong one. `adb
# start-server` binds 127.0.0.1:5037, which a container cannot reach, and the
# only documented way to widen that is `adb -a`, which binds 0.0.0.0 — on a
# shared lab machine that hands every other person on the network a debugging
# channel into the phone. Binding to just the Docker bridge would be the middle
# ground, but adb rejects it:
#
#   $ adb -L tcp:172.17.0.1:5037 nodaemon server
#   could not install *smartsocket* listener: listening on specified
#   hostname currently unsupported
#
# So TCP is all-or-nothing. A Unix socket avoids the choice entirely: it is a
# file, it is shared by bind-mounting its directory, it is reachable by nobody
# who cannot already read that directory, and it touches no network interface.
# The container gets the phone; the lab does not.
#
# The same socket also serves an emulator started on the host — see the
# "emulator on the host" section of docs/LAB_SETUP.md. That is the way to get a
# hardware-accelerated emulator on a host whose Docker refuses /dev/kvm: the
# policy governs the Docker API, not what you may run in your own session.

set -uo pipefail

# Lives beside the other host-side state this project keeps (Claude Code's
# login, the git identity), all under one directory that is yours and is not
# a Docker volume — volumes on this host are readable by everyone in the
# `docker` group.
ADB_DIR=${GREMLIN_ADB_DIR:-$HOME/.gremlin/adb}
SOCK="$ADB_DIR/adb.sock"
LOG="$ADB_DIR/server.log"
PIDFILE="$ADB_DIR/server.pid"

# Every adb command here is scoped to our own socket. Without this they would
# fall back to 127.0.0.1:5037 — the default server, which on a shared machine
# may be somebody else's.
export ADB_SERVER_SOCKET="localfilesystem:$SOCK"

have_adb() {
  if ! command -v adb >/dev/null 2>&1; then
    echo "adb is not installed on this host." >&2
    echo "It is the one piece that must live outside the container, because" >&2
    echo "the USB bus does. Without root, unpack Google's platform-tools into" >&2
    echo "your home directory and put it on PATH:" >&2
    echo >&2
    echo "  curl -fsSLO https://dl.google.com/android/repository/platform-tools-latest-linux.zip" >&2
    echo "  unzip -q platform-tools-latest-linux.zip -d \"\$HOME\"" >&2
    echo "  export PATH=\"\$HOME/platform-tools:\$PATH\"" >&2
    return 1
  fi
  return 0
}

running() {
  # The pidfile alone is not evidence — it outlives a crash. The pid has to
  # still be a live process we own.
  [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE" 2>/dev/null)" 2>/dev/null
}

start() {
  have_adb || exit 1

  if running; then
    echo "Already running (pid $(cat "$PIDFILE")), socket: $SOCK"
    status
    return 0
  fi

  # 0700: the socket's access control is the directory's. Anyone who can read
  # this path can drive the phone, so it is deliberately yours alone.
  mkdir -p "$ADB_DIR"
  chmod 700 "$ADB_DIR"

  # A socket file left behind by a killed server makes bind() fail with
  # "address already in use" even though nothing is listening.
  [ -S "$SOCK" ] && ! running && rm -f "$SOCK"

  echo "Starting adb server on $SOCK ..."
  # nodaemon, because the point is a server we can see and stop by pid; adb's
  # own daemonising would detach it from this pidfile.
  nohup adb -L "localfilesystem:$SOCK" nodaemon server >"$LOG" 2>&1 &
  echo $! >"$PIDFILE"

  # The socket appears slightly after the process does; polling beats a fixed
  # sleep that is either too short on a loaded machine or wasted on an idle one.
  for _ in $(seq 1 20); do
    [ -S "$SOCK" ] && break
    sleep 0.25
  done

  if ! [ -S "$SOCK" ]; then
    echo "Server did not create its socket. Log:" >&2
    sed 's/^/   /' "$LOG" >&2
    rm -f "$PIDFILE"
    exit 1
  fi

  echo "Started (pid $(cat "$PIDFILE"))."
  echo
  status
  cat <<EOF

Now tell the container to use it. Add BOTH of these to .env:

   GREMLIN_ADB_DIR=$ADB_DIR
   ADB_SERVER_SOCKET=localfilesystem:/run/adb/adb.sock

The first mounts this directory into the container; the second points the adb
client inside it at the socket. Then start the shell as usual:

   docker compose run --rm gremlin

Inside the container, \`adb devices\` should list exactly what it lists here.

Set ADB_SERVER_SOCKET only while this server is running. adb will not start a
server on a Unix socket by itself — with the variable set and nothing
listening, every adb command fails rather than falling back. Comment it out
again when you go back to wireless debugging.
EOF
}

status() {
  have_adb || exit 1
  if ! [ -S "$SOCK" ]; then
    echo "No shared adb server. Start one with: bash $0 start"
    return 0
  fi
  echo "Devices visible on $SOCK:"
  adb devices -l | sed 's/^/   /'
  cat <<'EOF'

If a phone is plugged in but shows as `unauthorized`, accept the "Allow USB
debugging?" prompt on its screen. If it does not appear at all, the phone is
not in the host's udev rules — check `lsusb` sees it, and that USB debugging
is on and the cable carries data rather than only power.
EOF
}

stop() {
  if running; then
    kill "$(cat "$PIDFILE")" 2>/dev/null
    echo "Stopped (pid $(cat "$PIDFILE"))."
  else
    echo "Not running."
  fi
  rm -f "$PIDFILE" "$SOCK"
}

case "${1:-start}" in
  start)  start ;;
  status) status ;;
  stop)   stop ;;
  *)
    echo "usage: bash $0 {start|status|stop}" >&2
    exit 2
    ;;
esac
