"""irisify: the command line. Every command reads and writes .irisify/ in the mod repo."""
import argparse
import json
import os
import shutil
import sys

from . import controllers, deploy, doctor, intake, machines, results, runner, suites, team, workflow
from .project import REPO, Project, load_structured, now


def out(obj, as_json):
    if as_json or not isinstance(obj, (str, list)):
        print(json.dumps(obj, indent=1) if not isinstance(obj, str) else obj)
    else:
        print("\n".join(obj) if isinstance(obj, list) else obj)


def cmd_init(a):
    p = Project.open(a.path, create=True)
    cfg = p.config()
    cfg.update({k: v for k, v in {"game": a.game, "steam_appid": a.appid, "engine": a.engine,
                                  "integration_branch": a.integration_branch}.items() if v})
    cfg.setdefault("integration_branch", "main")
    cfg.setdefault("build", {"cmd": "", "output": "build", "stamp_to": "build/BepInEx/plugins/irisify/build.json"})
    p.write("project.json", cfg)
    d = os.path.join(p.root, "design")
    tdir = os.path.join(REPO, "skill", "templates", "design")
    os.makedirs(d, exist_ok=True)
    made = []
    for f in sorted(os.listdir(tdir)):
        if not os.path.exists(os.path.join(d, f)):
            shutil.copy(os.path.join(tdir, f), os.path.join(d, f))
            made.append(f)
    for sub in ("scenarios", "suites"):
        os.makedirs(os.path.join(p.root, sub), exist_ok=True)
    src = os.path.join(REPO, "suites")
    for f in os.listdir(src):
        if not os.path.exists(os.path.join(p.root, "suites", f)):
            shutil.copy(os.path.join(src, f), os.path.join(p.root, "suites", f))
    print(f"Irisify project at {p.root}\n  design templates: {', '.join(made) or 'already there'}\n"
          f"  next: irisify machine add ... ; irisify status")


def cmd_status(a):
    p = Project.open()
    st = workflow.status(p)
    if a.json:
        return out(st, True)
    for ph in st["phases"]:
        mark = "✓" if ph["ok"] else ("→" if ph["id"] == st["current"] else "·")
        print(f" {mark} {ph['title']:<20} {'; '.join(ph['evidence'])[:110]}")
    cur = next((x for x in st["phases"] if x["id"] == st["current"]), None)
    if cur:
        print(f"\nnext: {cur['next']}")


def cmd_machine(a):
    p = Project.open()
    if a.op == "add":
        m = machines.add(p, a.name, a.roles.split(","), a.link, a.host, a.os, a.headset, a.game_dir)
        print(json.dumps({a.name: m}, indent=1))
    elif a.op == "list":
        out(machines.load(p), True)
    elif a.op in ("check", "setup"):
        st = machines.check_all(p, a.name)
        team.asks_from_machine_steps(p, st)
        for n, s in st.items():
            if a.name and n != a.name:
                continue
            print(f"{n}: {'reachable' if s.get('reachable') else 'NOT reachable'} via {s.get('link')} {s.get('host') or ''}"
                  + (f"  ({s.get('error')})" if s.get("error") else ""))
            for stp in s["steps"]:
                mark = "✓" if stp["done"] else ("?" if stp["done"] is None else "✗")
                print(f"   {mark} [{stp['who']}] {stp['what']}" + (f"\n        fix: {stp['fix']}" if not stp["done"] and stp.get("fix") else ""))


def cmd_doctor(a):
    p = Project.open()
    rep = doctor.platform(p, a.machine, a.appid) if a.what == "platform" else doctor.input_focus(p, a.machine, a.appid, a.log)
    for c in rep["checks"]:
        aid = f"doctor-{a.machine}-{c['id']}"
        if c["ok"] is False and c.get("who", "you") == "you":
            team.ask(p, f"{a.machine}: {c['what']}", why=f"found: {c.get('found')}", command=c.get("fix"), frm="doctor", ask_id=aid)
        elif c["ok"] and any(x["id"] == aid and x["state"] == "open" for x in team.asks(p)):
            team.resolve(p, aid, by="doctor")
    if a.json:
        return out(rep, True)
    for c in rep["checks"]:
        mark = {True: "✓", False: "✗", None: "?"}[c["ok"]]
        print(f" {mark} {c['what']}: {c.get('found')}" + (f"\n     fix ({c.get('who', 'you')}): {c['fix']}" if c.get("fix") else ""))


