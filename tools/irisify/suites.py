"""Suites: pick the right scenarios instead of always running everything.

Scenarios are described in `scenarios/*.json` (one object or a list):
  {"name": "swim_speed_curve", "owner": "swim-controls", "tags": ["swim", "locomotion", "comfort"],
   "touches": ["VR/Swim*.cs", "VR/ArmSwimming.cs"], "minutes": 3, "needs_restart": false,
   "covers": [...], "cannot_cover": [...], "shots": [{"moment": "...", "question": "..."}]}

Suites are in `suites/*.json`:
  {"name": "swim", "description": "...", "include_tags": ["swim"], "exclude_tags": [], "scenarios": [],
   "always": ["boot"], "interleave": null, "shuffle": false, "repeat": 1}

Built-in dynamic suites (no file needed):
  smoke       tags 'smoke' (boot, input reaches the mod, one mechanic). After every deploy. Minutes.
  changed     scenarios whose `touches` match files changed since the last green run's build, plus smoke.
  regression  everything that failed or was flaky on the last two builds.
  auto        changed + regression, deduplicated: what an agent should run after a change.
  full        everything, ordered cheap-first, restart-needing ones grouped.
  flaky-hunt  --scenario X: X interleaved between all others, shuffled with a logged seed.
"""
import fnmatch
import glob
import json
import os
import random
import subprocess

from . import results

BUILTIN = ("smoke", "changed", "regression", "auto", "full", "flaky-hunt")


def load_scenarios(project):
    meta = results.scenario_meta(project)
    for s in meta.values():
        s.setdefault("tags", [])
        s.setdefault("minutes", 2)
    return meta


def load_suites(project):
    out = {}
    for p in sorted(glob.glob(os.path.join(project.root, "suites", "*.json"))):
        with open(p) as f:
            d = json.load(f)
        out[d["name"]] = d
    return out


def changed_files(project, since):
    if not since:
        return None
    try:
        out = subprocess.run(["git", "-C", project.root, "diff", "--name-only", f"{since}...HEAD"],
                             capture_output=True, text=True, timeout=20).stdout
        out += subprocess.run(["git", "-C", project.root, "diff", "--name-only"], capture_output=True, text=True, timeout=20).stdout
    except Exception:
        return None
    return sorted({l.strip() for l in out.splitlines() if l.strip()})


def last_green_build(runs):
    for r in reversed(runs):
        if r["counts"].get("FAIL", 0) == 0 and r["counts"].get("CRASH", 0) == 0 and r["build"].get("commit"):
            return r["build"]["commit"]
    return None


def order(names, meta):
    """Cheap first, restart-needing scenarios together at the start (they restart anyway)."""
    return sorted(dict.fromkeys(names), key=lambda n: (not meta.get(n, {}).get("needs_restart", False),
                                                       meta.get(n, {}).get("minutes", 2), n))


def select(project, suite, scenario=None, seed=None, files=None):
    """Returns {"suite", "scenarios": [...ordered], "why": {name: reason}, "seed"}."""
    meta = load_scenarios(project)
    suites = load_suites(project)
    runs = results.list_runs(project)
    why = {}

    def add(names, reason):
        for n in names:
            why.setdefault(n, reason)

    smoke = [n for n, s in meta.items() if "smoke" in s["tags"]]
    if suite in suites:
        d = suites[suite]
        names = list(d.get("always", []))
        names += [n for n, s in meta.items() if set(s["tags"]) & set(d.get("include_tags", []))
                  and not set(s["tags"]) & set(d.get("exclude_tags", []))]
        names += d.get("scenarios", [])
        add(names, f"suite {suite}")
        sel = order(names, meta)
        sel = sel * int(d.get("repeat", 1))
        if d.get("interleave"):
            sel = interleave(sel, d["interleave"])
        if d.get("shuffle"):
            seed = seed if seed is not None else random.randrange(1 << 30)
            random.Random(seed).shuffle(sel)
        return {"suite": suite, "scenarios": sel, "why": why, "seed": seed}
    if suite == "smoke":
        add(smoke, "smoke")
    elif suite == "full":
        add(meta.keys(), "full")
    elif suite in ("changed", "auto"):
        add(smoke, "smoke")
        files = files if files is not None else changed_files(project, last_green_build(runs))
        if files is None:
            add(meta.keys(), "no green build to diff against: everything")
        else:
            for n, s in meta.items():
                hits = [f for f in files for pat in s.get("touches", []) if fnmatch.fnmatch(f, pat) or fnmatch.fnmatch(os.path.basename(f), pat)]
                if hits:
                    add([n], f"touches {hits[0]}")
                elif any(t in s["tags"] for t in ("settings", "input")) and any(f.endswith(("Settings.cs", ".json")) for f in files):
                    add([n], "settings/input changed")
    if suite in ("regression", "auto"):
        recent = {r["build"].get("id") for r in runs[-6:]}
        for r in runs[-6:]:
            for s in r["scenarios"]:
                if s["result"] in ("FAIL", "CRASH"):
                    add([s["base"]], f"{s['result']} on {r['build'].get('id')}")
        for bid, fl in results.flaky(runs).items():
            if bid in recent:
                add(fl.keys(), "flaky")
    if suite == "flaky-hunt":
        if not scenario:
            raise SystemExit("flaky-hunt needs --scenario <name>")
        others = [n for n in meta if n != scenario and not meta[n].get("needs_restart")]
        seed = seed if seed is not None else random.randrange(1 << 30)
        random.Random(seed).shuffle(others)
        sel = interleave(others, scenario)
        return {"suite": suite, "scenarios": sel, "why": {scenario: "hunted", **{o: "between" for o in others}}, "seed": seed}
    if suite not in BUILTIN and suite not in suites:
        raise SystemExit(f"unknown suite '{suite}' (built in: {', '.join(BUILTIN)}; files: {', '.join(suites) or 'none'})")
    return {"suite": suite, "scenarios": order(why.keys(), meta), "why": why, "seed": seed}


def interleave(names, x):
    out = [x]
    for n in names:
        if n != x:
            out += [n, x]
    return out


def estimate_minutes(project, names):
    meta = load_scenarios(project)
    return round(sum(meta.get(n, {}).get("minutes", 2) for n in names) + 1.5 * sum(1 for n in names if meta.get(n, {}).get("needs_restart")), 1)
