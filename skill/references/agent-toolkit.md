# Agent toolkit: Universal Modder + REA

This skill runs on top of the same tooling the agent-built game mods used. Universal Modder supplies the game-handling machinery (scan, backups, launching, screenshots, safe input, recording, knowledge base, packaging checks, subagent team). REA supplies reverse engineering through MCP. This skill adds the VR-specific layer: engine playbooks for VR, the mechanic audit and VR redesign, VR design rules, and VR testing.

Check exact flags with `um <command> --help` and `rea --help`; both projects move fast.

## Contents
1. Install
2. How the pieces map onto this skill's phases
3. `um` commands used in VR work
4. REA in practice
5. Running as a team (orchestrator + workers)
6. Logs, plans and field notes
7. Guardrails inherited from Universal Modder

## 1. Install

Check what's present first (`um --version`, `rea doctor`, the agent's plugin/MCP list). Install only what's missing, after telling the user what will be installed.

**Universal Modder** (`rehan-remade/universal-modder`, MIT). Prerequisites: Git, Python 3.10+, ffmpeg; `uv` recommended; Blender only for 3D-to-sprite renders (not needed for VR).
- Claude Code: `/plugin marketplace add rehan-remade/universal-modder` then `/plugin install universal-modder@universal-modder` (puts `um` on PATH).
- Any agent, skills only: `npx skills add https://github.com/rehan-remade/universal-modder`; then install the CLI with `uv tool install git+https://github.com/rehan-remade/universal-modder` (or `pipx install git+...`).
- Codex / Gemini CLI / Cursor / VS Code / OpenCode have their own commands in its README.
- fal (AI asset generation) is optional; only set up a key if the mod needs generated assets such as hand models or holster meshes.

**REA** (`morluto/rea`, MIT). Node.js 22/24/26 (current minimum patch versions in its README).
- `npx rea-agents setup` (choose the agent, e.g. Claude Code). It registers the MCP server and workflow instructions and backs up existing config.
- Verify with `rea doctor`, then restart the agent.
- Native backends use what the user has: Ghidra (free), IDA, Hopper or Kuna. Commercial tools must be legally licensed by the user.

## 2. How the pieces map onto this skill's phases

| Phase (SKILL.md) | Universal Modder | REA | This skill adds |
|---|---|---|---|
| Recon | `um kb search "<game>"`, `um scan` (engine, version, .NET vs native, anti-cheat, loaders, saves, ranked routes), `game-recon` skill → `MODDING_PLAN.md` | — | Existing VR mods/profiles check; VR route choice (UEVR / REFramework / Unity XR / custom core) |
| Safe lab | `um backup` snapshot of saves; game set to windowed mode | — | Pin game build + framework version |
| Close the loop | `um win launch / shot / record / drive / kill`, `game-automation` skill (in-game agent bridges) | — | VR observability: state/event logs, command channel, virtual hands (`testing-loop.md`) |
| VR core | `mod-any-game` engine playbooks (UE4SS, BepInEx, etc.) | Static RE of the game binary / assemblies | `engine-playbooks.md`, `re-pipeline.md`, `vr-from-scratch.md` |
| Mechanic audit | `game-research-websearch` skill for the wiki/patch-notes cross-check | Code side for non-reflective engines | `mechanics.md`, `vr-design.md` |
| Implement | Hot-reload pattern | Finding functions behind mechanics | Recipes |
| Verify | "The running game is the final oracle": `um win shot` after every reload | — | Scenario tests, human feel playtests |
| Package | `um publish check` (blocks game files, decompiled code, leaked keys), `publish-mod` skill | — | VR README (headsets/runtimes tested, comfort settings) |
| Share | `um kb new` / `um kb check` / `um kb pr` (PR only with user approval) | — | VR-specific gotchas |

## 3. `um` commands used in VR work

