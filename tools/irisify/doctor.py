"""Platform preflight and input-focus diagnostics, run on a machine through its link.

Every check prints what it found, whether it passes, the exact fix, and who runs the fix (agent or you).
"""
import json
import re

from . import controllers, machines
from .project import now


def _version_tuple(v):
    return tuple(int(x) for x in re.findall(r"\d+", v)[:3])


def evaluate(req, out):
    out = (out or "").strip()
    if "expect" in req:
        return out == req["expect"]
    if "expect_min_version" in req:
        try:
            return _version_tuple(out) >= _version_tuple(req["expect_min_version"])
        except ValueError:
            return False
    if req.get("expect_nonzero"):
        try:
            return int(out.split()[0]) > 0
        except (ValueError, IndexError):
            return False
    if "expect_contains" in req:
        return req["expect_contains"] in out
    return bool(out)


STEAM_INPUT_SCRIPT = r"""
APP=__APPID__
for d in "$HOME/.local/share/Steam" "$HOME/.steam/steam"; do
  [ -d "$d/userdata" ] || continue
  for f in "$d"/userdata/*/config/localconfig.vdf; do
    [ -f "$f" ] || continue
    awk -v app="\"$APP\"" '$1==app{inapp=1} inapp && /UseSteamControllerConfig|SteamControllerRumble|eEnableThirdPartyControllerConfiguration/{print FILENAME": "$0} inapp && /^\t\t\t\t}/{inapp=0}' "$f" | head -5
  done
  for f in "$d/logs/console_log.txt" "$d/logs/console-linux.txt" "$d/logs/controller.txt"; do
    [ -f "$f" ] && grep -E "Opted-in Controller Mask for AppId $APP|uses xinput|Queueing activation for controller.*app: $APP" "$f" | tail -5 | sed "s|^|$f: |"
  done
  for f in "$d/logs/vrserver.txt"; do
    [ -f "$f" ] && grep -E "desktopgame\.$APP|Failed to clear focus|IsInputAvailable|systemui" "$f" | tail -5 | sed "s|^|$f: |"
  done
done
"""


def steam_input_findings(output):
    """Interpret the script's output. Returns (state, evidence lines)."""
    lines = [l for l in output.splitlines() if l.strip()]
    forced = [l for l in lines if re.search(r"Opted-in Controller Mask|uses xinput|Queueing activation|desktopgame\.", l)]
    setting = [l for l in lines if "UseSteamControllerConfig" in l or "eEnableThirdPartyControllerConfiguration" in l]
    off = any(re.search(r'"(0|2)"', l) for l in setting) and not forced
    if forced:
        return "on", forced
    if setting and off:
        return "off", setting
    return "unknown", lines[-5:]


def platform(project, name, appid=None):
    data = machines.load(project)
    m = data["machines"].get(name)
    if not m:
        raise SystemExit(f"no machine '{name}' (irisify machine add ...)")
    link = machines.link_for(m)
    profiles = controllers.load_profiles()
    prof = profiles.get(m.get("headset") or "", {})
    results = []
    reqs = prof.get("host_requirements", {}).get((m.get("os") or "linux").lower(), [])
    for req in reqs:
        try:
            rc, out, err = link.run(req["check"], timeout=30)
        except Exception as e:
            rc, out = 1, str(e)
        ok = evaluate(req, out)
        results.append({"id": req["id"], "what": req["what"], "ok": ok, "found": (out or "").strip()[:200],
                        "fix": None if ok else req["fix"], "who": req.get("who", "you")})
    appid = appid or project.config().get("steam_appid")
    if appid:
        rc, out, err = link.run(STEAM_INPUT_SCRIPT.replace("__APPID__", str(int(appid))), timeout=30)
        state, ev = steam_input_findings(out)
        results.append({"id": "steam_input", "what": f"Steam Input off for app {appid}", "ok": state == "off" if state != "unknown" else None,
                        "found": state, "evidence": ev,
                        "fix": None if state == "off" else "Steam > the game > Properties > Controller > Disable Steam Input, then restart the game (lessons C1)",
                        "who": "you"})
    rep = {"machine": name, "at": now(), "headset": m.get("headset"), "checks": results}
    status = project.read("preflight.json", {})
    status[name] = rep
    project.write("preflight.json", status)
    return rep


FOCUS_LOG_RE = re.compile(r"\[(?:InputDiag|Irisify:focus)\][^\n]*(inputAvailable|IsInputAvailable)=(\w+)[^\n]*")


def input_focus(project, name, appid=None, log_path=None):
    """Focus first, bindings second."""
    rep = platform(project, name, appid)
    si = next((c for c in rep["checks"] if c["id"] == "steam_input"), None)
    findings = []
    if si:
        findings.append(si)
    m = machines.load(project)["machines"][name]
    log_path = log_path or project.config().get("log_path")
    if log_path:
        rc, out, err = machines.link_for(m).run(f'tail -c 400000 {machines.remote_path(log_path)} | grep -E "InputDiag|Irisify:focus|DOWN" | tail -40', timeout=30)
        avail = FOCUS_LOG_RE.findall(out)
        downs = [l for l in out.splitlines() if " DOWN" in l]
        last = avail[-1][1] if avail else None
        findings.append({"id": "focus_log", "what": "Game has input focus (IsInputAvailable=true in the mod's log)",
                         "ok": (last == "True" or last == "true") if last else None, "found": last or "no diagnostic lines",
                         "fix": None if last in ("True", "true") else "Input focus is held elsewhere: check Steam Input (above) and SteamVR overlays (vrcmd --overlays) before bindings"})
        findings.append({"id": "down_events", "what": "Button presses reach the mod (DOWN events)", "ok": bool(downs) if out else None,
                         "found": downs[-1] if downs else "none", "fix": None if downs else "Press a face button and the trigger in game, then re-run"})
    return {"machine": name, "at": now(), "checks": findings}
