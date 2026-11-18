// Irisify adapter (Unity / BepInEx 5 / Harmony 2). Template: copy into your plugin and change the namespace.
// Patches class by class so one bad target can't disable the whole mod (lessons B1), and logs the boot line the
// first-boot gate reads:  [Irisify] patches: N applied, M failed: [...]
using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using HarmonyLib;

namespace Irisify
{
    public static class SafePatcher
    {
        public static readonly List<string> Failed = new List<string>();

        public static int PatchAll(Harmony harmony, Assembly asm, Action<string> log, Action<string> logError)
        {
            int ok = 0;
            foreach (var type in AccessTools.GetTypesFromAssembly(asm))
            {
                if (!type.GetCustomAttributes(typeof(HarmonyPatch), true).Any() && !HasPatchMethods(type))
                    continue;
                try
                {
                    harmony.CreateClassProcessor(type).Patch();
                    ok++;
                }
                catch (Exception e)
                {
                    // Common causes: explicit interface methods are named "IInterface.Method" in metadata;
                    // a TargetMethods() that yields null; a transpiler that dropped a label (edit in place or MoveLabelsFrom).
                    Failed.Add(type.Name);
                    logError($"[Irisify] patch class {type.FullName} skipped: {e.GetBaseException().Message}");
                }
            }
            log($"[Irisify] patches: {ok} applied, {Failed.Count} failed" + (Failed.Count > 0 ? ": [" + string.Join(", ", Failed) + "]" : ""));
            return ok;
        }

        static bool HasPatchMethods(Type t) =>
            t.GetMethods(BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic)
             .Any(m => m.GetCustomAttributes(typeof(HarmonyPatch), true).Any());

        // Use in TargetMethods(): never yield null (it aborts the class).
        public static IEnumerable<MethodBase> NonNull(params MethodBase[] methods) => methods.Where(m => m != null);

        // Explicit interface implementations: AccessTools.Method(typeof(Arm), "IArm.Update").
        public static MethodBase Explicit(Type type, string iface, string method) =>
            AccessTools.Method(type, iface + "." + method) ?? AccessTools.Method(type, method);
    }
}