- `um scan` — first command on any game. Read its route ranking, then apply the VR routing in SKILL.md section 1.
- `um backup` — snapshot saves before the first injection and before every risky test; diff and restore when a test corrupts a save.
- `um win launch` — start the game (with any launch flags) so the agent controls the session.
- `um win shot` — screenshot the game window (use the desktop mirror/spectator view in VR). Take one after every hot reload and look at it.
- `um win drive` — input that reaches only the game window. Use it to drive the flat game (menus, keyboard/gamepad actions) during automated tests; VR hand input still comes from the mod's scripted virtual-hands provider. Ask the user before taking over input.
- `um win record` — window capture with game-only audio; use for bug repros and for the showcase video.
- `um win ps` / `um win kill` — find and stop the game process by PID only (never by name-wide kills).
- `um win reg` — registry inspection when a game stores settings or install paths there.
- `um video contact` — contact sheets from recordings, handy to review a test run's frames at a glance.
- `um kb search | show | new | check | pr` — prior art and field notes.
- `um publish check` — run before every release zip.

## 4. REA in practice

- Static work goes through REA's MCP tools: decompile the game's executable or assemblies, search strings (mechanic names, animation names, prompt text like "Climb", "Interact"), follow cross-references, rename and annotate as you learn. The disassembler database becomes shared memory across sessions.
- Unity Mono, XNA/FNA and other .NET games: REA's .NET analysis gives near-source C#; mechanic functions come straight from it.
- Gaps on Windows PC games: Windows Ghidra support is experimental, live process capture is Linux/macOS only, and attaching to a running process isn't documented. Do live work (breakpoints, value scans, frame captures) with x64dbg, Cheat Engine and RenderDoc, and record what you confirm back into the database.
- Its documented workflow (observe → dissect → spec → build → iterate) matches this skill's: observe the mechanic in game, dissect it in code, spec the VR version in `notes/mechanics.md`, build, iterate with tests.

## 5. Running as a team (orchestrator + workers)

Universal Modder ships three subagent roles for multi-day mods (several times the token cost of a single agent):
- **mod-orchestrator** — plans, dispatches the workers, checks their claims against logs and files, reports to the user. Start it the way your agent runs sub-agents (for Claude Code: `claude --agent mod-orchestrator`).
- **mod-game-worker** — the only agent allowed to touch the running game: build, deploy, launch, probe, measure, fix.
- **mod-offline-worker** — never touches the game: studies dumps and SDK data, designs features, writes code against stubs, hands live probes to the game worker.

Use the same split for VR, with these VR duties:
- Orchestrator owns `notes/mechanics.md` (the coverage map) and the milestone plan; it rejects any "done" without a passing scenario test or a logged result.
- Game worker owns the VR runtime and the game process: injection, hot reload, scenario runs, screenshots, log collection. Only one agent touches the game at a time.
- Offline worker does the mechanic audit (strings, data tables, bindings, code dumps; wiki as cross-check), REA analysis, VR redesigns, recipe code and scenario files.
For small jobs, one agent doing all three in sequence is cheaper and fine.

## 6. Logs, plans and field notes

Keep Universal Modder's conventions and add the VR files:
- `MODDING_PLAN.md` — from recon: ranked routes and the chosen one.
- `MODLOG.md` — written before any code: task understanding, plan, assumptions; then a running log of decisions.
- `notes/hooks.md`, `notes/signatures.md`, `notes/mechanics.md`, `notes/test-matrix.md`, `notes/gotchas.md` — this skill's working notes.
- At the end, a knowledge-base field note (`um kb new --game "<Game>" --title "<Title>" --from-scan <slug> --agent "<agent>"`, validate with `um kb check`). It must include: exact versions that worked (game build, UEVR/REFramework/loader version, runtime), chosen route and why, what the engine actually does (camera, render, input, key mechanic functions), how it was verified, and gotchas as symptom → cause → fix. Opening the PR (`um kb pr`) needs the user's approval.

## 7. Guardrails inherited from Universal Modder

- Only games the user owns. Never inject into anti-cheat-protected online games, never write cheats against other players, never bypass anti-cheat, DRM or ownership checks.
- Never ship game files or decompiled code; ship code, own assets, patches or converters. `um publish check` enforces this.
- Back up saves before touching them.
- Kill processes by PID only.
- Ask before controlling the user's mouse or keyboard, before installing loaders into game folders, and before publishing anything (including PRs).
