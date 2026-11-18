# Closing the loop: letting the agent test the game itself

The slow part of agent-built mods is not writing code; it's finding out whether the code worked in the running game. The agent-built mods that worked (e.g. a large C++ mod for GTA V story mode built with Universal Modder) ran the agent on the machine with the game, hot-reloaded the logic in about 5 seconds instead of minutes, and took a screenshot after each of 47 reloads. Set up the same loop for VR, using `um win launch / shot / drive / record / kill` for the game-handling parts (see `agent-toolkit.md`), plus the parts VR adds below.

## Contents
0. Platform preflight and the first-boot gate
1. Run where the game runs
2. Hot reload
3. Make the mod observable
4. Virtual hands: test VR mechanics without a headset
5. Scripted test scenarios
6. Seeing the game
6b. Performance
7. What still needs a human
8. Game patch routine

## 0. Platform preflight and the first-boot gate

Do this before any feature work; it's the step that, when skipped, wastes the most time (`lessons.md` A1, C1, C2). Irisify automates it: `irisify doctor platform --machine <m>` and `irisify gate check first-boot`.

**Preflight, on the machine that will run the game** (check each, don't wait for errors):
- The game runs from a store install the user owns, on the exact build you decompiled; record build id.
- Runtime: which VR runtime and how the headset connects (SteamVR wired, Steam Link/Frame adapter, WiVRn/ALVR, standalone). On Linux hosts: native Steam over Flatpak when wireless adapters or SteamVR helpers are involved; kernel version against the headset vendor's minimum; hardware video encode available to the runtime (e.g. Fedora needs RPM Fusion `mesa-*-freeworld` for H.265); SteamVR compositor capability (`setcap CAP_SYS_NICE=eip …/vrcompositor-launcher`).
- Steam Input setting for the game (Properties → Controller). On Steam Frame / Steam Link VR, Steam Input forced on can keep `IsInputAvailable()` false for the whole session; turn it off for VR titles that use SteamVR Input.
- Mod loader and its launch options (e.g. Proton `WINEDLLOVERRIDES="winhttp=n,b" %command%`), compatibility tool, and that the agent can deploy (SSH/adb) and read the loader's log.

**First-boot gate** (all must be true, logged, on the user's real hardware):
1. The game starts in VR (scene app registered, compositor shows it).
2. The mod logs `N patch classes applied, 0 failed` (patch class by class; see `lessons.md` B1).
3. Input diagnostic: action set active, `IsInputAvailable=true`, and pressing a face button and the trigger produce action DOWN events in the log. Poses working is not proof of input: poses can flow while every button is withheld.
4. The build id in the log matches the build the agent deployed.
Only then fan out. Keep the diagnostic in the mod (behind a toggle) for every later test.

## 1. Run where the game runs

The agent needs a shell and file access on the gaming PC: the agent running on that PC, or a link to it (SSH or adb, see `machines.md`; `irisify machine add` and `irisify machine setup` set it up), optionally with desktop control for screenshots and clicks. Without that, every test round-trips through the user and iteration collapses. Ask the user to set this up before starting serious work.

## 2. Hot reload

- UEVR: Lua scripts reload in place; keep game logic in Lua; C++ plugin only for hot paths.
- UE4SS: hot reload hotkey for Lua mods (configured in its settings ini).
- Custom engines: host DLL + reloadable logic DLL (see `re-pipeline.md` section 4). Reload on file change or on a command file the agent writes.
- Target: change → result in under ~10 seconds, no game restart.

## 3. Make the mod observable

Screenshots are slow and ambiguous; structured logs are fast and exact. Build these in from the first line of code:
- **State log**: append JSON lines to `<modfolder>/logs/state.jsonl` on every state change and at a low rate per tick: HMD and hand poses (world space), pawn position/velocity, movement mode, what each hand overlaps/grabs, equipped item, current mechanic state machine state, active vehicle.
- **Event log**: one line per mechanic event (grab_start, climb_start, ladder_exit, hatch_open_called, game_function_X_called + return value).
- **Error log**: hook failures, missing signatures, nil objects, with the feature disabled rather than crashing.
- **Command channel**: the mod polls `<modfolder>/cmd.json` (or a named pipe/local socket) for commands from the agent: teleport to a named test location, spawn an item, set time of day, start a scenario, reload scripts, dump an object's properties.

The agent then tests by: write command → wait → read logs → assert.

## 4. Virtual hands: test VR mechanics without a headset

Design rule: every read of HMD/controller pose and buttons goes through one input-provider interface in the mod. Implement two providers:
- **Live**: real OpenXR/UEVR data.
- **Scripted**: poses and buttons played back from a timeline the agent writes (e.g. "right hand at rung 1, grip; move up 0.4 m over 0.5 s; left hand to rung 2, grip; release right…"), or recorded from a real session and replayed.

With the scripted provider, climbing, grabbing, holstering, hatch wheels, swimming strokes and melee can be exercised automatically and deterministically. For runs without a headset, the VR runtime itself may still be needed: a simulator or null-HMD driver (SteamVR has a null driver option; Meta publishes an OpenXR simulator) can stand in; verify the current setup steps for whichever the user has.

Record real sessions from the user (pose + button timeline + event log) whenever something feels wrong; replay them as regression tests.

## 5. Scripted test scenarios

**Deterministic setup.** Random spawns, weather, time of day and physics make scenarios flaky. Give each scenario a dedicated test save in a known state (made once, stored with the mod's test assets, restored with `um backup` or a copy before each run), and use the command channel to pin anything still random (time of day, spawns) where the game allows it. Re-run a failing scenario before trusting a failure; a scenario that fails intermittently is a bug to fix, not noise to ignore.

Each row of the mechanic coverage map gets at least one scenario file:
```
scenario: ladder_up_and_off_into_ship
setup: teleport ship_dock_ladder_bottom; equip none
script: climb_hand_over_hand(rungs=8) ; mantle_top
expect:
  - event climb_start within 1s
  - movement_mode == Flying during climb
  - pawn.z increases >= 3.0 m
  - event ladder_exit
  - movement_mode == Walking
  - pawn inside volume ship_interior
  - no error log lines
```
Run the full suite after every change that touches shared code, and after every game patch. Keep failures and their fixes in `notes/gotchas.md`.

## 6. Seeing the game

- Use the desktop mirror/spectator view (UEVR has a spectator view) so screenshots of the monitor show the game.
- Capture screenshots per scenario step for visual checks the logs can't express (hand model clipping, UI placement, stereo artifacts); look at them, don't just collect them.
- For stereo artifacts, capture one frame per eye (RenderDoc) when something looks wrong.

## 6b. Performance

- Log frame time per frame and per feature (time spent in each library module's tick) to telemetry.
- Keep a `perf_baseline` scenario (same route, same actions) and run it after every change that adds per-frame work; flag regressions against the headset's frame budget (e.g. 11.1 ms at 90 Hz).
- Expensive traces/overlaps: run at a lower rate or only when a hand is near something.

## 7. What still needs a human

Logs and screenshots verify that mechanics function. They don't verify comfort, motion sickness, hand presence, scale, or whether an interaction feels good. Plan short, focused human playtests per milestone with a checklist (what to try, what to report), and turn every complaint into a recorded replay + a scenario so it never regresses.

## 8. Game patch routine

Games in active development (early access especially) patch often, and every patch can break hooks.
1. **Detect**: on startup the mod hashes or reads the version of the game executable and compares it with the build in the README; on mismatch it logs loudly and shows a one-line notice in VR.
2. **Self-check**: resolve every signature and reflection lookup, disable each feature whose hooks fail, and write a report (`logs/patch_check.json`).
3. **Re-test**: run the full scenario suite and the perf baseline on the new build.
4. **Repair**: re-find broken hooks with the recorded method in `notes/signatures.md` / `notes/hooks.md`; diff the new build's localization strings, data tables and bindings against the previous build (new or removed strings and rows show changed mechanics), read the patch notes, and update the coverage map.
5. **Report** to the user: what broke, what was fixed, what's disabled, and update the README's tested build.
If the user wants stability, they can pin the game version where the store allows it (e.g. Steam's update-on-launch setting or beta branches); mention this, don't change it for them.

## 9. Suites and the Irisify rig

Irisify generalizes the Subnautica rig (`tools/rig/`, `adapters/unity-bepinex/`):
- **Simulated headset.** Linux: Monado (`SIMULATED_ENABLE=1`) + OpenComposite, pointed at by env vars for the test
  process only (`tools/rig/monado.sh`). Windows: SteamVR's null driver (`tools/rig/null-driver.sh enable|disable`,
  with a backup and undo). On Linux SteamVR's compositor needs a DRM-lease display, so the null driver fails there.
- **Command channel.** JSON files dropped in `<game>/BepInEx/irisify/cmd/`, results appended to
  `<game>/BepInEx/irisify/results.jsonl` (schema: `docs/results-schema.md`), screenshots in `.../shots/`.
- **Scripted hands** sit inside the input layer (the action-source getters and the pose update), so features see
  scripted input exactly as real controllers. Button changes are queued and applied at the start of the next frame,
  so every reader sees one "down" frame.
- **Scenarios** declare `owner`, `covers`, `cannot_cover`, `shots` (moment + question) and their checks. Each
  restores the settings it changed, records a start state, and gets the comfort checks automatically.
- **Suites** are named lists in `suites/*.json`: `smoke` (boot, input, one mechanic, ~3 min), `full`, `comfort`,
  feature suites, `flaky-hunt` (a scenario interleaved between all others). Run one with
  `irisify suite run <name> --machine <rig>`. The runner restarts the game after a crash, records CRASH with the last
  log lines and goes on.
- **Runner-side checks** that need restarts: `boot` (cold start to the menu, no exceptions, all patches applied) and
  `settings_roundtrip` / `settings_migration`.

## 10. Run what a change touches, and keep the game up

- **File → scenario map.** Each scenario lists the files it `touches`. Shared core files fan out to their dependents
  through `core` in `.irisify/project.json`:
  ```json
  "core": [{"files": ["VR/BodyFrame.cs", "VR/HolsterLayout.cs"], "tags": ["body", "holsters"]},
           {"files": ["Input/InputClaims.cs", "Input/GripRouting.cs"], "tags": ["input", "grab", "locomotion"]},
           {"files": ["Settings*.cs", "SettingsMigration.cs"], "tags": ["settings"]}]
  ```
  `irisify suite plan auto` shows each scenario with why it's in ("touches X", "shared X", "FAIL on <build>").
- **Per merge: `auto`. Before the headset: `full`.** `irisify deploy` to a headset refuses without a green full run.
- **One game process.** The rig client loads the test save only when it isn't loaded already, and scenarios teleport
  within it. Restarts are for `boot`, settings round-trips and crashes.
- **Time per scenario.** The rig client records seconds per scenario and prints the slowest first. Suite estimates
  use measured times, so a slow scenario shows up in the plan before you run it. Give slow scenarios a
  `cap_seconds`: past it the result is CRASH and the game restarts, instead of one hang eating the run.
- **Quick and full sets.** A scenario that sweeps many cases (every shoulder reach, every build piece) declares
  `sets` and runs its quick set by default. The full set runs when the change hit a `core` rule with
  `"full_sets": true` (body and input files), and always in `nightly`. In Subnautica the shoulder sweep went from
  ~7.5 min to ~2 min this way.
- **Test saves, never the player's.** List them in `rig.saves` in `.irisify/project.json`; the first is the default
  (a creative save). A scenario that needs ingredients, hunger or a real stall says `"save": "survival"`. The rig
  client loads a different save only when the next scenario needs it.
- **One proof shot in targeted runs.** `smoke`, `changed`, `auto`, `regression` and `flaky-hunt` ask the adapter for
  one proof screenshot per scenario (`shots: "proof"`); `full`, `nightly` and `pre-headset` keep every moment, so
  the human's review has them all.
- **What it costs.** A targeted batch of 6–9 scenarios ran in 7–10 minutes on the Subnautica rig.
