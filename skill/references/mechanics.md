# Mechanic audit, VR redesign and implementation recipes

Engine-independent. "Find the function" means: UE4SS/EventViewerMod on Unreal, the object explorer on REFramework, decompiled C# on Unity, the RE pipeline on anything else.

## Contents
1. Audit: find every mechanic from both sides (1.1 trace from input to gameplay function)
2. Rethink each mechanic for VR
3. Coverage map
4. General implementation pattern
5. Recipes: vehicles, climbing, grabbing, holsters, melee/aiming, swimming, UI, hands, audio, co-op, cutscenes, body and comfort

## 1. Audit: find every mechanic from both sides

Cross-check two independent sources so nothing is missed. Prefer sources taken from the installed build: they always match the version you're modding.

- **Design side (what the player does), in priority order:**
  1. **Localization / string tables** (Unreal: localization `.locres` files and string tables, extract with FModel; Unity: text assets or localization packages; others: the language files). Every player-facing word is here: item and tool names, vehicle names, interaction prompts ("Climb", "Enter", "Open hatch", "Pick up"), HUD labels, tutorial text. Each string key leads to the code or data that displays it, so it's both a mechanic list and an entry point into the code.
  2. **Game data tables**: items, recipes, tools, vehicles, structures, creatures (Unreal DataTables/DataAssets, Unity ScriptableObjects, other engines' data files).
  3. **Input bindings and the controls screen**: every action the player can take.
  4. **In-game tutorials, help/encyclopedia entries (e.g. PDA/databank), achievements.**
  5. **Watching real play** (the user's recorded sessions, let's-plays): which actions happen most often, to set build order.
  6. **The wiki and patch notes, last**: use them to cross-check, to understand what a mechanic is for, and to judge priority. Wikis lag patches and can be wrong, especially in early access. Fan out subagents for large wikis (one per category).
- **Code side (what the game implements):** every input action; every interactable/usable/equippable/vehicle/climbable class; every component the player can touch; live call logs while performing each action.
- **When sources disagree:** the installed build (code, data, strings, in-game behavior) wins over the wiki; log the mismatch in `notes/mechanics.md`.
- **Reconcile:** every design-side mechanic maps to code (class/function), every code-side interactable class maps to a mechanic. Unmatched rows are hidden mechanics, cut content or dead code; list them.

### 1.1 Trace from input to gameplay function

Don't discover mechanics one object at a time; follow the input path and find the shared systems.
0. **Start from the prompt strings.** Find each interaction prompt in the localization tables ("Climb", "Enter", "Open"), then find what references its key: the widget or component that shows it leads straight to the interaction code for that mechanic.
1. **Enumerate input actions** and their bindings: Unreal Enhanced Input (InputAction assets and mapping contexts) or legacy action/axis mappings; Unity Input System action maps or `Input.GetButton` call sites; custom engines: the input read site found in recon.
2. **For each action, find the handler** it's bound to and follow calls until you reach the gameplay function (Unreal: EventViewerMod while pressing the button, plus header dumps; Unity: callers of the action's callback in the decompiled C#; native: cross-references from the handler in REA/Ghidra).
3. **Find the interaction system behind the interact button.** Most games route all "use" actions through one path: a trace or overlap from the camera/player → an object implementing an interactable interface or component (names like `Interactable`, `Usable`, `IInteract`, `UseComponent`) → a virtual `Interact`/`OnUse` function, often with a prompt text and a "can interact" check.
   - List **every class implementing that interface/component**: this is the complete list of interactables, found in one step.
   - Find the **targeting function** (what the player is "looking at"). Replacing its input (camera ray → hand position) converts every interactable to hand interaction at once; per-type recipes then refine the important ones (hatch wheels, ladders, seats).
   - Note the **"can interact" checks** (distance, angle to camera, line of sight) — they often need relaxing for hands.
4. Do the same for the other shared systems: equip/inventory (one equip function behind the hotbar, inventory UI and pickups), movement modes (one state machine for walk/swim/climb/vehicle), damage, UI/HUD binding (where widgets read their values).
5. Record the map `input action → handler → system → functions` in `notes/hooks.md`; the adapter (`architecture.md`) wraps these systems.

Deliver as `notes/mechanics.md` and summarize to the user before building.

## 2. Rethink each mechanic for VR

Don't bind the old button to a gesture. For each row ask how a native VR game would design it:

| Flat mechanic | VR redesign |
|---|---|
| Inventory grid | Body slots: hips/chest holsters, tools over the shoulder, backpack grabbed from behind the head opens the full grid as a world-space panel |
| Hotbar / quick slots | Belt or bandolier slots; reach and grab instead of pressing 1–5 |
| Tool / weapon switch | Holster one, draw another; radial wheel only as fallback |
| HUD bars (health, oxygen, ammo) | Diegetic: wrist display, gauge on the suit/tank, ammo counter on the weapon |
| PDA / map / logs | Handheld device pulled from a slot, readable at arm's length |
| Interact key on doors, hatches, valves | Grab the handle/wheel and move it; fallback: grab triggers the game's open animation |
| Ladder / climb prompt | Hand-over-hand climbing |
| Enter/exit vehicle | Grab the hatch/door, climb in, sit; controls are levers/sticks you hold |
| Eat / drink / heal | Bring the item to the mouth; injector to the arm |
| Reload button | Manual mag out/in or a simplified physical gesture (setting) |
| Crafting / fabricator menu | Menu stays, but on the machine's own screen with poke interaction; grab the output physically |
| Scanner / camera / flashlight | Point the held device; trigger to use |
| Throw | Physical throw with hand velocity |
| "Press E to pick up" | Reach and grab; highlight on hand proximity, not gaze |

When *not* to physicalize: actions repeated hundreds of times an hour (placing 50 identical building pieces, mass harvesting) get a fast assisted version or keep the button; anything that tires arms in long sessions gets a simplify option; don't slow a mechanic where timing is balanced (oxygen, combat windows, timers) without adjusting balance. When a redesign changes balance, say so and add a setting.

## 3. Coverage map

1. List every verb from the audit: movement (walk, sprint, crouch, jump, swim, dive, surface), traversal (ladders, ledges, ropes, vaults, doors, hatches, boarding/exiting vehicles and ships), each tool separately, vehicles (enter, pilot, dock, exit, each control), building/crafting, inventory/equipping, eating/drinking, reading/logs, combat, menus, map.
2. Tier each:
   - **Native** — done with the body as in a native VR game.
   - **Assisted** — physical trigger, the game's animation does the rest.
   - **Button** — unchanged; only for things with no physical analogue. Justify each in one line.
3. Table columns: verb · source (string key / data table / binding / wiki) · game function/class · tier · VR redesign · balance impact · status · tested.
4. Default: Native for anything the player touches with hands or body; Assisted when the game's animation/state machine can't be bypassed safely.
5. Build in gameplay-frequency order: what the player does every minute first.
6. Done when a full play session needs no flat-game button press except menus with no physical analogue.
7. **Controller button budget.** After tiering, list every action still needing a button or stick plus the framework's reserved inputs (UEVR opens its menu with both sticks clicked, for example) and assign them to the controller in a table (`notes/controls.md`): button · action · context (on foot / swimming / vehicle / menu). Use context to reuse buttons safely; keep the dominant hand's trigger and grip for physical interaction; avoid long-press and chord inputs for frequent actions; mirror the layout for left-handed mode. If actions don't fit, that's a decision point for the user.

Boarding and leaving ships/vehicles is the most common gap: treat hatch → ladder → interior → seat → controls → exit as one chain and test it end to end in both directions, including while the vehicle moves.

## 4. General implementation pattern

For each Native/Assisted mechanic: find the game's own function for the action → define the physical trigger (hand overlap + grip, motion over a threshold, body position) → call the game's function / set its state from the trigger → haptics and audio → handle interruption (release mid-action, damage, death, save/load, cutscene start) → log events (see `testing-loop.md`) → add a scenario test.

Prefer calling the game's own functions over re-implementing systems so saves, quests, achievements and co-op state stay consistent.

## 5. Recipes

### 5.1 Head stays inside vehicles / cockpits
- Detect vehicle state (possessed vehicle class or a piloting flag).
- In the camera hook (UEVR: `on_early_calculate_stereo_view_offset`), express the HMD position relative to a seat anchor and clamp it to a box/capsule sized to the cockpit (start ~0.3 m per axis, tune per vehicle).
- Past the clamp, don't hard-stop (nauseating): fade/vignette proportional to penetration depth.
- Same for walls on foot: trace from body head to HMD, fade on hit.
- Test: lean hard every direction in every vehicle; enter/exit repeatedly; at speed; vehicle destroyed while seated.

### 5.2 Physical climbing (ladders, ledges, rock faces)
- Hand objects follow controllers. Each tick, overlap/sphere-trace at each hand.
- Grip on a valid surface → store the grip point's world position; switch the character to a no-gravity mode (Unreal CharacterMovement Flying, or the game's own climb mode).
- While gripping: move the body by `-(current_hand_world - grip_point)`; with two hands, use the latest grip.
- Release with no grip → restore walking/falling; carry the hand's release velocity into the body for flings/vaults.
- Gate surfaces by physical material, class, or the game's own climbable/ledge detection, or players climb everything and break level design.
- Test: release mid-climb, grab spam, climb into ceilings, damage while climbing, save/load while hanging, mantle at top.

