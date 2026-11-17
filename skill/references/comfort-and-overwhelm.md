# Comfort and overwhelm audits

Both are measured by the rig and reviewed by a human. The rig catches the mechanical cases (snaps, label counts,
text sizes). The human catches what accumulates over time (fatigue, nausea, clutter).

## Comfort

### Rules
- The camera never moves or rotates without the player's input. Cinematics place the view once, then the player is
  free.
- A cut the game needs (seat entry, respawn) is **covered**: blink to black for 0.1 s, then fade back over 0.3 s,
  starting in the frame of the cut. A cut it doesn't need is **removed**: a physical route, or a glide over
  clamp(d/4, 0.25, 0.6) s for 0.35–6 m.
- Detect game teleports at the teleport call (`SetPosition` or the engine's equivalent), not from motion. A
  motion-based detector fires thousands of times at low frame rates.
- Where the head can go and the body can't, fade (walls) or limit (cockpits). Never let the player look out
  through a hull.
- No motion blur, DOF, camera shake or head bob. Bright flashes capped.

### Rig metrics (the adapter's `ComfortMonitor` measures them)
| event | threshold | meaning |
|---|---|---|
| `snap` | > 0.75 m beyond what velocity explains, or > 10° in one frame | a cut. Counted as covered if a blink was logged in that frame or the one before |
| `tilt` | up-axis change > 0.5°/frame outside vehicles | the world rolls |
| `turn` | yaw > 3°/s without input for > 0.5 s, outside vehicles | the view turns by itself |
| `drift` | > 0.25 m/s without input for > 0.5 s, not decaying, not falling | the body moves by itself |
| `flash` | mean luminance change > 0.25 within 0.2 s, not within 1 s of a head move | flashes, sudden fades |

Exclude the scripted head's own motion, the player's input plus 2.5 s of momentum after it, and windows the rig
itself opens (teleports, loads).

### Locomotion targets (set in design, measured by scenarios)
| metric | target | how |
|---|---|---|
| stick curve | half push ≈ 40% speed, monotonic | body speed at 0.25/0.5/0.75/1.0 |
| one-hand stroke | ≈ half stick top speed for a full sweep | 5/15/30/60 cm strokes |
| fine positioning | 5 cm hand move → 2.5–7.5 cm body move, settles ≤ 0.6 s | grab-the-water |
| effort per metre | hand path / body distance, lower is better; trend across builds | any physical locomotion |

### Human comfort checks (headset)
- Ten minutes of mixed play: any nausea, eye strain, neck strain?
- Five minutes of the main locomotion only: arm and shoulder fatigue?
- Seated and standing.

## Overwhelm

Overwhelm is too many things asking for attention at once. Subnautica's "thing that shows every button" was a correct
feature that overwhelmed (`lessons.md` D8).

### Budgets (the rig's `ui_contexts` scenario checks them)
| item | budget |
|---|---|
| visible text labels | swimming / on foot ≤ 12, building ≤ 20, cockpit ≤ 25, full-screen menus ≤ 80 |
| text size | FAIL < 0.5° em height, warn < 0.8°; target ≥ 2° for anything read in motion |
| UI distance | FAIL < 0.5 m unless held (under a controller or hand anchor) |
| overlap | text boxes from different canvases overlapping > 50% of the smaller one |
| head-locked canvases | none, except a lazy-follow HUD (it moves when the head turns 35°) |
| button labels | ≤ 3 lines per context, shown only when the controller is turned toward the face |
| hints | one at a time, never the same id twice per session |
| highlights | one reach ring per hand |

### Review questions (per context, in `design/reviews.md`)
1. List everything visible that isn't the world. Can any of it go?
2. What's the *one* thing the player needs here? Is it the most visible?
3. Is anything shown for a button that does nothing right now?
4. Does anything appear without the player looking for it? Is that earned (danger, low oxygen)?
