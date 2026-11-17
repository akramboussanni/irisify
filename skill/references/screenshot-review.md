# Screenshot review

On Subnautica the rig's numbers passed while the screenshots showed an invisible wrist computer, a floating gauge in
the middle of the view and the inside of the chest (`lessons.md` A7). Screenshots are evidence only when someone
looks at them with a question.

## Every scenario names its moments

```json
"shots": [
  {"moment": "wrist-glance", "question": "Is the wrist computer readable at full contrast?", "expect": "visible"},
  {"moment": "look-down-55", "question": "Is the body below the eyes, hands on the controllers, holsters visible?"}
]
```

The adapter saves `<scenario>-<moment>.png` (one eye, at eye resolution where possible). The runner records the
moment and question with the build id.

## Agent review (required before "ready for headset")

For each new or changed shot (the dashboard pairs it with the same moment in the previous build):
1. Answer the question in one line, from the image, not from the code.
2. Then check, regardless of the question:
   - anything floating that has a physical home (`immersion.md`)?
   - text at a lens edge or cut off?
   - the feature under test visible at all?
   - anything inside the camera (body, hull, cockpit)?
   - two copies of the same information?
3. Mark the shot `ok`, `flag` (with what's wrong) or `rig` (the capture angle or setup is wrong, not the mod). Write
   it with `irisify shots review <run> <moment> ok|flag|rig "<answer>"`.

A flagged shot opens an issue routed to the feature's owner.

## Human review

The dashboard's gallery shows each shot with its question and the agent's answer. The human marks readability and
feel questions. Screenshots are flat, single-eye captures, not what the lenses show, so anything about text size or
depth stays on the headset checklist until checked in the headset.

## Showing the user

Show screenshots to the user; don't just describe them. After a playtest-driven fix, put the before/after pair in
front of them (dashboard or chat). It's the fastest way for them to say "yes, that" or "no, not that".
