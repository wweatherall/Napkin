### H110 — T113 step 3: the menus move out of main.gd into menus.gd

Author: Claude (integrator, fretchup-73) | Date: 2026-11-22 | Status: open | For: either

References: T113, P45, A30, A34, I62.

Touches: viewport/menus.gd (new), viewport/main.gd (`_make_menus`, `_build_units_menu`, `_update_units_menu`,
`_on_units_menu`, `set_units`, `_update_menu_checks`, `_menu`, `_build_materials_menu`, `_on_wood_menu`,
`_file_dialog`, and their calls), viewport/keys.gd, viewport/measure_box.gd, viewport/test_units.gd,
viewport/tests/harness.gd, viewport/tests/quick/hide.gd, linked.gd, registry.gd, undo.gd, units.gd. Not
`switch_model`, `new_window`, `_last_model`, `_remember_model`, `_out_for`, `_set_title` (the model's files
stay in main).

Why (P45, T113): main.gd (~2,130 lines) is the file every job meets; moving whole sections out lets jobs run side by side and makes it easier to read. Behaviour unchanged: nothing William would notice changes, no message, file or saving changes. A filler job: Ready when nothing else holds its files.

Rules for every T113 step (each says what it is for, P44):
- Move the code, don't rewrite it: same names minus the leading `_` where callers outside the new file now need them, same comments, so `git diff --color-moved` shows a move and review is quick.
- No forwarders left in main.gd for the moved names (the point is a thinner main): callers, tests included, call the new object. Keep a forwarder only where a caller can't be changed in this job (say which in your response).
- The new file is a plain `RefCounted` (or `Node` if it needs `_process`/timers/dialogs as children) made in main like `keys` and `measure` (`load("res://<file>.gd").new()`, given `self`), no `class_name` (viewport/CLAUDE.md).

Today (checked 2026-11-22; H103 adds a Preferences item, re-read after it merges): `_menu(tag)` is the one
handler every menu item calls; keys.gd, harness.gd and several quick tests call `m._menu`; measure_box.gd and
test_units.gd call `m._update_units_menu` / `m.set_units`; the Tools menu is built from `tool_list` (A34).

Request: menus.gd as `m.menus` builds the menu bar and handles every item (`m.menus.run(tag)` for `_menu`);
what an item does stays where it is today (it calls main or the object that owns it), so only building and
dispatch move. `set_units` moves only if it is about the menu; if it sets the model's units, it stays and the
menu calls it: say which.

Cases that must still work: every menu item and its key (quick test registry checks the Tools menu), File >
New / Open / New Window, the units menu's check marks, Edit > Undo / Redo / Delete; the gate with no change to
tests/reference/.

Checks: the quick tests listed, calling `m.menus.*`; `wc -l viewport/main.gd` before and after.

Run the feature tests while building (`tools/featuretest.sh`), the quick test after each change, then `python3 tools/job.py test`. End your response with a Result line; leftovers as Follow-up lines; the folder-guide change (viewport/CLAUDE.md's Files list) as a For the integrator line.

#### Response — Codex, 2026-11-23

Branch: `codex/h110-t113-menus`.

`main.gd` went from 2,182 to 2,035 lines. `m.menus` builds the native menus, updates check marks, and dispatches menu, toolbar and keyboard commands. `set_units` stays in main's model-facing API and delegates to MeasureBox, which applies and persists the model's units. The read-only `m._menus` compatibility getter serves `tests/quick/models.gd` and `tests/suites/shell.gd`, both outside Touches.

Verified: feature tests and the gate passed (295 quick checks, six recorded suites matched, reference files unchanged). The Tools quick test reads the native menu, and the Units quick test checks the selected format and rounding. A separate macOS smoke test verified the native File New / Open / New Window and Edit Undo / Redo / Delete callback bindings and accelerators. The smoke test inspected the bindings without driving the system dialogs. Its native menu shutdown warnings also reproduced on the branch baseline.

Decision IDs added: none. Open questions: none.

Architecture: Add `viewport/menus.gd` (`m.menus`, RefCounted) to the module map. It owns the native menu RIDs, the duplicate-command filter, check marks and New/Open dialog presentation. Toolbar callbacks and matching keyboard shortcuts share `m.menus.run(tag)`. The Tools menu still derives from the tool registry. Main owns model switching, new-window creation and launching preferences. MeasureBox owns display units and asks the menus to refresh their check marks. Appearance owns the wood library and Paint command. Main still owns wood rendering and grain rotation, and menus.gd builds and checks the Wood menu.
For the integrator: Add `menus.gd` to the Files list in `viewport/CLAUDE.md`. Update the main, keys and appearance entries there and the corresponding module map entries to name `m.menus` as the menu owner.
Follow-up: When the model quick test and shell suite can be edited, have them read the menu RIDs from `m.menus` and remove main's compatibility getter.
