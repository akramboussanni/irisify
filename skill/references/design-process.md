# The design process

The Subnautica project built good mechanics on a missing design. Every area session designed its own corner, and
nobody designed the things that cut across all of them: what each button means, where the body is, where
information lives, what moves the camera, and how a player finds any of it (`lessons.md` A3). This file is the
process that prevents that. It is **not optional**, and the workflow state machine enforces it: `irisify gate check
design` fails until the artifacts below exist and pass their checks, and fan-out, integration and deploys refuse
to run before that.

The orchestrator (the agent that talks to the user) owns every design artifact. Workers read them and propose
changes in their notes. They never edit `design/controls.json` or `design/body-map.md` themselves.

## Overview

| Step | Artifact (in the mod repo) | Who decides | Machine check |
|---|---|---|---|
| 0. Intake | `design/00-intake.md` + `.irisify/intake.json` | user answers, agent judges | intake has no unanswered *blocking* question |
| 1. Evidence | `design/01-evidence.md` | agent | engine, build id, existing VR work, input path recorded |
| 2. Physical sketch | `design/02-physical-sketch.md` | agent, user reviews | one section per locomotion mode and per high-frequency mechanic |
| 3. Interaction inventory | `design/interactions.json` | agent | `irisify design lint`: every row has form, tier, context, discoverability, immersion verdict |
| 4. Control scheme | `design/controls.json` → generated bindings + prompts | agent, user approves trade-offs | `irisify controllers lint`: no double owner, every action bound or dropped, grips grab-only |
| 5. Body map | `design/body-map.md` | agent | calibration, neck pivot, body yaw, all spots in one frame |
| 6. Information placement | `design/ui-placement.md` | agent | every flat UI element has a home or a reason |
| 7. Comfort plan | `design/comfort.md` | agent, user picks defaults | teleport/cinematic audit complete, head-clip plan |
| 8. Reviews | `design/reviews.md` | agent; user for taste | immersion, overwhelm, discoverability tables filled in |
| 9. Test plan | `design/test-plan.md` + scenario files | agent | every interaction has a scenario or a `cannot_cover` line |
| Gate | dashboard **Design** card | **user signs off** | all of the above |

Then the vertical slice (one mechanic end to end, with the human feel check) *tests the design*. Expect to revise
steps 3–7 after it. That is the cheap moment to change them.

`irisify init` creates `design/` with a template for each artifact (`skill/templates/design/`).

---

## Step 0. Intake: grill the user, with judgment

Read `intake.md`. In short: detect everything you can (headset, controller type, runtime, host, Steam Input, game
build) before asking anything. Ask only the questions whose answers change a decision and can't be detected. Ask
the blocking ones first, at most four at a time, each with a recommended default. Write the answers down, and stop
asking once the defaults are good enough to build on.

## Step 1. Evidence: the installed build, not the wiki

