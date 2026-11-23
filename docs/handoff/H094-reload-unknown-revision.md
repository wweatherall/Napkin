### H094 — A reload from a revision Shop Sketch no longer remembers keeps the ops that file holds (H092 finding 6)

Author: Claude (integrator, fretchup-73) | Date: 2026-11-22 | Status: answered | For: codex

References: A36 and T64 (outside saves: a reload keeps the ops the file's revision held), A32 (save
generations), A35 (a new shared-file field bumps PROTOCOL_VERSION on both sides), H092 finding 6, H087 / A38
(the floor copy: a different problem, below the floor; nothing to reuse here).

Touches: worker/session.py (`save`, `_file_ops`, `reload_outside`), worker/serve.py (`PROTOCOL_VERSION` only),
viewport/main.gd (`PROTOCOL_VERSION` only), worker/test_outside_save.py. Not ARCHITECTURE.md or docs/protocol.md
(write `Architecture:` lines). Queued after H093, which also changes `reload_outside`.

Since H093 (merged 2026-11-23, checked against the code then): `reload_outside` copies FreeCAD's file to a
sibling snapshot, validates it and reads `frev = file_rev(snapshot)`, then calls `self._file_ops(frev)`, which
takes no path. So read `ShopSketchOps` from the file whose `frev` was read (give `_file_ops` the path: the
snapshot in `reload_outside`; `self.path` in `_open_existing(outside_reload=True)`, H093's cold retry on a new
worker, which also calls `_file_ops(file_meta_rev)` and gains the most from this). worker/test_outside_save.py
now has 43 checks, H098's 16 among them; all must still pass.

Today (checked 2026-11-22, still true after H093 except where the paragraph above says): `Session.save` records each saved revision's op list in `self.rev_ops`, keeping
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

Cases that must still work: all of worker/test_outside_save.py (43 checks: sections 6 and 7 are the
older-revision reloads; H098's 16 at the end), worker/test_generations.py, worker/test_floor_copy.py, and saving speed: say how much
longer a save of the scenario fixture takes (time it before and after).

Checks (worker/test_outside_save.py): a model saved at rev 1 (two boards), copied aside as FreeCAD would have
it open; then more than 50 further saves (ops synced and flushed one at a time); the rev 1 copy saved by FreeCAD
(`freecad_save`) and put back: the reload keeps rev 1's ops (r1, pp1, and the second board's) and drops the
rest. The same after the worker is restarted between the saves and FreeCAD's save (a new session's `rev_ops`
knows only the current revision). And a file with no `ShopSketchOps` (saved before this change: delete the
Meta key in the copy with FreeCAD) still reloads as today.

What can fail (P42; each gets a named check):
- An op whose strings XML must escape (a wood name or typed value with `"`, `&`, `<`, or non-ASCII like `°`):
  FreeCAD escapes the Meta value in Document.xml, so read it with an XML parser (ElementTree, as
  `validate_project` does), not `file_rev`'s regex, and check the round trip gives the same `canon` keys.
- `ShopSketchOps` missing, not JSON, or not a list of ops (an older file; a file hand-edited or cut short):
  fall back as listed (rev_ops, `.prev` journal, `[]`); the reload never fails because of it.
- `ShopSketchOps` present but `ShopSketchRev` absent or different (a Meta edited in FreeCAD): use the ops only
  when both are present and the revision is `frev`, so a file never claims ops from another revision.
- An entry built from Meta lacks the status fields an `applied` entry has today (`**st` from the journal): find
  which fields code reads after a reload (`board_marks`, the next sync's prefix by `key`, `save`'s rev_ops, the
  journal written at once) and fill them as `_file_ops`'s `.prev` path does; say which fields in your response.
- A failed save after `ShopSketchOps` is set on the live document: the live Meta then names ops no file holds
  yet; set it the same way and at the same point as `ShopSketchRev`, so the two can't disagree.
- A long model: the save writes the whole op list into Document.xml each autosave; time it (asked below) on the
  scenario fixture and on a model of 500 ops, and say both.

Reading path: session.py `save` (where `rev_ops` is filled and `ShopSketchRev` set) → `file_rev` → `_file_ops`
→ `reload_outside` → `_open_existing` (where `rev_ops` is reset). Who owns what: Session writes the file and
its Meta; FreeCAD's own save keeps what it doesn't know about.

Run the feature tests while building (`tools/featuretest.sh`), then `python3 tools/job.py test`. End your
response with a Result line; leftovers as Follow-up lines; anything for the merge as For the integrator lines.

#### Response — Codex, 2026-11-23

Branch `codex/h094-reload-unknown-revision`, implementation `b05e550`. FreeCAD 1.1.4 preserved both Meta keys through a normal edit and save. Rev 1 kept both boards and their four ops after 52 more saves, including on a cold reload. The journal records later ops as dropped. Older files and unusable Meta fall back to the session, the previous journal, or an empty op list.

Metadata restores `op`, canonical `key`, `id`, `type`, and `status: ok`. Board marks come from native geometry, the next sync compares canonical keys, and the next save and reload journal consume the restored status. The optional original timing and change details are absent from Meta. No decision IDs added or questions open.

Median of 21 warm `Session.save(outdir)` calls per case on this Mac, including GLB output. The 14-op scenario went from 11.1 ms to 10.9 ms (−0.2 ms). The same fixture extended to 500 ops with alternating shelf moves went from 17.7 ms to 17.8 ms (+0.1 ms). Both differences were within the observed run-to-run spread.

The feature suite and `job.py test` passed. The final run included 54 outside-save checks, 34 generation checks, 21 floor-copy checks, and 302 viewport quick checks.

Architecture: Session.save writes the successful ops as compact JSON in FCStd Meta ShopSketchOps alongside ShopSketchRev and rolls both back together on failure.

Architecture: Outside reloads recover the ops from Document.xml in the validated snapshot, or from the model file when a replacement worker initializes a cold retry. Matching Meta takes priority over revision history and the previous journal. Both worker and viewport now speak protocol 11.

For the integrator: Update the FCStd persistence description in ARCHITECTURE.md and the protocol version history and native-model Meta section in docs/protocol.md.

Result: b05e550; feature suite and job.py test passed; outside reloads recover the ops embedded in FreeCAD's saved revision.
