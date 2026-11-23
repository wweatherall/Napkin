### H087 — A38: a rebuild keeps FreeCAD's edits (the floor copy)

Author: Claude (integrator, fretchup-73) | Date: 2026-11-22 | Status: open | For: gemini

References: A38 (William's call, 2026-11-22), A23 (sync), A32 (save generations), A36 and T64 (outside saves),
T10 (rebuild past 20 undo steps), the H063 follow-up in docs/follow-ups.md (clear that line in your last commit).

Touches: worker/session.py, a new worker/test_floor_copy.py. Not serve.py, the viewport, the journal's existing
fields (add one, below), ARCHITECTURE.md or the folder guides: write what changes as "Architecture:" lines and
guide changes as "For the integrator:" lines.

The bug, today: `Session.sync` (session.py) calls `_rebuild(ops)` when the ops to take back go below
`session_base` or past FreeCAD's undo depth (`n_undo > self.doc.UndoCount`). `_rebuild` starts from
`_new_doc()` (an empty document) and replays every op. When `undo_floor > 0` the first `undo_floor` ops came from
a file FreeCAD changed (`_open_existing` with `external`, or `reload_outside`), so replaying them from empty
loses FreeCAD's change. (`sync` already refuses `k < undo_floor`; the loss is a rebuild with `k >= undo_floor`.)

Request (A38):
1. The floor copy: `<model>.floor.FCStd` beside the model (add `"floor_file"` to `generation()`'s dict, beside
   the other names). Write it with `self.doc.saveCopy(...)`, atomically (write a temp name, then `os.replace`),
   at the two moments the floor is set from a FreeCAD change: in `_open_existing` when `self.external` is true
   (after `_load_file`, before any op is applied: the document then is exactly the floor), and in
   `reload_outside` right after `_load_file`. Record it in the journal as one new field, `"floor_copy":
   {"sha256": <of the copy>, "ops": <undo_floor>}`, written by `_journal`; a journal without it reads as no copy.
2. `_rebuild(ops)`: when `undo_floor == 0`, as today. When `undo_floor > 0` and the floor copy exists, its
   sha256 matches the journal's `floor_copy.sha256` and `floor_copy.ops == undo_floor`: open the copy as the
   live document (as `_load_file` does, but from the copy's path; closing the old document first), set
   `applied` to the first `undo_floor` entries of the current `applied` (they're what the copy holds), apply
   `ops[undo_floor:]`, and keep `undo_floor` and `session_base = undo_floor`. Saving must still write the model's
   own path: `save` uses `saveCopy` to `self.path` today, so check it stays that way and say so. Otherwise (no
   copy, or it doesn't match): raise OpError("can't undo past the FreeCAD edit: its copy is missing") and leave
   the document as it was, instead of rebuilding from empty.
3. A model never edited in FreeCAD writes no floor copy and rebuilds exactly as today.

Cases that must still work: every existing worker test (test_generations.py's undo-floor checks, the outside-save
tests, test_scenario.py), saving and recovery of the other generation files (A32), the journal's other fields
unchanged.

Checks (worker/test_floor_copy.py, run by freecadcmd like the other worker tests; `TESTDIR` for outputs):
- a model with 3 boards, saved; then changed outside Shop Sketch (open it with FreeCAD's API, add a cube with a
  label you can find, save); reopened in a Session: the floor copy exists and its sha matches the journal;
- then 25 new ops (more than FreeCAD's 20 undo steps), then `sync` back to the first 2 of those (a rebuild):
  the cube is still there and the boards are as expected;
- the same through `reload_outside` (an outside save while the session is open);
- the floor copy deleted (or its sha changed) and the same sync: OpError with the exact message, and the
  document unchanged;
- a model never edited outside: no floor copy file, and a rebuild past 20 steps works as today.

Reading path: session.py `Session.__init__` → `_open_existing` (how the floor and `session_base` are set from the
journal) → `reload_outside` (the other way the floor is set) → `_journal` (what's saved) → `sync` (when it
rebuilds) → `_rebuild` → `save` and `_write` (saving writes `self.path`). Who owns what: Session owns
the live document, `applied`, the floor and the journal; serve.py only calls `sync` and `save`; the floor copy is
Session's alone.

Worker rules to know (worker/CLAUDE.md, "FreeCAD rules"): `freecadcmd` passes the script as `sys.argv[1]` (paths
through environment variables); when a script raises, freecadcmd runs it a second time (read the first error).

Run the feature tests while building (`tools/featuretest.sh`), then `python3 tools/job.py test` (the quick
test). End your response with a Result line; leftovers as Follow-up lines; anything for the merge as For the
integrator lines.
