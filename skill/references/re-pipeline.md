# Reverse-engineering pipeline (any engine)

Use this whenever there is no ready-made framework (no UEVR/REFramework/BepInEx path), or when a framework doesn't expose what a mechanic needs. The goal is always the same short list of things: the **camera**, the **projection**, the **player state**, the **input path**, the **render loop**, and the **functions behind each mechanic**.

## Contents
1. Tools
2. Recon (first hour)
3. Finding the things VR needs
4. Hooking
5. Surviving game updates
6. Working with an AI-driven disassembler

## 1. Tools

**REA (Reverse Engineer Anything, `morluto/rea`, MIT)** is the default front door when installed: one MCP server that connects the agent to Ghidra, IDA, Hopper or Kuna (whichever the user has), plus built-in static analysis for .NET assemblies (Unity Mono games, XNA/FNA/MonoGame games), JavaScript/Electron, Android (JADX) and more. Install with `npx rea-agents setup` (pick the agent, e.g. Claude Code), check with `rea doctor`, restart the agent. Know its gaps for PC games: Windows Ghidra support is experimental, live process-behavior capture is Linux/macOS only, and it doesn't document attaching to a running process or reading its memory. So on Windows, use REA for static work and pair it with x64dbg / Cheat Engine / RenderDoc for everything live. If REA isn't installed, use the disassembler's own MCP bridge below.

| Tool | Role |
|---|---|
| Ghidra (free) + an MCP bridge (via REA, or GhidraMCP and alternatives) | Static analysis, decompilation, renaming and annotating functions. With MCP the agent can query and annotate the database directly. |
| IDA Pro (paid) + ida-pro-mcp, or Binary Ninja + its MCP, or radare2 + r2mcp | Same role; pick what the user owns. |
| x64dbg | Live debugging: breakpoints, hardware write-breakpoints, call stacks at the moment something happens. |
| Cheat Engine | Value scanning (find the camera position, health, oxygen, movement mode in memory), "find what writes to this address", structure dissection. |
| ReClass.NET | Reconstruct class layouts from live memory. |
| RenderDoc / PIX | Frame capture: which draw calls are the 3D scene, which are UI, which passes are screen-space (break in stereo), where the view/projection constant buffers are. |
| MinHook or SafetyHook | Function detours. |
| Kiero-style D3D11/D3D12/Vulkan hook scaffolding | Hook Present / ExecuteCommandLists / vkQueuePresent to own the frame. |
| Frida (optional) | Quick runtime tracing and prototyping hooks without rebuilding a DLL. |

MCP bridges for disassemblers are community projects of varying maturity; check the repo and its README before installing, and verify their output (LLM renames and summaries can be wrong).

## 2. Recon (first hour)

1. Engine fingerprint: DLL names, file extensions, strings (`strings`-style scan for engine names, version strings, shader compiler names), PDB paths, RTTI class names.
2. Graphics API: which of `d3d11.dll`, `d3d12.dll`, `vulkan-1.dll` is loaded; whether the game already ships an OpenXR/OpenVR loader (some flat games do, from cut VR support; that's a huge shortcut).
3. Protection: packers, DRM wrappers, anti-tamper or kernel anti-cheat. Anti-cheat or online-only → stop (see SKILL.md scope). Packed executables need a clean dump before static analysis; do this only for the user's own copy for interoperability, and don't help strip DRM to enable piracy.
4. Scripting layers: many engines run game logic in a VM (Lua, Mono/.NET, Papyrus, proprietary). If one exists, hook the VM: you get names and readable logic for free.
5. Developer leftovers: console commands, debug cameras, free-cam, photo mode. A photo mode is a ready-made decoupled camera.

Write `notes/recon.md` with all of this before going deeper.

## 3. Finding the things VR needs

**Camera transform.** Cheat Engine: scan the camera position as floats while moving/rotating, narrow down, "find what writes" → the camera update function. In RenderDoc, the view matrix in the frame's constant buffers confirms it. Find the *last* write before rendering; that's where the HMD pose goes.

**Projection.** Look for the FOV value (scan for the degrees or radians value the options menu shows), then the function that builds the projection matrix from it. VR needs an asymmetric frustum per eye (from OpenXR's per-view FOV angles), so you must be able to replace the whole matrix, not just FOV.

**Render loop / scene render function.** Breakpoint on Present, walk the call stack up to the main loop; find the function that renders the 3D scene for one view. Calling it twice (once per eye) with different view matrices is the gold-standard stereo method.

**Player state.** Position, velocity, movement mode (walking, swimming, climbing, in-vehicle), current tool/item, health/oxygen. Value scans + "find what accesses" → the player class; reconstruct it in ReClass; recover the class name from RTTI.

**Input path.** Find where the game reads input (XInput, Raw Input, DirectInput, SDL, a platform layer) and where it converts raw input into actions. Inject VR input at the action level when possible; at the raw level (fake gamepad) as the cheapest fallback.

**Mechanic functions.** For each verb in the mechanic audit: trigger it in-game with a breakpoint set on a related value (ladder state flag, interaction prompt string xref, animation name string xref) and record the function. String xrefs ("Climb", "Interact", animation names, localization keys) are the fastest entry points.

**UI.** Find the UI render pass (RenderDoc) so it can be redirected to an offscreen texture and shown on a quad or wrist panel.

Log every find in `notes/hooks.md`: name, address/RVA, signature (AOB pattern), how found, confidence.

## 4. Hooking

- Ship as a proxy DLL (`dxgi.dll`, `dinput8.dll`, `version.dll`, `winmm.dll` — whichever the game loads from its folder) or via a loader the community already uses. No system-wide injection.
- Detour functions with MinHook/SafetyHook; keep hooks minimal and call the original.
- Split native code into a tiny **host DLL** that installs hooks once and a **logic DLL** that the host can unload/reload on a hotkey or file change. Hot reload is what makes agent iteration fast (seconds instead of a full game restart).
- Prefer an embedded scripting layer (Lua via sol2, or the engine's own VM) for gameplay logic, same reason.

## 5. Surviving game updates

- Resolve every address by AOB signature at startup, never hardcode offsets; fall back to RTTI/vtable lookups or string xrefs.
- On a failed signature, disable that feature and log loudly rather than crash.
- Keep a `notes/signatures.md` with the pattern, the surrounding function, and how to re-find it by hand.

## 6. Working with an AI-driven disassembler

- Start from strings, imports and RTTI, not from `main`; let the agent rename functions as it goes and keep the database as the shared memory between sessions.
- Confirm every important conclusion dynamically (breakpoint hit, value changes as expected) before building on it. Static guesses about game code are wrong often enough that unverified hooks waste more time than they save.
- Parallelize: one subagent per subsystem (camera/render, player/movement, input, UI, each mechanic cluster), each writing to `notes/hooks.md`.
