"""Controller knowledge: profiles, detection, lint, SteamVR binding generation and prompt tables.

One source of truth (`design/controls.json`) generates the binding JSON for every controller family and the
on-screen prompt tables, so prompts can't drift from bindings. Components are written with Steam Frame names
(the richest layout); each profile's `from_frame` map says where each one lands on that family, or that it's
missing there (lint reports what's lost).
"""
import glob
import json
import os
import re

from .project import PROFILES, load_structured

GRAB_INPUTS = {"grip"}
HANDS = ("left", "right")


# ---------- profiles ----------

def load_profiles():
    out = {}
    for p in sorted(glob.glob(os.path.join(PROFILES, "*.json"))):
        with open(p) as f:
            d = json.load(f)
        out[d["controller_type"]] = d
    return out


def component_name(path):
    """'/input/dpad_up' -> 'dpad_up'."""
    return path.rsplit("/", 1)[-1]


def profile_components(profile):
    return {component_name(k): v for k, v in profile["components"].items() if k.startswith("/input/") and "skeleton" not in k}


def map_component(profile, comp):
    """Frame-named component -> this family's component name, or None if it has no equivalent."""
    m = profile.get("from_frame", {})
    if comp in m:
        return m[comp]
    return comp if comp in profile_components(profile) else None


def profile_from_runtime_file(path):
    """Turn a SteamVR driver input profile (<type>_profile.json) into an Irisify profile skeleton."""
    with open(path) as f:
        d = json.load(f)
    comps = {}
    for k, v in d.get("input_source", {}).items():
        comps[k] = {a: b for a, b in v.items() if a not in ("binding_image_point", "order")}
        if v.get("visibility") == "InputValueVisibility_SteamVRInternal":
            comps[k]["internal"] = True
    return {
        "name": d.get("controller_type"),
        "controller_type": d.get("controller_type"),
        "source": f"read from {path}",
        "components": comps,
        "mirror_mappings": d.get("mirror_mappings", []),
        "from_frame": {},
    }


# ---------- detection ----------

TYPE_RE = re.compile(r"\b(frame_controller|knuckles|oculus_touch|holographic_controller|vive_controller|"
                     r"hpmotioncontroller|vive_cosmos_controller|pico_controller|generic)\b")
HMD_RE = re.compile(r"\b(frame_hmd|indexhmd|lighthouse|oculus|holographic)\b")
ADAPTER_RE = re.compile(r"\[Irisify\] controllers: left=(\S+) right=(\S+)(?: hmd=(\S+))?(?: runtime=(\S+))?")


def detect_from_text(texts):
    """texts: list of (source, text). Returns the best guess with evidence, most reliable source first."""
    for src, text in texts:
        m = None
        for m in ADAPTER_RE.finditer(text or ""):
            pass
        if m:
            return {"controller_type": m.group(2) if m.group(2) != "none" else m.group(1), "hmd": m.group(3),
                    "runtime": m.group(4), "evidence": f"{src}: {m.group(0)}", "confidence": "high"}
    for src, text in texts:
        counts = {}
        for t in TYPE_RE.findall(text or ""):
            counts[t] = counts.get(t, 0) + 1
        counts.pop("generic", None)
        if counts:
            best = max(counts, key=counts.get)
            hmd = HMD_RE.findall(text or "")
            return {"controller_type": best, "hmd": hmd[-1] if hmd else None, "runtime": "SteamVR",
                    "evidence": f"{src}: {best} mentioned {counts[best]}x", "confidence": "medium",
                    "candidates": sorted(counts, key=counts.get, reverse=True)}
    return None


DETECT_SCRIPT = r"""
for d in "$HOME/.local/share/Steam" "$HOME/.steam/steam" "/c/Program Files (x86)/Steam"; do
  [ -d "$d" ] || continue
  echo "@@steam $d"
  for f in "$d/logs/vrserver.txt" "$d/logs/vrserver.previous.txt"; do [ -f "$f" ] && { echo "@@file $f"; tail -c 200000 "$f"; }; done
  for p in "$d"/steamapps/common/SteamVR/drivers/*/resources/input/*_profile.json; do [ -f "$p" ] && echo "@@profile $p"; done
done
"""


