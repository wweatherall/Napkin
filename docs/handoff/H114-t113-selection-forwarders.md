### H114 — T113 step 4d: main.gd's selection pass-throughs go; callers use m.sel

Author: Claude (integrator, fretchup-73) | Date: 2026-11-22 | Status: answered | For: either

References: T113, P45, T41, A33b.

Touches: viewport/main.gd (the one-line forwarders under "selection and context": `unit_of`, `in_context`, `edit_blocked`,
`context_assembly`, `enter_context_of`, `leave_context`, `set_selection`, `hidden_boards`, `is_hidden`,
`hide_selected`, `unhide`, `toggle_hidden_geometry`, `make_assembly`, `_siblings_of`, `_linked_op`, `unit_tris`), viewport/keys.gd, viewport/menus.gd (`run`: `m.make_assembly`, added by H110 after this brief), viewport/tool_context.gd, viewport/presenter.gd, viewport/inference.gd,
viewport/test_tool_context.gd, the quick tests that call them: viewport/tests/quick/selection.gd,
viewport/tests/quick/hide.gd, viewport/tests/quick/assembly.gd, viewport/tests/quick/assembly_row.gd,
viewport/tests/quick/linked.gd, viewport/tests/quick/properties.gd, viewport/tests/quick/undo.gd. Not selection.gd's behaviour.

Why (P45, T113): main.gd (~2,130 lines) is the file every job meets; moving whole sections out lets jobs run side by side and makes it easier to read. Behaviour unchanged: nothing William would notice changes, no message, file or saving changes. A filler job: Ready when nothing else holds its files.

Rules for every T113 step (each says what it is for, P44):
- Move the code, don't rewrite it: same names minus the leading `_` where callers outside the new file now need them, same comments, so `git diff --color-moved` shows a move and review is quick.
- No forwarders left in main.gd for the moved names (the point is a thinner main): callers, tests included, call the new object. Keep a forwarder only where a caller can't be changed in this job (say which in your response).
- The new file is a plain `RefCounted` (or `Node` if it needs `_process`/timers/dialogs as children) made in main like `keys` and `measure` (`load("res://<file>.gd").new()`, given `self`), no `class_name` (viewport/CLAUDE.md).

Today (checked 2026-11-22): main.gd ~809-826 forwards `unit_of`, `in_context`, `edit_blocked`,
`context_assembly`, `enter_context_of`, `leave_context`, `set_selection`, `hidden_boards`, `is_hidden`,
`hide_selected`, `unhide`, `toggle_hidden_geometry`, `make_assembly`, `_siblings_of`, `_linked_op`,
`unit_tris` to selection.gd or the presenter. Production code mostly calls `m.sel` already (keys.gd calls
`m.set_selection`); the tests call the forwarders. H101 removes the ones Move's migration left; this does the rest.

Request: delete them; every caller uses `m.sel.*` (or `m.pres.unit_tris`). A forwarder that is also a signal
target or a menu action stays: say which.

Cases that must still work: the gate with no change to tests/reference/.

Checks: test_tool_context.gd, test_selection.gd and the quick tests listed; `grep -n "func unit_of" viewport/main.gd`
finds nothing; `wc -l viewport/main.gd` before and after.

Run the feature tests while building (`tools/featuretest.sh`), the quick test after each change, then `python3 tools/job.py test`. End your response with a Result line; leftovers as Follow-up lines; the folder-guide change (viewport/CLAUDE.md's Files list) as a For the integrator line.

#### Response — Gemini (2026-11-23)

- **Branch / commit:** `gemini/h114-t113-selection-forwarders` @ `c9236ec`
- **What changed:** Removed all 16 selection/presenter method forwarders (`unit_of`, `in_context`, `edit_blocked`, `context_assembly`, `enter_context_of`, `leave_context`, `set_selection`, `hidden_boards`, `is_hidden`, `hide_selected`, `unhide`, `toggle_hidden_geometry`, `make_assembly`, `_siblings_of`, `_linked_op`, `unit_tris`) from `viewport/main.gd` (`wc -l`: 1803 → 1783 lines, -20 lines). Updated callers in `viewport/main.gd` (`_update_tip`, `_show_siblings`, `_reset_model_state`), `viewport/keys.gd`, `viewport/menus.gd` (`run`: all selection menu actions, so no forwarder had to stay), and the 7 quick tests (`selection.gd`, `hide.gd`, `assembly.gd`, `assembly_row.gd`, `linked.gd`, `properties.gd`, `undo.gd`) to call `m.sel.*` directly. `tool_context.gd`, `presenter.gd`, `inference.gd`, and `test_tool_context.gd` already called `sel.*` / `pres.unit_tris` directly.
- **Verified:**
  - `grep -n "func unit_of" viewport/main.gd` → empty; grep across `viewport/`, `tools/`, `tests/` finds no remaining `m.<forwarder>` calls.
  - `tools/featuretest.sh`: all 35 suites passed (`SELECTION TESTS: 47 passed, 0 failed`, `TOOL CONTEXT TESTS: 148 passed, 0 failed`).
  - `python3 tools/job.py test` on clean `c9236ec`: passed (`QUICK 295 passed, 0 failed`, all 35 feature suites passed).
  - `tools/fulltest.sh`: passed (all 6 recorded suites match `tests/reference/` as `same`, targeted suites and all 35 feature suites passed).
- **IDs added:** none.
- **Open questions:** none.

Architecture: ARCHITECTURE.md (`viewport/main.gd` and `viewport/presenter.gd` rows): remove the note that Main forwards `unit_tris` and record that Main's 16 selection/presenter method forwarders were removed (callers use `m.sel.*` and `m.pres.unit_tris`; only selection property forwarders remain on Main).
For the integrator: Update `viewport/CLAUDE.md` Files list (`selection.gd` and `presenter.gd` rows) so it says main.gd no longer forwards the selection/presenter methods (`unit_of`, `set_selection`, `hide_selected`, `unit_tris`, etc.) and callers use `m.sel.*` / `m.pres.unit_tris` (property forwarders like `m.selection` and `m.context` still remain).
Result: c9236ec; quicktest 295/295, fulltest 6/6 reference same, 35/35 feature tests (selection 47/47, tool_context 148/148); removed all 16 selection/presenter method forwarders from viewport/main.gd (1803 -> 1783 lines) and updated main.gd, keys.gd, menus.gd and 7 quick tests to call m.sel.* directly
