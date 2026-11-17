# Lessons: root-cause analysis of the Subnautica / Steam Frame project

Source project: SubmersedVR fork (`deep-vr` + `claude/vr-*` branches), Subnautica build 20241558, played on a Valve
Steam Frame, both standalone and streamed from a Fedora laptop (Proton). About two days, one coordinating session,
seven feature sessions, then an input-focus session, a swim-controls session and a headset-free test rig.

Every entry has the same four parts:

- **What happened**: the symptom the user saw, or the bug the rig found.
- **Root cause**: the technical reason.
- **Why the agent missed it**: the reasoning gap, not just the bug. This part matters most, because the same gap
  causes different bugs in the next game.
- **What catches it up front**: the instruction, check or tool in Irisify that would have caught it before the user
  did. Each one points to the file that does it.

The entries are grouped by the gap behind them, not by date. The last section turns them into rules.

---

## A. Process: what was built, and in what order

### A1. Breadth built before one verified boot
- **What happened:** seven areas (vehicles, movement, gathering, machines, body, building, endgame) were built in
  parallel and merged into `deep-vr` as version 0.3.0. The MODLOG said "Nothing has run in game yet." On the first
  real launch, no patch applied and no button reached the game.
- **Root cause:** none of the work could run on the Mac where it was written, and the plan never required a launch
  before fan-out. Each session confirmed "builds with no warnings" and stopped there.
- **Why the agent missed it:** "it compiles" felt like progress, and the skill's gate sat in the phase list, which
  is advisory. Nothing *blocked* fan-out. The agent also treated "the user runs it later" as a valid plan, without
  asking the user to run it right away. Each session worked on its own branch, so none of them owned the
  question "does any of this load?"
- **What catches it up front:** the **first-boot gate** is a hard gate in the workflow state machine
  (`tools/irisify/workflow.py`). `irisify gate check first-boot` needs evidence: a boot log with the
  "N patch classes applied, 0 failed" line, an input-diagnostic DOWN event from the real controller, and the build
  id. `irisify integrate`, `irisify deploy` and the skill's fan-out step refuse to run until that gate is green.
  The dashboard shows the gate in red with "ask the user to launch it now" as the next action.

### A2. Parallel sessions overwrote each other's deploys
- **What happened:** several sessions each built their own branch and copied it to the same
  `BepInEx/plugins/SubmersedVR.dll` on the Frame. The user tested a build that was missing most features. Some
  sessions noted "deployed; old DLL kept as `.before-readability`", others "not deployed, Frame unreachable".
- **Root cause:** there was one deploy target and many writers, with no lock, no integration step and no build id
  in the game log.
- **Why the agent missed it:** each session reasoned only about its own branch. "Deploy my change so the user can
  test it" is locally helpful and globally destructive. Nobody could tell what was running, because the DLL didn't
  say.
- **What catches it up front:** `irisify deploy` only deploys from the integration branch with a clean tree. It
  takes a lock file on the device (`.irisify-deploy.lock` next to the plugin) and stamps the build id
  (`git describe` + branch + time) into a `build.json` that the adapter logs at boot. Every deploy is written to
  `.irisify/deploys.jsonl`, and the dashboard's **Devices** panel shows which build each device runs. Feature
  sessions get `verify-branch` (deploys only to the *rig*, inside a lock, and restores the integration build after).

### A3. No design process: mechanics were designed one at a time
- **What happened:** each area session designed its own mechanics well, but nobody designed the *scheme*. Grips got
  five owners, shortcuts stayed next to their physical versions, prompts showed Xbox glyphs, features were off by
  default, and on-body spots collided (PDA pocket 11 cm from a holster).
- **Root cause:** the plan was split by game area (vehicles, body...), not by cross-cutting concern (input, body
  frame, UI placement, comfort, discoverability). Cross-cutting concerns were left to the integrator. The integrator
  merged code and did not redesign anything.
- **Why the agent missed it:** splitting by area is the obvious way to parallelise. The "integrator" role was
  described as merging, not as owning design. The original skill also had no design artifacts that had to exist
  before code (control-scheme table, body map, UI placement map).
- **What catches it up front:** `skill/references/design-process.md`. Seven design documents (intake, physical
  sketch, interaction inventory, control scheme, body map, UI placement, comfort plan) must exist and be reviewed
  before breadth. The **design gate** checks they exist and that the control-scheme table has no input with two
  owners in one context (`irisify controllers lint`).

