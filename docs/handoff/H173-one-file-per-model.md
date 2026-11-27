### H173 — One file per model: everything the journal holds moves inside the .FCStd, nothing beside it

Author: Claude (integrator, napkin-77) | Date: 2026-11-27 | Status: open | For: gemini

References: A42 (this decision: William, 2026-11-27, "Yes, make it one file. This is important."), A32 / A37 / A38
(saving as a file-and-journal pair, recovering a mismatched pair, the floor copy: superseded when this merges),
A25 (undo floor), A36 (outside saves: reload or keep mine), G02 (the file is the model), G09 (never lose work),
P42 (a "What can fail" section for saving changes), H171 (`upgrade_op`: how old files were upgraded last time).

Touches: worker/session.py, worker/common.py (`JOURNAL_FORMAT`), worker/serve.py (`save_pending` and the outside-save
watch, only where they name the journal), worker/test_load.py, worker/test_floor_copy.py, worker/test_outside_save.py,
worker/test_link.py, worker/test_serve.py, worker/test_native.py, worker/test_generations.py, docs/protocol.md (the
`.FCStd` and journal section and "Publication and locations"), worker/CLAUDE.md (its lines on the journal).

Reading path:
1. docs/protocol.md `### Model .FCStd and <stem>.shopsketch.json journal`: the Meta keys (`ShopSketchRev`,
   `ShopSketchUnits`, `ShopSketchOps`) and every journal field.
2. worker/session.py: `generation` (the eight paths a model uses today), `read_journal`, `recover_generation`
   (A37: pairs a file with a journal by sha256), `keep_aside`, `Session._open_existing`, `_file_ops`, `save` (writes
   `.saving`, renames, then writes the journal; ~line 660-700), the floor copy (`floor_file`, ~454 and ~732), and
   where `outside_sha256` is set (~547).
3. worker/test_outside_save.py: how a FreeCAD save is simulated and detected.

Today (checked 2026-11-27): a model is the `.FCStd` plus files beside it: the journal `<stem>.shopsketch.json`
(history and results, reserved IDs and their owners, undo floor, dropped actions, outside-save hash, floor-copy
hash), a `.prev` pair, `.saving` temporaries, `.unmatched` copies of displaced files, and `<stem>.floor.FCStd` (the
document as FreeCAD's last edit left it, for undoing past it). The journal says whether the `.FCStd` is the one we
saved by its sha256; much of session.py (A32/A37) exists because the two files can disagree. The `.FCStd` already
carries `ShopSketchRev`, `ShopSketchUnits` and `ShopSketchOps` in its Meta, and FreeCAD keeps Meta through its own
save. Copying only the `.FCStd` today loses the undo floor, reserved IDs and dropped actions.

Request (A42):
1. **Everything inside the .FCStd.** What the journal holds goes into the document's Meta (one JSON value, e.g.
   `ShopSketchJournal`, alongside the existing keys; keep the `ShopSketch` prefix: the name purge T139 renames all
   of them together). The floor copy goes inside the same zip, as an entry the worker writes after FreeCAD's save
   (the save already rewrites the zip to inject GuiDocument metadata). If FreeCAD drops that entry on its own save,
   that is fine: a FreeCAD save makes FreeCAD's file the new floor (A38), so the copy is only needed once we save
   on top of it again, and we write it then. Check this reasoning against the code and say in your response
   whether it holds.
2. **Knowing a file is ours without a second file.** Today the journal's sha256 tells us whether FreeCAD changed
   the file while it was closed. Replace it with something stored inside the file: recommended, a hash of the
   zip's contents with our own Meta values left out, written into Meta by the same post-save rewrite (so storing it
   doesn't change what it hashes). On open, a mismatch means FreeCAD edited the file: open it as today's outside
   edit (A36/A38). A better signal is welcome if test_outside_save proves it; say which you chose and why.
3. **Saving is one atomic step.** Write `<stem>.saving.FCStd`, then rename it over the model; nothing else is
   written beside the model. With one file there is no pair to recover: delete A37's pair-matching
   (`recover_generation`'s pairs, `.prev`, `.unmatched`, `keep_aside` for saves) and keep only what one file
   needs: a leftover `.saving` file from an interrupted save is removed on open (the model itself is whole, because
   the rename is atomic). Say in your response which functions went and how many lines.
4. **Old models upgrade themselves (G09).** Opening a model with a journal beside it reads the journal as today
   (including H171's `upgrade_op`); the first save writes everything into the `.FCStd`, and only after that save
   has landed are the old journal, its `.prev` pair and the old `<stem>.floor.FCStd` removed. `.unmatched` files
   (bytes kept aside from an earlier recovery) are left alone: they may be the user's work. A journal that doesn't
   match its file (wrong sha) is handled as today on that first open, then removed after the first save.
5. protocol.md and worker/CLAUDE.md describe the one-file layout; the journal section becomes "what the .FCStd
   carries in its Meta". No protocol message changes, so no version bump; the saved format does change: say so
   in protocol.md with the date.

Not in this job: renaming the Meta keys (T139), outputs in the output folder (bodies.json, meshes, model.glb,
views.json: they are not beside the model in the app, which uses its own output folder), anything the window does.

What can fail (P42: this changes what is saved and how every model opens; nothing may be lost):
- An old model loses history, the undo floor, reserved IDs, dropped actions or FreeCAD's floor copy in the upgrade.
  Check: test_load.py with a model and journal written by main's code (make the fixture on main before you
  change anything, and commit it), opened, undone past the floor, saved, reopened from the `.FCStd` alone with the
  journal gone: same bodies, same undo, same reserved IDs.
- Copying only the `.FCStd` somewhere else: it opens with everything. Check: a test that copies just the file.
- A FreeCAD save while the model is closed is not noticed, or a file we saved is taken for FreeCAD's. Check:
  test_outside_save.py, both ways, including a FreeCAD save that changes only a property (no geometry).
- A crash during save leaves the model unreadable: the rename is atomic; a test kills the save between writing
  `.saving` and the rename, and reopening gives the previous save whole and removes `.saving`.
- The old journal removed before the new save landed: removal happens only after the rename. Check: a test with a
  failing save (read-only folder, as test_serve does) leaves the journal in place.
- A FreeCAD save on top of a file that carries our floor-copy entry: FreeCAD may drop it; undo past FreeCAD's
  newer edit still works or is refused with today's message, never silently wrong. Check: test_floor_copy.py.

Checks:
- The tests above, plus the whole worker suite and scenarios (they save and reopen constantly).
- `ls` of a model's folder after a session in a test: only the `.FCStd` (quote it in your response).
- `python3 tools/protocol_map.py --check`; `tools/TEST_BEFORE_MERGING.sh` passes (full scope).
