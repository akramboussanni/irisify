// One owner per press (lessons D2, D6). A physical feature claims the buttons it takes from the game while it owns a
// press; the input layer reports them as not pressed to the game until release. The first claimer wins, so the
// execution order of features *is* the claim priority: body spot (-1000) > grab near hand (-900) >
// pointing gesture (-850) > water/free grab (-750) > game action. Write that order into design/controls.json.
using System.Collections.Generic;

namespace Irisify
{
    public static class InputClaims
    {
        static readonly Dictionary<string, string> owner = new Dictionary<string, string>();   // button -> owner
        public static System.Action<string> Log = s => { };

        public static bool TryClaim(string who, params string[] buttons)
        {
            foreach (var b in buttons)
                if (owner.TryGetValue(b, out var o) && o != who) return false;
            foreach (var b in buttons) owner[b] = who;
            Log($"[InputClaims] {who} claims {string.Join(", ", buttons)}");
            return true;
        }

        public static void Release(string who)
        {
            var mine = new List<string>();
            foreach (var kv in owner) if (kv.Value == who) mine.Add(kv.Key);
            foreach (var b in mine) owner.Remove(b);
            if (mine.Count > 0) Log($"[InputClaims] {who} released");
        }

        public static bool IsClaimed(string button) => owner.ContainsKey(button);
        public static Dictionary<string, string> Snapshot() => new Dictionary<string, string>(owner);
    }
}