def parse_detect_output(out):
    texts, profiles, cur, buf = [], [], None, []
    for line in out.splitlines():
        if line.startswith("@@file "):
            if cur:
                texts.append((cur, "\n".join(buf)))
            cur, buf = line[7:], []
        elif line.startswith("@@profile "):
            profiles.append(line[10:])
        elif line.startswith("@@steam "):
            continue
        elif cur:
            buf.append(line)
    if cur:
        texts.append((cur, "\n".join(buf)))
    return texts, profiles


# ---------- controls file ----------

def load_controls(path):
    c = load_structured(path)
    c.setdefault("actions", [])
    c.setdefault("dropped", [])
    c.setdefault("contexts", {})
    return c


def iter_bindings(controls):
    """Yield (context, hand, component, sub, action) for every binding cell.

    A cell is either "Action", or a dict for sticks: {"position": "Move", "click": "Jump"},
    or {"click": "X", "when_holding": "item"} / a list of such for holding-state variants.
    """
    for ctx, hands in controls["contexts"].items():
        for hand in HANDS:
            for comp, cell in (hands.get(hand) or {}).items():
                cells = cell if isinstance(cell, list) else [cell]
                for c in cells:
                    if isinstance(c, str):
                        yield ctx, hand, comp, "click", c, "any"
                    elif isinstance(c, dict):
                        holding = c.get("when_holding", "any")
                        for sub, action in c.items():
                            if sub in ("when_holding", "label"):
                                continue
                            yield ctx, hand, comp, sub, action, holding


# ---------- lint ----------

def lint(controls, profiles=None, interactions=None, target_types=None):
    """Returns (errors, warnings), each a list of strings."""
    profiles = profiles or load_profiles()
    errors, warnings = [], []
    actions = {a["name"]: a for a in controls["actions"]}
    dropped = {d["name"] for d in controls["dropped"]}
    frame = profiles.get("frame_controller")
    frame_comps = profile_components(frame) if frame else {}
    used = set()
    owners = {}
    for ctx, hand, comp, sub, action, holding in iter_bindings(controls):
        used.add(action)
        if action not in actions:
            errors.append(f"{ctx}/{hand}/{comp}: '{action}' is not in actions")
            continue
        if frame_comps and comp not in frame_comps:
            errors.append(f"{ctx}/{hand}/{comp}: no such component (use Steam Frame names: {', '.join(sorted(frame_comps))})")
        elif frame_comps:
            side = frame_comps[comp].get("side")
            if side and side != hand:
                errors.append(f"{ctx}/{hand}/{comp}: on the Steam Frame '{comp}' is on the {side} controller")
            if frame_comps[comp].get("internal"):
                errors.append(f"{ctx}/{hand}/{comp}: SteamVR-internal input, can't be bound")
        role = actions[action].get("role")
        if comp in GRAB_INPUTS and role != "grab":
            errors.append(f"{ctx}/{hand}/{comp}: grips are for grabbing; '{action}' has role '{role or 'none'}' (lessons D2)")
        if role == "grab" and comp not in GRAB_INPUTS:
            warnings.append(f"{ctx}/{hand}/{comp}: grab action '{action}' off the grip")
        key = (ctx, hand, comp, sub)
        for other_holding, other in owners.get(key, []):
            if other != action and (holding == other_holding or "any" in (holding, other_holding)):
                errors.append(f"{ctx}/{hand}/{comp}.{sub}: two owners '{other}' and '{action}' (holding {other_holding}/{holding})")
        owners.setdefault(key, []).append((holding, action))
    for name, a in actions.items():
        if a.get("type") in ("pose", "skeleton", "vibration"):
            continue
        if name not in used and name not in dropped:
            errors.append(f"action '{name}' is neither bound in any context nor dropped with a reason (lessons D1)")
    for d in controls["dropped"]:
        if not d.get("why"):
            errors.append(f"dropped action '{d['name']}' needs a 'why'")
    # shortcuts next to their physical replacements
    for it in (interactions or []):
        if it.get("form") != "physical" or not it.get("in_preset", True):
            continue
        for replaced in it.get("replaces", []):
            for ctx, hand, comp, sub, action, holding in iter_bindings(controls):
                if action == replaced and ctx in it.get("contexts", []):
                    errors.append(f"{ctx}: '{replaced}' is still bound ({hand} {comp}) although '{it['id']}' replaces it (lessons A6)")
    # what each family loses
    for t, prof in profiles.items():
        if t == "frame_controller" or (target_types and t not in target_types):
            continue
        lost = sorted({f"{action} ({hand} {comp})" for ctx, hand, comp, sub, action, holding in iter_bindings(controls)
                       if map_component(prof, comp) is None})
        if lost:
            warnings.append(f"{t}: no input for {', '.join(lost)}")
    return errors, warnings


