// One-eye screenshots named <scenario>-<moment>.png, recorded with the moment's question (screenshot-review.md).
// Renders the head camera (plus your UI camera on top) into a texture, so it works without window focus and
// under Proton, where the VR mirror window only fills part of the backbuffer.
using System.Collections;
using System.Collections.Generic;
using System.IO;
using UnityEngine;

namespace Irisify.Rig
{
    public static class Capture
    {
        public static System.Func<Camera[]> Cameras = () => Camera.main != null ? new[] { Camera.main } : new Camera[0];   // world camera first, UI cameras after
        public static int Width = 1280, Height = 800;

        public static IEnumerator Take(string scenario, string moment, string question, List<Dictionary<string, object>> into)
        {
            yield return new WaitForEndOfFrame();
            var file = $"{scenario}-{moment}.png";
            var rt = RenderTexture.GetTemporary(Width, Height, 24);
            foreach (var cam in Cameras())
            {
                var prev = cam.targetTexture; cam.targetTexture = rt; cam.Render(); cam.targetTexture = prev;
            }
            var prevActive = RenderTexture.active; RenderTexture.active = rt;
            var tex = new Texture2D(Width, Height, TextureFormat.RGB24, false);
            tex.ReadPixels(new Rect(0, 0, Width, Height), 0, 0); tex.Apply();
            RenderTexture.active = prevActive; RenderTexture.ReleaseTemporary(rt);
            File.WriteAllBytes(Path.Combine(RigHost.Dir, "shots", file), tex.EncodeToPNG());
            Object.Destroy(tex);
            into.Add(new Dictionary<string, object> { ["file"] = file, ["moment"] = moment, ["question"] = question });
        }
    }
}
