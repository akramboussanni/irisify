#!/bin/bash
# Start a Windows game under Proton against the simulated headset (Monado via OpenComposite), outside Steam's
# runtime container (which can't see the host's Monado/OpenComposite libraries). Only this process sees the test
# runtime. Steam must be running (Steamworks). Prints the game's PID.
# Configure with env vars (or a copy of this file per game):
#   APPID=264710 GAME_DIR=~/.local/share/Steam/steamapps/common/Subnautica EXE=Subnautica.exe
#   GAME_ARGS="-vrmode openvr" DLL_OVERRIDES="winhttp=n,b" RIG_ENV=SUBMERSEDVR_TESTRIG=1 PROTON="Proton - Experimental"
set -euo pipefail
S=~/.local/share/Steam
: "${APPID:?set APPID}" "${GAME_DIR:?set GAME_DIR}" "${EXE:?set EXE}"
PROTON_BIN="$S/steamapps/common/${PROTON:-Proton - Experimental}/proton"
"$(dirname "$0")/monado.sh" start >/dev/null
OC=/usr/lib64/opencomposite/runtime; [ -d "$OC" ] || OC=/usr/lib/opencomposite/runtime
XRJ=/usr/share/openxr/1/openxr_monado.json
systemctl --user reset-failed irisify-game 2>/dev/null || true
systemd-run --user --collect --unit=irisify-game \
  -E STEAM_COMPAT_CLIENT_INSTALL_PATH=$S -E STEAM_COMPAT_DATA_PATH=$S/steamapps/compatdata/$APPID \
  -E STEAM_COMPAT_APP_ID=$APPID -E SteamAppId=$APPID -E SteamGameId=$APPID \
  -E WINEDLLOVERRIDES="${DLL_OVERRIDES:-winhttp=n,b}" -E IRISIFY_RIG=1 ${RIG_ENV:+-E $RIG_ENV} \
  -E VR_OVERRIDE=$OC -E XR_RUNTIME_JSON=$XRJ \
  --working-directory="$(eval echo "$GAME_DIR")" \
  "$PROTON_BIN" run "$(eval echo "$GAME_DIR")/$EXE" ${GAME_ARGS:-} >/dev/null
for i in $(seq 1 60); do
  p=$(pgrep -f "^[A-Z]:.*${EXE//./\\.}" | head -1 || true)   # anchored on the Windows path: never matches this shell (lessons C3)
  [ -n "$p" ] && { echo "$p"; exit 0; }
  sleep 1
done
echo "game process not found" >&2; exit 1
