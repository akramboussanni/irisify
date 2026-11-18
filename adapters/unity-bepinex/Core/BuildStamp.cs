// Logs the build id written by `irisify deploy` (build.json next to the plugin), so the tester, the agent and the
// dashboard agree on what's running (lessons A2):  [Irisify] build <id> (<branch>, <describe>)
using System.IO;
using System.Reflection;
using System.Text.RegularExpressions;

namespace Irisify
{
    public static class BuildStamp
    {
        public static string Id = "unknown";

        public static void Log(System.Action<string> log)
        {
            var dir = Path.GetDirectoryName(Assembly.GetExecutingAssembly().Location);
            foreach (var p in new[] { Path.Combine(dir, "irisify", "build.json"), Path.Combine(dir, "build.json") })
            {
                if (!File.Exists(p)) continue;
                var json = File.ReadAllText(p);
                Id = Field(json, "id") ?? Id;
                log($"[Irisify] build {Id} ({Field(json, "branch")}, {Field(json, "describe")})");
                return;
            }
            log("[Irisify] build unknown (no build.json: deploy with `irisify deploy`)");
        }

        static string Field(string json, string key)
        {
            var m = Regex.Match(json, "\"" + key + "\"\\s*:\\s*\"([^\"]*)\"");
            return m.Success ? m.Groups[1].Value : null;
        }
    }
}
