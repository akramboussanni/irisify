"""Build stamping, locked deploys, the integration loop and verify-branch.

One writer per target (lessons A2): a deploy needs the integration branch, a clean tree and the target's lock.
Every deploy is recorded in .irisify/deploys.jsonl with the build, so the dashboard knows what runs where.
"""
import json
import os
import shutil
import subprocess
import tempfile
import time

from . import machines, workflow
from .project import now


def git(root, *args, check=True):
    p = subprocess.run(["git", "-C", root] + list(args), capture_output=True, text=True)
    if check and p.returncode != 0:
        raise SystemExit(f"git {' '.join(args)}: {p.stderr.strip()}")
    return p.stdout.strip()


def build_record(root, merged=None):
    return {"id": git(root, "rev-parse", "--short", "HEAD"), "commit": git(root, "rev-parse", "HEAD"),
            "describe": git(root, "describe", "--always", "--dirty", check=False),
            "branch": git(root, "rev-parse", "--abbrev-ref", "HEAD"), "at": now(), "merged": merged or []}


def run_build(project, root=None):
    cfg = project.config()
    cmd = cfg.get("build", {}).get("cmd")
    if not cmd:
        raise SystemExit("set build.cmd in .irisify/project.json (e.g. \"cd SubmersedVR && dotnet build -nologo -v q\")")
    p = subprocess.run(["bash", "-lc", cmd], cwd=root or project.root, capture_output=True, text=True)
    out = (p.stdout + p.stderr)[-3000:]
    if p.returncode != 0:
        raise SystemExit(f"build failed:\n{out}")
    return out


def stamp(project, rec, root=None):
    """Write build.json into the build output so the adapter logs `[Irisify] build <id>` at boot."""
    out = project.config().get("build", {}).get("stamp_to")
    if out:
        path = os.path.join(root or project.root, out)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump(rec, f)
    return rec


LOCK_SCRIPT = r"""
L=__LOCK__
if [ -f "$L" ]; then
  AGE=$(( $(date +%s) - $(stat -c %Y "$L" 2>/dev/null || stat -f %m "$L") ))
  if [ "$AGE" -lt 1800 ] && ! grep -q "__OWNER__" "$L"; then echo "LOCKED $(cat "$L")"; exit 3; fi
fi
mkdir -p "$(dirname "$L")"; echo "__OWNER__ $(date -u +%FT%TZ)" > "$L"; echo OK
"""


def lock(link, game_dir, owner):
    path = machines.remote_path(game_dir.rstrip("/") + "/.irisify-deploy.lock")
    rc, out, err = link.run(LOCK_SCRIPT.replace("__LOCK__", path).replace("__OWNER__", owner))
    if rc == 3 or "LOCKED" in out:
        raise SystemExit(f"target is locked: {out.strip()} (another session is deploying; wait or ask it)")
    return path


def unlock(link, path):
    link.run(f"rm -f {path}")


def deploy(project, machine, force=None, owner="integrator", root=None, allow_branch=False):
    cfg = project.config()
    data = machines.load(project)
    m = data["machines"].get(machine)
    if not m:
        raise SystemExit(f"no machine '{machine}'")
    root = root or project.root
    integ = cfg.get("integration_branch", "main")
    branch = git(root, "rev-parse", "--abbrev-ref", "HEAD")
    if not allow_branch:
        workflow.require(project, "deploy", force)
        if branch != integ:
            raise SystemExit(f"deploys come from the integration branch '{integ}' (you're on '{branch}'). "
                             f"Workers: use `irisify verify-branch` on a rig machine instead (lessons A2)")
        if git(root, "status", "--porcelain", "--untracked-files=no"):
            raise SystemExit("working tree has uncommitted changes: commit first so the build id means something")
    rec = stamp(project, build_record(root), root)
    run_build(project, root)
    src = os.path.join(root, cfg.get("build", {}).get("output", "build")) + "/"
    link = machines.link_for(m)
    game_dir = m.get("game_dir")
    if not game_dir:
        raise SystemExit(f"set the game folder: irisify machine add {machine} --game-dir <path>")
    stop = cfg.get("deploy", {}).get("refuse_if_running")
    if stop:
        rc, out, err = link.run(stop)
        if rc == 0 and out.strip():
            raise SystemExit(f"the game is running on {machine}: stop it first ({out.strip()[:80]})")
    lp = lock(link, game_dir, owner)
    try:
        rc = link.push(src, game_dir.rstrip("/") + "/")
        ok = rc == 0
    finally:
        unlock(link, lp)
    project.append("deploys.jsonl", {"machine": machine, "build": rec, "ok": ok, "owner": owner, "branch": branch})
    if not ok:
        raise SystemExit("copy failed")
    return rec


def integrate(project, branches=None, force=None, suite="smoke", rig=None):
    """Merge ready branches into the integration branch, build, deploy to the rig, run a suite."""
    from . import runner
    workflow.require(project, "integrate", force)
    cfg = project.config()
    integ = cfg.get("integration_branch", "main")
    plan = project.read("integrate.json", {"branches": []})
    branches = branches or plan["branches"]
    root = project.root
    if git(root, "rev-parse", "--abbrev-ref", "HEAD") != integ:
        raise SystemExit(f"switch to '{integ}' first (integrate never switches branches for you)")
    git(root, "fetch", "--all", "--quiet", check=False)
    merged, conflicts = [], []
    for b in branches:
        p = subprocess.run(["git", "-C", root, "merge", "--no-edit", b], capture_output=True, text=True)
        if p.returncode != 0:
            subprocess.run(["git", "-C", root, "merge", "--abort"], capture_output=True)
            conflicts.append(b)
            project.append("issues.jsonl", {"id": f"merge-{b}-{int(time.time())}", "title": f"merge conflict: {b} into {integ}",
                                            "owner": b, "state": "open", "source": "integrate"})
        else:
            merged.append(b)
    rig = rig or next((n for n, m in machines.load(project)["machines"].items() if "rig" in m.get("roles", [])), None)
    out = {"merged": merged, "conflicts": conflicts}
    if rig:
        out["build"] = deploy(project, rig, force=force, owner="integrator")
        out["suite"] = runner.run_suite(project, suite, rig)
    project.append("activity.jsonl", {"what": "integrate", **{k: v for k, v in out.items() if k != "suite"}})
    return out


def verify_branch(project, ref, suite, machine, rig_branch=None):
    """A worker's branch + the rig code, built in a scratch worktree, deployed to the rig under its lock,
    the given suite run; then the integration build goes back on. The worker's branch is never changed."""
    from . import runner
    root = project.root
    wt = tempfile.mkdtemp(prefix="irisify-verify-")
    shutil.rmtree(wt)
    git(root, "worktree", "add", "-q", "--detach", wt, ref)
    try:
        if rig_branch:
            p = subprocess.run(["git", "-C", wt, "-c", "user.name=irisify", "-c", "user.email=irisify@localhost",
                                "merge", "-q", "--no-edit", rig_branch], capture_output=True, text=True)
            if p.returncode != 0:
                raise SystemExit(f"merging {rig_branch} into {ref} conflicts")
        deploy(project, machine, owner=f"verify:{ref}", root=wt, allow_branch=True)
        res = runner.run_suite(project, suite, machine)
    finally:
        git(root, "worktree", "remove", "--force", wt, check=False)
    try:
        deploy(project, machine, owner="integrator", force="restore after verify-branch")
    except SystemExit as e:
        res["restore"] = f"integration build not restored: {e}"
    return res
