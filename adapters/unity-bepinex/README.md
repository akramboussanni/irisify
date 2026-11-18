# Unity / BepInEx adapter

C# templates for the in-game half of Irisify, generalised from SubmersedVR (`Input/InputDiagnostics.cs` on `deep-vr`,
`TestRig/*` on `claude/vr-test-rig-*`), where the originals ran against Subnautica on the test laptop. **These
generalised files have not been compiled here** (no Unity references on this machine): copy them into your plugin,
fix the namespace, and fill in the marked hook points.

| File | What | Lesson |
|---|---|---|
| `Core/SafePatcher.cs` | class-by-class Harmony patching, the `patches: N applied, M failed` boot line | B1, B2 |
| `Core/BuildStamp.cs` | logs `[Irisify] build <id>` from the `build.json` that `irisify deploy` writes | A2 |
| `Diagnostics/InputFocusDiag.cs` | controller types, `IsInputAvailable`, action edges, from boot | C1, D4 |
| `Input/InputClaims.cs` | one owner per press; execution order = claim priority | D2, D6 |
| `Settings/SettingsMigration.cs` | versioned, ordered migrations so new defaults reach existing users | A5, B3 |
| `Rig/RigHost.cs` | command channel, results writer, scenario registry; off unless `IRISIFY_RIG=1` | A9 |
| `Rig/ScriptedInput.cs` | virtual hands, queued button edges | A8 |
| `Rig/ComfortMonitor.cs` | snap / tilt / turn / drift events, added to every scenario | E9 |
| `Rig/ViewChecks.cs` | own body near the eye, one held model per hand, body model near a busy hand, duplicated info, edge-band text | A7, E12, E13 |
| `Body/SkeletonProbe.cs` | log every bone, hide by verified subtree, proportion checks | E12 |
| `Rig/Capture.cs` | `<scenario>-<moment>.png` with the moment's question | A7 |

`RigHost` also needs a small JSON helper (`MiniJson.ParseArray` / `MiniJson.Serialize`): use the one your game ships
(Unity games often include MiniJSON), or SubmersedVR's `Utils/MiniJson.cs`.

Boot wiring, in your plugin's `Awake`:

```csharp
BuildStamp.Log(Logger.LogInfo);
SafePatcher.PatchAll(new Harmony(GUID), typeof(Plugin).Assembly, Logger.LogInfo, Logger.LogError);
SettingsMigration.Run(get, set, save, Logger.LogInfo);
// once the VR rig exists:
rig.AddComponent<InputFocusDiag>();
Irisify.Rig.RigHost.Install(rig);
Irisify.Rig.RigHost.Scenarios["holster_draw_stow"] = HolsterScenarios.DrawStow;
```
