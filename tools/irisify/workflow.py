"""The gated workflow. Each gate is a function over evidence in the project. Commands that depend on a gate call
`require()`, which refuses (with the reason and the next action) until it passes. `--force "<why>"` overrides and
is recorded in .irisify/overrides.jsonl and on the dashboard.
"""
import glob
import os
import re

from . import controllers, results
from .project import load_structured, now

PHASES = [
    ("setup", "Setup", "machines and links"),
    ("intake", "Intake", "detect, then ask"),
    ("platform", "Platform preflight", "every game host"),
    ("first-boot", "First boot", "real headset, all patches, input"),
    ("design", "Design", "nine artifacts, user sign-off"),
    ("slice", "Vertical slice", "one mechanic + foundations"),
    ("breadth", "Breadth", "features, suites green"),
    ("ready", "Ready for headset", "the human's checklist"),
]

DESIGN_FILES = ["00-intake.md", "01-evidence.md", "02-physical-sketch.md", "interactions.json", "controls.json",
                "body-map.md", "ui-placement.md", "comfort.md", "reviews.md", "test-plan.md"]

NEEDS = {"fanout": ["first-boot", "design", "slice"], "integrate": ["first-boot"], "deploy": ["first-boot"],
         "publish": ["ready"]}


def _g(ok, evidence, next_action=None, partial=None):
    return {"ok": ok, "evidence": evidence, "next": None if ok else next_action, "partial": partial}


def gate_setup(p):
    st = p.read("machines-status.json", {})
    ms = p.read("machines.json", {"machines": {}})["machines"]
    if not ms:
        return _g(False, [], "Add machines: irisify machine add <name> --roles ... --link ssh|adb|local")
    bad = [n for n in ms if not st.get(n, {}).get("reachable")]
    return _g(not bad, [f"{n}: {'reachable' if n not in bad else 'not reachable'}" for n in ms],
              f"Fix the link for {', '.join(bad)} (irisify machine setup {bad[0] if bad else ''})")


def gate_intake(p):
    from . import intake
    q = intake.questions()
    a = p.read("intake.json", {"answers": {}})["answers"]
    blocking = [x["id"] for x in q if x["rank"] == "blocking" and x["id"] not in a]
    return _g(not blocking, [f"{len(a)} answered"], f"Ask: {', '.join(blocking)} (dashboard Intake page)",
              partial=f"{len([x for x in q if x['rank'] == 'blocking']) - len(blocking)}/{len([x for x in q if x['rank'] == 'blocking'])} blocking")


def gate_platform(p):
    pre = p.read("preflight.json", {})
    hosts = [n for n, m in p.read("machines.json", {"machines": {}})["machines"].items() if "game-host" in m.get("roles", [])]
    if not hosts:
        return _g(False, [], "Add a game-host machine")
    ev, bad = [], []
    for h in hosts:
        r = pre.get(h)
        if not r:
            bad.append(h)
            ev.append(f"{h}: not checked")
            continue
        fails = [c["id"] for c in r["checks"] if c["ok"] is False]
        ev.append(f"{h}: {len(r['checks']) - len(fails)}/{len(r['checks'])} checks" + (f", failing {', '.join(fails)}" if fails else ""))
        if fails:
            bad.append(h)
    return _g(not bad, ev, f"irisify doctor platform --machine {bad[0] if bad else ''}")


PATCH_RE = re.compile(r"patches: (\d+) applied, (\d+) failed|loaded and patches applied! \((\d+) patch classes\)")


def gate_first_boot(p):
    ev = p.read("first-boot.json")
    if not ev:
        return _g(False, [], "Deploy to the headset, ask the user to launch the game in VR now and press A and the trigger, then: irisify gate first-boot --log <LogOutput.log>")
    checks = ev.get("checks", {})
    ok = all(checks.get(k) for k in ("patches_ok", "input_down", "build_matches"))
    return _g(ok, [f"{k}: {v}" for k, v in checks.items()], "Fix what's false above and re-run with a fresh log")


def first_boot_from_log(p, text, expected_build=None):
    m = None
    for m in PATCH_RE.finditer(text):
        pass
    failed = None
    if m:
        failed = int(m.group(2)) if m.group(2) is not None else 0
    downs = re.findall(r"\[(?:InputDiag|Irisify:input)\] (\S+) DOWN", text)
    avail = re.findall(r"inputAvailable=(\w+)", text)
    build = re.findall(r"\[Irisify\] build (\S+)", text)
    checks = {
        "patches_ok": failed == 0, "patch_line": m.group(0) if m else None,
        "input_available": (avail[-1] == "True") if avail else None,
        "input_down": bool(downs), "down_actions": sorted(set(downs))[:12],
        "build_in_log": build[-1] if build else None,
        "build_matches": (build[-1] == expected_build) if (build and expected_build) else (bool(build) or expected_build is None),
    }
    rec = {"at": now(), "checks": checks}
    p.write("first-boot.json", rec)
    return rec


