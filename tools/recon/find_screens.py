#!/usr/bin/env python3
"""Find a Unity game's own in-world screens and gauges, so diegetic UI goes on them (lessons E11).

  pip install UnityPy           (once, in a venv)
  python3 -I find_screens.py <Game>_Data [--names screen,display,monitor,gauge,hud,dash,panel] [--json out.json]

Lists GameObjects, materials and textures whose names match, with mesh names and texture sizes. Screens painted into
an interior texture show up as material/texture hits with no screen object: overlay those in the object's frame and
check parallax with head-lean screenshots. Read-only: never writes into the game folder.
"""
import argparse
import json
import os
import sys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("data_dir")
    ap.add_argument("--names", default="screen,display,monitor,gauge,hud,dash,panel,indoor,interior,cockpit")
    ap.add_argument("--json")
    a = ap.parse_args()
    try:
        import UnityPy  # type: ignore
    except ImportError:
        sys.exit("UnityPy isn't installed: pip install UnityPy (in a venv)")
    keys = [k.strip().lower() for k in a.names.split(",") if k.strip()]
    hits = {"gameobjects": [], "materials": [], "textures": [], "meshes": []}
    files = [os.path.join(a.data_dir, f) for f in os.listdir(a.data_dir)
             if f.endswith((".assets", ".bundle")) or f.startswith(("level", "sharedassets", "resources"))]
    for path in files:
        try:
            env = UnityPy.load(path)
        except Exception as e:
            print(f"skip {os.path.basename(path)}: {e}", file=sys.stderr)
            continue
        for obj in env.objects:
            t = obj.type.name
            if t not in ("GameObject", "Material", "Texture2D", "Mesh"):
                continue
            try:
                d = obj.read()
                name = getattr(d, "m_Name", None) or getattr(d, "name", "") or ""
            except Exception:
                continue
            if not any(k in name.lower() for k in keys):
                continue
            rec = {"name": name, "file": os.path.basename(path), "path_id": obj.path_id}
            if t == "Texture2D":
                rec["size"] = [getattr(d, "m_Width", None), getattr(d, "m_Height", None)]
                hits["textures"].append(rec)
            elif t == "Material":
                hits["materials"].append(rec)
            elif t == "Mesh":
                hits["meshes"].append(rec)
            else:
                hits["gameobjects"].append(rec)
    for k, v in hits.items():
        print(f"{k}: {len(v)}")
        for r in v[:40]:
            print(f"  {r['name']}  ({r['file']}#{r['path_id']}{', ' + str(r.get('size')) if r.get('size') else ''})")
    if a.json:
        with open(a.json, "w") as f:
            json.dump(hits, f, indent=1)


if __name__ == "__main__":
    main()
