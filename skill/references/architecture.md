# Architecture: a reusable VR library + a thin per-game adapter

Write the VR layer once and reuse it across games. Per game, write only the adapter that connects it to that game's functions. This is what makes deep conversions repeatable instead of a from-scratch effort each time, and it keeps game-specific hacks out of shared code.

## Contents
1. Layout
2. The game adapter contract
3. Library modules
4. Code quality rules
5. Version control
6. Tests that run without the game
7. Growing the library across games

## 1. Layout

```
vrlib/                      # shared, game-independent, versioned
  core/      input_provider (live | scripted | replay), poses, math, timing
  body/      body frame (HMD-yaw space), height calibration, slots
  hands/     hand state, grip, poses, finger curl, IK or hidden arms
  interact/  grab, poke, holster, climb, swim, throw, gesture detection
  comfort/   vignette, snap/smooth turn, collision fade, cockpit clamp
  ui/        panels (lazy-follow, world, wrist), text sizing, diegetic helpers
  feedback/  haptics, UI sounds
  telemetry/ state/event/error logs, command channel
  settings/  options menu + persistence
games/<game>/
  adapter.*  # implements the contract below for this game
  config.*   # tunables: slot items, climbable tags, cockpit boxes, scale
  scenarios/ # scenario tests for this game
  notes/     # recon, hooks, mechanics, gotchas
```

On UEVR this maps to a Lua library folder required by per-game scripts (plus an optional shared C++ plugin); on custom engines, to a static library linked by the per-game logic DLL. Pick one language per layer and stick to it.

## 2. The game adapter contract

Each game implements the same small interface; the library only ever talks to the game through it. Start from this list and extend only when a mechanic needs it:

- `get_player()`, `get_camera()`, `world_scale()`
- `get_movement_mode()`, `set_movement_mode(mode)`, `apply_movement(delta)`
- `find_interactables(position, radius)` → objects plus their kind (door, hatch, ladder, pickup, vehicle seat…)
- `interact(target, hand)` — calls the game's own interaction function
- `equip(item_or_slot)`, `unequip()`, `get_inventory()`, `get_quick_slots()`
- `fire/use(tool, origin, direction)`; `attack(hit_info)`
- `get_state()` → health, oxygen, ammo, etc. (feeds diegetic UI)
- `is_in_vehicle()`, `get_vehicle_seat_anchor()`, `enter_vehicle(v)`, `exit_vehicle()`
- `is_cutscene()`, `is_menu_open()`, `is_dialogue()`
- `on_level_loaded(cb)`, `on_player_respawn(cb)`

Every adapter function must log its calls through telemetry so scenario tests can assert on them.

## 3. Library modules (what each must handle)

- **Input provider**: one interface for HMD/controller poses, buttons, triggers and capacitive touch; live, scripted and replay implementations (see `testing-loop.md`).
- **Hands**: per-item grip poses (authored once per item class: pistol grip, tool grip, ladder rung, wheel), finger curl from capacitive/trigger values when nothing is held, smooth pose blending. Arms: two-bone IK to the game's shoulders, or hide arms entirely (floating hands are better than broken arms).
- **Held objects**: held items follow the hand with a physics constraint, not a hard attach, so they stop at walls instead of clipping through; optional weight lag by item mass; two-handed holds. Show a ghost hand at the true controller position when the held item is blocked.
- **Gestures**: velocity/trajectory windows, thresholds in config, hysteresis to prevent double triggers.
- **Comfort, UI, feedback, settings**: per `vr-design.md`.
- **Telemetry**: every module logs state transitions.

## 4. Code quality rules

- Keep pure logic (math, gesture detection, slot selection, climb deltas, clamp/fade) in functions with no engine calls, so they can be unit-tested.
- No hardcoded addresses or class names in the library; those live in the adapter/config, resolved by signature or reflection with a logged failure path.
- Every feature can be toggled off at runtime from settings; a broken feature disables itself and logs instead of crashing.
- Restore everything on unload/reload (movement modes, hidden meshes, hooked state).
- Name things after the game's own names found in discovery, so code and notes cross-reference.

## 5. Version control

- The mod is a git repo from the first file. Commit each working slice with a message saying what was verified and how ("ladder climb: scenario ladder_up passes, 3 screenshots"). Tag releases.
- When a change breaks the game, revert to the last good commit instead of patching forward blind.
- Never commit game files, dumps or decompiled code; keep them in an ignored local folder.

## 6. Tests that run without the game

- Unit tests for the pure logic (Lua: busted or a tiny test runner; C++: any test framework), run on every change by the offline worker.
- Adapter stub: a fake game implementing the contract, so library features can be exercised end to end with scripted input before touching the real game.
- In-game scenario tests (`testing-loop.md`) are the final check.

## 7. Growing the library across games

- After each game ships, review its adapter and config: anything that turned out game-independent (a gesture detector, a slot layout helper, a cockpit clamp variant) moves into `vrlib/` with tests.
- Version the library (semantic versioning) with a changelog; each game pins the library version it was tested with, so library changes can't silently break a shipped game.
- Extend the adapter contract only when a second game needs the same thing; one-off needs stay in that game's adapter.
- Keep a "patterns" note per engine (how the interaction system, equip system and movement modes were found and wrapped) so the next game on that engine starts from it.
