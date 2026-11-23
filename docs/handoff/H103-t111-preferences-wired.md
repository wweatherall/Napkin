### H103 — T111 step 2: preferences wired in: ⌘, opens the file, saving it applies the feel tunables and the default units

Author: Claude (integrator, fretchup-74) | Date: 2026-11-22 | Status: open | For: gemini

References: I63 (preferences: a JSON file, the default units and the feel tunables, live), I62 (a model with no
units saved opens in the user's default, else the last units used), T111, H102 (viewport/preferences.gd, merged),
H052 (the units' specs, merged: `Units.parse_spec`, `Units.DEFAULT_SPEC`, measure_box.gd `default_units`).

Touches: viewport/main.gd (the app-menu item, the poll timer, applying values, the status line; TRACKPAD_PX /
ZOOM_STEP read live), viewport/inference.gd (GRID, SNAP_PX, EDGE_PX, INFER_DEG, RELEASE_DEG read live),
viewport/tools/tool.gd (DRAG_PX, HOLD_MS read live), viewport/tool_context.gd (`pick.grid_step` /
`snap_radius` answer the live values), viewport/measure_box.gd (`default_units`: the preference first),
viewport/preferences.gd (the `units` section's check, `write_defaults`'s units), viewport/test_preferences.gd,
viewport/test_tool_context.gd (only its grid/snap check, if the live values change what it compares), a new quick
section viewport/tests/quick/preferences.gd. Not the worker, not docs/protocol.md (nothing on the wire changes),
not ARCHITECTURE.md or the folder guides ("Architecture:" / "For the integrator:" lines).

Today (checked 2026-11-22, after H052 and H102): the tunables are constants: inference.gd `GRID`, `SNAP_PX`,
`EDGE_PX`, `INFER_DEG`, `RELEASE_DEG` (read in its snapping methods; main.gd keeps `GRID` / `SNAP_PX` aliases;
tool_context.gd `pick.grid_step()` / `snap_radius()` return them); tools/tool.gd `DRAG_PX`, `HOLD_MS`
(`press_moved`, `press_released`); main.gd `TRACKPAD_PX` (pan/orbit) and `ZOOM_STEP` (wheel zoom, and the
zoom-toward-cursor `log(ZOOM_STEP)`). main.gd makes one `Inference.new()` (`infer`). Tests read the constants
(`Main.TRACKPAD_PX` in tests/quick/trackpad.gd and tests/suites/gesture.gd; test_tool_context.gd's grid/snap
check). preferences.gd's `units` is kept as given (any Dictionary); `write_defaults` writes `"units": {}`.
measure_box.gd `default_units()` gives the last units used (settings.cfg `[units] last`), else `fallback_spec`.

Request:
1. Live values. Keep every constant (the built-in value; tests and the defaults read them) and add the value
   the code uses beside it: `static var` in inference.gd (`grid`, `snap_px`, `edge_px`, `infer_deg`,
   `release_deg`) and tools/tool.gd (`drag_px`, `hold_ms`), plain vars in main.gd (`trackpad_px`, `zoom_step`),
   each starting at its constant. Every place that reads a constant to snap, drag, pan or zoom reads the live
   value instead; `pick.grid_step` / `snap_radius` too. One function applies a tuning Dictionary to all of them
   (main.gd `_apply_preferences(values)`).
2. The units section: `{"units": {"default": "<spec>"}}`, a spec `Units.parse_spec` accepts (`in-frac:1/16`,
   `mm:1`, ...), or `null` for not set. preferences.gd checks it: an unknown key in `units`, problem
   `preferences.json: unknown units setting <key>`; a value that isn't a spec or null, the last good value
   stays, problem `preferences.json: units default must be a units setting like "in-frac:1/16" (got <value>)`.
   `write_defaults` writes `"units": {"default": null}` when none is set, so the key can be found. measure_box.gd
   `default_units()`: the preference's default if set, else the last units used, else the fallback (I62). A
   change of the default never changes the open model's units: it applies to the next new model, or one with
   none saved.
3. The menu: Shop Sketch > Preferences… with ⌘, (NativeMenu's application menu, `APPLICATION_MENU_ID`; on a
   system without a global menu, nothing). It calls `write_defaults` (a missing file is written with the
   current values) and opens the file (`OS.shell_open` of its global path).
4. Watching: outside test mode, at start `load_from("user://preferences.json")` and apply; then a 0.5 s Timer
   calls `changed_on_disk` and on a change `load_from` and apply. The status line (`_say_status`) after a load
   that changed something or found a problem: `Preferences: SNAP_PX 18, ZOOM_STEP 0.9` (the changed keys, the
   live values; `default units in-dec:0.01` for the units default), or, when there's a problem, the first one,
   plus ` (and <n> more)` if there are more. Nothing is said at start when the file is missing or all is well.
5. Test mode never reads user://preferences.json (the built-ins hold). The quick section points main at its own
   file under the test's out folder (a `preferences_path` var, set before the timer starts) to drive the live path.

What can fail (a file the user edits while the app runs):
- A change while a gesture is under way (a drag, a press being timed): the new values apply at once and the
  gesture finishes without error. Check (quick): change DRAG_PX between press and release; the action completes.
- A bad file at start: the built-ins hold, and the status line says the problem. Check (quick): start the
  section with a broken file.
- A bad edit after a good one: the last good values stay in use (not the built-ins). Check (quick): SNAP_PX 18,
  then a broken file: SNAP_PX still 18, the problem in the status line.
- The file deleted while running: the last good values stay, nothing said. Check (unit, test_preferences.gd, if
  not already there).
- The default units changed while a model is open: its units don't change; a File > New model opens in the new
  default. Check (quick, or measure_box unit test).
- ⌘, with the folder or file missing: the file is written with the current values (`"default": null`), then
  opened. Check: `write_defaults` output, including the units key (unit); the menu item exists with ⌘,
  (quick, where NativeMenu has a global menu; else the check says SKIP).
- Test mode: a run with a user://preferences.json present doesn't read it. Check: a test puts one with SNAP_PX 30
  in a test's user dir equivalent, or asserts the startup path is skipped in test mode (say which).

Checks: the cases above; each live value equals its constant at start; `_apply_preferences` sets each of the nine
(read back through the live vars and `pick.grid_step` / `snap_radius`); the units default's check (good spec,
null, an unknown key, a bad value); `default_units` order (preference, last used, fallback).

Reading path: preferences.gd (all of it) → inference.gd's snapping methods (where each constant is read) →
tools/tool.gd `press_started` / `press_moved` / `press_released` → main.gd's pan/orbit/zoom input and
`_make_tools` (where `infer` is made) → tool_context.gd `PickCapability.grid_step` / `snap_radius` →
measure_box.gd `setup` / `default_units` → main.gd `_say_status` and the Wood menu (how a NativeMenu item is
added). Who owns what: preferences.gd reads and checks the file; main.gd decides when, applies the values and
talks; inference.gd, tool.gd and measure_box.gd only use what they're given.

Run `tools/featuretest.sh` and `tools/quicktest.sh` while building, then `python3 tools/job.py test`. End your
response with a Result line; leftovers as Follow-up lines; anything for the merge as For the integrator lines.
