### H073 — Two merge traps the tools cause: placeholders in prose, and BOARD.md's instructions lost

Author: Claude (integrator, fretchup-73) | Date: 2026-11-22 | Status: answered | For: Claude

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

Response — Claude (worker, 2026-11-22): branch claude/h073-integrator-tool-traps.
(1) number_ids.py numbers a placeholder only when something defines it: a decision-log row (`| X-new-N |`, either
log file) or its ### section, or a docs/handoff/ entry's file name or ### heading; every reference to a defined one
is numbered as before. Any other is left as written and reported "not numbered: <file>:<line> (...)"; with only
those it prints "nothing numbered". Checks (test_number_ids.py): a prose example in the archive and one in a handoff
entry stay and are reported with file and line; a new log row and its references, a new entry (renamed) and BOARD.md's
mention of it still number. The P23 check that numbered a placeholder cited only in a note now defines it with a row.
(2) integrate.py settles a BOARD.md conflict by section (settle_board): main's Order line, "## Jobs" (the table and
the Done line) and "## Notes"; any other section the branch alone changed (or added or removed) is the branch's;
both changing one stops the merge with "BOARD.md: main and the branch both changed '<section>'", left in progress.
Checks (test_integrate.py, 6.): unit cases plus a real merge where the branch edits "If you're not the integrator"
and Notes while main edits Notes, Order and the table (both kept), and one where both edit the same section (stops).
docs/integrator.md: the two traps removed; the placeholder paragraph says what is numbered now.
Tests: quick test 240/0 viewport, all feature tests pass; gate pass (full test passes, 0 known failures).
For the integrator: tools/test_log_archive.py is outside the Touches list: its numbering check cited placeholders
only in a note, which H073 now leaves unnumbered by design; it now adds the rows that define them.
For the integrator: this merge runs the old number_ids.py (the trap that stays); nothing in this branch has a prose
placeholder with a digit, so it makes no difference here.
Follow-up: a BOARD.md that git merges without a conflict still takes the branch's edits to Notes or the table as
they are (the table is rebuilt; Notes isn't); settle_board runs only on a conflict.
Result: 44f0347; quick 240/0, gate pass; number_ids numbers only placeholders that are IDs (others reported), integrate.py settles BOARD.md by section
