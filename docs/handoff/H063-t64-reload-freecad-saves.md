### H063 — T64: watch the model file and reload FreeCAD's saves, with a wave

Author: Claude (integrator, fretchup-73) | Date: 2026-11-22 | Status: answered | For: Claude

References: A36 (William's call, 2026-11-22: what happens when FreeCAD saves while actions are pending), Q19
(decided: watch, reload, wave, undo stops at the FreeCAD change), A25 (journal adoption, undo floor; the worker
already reloads a file replaced on disk: Session.disk_sig / file_sig), A32 and H062 (save generations: build on
them), T65 (the re-apply offer: next, not this job), W01-W09 (the wave), CLOSE_WAIT_S (the same kind of wait),
A35 (PROTOCOL_VERSION).

Touches: worker/session.py, worker/serve.py, a new worker/test_outside_save.py (and worker/scenario/NN_outside_save.py,
new, if it fits), viewport/document.gd, viewport/main.gd (small: the dialog and the reload's wave), viewport/test_document.gd,
a quick-test step (viewport/tests/quick/outside_save.gd, new; if the
quick-test or scenario registries' pinned lists must change, H046 (Codex) has those files: give the lines as "For the
integrator:" lines), docs/decision-log.md (A36's and T64's "Where in the code",
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

Response — Claude (worker, branch `claude/h063-t64-reload-freecad-saves`), 2026-11-22: built T64 as A36 says.

1. Watch: the worker stats each open model's file every WATCH_S (0.25 s) on its select loop's timeout (one stat
   per model; nothing reads the file unless its mtime/size moved). A change counts once it has held still for one
   look (FreeCAD half-way through writing isn't reloaded) and its sha256 isn't the bytes Session last read or wrote
   (a touch or a copy back isn't an outside save). Every save also looks just before writing, without the wait,
   so even an autosave due in the same moment never goes over FreeCAD's file. The window gets `outside_save`.
2. Nothing pending: the window sends `reload` at once; the worker reopens the file, writes bodies.json and says
   which boards changed (box, volume, area, wood, hiding) and which went; the window takes its ops, puts the
   wave over the changed boards and says so in the status line; undo stops there (the journal now keeps the
   floor, so it stops there in the next session too).
3. Pending: the worker holds the model (no autosave) as soon as it sees the save; the window waits for its syncs
   to land (OUTSIDE_SAVE_WAIT, 10 s, viewport/main.gd, a Tunables row) and then reloads. Not in time: the dialog
   "FreeCAD saved this model while Shop Sketch was busy", Use FreeCAD's version / Keep Shop Sketch's, naming why
   (didn't land, the worker hasn't answered: may be stuck, the worker stopped), logged in worker.log.
   Use FreeCAD's version reloads (the late sync answer then counts for nothing). Keep Shop Sketch's copies
   FreeCAD's file to `<model>.freecad-<YYYYmmdd-HHMMSS>.FCStd` and saves ours over it.
   Which actions are "dropped": every action the file's revision didn't hold, landed in time or not. FreeCAD
   saves the revision it had open (its ShopSketchRev), so actions Shop Sketch saved after FreeCAD opened the file
   are missing from it too. The worker remembers each revision's op list (the last 50; else the .prev journal;
   else none, so all are dropped). They go in the journal as `dropped: [{op, after_rev, at}]` for T65.
4. Autosave resumes after the reload or the choice. Closing (flush, bye, quit) while held, with actions unsaved,
   keeps both the same way as Keep Shop Sketch's; with nothing unsaved FreeCAD's file just stays.
   A worker that stops before the reload: the journal got `outside_sha256` the moment the save was seen, so a new
   worker opens FreeCAD's file as an outside edit (A25) instead of taking it for a save of ours that stopped part
   way (A32's "journal newer" rule would otherwise put our .prev pair back and move FreeCAD's file to .unmatched).
   The window sends no sync to a new worker while the choice is open.

Checks: worker/test_outside_save.py (25: nothing pending, landed in time, each choice's files on disk and the
journal's dropped list, no autosave over the outside save, one copy per choice, the copy-aside name, a flush while
held, an older revision saved in FreeCAD, an undo since that revision, a new worker after a crash);
viewport/test_document.gd (+19: waiting, the reload's ops with actions drawn meanwhile on top, the forced reload,
keep_mine, no sync to a worker back after a crash); quick-test section outside_save (an earlier revision of the open
model put back on disk: reloaded, the board it brings back waves, the delete is dropped, undo stops; the dialog's
reason and Keep Shop Sketch's copy). PROTOCOL_VERSION 5 on both sides.

Architecture: docs/protocol.md, worker → window event `{"cmd": "outside_save", "model", "rev" (the file's ShopSketchRev), "unsaved": bool}`: FreeCAD saved the open model (A36); the worker holds it (no autosave writes over the file) until the window answers.
Architecture: docs/protocol.md, new request `{"cmd": "reload", "model", "outdir", "seq"}` → the open reply's fields with `"cmd": "reload"`, plus `changed` / `removed` (board ids whose box, volume, area, wood or hiding differ; gone), `dropped` (ops the file didn't hold) and `outdir` (bodies.json written there).
Architecture: docs/protocol.md, new request `{"cmd": "keep_mine", "model", "outdir"?, "seq"}` → `{"ok", "cmd": "keep_mine", "model", "aside", "rev"}`: FreeCAD's file copied to `<model>.freecad-<YYYYmmdd-HHMMSS>.FCStd` (`-2`... if taken), then Shop Sketch's saved over it. flush / bye / quit of a held model with unsaved actions does the same; their `saved` entries carry `aside`. PROTOCOL_VERSION 5.
Architecture: docs/protocol.md, journal fields: `floor` (undo stops here: ops before it can't be taken back, A25; kept across saves and sessions), `dropped` ([{op, after_rev, at}]: actions an outside save didn't hold, for T65), `outside_sha256` (written the moment an outside save is seen; opening a file with that sha opens it external instead of recovering, A32).
Architecture: ARCHITECTURE.md § saving: serve.py watches each owned model's file every WATCH_S (0.25 s, on the select loop: one stat per model); a changed (mtime, size) must hold still for one look and differ from the bytes Session last read or wrote (`file_sha`) to count; save_pending also looks just before each save (no settling) and skips a held model, so no autosave goes over FreeCAD's save. `Session.reload_outside()` reopens the file, keeps the ops the file's revision held (`rev_counts`, else the .prev journal, else none), moves the rest to `dropped`, sets the undo floor there and writes the journal naming FreeCAD's file. `Session.save()` no longer resets the undo floor to 0.
Architecture: ARCHITECTURE.md, viewport document controller (document.gd, A31): owns the outside-save state (`outside`, `outside_seq`, `dropped`): `on_outside_save` reloads at once or emits `outside_waiting`; the idle branch of `on_sync_reply` sends the reload once everything has landed; while a reload is out, syncs wait (`in_flight`) and actions drawn meanwhile go on top of the reloaded ops; `on_link_up` sends no sync while the choice is open. Signals `outside_waiting`, `reloaded`, `kept_mine`. main.gd: `OUTSIDE_SAVE_WAIT`, the dialog (`_ask_outside`, `_outside_choice`), `_log_worker` (a line in worker.log), `_on_reloaded` (clears the presenter's remembered states, waves over `changed`).
Architecture: ARCHITECTURE.md module table, `worker/session.py` row: add outside saves (A36): `outside_sig`, `same_bytes`, `mark_outside`, `reload_outside`, `copy_outside_aside`, `aside_name`; `worker/serve.py` row: the file watch and the `reload` / `keep_mine` commands.

Follow-up: log.py add can't add a Tunables row (no kind for it), so OUTSIDE_SAVE_WAIT's and WATCH_S's rows were added to the Tunables table by hand.
Follow-up: Session.sync() rebuilds from the op list when an undo goes past FreeCAD's 20 steps, and that rebuild loses a FreeCAD change below the undo floor (it starts from an empty document); it should start from the file the floor came from. Before T64 this was already true after opening an externally edited file.
Follow-up: recover_generation() takes a FreeCAD save of an older revision for a save of ours that stopped part way (A32's "journal newer than the file" rule) when no worker saw it happen (e.g. FreeCAD saved while Shop Sketch was closed); FreeCAD's file goes to .unmatched (not lost, but not what opens). Ask William whether that rule should stay.
Follow-up: after a crash during an outside-save wait, "Keep Shop Sketch's" on the new worker saves FreeCAD's file plus the window's actions on top (the new worker loaded FreeCAD's file); the aside copy is still made.
For the integrator: worker/CLAUDE.md "Sync, undo, saving" still says "An outside edit sets an undo floor; merging is stage 2 (A25, Q19)": make it "The worker watches the open model's file; FreeCAD's save is reloaded with the wave, or kept beside ours (A36, T64); the journal keeps the undo floor and dropped actions." (the guide wasn't in this job's Touches).
For the integrator: H046 has the quick-test registry: the new section viewport/tests/quick/outside_save.gd isn't pinned in QUICK_LANES (it joins the shortest lane by itself; it takes about 1.2 s).

Result: 50c5a66; worker/test_outside_save.py 25/25, test_document.gd 89/89, quick test 216/216 (section outside_save), gate passed; the worker watches the open model file and holds it on a FreeCAD save; the window reloads it with the wave, or after OUTSIDE_SAVE_WAIT asks Use FreeCAD's version / Keep Shop Sketch's (FreeCAD's file copied aside); dropped actions and the undo floor kept in the journal (A36)