def cmd_controllers(a):
    if a.op == "profiles":
        for t, pr in controllers.load_profiles().items():
            comps = [k for k in controllers.profile_components(pr)]
            print(f"{t:<24} {pr.get('name')}: {', '.join(comps)}")
        return
    if a.op == "detect":
        p = Project.open()
        m = machines.load(p)["machines"][a.machine]
        rc, o, e = machines.link_for(m).run(controllers.DETECT_SCRIPT, timeout=60)
        texts, profs = controllers.parse_detect_output(o)
        logp = p.config().get("log_path")
        if logp:
            rc2, o2, _ = machines.link_for(m).run(f"tail -c 300000 {machines.remote_path(logp)}", timeout=30)
            texts.insert(0, (logp, o2))
        det = controllers.detect_from_text(texts) or {}
        det["profiles_on_machine"] = profs
        if det.get("controller_type"):
            want = [x for x in profs if x.endswith(f"/{det['controller_type']}_profile.json")]
            if want:
                rc3, o3, _ = machines.link_for(m).run(f"cat {machines.remote_path(want[0])}", timeout=30)
                import tempfile
                with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
                    f.write(o3)
                det["runtime_profile"] = controllers.profile_from_runtime_file(f.name)
                det["runtime_profile"]["source"] = f"{a.machine}:{want[0]}"
                os.unlink(f.name)
            intake.detected(p, "controller_type", det["controller_type"], det.get("evidence"))
        p.write("controller-profile.json", det)
        if a.json:
            return out(det, True)
        print(f"controller: {det.get('controller_type') or 'not found'} ({det.get('confidence', '-')}) — {det.get('evidence', '')}")
        if det.get("runtime_profile"):
            print("components: " + ", ".join(controllers.profile_components(det["runtime_profile"])))
        return
    c = controllers.load_controls(a.controls)
    if a.op == "lint":
        inter = load_structured(a.interactions) if a.interactions else None
        errors, warnings = controllers.lint(c, interactions=inter)
        for e in errors:
            print(f"error: {e}")
        for w in warnings:
            print(f"warn:  {w}")
        print(f"{len(errors)} errors, {len(warnings)} warnings")
        sys.exit(1 if errors else 0)
    if a.op == "table":
        print(controllers.context_table(c))
    elif a.op in ("bindings", "prompts"):
        rep = controllers.write_outputs(c, a.out, a.types.split(",") if a.types else None, kind=a.op)
        if a.op == "bindings":
            for t, lost in rep.items():
                print(f"bindings_{t}.json" + (f"  (no input on this controller for: {', '.join(sorted({l['action'] for l in lost}))})" if lost else ""))
            print("default_bindings.json: merge into your actions.json 'default_bindings'")
        else:
            print(f"prompts for {', '.join(rep)} + PROMPTS.md in {a.out}")


def cmd_suite(a):
    p = Project.open()
    if a.op == "list":
        meta = suites.load_scenarios(p)
        for name in list(suites.BUILTIN) + list(suites.load_suites(p)):
            try:
                sel = suites.select(p, name, scenario=a.scenario or (next(iter(meta), None) if name == "flaky-hunt" else None))
                print(f"{name:<14} {len(sel['scenarios']):>3} scenarios  ~{suites.estimate_minutes(p, sel['scenarios'])} min")
            except SystemExit as e:
                print(f"{name:<14} ({e})")
        return
    if a.op == "plan" or a.dry:
        sel = runner.run_suite(p, a.name, a.machine, a.scenario, a.seed, dry=True)
        if a.json:
            return out(sel, True)
        print(f"{a.name}: {len(sel['scenarios'])} scenarios, ~{sel['minutes']} min" + (f", seed {sel['seed']}" if sel["seed"] is not None else ""))
        for n in sel["scenarios"]:
            o = sel.get("options", {}).get(n, {})
            extra = "  ".join(x for x in (o.get("save"), o.get("set") and o["set"] + " set", o.get("cap") and f"cap {o['cap']}s") if x)
            print(f"  {n:<28} {sel['why'].get(n, ''):<34} {extra}")
        return
    res = runner.run_suite(p, a.name, a.machine, a.scenario, a.seed)
    if a.json:
        return out(res, True)
    print(f"{a.name} on {a.machine}: run {res.get('run')} rc={res.get('rc')} (planned ~{res['minutes']} min)")
    for rid in res.get("imported", []):
        r = p.read(os.path.join("runs", rid, "run.json")) or {}
        for sc in sorted(r.get("scenarios", []), key=lambda x: -(x.get("seconds") or 0)):
            print(f"  {(sc.get('seconds') or 0):7.1f}s  {sc['result']:<5} {sc['scenario']}")


def cmd_sync(a):
    p = Project.open()
    print(json.dumps(runner.sync(p, a.machine, a.build)))


