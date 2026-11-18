// Saved settings beat new defaults (lessons A5). Version the settings and migrate on load, one log line per step.
// Rules: non-setting statics never live in the settings class (a reflection serializer will try to save them,
// lessons B3); runtime kill switches are never persisted.
using System;
using System.Collections.Generic;

namespace Irisify
{
    public static class SettingsMigration
    {
        public const string VersionKey = "IrisifySettingsVersion";

        // Each step turns on what changed to default-on in that version. Append, never edit old steps.
        public static readonly List<Action<Action<string, object>>> Steps = new List<Action<Action<string, object>>>
        {
            set => { set("ArmSwimming", true); set("HeadClipFade", true); },        // v1 example
            set => { set("PhysicalContainers", true); },                             // v2 example
            // After removing persisted fail-safes (lessons A13), add one step that turns every feature an error path
            // could have switched off back on, once: set => { foreach (var f in FeaturesThatSelfDisabled) set(f, true); }
        };

        // get/set: your settings store. Call after the game loads its settings, before your features read them.
        public static void Run(Func<string, object> get, Action<string, object> set, Action save, Action<string> log)
        {
            int v = Convert.ToInt32(get(VersionKey) ?? 0);
            if (v >= Steps.Count) return;
            for (int i = v; i < Steps.Count; i++)
            {
                Steps[i](set);
                log($"[Settings] migration {i} -> {i + 1} applied");
            }
            set(VersionKey, Steps.Count);
            save();
        }
    }
}
