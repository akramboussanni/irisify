"""Irisify dashboard server. Python stdlib only; reads and writes the project's .irisify/ folder.

  irisify dashboard [--port 7420]      (binds 127.0.0.1; use --host 0.0.0.0 to reach it over Tailscale)

POSTs need the header `X-Irisify: 1`: a custom header forces a CORS preflight, which this server never answers,
so other web pages can't trigger suite runs or SSH commands through your browser.
"""
import json
import mimetypes
import os
import sys
import threading
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))

from irisify import intake, machines, results, runner, suites, workflow  # noqa: E402
from irisify.cli import issues_merged  # noqa: E402
from irisify.project import now  # noqa: E402

JOBS = {}
LOCK = threading.Lock()


def job(name, fn, *args):
    def run():
        try:
            JOBS[name] = {"state": "running", "at": now()}
            res = fn(*args)
            JOBS[name] = {"state": "done", "at": now(), "result": res}
        except BaseException as e:  # SystemExit carries the refusal text
            JOBS[name] = {"state": "failed", "at": now(), "error": str(e) or traceback.format_exc()[-800:]}
    with LOCK:
        if JOBS.get(name, {}).get("state") == "running":
            return False
        JOBS[name] = {"state": "running", "at": now()}
    threading.Thread(target=run, daemon=True).start()
    return True


def run_summaries(p):
    runs = results.list_runs(p)
    out = []
    for r in runs:
        plan = p.read(os.path.join("plans", r["id"] + ".json"), {}) or {}
        out.append({"id": r["id"], "machine": r["machine"], "suite": r.get("suite") or plan.get("suite"), "build": r["build"],
                    "build_inferred": r.get("build_inferred"), "imported": r["imported"], "counts": r["counts"],
                    "comfort_events": sum(s["metrics"].get("comfort_events", 0) for s in r["scenarios"]),
                    "scenarios": [{"name": s["scenario"], "result": s["result"], "owner": s.get("owner"),
                                   "why": (plan.get("why") or {}).get(s["base"]),
                                   "fails": [c["check"] for c in s["checks"] if not c.get("ok")][:3],
                                   "shots": len(s["shots"])} for s in r["scenarios"]]})
    return out, runs


def shots_index(runs, reviews):
    """Latest shot per (scenario, moment), with the previous build's same moment for before/after."""
    seen = {}
    for r in runs:
        for s in r["scenarios"]:
            for sh in s["shots"]:
                key = f"{s['base']}/{sh['moment']}"
                entry = {"run": r["id"], "build": r["build"].get("id"), "file": sh["file"], "present": sh.get("present", False),
                         "question": sh.get("question"), "scenario": s["base"], "moment": sh["moment"], "owner": s.get("owner"),
                         "review": reviews.get(f"{r['id']}/{sh['file']}")}
                prev = seen.get(key)
                if prev and prev["build"] != entry["build"]:
                    entry["before"] = {k: prev[k] for k in ("run", "build", "file", "present")}
                elif prev and prev.get("before"):
                    entry["before"] = prev["before"]
                seen[key] = entry
    vals = [e for e in seen.values() if e["present"] or (e.get("before") or {}).get("present")]
    return sorted(vals, key=lambda e: (e["review"] is not None, e["scenario"], e["moment"]))


def overview(p):
    summaries, runs = run_summaries(p)
    deploys = {}
    for d in p.lines("deploys.jsonl"):
        deploys[d["machine"]] = d
    issues = issues_merged(p)
    reviews = p.read("shot-reviews.json", {})
    try:
        suite_list = []
        for name in list(suites.BUILTIN) + list(suites.load_suites(p)):
            if name == "flaky-hunt":
                suite_list.append({"name": name, "count": None, "minutes": None, "needs": "scenario"})
                continue
            sel = suites.select(p, name)
            suite_list.append({"name": name, "count": len(sel["scenarios"]), "minutes": suites.estimate_minutes(p, sel["scenarios"]),
                               "description": suites.load_suites(p).get(name, {}).get("description")})
    except SystemExit as e:
        suite_list = [{"error": str(e)}]
    return {
        "project": dict(p.config(), root=p.root), "workflow": workflow.status(p),
        "machines": machines.load(p)["machines"], "machines_status": p.read("machines-status.json", {}),
        "preflight": p.read("preflight.json", {}), "deploys": deploys, "runs": summaries[-40:],
        "flaky": results.flaky(runs), "issues": issues, "shots": shots_index(runs, reviews)[:120],
        "checklist": results.headset_checklist(runs, issues), "intake": intake.state(p),
        "suites": suite_list, "signoffs": p.read("signoffs.json", {}), "jobs": JOBS,
        "activity": p.lines("activity.jsonl")[-20:], "profiles": profile_list(),
    }


