# Building the VR core yourself (no UEVR)

For engines without a universal injector. This is the part UEVR and REFramework do for you; here you do it by hand using the finds from `re-pipeline.md`. Study open-source precedents first: UEVR and REFramework (praydog, both open source), Cemu's BotW BetterVR, and the Unity VR injectors (e.g. UnityVRMod repos) show working architectures.

## Contents
1. Choose a stereo method
2. OpenXR plumbing
3. Head tracking and aim decoupling
4. UI
5. Performance and comfort
6. Order of work

## 1. Choose a stereo method

| Method | How | Pros | Cons |
|---|---|---|---|
| **Synchronous stereo (best)** | Call the scene render twice per frame with left/right view and projection | Correct 3D, no ghosting | Must find and safely re-enter the scene render function; game-side per-frame state (TAA history, particles, occlusion) may assume one view per frame |
| **Alternate frame / alternate eye (AFR/AER)** | Render left eye on even frames, right on odd; present each to its eye | Much easier: only the camera changes per frame | Ghosting on motion, halves effective framerate per eye; this is what R.E.A.L. uses (with mitigation in AER v2) |
| **Synchronized sequential** | Like AFR but the game simulation is stepped once per pair of frames | Fewer timing artifacts than plain AFR | Still two renders' latency; particles/animation timing issues |
| **Depth reprojection** | Render once, synthesize the second eye from depth | Cheapest | Not real stereo; disocclusion artifacts; use only as a last resort or preview |

Start with AFR to prove the pipeline end to end, then attempt synchronous stereo.

Per-eye problems to expect: screen-space effects (SSR, SSAO, motion blur, vignette, lens flares) computed for one view; TAA/upscalers keeping one history buffer; frustum culling done once for the mono camera (widen it to cover both eyes); shadows rendered once (usually fine to share).

## 2. OpenXR plumbing

- Create the OpenXR instance/session with the graphics binding matching the game (D3D11 or D3D12 device obtained from the hooked swapchain or device creation). For Vulkan, the Vulkan binding.
- Create per-eye swapchains (or one array swapchain), copy/resolve the game's rendered eye image into them each frame, submit a projection layer.
- Frame loop: `xrWaitFrame` / `xrBeginFrame` / `xrEndFrame` must be paced against the game's own present; get the predicted display time from `xrWaitFrame` and locate views with it.
- Build each eye's projection from the four FOV angles OpenXR returns (asymmetric frustum) in the engine's convention (left/right handed, reversed-Z, clip-space depth range). Getting this convention wrong is the most common cause of "everything is warped/swims".
- World scale: convert OpenXR meters to engine units (find the engine's unit, often cm or m).
- Fall back cleanly to flat mode if the runtime isn't present.

## 3. Head tracking and aim decoupling

- Write the HMD pose into the camera at the last point before view matrices are built (found in recon), composed with the game's own camera (body position + yaw).
- Decouple: movement direction from HMD or a controller; aiming from the weapon hand; the game's "camera forward" used for interaction traces must be redirected to the hand or HMD as the mechanic needs.
- Cutscenes: keep head tracking but parent to the cutscene camera; offer a "cinema screen" fallback for scenes that break.

## 4. UI

- Redirect the UI pass to an offscreen render target, then display it as an OpenXR quad layer (crisp, cheap) or a world-space quad / wrist panel.
- Crosshairs and screen-space markers must be reprojected to world space or removed.

## 5. Performance and comfort

- VR needs both eyes at the headset rate; budget roughly double the flat GPU cost for synchronous stereo. Expose resolution scale and the game's own quality settings.
- Never let the camera move without user input (cutscene camera shakes, head bob, landing dips): strip them.
- Snap/smooth turn, vignette, seated mode, height calibration.

## 6. Order of work

1. Hook present; display the flat game image on a quad in the headset (proves OpenXR plumbing).
2. Head rotation on the camera.
3. AFR stereo with correct projection.
4. Full 6DoF, world scale.
5. Synchronous stereo if achievable.
6. UI redirection.
7. Hands and the mechanic work (SKILL.md section 5 onward).
