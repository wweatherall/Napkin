### H066 — T101: recovery on opening, the newest file wins

Author: Claude (integrator, fretchup-73) | Date: 2026-11-22 | Status: queued (after H059) | For: either

References: A37 (William's call, 2026-11-22), A32 / T40 (save generations, H062: `recover_generation`), A25 (outside
edits and the undo floor), A36 / T64 (H063: `outside_sha256`, which already covers the case when a worker saw the save).

Touches: worker/session.py (`recover_generation` only), worker/test_generations.py, worker/test_outside_save.py
(only if a case there relies on the old rule). Not ARCHITECTURE.md or docs/protocol.md (P28): give "Architecture:"
lines for the recovery paragraph.

Request: build A37. Today `recover_generation` treats a journal newer than the file as a save of ours that stopped
part way, so a FreeCAD save made while Shop Sketch was closed (FreeCAD writes the revision it opened, an older
number) is moved to .unmatched and our .prev pair opens instead. Change it to:
1. The newest file on disk is the model: never put an older version back over a newer file.
2. Finish a save of ours that stopped part way only when the file is the new file of that save (it matches the
   .saving journal's sha256, or its ShopSketchRev is the journal's + 1 with a whole new pair).
3. Any other mismatch opens as an outside edit with its undo floor (A25), with no recovery reported.
4. The .prev pair only when the main file is missing or unreadable.
Dates decide only "never go back to something older"; contents decide the rest. Checks: a FreeCAD save of an older
revision made while closed opens as an outside edit (no .unmatched, FreeCAD's work shown); the two real broken-save
cases still recover; a missing or unreadable file still opens .prev; H062's and H063's tests still pass. Quick test,
then the gate. End your response with a Result line; leftovers as Follow-up lines; anything for the merge as For the
integrator lines.