### A4. Features off by default made the mod invisible
- **What happened:** "every feature off until playtested" (MODLOG 11-16). The user played what was in effect
  the old mod, didn't know holsters, punching or arm swimming existed, and reported them as missing.
- **Root cause:** conservative defaults, chosen to protect the user, plus nothing in the game that pointed at the
  features.
- **Why the agent missed it:** "off by default" is the safe engineering habit for unverified code. The agent didn't
  model what the player would *see*: a vanilla game. It assumed the user would read the options page or the notes.
- **What catches it up front:** design rule D-1 (`skill/references/discoverability.md`): ship one coherent
  **on-by-default physical preset**, and allow off-by-default only for features that are risky *and* optional.
  The discoverability audit asks of every feature "how does a player who never opens the menu find this?" and needs
  an answer (a hint, a visible model, a label, a reticle line). The rig scenario `discoverability` checks that each
  preset feature reports itself active in a fresh profile.

### A5. Saved settings overrode new defaults
- **What happened:** after arm swimming was switched to default-on, it still didn't work for the user. Their
  settings file had saved `ArmSwimming=false`, and saved values win over new defaults. A "3 exceptions → turn
  feature off" safety switch also wrote `false` into the saved settings.
- **Root cause:** settings had no version and no migrations. Runtime safety state was stored in the persisted
  settings object.
- **Why the agent missed it:** changing a default *looks* like it changes behaviour, and it only does for new users.
  The agent tested in its head against a fresh install, never against the user's existing file.
- **What catches it up front:** the adapter's settings template has a `SettingsVersion` and ordered migrations from
  the start (`adapters/unity-bepinex/Settings/SettingsMigration.cs`). Runtime kill switches never persist. Rig
  scenario `settings_migration` loads an old settings file and checks that every migrated value ends up on.
  Checklist line: "Did you change a default? Add a migration."

### A6. Old shortcuts left next to their physical versions
- **What happened:** the radial quick-slot wheel, D-pad cycling, the PDA button, the deconstruct button and builder
  rotate all stayed bound while their physical versions existed. There were two ways to do everything, and the
  prompts kept teaching the button.
- **Root cause:** physical features were added *on top of* the input scheme and never replaced it.
- **Why the agent missed it:** removing a working input feels risky, and adding feels safe. Nobody listed "which
  button does this physical mechanic make redundant?"
- **What catches it up front:** every interaction in the inventory (`design-process.md` step 3) has a
  `replaces:` field. `irisify controllers lint` warns when a context binds an action whose physical replacement is
  in the preset. SubmersedVR's eventual fix (`PhysicalShortcuts.cs`, one obvious way per action) is the pattern in
  `skill/references/control-scheme.md`.

### A7. Test-rig blind spots that only screenshots showed
- **What happened:** the rig's numeric checks passed while the screenshots showed real problems: the wrist computer
  was nearly invisible (two fades multiplied), a floating "O2 / depth / °C" gauge sat in the middle of the view,
  "Power: 100%" sat at the lens edge, subtitles were cut off at the top, and the bottom third of a look-down was
  the inside of the chest. Other `drawn_N` shots showed no hand only because of the capture angle.
- **Root cause:** checks measured what the author expected (counts, sizes, distances), not what was on screen.
- **Why the agent missed it:** a PASS reads as done. The agent didn't look at the images, or looked without a
  question to answer ("is anything floating that shouldn't be? is the thing I built visible?").
- **What catches it up front:** **screenshot review is a gate** (`skill/references/screenshot-review.md`). Every
  scenario names its key moments and a *caption question* ("the wrist computer is readable"). The dashboard's
  gallery shows the screenshots next to the same moment in the previous build. A run isn't "ready for headset"
  until each new or changed screenshot has been marked reviewed (by the agent with a written answer, and by the
  human for anything about feel or readability).

### A8. The test rig's own blind spots: SteamVR layer, feel, optics
- **What happened:** the rig runs Monado + OpenComposite, because SteamVR's null driver can't run its compositor on
  Linux (`VRInitError_Compositor_GnomeNoDRMLeasing` on Wayland, `CannotDRMLeaseDisplay` on X11). So SteamVR
  bindings, Steam Input and focus are never tested, and the input-focus bug class can't be seen there.
- **Root cause:** a real platform limit. The scripted input also replaces everything below the action layer.
- **Why the agent missed it:** it didn't; the rig notes say so. The gap was that nothing *routed* those checks to
  the human.
