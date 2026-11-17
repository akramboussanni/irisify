"""Intake: the question bank, detected facts, and recorded answers (.irisify/intake.json)."""
import json
import os

from .project import REPO, now


def questions():
    with open(os.path.join(REPO, "intake", "questions.json")) as f:
        return json.load(f)


def state(project):
    st = project.read("intake.json", {"answers": {}, "detected": {}})
    st.setdefault("detected", {})
    q = questions()
    open_q = [x for x in q if x["id"] not in st["answers"] and x["rank"] != "taste"]
    nxt = [x for x in open_q if x["rank"] == "blocking"][:4] or [x for x in open_q][:4]
    return {"questions": q, "answers": st["answers"], "detected": st["detected"], "next_round": [x["id"] for x in nxt]}


def answer(project, key, value, source="user", why=None):
    st = project.read("intake.json", {"answers": {}, "detected": {}})
    rec = {"value": value, "source": source, "at": now()}
    if why:
        rec["why"] = why
    st["answers"][key] = rec
    project.write("intake.json", st)
    return rec


def detected(project, key, value, evidence):
    st = project.read("intake.json", {"answers": {}, "detected": {}})
    st.setdefault("detected", {})[key] = {"value": value, "evidence": evidence, "at": now()}
    project.write("intake.json", st)
