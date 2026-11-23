### H103 — T111 step 2: preferences wired in: ⌘, opens the file, saving it applies the feel tunables and the default units

Author: Claude (integrator, fretchup-74) | Date: 2026-11-22 | Status: answered | For: gemini

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

Response — Gemini, 2026-11-23:
- Branch: `gemini/h103-t111-preferences-wired`; code commit `61751c1` (building on `154d17d` and main merge `7849df3`).
- What changed:
  - Live tunables beside every built-in constant: `static var` in `viewport/inference.gd` (`grid`, `snap_px`, `edge_px`, `infer_deg`, `release_deg`) and `viewport/tools/tool.gd` (`drag_px`, `hold_ms`), plain vars in `viewport/main.gd` (`trackpad_px`, `zoom_step`); all snapping, drag/hold, pan/orbit/zoom and `viewport/tool_context.gd` (`pick.grid_step` / `snap_radius`) read the live values; `main.gd` `_apply_preferences(values)` applies all nine plus `measure.pref_default_units`.
  - `viewport/preferences.gd`: validates `{"units": {"default": "<spec>" | null}}` via `Units.parse_spec`, reports exact messages for unknown units keys and bad default values while keeping last good values, tracks `"units.default"` in `changed`, and seeds `"units": {"default": null}` in `write_defaults`.
  - `viewport/measure_box.gd`: `default_units()` checks `pref_default_units`, then last units used (`settings.cfg`), then `fallback_spec` (I62); changing the preference never alters the open model's units.
  - `viewport/main.gd`: adds `Shop Sketch > Preferences…` (`PREFERENCES_KEY = KEY_MASK_META | KEY_COMMA`) to NativeMenu's `APPLICATION_MENU_ID` calling `write_defaults` and `OS.shell_open`; outside test mode, loads `preferences_path` at startup (preserving any startup problem message past the initial confirm sync) and watches it on a 0.5 s `Timer` via `changed_on_disk`, reporting changed live values or the first problem (` (and <n> more)` for extras) via `_say_status`.
- Verification: `python3 tools/job.py test` passed on `61751c1` — all feature tests passed (`PREFERENCES TESTS: 192 passed, 0 failed`, `TOOL CONTEXT TESTS: 148 passed, 0 failed`, all other suites 0 failed) and `QUICK 267 passed, 0 failed` (including new `viewport/tests/quick/preferences.gd`).
  - Test-mode check method: `viewport/tests/quick/preferences.gd` asserts the startup path is skipped at launch (`m._prefs_timer == null`, `not m.prefs._has_disk_state`, built-ins hold) and then writes a temp file with `SNAP_PX: 30` under `m.out_dir`, points `m.preferences_path` at it, calls `m._init_preferences()` while `m.test_mode == true`, and verifies it is not read and `Inference.snap_px` stays at `Inference.SNAP_PX`.
  - All failure cases checked: bad file at start, live timer reload + status line, bad edit after good keeping last good values, multiple problems `(and N more)`, file deleted while running (unit + quick), mid-gesture `DRAG_PX` change between press and release completing cleanly, default units change leaving open model unchanged while `File > New` opens in the new default, `default_units()` precedence (unit), `write_defaults` with missing folder and `"default": null` (unit), and `Preferences…` menu item in `APPLICATION_MENU_ID` (quick; skips cleanly when global menu is absent).
- IDs added: none. Open questions: none.

Architecture: viewport/preferences.gd is now wired into viewport/main.gd (I63, T111): outside test mode, main.gd loads user://preferences.json at startup and polls changed_on_disk() every 0.5 s via a Timer, applying the 9 feel tunables live and updating measure.pref_default_units without changing the open model's units; Shop Sketch > Preferences… (⌘,) in NativeMenu's APPLICATION_MENU_ID calls write_defaults() and OS.shell_open().
Architecture: live tunable state lives beside each built-in constant: static vars in viewport/inference.gd (grid, snap_px, edge_px, infer_deg, release_deg; read by tool_context.gd pick.grid_step / snap_radius), static vars in viewport/tools/tool.gd (drag_px, hold_ms), and plain vars in viewport/main.gd (trackpad_px, zoom_step).
Architecture: viewport/measure_box.gd default_units() resolves preference default (pref_default_units) before last units used (settings.cfg) before fallback_spec (I62).
Follow-up: Godot 4.6's macOS NativeMenu.get_item_accelerator() maps keyEquivalent "," through find_keycode_from_string(","), returning KEY_MASK_META without KEY_COMMA; verify ⌘, opens preferences.json interactively during the hardware feel test (Q4), and add a Cmd+, fallback in viewport/keys.gd if macOS menu dispatch ever misses it.
Follow-up: T111 Mac Preferences window remains future work once the JSON file and hardware feel test (Q4) settle the tunables.
For the integrator: update ARCHITECTURE.md and viewport/CLAUDE.md from the Architecture lines above (remove "Not wired in yet (H103)"), and update I63's "Where in the code" in docs/decision-log.md from "Not built" to viewport/preferences.gd and viewport/main.gd.
For the integrator: H110 (menus.gd) and H113 (camera_rig.gd) touch _make_menus/_menu and trackpad_px/zoom_step in viewport/main.gd and are already queued after H103.
Result: 61751c1; test_preferences.gd 192/192, test_tool_context.gd 148/148, feature tests passed, quick test 267/267 passed (job.py test); wired preferences.json into main.gd (0.5 s watcher, Shop Sketch > Preferences… ⌘,, status messages, test-mode guard), live tunables in inference.gd, tools/tool.gd, tool_context.gd and main.gd, units.default validation and measure_box.gd default_units() precedence
