### H093 — Outside saves: a failed reload asks, a worker lost mid-reload reloads again, and a question the actions overtook closes (H092 findings 2 and 5, A39)

Author: Claude (integrator, fretchup-73) | Date: 2026-11-22 | Status: open | For: either

References: A36 and T64 (outside saves), A39 (William, 2026-11-22: when the pending actions land while the
question is open, FreeCAD's version is taken, the question closes and the window says so), H092 (the ultra
review: findings 2, 4 and 5; 4 is A39), the H063 follow-up in docs/follow-ups.md (a crash during an outside-save
wait; related, not this job).

Touches: viewport/document.gd (`on_reload_reply`, `on_link_up`), viewport/main.gd (the outside-saves section:
`_ask_outside`, `_outside_choice`, `_on_reloaded`, and one new signal handler), worker/session.py
(`reload_outside`), viewport/test_document.gd, viewport/tests/quick/outside_save.gd, worker/test_outside_save.py.
Not serve.py (the model stays held after a failed reload, which is right: the window now asks), not the save
code, not ARCHITECTURE.md (write `Architecture:` lines). Queued after H083 because it touches main.gd.

Today (each checked against the code, 2026-11-22):
- Finding 2. serve.py's `reload` runs `s.reload_outside()` before `held.pop(path)`. If it raises (FreeCAD's file
  won't open), the model stays held, so autosave skips it, and `hold()` told the window only once.
  document.gd `on_reload_reply` on an error clears `outside` and carries on syncing, so nothing ever asks.
  Autosave is silently off until flush, bye or quit. And `reload_outside` closes `self.doc` before
  `_load_file()`, so a failed load leaves the session on a closed document.
- Finding 5. document.gd `on_link_up` with `outside` pending sets `dirty` and `outside_seq = -1` and sends
  nothing. An idle window sent its reload at once, so the `OUTSIDE_SAVE_WAIT` timer never started. Nothing asks
  and nothing reloads; the next action's sync builds on FreeCAD's file, which A36 means to prevent.
- Finding 4 / A39. main.gd `_outside_choice` returns when `doc.outside` is empty, but the reload `on_sync_reply`
  sends once the actions land doesn't empty it: `send_reload` leaves `outside` set until the reply. So a
  "Keep Shop Sketch's" clicked after that reload went out sends `keep_mine` too. The worker has already taken
  FreeCAD's version (the reload came first), and the window then ignores the reload's reply (`send_keep_mine`
  moved `outside_seq` on), so the window and the worker disagree about the model. Only the Godot `ConfirmationDialog` path can be open while replies arrive. Check
  whether `DisplayServer.dialog_show` (the native path, on macOS) blocks the main loop while it's up, and say so
  in your response; if it doesn't, it needs the same handling.

Request:
1. A failed reload leaves the session as it was. In `Session.reload_outside`, nothing of the session changes
   (`doc`, `applied`, `undo_floor`, `session_base`, `dropped`, the floor copy, the journal) unless FreeCAD's file
   opened. FreeCAD's `App.openDocument` on a path that's already open may hand back that same document: check
   this in 1.1.4 before you choose how to open the new one while the old stays live (opening a temporary copy
   of the file first is one way), and say which way you took.
2. A failed reload asks. In document.gd `on_reload_reply`, on an error: `outside` stays set (don't clear it),
   `outside_seq = -1`, `in_flight = false`, and a new signal `outside_failed(error: String)` is emitted instead
   of `sync_failed`; syncs stay held as they are while `outside` is set. main.gd handles it by asking at once,
   the same two buttons and title as `_ask_outside`, with this text (exact):
   `"%s was saved in FreeCAD, but Shop Sketch couldn't open FreeCAD's save: %s.\n\nUse FreeCAD's version: try
   opening it again.\nKeep Shop Sketch's: FreeCAD's file is first copied aside as %s.freecad-<time>.FCStd."` %
   [file name, error, file stem]. In test mode, append `"couldn't open FreeCAD's save: " + error` to
   `outside_asked` instead of showing it. Log it with `_log_worker` as `_ask_outside` does.
3. A worker lost mid-reload reloads again. In `on_link_up`, when `outside` is set: if a reload was out
   (`outside_seq >= 0` before it's reset), send it again (`send_reload()`); otherwise (still waiting for the
   actions to land) mark `dirty` as today and emit `outside_waiting`, so main.gd's timer runs and asks.
4. A39: a question the actions overtook closes. main.gd keeps the open `ConfirmationDialog` in a variable. When
   `on_sync_reply` sends the reload while it is open, the dialog closes (freed, its buttons do nothing more:
   `_outside_choice` also returns when `doc.outside_seq >= 0`, a reload already out). When that reload lands,
   `_on_reloaded`'s status line gets `" (Shop Sketch's actions landed while you were deciding, so the question
   closed)"` appended. In test mode, where no dialog is shown, count the closes in a test variable
   (`outside_closed`, beside `outside_asked`).

Cases that must still work: every check in viewport/test_document.gd's outside-saves section, the quick test's
outside_save section, worker/test_outside_save.py (30 checks), the save-failure section; an outside save with
nothing pending reloads at once with no question; "Keep Shop Sketch's" before anything lands still keeps ours.

Checks:
- worker/test_outside_save.py: FreeCAD's save replaced with bytes that aren't a FreeCAD file (write garbage over
  the model while it's held), then `reload`: an error reply; the session's document is still open and its
  boards are as before; a `keep_mine` afterwards saves ours (FreeCAD's file copied aside).
- viewport/test_document.gd: a reload's error reply keeps `outside`, emits `outside_failed` with the error, sends
  nothing; a reload out, then `on_link_up`: the reload is sent again (a new seq); waiting (sync in flight, no
  reload out), then `on_link_up`: `outside_waiting` is emitted, `dirty` set, nothing sent.
- viewport/tests/quick/outside_save.gd: `outside_failed` puts the exact reason in `outside_asked`; the
  question open (`_ask_outside` in test mode), then the actions land and the reload goes out: `outside_closed`
  is 1, `_outside_choice("mine")` then sends no `keep_mine`, and the status line ends with the A39 text.

Reading path: serve.py `hold` → `outside` → the `reload` and `keep_mine` commands; session.py `reload_outside`
→ `_load_file`; document.gd `on_outside_save` → `send_reload` → `on_sync_reply` (where the reload is sent once
the actions land) → `on_reload_reply` → `on_link_up` → `send_keep_mine`; main.gd's outside-saves section
(`_on_outside_waiting`, `_ask_outside`, `_outside_choice`, `_on_reloaded`). Who owns what: the worker holds the
model and owns the session; document.gd owns `outside`, `outside_seq` and when to reload; main.gd owns the
question and the status line.

Run the feature tests while building (`tools/featuretest.sh`), then `python3 tools/job.py test`. End your
response with a Result line; leftovers as Follow-up lines; anything for the merge as For the integrator lines.
