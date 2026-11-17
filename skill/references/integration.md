# Parallel agents: one integrator, one build, one deploy

## Roles
- **Orchestrator / integrator** (one): talks to the user, owns `design/`, owns the integration branch, merges,
  builds, deploys, runs the suite, routes failures. Only it deploys to a headset or game host.
- **Feature workers** (many): one branch each (`<prefix>/<area>`), cut from the integration branch. They write their
  own files, read the design, add scenarios for their features, and use `irisify verify-branch` on the rig. They never
  deploy to a headset, never merge other branches, and never edit the control scheme or body map (they propose changes
  in their notes).
- **Rig worker** (optional): owns the test rig code and scenarios, runs suites, routes failures with evidence.

## When to fan out
Only after the `first-boot`, `design` and `slice` gates (`irisify fanout` checks). Split by **concern first**
(input/controls, body, UI and readability, comfort, rig), then by game area. Cross-cutting concerns have exactly
one owner.

## Conventions (write them into the mod's `notes/conventions.md` before fan-out)
- One file per feature. Shared files get few-line edits only.
- Settings: a partial per area, a default from the preset, a migration when a default changes.
- Input: claim presses through the claim system, in the documented priority.
- Logging: `[Area] what happened` on every state change.
- Notes: `notes/<area>.md` with design, hook map, open questions and the playtest list.
- Commit messages say how the change was checked ("rig: holster_draw_stow PASS on 2556818" or "builds; not run").

## The integration loop (`irisify integrate`)
1. Fetch. For each ready branch, in the order in `.irisify/integrate.json`: merge into the integration branch.
   Stop on a conflict and route it to the branch owner.
2. Build. Stamp `build.json` (git describe, branch, time, merged branches).
3. Deploy to the rig (lock, install, unlock). Run the `smoke` suite, then the `full` suite.
4. Write the run to `.irisify/runs/<build>/`. The dashboard picks it up.
5. Route each failure to its owner (the scenario's `owner`), with check values, log lines, screenshots and the start
   state. Write it to `.irisify/issues.jsonl`.
6. If green and the user wants it: `irisify deploy --device <headset>`. It refuses unless the build is from the
   integration branch, the tree is clean, and the target's lock is free.

## Verifying a worker's branch (`irisify verify-branch <ref> <suite|scenarios>`)
A scratch worktree of `<ref>` with the rig branch merged in, built, deployed to the rig under its lock, the given
scenarios run. Afterwards the integration build goes back on. The owner's branch is never changed.