- **What catches it up front:** each scenario declares `covers:` and `cannot_cover:` (`tools/irisify/scenarios.py`).
  The dashboard's "Ready for headset" checklist is built from the union of `cannot_cover` items: bindings and focus,
  feel, optics and text, haptics, comfort over time. `tools/rig/null-driver.sh` documents where the null driver works
  (Windows; Linux only with a DRM-lease display) and switches to the Monado path on Linux.

### A9. Results not tied to a build
- **What happened:** `results.jsonl` lines on the rig have no build id. When a fix and a re-run crossed, it was
  unclear which build a PASS or FAIL belonged to. Sessions wrote "not deployed by me" in their notes to work around
  it.
- **Root cause:** the result format grew from a debugging tool.
- **What catches it up front:** Irisify's result schema (`docs/results-schema.md`) requires `build` on every line
  and a `run` header line. The importer gives legacy lines a build from the deploy log by time, and marks them
  `inferred`.

---

## B. Loading, patching and engine traps

### B1. `PatchAll` aborted on the first bad target
- **What happened:** one bad patch target (`ExosuitPropulsionArm` implements `IExosuitArm.Update` explicitly, so its
  metadata name is `IExosuitArm.Update`) made `harmony.PatchAll()` throw, and *no* patch applied.
- **Root cause:** `PatchAll` is all-or-nothing in practice. Explicit interface implementations have
  qualified names.
- **Why the agent missed it:** without a running game, the decompiler view (`void IExosuitArm.Update()`) reads like a
  method named `Update`. The agent also didn't consider failure isolation, because it pictured a correct build.
- **What catches it up front:** the adapter's `SafePatcher` (`adapters/unity-bepinex/Core/SafePatcher.cs`) patches
  class by class, logs and skips failures, filters null `TargetMethods`, and logs `[Irisify] patches: N applied, M
  failed: [...]`. The first-boot gate needs `M == 0`. Offline check: `tools/irisify/patchcheck.py` lists patch
  targets with `IInterface.` names found in the decompiled source.

### B2. A transpiler lost a branch label
- **What happened:** `PrawnArms_GrappleFallback` failed with "IL Compile Error": the transpiler replaced an
  instruction and the jump label on it went with it.
- **Root cause:** in Harmony, labels belong to `CodeInstruction` objects. Replacing the object drops them.
- **Why the agent missed it:** IL labels aren't visible in C# decompiler output, and it couldn't run the patch.
- **What catches it up front:** a rule in `skill/references/engine-playbooks.md`: change `opcode`/`operand` in place,
  or use `MoveLabelsFrom`/`MoveBlocksFrom`. The `SafePatcher` boot line catches the failure in the first-boot gate.

### B3. A settings `const` hung the main menu
- **What happened:** a `const` added to `Settings` for the migration version made `Settings.Serialize` throw
  `FieldAccessException` inside the game's settings load, and the start screen never reached the main menu. The
  rig's `boot` scenario found it.
- **Root cause:** the serializer reflected over *every* public static field, including constants.
- **Why the agent missed it:** it added a harmless-looking field to a class it didn't own, without reading how that
  class is consumed. Reflection-based serialization is an invisible contract.
- **What catches it up front:** a rule: non-setting statics go in their own class, and any reflection serializer
  skips `IsLiteral`/`IsInitOnly`. The `boot` scenario (cold start to main menu, no exceptions) runs after **every**
  integration. A boot-time hang is the most expensive kind of bug, because the user just sees a frozen screen.

### B4. The UI's movement lock froze the player with the builder tablet out
- **What happened:** "with the tablet out my body doesn't move". Opening the build menu selected it as a uGUI input
  group. With a controller as the primary device, `GamepadInputModule.OnGroupChanged` set
  `FPSInputModule.lockMovement = true`.
- **Root cause:** the game's full-screen-menu assumption (a menu means no movement) carried into a handheld menu.
- **Why the agent missed it:** moving a menu onto the hand changes its *meaning* (handheld, not modal), but the game
  still treats it as modal. The agent changed where the menu is drawn, not the menu's role.
- **What catches it up front:** design-process step 6 (UI placement) asks of every relocated flat UI: "Is it
  still modal? What does the game lock while it's open?" The `InputLockWatch` diagnostic pattern
  (`adapters/unity-bepinex/Diagnostics/InputLockWatch.cs`) logs every lock change, and the rig scenario template
  `move_with_ui_open` moves with each handheld UI open.