### 5.3 Grabbing and interacting with hands
- Find the game's interact function. Call it with the object under the hand instead of under the crosshair: hand overlap → nearest interactable → set the game's focus/target → invoke interact.
- Held items: attach to the hand socket on grab; on release detach and apply hand velocity (throwing).
- Haptics on contact. Test every interactable class, not just doors and pickups.

### 5.4 Holsters and body inventory
- Body-relative slots (hip L/R, chest, shoulder L/R, back) in HMD-yaw space, not full HMD rotation, so looking down doesn't move them; calibrate to user height.
- Grip inside a slot radius → equip that slot's item through the game's own equip function; release near a slot → stow. Haptic tick when a hand enters a slot.
- Map slots onto the game's hotbar/quick-slot data so saves and the flat UI stay in sync.
- Back slot opens the full inventory grid as a world-space panel.

### 5.5 Melee, gestures, two-handed aiming
- Controller velocity over 3–5 frames; swing = speed over threshold + direction → the game's attack function or synthesized input; apply impulse at the hit point for physical reactions.
- Two-handed weapons: aim = rear hand → front hand. Sights: projectile origin and direction from the weapon mesh, not the camera.
- Test: weak swings don't register; spam; swings during reload and menus.

### 5.6 Swimming
- Arm strokes: while in water, when both hands move backward relative to the HMD, push the body the opposite way scaled by stroke speed, with drag decay. Keep stick swimming as an option.
- Vertical movement follows HMD pitch, not the hidden flat camera.
- Handle the game's swim ↔ walk transitions so the camera doesn't snap.

