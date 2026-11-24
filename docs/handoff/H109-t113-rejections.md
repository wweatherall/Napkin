### H109 — T113 step 2: what a rejection takes with it moves to document.gd, and main's document pass-throughs go

Author: Claude (integrator, fretchup-73) | Date: 2026-11-22 | Status: open | For: either

References: T113, P45, T16, Q7, A31.

Touches: viewport/document.gd, viewport/test_document.gd, viewport/main.gd (the section "rejections take what
built on them (T16, Q7)" (`REJECT_WINDOW_MS`, `_rejected`, `_op_refs`, `_op_makes`, `_op_touches`,
`_on_rejected`); `_on_wave_rejected_done`; the pass-throughs `_op_of`, `remove_ops`, `remove_op`,
`_restore_counters`, `_consumed_rects`, `can_redo` and their call sites in `_on_op_removed`,
`_rebuild_rect_drafts`, `_on_synced`), viewport/tests/harness.gd, viewport/tests/suites/breath.gd,
viewport/tests/quick/undo.gd, viewport/tests/quick/worker.gd, viewport/tests/quick/outside_save.gd,
viewport/tests/quick/save_failure.gd (only the renamed calls). Not presenter.gd's waves, and not
viewport/tests/quick/reject.gd (`last_reject_note` stays on main beside `reject_note`).

Why (P45, T113): main.gd (1,342 lines) is the file every job meets; moving whole sections out lets jobs run side by side and makes it easier to read. Behaviour unchanged: nothing William would notice changes, no message, file or saving changes. A filler job: Ready when nothing else holds its files.

Rules for every T113 step (each says what it is for, P44):
- Move the code, don't rewrite it: same names minus the leading `_` where callers outside the new file now need them, same comments, so `git diff --color-moved` shows a move and review is quick.
- No forwarders left in main.gd for the moved names (the point is a thinner main): callers, tests included, call the new object. Keep a forwarder only where a caller can't be changed in this job (say which in your response).
- The new file is a plain `RefCounted` (or `Node` if it needs `_process`/timers/dialogs as children) made in main like `keys` and `measure` (`load("res://<file>.gd").new()`, given `self`), no `class_name` (viewport/CLAUDE.md).

Today (rechecked 2026-11-23 after H094, H096, H097, H122): main.gd 938–1022 keeps `REJECT_WINDOW_MS`, `_rejected`,
`last_reject_note`, `_op_of`, `_op_refs` (static, including `tg.region.get("lines", [])` from H096), `_op_makes`,
`_op_touches`, and `_on_rejected(o, w, drop_now)`. `_on_wave_rejected_done` (929–936) also reads `_rejected` to
remove `[oid] + _rejected[oid]["deps"]` via `remove_ops`/`remove_op`. Which earlier rejection an op joins (by the
ids it refers to, or a board named in FreeCAD's message), the ids and boards a rejection collects and its note are
reasoning about ops, not drawing; only the wave lines (`w["state"]`, `w["dependent"]`, `w["root"]`, `op_waves`),
`reject_note` / `last_reject_note` and `drop_now` are main's/the presenter's. The six document pass-throughs live
at main.gd 734 (`can_redo`), 756 (`remove_ops`), 760 (`remove_op`), 776 (`_restore_counters`), 780
(`_consumed_rects`) and 947 (`_op_of`); `redo()` and `undo()` already go through document.gd (`take_redo`,
`at_undo_floor`) and stay in main (they draw).

Request: document.gd gets the rejection bookkeeping as a function with no wave in it, e.g.
`reject(op_id, message, now_ms, still_playing: Callable) -> {root, joined: bool, note}` (shape yours) plus a
helper for `_on_wave_rejected_done` (e.g. `rejected_deps(oid)` or `rejected_ids(oid)`) so main doesn't touch
`doc._rejected`; document.gd owns `_rejected` (cleared in `reset()`) and `REJECT_WINDOW_MS`. Main's `_on_rejected`
keeps only the wave, `reject_note` / `last_reject_note` and `drop_now` lines around it. The six pass-throughs
listed go; callers in main and tests use `doc.*` / `m.doc.*`.

Cases that must still work: the rejecttest suite and the quick test's rejection steps; the gate with no change
to tests/reference/.

Checks (new, headless, the point of moving it: it can now be tested without a window), in test_document.gd: an
op rejected alone is its own root with its note; a later op whose plane is on the rejected op's board joins it
("(and 1 action that built on it)"); one naming the board in FreeCAD's message joins it; an independent op
doesn't; after REJECT_WINDOW_MS an old root no longer collects (unless still playing).

Reading path: main.gd `_on_synced` / `_on_worker` (where rejections arrive) → `_on_rejected` → `_op_refs`,
`_op_makes`, `_op_touches` → presenter.gd's wave states → `_on_wave_rejected_done`.

Run the feature tests while building (`tools/featuretest.sh`), the quick test after each change, then `python3 tools/job.py test`. End your response with a Result line; leftovers as Follow-up lines; the folder-guide change (viewport/CLAUDE.md's Files list) as a For the integrator line.
