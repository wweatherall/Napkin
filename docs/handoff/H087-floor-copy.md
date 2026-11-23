### H087 — A38: a rebuild keeps FreeCAD's edits (the floor copy)

Author: Claude (integrator, fretchup-73) | Date: 2026-11-22 | Status: answered | For: gemini

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

### Response — Gemini (worker, gemini-cedar), 2026-11-22

Branch `gemini/h087-floor-copy`, implementation commit `60b429c` (branched from `main` `3120b76`).

Implemented A38 in `worker/session.py` and added `worker/test_floor_copy.py` (and cleared the H063 rebuild follow-up in `docs/follow-ups.md`):
- Added `"floor_file": base + ".floor" + ext` (`<model>.floor.FCStd`) to `generation()`.
- Added `Session._write_floor_copy()` to write `<model>.floor.FCStd` atomically via `self.doc.saveCopy(<model>.floor.tmp.FCStd)` + `os.replace(...)` and record `self.floor_copy = {"sha256": <hex>, "ops": self.undo_floor}` in `_open_existing()` when `self.external` is true and in `reload_outside()` right after `_load_file()`. On normal opens (`not self.external`), `self.floor_copy` is read from the journal's `floor_copy` field (or `None` if absent). `Session._journal()` writes `"floor_copy"` only when `self.floor_copy` is set; all existing journal fields are unchanged.
- Updated `Session._load_file(path=None)` to accept an explicit file path, and updated `Session._rebuild(ops)` so `undo_floor == 0` stays unchanged while `undo_floor > 0` verifies `<model>.floor.FCStd` exists and matches `floor_copy` (`sha256` and `ops == undo_floor`), closes the old document, opens `<model>.floor.FCStd`, clears undos, keeps `applied[:undo_floor]`, `undo_floor`, and `session_base = undo_floor`, and replays `ops[undo_floor:]`. When the floor copy is missing, modified, or unrecorded in the journal, `_rebuild` raises `OpError("can't undo past the FreeCAD edit: its copy is missing")` before closing or modifying the live document.
- Checked `Session.save()` and `_write()`: saving continues to call `self.doc.saveCopy(g["saving_file"])` and rename to `g["file"]` (`self.path`), using `self.path` for `write_gui_document`, so saving after a floor-copy rebuild writes the model's own path and leaves `<model>.floor.FCStd` byte-for-byte untouched (verified in `worker/test_floor_copy.py`).

Verified with `tools/featuretest.sh` and `python3 tools/job.py test` on `60b429c`: `FLOOR COPY TESTS: 21 passed, 0 failed` (covering external edit on reopen, 25 ops + rebuild, saving after rebuild, rebuild across restart, `reload_outside` + 25 ops + rebuild, deleted/tampered floor copy and legacy journal without `floor_copy` raising the exact `OpError` with document unchanged, and never-edited models writing no floor copy), all 32 feature suites passed (including `GENERATION TESTS: 34/34`, `OUTSIDE SAVE TESTS: 26/26`, `NATIVE TESTS: 83/83`, `SCENARIO TESTS: 535/535`), and `viewport: QUICK 240 passed, 0 failed in 20.8 s`. No new decision IDs added; no open questions.

Architecture: `worker/session.py` `generation()` adds `"floor_file"` (`<model>.floor.FCStd`) beside the model; `Session._write_floor_copy()` writes it atomically (`saveCopy` to a temp name + `os.replace`) when the undo floor is set from FreeCAD (`_open_existing` when `self.external`, and `reload_outside` right after `_load_file`). Models never edited in FreeCAD write no floor copy.
Architecture: the journal (`<model>.shopsketch.json`) gains one optional field `"floor_copy": {"sha256": <hex>, "ops": <undo_floor>}` written by `Session._journal()`; a journal without it reads as no copy, and all existing journal fields are unchanged.
Architecture: `Session._rebuild(ops)` starts from `<model>.floor.FCStd` when `undo_floor > 0` and the file's sha256 and `ops` match `floor_copy`, keeping `applied[:undo_floor]`, `undo_floor`, and `session_base = undo_floor`, then replaying `ops[undo_floor:]`; if the copy is missing or mismatched it raises `OpError("can't undo past the FreeCAD edit: its copy is missing")` and leaves the document unchanged. `Session.save()` still writes via `saveCopy` to `self.path` (not the floor copy). `Session` alone owns the floor copy; no protocol or viewport changes.
For the integrator: update `ARCHITECTURE.md` with the `Architecture:` lines above (`<model>.floor.FCStd`, journal `floor_copy`, `Session._rebuild`).
For the integrator: update `worker/CLAUDE.md` ("Sync, undo, saving") to note `<model>.floor.FCStd` and the journal's `floor_copy` field for A38 rebuilds.
For the integrator: update `A38`'s "Where in the code" in `docs/decision-log.md` from `Not built: worker/session.py _rebuild (job H087)` to `Built (H087): worker/session.py generation() floor_file, _write_floor_copy(), _open_existing(), reload_outside(), _journal() floor_copy, _rebuild(); worker/test_floor_copy.py`.
Result: 60b429c; 21/21 floor copy checks, 32 feature suites, 240/240 quick viewport checks passed; A38 floor copy (<model>.floor.FCStd and journal floor_copy) keeps FreeCAD edits across rebuilds past 20 undo steps or below session_base.