Record: engine and version, game build id, mod loader, existing VR mods and what they already solve (fork a good base
before starting over), how input reaches gameplay (the input layer's call into the game), the interaction system
behind the interact button (it lists every interactable at once), the camera rig, the HUD/canvas system, and the
save/settings system (how settings are serialized, which matters for `lessons.md` B3 and A5).

**Asset inspection** (`lessons.md` E11): list the game's own in-world screens, gauges, labels and lights, with their
meshes, UV regions and materials (`tools/recon/find_screens.py` with UnityPy for Unity; AssetRipper; FModel for
Unreal). Some screens are painted into a texture with no object to attach to; you need to know before designing UI.
Also dump the player skeleton: every bone with its full path and children (`lessons.md` E12). Every claim gets a
file:line or an address. Write *unknowns* as unknowns.

## Step 2. Physical sketch: how would a body do this?

Before choosing any input, write for each locomotion mode (walk, swim, climb, drive, fly...) and each mechanic used
more than once a minute:

1. **How a real person does it.** A diver swims along the body, and depth is a separate deliberate act. A climber
   pulls with alternating hands. A driver's hands stay on the controls.
2. **What a VR player can sustain for an hour.** Thumbs and wrists are cheap. Whole-arm strokes tire you in minutes.
   Looking hard down strains the neck. Seated players can't turn their body, and standing players drift.
3. **Seated and standing.** Both must work unless the intake says otherwise.
4. **The three tiers of control.** *Travel* (cover distance), *cruise* (hold a speed and direction without effort)
   and *fine positioning* (move 5 cm precisely). Each tier needs a mechanic. Subnautica's swimming had travel
   (stick) and nothing for fine positioning until "hold the water" was added (`lessons.md` E2).
5. **Where the eyes are free.** The head looks. It never steers unless the user asked for it.
6. **Precision, not just speed.** How does the player move 5 cm without the stick? (Subnautica: grip the water and move
   the hand, 1:1.) Speed graded by stroke size and stick deflection, scaled to the game's real top speed, which
   equipment changes.

The result is a short paragraph per mode plus the chosen design, for example "body-facing swim, right stick depth,
grab the water to nudge 1:1, optional strokes on top". Write the physical version first, then the immersion check
(step 8), then the input.

## Step 3. Interaction inventory

One row per thing the player does, in `design/interactions.json` (schema: `skill/templates/design/interactions.json`):

```yaml
- id: holster_draw
  game_action: QuickSlots.SlotKeyDown          # the game function it ends in (use the game's own path)
  contexts: [on_foot, swimming]
  form: physical                               # physical | assisted | button | dropped
  input: {hand: right, gesture: grip_at_spot, spot: right_hip}
  when_holding: nothing                        # nothing | item | tool | any: what's in that hand
  replaces: [OpenQuickSlotWheel, CycleNext, CyclePrev]   # buttons this makes redundant
  frequency: high                              # high | medium | low (drives order of work)
  discoverability: {seen: "tool model on the hip", taught: "hint 'holsters' on first bind"}
  immersion: {verdict: physical, why: "reaching to the hip is faster than a menu"}
  feedback: [haptic_tick_on_enter, ghost_on_spot]
  owner: body                                  # which worker builds it
  scenario: holster_draw_stow
```

Rules for this table:
- **Trace every UI flow end to end** (open → select → confirm → close), not only the button that starts it. The
  Subnautica PDA assign flow had an unbound confirm action and a gamepad-only picker (`lessons.md` D1).
- **Walk the whole action manifest.** Every game action appears in some row, even if as `form: dropped` with a
  reason.
- **`when_holding` is part of the key.** The same grip at the same spot means different things with and without an
  item in hand (`lessons.md` D6).
- **Every let-go has a visible outcome** (`lessons.md` E8). Write it in `feedback`.
- **Pick targets from the input the player uses** (the laser, the hand), never the game's hover or gaze.

## Step 4. Control scheme

Read `control-scheme.md` and `controllers.md`. Write `design/controls.json` (the action manifest + one table per
context) and generate everything else from it:

```
irisify controllers detect            # real controller type and component list from the runtime
irisify controllers lint design/controls.json design/interactions.json
irisify controllers bindings design/controls.json --out <mod>/StreamingAssets/SteamVR/
irisify controllers prompts  design/controls.json --out <mod>/prompts/
```

Hard rules (lint fails otherwise): grips grab, nothing else; one owner per physical input per context and holding
state; every manifest action bound in some context or dropped with a reason; no shortcut bound while its physical
replacement is in the preset; prompts generated, never hand-written; the claim priority is written down
(body spot > grab near hand > pointing gesture > game action).

## Step 5. Body map

Read `vr-design.md` section 7. Decide and write down:
- **Height calibration:** stored per posture (standing, seated), measured from the runtime floor, with a gesture and a
  menu entry, and a prompt when uncalibrated.
- **Body frame:** where the body is relative to the head: a **neck pivot** (~20 cm below and ~9 cm behind the eyes,
  scaled with height), body yaw with a dead zone (±35–40°) and lazy follow, and a snap to the head after a big
  change. One function gives this frame. The mesh, holsters, pouches, UI anchors and every "is the hand at the body?"
  test use it (`lessons.md` E6).
- **The visible body:** full body with arm IK (and leg bend on crouch), or a deliberate hands-only choice with a reason.
- **Spots:** a table of every on-body spot (name, offset in the body frame, radius, hand, owner). Spots closer than
  2× their radii to each other need different hands or an explicit priority.
- **What's visible on the body:** holstered items as their own models, not icons (`lessons.md` E7). Body models hide
  while a busy hand is within ~20 cm (`lessons.md` E13).
- **The skeleton, verified:** bones resolved by verified subtree and logged at setup; head *and* neck collapsed when
  the full body shows (neck skin can be baked into the body mesh); proportions asserted; children of any moved bone
  listed (`lessons.md` E12).
- **Seated in vehicles:** the seat pose rarely matches the player's eye height. Shift the seated body, bounded, so its
  eye point matches the headset through the neck pivot.
- **Out-of-view slots** (shoulders, back): regions in the body frame with generous margins and distinct haptics, a
  reach success-rate scenario with a target, and false-trigger cases. Ask first whether the spot suits the platform
  (`lessons.md` E14).

## Step 6. Information placement

List every piece of flat UI the game shows (HUD widgets, prompts, menus, notifications, subtitles, tooltips,
reticle text). For each, choose a home in this order and write the reason:

0. **The game's own surfaces first:** an existing cockpit screen, gauge or label from the asset inspection. If it is
   painted into a texture, overlay it in the object's frame and check parallax with head-lean shots (`lessons.md` E11).
1. **On the thing it describes:** charge on the tool, contents on the locker door, rounds in the magazine.
2. **On the body or gear, where you'd glance anyway:** wrist dive computer, tank gauge, glove.
3. **In the world, at the place of use:** crafting panel at the machine, vehicle stats on the dash.
4. **Handheld:** a tablet or PDA you hold and can put away. Check it doesn't keep the game's modal locks (`lessons.md` B4).
5. **Flat, lazy-follow HUD:** only for what has no physical home (subtitles, system messages). Bring it in from the
   lens edges and size it in degrees.

Size everything by its smallest meaningful element in visual angle, for the target headset's pixels per degree (the
headset profile has it): text ≥ 2° font height, icons ≥ 4 cm at a 45 cm hold, panel text never below 0.8°.

