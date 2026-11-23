# Follow-ups

Leftovers from merged jobs (P26): a worker writes each one as its own `Follow-up: <what>` line in its handoff
response, and tools/integrate.py copies it here at merge. The integrator removes a line in the commit that does it,
or that turns it into a Work list item. `python3 tools/startup.py` lists the open ones.

## Open

- H057 (2026-11-22): worker/test_serve.py fails 4 of 20 (the saved/focus/save_failed replies arrive in another order) when featuretest.sh is given an output folder inside the repo (e.g. scratch/feat) under full load; passes alone, and with the default /var/folders output (what quicktest and the gate use). Timing-sensitive, seen in this job, not caused by it.
- H061 (2026-11-22): Codex sessions are counted only if CODEX_SESSION_ID or CODEX_THREAD_ID is set; if Codex has neither, its count never applies (it falls back to "codex"). Worth checking from a Codex session.
- H062 (2026-11-22): the .unmatched files are never cleaned up (overwritten by the next recovery); fine while recoveries are rare.
- H063 (2026-11-22): Session.sync() rebuilds from the op list when an undo goes past FreeCAD's 20 steps, and that rebuild loses a FreeCAD change below the undo floor (it starts from an empty document); it should start from the file the floor came from. Before T64 this was already true after opening an externally edited file.
- H063 (2026-11-22): after a crash during an outside-save wait, "Keep Shop Sketch's" on the new worker saves FreeCAD's file plus the window's actions on top (the new worker loaded FreeCAD's file); the aside copy is still made.
- integrator (2026-11-22): worker/test_outside_save.py "an outside save with actions unsaved says so" failed once in the gate's quick test (got unsaved: False), passed in the same gate's full test and 5 of 5 alone: timing-sensitive under load, like H057's test_serve note.
- H059 (2026-11-22): tools/test_log.py assumes its copied real log has no I/G/Q/T/A placeholders when testing branch allocation; adding an I-new decision on a worker branch caused four false failures. Its temporary test edit was reverted to avoid overlap with H068; H059 uses a W-new View decision. H068 owns this test, so carry any fix there.
- integrator (2026-11-22): document.gd reserve_values and session.py id_strings reserve every string in the ops (types, wood names, typed values), not only ID fields; the whole set goes out with every sync and into the journal. Fine at today's sizes; limit it to ID fields before models get long (H059).
- H066 (2026-11-22): H066 initial quick test under load: tools/test_startup.py timed out at line 131 running startup.py T1 (10-second timeout); passed in the subsequent required gate. Inspect for a deterministic wait if it recurs.
- H071 (2026-11-22): H069 must resolve the known startup/outside-save timing failures before H071's final-commit quick verification and job.py done can be completed reliably; no changes to H069-owned files were made here.
- H070 (2026-11-22): startup.py's integrator reminder ("after a clear, re-arm the queue watch ... (H050)") could point to docs/integrator.md instead of the archived H050.