### B5. The intermittent slow swim with the builder (still open)
- **What happened:** swimming with the builder in hand was sometimes much slower. It was never reproduced on demand.
  The rig grew `builder_move` (run first, between other scenarios and last), `builder_bisect` (per-frame
  `lockMovement` and move-direction samples, setter stack traces per builder setting) and a `GameInput.ClearInput`
  tracer. `builder_move` passed five times in the latest full suite.
- **Root cause:** unknown. Candidates: state leaking from an earlier scenario or interaction (claims, input group,
  carry), or a frame-rate-dependent path.
- **Why the agent missed it:** intermittent bugs need *order* and *state* variation, and early scenarios always
  started from a clean state.
- **What catches it up front:** the scenario runner records a **start-state snapshot** (claims, held item, menus,
  locks, fps) for every scenario. `--interleave name` repeats a scenario between all others, and `--shuffle`
  randomises order with a seed. The dashboard flags a scenario whose metrics vary by more than 25% across runs of
  one build as **flaky**, and routes it to its owner with all the start states.

---

## C. Platform and input focus

### C1. Steam Input forced on blocked SteamVR input focus
- **What happened:** controllers tracked, but no button reached the game. `IVRSystem.IsInputAvailable()` was false
  and `ShouldApplicationPause()` true for the whole session, and every action had `bActive=false`. Bindings loaded
  correctly. It looked like a SteamVR/Frame bug and wasted most of a session.
- **Root cause:** Steam Input was **forced on for the game** (per-game `eEnableThirdPartyControllerConfiguration =
  1`). Steam took the Frame controllers as a virtual Xbox pad and wrapped the game in a desktop-game panel
  (`valve.steam.desktopgame.264710`) that held input focus. The hard-grip laser/gamepad switch was Steam Input's own
  mode switch. The fix: Properties → Controller → Disable Steam Input (value 2), on whichever machine runs the game.
- **Why the agent missed it:** it debugged from the mod outward (bindings, action sets, SteamVR versions) instead of
  asking first "who has input focus?" The decisive evidence ("Opted-in Controller Mask for AppId 264710",
  "Controller 0 uses xinput") was in Steam's console log, which nobody read. Poses working was taken to mean input
  worked.
- **What catches it up front:** `irisify doctor input-focus` (`tools/irisify/focus.py`) reads Steam's console log
  and `vrserver.txt` for those lines, checks the per-game Steam Input setting, and prints the fix. The adapter's
  `InputFocusDiag` logs `IsInputAvailable`, `ShouldApplicationPause`, `bActive` and DOWN events from boot. Platform
  preflight step 5: "Steam Input for this game: off" on every machine that runs the game. The rule is **focus
  first, bindings second**.

