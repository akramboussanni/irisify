"""Find Harmony patch targets that name a method a class only implements explicitly (IInterface.Method),
the bug that made PatchAll throw on Subnautica (lessons B1). Static, offline: decompiled C# + mod source."""
import os
import re

EXPLICIT = re.compile(r"\b(?:void|bool|int|float|[A-Z]\w*)\s+(I[A-Z]\w*)\.(\w+)\s*\(")
CLASS = re.compile(r"\bclass\s+(\w+)")
PATCH = re.compile(r"HarmonyPatch\(\s*typeof\((\w+)\)\s*,\s*(?:nameof\(\w+\.(\w+)\)|\"(\w+)\")")


def scan(decomp_dir, mod_dir):
    explicit = {}
    for root, _, files in os.walk(decomp_dir):
        for f in files:
            if not f.endswith(".cs"):
                continue
            text = open(os.path.join(root, f), errors="replace").read()
            m = CLASS.search(text)
            if not m:
                continue
            names = {}
            for iface, meth in EXPLICIT.findall(text):
                names.setdefault(meth, set()).add(iface)
            plain = set(re.findall(r"\b(?:public|private|protected|internal)[^;{(=]*?\b(\w+)\s*\(", text))
            for meth, ifaces in names.items():
                if meth not in plain:
                    explicit[(m.group(1), meth)] = sorted(ifaces)
    hits = []
    for root, _, files in os.walk(mod_dir):
        for f in files:
            if f.endswith(".cs"):
                p = os.path.join(root, f)
                for i, line in enumerate(open(p, errors="replace"), 1):
                    for cls, a, b in PATCH.findall(line):
                        meth = a or b
                        if (cls, meth) in explicit:
                            hits.append({"file": p, "line": i, "class": cls, "method": meth,
                                         "use": [f"{x}.{meth}" for x in explicit[(cls, meth)]]})
    return hits


# A catch block that writes a setting: the fail-safe that persists (lessons A13).
CATCH = re.compile(r"\bcatch\b")
SETTING_WRITE = re.compile(r"\b(\w*(?:Settings|Config|Prefs|Options)\w*)\.(\w+)\s*=\s*(false|0)\b")


def failsafe_scan(src_dir, window=8):
    """Every `catch` followed within `window` lines (before its block closes) by `<Settings>.X = false`."""
    hits = []
    for root, _, files in os.walk(src_dir):
        for f in files:
            if not f.endswith(".cs") or f == "FeatureSuspend.cs":
                continue
            p = os.path.join(root, f)
            lines = open(p, errors="replace").read().splitlines()
            for i, line in enumerate(lines):
                if not CATCH.search(line):
                    continue
                depth, opened = 0, False
                for j in range(i, min(i + window, len(lines))):
                    seg = lines[j][CATCH.search(lines[j]).start():] if j == i else lines[j]
                    m = SETTING_WRITE.search(seg)
                    if m and (opened or "{" in seg[:m.start()]):
                        hits.append({"file": p, "line": j + 1, "setting": f"{m.group(1)}.{m.group(2)}", "text": lines[j].strip()})
                        break
                    depth += seg.count("{") - seg.count("}")
                    opened = opened or "{" in seg
                    if opened and depth <= 0:
                        break
    return hits
