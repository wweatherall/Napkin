# Follow-ups

Leftovers from merged jobs (P26): a worker writes each one as its own `Follow-up: <what>` line in its handoff
response, and tools/integrate.py copies it here at merge. The integrator removes a line in the commit that does it,
or that turns it into a Work list item. `python3 tools/startup.py` lists the open ones.

## Open

- integrator (2026-11-22): William will have the integrator set up `/code-review ultra` later, on the biggest diff it will take (find its size limit first); he sends it off himself. Holds the H074 whole-code findings question.
- H061 (2026-11-22): Codex sessions are counted only if CODEX_SESSION_ID or CODEX_THREAD_ID is set; if Codex has neither, its count never applies (it falls back to "codex"). Worth checking from a Codex session.
- H062 (2026-11-22): the .unmatched files are never cleaned up (overwritten by the next recovery); fine while recoveries are rare.
- H063 (2026-11-22): Session.sync() rebuilds from the op list when an undo goes past FreeCAD's 20 steps, and that rebuild loses a FreeCAD change below the undo floor (it starts from an empty document); it should start from the file the floor came from. Before T64 this was already true after opening an externally edited file.
- H063 (2026-11-22): after a crash during an outside-save wait, "Keep Shop Sketch's" on the new worker saves FreeCAD's file plus the window's actions on top (the new worker loaded FreeCAD's file); the aside copy is still made.
- H059 (2026-11-22): tools/test_log.py assumes its copied real log has no I/G/Q/T/A placeholders when testing branch allocation; adding an I-new decision on a worker branch caused four false failures. Its temporary test edit was reverted to avoid overlap with H068; H059 uses a W-new View decision. H068 owns this test, so carry any fix there.
- integrator (2026-11-22): document.gd reserve_values and session.py id_strings reserve every string in the ops (types, wood names, typed values), not only ID fields; the whole set goes out with every sync and into the journal. Fine at today's sizes; limit it to ID fields before models get long (H059).
- H069 (2026-11-22): With a relative whole-suite output path (`scratch/h069-load-01`), worker/scenario/99_regions.py timed out after 30 seconds invoking Godot with `--regions-output=scratch/h069-load-01/scenario/region-predictions.json`. This is outside H069's files; the subsequent 20 complete runs with absolute paths inside the same worktree all passed. Evidence: scratch/h069-load-01/scenario.log.
- H073 (2026-11-22): a BOARD.md that git merges without a conflict still takes the branch's edits to Notes or the table as they are (the table is rebuilt; Notes isn't); settle_board runs only on a conflict.
- H078 (2026-11-22): docs/agent-handoff.md's "Jobs, round 1" section (below the open list, outside this job's Touches)
- H078 (2026-11-22): AGENTS.md's `git log --oneline -15 main` / `git branch -a` step repeats what startup.py already
- H078 (2026-11-22): say in CLAUDE.md what "watched code" is (which paths the architecture check watches), so a worker
- H081 (2026-11-22): worker/test_length_protocol.py creates its temporary folder through TMPDIR instead of its assigned TESTDIR. In a job it now lands in scratch and is removed on exit.
- H081 (2026-11-22): integrate.py and job.py test capture the scripts' output until exit. Live progress is visible when running the scripts directly or through job.py run.
