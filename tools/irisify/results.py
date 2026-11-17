"""Results: import the rig's results.jsonl (Irisify schema or the older SubmersedVR rig format), group lines into
runs, tie runs to builds, compute metrics and find flaky scenarios. See docs/results-schema.md.
"""
import glob
import json
import os
import re
import shutil

from .project import now

REPEAT_RE = re.compile(r"^(.*)#(\d+)$")


def base_name(scenario):
    m = REPEAT_RE.match(scenario or "")
    return m.group(1) if m else scenario


def shot_basename(p):
    """Proton returns Z:\\home\\...; keep only the file name (lessons C3)."""
    if isinstance(p, dict):
        p = p.get("path") or p.get("file") or ""
    return re.split(r"[\\/]", p)[-1]


def split_runs(lines):
    """Group result lines into runs: a `run` header starts one, a `summary` line ends one."""
    runs, cur = [], None
    for l in lines:
        if l.get("type") == "run" or ("run" in l and isinstance(l.get("run"), dict)):
            if cur and cur["scenarios"]:
                runs.append(cur)
            hdr = l.get("run") if isinstance(l.get("run"), dict) else l
            cur = {"header": hdr, "scenarios": [], "commands": 0}
            continue
        if cur is None:
            cur = {"header": {}, "scenarios": [], "commands": 0}
        if "scenario" in l and "result" in l:
            prev = cur["scenarios"][-1] if cur["scenarios"] else None
            if l.get("via") == "rigclient" and prev and not prev.get("via") and base_name(prev["scenario"]) == base_name(l["scenario"]):
                cur["scenarios"][-1] = l
            else:
                cur["scenarios"].append(l)
        elif "summary" in l:
            cur["summary"] = l
            runs.append(cur)
            cur = None
        else:
            cur["commands"] += 1
    if cur and cur["scenarios"]:
        runs.append(cur)
    return runs


def comfort_events(sc):
    n = 0
    for c in sc.get("checks", []):
        name = (c.get("check") or "").lower()
        if name.startswith("comfort") and isinstance(c.get("value"), list):
            n += len(c["value"])
    return n


def numeric_checks(sc):
    out = {}
    for c in sc.get("checks", []):
        v = c.get("value")
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            out[c.get("check")] = v
    return out


def normalise_scenario(sc, meta):
    name = sc["scenario"]
    info = meta.get(base_name(name), {})
    shots = []
    for s in sc.get("shots", []):
        fn = shot_basename(s)
        moment = (s.get("moment") if isinstance(s, dict) else None) or fn.rsplit(".", 1)[0].split("-", 1)[-1]
        q = (s.get("question") if isinstance(s, dict) else None) or info.get("shots", {}).get(moment, {}).get("question")
        shots.append({"file": fn, "moment": moment, "question": q})
    return {
        "scenario": name, "base": base_name(name), "result": sc.get("result"), "detail": sc.get("detail", ""),
        "checks": sc.get("checks", []), "shots": shots, "log": sc.get("log", [])[-60:],
        "errors": sc.get("errors", []), "startState": sc.get("startState"),
        "owner": sc.get("owner") or info.get("owner"), "covers": sc.get("covers") or info.get("covers", []),
        "cannot_cover": sc.get("cannot_cover") or info.get("cannot_cover", []),
        "metrics": dict(sc.get("metrics") or {}, comfort_events=comfort_events(sc), **{f"check:{k}": v for k, v in numeric_checks(sc).items()}),
    }


def scenario_meta(project):
    meta = {}
    for p in glob.glob(os.path.join(project.root, "scenarios", "*.json")) + glob.glob(os.path.join(project.dir, "scenarios", "*.json")):
        try:
            with open(p) as f:
                d = json.load(f)
        except ValueError:
            continue
        for s in d if isinstance(d, list) else [d]:
            if "name" in s:
                s["shots"] = {x["moment"]: x for x in s.get("shots", [])}
                meta[s["name"]] = s
    return meta


def current_build(project, machine):
    deploys = [d for d in project.lines("deploys.jsonl") if d.get("machine") == machine and d.get("ok", True)]
    return deploys[-1]["build"] if deploys else None


