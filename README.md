# Irisify

Turn a flat PC game into a deep VR conversion with an AI agent, without the agent skipping the steps that matter.

Irisify packages three things, learned from a two-day Subnautica + Steam Frame project where several agent sessions
built a lot of good VR mechanics on a missing foundation:

1. **A skill** (`skill/`): a gated workflow for any coding agent. It covers intake, design, first boot on the real
   headset, a vertical slice, then breadth, and it carries the design process, controller knowledge, comfort and
   immersion reviews and the lessons behind them.
2. **A toolkit** (`bin/irisify`, Python 3.8+, stdlib only): machines and links (SSH, adb, local), platform and
   input-focus doctors, controller detection with binding and prompt generation, tag-based test suites on a
   headset-free rig, locked and stamped deploys, an integrator for parallel agents, and gates that refuse to move on
   without evidence.
3. **A dashboard** (`dashboard/`): a self-hosted web app where the human sees builds, every test case, the
   screenshots, comfort over time, which build each device runs, open issues and who owns them, and what's left to
   check in the headset.

Start with [`docs/lessons.md`](docs/lessons.md). It's the root-cause analysis everything else comes from.

## Quick start

```bash
git clone <this repo> ~/irisify
```

```bash
export PATH="$HOME/irisify/bin:$PATH"
```

In the mod's repo:

```bash
irisify init --game "Subnautica" --appid 264710
```

```bash
irisify machine add fedora --roles game-host,rig --link ssh --host user@rig-laptop --headset frame_controller --game-dir "~/.local/share/Steam/steamapps/common/Subnautica"
```

```bash
irisify machine check && irisify doctor platform --machine fedora
```

```bash
irisify dashboard
```

Then open http://127.0.0.1:7420. To reach it from another device on your tailnet, add `--host 0.0.0.0`. It has no
login, so only do that on a private network.

At any point, `irisify status` prints the phase, which gates pass, and the next action.

## How an agent uses it, end to end

1. **Load the skill.** Point the agent at `skill/SKILL.md`. For Claude Code, copy or symlink `skill/` into
   `~/.claude/skills/irisify`. Other agents: put SKILL.md in their instructions. It's plain Markdown.
2. **Setup:** `irisify machine add` for each machine (dev, game host, rig, headset), then `irisify machine check`.
   Steps that need the human (sudo, a password, Tailscale sign-in, developer mode on a headset) show as "you" with
   the exact command to copy. The agent runs the rest.
3. **Intake:** detect first (`irisify controllers detect --machine <m>`, `doctor platform`), then ask only what a
   tool can't answer. The dashboard's Intake page shows the questions with a recommendation each, and "You decide"
   records the recommendation.
4. **Platform preflight and first boot (hard gate):** the user launches the game in VR on the real headset and
   presses a button. Then `irisify gate first-boot --log LogOutput.log --build <id>` checks for all patch classes
   applied, a button DOWN event, and a matching build id. Nothing else runs before this passes.
5. **Design:** fill in `design/` (templates come from `irisify init`): physical sketch, interactions, the control
   scheme in `design/controls.json`, body map, information placement, comfort plan, reviews, test plan. Then:
   ```bash
   irisify controllers lint design/controls.json design/interactions.json
   ```
   ```bash
   irisify controllers bindings design/controls.json --out <mod>/StreamingAssets/SteamVR
   ```
   ```bash
   irisify controllers prompts design/controls.json --out <mod>/prompts
   ```
   The user signs off the design decisions on the dashboard.
6. **Vertical slice:** one mechanic end to end with its scenario green, then a human feel check and sign-off.
7. **Breadth:** `irisify fanout` (it refuses until the gates pass). Workers use branches and
   `irisify verify-branch <ref> <suite> --machine <rig>`. The integrator runs `irisify integrate`, which merges,
   builds, stamps, deploys to the rig and runs the smoke suite.
8. **Test after every change:** `irisify suite run auto` (smoke, plus what the diff touches, plus recent failures and
   flaky tests). Before the headset: `irisify suite run pre-headset`. The agent reviews every new screenshot
   (`irisify shots review …`).
9. **Ready for headset:** `irisify deploy --machine <headset>` (integration branch only, clean tree, under a lock).
   The dashboard's Headset checklist lists what only the human can judge, plus their own open complaints in their
   words.
