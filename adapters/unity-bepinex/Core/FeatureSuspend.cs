// An error stops a feature for this session only (lessons A13). Never write the player's settings from an error path:
// one exception would turn the feature off in every later game and every later test run.
//
//   try { DoSwim(); } catch (Exception e) { FeatureSuspend.TurnOff("ArmSwimming", e); }
//   bool on = Settings.ArmSwimming && !FeatureSuspend.IsOff("ArmSwimming");
//
// The rig client fails any scenario whose log has an [Irisify:suspend] line, so a silent fail-safe can't hide a bug.
// The settings save path must not read IsOff: suspension is not a preference.
using System;
using System.Collections.Generic;

namespace Irisify
{
    public static class FeatureSuspend
    {
        static readonly Dictionary<string, string> off = new Dictionary<string, string>();
        static readonly Dictionary<string, int> errors = new Dictionary<string, int>();

        public static Action<string> Log = s => UnityEngine.Debug.LogWarning(s);

        public static bool IsOff(string feature) => off.ContainsKey(feature);

        public static IReadOnlyDictionary<string, string> Suspended => off;

        // Turn a feature off for the session after `threshold` errors (default: the first one).
        public static void TurnOff(string feature, object why, int threshold = 1)
        {
            errors.TryGetValue(feature, out var n);
            errors[feature] = ++n;
            if (n < threshold || off.ContainsKey(feature)) return;
            var msg = why is Exception e ? e.GetType().Name + ": " + e.Message : why?.ToString() ?? "error";
            off[feature] = msg;
            Log($"[Irisify:suspend] {feature}: {msg} (this session only; settings unchanged)");
        }

        // The rig's reset_settings command and a new game session call this.
        public static void Clear() { off.Clear(); errors.Clear(); }
    }
}
