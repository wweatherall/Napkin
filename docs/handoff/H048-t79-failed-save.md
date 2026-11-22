### H048 — T79: a failed save is forgotten

Author: Claude (integrator) | Date: 2026-11-22 | Status: answered | For: Claude

References: T79, A21 (the .FCStd is the model), A24 (the journal), A35 (protocol version), Q22/T19 (the save
indicator), T45; docs/protocol.md finding 5; worker/serve.py `save_pending`, `handle` (flush / bye / quit);
viewport/document.gd `on_saved`; viewport/main.gd the save indicator (~line 460) and `_shutdown_worker`.

Touches: worker/serve.py, worker/session.py (only if the save itself must report more), worker/test_serve.py,
viewport/document.gd, viewport/test_document.gd, viewport/main.gd (the save indicator and `_shutdown_worker` only),
a new viewport/tests/quick/save_failure.gd, docs/protocol.md, ARCHITECTURE.md (the saving / recovery section).
Not viewport/tools/* (H047 is reading them for the T88 spec), not tools/quicktest.sh, quick_runner.gd, harness.gd,
quick/worker.gd (H045). If H045's worker-cleanup work needs `_shutdown_worker` too, the two of you say so in chat
before either edits it.

Request: today `save_pending` logs a save failure, drops the pending save, and flush / bye / quit still answer ok;
the window shows "Saved" only when a `saved` event comes, but nothing tells it a save failed, and closing waits a
bounded time instead of for the saved revision. Make a failed save stay pending (retried on the next sync or
flush), send the window a `save_failed` event (model, rev, error), and make flush / bye / quit answer with what
was saved (and not ok when the latest revision couldn't be). The window shows the failure and, on closing, waits
for the latest revision to be saved, or says it couldn't be. Bump the protocol version (A35) and document the
event. Ask William before building, one question at a time with a recommendation, and log each answer: what the
indicator says on a failure (recommend "Couldn't save: <reason>", in the save indicator's place, staying until a
save lands) and what closing does when the save keeps failing (recommend: a dialog with Retry / Close without
saving / Cancel). Checks: a scenario or serve test that makes a save fail (a read-only folder) and sees the event,
the retry and the not-ok flush; a document test for the window's side; a quick section for the indicator.

Response — Claude (worker session), 2026-11-22: done on `claude/h048-failed-save`, commit 2a624aa.
- William's answers, logged: I-new-1 (the indicator says "Couldn't save: <reason>" in Saved's place, red, until a
  save lands) and I-new-2 (closing waits for the latest revision; if it can't be saved: Retry / Close without saving /
  Cancel). New tunable CLOSE_WAIT_S = 10 s (no answer from FreeCAD in that long asks too).
- Worker: a failed save stays pending; the timer skips it, the next sync / flush / bye / quit retries it; each failure
  sends the owner `save_failed {model, rev, error}`; flush / bye / quit carry `saved` / `failed` lists, ok only when
  nothing failed (quit still stops: the window asked first). `flush` takes an optional `model`. `Session.save` rolls
  the revision back on failure (the retry saves the same rev) and raises "the folder <name> is read-only" instead of
  FreeCAD's "Failed to open file". Protocol version 2 → 3 (both sides).
- Window: `document.gd` gains `save_error`, `on_save_failed`, `unsaved`, `begin_close` / `cancel_close` /
  `on_flush_reply` and signals `close_ready` / `close_blocked`; `main.gd` turns off auto-accept quit and handles
  `NOTIFICATION_WM_CLOSE_REQUEST` (`_request_close`, `_ask_close` with the native alert, `_close_choice`,
  `_close_now`); `_shutdown_worker` runs once. `_shutdown_worker` itself is otherwise unchanged (H045: no clash).
- Verified: `python3 worker/test_serve.py` 20/20 (7 new); `test_document.gd` 65/65 (15 new); `tools/quicktest.sh`
  208 passed, 0 failed (new section `save_failure`, joined lane 2); `tools/fulltest.sh` exit 0.
- Architecture sections changed: "Protocol at a glance" (flush, bye, save_failed rows) and "Files, persistence and
  recovery" (failed saves; closing). docs/protocol.md: lifecycle, events, version, finding 5 marked fixed.
- Outside the Touches list: docs/decision-log.md (I-new-1, I-new-2, the tunable) and one line of worker/CLAUDE.md
  (the serve test's count and what it covers).
- Not tested by hand: the native close dialog itself (test mode records the question instead of showing it). Worth
  a look by William: put a model in a read-only folder, draw, close the window.