### C2. Flatpak vs native Steam, kernel, codecs, setcap for the Steam Frame adapter
- **What happened:** these were found one error at a time on the laptop. Flatpak Steam never set up the Frame's
  wireless adapter (native Steam from RPM Fusion did). The adapter needs kernel 7.2+. Fedora's `mesa-vulkan-drivers`
  has no H.265 encode, which SteamVR streaming needs (RPM Fusion's `mesa-vulkan-drivers-freeworld` has it). SteamVR's
  compositor wants `cap_sys_nice` (`setcap` on `vrcompositor-launcher`). The dongle joins the Frame's own network
  through a NetworkManager connection Steam creates, so the dongle must stay managed.
- **Root cause:** a streaming VR stack on Linux has many independent preconditions, and none is checked up front.
- **Why the agent missed it:** it treated "set up the laptop" as a single step and reacted to each error as it came
  up, instead of listing every precondition for this headset + host + runtime first.
- **What catches it up front:** `irisify doctor platform` (`tools/irisify/preflight.py`) runs over SSH on the host and
  checks Steam packaging (Flatpak or native), kernel version against the headset profile's minimum, H.265/HEVC
  encode in `vainfo`/Vulkan, `getcap` on the compositor launcher, NetworkManager managing the adapter, Proton
  version, and per-game Steam Input. Each check prints the exact fix and says whether it needs sudo (the human runs
  it) or not (the agent runs it). The Steam Frame preconditions live in `controllers/profiles/frame_controller.json`
  under `host_requirements`, so the next headset brings its own list.

### C3. Shell and tooling gotchas
- `pgrep -f` over `ssh 'bash -c …'` matches the remote shell's own command line. Match exact names or a pattern
  anchored on the Windows path (`^[A-Z]:.*Game\.exe`), and kill by PID.
- Inline Python with nested quotes through `ssh` breaks. Copy a script and run it.
- macOS `tar` adds `._*` files: use `COPYFILE_DISABLE=1`.
- Steam rewrites `~/.config/openvr/openvrpaths.vrpath` on start. Point *one process* at a test runtime with env vars
  (`VR_OVERRIDE`, `XR_RUNTIME_JSON`) and never edit the user's global runtime.
- Proton screenshot paths come back as `Z:\home\...`. Normalise them before showing them.
- **What catches it up front:** the rig scripts in `tools/rig/` already do all of this. `docs/gotchas.md` keeps the
  list growing.

---

## D. Control scheme and controller knowledge

### D1. Unbound actions (UIAssign) and gamepad-only UI flows
- **What happened:** the user couldn't assign quick slots in the PDA. `UIAssign` was unbound in every layout
  (upstream too), and the game's slot picker needed gamepad navigation.
- **Root cause:** the binding files were written by copying an existing layout, not by walking the action manifest.
- **Why the agent missed it:** it checked that the buttons it *used* were bound, not that every action the game
  *needs* was bound. It also traced the button that starts a flow, never the flow (open → select → confirm).
- **What catches it up front:** `irisify controllers lint` fails when a manifest action is neither bound in a
  context nor in the `dropped:` list with a reason. Design step 3 traces every UI flow end to end, and the rig
  template `ui_flow` drives one with scripted input.

### D2. Grips overloaded
- **What happened:** the grips meant swim up/down + sprint + builder rotate + holster draw + grab + pouch + PDA
  draw + pull-deconstruct. "The grip buttons are used for going up and down right now, which makes the whole
  control scheme extremely infuriating." Every grab also moved you.
- **Root cause:** the upstream Touch layout used the grips for locomotion, and every new physical feature also
  wanted the grip. `InputClaims` resolved *conflicts* but not *meaning*.
- **Why the agent missed it:** each feature, seen alone, picked the most natural input, which for grabbing is the
  grip. Nobody looked at the column for one input across all features.
- **What catches it up front:** a control-scheme rule: **grips are for grabbing, nothing else**. The context table
  in the controllers module is checked per input: `lint` lists every owner of each physical input per context, and
  fails on a locomotion action bound to a grip when a grab feature exists. A **claim-priority order** is set in
  design (body spot > grab near hand > pointing gesture > game action), not found during merges.

### D3. Button prompts didn't match the controller
- **What happened:** "sometimes the buttons shown in UI just don't line up with what they really are." The game
  drew Xbox glyphs in Xbox positions, and the readability session's label table was hand-written and could drift
  from the binding file.
- **Root cause:** prompts and bindings were two sources of truth.
- **Why the agent missed it:** prompts are UI and bindings are input, so they lived in different heads.
- **What catches it up front:** `irisify controllers prompts` generates the prompt table **from the same manifest
  and context table** that generates the binding JSON (`controllers/generate.py`). The adapter reads that generated
  table, and a test fails if a prompt names an input the binding doesn't use. SubmersedVR's eventual
  `ButtonPrompts.cs` (prompts read from the binding file) is the same idea at runtime.

### D4. Controller type and layout guessed instead of read
- **What happened:** the Frame binding was written from Valve's docs page and two community PRs. Confidence was
  "high", but the notes still carried a "if the type differs (e.g. `steam_frame_controller`)…" fallback. The Frame
  is not a Touch layout: the left hand has a D-pad, the right has A/B/X/Y, both have a bumper, the grip is an
  analog trigger, and the thumbrest is SteamVR-internal touch only. SteamVR's fallback to a Touch binding puts B/Y
  on odd buttons.
- **Root cause:** the runtime's own input profile (`drivers/frame_controller/resources/input/frame_controller_profile.json`)
  was never read, although it lists every component, its side, its type and the mirror mapping.
- **What catches it up front:** `irisify controllers detect` reads the connected controller type (OpenVR
  `Prop_ControllerType_String` via the adapter, or `vrserver.txt`), finds the driver's input profile and writes the
  real component list into the project. Bindings are generated only from real components. The Frame profile is
  checked in (`controllers/profiles/frame_controller.json`), taken from the runtime's file on 2026-11-17.

### D5. Analog grips registered while just holding the controller
- **What happened:** arm strokes were skipped while "the grip is held". On the Frame the grip is an analog trigger
  (`type: trigger`, `value: true`), and a relaxed hold can cross a low click threshold.
- **Root cause:** the code treated "grip" as a digital button, and the binding's click threshold was the default.
- **What catches it up front:** the controller profile marks analog grips, and the binding generator gives grab
  actions explicit `click_activate_threshold`/`click_deactivate_threshold` values. The skill says: never gate
  a gesture on "grip not pressed" without hysteresis.

### D6. The double grip action at lockers
- **What happened:** on the rig (`containers_lifepod`), one squeeze both *stashed* the held scanner into the locker
  and, through reach-to-open's quick-tap rule, *opened* the locker.
- **Root cause:** two features, each correct alone, both acted on the same grip release, with no claim between them.
  "Stash" and "open" were in different sessions (body/readability vs machines).
- **Why the agent missed it:** the claim system covered presses, and this was a press-and-release pair split across
  features. Nobody listed what one grip *means* in that spot with an item in hand.
- **What catches it up front:** the interaction inventory has a `when_holding:` column. Design rule: with an item in
  the hand, the grip means "do something with this item" (put it away, put it in, throw), and every other grip
  feature for that hand backs off. The lint check flags two interactions sharing an input, context and `when_holding`
  state. SubmersedVR's fix was exactly that (`c594079`).

### D7. Y auto-assign surprised the player; physical carry was what they wanted
- **What happened:** a fallback put "assign quick slot" on the right Y button, cycling through slots. The user
  didn't know where an item went, and wanted to put items on the body by hand. Later builds named the spot ("Knife →
  right hip") and added a grip-carry from the PDA onto the body. Then Y stopped assigning while the carry was on, and
  the user asked "the UI should say that".
- **Root cause:** a quick fix for an unbound action (D1) became a design decision without being designed. Then the
  physical version replaced it silently.
- **What catches it up front:** the decision-points list in the skill: "a button replaces a physical action" is a
  design decision with a written reason. Every removed or changed control gets a one-time hint and a tooltip line
  (discoverability audit).

### D8. Overwhelming button labels
- **What happened:** "overwhelmed by the thing that shows every button." The legend card listed every button,
  always.
- **Root cause:** discoverability was solved by showing everything, which is a flat-game habit (a full key map).
- **What catches it up front:** the overwhelm audit (`skill/references/comfort-and-overwhelm.md`) has a budget: at
  most 3 lines per context, only on a glance (controller turned toward the face), and nothing for buttons that do
  nothing right now. The rig's `ui_contexts` scenario counts visible text labels per context against budgets
  (swimming ≤ 12, building ≤ 20, cockpit ≤ 25).

---

## E. Locomotion and the body

### E1. Head-relative swimming
- **What happened:** "swim forward and backward without just looking at random places." Upstream steered by the
  head with full pitch: every glance steered, and diving meant staring at the floor.
- **Root cause:** the flat game's "forward = camera forward" carried over. In VR the head is an *eye*, not a
  steering wheel.
- **Why the agent missed it:** it ported the flat mapping without asking how a diver actually moves (along the body;
  depth is a separate act).
- **What catches it up front:** design-process step 2, the **physical sketch**: for every locomotion mode, write how
  a real body does it, what a player can sustain for an hour, and seated vs standing, *before* choosing inputs. Rule:
  direction comes from the body or a hand, never the head. The body-facing scheme (body yaw follows the head
  lazily, ±40° free look) is the default pattern in `vr-design.md`.

### E2. Strokes too effortful and too slow; no fine adjustment; no graded speed
- **What happened:** arm strokes were "way too much effort, way too slow", even after tuning. There was no way to
  make small adjustments without the stick, and almost any stick push swam flat out.
- **Root cause:** stroke push was too weak against the stick's 5 m/s and arrived through the drag balance, too late.
  The game's motor had one top speed (stick deflection only scaled acceleration). And a stroke detector can't do
  small precise moves at all.
- **Why the agent missed it:** it tuned numbers without measuring them. "Feels right" was guessed. It also took the
  user's request for "physical swimming" literally (arm strokes) instead of as the goal (effortless, precise
  control), so it missed the obvious second tool: grab the water and move 1:1.