def import_file(project, machine, results_path, shots_dir=None, build=None, suite=None):
    """Import new lines from a synced results.jsonl. Keeps an offset per machine so re-syncs only add new runs."""
    offsets = project.read("import-offsets.json", {})
    key = f"{machine}:{os.path.abspath(results_path)}"
    size = os.path.getsize(results_path)
    start = offsets.get(key, 0)
    if start > size:  # file was reset on the rig
        start = 0
    with open(results_path, "rb") as f:
        f.seek(start)
        data = f.read().decode("utf-8", "replace")
    lines = []
    for l in data.splitlines():
        try:
            lines.append(json.loads(l))
        except ValueError:
            pass
    meta = scenario_meta(project)
    made = []
    for i, r in enumerate(split_runs(lines)):
        hdr = r["header"]
        b = hdr.get("build") or build or current_build(project, machine)
        run_id = hdr.get("id") or f"{now().replace(':', '').replace('-', '')}-{machine}-{len(made) + 1}"
        scen = [normalise_scenario(s, meta) for s in r["scenarios"]]
        run = {
            "id": run_id, "machine": machine, "imported": now(), "build": b if isinstance(b, dict) else ({"id": b} if b else {"id": "unknown"}),
            "build_inferred": not hdr.get("build"), "suite": hdr.get("suite") or suite,
            "counts": count(scen), "scenarios": scen,
        }
        d = project.path("runs", run_id)
        os.makedirs(os.path.join(d, "shots"), exist_ok=True)
        if shots_dir and os.path.isdir(shots_dir):
            for s in scen:
                for sh in s["shots"]:
                    src = os.path.join(shots_dir, sh["file"])
                    if os.path.exists(src):
                        shutil.copy2(src, os.path.join(d, "shots", sh["file"]))
                        sh["present"] = True
        project.write(os.path.join("runs", run_id, "run.json"), run)
        made.append(run_id)
    offsets[key] = size
    project.write("import-offsets.json", offsets)
    return made


def count(scen):
    c = {"PASS": 0, "FAIL": 0, "SKIP": 0, "CRASH": 0}
    for s in scen:
        c[s.get("result") or "FAIL"] = c.get(s.get("result") or "FAIL", 0) + 1
    return c


def list_runs(project):
    runs = []
    for p in sorted(glob.glob(project.path("runs", "*", "run.json"))):
        with open(p) as f:
            runs.append(json.load(f))
    runs.sort(key=lambda r: r.get("imported", ""))
    return runs


def flaky(runs, spread=0.25):
    """Scenarios whose result or a numeric check varies within one build. Returns {build: {scenario: reason}}."""
    by = {}
    for r in runs:
        bid = r["build"].get("id")
        for s in r["scenarios"]:
            by.setdefault(bid, {}).setdefault(s["base"], []).append(s)
    out = {}
    for bid, scen in by.items():
        for name, items in scen.items():
            results = {i["result"] for i in items if i["result"] != "SKIP"}
            reason = None
            if len(results) > 1:
                reason = f"results differ: {sorted(results)} over {len(items)} runs"
            else:
                keys = set().union(*(i["metrics"].keys() for i in items))
                for k in keys:
                    vals = [i["metrics"][k] for i in items if isinstance(i["metrics"].get(k), (int, float))]
                    if len(vals) >= 2 and max(abs(v) for v in vals) > 0:
                        sp = (max(vals) - min(vals)) / max(abs(v) for v in vals)
                        if sp > spread and k != "comfort_events":
                            reason = f"{k} varies {round(sp * 100)}% ({min(vals)}..{max(vals)})"
                            break
            if reason:
                out.setdefault(bid, {})[name] = reason
    return out


def headset_checklist(runs, issues=()):
    """Everything the rig can't cover, plus open user complaints, for the latest build."""
    if not runs:
        return []
    latest = runs[-1]
    items = {}
    for s in latest["scenarios"]:
        for c in s.get("cannot_cover", []):
            items.setdefault(c, []).append(s["base"])
    out = [{"item": k, "from": sorted(set(v))} for k, v in items.items()]
    for i in issues:
        if i.get("source") == "user" and i.get("state") != "closed":
            out.append({"item": f"Re-check: \"{i['title']}\"", "from": ["user"]})
    return out