def cmd_import(a):
    p = Project.open()
    made = results.import_file(p, a.machine, a.results, a.shots, build=a.build, suite=a.suite)
    print(f"imported {len(made)} runs: {', '.join(made)}")


def cmd_gate(a):
    p = Project.open()
    if a.op == "first-boot":
        with open(a.log, errors="replace") as f:
            text = f.read()
        rec = workflow.first_boot_from_log(p, text, a.build)
        out(rec, True)
        return
    g = workflow.GATES[a.name](p)
    out({a.name: g}, True)
    sys.exit(0 if g["ok"] else 1)


def cmd_signoff(a):
    p = Project.open()
    s = p.read("signoffs.json", {})
    s[a.what] = {"at": now(), "by": a.by, "note": a.note}
    p.write("signoffs.json", s)
    print(f"signed off {a.what}")


def cmd_shots(a):
    p = Project.open()
    r = p.read("shot-reviews.json", {})
    r[f"{a.run}/{a.file}"] = {"verdict": a.verdict, "answer": a.answer, "by": a.by, "at": now()}
    p.write("shot-reviews.json", r)
    if a.verdict == "flag":
        p.append("issues.jsonl", {"id": f"shot-{a.run}-{a.file}", "title": f"screenshot {a.file}: {a.answer}", "state": "open",
                                  "owner": a.owner, "run": a.run, "source": "screenshot"})
    print("recorded")


def cmd_issue(a):
    p = Project.open()
    if a.op == "add":
        rec = p.append("issues.jsonl", {"id": a.id or f"i-{len(p.lines('issues.jsonl')) + 1}", "title": a.title, "owner": a.owner,
                                        "state": "open", "source": a.source, "scenario": a.scenario})
        print(json.dumps(rec))
    elif a.op == "close":
        p.append("issues.jsonl", {"id": a.id, "state": "closed", "build": a.build})
        print("closed")
    else:
        for i in issues_merged(p):
            print(f"{i['state']:<7} {i.get('owner') or '-':<16} {i['title']}")


def issues_merged(p):
    by = {}
    for l in p.lines("issues.jsonl"):
        by.setdefault(l["id"], {}).update({k: v for k, v in l.items() if v is not None})
    return list(by.values())


def cmd_intake(a):
    p = Project.open()
    if a.op == "set":
        for kv in a.pairs:
            k, v = kv.split("=", 1)
            intake.answer(p, k, v, source=a.source, why=a.why)
        print("saved")
    else:
        st = intake.state(p)
        print("next round: " + ", ".join(st["next_round"]))
        for q in st["questions"]:
            ans = st["answers"].get(q["id"])
            print(f" [{q['rank']:<8}] {q['q']}  ->  {ans['value'] + ' (' + ans['source'] + ')' if ans else 'recommend: ' + str(q.get('recommend'))}")


def cmd_deploy(a):
    p = Project.open()
    print(json.dumps(deploy.deploy(p, a.machine, force=a.force), indent=1))


def cmd_integrate(a):
    p = Project.open()
    print(json.dumps(deploy.integrate(p, a.branches.split(",") if a.branches else None, a.force, a.suite, a.rig), indent=1))


def cmd_verify(a):
    p = Project.open()
    print(json.dumps(deploy.verify_branch(p, a.ref, a.suite, a.machine, a.rig_branch), indent=1))


def cmd_fanout(a):
    p = Project.open()
    workflow.require(p, "fanout", a.force)
    print("gates passed: fan out. Give every worker skill/references/integration.md and notes/conventions.md.")


def cmd_scenarios(a):
    p = Project.open()
    errors, warnings = suites.lint_scenarios(p)
    for e in errors:
        print(f"error: {e}")
    for w in warnings:
        print(f"warn:  {w}")
    print(f"{len(errors)} errors, {len(warnings)} warnings")
    sys.exit(1 if errors else 0)


def cmd_agent(a):
    p = Project.open()
    if a.op == "list":
        for x in team.agents(p):
            print(f"{x['state']:<8} {x['agent']:<20} {x.get('feature') or '-':<22} {x.get('doing') or ''}")
        return
    print(json.dumps(team.report(p, a.name, a.op, a.doing, a.feature, a.branch, a.session)))


def cmd_feature(a):
    p = Project.open()
    if a.op == "list":
        for fid, f in p.read("features.json", {}).items():
            print(f"{f.get('state', ''):<11} {fid:<24} {f.get('owner') or '-':<18} {f.get('title', '')}")
        return
    print(json.dumps(team.set_feature(p, a.id, a.title, a.state, a.owner, a.scenarios.split(",") if a.scenarios else None, a.branch, a.note)))


