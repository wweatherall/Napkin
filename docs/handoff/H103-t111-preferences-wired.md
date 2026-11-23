### H103 — T111 step 2: preferences wired in: ⌘, opens the file, saving it applies the feel tunables and the default units

Author: Claude (integrator, fretchup-74) | Date: 2026-11-22 | Status: queued (after H052, H102) | For: either

References: I63, I62, T111, H102 (viewport/preferences.gd), H052 (the units' names and the model's units).

Touches: viewport/main.gd (the app menu item, the poll timer, TRACKPAD_PX / ZOOM_STEP read from preferences,
the status line), viewport/inference.gd (GRID, SNAP_PX, EDGE_PX, INFER_DEG, RELEASE_DEG read from
preferences), viewport/tools/tool.gd (DRAG_PX, HOLD_MS), viewport/units.gd only if H052 left no way to check a
units choice, viewport/preferences.gd (the units check), a quick section (tests/quick/preferences.gd), the
tests that read the constants (tests/quick/trackpad.gd, tests/suites/gesture.gd: `Main.TRACKPAD_PX`).

To be written in full when H052 is merged (its names for the units decide the `units` section), with its "What
can fail" list. The shape, from I63: Shop Sketch > Preferences… (⌘,, NativeMenu's application menu) writes the
file with the current values if missing (`write_defaults`) and opens it (`OS.shell_open`); a 0.5 s timer calls
`changed_on_disk` and on a change `load_from`, applies the values, and says `Preferences: <KEY> <value>, ...`
(or the first problem) in the status bar; in test mode the file is never read (the built-ins hold); the default
units are used where I62 says (a new model, or one with none saved), never changing an open model's units.
