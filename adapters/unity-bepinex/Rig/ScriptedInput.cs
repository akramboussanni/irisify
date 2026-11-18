// Virtual hands. While Active, every head/controller pose and button the mod and the game read comes from here.
// Put the override *inside* the input layer (the VR plugin's action getters and pose update), not in each feature,
// so features see scripted input exactly as they'd see real controllers. SubmersedVR's version patches the SteamVR
// Unity plugin's action-source getters and SteamVR_Behaviour_Pose.UpdateTransform (claude/vr-test-rig-* branch).
//
// Button changes are queued and applied at the start of the next frame (ScriptedInputDriver runs first), so every
// Update reader sees a press as "down this frame" exactly once, like a real button. Applying immediately from a
// scenario coroutine (which runs after Update) makes the down frame invisible to Update readers.
using System.Collections.Generic;
using UnityEngine;

namespace Irisify.Rig
{
    public struct RigPose { public Vector3 position; public Quaternion rotation; public RigPose(Vector3 p, Quaternion r) { position = p; rotation = r; } }

    public static class ScriptedInput
    {
        public static bool Active;
        public static RigPose Head = new RigPose(Vector3.zero, Quaternion.identity);
        public static RigPose Left = DefaultLeft, Right = DefaultRight;
        public static RigPose DefaultLeft => new RigPose(new Vector3(-0.2f, -0.35f, 0.3f), Quaternion.identity);
        public static RigPose DefaultRight => new RigPose(new Vector3(0.2f, -0.35f, 0.3f), Quaternion.identity);

        class Btn { public bool left, right; public int changedLeft = -10, changedRight = -10; }
        static readonly Dictionary<string, Btn> buttons = new Dictionary<string, Btn>();
        static readonly Dictionary<string, Vector2> axes = new Dictionary<string, Vector2>();
        static readonly List<(string, string, bool)> queued = new List<(string, string, bool)>();

        public static void Reset() { buttons.Clear(); axes.Clear(); queued.Clear(); Head = new RigPose(Vector3.zero, Quaternion.identity); Left = DefaultLeft; Right = DefaultRight; }
        public static void SetButton(string action, string hand, bool down) => queued.Add((action.ToLowerInvariant(), hand, down));
        public static void SetAxis(string action, Vector2 v) => axes[action.ToLowerInvariant()] = v;
        public static void ReleaseAll() { foreach (var kv in buttons) if (kv.Value.left || kv.Value.right) SetButton(kv.Key, "both", false); axes.Clear(); }

        public static void ApplyQueued()
        {
            int f = Time.frameCount;
            foreach (var (key, hand, down) in queued)
            {
                if (!buttons.TryGetValue(key, out var b)) buttons[key] = b = new Btn();
                if (hand != "right" && b.left != down) { b.left = down; b.changedLeft = f; }
                if (hand != "left" && b.right != down) { b.right = down; b.changedRight = f; }
            }
            queued.Clear();
        }

        // Read side: call these from your patched getters.
        public static bool State(string action, string hand) { if (!buttons.TryGetValue(action.ToLowerInvariant(), out var b)) return false; return hand == "left" ? b.left : hand == "right" ? b.right : b.left || b.right; }
        public static bool Down(string action, string hand) { if (!buttons.TryGetValue(action.ToLowerInvariant(), out var b)) return false; int f = Time.frameCount; return hand == "left" ? b.left && b.changedLeft == f : hand == "right" ? b.right && b.changedRight == f : (b.left && b.changedLeft == f) || (b.right && b.changedRight == f); }
        public static Vector2 Axis(string action) => axes.TryGetValue(action.ToLowerInvariant(), out var v) ? v : Vector2.zero;

        // Scenario helpers
        public static System.Collections.IEnumerator Move(string which, Vector3 to, float seconds)
        {
            RigPose from = which == "head" ? Head : which == "left" ? Left : Right;
            for (float t = 0; t < seconds; t += Time.deltaTime)
            {
                var p = new RigPose(Vector3.Lerp(from.position, to, t / seconds), from.rotation);
                if (which == "head") Head = p; else if (which == "left") Left = p; else Right = p;
                yield return null;
            }
        }
    }

    [DefaultExecutionOrder(-32000)]
    public class ScriptedInputDriver : MonoBehaviour
    {
        void Update() { if (ScriptedInput.Active) ScriptedInput.ApplyQueued(); }
    }
}