def cmd_ask(a):
    p = Project.open()
    if a.op == "list":
        for x in team.asks(p):
            if x["state"] == "open" or a.all:
                print(f"{x['state']:<9} {x['id']:<26} {x['title']}" + (f"\n          $ {x['command']}" if x.get("command") else ""))
        return
    if a.op in ("done", "dismiss"):
        print(json.dumps(team.resolve(p, a.text, "done" if a.op == "done" else "dismissed", a.answer, by=a.by)))
        return
    print(json.dumps(team.ask(p, a.text, a.why, a.command, a.frm, a.kind)))


def cmd_patchcheck(a):
    from . import patchcheck
    hits = patchcheck.scan(a.decomp, a.src)
    for h in hits:
        print(f"{h['file']}:{h['line']}: {h['class']}.{h['method']} is only implemented explicitly; target {' or '.join(h['use'])}")
    print(f"{len(hits)} suspicious patch targets")
    sys.exit(1 if hits else 0)


def cmd_failsafe(a):
    from . import patchcheck
    hits = patchcheck.failsafe_scan(a.src)
    for h in hits:
        print(f"{h['file']}:{h['line']}: {h['setting']} written from an error path; use FeatureSuspend.TurnOff (lessons A13)")
    print(f"{len(hits)} persisted fail-safes")
    sys.exit(1 if hits else 0)