10. **Feedback loop:** every complaint changes a design artifact first, adds the check that would have caught it,
    and becomes a lesson if it could happen in another game.

## Suites

Tests are scenarios described in `scenarios/*.json` (owner, tags, files they touch, what they cover, what they can't
cover, screenshot moments with questions). Suites pick from them, so you don't run everything every time:

| Suite | What | When |
|---|---|---|
| `smoke` | boot, input, one mechanic per area | after every deploy |
| `auto` | smoke + scenarios whose files changed since the last green build + recent failures and flaky ones | after every change (the default) |
| `changed` / `regression` | the two halves of `auto` | |
| area suites (`locomotion`, `body`, `interaction`, `building`, `vehicles`, `ui`, `comfort`) | by tag | working on one area |
| `pre-headset` | smoke + comfort + UI + `headset-critical` | before the human puts the headset on |
| `full` | everything, cheap first | before a release |
| `nightly` | everything shuffled with a logged seed, then again in order | catches state leaking between tests |
| `flaky-hunt --scenario X` | X between every other test | an intermittent bug |

Plan a suite with `irisify suite plan <name>`, which shows each test and why it's included. Run it with
`irisify suite run <name>`, or from the Builds page.

## Architecture

```
your mod repo
├── design/                 the nine design artifacts (controls.json generates bindings + prompts)
├── scenarios/*.json        test metadata          suites/*.json   tag-based suites
└── .irisify/               state the CLI, the agent and the dashboard share (JSON / JSON lines)
    machines.json  machines-status.json  preflight.json  intake.json  signoffs.json
    deploys.jsonl  issues.jsonl  activity.jsonl  shot-reviews.json  runs/<run>/{run.json,shots/}

irisify (this repo)
├── skill/                  SKILL.md + references/ + templates/design/
├── tools/irisify/          the CLI: machines, doctor, controllers, suites, runner, results, workflow, deploy
├── tools/rig/              runs on the rig machine: rigclient.py, monado.sh, null-driver.sh, launch-proton.sh, stop.sh
├── controllers/profiles/   frame_controller (read from SteamVR's own profile), knuckles, oculus_touch, holographic, generic
├── adapters/unity-bepinex/ in-game half: SafePatcher, BuildStamp, InputFocusDiag, InputClaims, SettingsMigration, rig host
├── dashboard/              server.py (stdlib) + static/index.html
├── intake/questions.json   the question bank
└── examples/subnautica/    the project this came from: scenarios, controls, machines, project config
```

Data flow: the in-game adapter writes `results.jsonl` and screenshots on the rig. `irisify suite run` drives it
through `rigclient.py` over SSH, then `irisify sync` pulls the results into `.irisify/runs/`. The dashboard reads
`.irisify/`. Gates read the same files, so the agent and the human always see the same evidence.

## Steam Frame notes

- Controller type `frame_controller` (HMD `frame_hmd`). It's not a Touch layout: the left controller has a D-pad,
  View and a bumper, and the right has A/B/X/Y, Menu and a bumper. Grips are analog. The profile in
  `controllers/profiles/frame_controller.json` was read from SteamVR's driver on the test laptop.
- **Steam Input must be off for the game** on whichever machine runs it, or SteamVR never gives the game input focus.
  `irisify doctor input-focus --machine <m>` checks it.
- On a Linux streaming host you need: native Steam (not Flatpak), kernel 7.2+, H.265 encode (Fedora: RPM Fusion
  `mesa-*-freeworld`), and `cap_sys_nice` on `vrcompositor-launcher`. `irisify doctor platform` checks all of these.

## Status

- **Verified here:** the CLI, suites, importer, gates and dashboard against the real Subnautica rig results (imported
  read-only), the controller generator (it regenerates the shipped Frame binding except four touch-dpad move
  bindings that were dropped on purpose), `machine check` and `doctor platform` against the real laptop over
  Tailscale, and 19 unit tests (`python3 -m unittest discover tests`), including the rig client against a fake game.
- **Not verified:** `suite run`, `deploy`, `integrate` and `verify-branch` against a live rig, because the running
  Subnautica rig was left untouched. The C# adapter templates are generalised from code that ran in SubmersedVR, but
  these copies haven't been compiled. Quest support is profile and adb only, and its streaming checks are still TODO.
