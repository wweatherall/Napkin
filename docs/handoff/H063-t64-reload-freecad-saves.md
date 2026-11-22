### H063 — T64: watch the model file and reload FreeCAD's saves, with a wave

Author: Claude (integrator, fretchup-73) | Date: 2026-11-22 | Status: queued (after H062) | For: Claude

References: A36 (William's call, 2026-11-22: what happens when FreeCAD saves while actions are pending), Q19
(decided: watch, reload, wave, undo stops at the FreeCAD change), A25 (journal adoption, undo floor; the worker
already reloads a file replaced on disk: Session.disk_sig / file_sig), A32 and H062 (save generations: build on
them), T65 (the re-apply offer: next, not this job), W01-W09 (the wave), CLOSE_WAIT_S (the same kind of wait),
A35 (PROTOCOL_VERSION).

Touches: worker/session.py, worker/serve.py, a new worker/test_outside_save.py (and a worker/scenario step if it
fits), viewport/document.gd, viewport/main.gd (small: the dialog and the reload's wave), viewport/test_document.gd,
a quick-test step (viewport/tests/quick/, a new file), docs/decision-log.md (A36's and T64's "Where in the code",
a Tunables row with `log.py add`). Not docs/protocol.md or ARCHITECTURE.md (P28: the integrator's):
write what your change does to them as "Architecture:" lines in your response.

Request: build T64 as A36 says.
1. Watch: the worker notices when the model's file changes on disk and the change isn't its own save (not its rev,
   not its sha256), while the window is open, without waiting for the next sync (a cheap stat check on its
   select loop's timeout is enough; say what you chose). It tells the window (a new event).
2. Nothing pending: reload the file (as A25 does), show the changed boards with the wave, and undo stops at the
   FreeCAD change.
3. Actions pending: stop autosaving that model at once; wait up to OUTSIDE_SAVE_WAIT (10 s, a tunable) for them to
   land; then reload as in 2. If they don't land: the dialog "FreeCAD saved this model while Shop Sketch was busy"
   with "Use FreeCAD's version" (reload; the unfinished actions stay in the journal marked dropped, for T65) and
   "Keep Shop Sketch's" (copy FreeCAD's file aside as <model>.freecad-<time>.FCStd first, then save over it).
   Both versions always survive on disk. If the worker was stuck or crashed, log it in worker.log and say so in
   the dialog.
4. Autosave resumes once the choice is made (or after the reload in 2).
Checks: an outside save with nothing pending reloads and reports the changed bodies; one with pending actions that
land in time; one where they don't (each choice: files on disk afterwards, the journal's dropped actions); no
autosave writes over the outside save meanwhile; the copy-aside name; the quick-test step (an outside edit to the
open model, then the wave). Quick test, then the gate. Bump PROTOCOL_VERSION on both sides (A35). End your
response with a Result line; leftovers as Follow-up lines; anything for the merge as For the integrator lines.
