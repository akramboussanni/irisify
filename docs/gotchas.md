# Gotchas (symptom → cause → fix)

| Symptom | Cause | Fix |
|---|---|---|
| No patch applied at all | `PatchAll` threw on one bad target | `SafePatcher` (class by class); read the `failed:` list |
| "IL Compile Error" in one transpiler | a replaced instruction took its branch label | edit `opcode`/`operand` in place, or `MoveLabelsFrom` |
| Patch target not found on an interface method | explicit implementations are named `IFace.Method` | `SafePatcher.Explicit(type, "IFace", "Method")`; `irisify patchcheck` |
| Start screen never reaches the menu | a reflection serializer hit a `const`/readonly in the settings class | keep non-settings out of it; skip `IsLiteral`/`IsInitOnly` |
| Hands track, no button works | Steam Input forced on for the game → desktop-game panel holds focus | Disable Steam Input for the game; `irisify doctor input-focus` |
| A new default-on feature is still off | the saved settings file wins | settings migration |
| Movement freezes with a handheld menu open | the game's UI input group sets a movement lock | release the lock while the handheld UI is up |
| Remote `pgrep -f` kills the wrong thing / matches itself | the remote shell's own command line matches | anchor on `^[A-Z]:.*Game\.exe`, kill by PID |
| Inline script breaks over ssh | nested quoting | pipe a script to `bash -s` (the SSH link does) |
| `._*` files on the Linux side | macOS tar/rsync AppleDouble | `COPYFILE_DISABLE=1` (the SSH link sets it) |
| SteamVR null driver fails on Linux | compositor needs a DRM-lease display | Monado + OpenComposite (`tools/rig/monado.sh`) |
| Screenshot paths look like `Z:\home\…` | Proton path | the importer keeps the file name only |
| Frame streaming: GPU rejected | no H.265 encode in Fedora's Mesa | RPM Fusion `mesa-*-freeworld` |
| Frame adapter never set up | Flatpak Steam | native Steam |
