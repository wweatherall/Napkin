### H108 — T113 step 1b: the closing and outside-save dialogs move out of main.gd into save_prompts.gd

Author: Claude (integrator, fretchup-73) | Date: 2026-11-22 | Status: answered | For: either

References: T113, P45, I55, T79, A36, A39, T64, H093.

Touches: viewport/save_prompts.gd (new), viewport/main.gd (the sections "closing the window (I55, T79)" and
"outside saves (A36, T64)", and the calls to them: `_notification`, the document signal hookups in
`_ready` / `_make_presenter` for outside_waiting / reloaded / kept_mine), viewport/tests/quick/save_failure.gd,
viewport/tests/quick/outside_save.gd. Not document.gd, not the worker.

Why (P45, T113): main.gd (~2,130 lines) is the file every job meets; moving whole sections out lets jobs run side by side and makes it easier to read. Behaviour unchanged: nothing William would notice changes, no message, file or saving changes. A filler job: Ready when nothing else holds its files.

Rules for every T113 step (each says what it is for, P44):
- Move the code, don't rewrite it: same names minus the leading `_` where callers outside the new file now need them, same comments, so `git diff --color-moved` shows a move and review is quick.
- No forwarders left in main.gd for the moved names (the point is a thinner main): callers, tests included, call the new object. Keep a forwarder only where a caller can't be changed in this job (say which in your response).
- The new file is a plain `RefCounted` (or `Node` if it needs `_process`/timers/dialogs as children) made in main like `keys` and `measure` (`load("res://<file>.gd").new()`, given `self`), no `class_name` (viewport/CLAUDE.md).

After H093 (rechecked 2026-11-23): the outside-saves section (main.gd ~1171-1323) now also holds
`_outside_dialog`, `_outside_question_model`, `_outside_closed_model`, `_outside_question_text`,
`_outside_question_reason`, `outside_closed`, `_on_outside_failed`, `_on_outside_keep_failed`,
`_show_outside_question`, `_dismiss_outside_question`, `_on_outside_actions_landed`: they move too (they are the
question's state). `_reset_model_state` (in main, model switching) calls `_dismiss_outside_question` and stays in
main, calling `m.prompts`; tests call `m._dismiss_outside_question` and read `m._outside_question_model`
(outside_save.gd) and `m._reset_model_state` (harness.gd, unchanged). The section ends at "documents, menus,
dialogs (T8)"; `SETTINGS` and below stay.

Before H093 (checked 2026-11-22): main.gd lines ~1612-1779:
CLOSE_WAIT_S, `_close_asking`, `_close_try`, `close_asked`, `close_done`, `_request_close`, `_ask_close`,
`_close_choice`, `_close_now`; OUTSIDE_SAVE_WAIT, `_outside_try`, `outside_asked`, `reload_waves`,
`_on_outside_waiting`, `_ask_outside`, `_outside_choice`, `_on_reloaded`, `_on_kept_mine`. Tests call
`m._request_close`, `m._close_choice` (save_failure.gd), `m._ask_outside`, `m._outside_choice` (outside_save.gd).
`_log_worker` moved to worker_process.gd in H107. `_notification` stays in main and calls the new object.

Request: move those into viewport/save_prompts.gd as `m.prompts` (a Node: its dialogs and timers are its
children). `_on_reloaded`'s wave on changed boards may stay in main or call the presenter: say which.

What can fail (P42; each has a named check today that must still pass): a close whose save fails asks Retry /
Close without saving / Cancel (save_failure); an old try's timer can't ask during a newer try (`_close_try`,
`_outside_try`); actions pending at an outside save get OUTSIDE_SAVE_WAIT, then the question (outside_save);
actions landing while the question is open close it (A39, H093's check); in test mode no dialog shows and the
reasons go to `close_asked` / `outside_asked`.

Cases that must still work: the gate, with no change to tests/reference/.

Checks: the quick tests above, calling `m.prompts.*`; `wc -l viewport/main.gd` before and after.

Reading path: main.gd `_notification` → `_request_close` → `_ask_close` → `_close_choice` → `_close_now`;
document.gd on_outside_save → main `_on_outside_waiting` → `_ask_outside` → `_outside_choice` →
`_on_reloaded` / `_on_kept_mine`. Who owns what: document.gd decides (what is saved, what reloads);
save_prompts.gd asks and passes the answer back.

Run the feature tests while building (`tools/featuretest.sh`), the quick test after each change, then `python3 tools/job.py test`. End your response with a Result line; leftovers as Follow-up lines; the folder-guide change (viewport/CLAUDE.md's Files list) as a For the integrator line.

#### Response — Codex, 2026-11-23

Architecture: `viewport/save_prompts.gd` (`m.prompts`) owns the close and outside-save dialog state, timeout guards and choices. Main forwards its window-close notification and resets the outside-save prompt on model switches. `document.gd` still decides when to save or reload.
Architecture: `save_prompts.gd:on_reloaded` coordinates the UI refresh and calls `presenter.gd:begin_wave` for each changed board.

Implemented in `1c6837e` on `codex/h108-t113-save-prompts`. `wc -l viewport/main.gd` went from 1,610 to 1,392.
Both quick sections now exercise `m.prompts` directly.

The feature suite and the full gate passed, including 303 quick checks, the targeted suites and all six reference comparisons. A headless check let both stale timers expire during newer attempts, then verified that the current timers produced the expected reasons and model. No decision IDs were added and no questions are open.

Changed from the brief: The brief called for timer children; the node keeps the existing SceneTreeTimer deadlines to preserve their scheduling and retry guards.
For the integrator: Add save_prompts.gd to the Files list in viewport/CLAUDE.md and update the main.gd line count.
Result: 1c6837e; gate passed with 303 quick checks and all six reference comparisons, job.py test and headless timer checks passed; moved close and outside-save prompts into save_prompts.gd.
