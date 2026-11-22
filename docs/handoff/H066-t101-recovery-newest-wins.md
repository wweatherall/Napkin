### H066 — T101: recovery on opening, the newest file wins

Author: Claude (integrator, fretchup-73) | Date: 2026-11-22 | Status: answered | For: either

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

Response — Codex, 2026-11-22:

Branch: `codex/h066-t101-recovery-newest-wins`. Implements existing A37; no new decisions or placeholders.
`recover_generation` validates the model archive, preserves readable outside edits regardless of revision or
missing journal, and restricts staged recovery to the matching .saving journal or a whole staged pair at rev+1.
A staged model cannot replace a newer main file. Missing/unreadable main files still recover a whole pair,
keeping displaced bytes aside. Regression coverage includes FreeCAD saving an older revision while closed,
lost journals, corrupt/missing models, and both accepted and vetoed staged saves.

Architecture: In ARCHITECTURE.md's save-generation recovery paragraph, replace the journal-newer trigger with A37:
a readable main model is preserved unless its hash matches the .saving journal, or it is rev+1 and a whole staged
pair of that revision can finish the save without replacing a newer file. Other mismatches open external with
A25's undo floor; .prev fallback is limited to missing or unreadable models. Archive readability checks parse
Document.xml and verify ZIP entries. No protocol or file-format change.

Verification: standalone `worker/test_generations.py` 34/34; required `tools/gate.sh` PASS (66 s),
quick viewport 240/240, all feature tests including generations 34/34 and outside-save 25/25, full test passed.
Gate logs: `scratch/shopsketch-gate.1o8Xbc/`. Initial quick run had outside-save's known H069 unsaved=False flake
and test_startup.py's 10-second subprocess timeout under load; viewport 240/240 and generations 34/34 passed.
No test was weakened or changed outside the generation suite. Latest main (5fd6cdf) merged before the gate.

Follow-up: H066 initial quick test under load: tools/test_startup.py timed out at line 131 running startup.py T1 (10-second timeout); passed in the subsequent required gate. Inspect for a deterministic wait if it recurs.
Result: 73c00b4; generation tests 34/34, gate PASS (quick 240/240 and full passed); preserves newer outside models and limits generation recovery to identifiable interrupted saves or missing/unreadable main files
