#!/bin/bash
# Stop the test game by PID (anchored on the Windows exe path), and with "all" the simulated headset.
#   EXE=Subnautica.exe stop.sh [all]
: "${EXE:?set EXE}"
pat="^[A-Z]:.*${EXE//./\\.}"
for p in $(pgrep -f "$pat"); do kill "$p"; done
sleep 3
for p in $(pgrep -f "$pat"); do kill -9 "$p"; done
[ "${1:-}" = all ] && "$(dirname "$0")/monado.sh" stop
exit 0
