# VR design notes: comfort, image, UI

What makes a VR conversion comfortable, readable and immersive. Numbers come from platform guidelines (Meta, Microsoft) and research; headsets differ, so treat them as starting values to tune on the target headset, and expose the important ones as settings.

## Contents
1. Comfort and motion sickness
2. Image: brightness, contrast, post-processing
3. UI: where it goes, how big, how it behaves
4. Making UI immersive (diegetic first)
5. Interaction feedback
6. Settings menu checklist
7. Locomotion, body and reach

## 1. Comfort and motion sickness

The cause is visual-vestibular conflict: the eyes see self-motion the inner ear doesn't feel. Every rule below reduces unexpected or unmatched motion.

**Never move the camera without the player's input.** Strip or disable from the flat game: camera shake, head bob, landing dips, recoil kick on the view, hit-reaction camera jerks, cinematic camera moves during gameplay, forced look-at, auto-centering. Move recoil to the weapon/hand instead of the view. Avoid any vertical camera motion the player didn't cause (elevators and vehicles that bob: stabilize the camera or add a stable cockpit frame).

**Frame rate.** Hold the headset's native rate; drops are worse in VR than on a monitor. Below the rate, the runtime's reprojection hides some judder but not all. Expose resolution scale and quality settings and default them conservatively. (Microsoft's floor is 60 FPS; most PC headsets target 72–120 Hz.)

**Locomotion options** (offer all; defaults matter):
- Movement: smooth (least comfortable, most immersive, many players' preference after adaptation), dash, teleport (most comfortable). Adjustable speed.
- Direction: head-based or controller-based; swappable movement hand.
- Use constant velocity: acceleration and deceleration ramps cause more discomfort than steady movement. Remove the flat game's movement smoothing ramps if possible.
- Turning: snap turn default (adjustable increments, e.g. 15°/30°/45°), smooth turn optional with adjustable speed. Rotation causes more sickness than translation.

**Vignette / tunneling / blinders.**
- Narrow the field of view during artificial movement and turning, fade back when stopped. Use a smaller window for rotation than for translation.
- A stable, high-contrast background in the periphery (a "cage" or grid) grounds the player better than plain black; plain black is fine as a simpler option.
- Scale strength with speed (stronger at higher speed/angular velocity), smooth the transitions.
- Evidence is mixed: tunneling helps many people, especially early on, but highly susceptible players can find a strong vignette ineffective and distracting, and adaptation over repeated sessions matters a lot. So: on by default at moderate strength, adjustable from off to strong.
- Keep the horizon stable during motion.

**Vehicles and cockpits.** A visible, stable cockpit frame around the player reduces sickness in moving vehicles. Keep the head inside it (clamp + fade, see `mechanics.md`). Avoid banking/rolling the camera with the vehicle unless the player is in a cockpit that rolls with them.

**Posture and body.** Standing and seated modes, height calibration and adjustable player height, real crouch plus artificial crouch, no mechanic that requires reaching the floor without an alternative.

**Collision.** When the head enters geometry, fade to black rather than pushing the player back.

## 2. Image: brightness, contrast, post-processing

- **Turn off or reduce screen-space effects that are wrong or uncomfortable in stereo:** motion blur (always off), depth of field (off; the eyes do their own focusing), lens flares and screen-space vignettes (the game's own vignette fights the comfort vignette), chromatic aberration, film grain, screen-space reflections if they differ per eye, heavy sharpening.
- **Bright flashes:** muzzle flashes, explosions, lightning and white screens fill the whole visual field in VR and are much harsher than on a monitor. Cap their intensity and duration; avoid full-screen white fades (fade to black instead).
- **Auto-exposure:** smooth and limit the game's eye adaptation; abrupt exposure swings when entering or leaving dark areas are tiring. Consider clamping the exposure range.
- **Dark scenes:** LCD headsets show dark scenes as grey with mura; OLED/micro-OLED show deep blacks but can smear. Provide a brightness/gamma slider with a calibration image ("barely visible symbol"), and don't rely on near-black detail for gameplay.
- **Overall brightness:** research found headsets usable at significantly lower brightness when content is compensated, but users still prefer brighter; let the player choose rather than forcing a level.
- **Distance detail:** VR resolves less detail at distance than a monitor; keep important gameplay signals large and contrasty.
- **Anti-aliasing:** shimmer is more visible in VR; prefer stable AA, and check upscalers per eye for ghosting.

## 3. UI: where it goes, how big, how it behaves

**Distance.** Headset optics focus at a fixed distance (roughly 1.25–2.5 m depending on headset); content near that distance is most comfortable to read. Content under ~1 m causes strain that rises sharply as it gets closer, and anything inside ~40 cm should fade out.
- Ray/laser-pointed panels: ~0.8 m to 3 m, avoid closer than 0.8 m.
- Directly touched (poke) panels: ~42–46 cm, arm's reach.
- Don't put interactive UI in the 0.5–0.8 m band (too far to touch comfortably, too close to read comfortably).
- Keep time spent reading near content (under 1 m) short.

**Angles.**
- Best region: 0° to 35° below the horizon; resting gaze 10–20° below.
- Avoid content more than 10° above the horizon or 60° below, or more than 45° to the side for frequent use.
- Frequent interactions horizontal and centered; rare ones can require turning.

**Size and type.**
- Size UI by angular size, not physical size: keep angular size constant when a panel moves nearer/farther.
- Text at least ~1.5° tall on a typical headset; larger for body text you read for long. Sans-serif, high x-height, Medium/Bold weights (thin weights break up), no italics, high contrast.
- Hit targets at least ~2.5–3° (about 22 mm at touch distance), at least 12 mm apart.
- Test every panel on the actual headset; monitors lie about legibility.

**Anchoring.**
- **Head-locked (rigidly following the head): avoid** for anything but brief, small, peripheral elements (a fade, a tiny damage indicator). Rigid head-locked HUDs are uncomfortable.
- **Body-locked / lazy follow:** follows the player's position, rotates only after the head turns past a threshold, with smoothing. Good for menus and HUD fallbacks.
- **World-locked:** fixed in the scene. Good for in-world screens, shops, crafting stations, and menus once opened.
- **Object/hand-locked:** attached to a tool, weapon or the wrist. Good for glanceable read-only info. For menus you poke with the other hand, spawn from the hand or wrist and then lock in world space, because a panel moving with the hand you're aiming at is hard to hit.
- Keep panels upright (no roll) and facing the player.

**Converting the flat game's UI (what UEVR and similar do by default):** the whole 2D UI is drawn to a quad in front of the player. That's an acceptable baseline for menus, but the gameplay HUD should be split up and moved (section 4). Set the quad's distance (~1.5–2 m), size and follow behavior (lazy follow, not head-locked) and test readability. Remove or reproject crosshairs, waypoint markers and screen-space indicators: a 2D crosshair at a fixed depth is wrong in stereo; put an aim dot or laser at the actual hit point instead, or none when the weapon has sights.

## 4. Making UI immersive (diegetic first)

For each element of the flat HUD and menus, choose the most immersive option that stays readable, in this order:

1. **Diegetic on the object it describes.** The information lives where it exists in the world: ammo shown on the weapon (Half-Life: Alyx lights each round on the magazine and dims as it empties, with empty magazines unlit so they're not mistaken for useful ones), oxygen gauge on the tank, battery level on the tool, vehicle stats on the vehicle's dashboard, damage shown on the suit.
2. **Diegetic on the body.** Wrist display for health/oxygen/time (glance by turning the wrist), a device pulled from a holster for map/PDA/logs.
3. **Spatial in the world.** World-locked panels for crafting, shops, storage, in-world terminals (render on the machine's own screen).
4. **Body-locked panel.** Lazy-follow panel for things with no world analogue (quest list, inventory grid, pause menu).
5. **Head-locked.** Only tiny transient cues.

Supporting rules:
- **Show on demand, hide when idle.** Glanceable info appears when you look at your wrist or hold the item, not permanently.
- **Highlight with light, not outlines.** Subtle glows on important items preserve immersion better than bright full outlines (an Alyx design choice); keep outlines as an accessibility option.
- **Use sound and haptics as UI.** Low-oxygen breathing, a tool's charge-up tone, a haptic pulse when ammo runs low reduce the need for visual HUD.
- **Notifications and subtitles:** lazy-follow, slightly below center, never on the edge of view; subtitles near the speaker when possible, else below center.
- **Make menus work both ways:** laser pointer and direct touch, as Alyx does.
- **Keep the readable fallback:** some players want numbers; offer a classic HUD panel option (wrist or lazy-follow).

How to do it in a mod: list every HUD widget and menu in the mechanic audit (they're mechanics too), find the variables each widget reads, hide the original widget, and rebuild it as a world-space widget or material parameter on the relevant mesh (Unreal: widget components and dynamic material parameters via pak/Blueprint mod; other engines: render-to-texture on the object). Rebind it to the same variables so it stays correct.

## 5. Interaction feedback

Every grab, poke, press and equip needs confirmation: hover state, pressed state, a short distinct sound, and haptics on controllers. Multi-step interactions benefit from staged feedback (Alyx's force-pull: highlight on select, lock on trigger, gesture to pull, each with its own sound). Don't change layouts on hover (things move under the finger). Prevent hands passing through panels when poking.

## 6. Settings menu checklist

Ship these in the mod's own options menu:
- Movement: smooth/dash/teleport, speed, head- vs controller-directed, movement hand.
- Turning: snap/smooth, snap angle, smooth speed.
- Vignette: off/low/medium/high, separate strength for turning.
- Posture: standing/seated, height calibration, player height offset, artificial crouch.
- Handedness: left/right dominant.
- Physical mechanics: physical vs simplified for climbing, reloading, valves/hatches, swimming strokes.
- Image: brightness/gamma calibration, flash intensity limit, resolution scale.
- UI: HUD style (diegetic / wrist / classic panel), UI distance and size, subtitle placement and size, highlight style.
- Comfort extras: cockpit frame/cage on/off, collision fade on/off.

## 7. Locomotion, body and reach

Design these physically before writing code; they decide whether every other mechanic feels right.

- **Head pitch never steers.** Players look around while moving; pitch-relative movement makes them "look at random places" to steer, and looking down dives. Facing (head or body yaw) is a fine source of direction, and so is a hand's pointing direction. Vertical movement comes from the stick, a hand, or its own stroke type, not from looking up and down. When a player complains about direction, ask which axis.
- **Feel is picked in the headset.** Build a minimal version of each candidate locomotion model and let the human try them all before polishing one. Speed curves and terrain checks prove it works, not that it feels right.
- **Swimming and other effort gestures must be effortless.** Small, comfortable motions count (wrist flicks, short pulls); speed matches or beats the stick; long glide; the stick always works as a fallback. Test for an hour of play, not ten seconds.
- **Grips are for grabbing.** Don't put vertical movement, sprint or menus on the grips once holsters, climbing or pickups use them.
- **Climbing moves the body by hand deltas.** No handing off to the game's climb cinematic or teleports; mantle at the top; keep the game's player state (inside/outside, current sub) consistent.
- **Minimize teleports and forced camera motion everywhere:** hatches, moonpools, vehicle entry and exit, intros, elevators. Each becomes physical, a smooth player-driven move, or a short fade, in that order of preference.
- **Height and body are part of the core.** One-time height calibration (standing and seated) so tall or short players reach the same things; a visible body with IK, or a deliberate hands-only choice; holstered items visible on the body where the hand goes to get them.
- **The head stays inside geometry.** Fade on head-in-wall and cockpit limits from day one; players will poke their head through hulls in the first minute.
