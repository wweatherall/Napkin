### H110 — T113 step 3: the menus move out of main.gd into menus.gd

Author: Claude (integrator, fretchup-73) | Date: 2026-11-22 | Status: queued (after H103, H101) | For: either

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