def cmd_dashboard(a):
    sys.path.insert(0, os.path.join(REPO, "dashboard"))
    import server  # noqa
    server.serve(Project.open(), a.host, a.port)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="irisify", description="Flat game → deep VR, with gates.")
    ap.add_argument("--json", action="store_true")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("init", help="make this mod repo an Irisify project")
    s.add_argument("path", nargs="?")
    s.add_argument("--game"); s.add_argument("--appid", type=int); s.add_argument("--engine"); s.add_argument("--integration-branch")
    s.set_defaults(f=cmd_init)

    sub.add_parser("status", help="phase, gates, next action").set_defaults(f=cmd_status)

    s = sub.add_parser("machine", help="machines, roles, links")
    s.add_argument("op", choices=["add", "list", "check", "setup"]); s.add_argument("name", nargs="?")
    s.add_argument("--roles", default="game-host"); s.add_argument("--link", default="ssh"); s.add_argument("--host")
    s.add_argument("--os"); s.add_argument("--headset"); s.add_argument("--game-dir")
    s.set_defaults(f=cmd_machine)

    s = sub.add_parser("doctor", help="platform preflight / input focus")
    s.add_argument("what", choices=["platform", "input-focus"]); s.add_argument("--machine", required=True)
    s.add_argument("--appid", type=int); s.add_argument("--log")
    s.set_defaults(f=cmd_doctor)

    s = sub.add_parser("controllers", help="detect, lint, bindings, prompts")
    s.add_argument("op", choices=["profiles", "detect", "lint", "table", "bindings", "prompts"])
    s.add_argument("controls", nargs="?", default="design/controls.json"); s.add_argument("interactions", nargs="?")
    s.add_argument("--machine"); s.add_argument("--out", default="generated"); s.add_argument("--types")
    s.set_defaults(f=cmd_controllers)

    s = sub.add_parser("suite", help="plan or run a suite on a rig")
    s.add_argument("op", choices=["run", "plan", "list"]); s.add_argument("name", nargs="?", default="auto")
    s.add_argument("--machine"); s.add_argument("--scenario"); s.add_argument("--seed", type=int); s.add_argument("--dry", action="store_true")
    s.set_defaults(f=cmd_suite)

    s = sub.add_parser("sync", help="pull results and screenshots from a rig")
    s.add_argument("--machine", required=True); s.add_argument("--build")
    s.set_defaults(f=cmd_sync)

    s = sub.add_parser("import", help="import a local results.jsonl (e.g. from an older rig)")
    s.add_argument("results"); s.add_argument("--shots"); s.add_argument("--machine", default="rig"); s.add_argument("--build"); s.add_argument("--suite")
    s.set_defaults(f=cmd_import)

    s = sub.add_parser("gate", help="check a gate, or record first-boot evidence from a log")
    s.add_argument("op", choices=["check", "first-boot"]); s.add_argument("name", nargs="?", choices=list(workflow.GATES))
    s.add_argument("--log"); s.add_argument("--build")
    s.set_defaults(f=cmd_gate)

    s = sub.add_parser("signoff", help="record the user's sign-off (design, slice)")
    s.add_argument("what"); s.add_argument("--by", default="user"); s.add_argument("--note")
    s.set_defaults(f=cmd_signoff)

    s = sub.add_parser("shots", help="review a screenshot")
    s.add_argument("op", choices=["review"]); s.add_argument("run"); s.add_argument("file")
    s.add_argument("verdict", choices=["ok", "flag", "rig"]); s.add_argument("answer")
    s.add_argument("--by", default="agent"); s.add_argument("--owner")
    s.set_defaults(f=cmd_shots)

    s = sub.add_parser("issue", help="issues routed to owners")
    s.add_argument("op", choices=["add", "close", "list"]); s.add_argument("title", nargs="?")
    s.add_argument("--id"); s.add_argument("--owner"); s.add_argument("--source", default="agent"); s.add_argument("--scenario"); s.add_argument("--build")
    s.set_defaults(f=cmd_issue)

    s = sub.add_parser("intake", help="show or record intake answers")
    s.add_argument("op", choices=["show", "set"]); s.add_argument("pairs", nargs="*")
    s.add_argument("--source", default="user"); s.add_argument("--why")
    s.set_defaults(f=cmd_intake)

    s = sub.add_parser("deploy", help="deploy the integration build to a machine (locked, stamped)")
    s.add_argument("--machine", required=True); s.add_argument("--force")
    s.set_defaults(f=cmd_deploy)

    s = sub.add_parser("integrate", help="merge, build, deploy to the rig, run a suite")
    s.add_argument("--branches"); s.add_argument("--suite", default="auto"); s.add_argument("--rig"); s.add_argument("--force")
    s.set_defaults(f=cmd_integrate)

    s = sub.add_parser("verify-branch", help="test a worker's branch on the rig without touching it")
    s.add_argument("ref"); s.add_argument("suite"); s.add_argument("--machine", required=True); s.add_argument("--rig-branch")
    s.set_defaults(f=cmd_verify)

    s = sub.add_parser("fanout", help="check the gates before starting parallel workers")
    s.add_argument("--force")
    s.set_defaults(f=cmd_fanout)

    s = sub.add_parser("agent", help="agents report what they're doing (the dashboard shows it)")
    s.add_argument("op", choices=["start", "status", "done", "blocked", "list"]); s.add_argument("name", nargs="?")
    s.add_argument("doing", nargs="?"); s.add_argument("--feature"); s.add_argument("--branch"); s.add_argument("--session")
    s.set_defaults(f=cmd_agent)

    s = sub.add_parser("feature", help="features and their state")
    s.add_argument("op", choices=["set", "list"]); s.add_argument("id", nargs="?")
    s.add_argument("--title"); s.add_argument("--state", choices=team.FEATURE_STATES); s.add_argument("--owner")
    s.add_argument("--scenarios"); s.add_argument("--branch"); s.add_argument("--note")
    s.set_defaults(f=cmd_feature)

    s = sub.add_parser("ask", help="ask the human to do or decide something (shows on the dashboard)")
    s.add_argument("op", choices=["new", "list", "done", "dismiss"]); s.add_argument("text", nargs="?", help="the request, or the ask id for done/dismiss")
    s.add_argument("--why"); s.add_argument("--command"); s.add_argument("--kind", default="do", choices=["do", "decide", "check"])
    s.add_argument("--from", dest="frm"); s.add_argument("--answer"); s.add_argument("--by", default="agent"); s.add_argument("--all", action="store_true")
    s.set_defaults(f=cmd_ask)

    s = sub.add_parser("scenarios", help="lint scenario metadata (owners, questions, worst-case coverage)")
    s.add_argument("op", choices=["lint"])
    s.set_defaults(f=cmd_scenarios)

    s = sub.add_parser("patchcheck", help="find patch targets that are explicit interface methods")
    s.add_argument("decomp"); s.add_argument("src")
    s.set_defaults(f=cmd_patchcheck)

    s = sub.add_parser("failsafe", help="find catch blocks that write settings (fail-safes that persist)")
    s.add_argument("src")
    s.set_defaults(f=cmd_failsafe)

    s = sub.add_parser("dashboard", help="serve the dashboard")
    s.add_argument("--host", default="127.0.0.1"); s.add_argument("--port", type=int, default=7420)
    s.set_defaults(f=cmd_dashboard)

    a = ap.parse_args(argv)
    if getattr(a, "cmd", None) == "suite" and a.op == "run" and not a.machine and not a.dry:
        p = Project.open()
        a.machine = next((n for n, m in machines.load(p)["machines"].items() if "rig" in m.get("roles", [])), None)
        if not a.machine:
            raise SystemExit("no rig machine: irisify machine add <name> --roles rig ...")
    a.f(a)


if __name__ == "__main__":
    main()
