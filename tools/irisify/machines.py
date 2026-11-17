"""Machines, roles and links (local, SSH, adb), plus the checks and guided setup steps for each.

`.irisify/machines.json`:
  {"machines": {"fedora": {"roles": ["game-host", "rig"], "link": "ssh", "host": "user@rig-laptop",
                           "os": "linux", "headset": "frame_controller", "game_dir": "~/.local/share/Steam/steamapps/common/Subnautica"}}}
"""
import json
import os
import shlex
import shutil
import subprocess

from .project import now

ROLES = ("dev", "game-host", "rig", "headset")
LINKS = ("local", "ssh", "adb")


class Link:
    def __init__(self, m):
        self.m = m

    def run(self, cmd, timeout=60):
        raise NotImplementedError

    def push(self, src, dst):
        raise NotImplementedError

    def pull(self, src, dst):
        raise NotImplementedError


class LocalLink(Link):
    def run(self, cmd, timeout=60):
        p = subprocess.run(["bash", "-lc", cmd], capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout, p.stderr

    def push(self, src, dst):
        dst = os.path.expanduser(dst)
        os.makedirs(os.path.dirname(dst.rstrip("/")) or ".", exist_ok=True)
        return subprocess.run(["rsync", "-a", src, dst]).returncode

    pull = push


class SshLink(Link):
    def base(self):
        return ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", self.m["host"]]

    def run(self, cmd, timeout=60):
        # One script over stdin: no nested quoting through ssh (lessons C3).
        p = subprocess.run(self.base() + ["bash", "-s"], input=cmd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout, p.stderr

    def push(self, src, dst):
        env = dict(os.environ, COPYFILE_DISABLE="1")
        return subprocess.run(["rsync", "-a", "-e", "ssh -o BatchMode=yes", src, f"{self.m['host']}:{dst}"], env=env).returncode

    def pull(self, src, dst):
        os.makedirs(dst, exist_ok=True)
        return subprocess.run(["rsync", "-a", "-e", "ssh -o BatchMode=yes", f"{self.m['host']}:{src}", dst]).returncode


class AdbLink(Link):
    def base(self):
        return ["adb", "-s", self.m["host"]]

    def connect(self):
        if ":" in self.m["host"]:
            subprocess.run(["adb", "connect", self.m["host"]], capture_output=True, timeout=15)

    def run(self, cmd, timeout=60):
        self.connect()
        p = subprocess.run(self.base() + ["shell", cmd], capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout, p.stderr

    def push(self, src, dst):
        self.connect()
        return subprocess.run(self.base() + ["push", src, dst]).returncode

    def pull(self, src, dst):
        self.connect()
        os.makedirs(dst, exist_ok=True)
        return subprocess.run(self.base() + ["pull", src, dst]).returncode


def link_for(m):
    return {"local": LocalLink, "ssh": SshLink, "adb": AdbLink}[m.get("link", "local")](m)


def load(project):
    return project.read("machines.json", {"machines": {}})


def save(project, data):
    project.write("machines.json", data)


def add(project, name, roles, link, host=None, os_name=None, headset=None, game_dir=None):
    for r in roles:
        if r not in ROLES:
            raise SystemExit(f"unknown role {r} (roles: {', '.join(ROLES)})")
    if link not in LINKS:
        raise SystemExit(f"unknown link {link} (links: {', '.join(LINKS)})")
    if link != "local" and not host:
        raise SystemExit("--host is needed for ssh (user@address) and adb (address:port or serial)")
    data = load(project)
    m = data["machines"].get(name, {})
    m.update({k: v for k, v in {"roles": roles, "link": link, "host": host, "os": os_name, "headset": headset,
                                "game_dir": game_dir}.items() if v})
    data["machines"][name] = m
    save(project, data)
    return m


# ---------- network helpers ----------

def tailscale_peers():
    """{hostname/ip: online} from the local tailscale CLI, or None if it isn't installed/running."""
    exe = shutil.which("tailscale") or ("/Applications/Tailscale.app/Contents/MacOS/Tailscale"
                                        if os.path.exists("/Applications/Tailscale.app/Contents/MacOS/Tailscale") else None)
    if not exe:
        return None
    try:
        p = subprocess.run([exe, "status", "--json"], capture_output=True, text=True, timeout=8)
        d = json.loads(p.stdout)
    except Exception:
        return None
    peers = {}
    for peer in (d.get("Peer") or {}).values():
        for key in [peer.get("HostName", "")] + (peer.get("TailscaleIPs") or []):
            if key:
                peers[key.lower()] = bool(peer.get("Online"))
    return {"backend": d.get("BackendState"), "peers": peers}


def host_address(m):
    h = m.get("host") or ""
    return h.split("@")[-1].split(":")[0].lower()


# ---------- check ----------

def remote_path(p):
    """A double-quoted shell word; a leading ~ becomes $HOME on the far side."""
    p = (p or "").replace("\\", "\\\\").replace('"', '\\"').replace("`", "\\`")
    if p.startswith("~"):
        p = "$HOME" + p[1:]
    return '"' + p + '"'


PROBE = r"""
echo "os=$(uname -s 2>/dev/null)"; echo "kernel=$(uname -r 2>/dev/null)"
echo "gpu=$( (lspci 2>/dev/null | grep -iE 'vga|3d' | head -1 | cut -d: -f3) || true)"
for d in "$HOME/.local/share/Steam" "$HOME/.steam/steam"; do [ -d "$d" ] && { echo "steam=$d"; break; }; done
flatpak list 2>/dev/null | grep -q com.valvesoftware.Steam && echo "steam_flatpak=1"
[ -d "$HOME/.local/share/Steam/steamapps/common/SteamVR" ] && echo "steamvr=1"
command -v monado-service >/dev/null && echo "monado=1"
[ -d /usr/lib64/opencomposite ] || [ -d /usr/lib/opencomposite ] && echo "opencomposite=1"
pgrep -x vrserver >/dev/null && echo "vrserver_running=1"
pgrep -x monado-service >/dev/null && echo "monado_running=1"
GD=__GAME_DIR__
if [ -n "$GD" ] && [ -d "$GD" ]; then echo "game_dir=1"
  [ -f "$GD/.irisify-deploy.lock" ] && echo "lock=$(cat "$GD/.irisify-deploy.lock" | tr '\n' ' ')"
  B=$(find "$GD" -maxdepth 4 -name build.json -path '*irisify*' 2>/dev/null | head -1); [ -n "$B" ] && echo "build=$(tr -d '\n' < "$B")"
fi
"""


def check(project, name, m):
    st = {"name": name, "at": now(), "roles": m.get("roles", []), "link": m.get("link"), "host": m.get("host"),
          "headset": m.get("headset")}
    ts = tailscale_peers()
    addr = host_address(m)
    if m.get("link") != "local" and ts:
        st["tailscale"] = {"backend": ts["backend"], "peer_online": ts["peers"].get(addr)}
    try:
        if m.get("link") == "adb" and not shutil.which("adb"):
            raise FileNotFoundError("adb not installed on this machine")
        rc, out, err = link_for(m).run(PROBE.replace("__GAME_DIR__", remote_path(m.get("game_dir", ""))), timeout=25)
        st["reachable"] = rc == 0
        facts = {}
        for line in out.splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                facts[k.strip()] = v.strip()
        if "build" in facts:
            try:
                facts["build"] = json.loads(facts["build"])
            except ValueError:
                pass
        st["facts"] = facts
        if rc != 0:
            st["error"] = (err or out).strip()[-400:]
    except subprocess.TimeoutExpired:
        st["reachable"] = False
        st["error"] = "timed out"
    except FileNotFoundError as e:
        st["reachable"] = False
        st["error"] = str(e)
    st["steps"] = setup_steps(m, st)
    return st


def check_all(project, only=None):
    data = load(project)
    status = project.read("machines-status.json", {})
    for name, m in data["machines"].items():
        if only and name != only:
            continue
        status[name] = check(project, name, m)
    project.write("machines-status.json", status)
    return status


# ---------- setup steps ----------

def setup_steps(m, st):
    """Ordered steps with who does them and whether they're done. `who`: agent | you | check."""
    f = st.get("facts", {}) if st else {}
    reach = st.get("reachable") if st else None
    link = m.get("link")
    roles = m.get("roles", [])
    steps = []

    def step(id, what, done, who, fix=None, why=None):
        steps.append({"id": id, "what": what, "done": done, "who": who, "fix": fix, "why": why})

    if link == "ssh":
        ts = (st or {}).get("tailscale")
        if ts is not None:
            step("tailscale", "Tailscale up on both ends, peer online", bool(ts.get("peer_online")), "you",
                 "Install Tailscale on the machine and sign in to the same tailnet (https://tailscale.com/download)",
                 "a stable address on any network")
        step("ssh_key", "SSH key login works", bool(reach), "you",
             f"ssh-copy-id {m.get('host')}   (once; asks for the password)", "the agent deploys and reads logs over SSH")
    elif link == "adb":
        step("adb_installed", "adb on this machine", bool(shutil.which("adb")), "agent",
             "macOS: brew install android-platform-tools · Fedora: sudo dnf install android-tools")
        step("dev_mode", "Developer mode on the headset, wireless debugging paired", bool(reach), "you",
             f"On the headset: enable developer mode, then here: adb pair <ip>:<pair-port> && adb connect {m.get('host')}")
    if not reach:
        return steps
    if "game-host" in roles or "rig" in roles:
        if f.get("os") == "Linux":
            step("steam_native", "Native Steam (not Flatpak)", "steam_flatpak" not in f, "you",
                 "Install your distro's Steam package and remove the Flatpak (lessons C2)")
            step("steamvr", "SteamVR installed", "steamvr" in f, "you", "Install SteamVR from Steam")
        step("game", "Game installed at the configured path", "game_dir" in f, "you" if not m.get("game_dir") else "check",
             "Set it: irisify machine add <name> --game-dir <path>")
    if "rig" in roles and f.get("os") == "Linux":
        step("monado", "Monado + OpenComposite for the headset-free rig", "monado" in f and "opencomposite" in f, "you",
             "Fedora: sudo dnf install monado opencomposite", "SteamVR's null driver can't run its compositor on Linux")
    steps.append({"id": "preflight", "what": "Platform preflight for the headset", "done": None, "who": "agent",
                  "fix": f"irisify doctor platform --machine <name>"})
    return steps
