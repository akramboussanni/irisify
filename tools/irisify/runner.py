"""Running suites on a rig machine and syncing results back."""
import json
import os
import tempfile
import time

from . import machines, results, suites
from .project import REPO, now

RIG_HOME = "~/irisify-rig"


def rig_config(project, name):
    cfg = project.config().get("rig", {})
    m = machines.load(project)["machines"][name]
    out = dict(cfg)
    out.setdefault("rig_dir", (m.get("game_dir") or "") + "/BepInEx/irisify")
    out.setdefault("log", (m.get("game_dir") or "") + "/BepInEx/LogOutput.log")
    return out


def push_client(project, name):
    m = machines.load(project)["machines"][name]
    link = machines.link_for(m)
    link.run(f"mkdir -p {RIG_HOME}")
    link.push(os.path.join(REPO, "tools", "rig") + "/", RIG_HOME + "/")
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(rig_config(project, name), f, indent=1)
    link.push(f.name, RIG_HOME + "/rig.json")
    os.unlink(f.name)
    return link


def locked_by_other(project, name, me="suite"):
    st = project.read("machines-status.json", {}).get(name, {})
    lock = st.get("facts", {}).get("lock")
    return lock if lock and me not in lock else None


def run_suite(project, suite, machine, scenario=None, seed=None, dry=False):
    sel = suites.select(project, suite, scenario=scenario, seed=seed)
    names = sel["scenarios"]
    est = suites.estimate_minutes(project, names)
    plan = {"suite": suite, "machine": machine, "scenarios": names, "why": sel["why"], "seed": sel["seed"], "minutes": est,
            "options": sel["options"]}
    if dry or not names:
        return plan
    m = machines.load(project)["machines"].get(machine)
    if not m or "rig" not in m.get("roles", []):
        raise SystemExit(f"'{machine}' isn't a rig machine (irisify machine add {machine} --roles rig ...)")
    build = current_build_record(project, machine)
    run_id = f"{time.strftime('%Y%m%d-%H%M%S')}-{machine}-{suite}"
    link = push_client(project, machine)
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(sel["options"], f)
    link.push(f.name, RIG_HOME + "/options.json")
    os.unlink(f.name)
    cmd = (f"cd {RIG_HOME} && python3 rigclient.py --config rig.json run --scenarios {','.join(names)} --options options.json "
           f"--run-id {run_id} --suite {suite} --machine {machine} --build '{json.dumps(build)}'"
           + (f" --seed {sel['seed']}" if sel["seed"] is not None else ""))
    project.write(os.path.join("plans", run_id + ".json"), dict(plan, run=run_id, build=build, at=now()))
    project.append("activity.jsonl", {"what": "suite started", "suite": suite, "machine": machine, "run": run_id, "minutes": est})
    rc, out, err = link.run(cmd, timeout=int(60 * (est * 3 + 10)))
    imported = sync(project, machine)
    project.append("activity.jsonl", {"what": "suite finished", "suite": suite, "machine": machine, "run": run_id, "rc": rc})
    plan.update({"run": run_id, "rc": rc, "output": out[-2000:], "imported": imported})
    return plan


def current_build_record(project, machine):
    deploys = [d for d in project.lines("deploys.jsonl") if d.get("machine") == machine and d.get("ok", True)]
    return deploys[-1]["build"] if deploys else {"id": "unknown"}


def sync(project, machine, build=None):
    """Pull results.jsonl and shots from a rig machine into .irisify/inbox/<machine>/ and import new runs."""
    m = machines.load(project)["machines"][machine]
    cfg = rig_config(project, machine)
    inbox = project.path("inbox", machine)
    os.makedirs(inbox, exist_ok=True)
    link = machines.link_for(m)
    src = cfg["rig_dir"].rstrip("/") + "/"
    link.pull(src + "results.jsonl", inbox)
    link.pull(src + "shots/", os.path.join(inbox, "shots"))
    p = os.path.join(inbox, "results.jsonl")
    if not os.path.exists(p):
        return []
    return results.import_file(project, machine, p, os.path.join(inbox, "shots"), build=build)
