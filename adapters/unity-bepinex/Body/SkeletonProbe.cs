// Never assume a skeleton (lessons E12). At setup: log every bone with its path, position and children; pick bones
// to hide by verified subtree; after any change, assert the body's proportions.
using System.Collections.Generic;
using System.Linq;
using UnityEngine;

namespace Irisify.Body
{
    public static class SkeletonProbe
    {
        public static void LogAll(Transform root, System.Action<string> log)
        {
            foreach (var t in root.GetComponentsInChildren<Transform>(true))
                log($"[Skeleton] {Path(root, t)} pos {t.position} children [{string.Join(", ", t.Cast<Transform>().Select(c => c.name))}]");
        }

        public static string Path(Transform root, Transform t)
        {
            var parts = new List<string>();
            for (var x = t; x != null && x != root.parent; x = x.parent) parts.Add(x.name);
            parts.Reverse();
            return string.Join("/", parts);
        }

        // The highest bone whose subtree contains the head and none of the forbidden bones (pelvis, chest, limbs).
        // Returns null (and logs why) rather than guessing: collapsing "the head's parent" once collapsed a whole body.
        public static Transform HeadSubtree(Transform head, IEnumerable<Transform> forbidden, System.Action<string> log)
        {
            var bad = new HashSet<Transform>(forbidden.Where(f => f != null));
            Transform best = null;
            for (var x = head; x != null; x = x.parent)
            {
                if (x.GetComponentsInChildren<Transform>(true).Any(bad.Contains)) break;
                best = x;
            }
            log(best == null ? "[Skeleton] no safe head subtree found: not hiding the head" : $"[Skeleton] hiding subtree {best.name} (contains the head, no torso or limbs); children: {string.Join(", ", best.GetComponentsInChildren<Transform>(true).Select(c => c.name))}");
            return best;
        }

        // Feet near the floor, torso below the eyes, head above the pelvis.
        public static List<string> CheckProportions(Vector3 eye, Vector3 floor, Transform pelvis, Transform chest, Transform leftFoot, Transform rightFoot)
        {
            var problems = new List<string>();
            foreach (var f in new[] { leftFoot, rightFoot })
                if (f != null && Mathf.Abs(f.position.y - floor.y) > 0.25f) problems.Add($"{f.name} {f.position.y - floor.y:0.00} m off the floor");
            if (chest != null && chest.position.y > eye.y - 0.15f) problems.Add($"{chest.name} not below the eyes");
            if (pelvis != null && chest != null && pelvis.position.y > chest.position.y) problems.Add("pelvis above chest: spine order assumed wrong?");
            return problems;
        }
    }
}