- **What catches it up front:** a comfort metric with a target: **effort per metre** (hand path length per metre
  travelled) and **time to reach cruise**, measured by the rig's `swim_speed_curve`-style scenario against targets
  set in the design (one hand ≈ half stick speed, two hands ≈ full). Locomotion design must cover three tiers:
  travel, cruise and fine positioning, and each needs a mechanic. Stick speed must be graded (dead zone, curve,
  half push ≈ 40%).

### E3. Climbing through teleporting cinematics
- **What happened:** "I want to physically grab ladders... minimize teleportation as much as possible." Ladders and
  hatches ran the game's cinematic or teleport.
- **Root cause:** the game models ladders as an interact → teleport. The mod kept the interaction and only changed
  how it was triggered.
- **What catches it up front:** the **teleport audit**, which the skill now requires during design: grep every
  `SetPosition`/cinematic/camera-driving call, list each with its VR treatment (physical route, glide, blink, keep).
  SubmersedVR's `notes/movement.md` table is the template. The `comfort` monitor flags any unexplained view jump > 0.75 m.

### E4. The intro forced the head
- **What happened:** the wake-up cinematic rotated and moved the view.
- **Root cause:** cinematics drive the camera and the VR rig followed.
- **What catches it up front:** the teleport/cinematic audit above, plus a rule: the camera never moves or rotates
  without the player's input. Cinematics place the view once, then the player is free (`IntroComfort` pattern).

