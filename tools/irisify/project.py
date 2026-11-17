"""Finding the project and reading/writing its state files.

A project is a mod repo (or any folder) with an `.irisify/` directory. Everything Irisify knows about it lives
there as plain JSON / JSON lines, so agents, the CLI and the dashboard all read the same files.
"""
import json
import os
import time

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PROFILES = os.path.join(REPO, "controllers", "profiles")


def find_root(start=None):
    d = os.path.abspath(start or os.environ.get("IRISIFY_PROJECT") or os.getcwd())
    while True:
        if os.path.isdir(os.path.join(d, ".irisify")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent


class Project:
    def __init__(self, root):
        self.root = root
        self.dir = os.path.join(root, ".irisify")

    @classmethod
    def open(cls, start=None, create=False):
        root = find_root(start)
        if root is None:
            if not create:
                raise SystemExit("no Irisify project here (run `irisify init` in the mod repo)")
            root = os.path.abspath(start or os.getcwd())
            os.makedirs(os.path.join(root, ".irisify"), exist_ok=True)
        return cls(root)

    def path(self, *parts):
        return os.path.join(self.dir, *parts)

    def read(self, name, default=None):
        p = self.path(name)
        if not os.path.exists(p):
            return default
        with open(p) as f:
            return json.load(f)

    def write(self, name, data):
        p = self.path(name)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        tmp = p + ".tmp"
        with open(tmp, "w") as f:
            json.dump(data, f, indent=1, sort_keys=False)
            f.write("\n")
        os.replace(tmp, p)

    def append(self, name, record):
        p = self.path(name)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        record = dict(record)
        record.setdefault("at", now())
        with open(p, "a") as f:
            f.write(json.dumps(record) + "\n")
        return record

    def lines(self, name):
        p = self.path(name)
        if not os.path.exists(p):
            return []
        out = []
        with open(p) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        out.append(json.loads(line))
                    except ValueError:
                        pass
        return out

    def config(self):
        return self.read("project.json", {})


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def load_structured(path):
    """JSON always; YAML when PyYAML is installed."""
    with open(path) as f:
        text = f.read()
    if path.endswith((".yaml", ".yml")):
        try:
            import yaml  # type: ignore
        except ImportError:
            raise SystemExit(f"{path}: YAML needs PyYAML (pip install pyyaml), or write it as .json")
        return yaml.safe_load(text)
    return json.loads(text)
