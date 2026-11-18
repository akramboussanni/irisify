#!/bin/bash
# SteamVR's null driver: a headset-free SteamVR for the rig. Works on Windows (Git Bash / WSL path to Steam) and on
# Linux only with a display SteamVR can DRM-lease; without one the compositor fails
# (VRInitError_Compositor_GnomeNoDRMLeasing / CannotDRMLeaseDisplay). On Linux prefer monado.sh.
#   null-driver.sh enable | disable | status       (STEAM=<steam root> to override detection)
# enable backs up steamvr.vrsettings to steamvr.vrsettings.irisify-backup first; disable restores it exactly.
set -euo pipefail
STEAM=${STEAM:-}
for d in "$HOME/.local/share/Steam" "$HOME/.steam/steam" "/c/Program Files (x86)/Steam" "/mnt/c/Program Files (x86)/Steam"; do
  [ -z "$STEAM" ] && [ -d "$d/config" ] && STEAM=$d
done
[ -n "$STEAM" ] || { echo "Steam not found; set STEAM=<path>" >&2; exit 2; }
CFG="$STEAM/config/steamvr.vrsettings"; BAK="$CFG.irisify-backup"
NULLCFG="$STEAM/steamapps/common/SteamVR/drivers/null/resources/settings/default.vrsettings"
case "${1:-status}" in
  enable)
    pgrep -x vrserver >/dev/null && { echo "SteamVR is running: quit it first" >&2; exit 1; }
    [ -f "$BAK" ] || cp "$CFG" "$BAK"
    [ -f "$NULLCFG.irisify-backup" ] || cp "$NULLCFG" "$NULLCFG.irisify-backup"
    python3 - "$CFG" "$NULLCFG" <<'PY'
import json, sys, re
def load(p):
    try:
        return json.load(open(p))
    except Exception:
        return {}
cfg, nul = sys.argv[1], sys.argv[2]
c = load(cfg)
c.setdefault("steamvr", {}).update({"requireHmd": False, "forcedDriver": "null", "activateMultipleDrivers": True})
json.dump(c, open(cfg, "w"), indent=3)
n = load(nul)
n.setdefault("driver_null", {}).update({"enable": True, "windowWidth": 1280, "windowHeight": 720, "renderWidth": 1280, "renderHeight": 720})
json.dump(n, open(nul, "w"), indent=3)
PY
    echo "null driver on (backup: $BAK). Undo: $0 disable" ;;
  disable)
    pgrep -x vrserver >/dev/null && { echo "SteamVR is running: quit it first" >&2; exit 1; }
    [ -f "$BAK" ] && mv "$BAK" "$CFG" && echo "restored $CFG"
    [ -f "$NULLCFG.irisify-backup" ] && mv "$NULLCFG.irisify-backup" "$NULLCFG" && echo "restored null driver settings"
    true ;;
  status)
    python3 -c "import json,sys;c=json.load(open(sys.argv[1])).get('steamvr',{});print('forcedDriver',c.get('forcedDriver'),'requireHmd',c.get('requireHmd'))" "$CFG"
    [ -f "$BAK" ] && echo "backup present: null driver is on" || echo "no backup: null driver not set by irisify" ;;
  *) echo "usage: $0 enable|disable|status" >&2; exit 2 ;;
esac
