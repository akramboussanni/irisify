// Focus first, bindings second (lessons C1). Logs, from boot: the controller types (for `irisify controllers detect`),
// whether the game has input focus, and every action edge. Poses can flow while every button is withheld.
//   [Irisify] controllers: left=frame_controller right=frame_controller hmd=frame_hmd runtime=SteamVR
//   [Irisify:focus] inputAvailable=True shouldPause=False actionSetActive=True
//   [Irisify:input] Jump DOWN (right)
// Adapt the two marked spots to your game's input layer (SteamVR Unity plugin shown).
using System.Collections.Generic;
using UnityEngine;
using Valve.VR;

namespace Irisify
{
    public class InputFocusDiag : MonoBehaviour
    {
        public static System.Action<string> Log = Debug.Log;
        readonly Dictionary<string, bool> last = new Dictionary<string, bool>();
        float nextSummary;
        bool announced;

        void Update()
        {
            if (OpenVR.System == null) return;
            if (!announced) { announced = true; Announce(); }
            if (Time.unscaledTime >= nextSummary)
            {
                nextSummary = Time.unscaledTime + 5f;
                Log($"[Irisify:focus] inputAvailable={OpenVR.System.IsInputAvailable()} shouldPause={OpenVR.System.ShouldApplicationPause()} "
                    + $"actionSetActive={ActionSetActive()}");
            }
            if (SteamVR_Input.actionsBoolean == null) return;
            foreach (var a in SteamVR_Input.actionsBoolean)   // (1) your game's boolean actions
            {
                bool l = a.GetState(SteamVR_Input_Sources.LeftHand), r = a.GetState(SteamVR_Input_Sources.RightHand);
                bool now = l || r || a.GetState(SteamVR_Input_Sources.Any);
                if (last.TryGetValue(a.fullPath, out var was) && was == now) continue;
                last[a.fullPath] = now;
                if (was || now) Log($"[Irisify:input] {a.GetShortName()} {(now ? "DOWN" : "up")} ({(l && r ? "both" : l ? "left" : r ? "right" : "any")})");
            }
        }

        static bool ActionSetActive()   // (2) your action set
        {
            var sets = SteamVR_Input.actionSets;
            return sets != null && sets.Length > 0 && sets[0].IsActive(SteamVR_Input_Sources.Any);
        }

        static void Announce()
        {
            string Type(uint i)
            {
                var err = ETrackedPropertyError.TrackedProp_Success;
                var sb = new System.Text.StringBuilder(64);
                OpenVR.System.GetStringTrackedDeviceProperty(i, ETrackedDeviceProperty.Prop_ControllerType_String, sb, 64, ref err);
                return err == ETrackedPropertyError.TrackedProp_Success ? sb.ToString() : "none";
            }
            uint left = OpenVR.System.GetTrackedDeviceIndexForControllerRole(ETrackedControllerRole.LeftHand);
            uint right = OpenVR.System.GetTrackedDeviceIndexForControllerRole(ETrackedControllerRole.RightHand);
            Log($"[Irisify] controllers: left={Type(left)} right={Type(right)} hmd={Type(OpenVR.k_unTrackedDeviceIndex_Hmd)} runtime=SteamVR");
        }
    }
}
