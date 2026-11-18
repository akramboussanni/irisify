# Gates and checklists

The workflow is a state machine in `.irisify/state.json`, driven by `irisify gate check <gate>`. Each gate passes
only with evidence (files, rig results, sign-offs). The dashboard's Workflow card shows the state. Commands that
depend on a gate refuse to run before it passes, and say why:

| Command | Needs |
|---|---|
| `irisify fanout` (start parallel workers) | `first-boot`, `design`, `slice` |
| `irisify integrate` | `first-boot` |
| `irisify deploy --device <headset>` | `first-boot`, and suite green on that build for `ready` deploys |
| `irisify publish check` | `ready` |

`--force "<reason>"` overrides a gate. The reason goes in `MODLOG.md` and on the dashboard. Use it only when the user
said to.

## intake
- [ ] Detection run (`irisify machine check`, `controllers detect`, `doctor platform`).
- [ ] Every blocking intake question answered or decided with a reason.

## platform (preflight, per machine that runs the game)
`irisify doctor platform --machine <name>` checks and prints fixes:
- [ ] Game install and build id match the decompiled build.
- [ ] VR runtime present. Headset connection path known (wired, Steam Link or Frame adapter, WiVRn/ALVR, standalone).
- [ ] Linux: native Steam (not Flatpak) when a wireless adapter is involved; kernel ≥ the headset profile's minimum;
      hardware H.265/HEVC encode; `cap_sys_nice` on the compositor launcher; the adapter's network managed.
- [ ] Steam Input **off** for the game, on every machine that runs it.
- [ ] Mod loader installed and launch options set (Proton: `WINEDLLOVERRIDES="winhttp=n,b" %command%`).
- [ ] The agent can deploy and read logs on it (SSH or adb, see `machines.md`).

## first-boot (hard stop)
- [ ] The game starts in VR on the user's real headset.
- [ ] Boot log: `[Irisify] patches: N applied, 0 failed`.
- [ ] Input diagnostic: `IsInputAvailable=true`, action set active, a face button and a trigger produce DOWN events.
- [ ] Build id in the log = the deployed build.
If the agent can't run the game, ask the user to launch it **now** and paste or sync the log.

## design
- [ ] All artifacts in `design-process.md` exist.
- [ ] `irisify design lint` and `irisify controllers lint` pass.
- [ ] User signed off the decision points on the dashboard.

## slice
- [ ] One high-frequency mechanic, end to end, through the adapter, with telemetry.
- [ ] Its scenario passes on the rig, comfort events 0.
- [ ] Foundations in place: height calibration, body frame with neck pivot, control scheme generated, on-body UI rule.
- [ ] Human feel check recorded (intake.md, section 5).

## breadth (per feature, before merging)
- [ ] Feature scenario passes, plus a worst-case variant for content-heavy features (`irisify scenarios lint`).
- [ ] Comfort, overwhelm and view checks pass (clearance, one held model per hand, no body model near a busy hand,
      no duplicated info, no text in the 10° edge bands).
- [ ] Merged by the integrator in a batch; the affected scenarios (`auto`, with shared-core fan-out) ran on the merged
      build, not just the feature's own scenario.
- [ ] Movement changes log per-step physics (input → applied velocity → body speed).
- [ ] Screenshot moments reviewed.
- [ ] Discoverability row filled in. In the preset, or off with a reason.
- [ ] Changed default → settings migration.
- [ ] No new double owner in `controllers lint`.

## ready (for the headset)
- [ ] The headset runs the integration build (dashboard Devices).
- [ ] Full (or nightly) suite green on that exact commit: `irisify deploy` to a headset refuses otherwise. No flaky
      scenario unexplained.
- [ ] Body: proportions check and clearance check pass standing, seated and in each vehicle.
- [ ] All changed screenshots reviewed by the agent.
- [ ] The headset checklist lists every `cannot_cover` item plus the user's own open complaints in their words.
