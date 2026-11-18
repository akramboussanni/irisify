#!/usr/bin/env python3
"""Irisify rig client. Runs on the rig machine, next to the game. Python 3.8+, stdlib only.

Talks to the in-game adapter through its command channel: JSON files dropped into <rig>/cmd/ run in name order,
and every command and scenario appends one JSON line to <rig>/results.jsonl.

  rigclient.py --config rig.json cmd '{"cmd":"dump"}'
  rigclient.py --config rig.json run --scenarios boot,swim_controls --run-id 20261117-fedora-1 --build '{"id":"2556818"}'
  rigclient.py --config rig.json start | stop | alive

rig.json (written by `irisify suite run`, or by hand):
  {"rig_dir": "~/.local/share/Steam/steamapps/common/Subnautica/BepInEx/irisify",
   "log": "~/.local/share/Steam/steamapps/common/Subnautica/BepInEx/LogOutput.log",
   "start": "~/irisify-rig/launch.sh", "stop": "~/irisify-rig/stop.sh",
   "patch_line": "patches: (\\d+) applied, (\\d+) failed", "menu_timeout": 240, "scenario_timeout": 600,
   "load": {"cmd": "load", "slot": "slot9000"},
   "saves": {"creative": {"cmd": "load", "slot": "slot9000"}, "survival": {"cmd": "load", "slot": "slot9001"}}}

--options options.json gives per-scenario {"save", "set": "quick|full", "shots": "proof|all", "cap": seconds}.
The save, set and shots go to the adapter with the scenario command; the cap replaces scenario_timeout.
A different save is loaded only when the scenario needs it, so a run stays in one game process.

"reset_settings": an adapter command (e.g. {"cmd": "reset_settings"}) or a shell line ("sh: cp defaults.cfg ...")
run once before the first scenario, so test settings can't leak between runs. A scenario whose log has an
[Irisify:suspend] line (a feature turned itself off) is a FAIL: a silent fail-safe hides a real bug.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
import uuid


def x(p):
    return os.path.expanduser(os.path.expandvars(p)) if p else p


class Rig:
    def __init__(self, cfg):
        self.cfg = cfg
        self.dir = x(cfg["rig_dir"])
        self.cmd_dir = os.path.join(self.dir, "cmd")
        self.results = os.path.join(self.dir, "results.jsonl")

    def size(self):
        return os.path.getsize(self.results) if os.path.exists(self.results) else 0

    def read_from(self, off):
        if not os.path.exists(self.results):
            return [], off
        with open(self.results, "rb") as f:
            f.seek(off)
            data = f.read()
        out = []
        for l in data.decode("utf-8", "replace").splitlines():
            try:
                out.append(json.loads(l))
            except ValueError:
                pass
        return out, off + len(data)

    def append(self, record):
        os.makedirs(self.dir, exist_ok=True)
        with open(self.results, "a") as f:
            f.write(json.dumps(record) + "\n")

    def send(self, cmds, timeout=120):
        if isinstance(cmds, dict):
            cmds = [cmds]
        tag = uuid.uuid4().hex[:8]
        for i, c in enumerate(cmds):
            c.setdefault("id", f"{tag}-{i}")
        last = cmds[-1]["id"]
        os.makedirs(self.cmd_dir, exist_ok=True)
        off = self.size()
        tmp = os.path.join(self.cmd_dir, f".{time.time_ns()}.tmp")
        with open(tmp, "w") as f:
            json.dump(cmds, f)
        os.rename(tmp, os.path.join(self.cmd_dir, f"{time.time_ns()}.json"))  # atomic: the game never reads half a file
        got, end = [], time.time() + timeout
        while time.time() < end:
            lines, off = self.read_from(off)
            for l in lines:
                got.append(l)
                if l.get("id") == last:
                    return got
            time.sleep(0.3)
        raise TimeoutError(f"no result for {last} after {timeout}s")

    def alive(self, timeout=5):
        try:
            self.send({"cmd": "ping"}, timeout=timeout)
            return True
        except TimeoutError:
            return False

    def sh(self, key):
        c = self.cfg.get(key)
        if c:
            subprocess.run(["bash", "-lc", x(c)], check=False)

    def start(self):
        if self.alive():
            return True
        self.sh("start")
        end = time.time() + self.cfg.get("menu_timeout", 240)
        while time.time() < end:
            if self.alive(timeout=5):
                return True
            time.sleep(4)
        return False

    def stop(self):
        self.sh("stop")

    def log_size(self):
        p = x(self.cfg.get("log"))
        return os.path.getsize(p) if p and os.path.exists(p) else 0

    def log_since(self, off):
        p = x(self.cfg.get("log"))
        if not p or not os.path.exists(p):
            return ""
        with open(p, "rb") as f:
            f.seek(off)
            return f.read().decode("utf-8", "replace")


def check(name, ok, value=None):
    return {"check": name, "ok": bool(ok), "value": value}


def boot(rig, run):
    """Runner-side: cold start to the main menu, no exceptions, every patch class applied."""
    rig.stop()
    time.sleep(3)
    off = rig.log_size()
    t0 = time.time()
    up = rig.start()
    menu = False
    end = time.time() + rig.cfg.get("menu_timeout", 240)
    while up and time.time() < end:
        try:
            d = rig.send({"cmd": "dump"}, timeout=10)[-1].get("data", {})
            if d.get("mainMenu") or d.get("scene") in ("menu", "game"):
                menu = True
                break
        except TimeoutError:
            pass
        time.sleep(3)
    log = rig.log_since(off)
    exc = [l for l in log.splitlines() if "Exception" in l][:10]
    m = re.search(rig.cfg.get("patch_line", r"patches: (\d+) applied, (\d+) failed"), log)
    checks = [check("rig answered", up), check("main menu reached", menu, round(time.time() - t0)),
              check("no exceptions up to the menu", not exc, exc),
              check("all patch classes applied", bool(m) and (len(m.groups()) < 2 or m.group(2) == "0"), m.group(0) if m else None)]
    build = re.search(r"\[Irisify\] build (\S+)", log)
    if build:
        checks.append(check("build id in the log matches", build.group(1) == run.get("build", {}).get("id", build.group(1)), build.group(1)))
    return checks


def save_cmd(rig, save):
    saves = rig.cfg.get("saves") or {}
    if save and save in saves:
        return saves[save]
    return rig.cfg.get("load") or (next(iter(saves.values())) if saves else None)


def loaded(rig, load):
    want = load.get("slot")
    try:
        d = rig.send({"cmd": "dump"}, timeout=15)[-1].get("data", {})
    except TimeoutError:
        return False
    return d.get("scene") == "game" and (want is None or d.get("slot") == want)


def run_scenarios(rig, args):
    build = json.loads(args.build) if args.build else {}
    names = [n for n in args.scenarios.split(",") if n]
    options = {}
    if getattr(args, "options", None):
        with open(args.options) as f:
            options = json.load(f)
    run = {"type": "run", "id": args.run_id, "build": build, "suite": args.suite, "machine": args.machine,
           "scenarios": names, "seed": args.seed, "started": time.time()}
    rig.append(run)
    reset = rig.cfg.get("reset_settings")
    if isinstance(reset, str) and reset.startswith("sh:"):
        subprocess.run(["bash", "-lc", reset[3:]], timeout=60)  # before the game reads them
        reset = None
    summary, seen, seconds = {}, {}, {}
    for name in names:
        seen[name] = seen.get(name, 0) + 1
        label = name if seen[name] == 1 else f"{name}#{seen[name]}"
        t0 = time.time()
        if name == "boot":
            checks = boot(rig, run)
            res = {"scenario": label, "result": "PASS" if all(c["ok"] for c in checks) else "FAIL", "checks": checks}
            rig.append(dict(res, run=args.run_id, build=build, t=time.time()))
            summary[label] = res["result"]
            continue
        if not rig.start():
            rig.append({"scenario": label, "result": "CRASH", "detail": "game did not come up", "run": args.run_id, "build": build})
            summary[label] = "CRASH"
            continue
        if reset:
            try:
                rig.send(dict(reset) if isinstance(reset, dict) else {"cmd": reset}, timeout=30)
            except TimeoutError:
                pass
            reset = None
        opt = options.get(name, {})
        load = save_cmd(rig, opt.get("save"))
        if load and not loaded(rig, load):
            # One game process for the whole run: load a test save only when it isn't already loaded;
            # scenarios teleport within it instead of relaunching.
            try:
                rig.send(dict(load), timeout=700)
            except TimeoutError:
                pass
        off = rig.log_size()
        cmd = {"cmd": "scenario", "name": name, "run": args.run_id}
        cmd.update({k: opt[k] for k in ("set", "shots", "save") if k in opt})
        try:
            got = rig.send(cmd, timeout=opt.get("cap") or rig.cfg.get("scenario_timeout", 600))
            res = next((l for l in reversed(got) if l.get("scenario") == name or l.get("scenario") == label), None)
            if res is None:
                res = {"scenario": name, "result": "FAIL", "detail": "no scenario line in the results"}
            res = dict(res)
            res["scenario"] = label
            res.setdefault("run", args.run_id)
            res.setdefault("build", build)
            suspended = [l.strip() for l in rig.log_since(off).splitlines() if "[Irisify:suspend]" in l]
            if suspended:
                res["checks"] = list(res.get("checks") or []) + [{"check": "no feature turned itself off", "ok": False, "value": suspended[:5]}]
                if res.get("result") == "PASS":
                    res["result"] = "FAIL"
            res["seconds"] = round(time.time() - t0, 1)
            if opt.get("set"):
                res["set"] = opt["set"]
            res["via"] = "rigclient"  # the importer replaces the adapter's own line with this labelled copy
            rig.append(res)
            summary[label] = res.get("result")
            seconds[label] = res["seconds"]
        except TimeoutError:
            tail = rig.log_since(off).splitlines()[-30:]
            rig.append({"scenario": label, "result": "CRASH", "detail": f"no answer in {opt.get('cap') or rig.cfg.get('scenario_timeout', 600)}s; game restarted", "log": tail,
                        "run": args.run_id, "build": build})
            summary[label] = "CRASH"
            rig.stop()
    counts = {}
    for v in summary.values():
        counts[v] = counts.get(v, 0) + 1
    rig.append({"summary": summary, **counts, "seconds": seconds, "run": args.run_id, "t": time.time()})
    for k, v in sorted(seconds.items(), key=lambda kv: -kv[1]):
        print(f"{v:7.1f}s  {summary.get(k)}  {k}", file=sys.stderr)
    print(json.dumps({"run": args.run_id, "summary": summary, "counts": counts, "seconds": seconds}))
    return 0 if not counts.get("FAIL") and not counts.get("CRASH") else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "rig.json"))
    sub = ap.add_subparsers(dest="op", required=True)
    c = sub.add_parser("cmd")
    c.add_argument("json")
    r = sub.add_parser("run")
    r.add_argument("--scenarios", required=True)
    r.add_argument("--run-id", required=True)
    r.add_argument("--build", default="")
    r.add_argument("--suite", default=None)
    r.add_argument("--machine", default=None)
    r.add_argument("--seed", type=int, default=None)
    r.add_argument("--options", default=None)
    for n in ("start", "stop", "alive"):
        sub.add_parser(n)
    a = ap.parse_args()
    with open(a.config) as f:
        rig = Rig(json.load(f))
    if a.op == "cmd":
        for l in rig.send(json.loads(a.json)):
            print(json.dumps(l))
    elif a.op == "run":
        sys.exit(run_scenarios(rig, a))
    elif a.op == "start":
        sys.exit(0 if rig.start() else 1)
    elif a.op == "stop":
        rig.stop()
    elif a.op == "alive":
        sys.exit(0 if rig.alive() else 1)


if __name__ == "__main__":
    main()
