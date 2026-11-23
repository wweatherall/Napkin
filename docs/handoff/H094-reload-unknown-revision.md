### H094 — A reload from a revision Shop Sketch no longer remembers keeps the ops that file holds (H092 finding 6)

Author: Claude (integrator, fretchup-73) | Date: 2026-11-22 | Status: queued (after H093) | For: either

References: A36 and T64 (outside saves: a reload keeps the ops the file's revision held), A32 (save
generations), A35 (a new shared-file field bumps PROTOCOL_VERSION on both sides), H092 finding 6, H087 / A38
(the floor copy: a different problem, below the floor; nothing to reuse here).

Touches: worker/session.py (`save`, `_file_ops`, `reload_outside`), worker/serve.py (`PROTOCOL_VERSION` only),
viewport/main.gd (`PROTOCOL_VERSION` only), worker/test_outside_save.py. Not ARCHITECTURE.md or docs/protocol.md
(write `Architecture:` lines). Queued after H093, which also changes `reload_outside`.

Today (checked 2026-11-22): `Session.save` records each saved revision's op list in `self.rev_ops`, keeping
the last 50 (`sorted(self.rev_ops)[:-50]` are deleted), and `_open_existing` resets it to the current
revision only, so a reopen or a new worker forgets the rest. `_file_ops(frev)` falls back to the `.prev`
journal (one revision), then to `[]`. With `[]`, `reload_outside` drops every action, including the rects,
lines and boards FreeCAD's file holds natively: they vanish from the window's list and view. This happens when
FreeCAD has the model open in the background while Shop Sketch autosaves more than 50 times (or restarts), and
FreeCAD then saves.

Request: make every saved file say which ops it holds. In `save`, write the revision's op list (the `ok` ops of
`self.applied`, the same list `rev_ops` gets) into the document's Meta as `ShopSketchOps` (compact JSON of the
ops), beside `ShopSketchRev`, before the copy is saved. `_file_ops(frev)` then reads `ShopSketchOps` from
FreeCAD's file first (from Document.xml without opening it, as `file_rev` reads `ShopSketchRev`) and uses it
when its revision is `frev`; then `rev_ops`, then the `.prev` journal, then `[]` as today (a file saved before
this change has no `ShopSketchOps`). FreeCAD keeps a document's Meta when it saves: check this in 1.1.4 with a
real FreeCAD save in the test (it's the whole point), and say what you found. Keep `rev_ops` (it is quicker and
covers a file whose Meta FreeCAD changed). Bump `PROTOCOL_VERSION` by one on both sides (a new field in a shared
file, A35).

Cases that must still work: all of worker/test_outside_save.py (30 checks: sections 6 and 7 are the
older-revision reloads), worker/test_generations.py, worker/test_floor_copy.py, and saving speed: say how much
longer a save of the scenario fixture takes (time it before and after).

Checks (worker/test_outside_save.py): a model saved at rev 1 (two boards), copied aside as FreeCAD would have
it open; then more than 50 further saves (ops synced and flushed one at a time); the rev 1 copy saved by FreeCAD
(`freecad_save`) and put back: the reload keeps rev 1's ops (r1, pp1, and the second board's) and drops the
rest. The same after the worker is restarted between the saves and FreeCAD's save (a new session's `rev_ops`
knows only the current revision). And a file with no `ShopSketchOps` (saved before this change: delete the
Meta key in the copy with FreeCAD) still reloads as today.

Reading path: session.py `save` (where `rev_ops` is filled and `ShopSketchRev` set) → `file_rev` → `_file_ops`
→ `reload_outside` → `_open_existing` (where `rev_ops` is reset). Who owns what: Session writes the file and
its Meta; FreeCAD's own save keeps what it doesn't know about.

Run the feature tests while building (`tools/featuretest.sh`), then `python3 tools/job.py test`. End your
response with a Result line; leftovers as Follow-up lines; anything for the merge as For the integrator lines.