### 5.7 UI
Full design rules (distances, angles, sizes, anchoring, diegetic order) are in `vr-design.md`; implementation summary:
- Menus on a lazy-follow or world-locked panel (UEVR projects the 2D UI to a quad by default; tune its distance and follow behavior).
- HUD → wrist or diegetic widgets bound to the same values the flat HUD reads; hide the flat HUD.
- In-game screens (PDAs, terminals) → render on the device/terminal mesh with poke interaction.
- Test small text at the headset's real resolution.

### 5.8 Hands and held objects
- Grip poses per item class, finger curl from controller touch sensors when empty-handed, IK arms or no arms (see `architecture.md` section 3).
- Held items constrained by physics so they stop at walls; ghost hand shows the real controller position when blocked.

### 5.9 Audio
- Attach the audio listener to the HMD, not the old flat camera, so spatial audio follows head movement (check whether the framework already does this).
- Sounds that came from the "player camera" (tool sounds, UI) should come from the hand or object that makes them.

### 5.10 Co-op
- Hand and head poses don't replicate to other players by default; others see the flat animation. Route every action through the game's own replicated functions (interact, equip, fire) so outcomes stay in sync, and test with a second player before claiming co-op support.

### 5.11 Cutscenes, dialogue and menus
- Detect them (adapter `is_cutscene`, `is_dialogue`, `is_menu_open`); suspend grabbing, climbing and holsters, keep head tracking, parent to the cutscene camera; fall back to a cinema screen for scenes that break. Restore state cleanly when they end.

### 5.12 Body and comfort
- Hide the head mesh, keep the body for shadows; hands from the game's mesh where possible.
- Options menu: snap/smooth turn, vignette, seated/standing height, left-handed mode, physical vs button climbing, physical vs simplified reload.
