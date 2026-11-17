# Owning the control scheme

The control scheme is one design owned by the orchestrator, written before breadth, and generated into bindings
and prompts. It's never the sum of each feature's favourite button. See `controllers.md` for the tooling.

## Rules (`irisify controllers lint` enforces the first six)

1. **Grips grab. Nothing else.** No locomotion, sprint or rotate on a grip when any grab feature exists. The analog
   grip needs explicit click thresholds with hysteresis (`lessons.md` D5).
2. **One owner per input, per context, per holding state.** Context = on foot / swimming / vehicle X / menu / tool X.
   Holding state = nothing / item / tool. Two features that both act on "right grip, on foot, holding an item" are a
   lint error (`lessons.md` D6).
3. **Every manifest action is bound in some context, or listed under `dropped:` with a reason** (`lessons.md` D1).
4. **No shortcut next to its physical replacement.** If `holster_draw` replaces `OpenQuickSlotWheel` and holsters are
   in the preset, the wheel isn't bound on foot (`lessons.md` A6). The replaced action stays available where the
   physical version doesn't apply (vehicles).
5. **Prompts are generated** from the same file as the bindings, never hand-written (`lessons.md` D3).
6. **Locomotion never reads the head** for direction, unless a scheme for it is an explicit option.
7. **The claim priority is written down**, for when spatial conditions overlap: body spot > grab near the hand >
   pointing gesture > game action. Implement it with an input-claim system (first claimer owns the press until
   release) and an explicit execution order per feature.
8. **Free buttons are a resource.** List them per context. Spend them on things that have no good gesture (recenter,
   laser toggle), not on duplicates.
9. **Map by the controller's real layout.** Not every controller is Touch-shaped: the Steam Frame has a left D-pad and
   all four face buttons on the right, plus bumpers. Read the runtime's input profile (`controllers detect`). Use the
   generic-controller and Touch bindings as fallbacks only.
10. **Steam Input off** for any game that uses SteamVR Input (`lessons.md` C1). It's a platform check, not a binding.

## The per-context table

Write it in `design/controls.yaml` (schema in `controllers/schema.md`) and render it in the design doc with
`irisify controllers table`. Example (Steam Frame, Subnautica, after the fixes):

| Context | L stick | R stick | L trigger | R trigger | L grip | R grip | A / B / X / Y (right) | L D-pad / bumpers / View |
|---|---|---|---|---|---|---|---|---|
| On foot | walk, full tilt runs, click jump | x snap turn | interact / pick up | use tool | grab | grab | A interact, B exit, X —, Y — | ↑ —, ↓ reload, ←/→ —; View pause |
| Swimming | swim along body facing | y up/down, x snap turn | interact | use tool | grab / hold the water | grab / hold the water | same | same |
| Seamoth | thrust/strafe | yaw/pitch | left module | right module | descend | ascend | B exit | ←/→ select module |
| PDA | — | scroll | — | submit | — | carry item onto body | A submit, B cancel | bumpers tabs, View pause |
| Builder out | walk/swim | y up/down | place | menu / cancel | pull to deconstruct | grab | B cancel | ←/→ rotate ghost |

## Checklist before breadth

- [ ] `irisify controllers detect` ran on the real headset. The profile is in the project.
- [ ] Every context has a table row. Every cell has at most one owner per holding state.
- [ ] `lint` passes: no double owners, no grip locomotion, no orphan actions, no shortcut next to its replacement.
- [ ] Bindings and prompts are generated. The game shows generated prompts, not gamepad glyphs.
- [ ] Every UI flow traced end to end in VR (open → select → confirm → close).
- [ ] Fallback bindings exist for the other controller families (Touch, Index, WMR, generic).
- [ ] The decision points (a button that replaces a physical action, an action dropped) are in `MODLOG.md` with a reason.
