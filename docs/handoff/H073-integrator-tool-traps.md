### H073 — Two merge traps the tools cause: placeholders in prose, and BOARD.md's instructions lost

Author: Claude (integrator, fretchup-73) | Date: 2026-11-22 | Status: open | For: either

References: T74 (placeholder IDs), P26, P28, docs/integrator.md ("Traps seen at merge"), H070.
William asked for this, 2026-11-22 (onboarding fixes, after the integrator's review of its own start).

Touches: tools/number_ids.py and tools/test_number_ids.py, tools/integrate.py (its BOARD.md conflict settling only)
and tools/test_integrate.py, docs/integrator.md (remove the two traps this clears).

Request: fix two traps seen on 2026-11-22.
(1) number_ids.py numbers every placeholder it finds, including one written as an example in prose: archiving H050
turned its example placeholder into a real-looking "P42" in docs/handoff-archive.md (no such decision exists). Make
it number only placeholders that are IDs: in the decision log, rows a branch adds (`| X-new-N |`) and references to
them; in docs/handoff/, an entry's file name and heading and references to those. A placeholder that matches no
row or entry it is giving a number to is reported ("not numbered: <file>:<line>"), not numbered. Check: a prose
example in the archive and in a handoff entry stays as written and is reported; today's real cases (a new log row
and its references, a new handoff entry, BOARD.md's mention of it) still number.
(2) integrate.py settles a BOARD.md conflict by taking main's whole file, so a branch's edits to the board's
instruction sections are lost (H070's were; the integrator put them back by hand). Keep main's Order line, job
table and Notes (the integrator's), and take the branch's other sections when only the branch changed them; if
both changed the same section, stop and say so. Check: a branch editing "If you're not the integrator" while main
changed Notes merges with both; both editing the same section stops.
Quick test, then the gate. End your response with a Result line; leftovers as Follow-up lines; anything for the
merge as For the integrator lines.
