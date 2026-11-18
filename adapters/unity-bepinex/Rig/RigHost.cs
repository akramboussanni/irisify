// The in-game half of the Irisify rig: command channel + results writer + scenario registry.
// Off unless IRISIFY_RIG=1 (or <rig_dir>/enable exists): it's a cheat channel and must never ship enabled.
// Protocol (tools/rig/rigclient.py, docs/results-schema.md):
//   <BepInEx>/irisify/cmd/*.json      arrays of {"id","cmd",...} run in name order
//   <BepInEx>/irisify/results.jsonl   one line per command: {"id","cmd","ok","data","t","frame"}
//                                     one line per scenario: {"scenario","result","checks","shots","log","startState","build","t"}
using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEngine;

namespace Irisify.Rig
{
    public class Check { public string check; public bool ok; public object value; }

    public class ScenarioContext
    {
        public readonly List<Check> Checks = new List<Check>();
        public readonly List<Dictionary<string, object>> Shots = new List<Dictionary<string, object>>();
        public readonly List<string> Log = new List<string>();
        public string Name;
        public void Expect(string what, bool ok, object value = null) => Checks.Add(new Check { check = what, ok = ok, value = value });
        public IEnumerator Shot(string moment, string question) { yield return Capture.Take(Name, moment, question, Shots); }
    }

    public class RigHost : MonoBehaviour
    {
        public static bool Enabled => Environment.GetEnvironmentVariable("IRISIFY_RIG") == "1" || File.Exists(Path.Combine(Dir, "enable"));
        public static string Dir = Path.Combine(BepInEx.Paths.BepInExRootPath, "irisify");
        public static Func<Dictionary<string, object>> Dump = () => new Dictionary<string, object>();          // fill from your game
        public static Func<Dictionary<string, object>> StartState = () => Dump();
        public static readonly Dictionary<string, Func<ScenarioContext, IEnumerator>> Scenarios = new Dictionary<string, Func<ScenarioContext, IEnumerator>>();
        public static readonly Dictionary<string, Func<Dictionary<string, object>, object>> Commands = new Dictionary<string, Func<Dictionary<string, object>, object>>();
        static readonly List<string> captured = new List<string>();
        bool busy;

        public static void Install(GameObject host)
        {
            if (!Enabled) return;
            Directory.CreateDirectory(Path.Combine(Dir, "cmd"));
            Directory.CreateDirectory(Path.Combine(Dir, "shots"));
            Application.logMessageReceived += (msg, st, type) => { lock (captured) { captured.Add(msg); if (captured.Count > 4000) captured.RemoveRange(0, 1000); } };
            host.AddComponent<RigHost>();
            host.AddComponent<ScriptedInputDriver>();
            host.AddComponent<ComfortMonitor>();
            Commands["ping"] = a => "pong";
            Commands["dump"] = a => Dump();
            Commands["shot"] = a => null;   // handled as a coroutine below
        }

        void Update()
        {
            if (busy) return;
            var files = Directory.GetFiles(Path.Combine(Dir, "cmd"), "*.json").OrderBy(f => f).ToList();
            if (files.Count == 0) return;
            var text = File.ReadAllText(files[0]);
            File.Delete(files[0]);
            StartCoroutine(Run(MiniJson.ParseArray(text)));
        }

        IEnumerator Run(List<Dictionary<string, object>> cmds)
        {
            busy = true;
            foreach (var c in cmds)
            {
                var name = c.TryGetValue("cmd", out var n) ? n as string : null;
                if (name == "scenario") { yield return RunScenario(c); continue; }
                object data = null; bool ok = true; string error = null;
                try
                {
                    if (name != null && Commands.TryGetValue(name, out var fn)) data = fn(c);
                    else { ok = false; error = "unknown command " + name; }
                }
                catch (Exception e) { ok = false; error = e.Message; }
                Write(new Dictionary<string, object> { ["id"] = c.GetValueOrDefault("id"), ["cmd"] = name, ["ok"] = ok, ["data"] = data, ["error"] = error, ["t"] = Time.time, ["frame"] = Time.frameCount });
            }
            busy = false;
        }

        IEnumerator RunScenario(Dictionary<string, object> c)
        {
            var name = c.GetValueOrDefault("name") as string;
            if (!Scenarios.TryGetValue(name ?? "", out var fn))
            {
                Write(new Dictionary<string, object> { ["id"] = c.GetValueOrDefault("id"), ["scenario"] = name, ["result"] = "SKIP", ["detail"] = "no such scenario" });
                yield break;
            }
            var ctx = new ScenarioContext { Name = name };
            var start = StartState();
            int logFrom; lock (captured) logFrom = captured.Count;
            ComfortMonitor.Reset();
            ScriptedInput.Reset(); ScriptedInput.Active = true;
            var it = fn(ctx);
            while (true)
            {
                object cur;
                try { if (!it.MoveNext()) break; cur = it.Current; }
                catch (Exception e) { ctx.Expect("scenario ran without an exception", false, e.Message); break; }
                yield return cur;
            }
            ScriptedInput.ReleaseAll();
            ComfortMonitor.AddChecks(ctx);   // every scenario gets the comfort checks
            List<string> log; lock (captured) log = captured.Skip(logFrom).Where(l => l.StartsWith("[")).Take(200).ToList();
            var result = ctx.Checks.Count == 0 ? "SKIP" : ctx.Checks.All(x => x.ok) ? "PASS" : "FAIL";
            Write(new Dictionary<string, object> {
                ["id"] = c.GetValueOrDefault("id"), ["scenario"] = name, ["result"] = result, ["run"] = c.GetValueOrDefault("run"),
                ["build"] = BuildStamp.Id, ["checks"] = ctx.Checks.Select(x => new Dictionary<string, object> { ["check"] = x.check, ["ok"] = x.ok, ["value"] = x.value }).ToList(),
                ["shots"] = ctx.Shots, ["startState"] = start, ["log"] = log, ["t"] = Time.time, ["frame"] = Time.frameCount });
        }

        public static void Write(Dictionary<string, object> line)
        {
            File.AppendAllText(Path.Combine(Dir, "results.jsonl"), MiniJson.Serialize(line) + "\n");
            Debug.Log("[Irisify:rig] RESULT " + (line.GetValueOrDefault("scenario") ?? line.GetValueOrDefault("cmd")));
        }
    }

    static class DictExt
    {
        public static object GetValueOrDefault(this Dictionary<string, object> d, string k) => d.TryGetValue(k, out var v) ? v : null;
    }
}
