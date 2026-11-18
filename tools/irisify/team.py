"""AI-first coordination: agents report what they're doing, features track their state, and agents ask the human
for the things only a human can do. The dashboard only visualizes this; the agent drives.

.irisify/agents.jsonl    {"agent", "event": "start|status|done|blocked", "feature", "branch", "doing", "at"}
.irisify/features.json   {"<id>": {"title", "owner", "state", "scenarios", "branch", "updated"}}
.irisify/asks.jsonl      {"id", "title", "why", "command", "from", "state": "open|done|dismissed", "kind", "at"}
"""
from .project import now

FEATURE_STATES = ["idea", "design", "building", "testing", "merged", "in-headset", "done", "parked"]


# ---------- agents ----------

def report(project, agent, event="status", doing=None, feature=None, branch=None, session=None):
    rec = {"agent": agent, "event": event, "doing": doing, "feature": feature, "branch": branch, "session": session}
    rec = project.append("agents.jsonl", {k: v for k, v in rec.items() if v is not None})
    if feature and event in ("start", "status", "blocked"):
        f = project.read("features.json", {})
        if feature in f:
            f[feature]["owner"] = agent
            f[feature]["updated"] = now()
            if f[feature].get("state") in ("idea", "design") and event == "start":
                f[feature]["state"] = "building"
            project.write("features.json", f)
    return rec


def agents(project):
    """Latest state per agent, with a short trail of what it did."""
    by = {}
    for l in project.lines("agents.jsonl"):
        a = by.setdefault(l["agent"], {"agent": l["agent"], "trail": []})
        for k in ("feature", "branch", "session"):
            if l.get(k):
                a[k] = l[k]
        if l.get("doing"):
            a["doing"] = l["doing"]
            a["trail"] = (a["trail"] + [{"at": l["at"], "doing": l["doing"]}])[-8:]
        a["state"] = {"start": "working", "status": "working", "done": "idle", "blocked": "blocked"}.get(l["event"], "working")
        a["at"] = l["at"]
    return sorted(by.values(), key=lambda a: a["at"], reverse=True)


# ---------- features ----------

def set_feature(project, fid, title=None, state=None, owner=None, scenarios=None, branch=None, note=None):
    if state and state not in FEATURE_STATES:
        raise SystemExit(f"state must be one of {', '.join(FEATURE_STATES)}")
    f = project.read("features.json", {})
    cur = f.get(fid, {"title": title or fid, "state": "idea"})
    for k, v in {"title": title, "state": state, "owner": owner, "scenarios": scenarios, "branch": branch, "note": note}.items():
        if v is not None:
            cur[k] = v
    cur["updated"] = now()
    f[fid] = cur
    project.write("features.json", f)
    return cur


# ---------- asks (the agent asks the human) ----------

def ask(project, title, why=None, command=None, frm=None, kind="do", ask_id=None):
    """kind: do (a step only the human can take), decide (a choice; put options in `command`), check (in the headset)."""
    open_ = {a["id"]: a for a in asks(project) if a["state"] == "open"}
    for a in open_.values():
        if a["title"] == title:
            return a  # don't ask twice
    rec = {"id": ask_id or f"a{len(project.lines('asks.jsonl')) + 1}", "title": title, "why": why, "command": command,
           "from": frm, "kind": kind, "state": "open"}
    return project.append("asks.jsonl", {k: v for k, v in rec.items() if v is not None})


def resolve(project, ask_id, state="done", answer=None, by="user"):
    return project.append("asks.jsonl", {"id": ask_id, "state": state, "answer": answer, "by": by})


def asks(project):
    by = {}
    for l in project.lines("asks.jsonl"):
        cur = by.setdefault(l["id"], {"created": l["at"]})
        cur.update({k: v for k, v in l.items() if v is not None})
    return sorted(by.values(), key=lambda a: a["created"])


def asks_from_machine_steps(project, status):
    """Machine setup steps that need the human become asks, so the agent's checks turn into a to-do list."""
    made = []
    for name, st in status.items():
        for s in st.get("steps", []):
            if s.get("who") == "you" and s.get("done") is False:
                made.append(ask(project, f"{name}: {s['what']}", why=s.get("why"), command=s.get("fix"), frm="machine check",
                                ask_id=f"setup-{name}-{s['id']}"))
            elif s.get("done") and any(a["id"] == f"setup-{name}-{s['id']}" and a["state"] == "open" for a in asks(project)):
                resolve(project, f"setup-{name}-{s['id']}", by="machine check")
    return made
