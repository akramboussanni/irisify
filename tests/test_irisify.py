"""Unit tests (stdlib unittest): python3 -m unittest discover tests"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))

from irisify import controllers, doctor, results, suites, workflow  # noqa: E402
from irisify.project import Project  # noqa: E402

EXAMPLE = os.path.join(REPO, "examples", "subnautica")


def project():
    d = tempfile.mkdtemp(prefix="irisify-test-")
    os.makedirs(os.path.join(d, ".irisify"))
    os.makedirs(os.path.join(d, "scenarios"))
    os.makedirs(os.path.join(d, "suites"))
    shutil.copy(os.path.join(EXAMPLE, "scenarios", "scenarios.json"), os.path.join(d, "scenarios"))
    for f in os.listdir(os.path.join(REPO, "suites")):
        shutil.copy(os.path.join(REPO, "suites", f), os.path.join(d, "suites"))
    return Project(d)


class Controllers(unittest.TestCase):
    def setUp(self):
        self.c = controllers.load_controls(os.path.join(EXAMPLE, "design", "controls.json"))

    def test_frame_profile_is_not_touch_shaped(self):
        p = controllers.load_profiles()["frame_controller"]
        comps = controllers.profile_components(p)
        self.assertEqual(comps["dpad_up"]["side"], "left")
        for b in "abxy":
            self.assertEqual(comps[b]["side"], "right")
        self.assertEqual(comps["grip"]["type"], "trigger")  # analog grip

    def test_example_lints_clean(self):
        inter = json.load(open(os.path.join(EXAMPLE, "design", "interactions.json")))
        errors, _ = controllers.lint(self.c, interactions=inter)
        self.assertEqual(errors, [])

    def test_lint_catches_the_subnautica_mistakes(self):
        c = json.loads(json.dumps(self.c))
        c["contexts"]["on_foot"]["right"]["grip"] = "Jump"                          # locomotion on a grip (D2)
        c["contexts"]["on_foot"]["left"]["dpad_up"] = "PDA"                         # shortcut next to thigh PDA (A6)
        c["actions"].append({"name": "UIAssign2", "type": "boolean"})               # orphan action (D1)
        c["contexts"]["swimming"]["left"]["a"] = "Exit"                             # A is on the right on the Frame
        c["contexts"]["pda"]["right"]["trigger"] = [{"click": "UISubmit"}, {"click": "UICancel", "when_holding": "item"}]  # double owner (D6)
        inter = json.load(open(os.path.join(EXAMPLE, "design", "interactions.json")))
        errors, _ = controllers.lint(c, interactions=inter)
        text = "\n".join(errors)
        for needle in ("grips are for grabbing", "still bound", "neither bound", "on the right controller", "two owners"):
            self.assertIn(needle, text)

    def test_generated_frame_binding_matches_shipped_layout(self):
        b, lost = controllers.generate_binding(self.c, controllers.load_profiles()["frame_controller"])
        self.assertEqual(lost, [])
        pairs = {(s["path"], k, v["output"]) for s in b["bindings"]["/actions/subnautica"]["sources"] for k, v in s["inputs"].items()}
        self.assertIn(("/user/hand/right/input/y", "click", "/actions/subnautica/in/uiassign"), pairs)
        self.assertIn(("/user/hand/left/input/dpad_left", "click", "/actions/subnautica/in/builderrotateleft"), pairs)
        grips = [s for s in b["bindings"]["/actions/subnautica"]["sources"] if s["path"].endswith("/grip")]
        self.assertTrue(all("click_activate_threshold" in s.get("parameters", {}) for s in grips))

    def test_prompts_come_from_the_same_table(self):
        p = controllers.generate_prompts(self.c, controllers.load_profiles()["frame_controller"])
        self.assertEqual(p["pda"]["UIAssign"][0]["glyph"], "R Y")
        self.assertEqual(p["on_foot"]["Jump"][0]["glyph"], "L Stick click")
        t = controllers.generate_prompts(self.c, controllers.load_profiles()["oculus_touch"])
        self.assertNotIn("UIAssign", t.get("pda", {}))  # no right Y on Touch: lint warns instead of lying

    def test_detect_prefers_adapter_line(self):
        d = controllers.detect_from_text([("log", "x [Irisify] controllers: left=frame_controller right=frame_controller hmd=frame_hmd runtime=SteamVR"),
                                          ("vrserver", "knuckles knuckles")])
        self.assertEqual(d["controller_type"], "frame_controller")
        self.assertEqual(d["confidence"], "high")


class Doctor(unittest.TestCase):
    def test_version_and_expectations(self):
        self.assertTrue(doctor.evaluate({"expect_min_version": "7.2"}, "7.3.4-200.fc44.x86_64"))
        self.assertFalse(doctor.evaluate({"expect_min_version": "7.2"}, "6.11.0"))
        self.assertTrue(doctor.evaluate({"expect_contains": "cap_sys_nice"}, "x cap_sys_nice=eip"))

    def test_steam_input_evidence(self):
        state, ev = doctor.steam_input_findings("controller.txt: [..] Opted-in Controller Mask for AppId 264710: 1000\n")
        self.assertEqual(state, "on")


class Results(unittest.TestCase):
    def test_legacy_lines_merge_into_sessions(self):
        lines = [{"scenario": "a", "result": "PASS", "t": 10}, {"summary": {"a": "PASS"}},
                 {"scenario": "b", "result": "FAIL", "t": 20}, {"summary": {"b": "FAIL"}},
                 {"scenario": "c", "result": "PASS", "t": 5}, {"summary": {"c": "PASS"}}]  # game restarted
        runs = results.merge_legacy(results.split_runs(lines))
        self.assertEqual([len(r["scenarios"]) for r in runs], [2, 1])

    def test_rigclient_line_replaces_adapter_line(self):
        lines = [{"type": "run", "id": "r"}, {"scenario": "x", "result": "PASS"}, {"scenario": "x#2", "result": "FAIL", "via": "rigclient"}, {"summary": {}}]
        self.assertEqual([s["scenario"] for s in results.split_runs(lines)[0]["scenarios"]], ["x#2"])

    def test_flaky_within_a_build(self):
        mk = lambda res, v: {"id": "r", "build": {"id": "b1"}, "scenarios": [{"base": "s", "result": res, "metrics": {"check:speed": v}}]}
        self.assertIn("s", results.flaky([mk("PASS", 9.0), mk("FAIL", 9.0)])["b1"])
        self.assertIn("s", results.flaky([mk("PASS", 9.0), mk("PASS", 4.0)])["b1"])
        self.assertEqual(results.flaky([mk("PASS", 9.0), mk("PASS", 8.9)]), {})

    def test_proton_paths(self):
        self.assertEqual(results.shot_basename("Z:\\home\\user\\shots\\a-b.png"), "a-b.png")


class Suites(unittest.TestCase):
    def test_tag_suite_and_reasons(self):
        p = project()
        sel = suites.select(p, "locomotion")
        self.assertEqual(sel["scenarios"][0], "boot")
        self.assertIn("swim_controls", sel["scenarios"])
        self.assertNotIn("holster_draw_stow", sel["scenarios"])
        self.assertTrue(sel["why"]["swim_controls"].startswith("tag"))

    def test_changed_picks_by_touched_files(self):
        p = project()
        sel = suites.select(p, "changed", files=["SubmersedVR/VR/WaterGrab.cs"])
        self.assertIn("swim_water_hold", sel["scenarios"])
        self.assertNotIn("seamoth_enter_exit", sel["scenarios"])
        self.assertIn("boot", sel["scenarios"])  # smoke always

    def test_shared_core_files_fan_out(self):
        p = project()
        cfg = {"core": [{"files": ["VR/BodyFrame.cs"], "tags": ["holsters"]}]}
        p.write("project.json", cfg)
        sel = suites.select(p, "changed", files=["SubmersedVR/VR/BodyFrame.cs"])
        self.assertIn("holster_carry_release", sel["scenarios"])
        self.assertTrue(sel["why"]["holster_carry_release"].startswith("shared"))
        self.assertNotIn("swim_water_hold", sel["scenarios"])

    def test_run_options_sets_saves_and_shots(self):
        p = project()
        p.write("project.json", {"rig": {"saves": {"creative": {}, "survival": {}}},
                                 "core": [{"files": ["VR/BodyFrame.cs"], "tags": ["holsters"], "full_sets": True}]})
        o = suites.select(p, "changed", files=["SubmersedVR/VR/BodyFrame.cs"])["options"]
        self.assertEqual(o["shoulder_reach_rate"]["set"], "full", "a body core change runs the full sets")
        self.assertEqual(o["shoulder_reach_rate"]["shots"], "proof", "targeted runs keep one proof shot")
        self.assertEqual(o["boot"]["save"], "creative")
        o = suites.select(p, "changed", files=["SubmersedVR/VR/WaterGrab.cs"])["options"]
        self.assertNotIn("shoulder_reach_rate", o)
        o = suites.run_options(p, "full", ["shoulder_reach_rate", "build_menu_all_unlocked"], files=["x.cs"])
        self.assertEqual(o["shoulder_reach_rate"]["set"], "quick")
        self.assertEqual(o["shoulder_reach_rate"]["shots"], "all")
        self.assertEqual(o["build_menu_all_unlocked"]["cap"], 300)

    def test_flaky_hunt_interleaves(self):
        p = project()
        sel = suites.select(p, "flaky-hunt", scenario="builder_move", seed=1)
        s = sel["scenarios"]
        self.assertEqual(s[0], "builder_move")
        self.assertEqual(s[::2], ["builder_move"] * len(s[::2]))


class ScenarioLint(unittest.TestCase):
    def test_worst_case_required_for_content_tags(self):
        p = project()
        errors, _ = suites.lint_scenarios(p)
        self.assertEqual(errors, [])
        path = os.path.join(p.root, "scenarios", "scenarios.json")
        sc = [s for s in json.load(open(path)) if s.get("content") != "worst-case"]
        json.dump(sc, open(path, "w"))
        errors, _ = suites.lint_scenarios(p)
        self.assertTrue(any("worst-case" in e and "containers" in e for e in errors))


class DeployPolicy(unittest.TestCase):
    def test_headset_deploy_needs_green_full_suite_on_the_commit(self):
        from irisify import deploy
        p = project()
        with self.assertRaises(SystemExit):
            deploy.require_full_suite(p, "abc123")
        run = {"id": "r1", "seq": 1, "imported": "2026-11-17T00:00:00Z", "suite": "full", "machine": "rig",
               "build": {"id": "abc", "commit": "abc123"}, "counts": {"PASS": 3, "FAIL": 0, "SKIP": 0, "CRASH": 0}, "scenarios": []}
        p.write(os.path.join("runs", "r1", "run.json"), run)
        self.assertEqual(deploy.require_full_suite(p, "abc123")["id"], "r1")
        run["suite"] = "smoke"; run["id"] = "r2"; run["build"]["commit"] = "def456"
        p.write(os.path.join("runs", "r2", "run.json"), run)
        with self.assertRaises(SystemExit):
            deploy.require_full_suite(p, "def456")      # a green smoke run isn't enough


class Workflow(unittest.TestCase):
    def test_first_boot_from_log(self):
        p = project()
        log = "[Irisify] build abc123 (main, abc123)\n[Irisify] patches: 181 applied, 0 failed\n[Irisify:focus] inputAvailable=True\n[Irisify:input] Jump DOWN (left)\n"
        rec = workflow.first_boot_from_log(p, log, "abc123")
        self.assertTrue(all(rec["checks"][k] for k in ("patches_ok", "input_down", "build_matches")))
        self.assertTrue(workflow.gate_first_boot(p)["ok"])
        rec = workflow.first_boot_from_log(p, "[Irisify] patches: 180 applied, 1 failed\n", None)
        self.assertFalse(workflow.gate_first_boot(p)["ok"])

    def test_fanout_refuses_without_gates(self):
        p = project()
        with self.assertRaises(SystemExit) as e:
            workflow.require(p, "fanout")
        self.assertIn("first-boot", str(e.exception))
        workflow.require(p, "fanout", force="user said so")
        self.assertEqual(p.lines("overrides.jsonl")[-1]["why"], "user said so")


class RigClient(unittest.TestCase):
    """rigclient.py against a fake game that answers the command channel."""

    def test_run_writes_header_results_and_summary(self):
        d = tempfile.mkdtemp(prefix="irisify-rig-")
        cmd = os.path.join(d, "cmd")
        os.makedirs(cmd)
        res = os.path.join(d, "results.jsonl")
        stop = threading.Event()
        loads, seen_cmds = [], []
        logf = os.path.join(d, "LogOutput.log")
        open(logf, "w").close()

        def game():
            while not stop.is_set():
                for f in sorted(os.listdir(cmd)):
                    if not f.endswith(".json"):
                        continue
                    for c in json.load(open(os.path.join(cmd, f))):
                        if c["cmd"] == "load":
                            loads.append(c.get("slot"))
                        if c["cmd"] == "scenario":
                            seen_cmds.append(c)
                            if c["name"] == "self_off":
                                open(logf, "a").write("[Irisify:suspend] ArmSwimming: NullReferenceException\n")
                        if c["cmd"] == "scenario":
                            line = {"id": c["id"], "scenario": c["name"], "result": "FAIL" if c["name"] == "bad" else "PASS",
                                    "checks": [{"check": "x", "ok": c["name"] != "bad"}]}
                        else:
                            line = {"id": c["id"], "cmd": c["cmd"], "ok": True, "data": {"scene": "game" if loads else "menu", "slot": loads[-1] if loads else None}}
                        open(res, "a").write(json.dumps(line) + "\n")
                    os.remove(os.path.join(cmd, f))
                time.sleep(0.05)

        t = threading.Thread(target=game, daemon=True)
        t.start()
        cfg = os.path.join(d, "rig.json")
        json.dump({"rig_dir": d, "log": logf, "scenario_timeout": 10, "reset_settings": {"cmd": "reset_settings"}, "saves": {"creative": {"cmd": "load", "slot": "slot9000"},
                                                                   "survival": {"cmd": "load", "slot": "slot9001"}}}, open(cfg, "w"))
        opts = os.path.join(d, "options.json")
        json.dump({"good": {"save": "creative", "set": "quick", "shots": "proof", "cap": 10}, "bad": {"save": "creative"},
                   "eat": {"save": "survival"}, "self_off": {"save": "survival"}}, open(opts, "w"))
        p = subprocess.run([sys.executable, os.path.join(REPO, "tools", "rig", "rigclient.py"), "--config", cfg, "run",
                            "--scenarios", "good,bad,good,eat,self_off", "--run-id", "r1", "--build", '{"id": "b1"}', "--options", opts],
                           capture_output=True, text=True, timeout=60)
        stop.set()
        self.assertEqual(p.returncode, 1, p.stderr)
        runs = results.split_runs([json.loads(l) for l in open(res)])
        self.assertEqual(len(runs), 1)
        self.assertEqual([s["scenario"] for s in runs[0]["scenarios"]], ["good", "bad", "good#2", "eat", "self_off"])
        self_off = runs[0]["scenarios"][-1]
        self.assertEqual(self_off["result"], "FAIL", "a feature that turned itself off fails the scenario")
        self.assertEqual(sum(1 for l in open(res) if '"reset_settings"' in l), 1, "test settings reset once per run")
        self.assertEqual(runs[0]["header"]["build"]["id"], "b1")
        self.assertEqual(loads, ["slot9000", "slot9001"], "each save loads once, only when a scenario needs it")
        self.assertEqual(seen_cmds[0].get("set"), "quick")
        self.assertEqual(seen_cmds[0].get("shots"), "proof")
        self.assertTrue(all("seconds" in s for s in runs[0]["scenarios"]))


class FailSafe(unittest.TestCase):
    def test_finds_catch_that_writes_a_setting(self):
        d = tempfile.mkdtemp(prefix="irisify-src-")
        with open(os.path.join(d, "Swim.cs"), "w") as f:
            f.write("void A() {\n  try { Go(); }\n  catch (Exception e)\n  {\n    Log(e);\n    Settings.ArmSwimming = false;\n  }\n}\n"
                    "void B() {\n  try { Go(); } catch { FeatureSuspend.TurnOff(\"X\", null); }\n  Settings.Other = false;\n}\n")
        from irisify import patchcheck
        hits = patchcheck.failsafe_scan(d)
        self.assertEqual([h["setting"] for h in hits], ["Settings.ArmSwimming"])


class SkillCopy(unittest.TestCase):
    def test_lessons_copy_in_sync(self):
        a = open(os.path.join(REPO, "docs", "lessons.md")).read()
        b = open(os.path.join(REPO, "skill", "references", "lessons.md")).read()
        self.assertEqual(a, b, "run: cp docs/lessons.md skill/references/lessons.md")


if __name__ == "__main__":
    unittest.main()
