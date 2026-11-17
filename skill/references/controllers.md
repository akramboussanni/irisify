# Controller knowledge: detect, read the real profile, generate bindings and prompts

One source of truth, `design/controls.yaml`, generates the SteamVR binding JSON for every controller family **and**
the on-screen prompt tables. Prompts can't drift from bindings, because both come out of one generator
(`lessons.md` D3, D4).

## 1. Detect

```
irisify controllers detect --machine fedora
```

In order, until one answers:
1. **The adapter's runtime report** (best): at boot the adapter logs `[Irisify] controllers: left=<type> right=<type>
   hmd=<type> runtime=<name>` from OpenVR `Prop_ControllerType_String` / OpenXR's current interaction profile.
2. **SteamVR's log**: `vrserver.txt` lines naming the driver and device class (`frame_controller`, `knuckles`,
   `oculus_touch`, `holographic_controller`...).
3. **Installed drivers**: `<SteamVR>/drivers/*/resources/input/*_profile.json`.
4. **Ask the user**, with the detected candidates.

Then it reads that driver's **input profile** (`<driver>/resources/input/<type>_profile.json`), which lists every
component (`/input/a`, `/input/grip`...), its type (`button`, `trigger`, `joystick`), its side, and capabilities
(`click`, `touch`, `value`, `force`), plus `mirror_mappings`. It writes them to `.irisify/controller-profile.json`. The
binding generator only uses components the profile has.

## 2. Known profiles (`controllers/profiles/`)

| type | headset | layout notes |
|---|---|---|
| `frame_controller` | Steam Frame | **Left: D-pad (up/down/left/right), View, bumper. Right: A, B, X, Y, Menu, bumper.** Both: thumbstick (click, touch), trigger (analog), grip (analog *trigger* type: set click thresholds), thumbrest (touch, SteamVR-internal). Poses incl. `openxr_grip`/`openxr_aim`. Skeleton. Mirror mapping: left D-pad up/right/down/left ↔ right Y/B/A/X, View ↔ Menu. HMD type is `frame_hmd`: never bind controllers to it. **Steam Input must be off for the game.** |
| `knuckles` | Valve Index | A/B per hand, trackpad, force-sensing grip, finger tracking |
| `oculus_touch` | Rift/Quest via Link/Air Link/VD/ALVR | X/Y left, A/B right, menu left, grip and trigger analog |
| `holographic_controller` | WMR | trackpad + thumbstick, menu, grip button |
| `generic` | OpenXR `khr/generic_controller` fallback | trigger, squeeze, thumbstick, primary, secondary, menu |

The Frame profile was read from the runtime's own file on the test laptop on 2026-11-17 (`drivers/frame_controller`).
Refresh it with `irisify controllers detect --refresh` after SteamVR updates.

## 3. The manifest and context table (`design/controls.yaml`)

```yaml
game: subnautica
action_set: /actions/subnautica
app_key: steam.app.264710
actions:                      # every action the game or mod reads
  - {name: Move, type: vector2}
  - {name: LeftHand, type: boolean, label: "Interact"}
  - {name: MoveUp, type: boolean, label: "Grab", role: grab}       # role: grab → only on grips
  - {name: UIAssign, type: boolean, label: "Assign"}
dropped:
  - {name: TakePicture, why: "no use in VR"}
contexts:
  on_foot:
    left:  {thumbstick: {position: Move, click: Jump}, trigger: LeftHand, grip: MoveDown, dpad_up: PDA}
    right: {thumbstick: {position: Look}, trigger: RightHand, grip: MoveUp, a: LeftHand, b: Exit}
  pda:
    right: {trigger: UISubmit, b: UICancel, y: UIAssign}
families:                     # how abstract buttons map onto each controller family
  frame_controller: {}        # native names, nothing to map
  oculus_touch: {dpad_up: y, dpad_down: x, view: menu}
  knuckles: {dpad_up: b, x: a, y: b}
```

SteamVR bindings aren't per context (one binding per action set), so the generator **merges** the contexts into one
binding per family (the union of sources per input). The *context* table is what the lint and the prompts use: the
mod decides per context what an action does.

## 4. Commands

```
irisify controllers lint design/controls.yaml [design/interactions.yaml]
irisify controllers bindings design/controls.yaml --out StreamingAssets/SteamVR/   # bindings_<type>.json + actions.json default_bindings
irisify controllers prompts design/controls.yaml --out prompts/                    # prompts.<type>.json + PROMPTS.md
irisify controllers table design/controls.yaml                                     # markdown table for the design doc
```

Lint errors: a component the profile doesn't have; two owners for one input in one context and holding state; a
`role: grab` action off the grips, or a non-grab action on a grip; a manifest action neither bound nor dropped; a
shortcut bound in a context where its physical replacement is active (from `interactions.yaml`).

## 5. Prompts at runtime

The adapter loads `prompts.<detected type>.json`: `{context: {action: {hand, input, label, glyph}}}`. It replaces the
game's prompt text and glyphs (Subnautica: a prefix on `GameInput.AppendDisplayText`). Glyph names map onto the
game's own sprites where one fits (trigger → LT/RT, bumper → LB/RB) and fall back to text ("L Grip").

## 6. Focus first

If input doesn't arrive, it's almost never the binding: `irisify doctor input-focus --machine <m>` checks Steam Input
for the game, Steam's console log for "Opted-in Controller Mask" / "uses xinput", and the adapter's
`IsInputAvailable` / `bActive` lines.
