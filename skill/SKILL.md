---
name: irisify
description: Turn a flat PC game into a deep VR conversion with an AI agent. Every mechanic is physical where that's better (ladders, vehicles, hatches, holstered inventory, tools, swimming, combat), the UI lives on the body and gear, and everything is checked by a headset-free test rig before the human puts the headset on. Covers reverse engineering (Universal Modder, REA, Ghidra/IDA), frameworks (UEVR/UE4SS, REFramework, BepInEx/MelonLoader), controller bindings and prompts for the user's real headset (Steam Frame, Index, Touch, WMR), test machines, parallel agents and a dashboard for the human. Use whenever someone wants to make or improve a VR mod, motion controls, VR UI or comfort, a VR mechanics audit, or names a game and VR ("make Subnautica feel native in VR").
---

# Irisify: flat game → deep VR, with gates

Most community VR mods add stereo, head tracking and a gun on the controller, then stop. This skill goes further:
every mechanic and every piece of UI is redesigned for VR, implemented through the game's own functions, and tested
automatically. It's also built from a project where an agent got the order of things wrong. Seven areas were built
before anything ran, and most of the user's complaints were about control-scheme, comfort and discoverability gaps
that a design step would have caught. So this skill is **gated**: the workflow refuses to move on without evidence.
Read `references/lessons.md` once before you start. It explains why each gate exists.

Agent-agnostic: any coding agent with a shell can follow it. Tools are plain CLIs (`irisify`, `um`, the engine's
loaders). Where a step needs the human (sudo, a sign-in, putting the headset on), it says so.

## The workflow

Run `irisify status` at any time. It prints the current phase, which gates pass, and the next action. The dashboard
(`irisify dashboard`) shows the same for the human.

| # | Phase | Read | Gate to leave it |
|---|---|---|---|
| 0 | **Setup**: machines, links, toolchain | `references/machines.md`, `references/agent-toolkit.md` | `irisify machine check` green for every machine with a role |
| 1 | **Intake**: detect, then grill the user with judgment | `references/intake.md` | `intake` |
| 2 | **Evidence and recon**: engine, build, existing VR work, input path | `references/re-pipeline.md`, `references/engine-playbooks.md` | `design/01-evidence.md` exists |
| 3 | **Platform preflight** on each machine that runs the game | `references/gates.md` (platform) | `platform` |
| 4 | **First boot** on the user's real headset | `references/testing-loop.md` §0 | **`first-boot` (hard stop)** |
| 5 | **Design**: the nine artifacts | `references/design-process.md` + the review files | `design` (user signs off the decisions) |
| 6 | **Vertical slice**: one mechanic end to end + the foundations | `references/mechanics.md`, `references/architecture.md` | `slice` (includes a human feel check) |
| 7 | **Breadth**: remaining mechanics, parallel workers | `references/integration.md` | per-feature checklist in `gates.md` |
| 8 | **Ready for headset**, playtest, feedback loop | `references/screenshot-review.md`, `design-process.md` (feedback loop) | `ready` |
| 9 | **Package**; game-update routine | `references/agent-toolkit.md` §6–7, `testing-loop.md` §8 | `irisify publish check` |

Phases 2 and 3 can run in parallel. Phase 4 needs 3. Nothing in 5–9 is built before phase 4 passes. If you can't
run the game yourself, ask the user to launch it now, not after features exist.

## Hard rules (each one is a lesson from the field)

1. **Nothing is done until it has run.** "Builds with no warnings" is not a result. Every mechanic needs a passing
   scenario or a logged result in the game, and every claim names the build id it was seen on.
2. **Patch class by class.** One bad target must not disable the mod. Log `patches: N applied, M failed` at boot.
   In transpilers, keep labels (edit in place, or `MoveLabelsFrom`). Explicit interface methods are named
   `IInterface.Method`.
3. **Focus first, bindings second.** When buttons don't arrive: Steam Input for the game (must be off), runtime focus
   (`IsInputAvailable`, `ShouldApplicationPause`, `bActive`), *then* bindings. Poses working proves nothing about
   buttons.
4. **Read the controller's real profile.** Detect the controller type, read the runtime's input profile, generate
   bindings and prompts from `design/controls.json`. Never hand-write either.
5. **Grips grab, nothing else. One owner per input per context per holding state.** No shortcut left next to its
   physical replacement. Every manifest action bound or dropped with a reason.
6. **Design the cross-cutting things once, before breadth:** control scheme, body map (calibration, neck pivot, body
   yaw), information placement, comfort plan. The orchestrator owns them.
7. **Locomotion never steers by the head.** Design travel, cruise and fine positioning, each with a mechanic, and
   measure effort per metre against targets.
8. **Immersion, not realism.** Pick the lightest physical form that keeps the meaning, like the rounds in an Alyx
   magazine. Information goes on the thing, then the body, then the world, and flat only when nothing else fits.
9. **Ship it on.** One coherent preset on by default, discoverable in game (visible models, rings, one-time hints).
   Changing a default needs a settings migration. Runtime kill switches never persist.
   **A fail-safe never writes settings:** an error stops the feature for the session through
   `FeatureSuspend.TurnOff`, logs `[Irisify:suspend]`, and fails the scenario. Run `irisify failsafe <src>` before
   merging. Ask yourself where any defensive disable's state goes (lessons A13).
10. **The camera never moves without input.** Cuts the game needs are covered by a blink. Other cuts are removed.
    The head can't go through hulls.
11. **Every let-go has a visible outcome.** Pick targets from the ray the player uses, never the game's hover.
12. **Look at the screenshots with a question.** A PASS without a reviewed image proves nothing about what's on
    screen. Show the user before/after images.
