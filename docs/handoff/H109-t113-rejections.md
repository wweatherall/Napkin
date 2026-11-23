### H109 — T113 step 2: what a rejection takes with it moves to document.gd, and main's document pass-throughs go

Author: Claude (integrator, fretchup-73) | Date: 2026-11-22 | Status: queued (after H096, H094) | For: either

References: T113, P45, T16, Q7, A31.

Touches: viewport/document.gd, viewport/test_document.gd, viewport/main.gd (the section "rejections take what
built on them (T16, Q7)"; the pass-throughs `_op_of`, `remove_ops`, `remove_op`, `_restore_counters`,
`_consumed_rects`, `can_redo`), viewport/keys.gd, viewport/tests/harness.gd, viewport/tests/suites/breath.gd,
viewport/tests/quick/undo.gd, viewport/tests/quick/worker.gd, viewport/tests/quick/outside_save.gd,
viewport/tests/quick/save_failure.gd (only the renamed calls). Not
presenter.gd's waves.

Why (P45, T113): main.gd (~2,130 lines) is the file every job meets; moving whole sections out lets jobs run side by side and makes it easier to read. Behaviour unchanged: nothing William would notice changes, no message, file or saving changes. A filler job: Ready when nothing else holds its files.

Rules for every T113 step (each says what it is for, P44):
- Move the code, don't rewrite it: same names minus the leading `_` where callers outside the new file now need them, same comments, so `git diff --color-moved` shows a move and review is quick.
- No forwarders left in main.gd for the moved names (the point is a thinner main): callers, tests included, call the new object. Keep a forwarder only where a caller can't be changed in this job (say which in your response).
- The new file is a plain `RefCounted` (or `Node` if it needs `_process`/timers/dialogs as children) made in main like `keys` and `measure` (`load("res://<file>.gd").new()`, given `self`), no `class_name` (viewport/CLAUDE.md).

Today (checked 2026-11-22): main.gd ~1257-1342 keeps REJECT_WINDOW_MS, `_rejected`, `last_reject_note`, and
`_op_refs` (static), `_op_makes`, `_op_touches`, `_on_rejected(o, w, drop_now)`. Which earlier rejection an op
joins (by the ids it refers to, or a board named in FreeCAD's message), the ids and boards a rejection collects and
its note are reasoning about ops, not drawing; only the wave lines (`w["state"]`, `w["dependent"]`,
`w["root"]`, `op_waves`) and `drop_now` are main's/the presenter's. `redo()` and `undo()` already go through
document.gd (`take_redo`, `at_undo_floor`) and stay in main (they draw).

Request: document.gd gets the rejection bookkeeping as a function with no wave in it, e.g.
`reject(op_id, message, now_ms, still_playing: Callable) -> {root, joined: bool, note}` (shape yours), owning
`_rejected` and REJECT_WINDOW_MS; main's `_on_rejected` keeps only the wave and `drop_now` lines around it. The
pass-throughs listed go; callers use `m.doc.*`.

Cases that must still work: the rejecttest suite and the quick test's rejection steps; the gate with no change
to tests/reference/.

Checks (new, headless, the point of moving it: it can now be tested without a window), in test_document.gd: an
op rejected alone is its own root with its note; a later op whose plane is on the rejected op's board joins it
("(and 1 action that built on it)"); one naming the board in FreeCAD's message joins it; an independent op
doesn't; after REJECT_WINDOW_MS an old root no longer collects (unless still playing).

Reading path: main.gd `_on_synced` / `_on_worker` (where rejections arrive) → `_on_rejected` → `_op_refs`,
`_op_makes`, `_op_touches` → presenter.gd's wave states → `_on_wave_rejected_done`.

Run the feature tests while building (`tools/featuretest.sh`), the quick test after each change, then `python3 tools/job.py test`. End your response with a Result line; leftovers as Follow-up lines; the folder-guide change (viewport/CLAUDE.md's Files list) as a For the integrator line.
