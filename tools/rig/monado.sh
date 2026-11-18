#!/bin/bash
# Simulated headset for the headset-free rig on Linux: Monado's simulated HMD + controllers, compositor in a normal
# X11 window. Nothing in the user's SteamVR/OpenXR config changes: launch.sh points only the test game at it.
#   monado.sh start | stop | status
set -euo pipefail
case "${1:-status}" in
  start)
    command -v monado-service >/dev/null || { echo "monado-service missing. Fedora: sudo dnf install monado opencomposite (you run this)" >&2; exit 2; }
    if ! pgrep -x monado-service >/dev/null; then
      systemd-run --user --collect --unit=irisify-monado -E SIMULATED_ENABLE=1 \
        -E XRT_COMPOSITOR_FORCE_XCB=1 -E XRT_NO_STDIN=1 monado-service >/dev/null
      sleep 3
    fi ;;
  stop) systemctl --user stop irisify-monado 2>/dev/null || true ;;
  status) ;;
  *) echo "usage: $0 start|stop|status" >&2; exit 2 ;;
esac
echo "monado-service: $(pgrep -x monado-service || echo not running)"
