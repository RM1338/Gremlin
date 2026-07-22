#!/usr/bin/env bash
# Attach a physical Android phone to the container over the network.
#
# Run this INSIDE the dev container. Wireless debugging needs no USB and no
# device mapping, which matters on a managed host that forbids both — it is
# ordinary TCP, so nothing has to be granted.
#
#   bash scripts/connect_phone.sh                 # show what is connected
#   bash scripts/connect_phone.sh 10.1.2.3:37000  # connect
#   bash scripts/connect_phone.sh 10.1.2.3:41234 123456   # pair first, then connect
#
# On the phone: Settings > Developer options > Wireless debugging. "Pair device
# with pairing code" shows a *pairing* port and code, used once. The main
# screen shows a different, longer-lived *connect* port. They are not the same
# port, which is the usual reason a first attempt fails.

set -uo pipefail

target=${1:-}
code=${2:-}

if [ -z "$target" ]; then
  echo "Currently visible to adb:"
  adb devices -l | sed 's/^/   /'
  echo
  echo "To attach a phone, enable Wireless debugging on it, then:"
  echo "   bash $0 <ip>:<pairing-port> <6-digit-code>   # first time only"
  echo "   bash $0 <ip>:<connect-port>                  # every time after"
  exit 0
fi

if [ -n "$code" ]; then
  echo "Pairing with $target ..."
  # Pairing is one-time per phone: it exchanges a key that later connects reuse.
  if ! adb pair "$target" "$code"; then
    echo "Pairing failed. The pairing port and code change every time that" >&2
    echo "dialog is opened — reopen it and use the fresh values." >&2
    exit 1
  fi
  echo
  echo "Paired. Now connect using the port shown on the main Wireless"
  echo "debugging screen (not the pairing port):"
  echo "   bash $0 <ip>:<connect-port>"
  exit 0
fi

echo "Connecting to $target ..."
if ! adb connect "$target"; then
  echo "Connect failed." >&2
  exit 1
fi

# `adb connect` reports success even when the handshake is later refused, so
# the device list is the only trustworthy confirmation.
sleep 1
if adb devices | grep -q "^${target}[[:space:]]*device$"; then
  echo
  echo "Connected:"
  adb devices -l | sed 's/^/   /'
  echo
  echo "Set this as the target for a run:"
  echo "   export GREMLIN_SERIAL=$target"
else
  echo
  echo "Not authorised yet. Check the phone for an 'Allow debugging?' prompt," >&2
  echo "accept it, and run this again. Current state:" >&2
  adb devices -l | sed 's/^/   /' >&2
  exit 1
fi
