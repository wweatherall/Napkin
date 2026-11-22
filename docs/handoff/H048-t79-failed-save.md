### H048 — T79: a failed save is forgotten

Author: Claude (integrator) | Date: 2026-11-22 | Status: open | For: Claude

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