# ---------- SteamVR bindings ----------

def _mode_for(comp_info, sub):
    t = comp_info.get("type")
    if t == "joystick":
        return "joystick"
    if t == "trackpad":
        return "trackpad"
    if t == "trigger":
        return "trigger"
    return "button"


def generate_binding(controls, profile):
    """One SteamVR binding JSON for one controller type (contexts merged: SteamVR binds per action set)."""
    aset = controls.get("action_set", "/actions/main")
    actions = {a["name"]: a for a in controls["actions"]}
    comps = profile_components(profile)
    sources, seen, lost = [], set(), []
    for ctx, hand, comp, sub, action, holding in iter_bindings(controls):
        target = map_component(profile, comp)
        if target is None or target not in comps:
            lost.append({"context": ctx, "hand": hand, "component": comp, "action": action})
            continue
        key = (hand, target, sub, action)
        if key in seen:
            continue
        seen.add(key)
        info = comps[target]
        mode = _mode_for(info, sub)
        out_sub = sub
        if mode == "joystick" and sub == "click":
            out_sub = "click"
        if mode == "trigger" and actions[action].get("type") == "vector1":
            out_sub = "pull"
        src = {"path": f"/user/hand/{hand}/input/{target}", "mode": mode,
               "inputs": {out_sub: {"output": f"{aset}/in/{action}".lower()}}}
        if mode == "trigger" and actions[action].get("role") == "grab" and info.get("value"):
            src["parameters"] = {"click_activate_threshold": "0.7", "click_deactivate_threshold": "0.45"}
        sources.append(src)
    poses, skeleton, haptics = [], [], []
    for a in controls["actions"]:
        hand = a.get("hand")
        if a.get("type") == "pose" and hand:
            poses.append({"output": f"{aset}/in/{a['name']}".lower(), "path": f"/user/hand/{hand}/pose/{a.get('pose', 'raw')}"})
        elif a.get("type") == "skeleton" and hand:
            skeleton.append({"output": f"{aset}/in/{a['name']}".lower(), "path": f"/user/hand/{hand}/input/skeleton/{hand}"})
        elif a.get("type") == "vibration" and hand:
            haptics.append({"output": f"{aset}/out/{a['name']}".lower(), "path": f"/user/hand/{hand}/output/haptic"})
    binding = {
        "action_manifest_version": 0,
        "alias_info": {},
        "app_key": controls.get("app_key", "system.generated.game"),
        "bindings": {aset: {"chords": [], "haptics": haptics, "poses": poses, "skeleton": skeleton, "sources": sources}},
        "category": "steamvr_input",
        "controller_type": profile["controller_type"],
        "description": f"Generated by Irisify from design/controls for {profile.get('name', profile['controller_type'])}",
        "name": f"{controls.get('game', 'Game')} VR ({profile.get('name', profile['controller_type'])})",
        "options": {},
        "simulated_actions": [],
    }
    return binding, lost


