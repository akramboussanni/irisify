# Discoverability: a feature the player can't find doesn't exist

Subnautica's first playtest reported most of the mod as missing, because it was off by default and nothing in the
game pointed at it (`lessons.md` A4). Discoverability is designed, not added later.

## Defaults

- **One coherent preset ships on by default.** All the physical mechanics that fit together, plus every readability
  feature (they only change how things are shown).
- **Off by default only for features that are risky *and* optional** (an experimental drive handle, a strong
  vignette). Write the reason next to the setting.
- **Changing a default needs a settings migration** (versioned, ordered, one log line per step), or existing users
  never see it (`lessons.md` A5). Runtime kill switches are never saved.
- **One "Recommended" switch** in the options turns the whole preset on and never turns anything off.
- **Options grouped by situation** ("Start here", "Swimming", "Your body", "Vehicles"), not by implementation area.

## How a player finds each feature

For every feature in the preset, fill in one row in `design/reviews.md`:

| feature | seen as | taught by | when | rig check |
|---|---|---|---|---|
| holsters | tool models on hips/chest/shoulders | hint "Hold grip on a tool and put it on your body", first 3 PDA opens; tooltip line on bindable items | PDA open | `pda_hint` |
| reach to grab | ring on what a hand can grab | reticle line "<item>: reach out and grip it" | first grabbable in reach | `grab_ring_visible` screenshot |
| thigh PDA | PDA model on the left thigh | hint "Lift the PDA from your left thigh" | first PDA button press | `hint_once` |

Tools of discoverability, from lightest to heaviest:
1. **The object shows it.** A visible holstered tool, a handle that looks grabbable, a ring when in reach.
2. **Feedback on approach.** A haptic tick on entering a spot, a ghost preview of where an item will go.
3. **A one-line hint, once, in context.** Each hint has a context (show only while the PDA is open, say) and a
   priority, one at a time, ≥ 1.5 s apart in a context and ≥ 12 s apart otherwise, counted as seen after 2 s
   on screen. "Show hints again" resets them.
4. **A tooltip line** on the item or object involved.
5. **Glance labels** on the controller, at most 3 lines (`comfort-and-overwhelm.md`).

## When a control changes

Every removed or changed control gets a hint and a tooltip line where the player looks for the old one ("the UI
should say that", `lessons.md` G). Example: when Y stops assigning quick slots because the physical carry is on, the
PDA shows "Hold grip on a tool and put it on your body" on the next open.

## Checklist

- [ ] Every preset feature has a row, and no row says "options page" as the only way to find it.
- [ ] Fresh profile: rig scenario `discoverability` sees every preset feature report itself active.
- [ ] Old profile: `settings_migration` turns changed defaults on.
- [ ] Hints: no id shown twice per session, context respected (rig `pda_hint`-style check).
