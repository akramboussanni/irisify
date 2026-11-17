# Immersion is not realism

The goal is presence: the player forgets they're holding controllers. Realism is one tool for that, and it often
works against it. A tank gauge you have to reach over your shoulder to read is realistic and breaks flow every time.
Half-Life: Alyx shows the rounds through the magazine instead of a floating ammo counter. The information is
*there*, in the world, and getting it costs a glance, not a procedure.

## The two questions

Ask both for every interaction and every piece of information, and write the answers in `design/reviews.md`:

1. **Does the current form break presence?**
   Signs: it floats, it's head-locked, it's a menu where the world has no menu, it shows a button glyph, it
   teleports or turns you, it says something the world could show (a "Power: 100%" label instead of a lit bar on
   the tool), or the game narrates what your hands could do.
2. **Would the fully physical form be worse?**
   Signs: tedious when repeated (a ten-second action done 200 times), tiring (whole-arm motions for travel),
   imprecise (strokes for 5 cm moves), unreachable (your own feet, your back), slower than the flat version for no
   gain, or easy to trigger by accident.

## Decide

| Presence broken? | Physical worse? | Do this |
|---|---|---|
| yes | no | make it physical or diegetic |
| yes | yes | the **lightest physical form that keeps the meaning**: a gesture that stands for the procedure (squeeze and pull to deconstruct; tap the flashlight to toggle it), or the information on the object |
| no | — | leave it (don't make things physical for their own sake) |

Make the "lightest form" concrete. A reload is "eject, insert", not "eject, pocket, find a magazine, check it,
insert, rack". Eating is "bring it to the mouth", not "unwrap, chew".

## Information

The order of homes (also in `design-process.md` step 6): on the thing → on the body or gear → in the world at the
place of use → handheld → lazy-follow flat. Examples:

| Flat game | Immersive form | Notes |
|---|---|---|
| ammo counter | rounds visible in the magazine, a glowing digit on the gun | Alyx |
| oxygen bar | dive computer on the wrist you glance at; haptic pulse when low | Subnautica rig: show on glance, full contrast |
| battery % | lit bar on the tool, amber/red, pulses near empty | |
| locker contents in a menu | a strip on the door, real models on the shelves | |
| vehicle HUD | stats on the dash, red glow when damaged | |
| quest marker | a ping in the world, a sound from that direction | keep it, but in the world |
| button prompt | nothing, if the object explains itself; else a glance label on the controller | ≤ 3 lines |
| subtitles | lazy-follow, low, small | no physical home: keep flat |

## Mechanics

| Flat | Too realistic | Right weight |
|---|---|---|
| hold W to swim | arm strokes only | body-facing stick for travel, grab the water for 5 cm nudges, strokes optional |
| ladder = interact + teleport | climb every rung of a 30 m shaft | hand over hand, with a glide-to-end after letting go on a long route |
| radial inventory | rummage in a backpack | tools visible on hips/chest/shoulders, draw by reaching |
| press E to eat | unwrap, bite, chew | bring it to the mouth, short dwell |
| equip fins | reach your feet | the menu, or knees as an honest stand-in |
| hold a tool with a grip | tool drops when you relax | hold without grip (the game's rule); squeeze-and-release at the body puts it away |

## Things that look immersive and aren't

- **Every button labelled, always.** It reads as a tutorial overlay (`lessons.md` D8).
- **Floating explainer panels.** Use one-time hints in context.
- **Physics on everything.** Items that jitter, clip or fly off break presence more than kinematic ones.
- **Haptics on everything.** Reserve strong pulses for meaning (picked up, broke, low oxygen).
- **Fake body parts that don't match the player.** A body at the wrong height or one that follows the head instantly
  is worse than no body. Calibrate, add the neck pivot, add body yaw lag.

## Review output

In `design/reviews.md`:

```
| id | current | presence broken? | physical worse? | decision | lightest form |
| oxygen | HUD bar | yes (head-locked) | n/a | diegetic | wrist dive computer on glance + haptics |
| swim | head-steered stick | yes (eyes steer) | strokes-only: yes | three tiers | body-facing stick, water grab, optional strokes |
```

The screenshot review (`screenshot-review.md`) re-checks this on images: "Is anything floating that has a physical
home?"