### E5. Head through hulls
- **What happened:** you could lean out through the lifepod hull and out of cockpits.
- **Root cause:** in room-scale or seated tracking the head is free, but the game's collision is on the body capsule.
- **What catches it up front:** a design checklist line: "Where can the head go that the body can't?" with a head-in-
  wall fade and a cockpit head limit as defaults. Rig scenarios `head_clip_fade` and `vehicle_head_limit` are
  templates.

### E6. No body, no height calibration, camera inside the chest
- **What happened:** "I don't have a body, only arms." "I'm way too tall and lowering myself is way too hard." Later
  a rig screenshot looking 55° down showed the chest as a blob filling the bottom third: the body hung from the
  headset position, so tipping the head carried the torso forward under the eyes.
- **Root cause:** body and height were treated as polish. When they were added, the body was attached to the head
  position instead of to a neck pivot, and the body followed the head's yaw instantly.
- **Why the agent missed it:** without a headset it never *saw* a look-down. The anatomy (eyes ~20 cm above and ~9 cm in
  front of the neck pivot) wasn't in its model of "put the body under the camera".
- **What catches it up front:** the **body map** is a design document: height calibration (stored per posture), a
  neck pivot, body yaw with a dead zone, and every on-body spot defined in one body frame that the mesh, holsters and
  UI all share. Rig screenshot moments: look down 35° and 55° standing and seated, each with the caption question
  "Is the body below the eyes, are the hands on the controllers, are holsters visible on the body?"

### E7. Holster icons covered holstered models; static floating HUD vs on-body UI
- **What happened:** slot markers floated over the body, and later the tools' own models sat on the body. The HUD
  was a static sheet you had to move your eyes to. The user's direction was "info goes on the body and gear, like
  Half-Life: Alyx".
- **Root cause:** the first readability pass solved "can't read the HUD" by making the HUD readable, not by
  removing it.
- **What catches it up front:** the **immersion review** (section F) and the UI placement document: every flat
  UI element has a diegetic home (wrist, tool, dash, door) or a written reason it stays flat.

### E8. Dropped items vanished; the PDA picked the wrong item
- **What happened:** "dropped items seem to disappear." Letting go of a carried copy away from a spot cancelled it,
  and the copy vanished, as if the item was gone. The PDA also closed under a carry when the player looked down.
  Separately, a grip with the laser on the Flashlight took the Seaglide: the carry read the game's
  `hoveredItem`, which can differ from what the laser points at on the grip frame.
- **Root cause:** (1) a let-go with no world result reads as a loss. In VR, letting go of something should do what
  letting go does. (2) Two features (PDA lower-to-close and carry) disagreed about the left hand's meaning. (3) The
  feature trusted the game's hover state (which follows gaze or a gamepad cursor) instead of the ray the player is
  actually using.
- **What catches it up front:** design rule: **every let-go has a visible outcome** (drops into the world, goes back
  to where it came from with a message, or goes into the container under the hand). Rule: pick targets from the
  input the player is using (the laser ray), never from the game's hover. Rig scenario templates: `carry_release_away`
  and `laser_vs_gaze_pick`.

### E9. Vehicle board and eject view snaps
- **What happened:** the rig found that boarding a Seamoth turned the view 180° in one frame, and leaving moved it
  3–15 m.