13. **One writer per target.** Workers use branches and `verify-branch` on the rig. Only the integrator deploys, from
    the integration branch, under a lock, with a stamped build id.
14. **Ask what only the user knows, decide the rest.** Blocking questions first, at most four at a time, always with a
    recommendation. Feel questions after they've played. Always ask before anything outward-facing.

## AI-first: the agent drives, the dashboard shows

You run everything: setup, checks, suites, deploys. The human doesn't configure anything in the dashboard. It's a
visualizer, there so they can see what's happening, which sessions work on which features, and what you need from
them. Keep it true:

- **Report as you work.** `irisify agent start <you> "<what you're doing>" --feature <id> --branch <b>` when you begin,
  `irisify agent status <you> "<step>"` at each meaningful step, `irisify agent blocked|done <you> "..."` at the end.
  Use your session name as `<you>` so the human can match it to the session in their app.
- **Track features.** `irisify feature set <id> --title "..." --state idea|design|building|testing|merged|in-headset|done`
  with the scenarios that prove it.
- **Ask, don't instruct in prose.** Anything only the human can do (sudo, a password, a sign-in, a click on the
  headset, a feel check, a decision) goes through `irisify ask new "<one clear instruction>" --why "..." --command "<exact
  command>" --kind do|decide|check`. It appears at the top of their dashboard. `machine check` and `doctor` file their
  own asks for steps marked "you", and close them once they pass. Mark an ask done yourself when you can verify it.
- **Still tell them in chat** what you asked and why, briefly, and point them at the dashboard.

## Tools

`irisify` is the CLI (see the repo README). The ones you'll use most: `status`, `agent`, `feature`, `ask`,
`machine add|check`, `doctor platform|input-focus`, `controllers detect|lint|bindings|prompts`,
`suite plan|run <suite>` (default `auto`), `scenarios lint`, `failsafe <src>`, `shots review`, `gate first-boot`, `deploy`,
`integrate`, `verify-branch`, `fanout`. Start the dashboard for the human with `irisify dashboard` and show them
screenshots there instead of describing them.

## Reference files

| File | What |
|---|---|
| `references/lessons.md` | the root-cause analysis these rules come from |
| `references/design-process.md` | the nine design artifacts, the design gate, the feedback loop |
| `references/intake.md` | detect-then-ask, the question bank, when to stop |
| `references/gates.md` | every gate's checklist, and which commands each gate unlocks |
| `references/machines.md` | machines, roles, SSH/adb links, setup steps, headsets |
| `references/controllers.md` | detection, real profiles (Steam Frame), bindings and prompts generation |
| `references/control-scheme.md` | rules and the per-context table |
| `references/immersion.md` | the immersion review: presence vs tedium |
| `references/discoverability.md` | defaults, migrations, hints, the discoverability table |
| `references/comfort-and-overwhelm.md` | comfort rules and metrics, overwhelm budgets |
| `references/screenshot-review.md` | moments, questions, agent and human review |
| `references/integration.md` | orchestrator/workers, integrate, verify-branch |
| `references/testing-loop.md` | the closed loop: rig, scripted hands, scenarios, suites |
| `references/mechanics.md` | audit, redesign and recipes per mechanic |
| `references/vr-design.md` | comfort, image, UI sizing, locomotion and body |
| `references/architecture.md` | shared VR library + per-game adapter |
| `references/engine-playbooks.md` | Unreal (UEVR/UE4SS), RE Engine, Unity, Creation, emulators, custom |
| `references/re-pipeline.md`, `references/vr-from-scratch.md` | reverse engineering; a VR core for custom engines |
| `references/agent-toolkit.md` | Universal Modder (`um`) and REA |

## Route by engine

| Fingerprint | Engine | VR route |
|---|---|---|
| `<Game>-Win64-Shipping.exe`, `.pak`/`.utoc`/`.ucas` | Unreal 4/5 | UEVR + UE4SS |
| `re_chunk_000.pak` | RE Engine | REFramework |
| `UnityPlayer.dll` + `_Data/Managed` (Mono) or `GameAssembly.dll` (IL2CPP) | Unity | BepInEx / MelonLoader + Harmony; Irisify's Unity adapter (`adapters/unity-bepinex/`) |
| Skyrim / Fallout 4 | Creation | official VR versions + SKSE/F4SE VR |
| emulator | console | emulator-level hooks |
| anything else | custom | full RE pipeline + your own VR core |

Check for existing VR work first. Improving a good base (as SubmersedVR was for Subnautica) beats starting over.

## Decision points: ask the user, with a recommendation

- A redesign changes game balance (slower actions, timing windows, stamina or oxygen pressure).
- The tier of a frequent mechanic (physical / assisted / button) where reasonable players would differ.
- Comfort defaults (turning, vignette, blink).
- A mechanic needs a risky hook or a large native effort.
- The button budget forces dropping or merging actions, or a button replaces a physical action.
- Anything that leaves the machine: pushing, publishing, posting, installing loaders into the user's game folder for the
  first time, touching their saves.

Record each decision and its reason in `MODLOG.md`. The dashboard shows open decisions on the Design card.

## Scope and limits

- Only games the user owns. Single-player and private co-op. No kernel anti-cheat, no online or competitive play, no
  DRM or ownership-check bypass. Stop and tell the user if the game is protected that way.
- Reverse engineer the user's own copy for interoperability. Ship code, configs, your own assets and patches. Never
  ship game files or decompiled source.
- Back up saves before touching them. Test saves are separate from the user's. Kill processes by PID. Ask before
  taking over input on the user's desktop.
- Debug channels (teleport, spawn, scripted hands) are compiled out or off unless a dev flag is set.
- Be honest about effort and status: mark unverified work as unverified, with the build it was last seen on.