def default_bindings_entries(types):
    return [{"controller_type": t, "binding_url": f"bindings_{t}.json"} for t in types]


# ---------- prompts ----------

def generate_prompts(controls, profile):
    """{context: {action: [{hand, input, label, glyph}]}} for one controller type."""
    actions = {a["name"]: a for a in controls["actions"]}
    glyphs = profile.get("glyphs", {})
    out = {}
    for ctx, hand, comp, sub, action, holding in iter_bindings(controls):
        target = map_component(profile, comp)
        if target is None:
            continue
        base = glyphs.get(target, target.replace("_", " ").title())
        glyph = f"{'L' if hand == 'left' else 'R'} {base}"
        if sub not in ("click",):
            glyph += {"position": "", "touch": " (touch)", "pull": ""}.get(sub, f" {sub}")
        entry = {"hand": hand, "input": target, "sub": sub, "glyph": glyph.strip(),
                 "label": actions.get(action, {}).get("label", action)}
        if holding != "any":
            entry["when_holding"] = holding
        out.setdefault(ctx, {}).setdefault(action, []).append(entry)
    return out


def prompts_markdown(all_prompts):
    lines = ["# Button prompts (generated; don't edit)", ""]
    for t, prompts in all_prompts.items():
        lines += [f"## {t}", "", "| context | action | prompt |", "|---|---|---|"]
        for ctx, acts in prompts.items():
            for action, entries in acts.items():
                lines.append(f"| {ctx} | {action} | {' or '.join(e['glyph'] for e in entries)} |")
        lines.append("")
    return "\n".join(lines)


def context_table(controls):
    """Markdown table: one row per context, one column per (hand, component) used."""
    cols = []
    for ctx, hand, comp, sub, action, holding in iter_bindings(controls):
        if (hand, comp) not in cols:
            cols.append((hand, comp))
    cols.sort(key=lambda c: (HANDS.index(c[0]), c[1]))
    head = "| context | " + " | ".join(f"{'L' if h == 'left' else 'R'} {c}" for h, c in cols) + " |"
    rows = [head, "|" + "---|" * (len(cols) + 1)]
    for ctx in controls["contexts"]:
        cells = []
        for h, c in cols:
            vals = [f"{a}{'' if s == 'click' else '.' + s}{'' if hd == 'any' else ' [' + hd + ']'}"
                    for cx, hh, cc, s, a, hd in iter_bindings(controls) if cx == ctx and hh == h and cc == c]
            cells.append(", ".join(vals) or "—")
        rows.append(f"| {ctx} | " + " | ".join(cells) + " |")
    return "\n".join(rows)


def write_outputs(controls, out_dir, types=None, kind="bindings"):
    profiles = load_profiles()
    types = types or [t for t in profiles if t != "generic"]
    os.makedirs(out_dir, exist_ok=True)
    report = {}
    if kind == "bindings":
        for t in types:
            b, lost = generate_binding(controls, profiles[t])
            with open(os.path.join(out_dir, f"bindings_{t}.json"), "w") as f:
                json.dump(b, f, indent=2)
            report[t] = lost
        with open(os.path.join(out_dir, "default_bindings.json"), "w") as f:
            json.dump(default_bindings_entries(types), f, indent=2)
    else:
        allp = {}
        for t in types:
            allp[t] = generate_prompts(controls, profiles[t])
            with open(os.path.join(out_dir, f"prompts.{t}.json"), "w") as f:
                json.dump(allp[t], f, indent=2)
        with open(os.path.join(out_dir, "PROMPTS.md"), "w") as f:
            f.write(prompts_markdown(allp))
        report = {t: sum(len(v) for v in p.values()) for t, p in allp.items()}
    return report
