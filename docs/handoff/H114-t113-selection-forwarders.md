### H114 — T113 step 4d: main.gd's selection pass-throughs go; callers use m.sel

Author: Claude (integrator, fretchup-73) | Date: 2026-11-22 | Status: queued (after H101) | For: either

References: T113, P45, T41, A33b.

Touches: viewport/main.gd (the one-line forwarders under "selection and context": `unit_of` … `unit_tris`, about
18), viewport/keys.gd, viewport/tool_context.gd, viewport/presenter.gd, viewport/inference.gd,
viewport/test_tool_context.gd, viewport/tests/quick/*.gd that call them (selection, hide, assembly,
assembly_row, linked, properties, undo). Not selection.gd's behaviour.

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