## Step 7. Comfort plan

Read `comfort-and-overwhelm.md`. Produce:
- **The teleport and cinematic audit:** grep every position set, cinematic, camera-driving and forced-look call in the
  game code. One row each: what the game does, and the VR treatment (physical route / glide / blink / keep with a
  reason). Subnautica's table (in `examples/subnautica/design/comfort.md`) has about 20 rows.
- **The head-clip plan:** where the head can go that the body can't (walls, hulls, cockpits), and what happens then
  (fade, limit).
- **Comfort defaults** for the user's tolerance (from intake): turn type, vignette, blink on cuts.
- **Comfort budgets** the rig will enforce: no snap > 0.75 m or > 10° in one frame unless covered, no view turn or drift
  without input, no luminance jump > 0.25 within 0.2 s.

## Step 8. Reviews

Fill in three tables in `design/reviews.md`:

- **Immersion review** (`immersion.md`): for every interaction and every information element, does it break
  presence, and would the realistic version be tedious? Pick the lightest physical form that keeps the meaning.
- **Overwhelm review** (`comfort-and-overwhelm.md`): per context, how many things compete for attention (labels,
  panels, hints, highlights). Budget: ≤ 3 button labels per context, shown on a glance only, and one hint at a time.
- **Discoverability review** (`discoverability.md`): for every feature in the preset, how a player who never opens
  the menu finds it, where it's taught, and how often.

## Step 9. Test plan

Every row of `interactions.json` names a scenario. Content-heavy features (containers, menus, inventories, building)
also get a **worst-case** scenario: full inventories, many kinds, long names, deep pages (`lessons.md` A10). Every scenario declares `covers` and `cannot_cover`, and names its
screenshot moments with a caption question. The union of `cannot_cover` becomes the human's headset checklist
(`screenshot-review.md`, `testing-loop.md`).

## The design gate

`irisify gate check design` passes when every artifact exists, the lints pass, and the user has signed off on the
dashboard's Design card. The card shows the decision points (choices a reasonable player would make differently)
with your recommendation for each. Don't ask the user to read the whole design. Show them the decisions.

---

## After every playtest: the feedback loop

The design is wrong somewhere until the user has played it. For every piece of feedback:

1. **Classify it:** bug (the design says X, the build does Y), design gap (the design never covered it), or
   preference (reasonable players differ: add a setting, keep the default).
2. **Change the design artifact first**, then the code. A design gap always changes an artifact.
3. **Add the check that would have caught it** (a scenario, a lint rule, a screenshot moment with a question).
4. **Write a lesson** in `notes/lessons.md` when the gap could recur in another game, and send it upstream to
   Irisify's `docs/lessons.md`.
5. **Close the loop with the user** on the dashboard: the issue shows the build that fixes it, and the headset
   checklist gets the line "re-check: <their words>".

Subnautica feedback, classified as examples:

| User said | Class | Artifact changed | Check added |
|---|---|---|---|
| "swimming is still ass ... without just looking at random places" | design gap | physical sketch (swim), controls | `swim_controls` (level along body, head turn doesn't steer) |
| "the grip buttons are used for going up and down" | design gap | controls (grips grab-only) | controllers lint rule |
| "the buttons shown in UI just don't line up" | design gap | controls → generated prompts | prompt/binding consistency test |
| "I don't have a body, only arms" | design gap | body map | look-down screenshot moments |
| "way too much effort, way too slow" | bug (against targets) + gap | physical sketch (three tiers) | `swim_speed_curve`, effort per metre |
| "overwhelmed by the thing that shows every button" | design gap | overwhelm review | `ui_contexts` label budget |
| "builder tablet is way too small" | bug (sized in metres) | ui-placement (size in degrees) | text angle FAIL < 0.5° |
| "dropped items seem to disappear" | design gap | interactions (`feedback` on let-go) | `carry_release_away` |
| "the UI should say that" | design gap | discoverability review | `pda_hint` |
