# Results schema

The in-game adapter and `tools/rig/rigclient.py` append JSON lines to `<rig_dir>/results.jsonl`. `irisify sync`
pulls them, and `irisify import` splits them into runs under `.irisify/runs/<run>/run.json` with their screenshots.

## Lines

**Run header** (written by rigclient before a suite):
```json
{"type": "run", "id": "20261117-201500-fedora-auto", "build": {"id": "2556818", "commit": "…", "branch": "deep-vr"},
 "suite": "auto", "machine": "fedora", "scenarios": ["boot", "swim_controls"], "seed": null, "started": 1794960000.0}
```

**Command result**:
```json
{"id": "a1b2c3d4-0", "cmd": "dump", "ok": true, "data": {…}, "t": 680.26, "frame": 30053}
```

**Scenario result** (required: `scenario`, `result`; everything else optional but used):
```json
{"scenario": "builder_move", "result": "PASS|FAIL|SKIP|CRASH", "detail": "",
 "build": "2556818", "run": "20261117-201500-fedora-auto", "owner": "building",
 "checks": [{"check": "moves with the builder drawn (>= 70 % of normal)", "ok": true, "value": {"builder": 8.3, "bare": 9.27}}],
 "shots": [{"file": "builder_move-moving-with-builder.png", "moment": "moving-with-builder", "question": "Is the builder in the right hand?"}],
 "startState": {"claims": [], "held": "None", "fps": 51}, "log": ["[Swim] context swim …"], "errors": [],
 "metrics": {"effort_per_metre": 0.42}, "seconds": 13.6, "t": 693.89, "frame": 30636}
```
A line with `"via": "rigclient"` replaces the adapter's own line for the same scenario just before it (it adds the
`#2` label for repeats and the duration).

**Summary**: `{"summary": {"builder_move": "PASS"}, "PASS": 1, "run": "…", "t": …}` ends a run.

## Older SubmersedVR rig files

No run header and no build id; a `summary` after every scenario. The importer merges consecutive single-scenario
runs while game time keeps rising, and marks the build `inferred` (from `--build`, or the last deploy to that
machine). Its `summary.json` (`{"summary": …, "results": [scenario lines]}`) imports as one full run:
`irisify import summary.json --shots shots/ --build <id> --suite full`.

## Scenario metadata (`scenarios/*.json`)

```json
{"name": "swim_controls", "owner": "swim-controls", "type": "Locomotion", "tags": ["swim", "locomotion", "smoke"],
 "touches": ["VR/Swim*.cs"], "minutes": 2, "needs_restart": false,
 "covers": ["level along body facing"], "cannot_cover": ["feel and effort over minutes"],
 "shots": [{"moment": "dive", "question": "Is the view level while diving?"}]}
```
`tags` pick suites, `touches` drive the `changed` suite, `type` (or the first matching tag) groups tests in the
dashboard, and `cannot_cover` builds the human's headset checklist.
