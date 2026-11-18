// Screenshot classes that became automatic checks (lessons A7, E12, E13). Added to every scenario like the comfort
// checks; RigHost calls ViewChecks.AddChecks(ctx) at the end. Fill in the hook points for your game.
using System;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;

namespace Irisify.Rig
{
    public static class ViewChecks
    {
        public static Func<Camera> Eye = () => Camera.main;
        public static Func<IEnumerable<Renderer>> OwnBody = () => Enumerable.Empty<Renderer>();      // the player's own body renderers (skinned too)
        public static Func<IEnumerable<Transform>> OwnBones = () => Enumerable.Empty<Transform>();     // head/neck/spine bones to keep away from the eye
        public static Func<string, IEnumerable<GameObject>> HeldModels = hand => Enumerable.Empty<GameObject>();   // real held item + proxies, per hand
        public static Func<IEnumerable<GameObject>> BodyAttachments = () => Enumerable.Empty<GameObject>();       // holster/pouch/pocket models
        public static Func<IEnumerable<(string widget, string text, RectTransform rect)>> VisibleTexts = () => Enumerable.Empty<(string, string, RectTransform)>();
        public static float Clearance = 0.15f, ConeDegrees = 20f, BusyHandRadius = 0.20f, EdgeBandDegrees = 10f;

        public static void AddChecks(ScenarioContext ctx)
        {
            var cam = Eye();
            if (cam == null) return;
            var eye = cam.transform;

            // Own body near or in front of the eye (bones and baked vertices via renderer bounds)
            var close = new List<string>();
            foreach (var b in OwnBones())
            {
                var d = b.position - eye.position;
                if (d.magnitude < Clearance || (Vector3.Angle(eye.forward, d) < ConeDegrees && d.magnitude < 0.6f)) close.Add($"{b.name} {d.magnitude:0.00} m");
            }
            foreach (var r in OwnBody().Where(r => r.enabled && r.gameObject.activeInHierarchy))
            {
                var p = r.bounds.ClosestPoint(eye.position);
                if ((p - eye.position).magnitude < Clearance) close.Add($"{r.name} bounds {(p - eye.position).magnitude:0.00} m");
            }
            ctx.Expect("view: no own body within 15 cm of the eye or in the central view cone", close.Count == 0, close);

            // One held model per hand, and no body attachment shown near a busy hand
            foreach (var hand in new[] { "left", "right" })
            {
                var held = HeldModels(hand).Where(g => g != null && g.activeInHierarchy).ToList();
                ctx.Expect($"view: at most one held model in the {hand} hand", held.Count <= 1, held.Select(g => g.name).ToList());
                if (held.Count == 0) continue;
                var near = BodyAttachments().Where(a => a != null && a.activeInHierarchy && (a.transform.position - held[0].transform.position).magnitude < BusyHandRadius)
                                            .Select(a => a.name).ToList();
                ctx.Expect($"view: no body model shown near the busy {hand} hand", near.Count == 0, near);
            }

            // Same information on two widgets; text in the top/bottom edge bands
            var texts = VisibleTexts().Where(t => !string.IsNullOrWhiteSpace(t.text)).ToList();
            var dupes = texts.GroupBy(t => Normalise(t.text)).Where(g => g.Key.Length >= 3 && g.Select(x => x.widget).Distinct().Count() > 1)
                             .Select(g => $"{g.Key}: {string.Join(", ", g.Select(x => x.widget).Distinct())}").ToList();
            ctx.Expect("view: no information shown by two widgets at once", dupes.Count == 0, dupes);
            var edge = new List<string>();
            float half = cam.fieldOfView / 2f;
            foreach (var t in texts)
            {
                var v = eye.InverseTransformPoint(t.rect.position);
                float pitch = Mathf.Atan2(v.y, v.z) * Mathf.Rad2Deg;
                if (v.z > 0 && Mathf.Abs(pitch) > half - EdgeBandDegrees) edge.Add($"{t.widget}: {t.text} at {pitch:0}°");
            }
            ctx.Expect("view: no text in the top or bottom 10° band", edge.Count == 0, edge);
        }

        static string Normalise(string s) => new string(s.ToLowerInvariant().Where(char.IsLetterOrDigit).ToArray());
    }
}
