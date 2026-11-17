# Machines, headsets and links

A project has one or more machines, in `.irisify/machines.json` (or the dashboard's Machines page, which writes the
same file). Each machine has **roles** and a **link**.

| Role | Means |
|---|---|
| `dev` | builds the mod, decompiles, runs the dashboard (often the agent's own machine) |
| `game-host` | runs the game in VR for the human (wired or streaming to the headset) |
| `rig` | runs the headset-free test rig (simulated headset, scripted hands) |
| `headset` | the headset itself; for standalone play it's also a game host |

| Link | Use for | Notes |
|---|---|---|
| `local` | this machine | |
| `ssh` | Linux/Windows/macOS hosts, SteamOS-based headsets with SSH on | key auth; Tailscale address preferred (stable across networks) |
| `adb` | Android-based headsets (Quest; others with developer mode) | `adb connect <ip>:5555` over Wi-Fi or Tailscale; file push/pull, logcat |

One machine can do everything (a Windows PC: dev + game-host + rig), or the roles can be split. On Subnautica the
Mac was `dev`, the Fedora laptop was `game-host` + `rig`, and the Steam Frame was `headset` + standalone `game-host`.

## Commands

```
irisify machine add fedora --roles game-host,rig --link ssh --host user@rig-laptop
irisify machine add frame  --roles headset,game-host --link ssh --host steam@frame   # or --link adb --host 192.168.1.50:5555
irisify machine check [name]      # reachability, OS, GPU, runtime, game install, Steam Input, lock, build
irisify machine setup <name>      # the guided steps; runs what the agent may, prints what needs the human
```

`check` writes `.irisify/machines-status.json`, which the dashboard reads for its connection panel.

## Setup steps (generated per machine from its roles, OS and headset profile)

Each step is marked **agent** (the agent runs it), **you** (needs sudo, a password, a GUI click, or a physical
action) or **check** (read-only). The agent never runs a "you" step, even when it could reach it.

1. **Network:** Tailscale on both ends (`tailscale status` shows the peer online), or a reachable LAN address.
   Tailscale needs the user's sign-in. That's a "you" step, in the browser they normally use.
2. **Link:** an SSH key (`ssh-copy-id`, a "you" step once), or `adb pair`/`adb connect` with developer mode on the
   headset (a "you" step on the headset).
3. **Game:** installed, the build id recorded, saves backed up (`irisify backup`).
4. **Platform:** the headset profile's `host_requirements` (`controllers/profiles/*.json`), for example the Steam
   Frame on Linux needs native Steam, kernel ≥ 7.2, H.265 encode and `cap_sys_nice`.
5. **Rig** (for `rig` machines): see `testing-loop.md` and `tools/rig/`. Linux uses Monado + OpenComposite (SteamVR's
   null driver can't run its compositor without a DRM-lease display). Windows can use SteamVR's null driver.
6. **Deploy target:** the mod's install path, the log path, the lock file location.

## Headsets

Pick the headset in the dashboard or with `irisify machine add ... --headset <profile>`. Profiles live in
`controllers/profiles/` and carry the controller type, the real component list, display numbers (pixels per degree)
and host requirements. Supported now: Steam Frame, Valve Index, and Touch/WMR bindings. Quest (Link, Air Link,
Virtual Desktop, ALVR) is planned: the profile and the adb link exist, and the streaming-specific checks are marked
TODO in `tools/irisify/preflight.py`.

## One writer per target

Every deploy takes the target's lock (`irisify deploy` does it). A feature worker never deploys to a `headset` or
`game-host`. It uses `irisify verify-branch` on a `rig` machine, which takes the rig lock and puts the integration
build back afterwards.