- **Root cause:** the game needs both cuts (seat facing, exit point). Gliding through 180° would be worse.
- **What catches it up front:** the comfort monitor's `snap` event (> 0.75 m beyond velocity, or > 10° in one frame).
  The design rule: a cut the game needs is **covered** (a short blink, 0.1 s black, 0.3 s fade), and a cut it doesn't
  need is **removed** (glide or physical route). The monitor counts a snap as covered only when the blink was logged
  in that frame.

### E10. The tiny builder tablet
- **What happened:** "the builder tablet is way too small and unreadable." The whole game menu was squeezed into
  26 cm, which made icons ~2 cm and text 0.6–0.8°.
- **Root cause:** size was set in metres of panel width, not in degrees of what's inside.
- **What catches it up front:** a readability rule: size UI by its smallest meaningful element in **visual
  angle** (text ≥ 2° font height, icons ≥ 4 cm at a 45 cm hold) for the target headset's real pixels per degree
  (Frame: 1728×1728 per eye, ~16 px/° average). The rig's `ui_contexts` FAILs text under 0.5° and warns under 0.8°.
  The controller/headset profile carries `px_per_degree`.

---

## F. Immersion is not realism (added on the user's direction, 2026-11-17)

- **What the user said:** minimise what makes it feel like a game, but realism doesn't automatically mean immersion.
  The example is Half-Life: Alyx showing the rounds in the magazine instead of a floating ammo counter.
- **What went wrong in SubmersedVR, seen through that lens:**
  - *Too gamey:* floating chest gauge "O2 / depth / °C" in the middle of the view; "Power: 100%" reticle subscript;
    holster slot markers over the body; a button legend card listing every button; quick-slot wheel; floating
    builder menu.
  - *Too realistic, not more immersive:* arm strokes as the *only* way to swim (tiring, imprecise); food needing a
    0.35 s dwell at the mouth is fine, but a tank you would have to reach over your shoulder to read would not be.
    Equipping fins at your feet isn't reachable, so "knees" was the honest stand-in. Gripping to hold a tool was
    rejected for a good reason: in the game tools are held without grip, and letting go mid-use must never drop
    them.
  - *Got it right:* tool charge on the tool, oxygen on a wrist dive computer you look at, locker contents on the
    door, real item models on the shelves, holstered tools visible on the body, vehicle stats on the dash.
- **Root cause:** the agent had "physical" and "diegetic" as goals, but no test for when physical is worse.
- **What catches it up front:** `skill/references/immersion.md`, the **immersion review**. For every mechanic and
  every piece of information: (1) Does it break presence (floating, head-locked, a menu where there's no menu in the
  world)? (2) Would doing it "for real" be tedious, tiring, imprecise or unreachable? Then pick the **lightest
  physical form that keeps the meaning**: rounds in the magazine, not a counter; a squeeze and pull, not a ten-step
  procedure. The review has a column for each and is part of the design gate.

---

## G. Discoverability: the player has to be able to find it

- **Hint scheduling:** PDA hints waited behind five general hints and never showed while the PDA was open (rig
  `pda_hint` FAIL). Hints need a context and a priority.
- **"The UI should say that":** when a control changes (Y stopped assigning), the game must say so where the player
  looks for it (tooltip line on the item, one-time hint on PDA open).
- **What catches it up front:** the discoverability audit table: feature → how it's found → where it's taught →
  how often → what the rig checks (`hint shown once, in context`).

---

## H. What the agent kept doing wrong, as rules

1. **Nothing is done until it has run.** Compile ≠ works. Gate fan-out on one verified boot on the real headset.
2. **Own the cross-cutting design before splitting the work.** Split by concern (input, body, UI, comfort) first,
   by game area second. The integrator owns design, not just merges.
3. **One source of truth per contract:** manifest → bindings + prompts, body frame → mesh + holsters + UI,
   build id → log + dashboard + deploy record.
4. **Model the player's actual state:** their saved settings, their Steam settings, their height, their headset's
   real controller profile, what they see when they look down.
5. **Look at the screenshots with a question.** A PASS without a reviewed image proves nothing about what's on screen.
6. **Debug from the outside in for input:** focus → runtime → bindings → mod.
7. **Every let-go, every changed control, every new feature has a visible result** the player can notice without
   reading notes.
8. **Physical when it's better, abstract when physical is tedious.** Immersion is the test, not realism.
9. **One writer per target.** Branches for workers, one integrator deploys, every build stamped.
10. **Ask the user early about the things only they know** (the hardware works, the platform is set up, feel), and
    decide the rest yourself with a written reason.
