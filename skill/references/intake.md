# Intake: grill the user, with judgment

The user knows things no tool can detect: how they play, what they'll tolerate, what "immersive" means to them, and
whether the headset is on their head right now. They also don't want to answer what a tool could have told you.
Good intake is **detect first, ask what matters, recommend always, stop early**.

The question bank is `intake/questions.json`. The dashboard's **Intake** page renders it, with detected values
filled in, and writes the answers to `.irisify/intake.json`. An agent without the dashboard asks the same questions
in chat and writes the same file with `irisify intake set key=value`.

## 1. Detect before asking

Run these first. Each answer they give removes a question.

| Run | Answers |
|---|---|
| `irisify rig status` | is a game host reachable (SSH over Tailscale/LAN), OS, GPU |
| `irisify controllers detect --host <host>` | headset model, controller type, input profile, runtime (SteamVR / OpenXR runtime), finger tracking |
| `irisify doctor platform --host <host>` | Steam packaging, kernel, encoder, Proton, Steam Input for the game |
| `um scan` / file fingerprints | engine, version, mod loaders, anti-cheat |
| the game's save and settings folders | whether the user has existing saves (back them up), existing mod settings |
| existing VR mods for the game | what's already solved |

If detection gives an answer, show it to the user as a fact ("Detected: Steam Frame, `frame_controller`, streamed
from Fedora via Steam Link") and ask only if it looks wrong.

## 2. Which questions to ask

Ask a question only if **both** are true:
- the answer changes a decision you'd otherwise make differently (a default, the order of work, a design form), and
- you can't detect it or infer it from what the user already said.

Questions are ranked:

- **Blocking** (ask now, before any design): how they play (seated, standing, both), how they connect to the game
  (streamed or native, which machine runs it), whether the agent may run the game itself (and on which machine),
  whether existing saves must never be touched, and their motion-sickness tolerance.
- **Shaping** (ask in the design review, with a recommendation): realism vs convenience for specific mechanics
  (manual reload, reach for food), comfort defaults (snap vs smooth turn, vignette), which mechanics they care about
  most (order of work), and how much flat UI they'll accept.
- **Taste** (don't ask, decide and note it; the user overrides on the dashboard): colours, label wording, haptic
  strengths, numeric tuning.

At most **four questions per round**. Each question comes with your recommended answer and one line on why it
matters. A user who says "you decide" gets your recommendation, recorded as `decided_by: agent`.

## 3. How to ask (the grill)

- **Be concrete.** Not "what comfort settings do you want?" but "Smooth turning makes some people sick. Snap turn 30°
  (recommended) or smooth?"
- **Challenge vague goals.** "Make it immersive" → "Immersive like Half-Life: Alyx (ammo shown on the magazine, but
  reloading is still two quick motions), or like a sim (every step done by hand)? Most people find full sims tiring
  after an hour."
- **Surface contradictions.** "You want no floating UI and you play seated with a lot of crafting. Crafting menus will
  sit at the machine. Is that OK, or do you want a tablet you hold?"
- **Ask about failure, not only success.** "If an option you like is off by default and you never find it, would
  you rather I ship more on by default and you turn things off?"
- **Name the cost.** "Physical ladders means a hand-over-hand climb every time. Fine for 3 m, tiring for 30 m. Climb
  long ones by hand too, or with an optional assist?"
- **Don't ask twice.** Read `.irisify/intake.json` and the MODLOG first.
- **Don't ask what's yours to decide.** Implementation choices, file layouts, tool choices and numeric tuning are
  yours.

## 4. When to stop

Stop asking when every blocking question has an answer and the shaping questions have recommendations recorded. Build
the vertical slice, then ask about *feel*, with the headset on, which is the only time those answers are reliable.

## 5. Later rounds

- **After the vertical slice:** a feel check of 3–5 specific questions tied to what they just did ("Did the ladder climb
  feel 1:1? Too slow, right, too fast?").
- **After every playtest:** collect free feedback first, then classify it (`design-process.md`, feedback loop). Ask a
  follow-up only when a complaint is ambiguous ("'swimming is weird': direction, speed, or effort?").
- **Before anything outward-facing** (publishing, pushing, posting to a mod site): always ask.

## 6. Recording

`.irisify/intake.json`:

```json
{
  "answers": {
    "play_posture": {"value": "both", "source": "user", "at": "2026-11-16T21:03:00Z"},
    "headset": {"value": "Steam Frame", "source": "detected", "evidence": "vrserver.txt: frame_hmd"},
    "turn": {"value": "snap30", "source": "agent", "why": "user said 'you decide'; low sickness tolerance"}
  },
  "open": ["manual_reload"]
}
```

Every design decision that depends on an answer cites its key, so changing the answer shows what to revisit.
