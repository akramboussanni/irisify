// View motion the player didn't cause (lessons A7, E9; skill/references/comfort-and-overwhelm.md). Every rendered
// frame, after all LateUpdates, compare the rig's world pose with the last frame, excluding the scripted head's own
// motion. Hook points to fill in: RigTransform (the tracking origin the game moves), PlayerVelocity, InVehicle,
// PlayerGaveInput, and CutCovered (true in the frame your blink/fade starts).
using System;
using System.Collections.Generic;
using UnityEngine;

namespace Irisify.Rig
{
    [DefaultExecutionOrder(32000)]
    public class ComfortMonitor : MonoBehaviour
    {
        public static Func<Transform> RigTransform = () => null;
        public static Func<Vector3> PlayerVelocity = () => Vector3.zero;
        public static Func<bool> InVehicle = () => false, PlayerGaveInput = () => false, CutCovered = () => false, RigWindow = () => false;
        public static readonly List<Dictionary<string, object>> Events = new List<Dictionary<string, object>>();
        Vector3 lastPos; Quaternion lastRot; bool has; float inputUntil, turnFor, driftFor;

        public static void Reset() => Events.Clear();

        void LateUpdate()
        {
            var t = RigTransform();
            if (t == null) { has = false; return; }
            float dt = Mathf.Max(Time.deltaTime, 1e-4f);
            if (PlayerGaveInput()) inputUntil = Time.time + 2.5f;
            bool excused = Time.time < inputUntil || RigWindow();
            if (has)
            {
                Vector3 d = t.position - lastPos;
                float unexplained = (d - PlayerVelocity() * dt).magnitude;
                float ang = Quaternion.Angle(lastRot, t.rotation);
                float yawRate = Mathf.Abs(Mathf.DeltaAngle(lastRot.eulerAngles.y, t.rotation.eulerAngles.y)) / dt;
                float tilt = Vector3.Angle(lastRot * Vector3.up, t.rotation * Vector3.up);
                if ((unexplained > 0.75f || ang > 10f) && !CutCovered() && !RigWindow()) Add("snap", unexplained, ang);
                if (!InVehicle())
                {
                    if (tilt > 0.5f && !excused) Add("tilt", tilt, 0);
                    turnFor = (yawRate > 3f && !excused) ? turnFor + dt : 0; if (turnFor > 0.5f) { Add("turn", yawRate, 0); turnFor = -999; }
                    float speed = d.magnitude / dt;
                    driftFor = (speed > 0.25f && !excused) ? driftFor + dt : 0; if (driftFor > 0.5f) { Add("drift", speed, 0); driftFor = -999; }
                }
            }
            lastPos = t.position; lastRot = t.rotation; has = true;
        }

        static void Add(string kind, float a, float b) => Events.Add(new Dictionary<string, object> { ["kind"] = kind, ["value"] = Math.Round(a, 3), ["deg"] = Math.Round(b, 2), ["frame"] = Time.frameCount });

        public static void AddChecks(ScenarioContext ctx)
        {
            ctx.Expect("comfort: no view snaps, tilts, turns or drift the player didn't cause", Events.Count == 0, new List<Dictionary<string, object>>(Events));
        }
    }
}
