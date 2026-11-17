# Engine playbooks

Pick the playbook from the engine fingerprint (SKILL.md section 1). Each gives the fastest route to: stereo + tracking, a scripting layer for game logic, and the tools to find mechanic functions. Everything after that (mechanic audit, redesign, recipes, testing) is engine-independent.

## Contents
1. Unreal Engine 4/5 — UEVR + UE4SS
2. RE Engine — REFramework
3. Unity — Mono and IL2CPP
4. Bethesda Creation Engine
5. Emulated console games
6. Custom / proprietary engines

## 1. Unreal Engine 4/5 — UEVR + UE4SS

Fingerprint: `<Game>/Binaries/Win64/<Game>-Win64-Shipping.exe`; `.pak`/`.utoc`/`.ucas` in `Content/Paks`.

| Tool | Use it for |
|---|---|
| **UEVR nightly** (praydog/UEVR-nightly) | Stereo rendering, head/controller tracking, UObjectHook, Lua + C++ plugin API, Blueprint VR API. Use a recent nightly; the old beta lacks most current features. |
| **UE4SS dev build** (UE4SS-RE/RE-UE4SS) | Live property viewer, object dumper, C++ and UHT header dumpers (mirror `.uproject`), EventViewerMod (live ProcessEvent call flow), Blueprint mod loader, Lua/C++ mods. |
| **FModel** / **retoc** / **repak** | Browse/extract cooked assets; pack IoStore and pak files. |
| **Matching Unreal Editor version** | Blueprint/pak mods against the mirror project (exact engine version). |

Layers of a UEVR mod, bottom-up (don't write C++ for what UObjectHook already does):
1. **Profile settings** (`%APPDATA%\UnrealVRMod\<ExeName>\config.txt`): rendering method (Native Stereo first; Synchronized Sequential / AFR when native stereo breaks effects; motion blur off), world scale, UI projection, aim method, roomscale.
2. **UObjectHook** (in-game menu, saved per profile): attach camera to pawn/head socket, attach components to controllers, persist property edits. Set **"Enabled at Startup"** or a shipped profile silently does nothing.
3. **Lua scripts** (`<profile>/scripts/*.lua`): game logic, hot-reloadable.
4. **C++ plugin** (`<profile>/plugins/*.dll`): per-frame hot paths, inline hooks (SafetyHook), ImGui UI, render-thread work.
5. **Pak / Blueprint mods**: new assets — hand meshes, holsters, wrist widgets, physics constraints. UEVR drives any `UMotionControllerComponent` when UObjectHook is active.

Discovery: UE4SS object/header dump → UEVR UObjectHook → Common Objects → Acknowledged Pawn (walk components and sockets) → EventViewerMod while performing each mechanic → `notes/hooks.md`.

Lua skeleton (verify signatures against https://praydog.github.io/uevr-docs before use):
```lua
local api = uevr.api
local vr = uevr.params.vr
local callbacks = uevr.sdk.callbacks

callbacks.on_pre_engine_tick(function(engine, delta)
    local pawn = api:get_local_pawn(0)
    if not pawn then return end
    -- hand traces, climb deltas, gestures, mechanic state machines
end)

callbacks.on_xinput_get_state(function(retval, user_index, xstate)
    -- synthesize the game's gamepad actions from VR gestures (cheapest trigger)
end)

callbacks.on_early_calculate_stereo_view_offset(function(device, view_index, world_to_meters, position, rotation, is_double)
    -- clamp/redirect camera (vehicles, tight spaces, cutscenes)
end)

callbacks.on_script_reset(function()
    -- restore every property and movement mode you changed
end)
```
UObjectHook from Lua: `UEVR_UObjectHook.activate()`, `get_first_object_by_class(cls, false)`, `get_or_add_motion_controller_state(component)`. UE4SS Lua: `RegisterHook("/Script/Module.Class:Function", fn)`, `FindFirstOf("Class")`, `NotifyOnNewObject(path, fn)`.

Reference mods: `praydog/SH2R-UEVR` (melee physics, two-handed aiming, items to hand), `Ashok0/SystemShock-UEVR` (gesture melee, ADS alignment, menus). Ship: profile folder zip + optional pak + README pinning the UEVR nightly and game build.

Known example: Subnautica 2 is UE5 and runs under UEVR (unstable in early access).

## 2. RE Engine — REFramework

Fingerprint: Capcom titles (RE2/3/4/7/8, DMC5, Monster Hunter Rise/Wilds, Dragon's Dogma 2…), `re_chunk_000.pak`.
- REFramework (praydog, open source) provides VR (for supported titles), a reflection-based Lua API, an object explorer, and a C++ plugin API. Lua scripts load from its autorun folder in the game directory.
- Discovery: the in-game object explorer and type browser stand in for UE4SS dumps; hook managed methods via the Lua SDK's hook functions.
- Verify current API names in the REFramework docs/wiki before writing scripts; the API differs from UEVR's.

## 3. Unity — Mono and IL2CPP

Fingerprint: `UnityPlayer.dll`, `<Game>_Data`. `Managed/Assembly-CSharp.dll` → Mono; `GameAssembly.dll` + `global-metadata.dat` → IL2CPP.
- **Mono:** decompile `Assembly-CSharp.dll` (ILSpy/dnSpyEx, or REA's .NET analysis) — near-source C#. Mods via BepInEx + Harmony patches.
- **IL2CPP:** generate stubs with Il2CppDumper or Cpp2IL; BepInEx IL2CPP builds or MelonLoader; Unhollower/Il2CppInterop for calling game types.
- VR core: load Unity's XR plugin (OpenXR) into the game if the engine version supports it, or use an existing Unity VR injector as the starting point; create an XR rig, reparent the game camera, add tracked hand objects. Study existing per-game Unity VR mods and Unity VR injector repos for the version you're on.
- After the VR core, the mechanic audit applies identically: Harmony prefix/postfix patches are your hooks; C# source makes the code side of the audit easy.

## 4. Bethesda Creation Engine

Skyrim and Fallout 4 have official VR versions with script extenders (SKSE VR, F4SE VR) and large VR mod ecosystems; build on those rather than injecting VR. Older Gamebryo titles (Fallout 3/New Vegas) have no official VR; treat them as custom engines for the VR core but use NVSE/xNVSE and the existing plugin ecosystem for game logic.

## 5. Emulated console games

Emulator-level VR exists for some titles (Cemu's BotW BetterVR as an example of graphic packs + hooks inside the emulator). The emulator is the engine: hook its renderer for stereo and its memory for game state; game logic lives in the guest code, so RE is done on the guest binary (console-specific tools).

## 6. Custom / proprietary engines

No framework: follow `re-pipeline.md` to find camera, projection, render loop, player state, input and mechanic functions, then `vr-from-scratch.md` to build the stereo/OpenXR core, then the mechanic work. Embed a scripting layer (Lua) early so mechanic logic can hot-reload. Budget: getting a clean synchronous-stereo core on an unknown engine is a large project; AFR first gets a playable build much sooner.