def profile_list():
    from irisify import controllers
    return [{"type": t, "name": pr.get("name"), "notes": pr.get("notes", []), "supported": t in ("frame_controller", "knuckles"),
             "display": pr.get("display")} for t, pr in controllers.load_profiles().items()]


class Handler(BaseHTTPRequestHandler):
    project = None

    def log_message(self, fmt, *args):
        pass

    def send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def file(self, path):
        if not os.path.isfile(path):
            return self.send(404, {"error": "not found"})
        with open(path, "rb") as f:
            self.send(200, f.read(), mimetypes.guess_type(path)[0] or "application/octet-stream")

    def do_GET(self):
        p = self.project
        u = urlparse(self.path)
        parts = [unquote(x) for x in u.path.split("/") if x]
        try:
            if not parts:
                return self.file(os.path.join(HERE, "static", "index.html"))
            if parts[0] == "static" and len(parts) == 2 and "/" not in parts[1] and not parts[1].startswith("."):
                return self.file(os.path.join(HERE, "static", parts[1]))
            if parts == ["api", "overview"]:
                return self.send(200, overview(p))
            if parts[:2] == ["api", "run"] and len(parts) == 3:
                r = p.read(os.path.join("runs", os.path.basename(parts[2]), "run.json"))
                return self.send(200 if r else 404, r or {"error": "no such run"})
            if parts[0] == "shots" and len(parts) == 3:
                return self.file(p.path("runs", os.path.basename(parts[1]), "shots", os.path.basename(parts[2])))
        except Exception as e:
            return self.send(500, {"error": str(e)})
        self.send(404, {"error": "not found"})

    def do_POST(self):
        if self.headers.get("X-Irisify") != "1":
            return self.send(403, {"error": "missing X-Irisify header"})
        p = self.project
        n = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(n) or b"{}")
        path = urlparse(self.path).path
        try:
            if path == "/api/machine/add":
                m = machines.add(p, body["name"], body["roles"], body["link"], body.get("host"), body.get("os"),
                                 body.get("headset"), body.get("game_dir"))
                job(f"check:{body['name']}", machines.check_all, p, body["name"])
                return self.send(200, m)
            if path == "/api/machine/check":
                started = job(f"check:{body.get('name') or 'all'}", machines.check_all, p, body.get("name"))
                return self.send(200, {"started": started})
            if path == "/api/suite":
                if body.get("dry"):
                    return self.send(200, runner.run_suite(p, body["name"], body.get("machine"), body.get("scenario"), dry=True))
                started = job(f"suite:{body['name']}", runner.run_suite, p, body["name"], body["machine"], body.get("scenario"))
                return self.send(200, {"started": started})
            if path == "/api/sync":
                started = job(f"sync:{body['machine']}", runner.sync, p, body["machine"])
                return self.send(200, {"started": started})
            if path == "/api/review":
                r = p.read("shot-reviews.json", {})
                r[f"{body['run']}/{body['file']}"] = {"verdict": body["verdict"], "answer": body.get("answer", ""), "by": "user", "at": now()}
                p.write("shot-reviews.json", r)
                if body["verdict"] == "flag":
                    p.append("issues.jsonl", {"id": f"shot-{body['run']}-{body['file']}", "title": f"screenshot {body.get('moment') or body['file']}: {body.get('answer') or 'flagged'}",
                                              "owner": body.get("owner"), "state": "open", "source": "user", "run": body["run"]})
                return self.send(200, {"ok": True})
            if path == "/api/intake":
                return self.send(200, intake.answer(p, body["id"], body["value"], source=body.get("source", "user"), why=body.get("why")))
            if path == "/api/signoff":
                s = p.read("signoffs.json", {})
                s[body["what"]] = {"at": now(), "by": "user", "note": body.get("note")}
                p.write("signoffs.json", s)
                return self.send(200, s[body["what"]])
            if path == "/api/issue":
                rec = {"id": body.get("id") or f"i-{len(p.lines('issues.jsonl')) + 1}", "title": body["title"],
                       "owner": body.get("owner"), "state": body.get("state", "open"), "source": body.get("source", "user")}
                return self.send(200, p.append("issues.jsonl", rec))
        except SystemExit as e:
            return self.send(409, {"error": str(e)})
        except (KeyError, ValueError) as e:
            return self.send(400, {"error": f"bad request: {e}"})
        self.send(404, {"error": "not found"})


def serve(project, host="127.0.0.1", port=7420):
    Handler.project = project
    srv = ThreadingHTTPServer((host, port), Handler)
    print(f"Irisify dashboard for {project.root}: http://{host}:{port}/")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    from irisify.project import Project
    serve(Project.open(), port=int(os.environ.get("PORT", 7420)))