def gate_design(p):
    d = os.path.join(p.root, "design")
    missing = [f for f in DESIGN_FILES if not (os.path.exists(os.path.join(d, f)) or os.path.exists(os.path.join(d, f.replace(".json", ".yaml"))))]
    ev = [f"missing: {', '.join(missing)}"] if missing else ["all artifacts present"]
    lint_errors = []
    cp = os.path.join(d, "controls.json")
    if os.path.exists(cp):
        ip = os.path.join(d, "interactions.json")
        inter = load_structured(ip) if os.path.exists(ip) else None
        errors, warnings = controllers.lint(controllers.load_controls(cp), interactions=inter)
        lint_errors = errors
        ev.append(f"controls lint: {len(errors)} errors, {len(warnings)} warnings")
    signed = p.read("signoffs.json", {}).get("design")
    ev.append(f"user sign-off: {signed['at'] if signed else 'not yet'}")
    ok = not missing and not lint_errors and bool(signed)
    nxt = ("Write " + missing[0] + " (skill/templates/design/)") if missing else ("Fix controls lint: " + lint_errors[0]) if lint_errors else "Ask the user to sign off the Design card on the dashboard"
    return _g(ok, ev, nxt)


def gate_slice(p):
    s = p.read("signoffs.json", {}).get("slice")
    runs = results.list_runs(p)
    green = [r for r in runs if r["counts"].get("PASS") and not r["counts"].get("FAIL") and not r["counts"].get("CRASH")]
    ev = [f"green runs: {len(green)}", f"feel check: {s['at'] if s else 'not yet'}"]
    return _g(bool(s) and bool(green), ev, "Run the slice's scenario green, then do the feel check with the user and sign off")


def gate_breadth(p):
    runs = results.list_runs(p)
    if not runs:
        return _g(False, ["no runs"], "irisify suite run full --machine <rig>")
    last = runs[-1]
    c = last["counts"]
    fl = results.flaky(runs).get(last["build"].get("id"), {})
    ok = not c.get("FAIL") and not c.get("CRASH") and not fl
    total = sum(c.values())
    return _g(ok, [f"last run {last['id']}: {c.get('PASS', 0)}/{total} pass", f"flaky: {', '.join(fl) or 'none'}"],
              "Route the failures (dashboard Issues), fix, re-run `irisify suite run auto`",
              partial=f"{c.get('PASS', 0)}/{total}")


def gate_ready(p):
    runs = results.list_runs(p)
    b = gate_breadth(p)
    reviews = p.read("shot-reviews.json", {})
    unreviewed = []
    if runs:
        for s in runs[-1]["scenarios"]:
            for sh in s["shots"]:
                if f"{runs[-1]['id']}/{sh['file']}" not in reviews:
                    unreviewed.append(sh["file"])
    dev = p.read("machines.json", {"machines": {}})["machines"]
    heads = [n for n, m in dev.items() if "headset" in m.get("roles", [])]
    deploys = p.lines("deploys.jsonl")
    on_build = {}
    for d in deploys:
        on_build[d["machine"]] = d["build"].get("id")
    latest = runs[-1]["build"].get("id") if runs else None
    behind = [h for h in heads if on_build.get(h) != latest]
    ev = [f"suite: {'green' if b['ok'] else 'not green'}", f"unreviewed shots: {len(unreviewed)}",
          f"headsets on {latest}: {', '.join(h for h in heads if h not in behind) or 'none'}"]
    ok = b["ok"] and not unreviewed and not behind
    nxt = b["next"] if not b["ok"] else (f"Review {len(unreviewed)} screenshots" if unreviewed else f"irisify deploy --machine {behind[0]}" if behind else None)
    return _g(ok, ev, nxt)


GATES = {"setup": gate_setup, "intake": gate_intake, "platform": gate_platform, "first-boot": gate_first_boot,
         "design": gate_design, "slice": gate_slice, "breadth": gate_breadth, "ready": gate_ready}


def status(p):
    out = []
    current = None
    for key, title, sub in PHASES:
        g = GATES[key](p)
        out.append({"id": key, "title": title, "sub": sub, **g})
        if not g["ok"] and current is None:
            current = key
    return {"phases": out, "current": current, "overrides": p.lines("overrides.jsonl")[-10:]}


def require(p, action, force=None):
    missing = [g for g in NEEDS.get(action, []) if not GATES[g](p)["ok"]]
    if not missing:
        return
    if force:
        p.append("overrides.jsonl", {"action": action, "gates": missing, "why": force})
        return
    g = GATES[missing[0]](p)
    raise SystemExit(f"refusing '{action}': gate '{missing[0]}' hasn't passed.\n  evidence: {'; '.join(g['evidence'])}\n"
                     f"  next: {g['next']}\n  (override only if the user said so: --force \"<why>\")")
