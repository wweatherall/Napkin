# Follow-ups

Leftovers from merged jobs (P26): a worker writes each one as its own `Follow-up: <what>` line in its handoff
response, and tools/integrate.py copies it here at merge. The integrator removes a line in the commit that does it,
or that turns it into a Work list item. `python3 tools/startup.py` lists the open ones.

## Open

- H060 (2026-11-22): integrate.py takes an entry's ID from its file name's first dash, so an entry still named H-new-N at merge records its Result and follow-ups as "H" (number_ids runs after); seen in reading, not hit yet.
- H057 (2026-11-22): worker/test_serve.py fails 4 of 20 (the saved/focus/save_failed replies arrive in another order) when featuretest.sh is given an output folder inside the repo (e.g. scratch/feat) under full load; passes alone, and with the default /var/folders output (what quicktest and the gate use). Timing-sensitive, seen in this job, not caused by it.
- integrator (2026-11-22): integrate.py on a scratch merge branch (main merged into a job branch first, as for H057) doesn't mark the original job merged or remove its worktree and branch; done by hand with job.merged(). Let integrate.py take --job H0NN, or notice the job branch is merged.
- H061 (2026-11-22): Codex sessions are counted only if CODEX_SESSION_ID or CODEX_THREAD_ID is set; if Codex has neither, its count never applies (it falls back to "codex"). Worth checking from a Codex session.
- H062 (2026-11-22): the .unmatched files are never cleaned up (overwritten by the next recovery); fine while recoveries are rare.
- Codex-review (2026-11-22): Question for the integrator (review at 579834a). What should count as a passing feature test? In a temporary fixture, a test printed “EXAMPLE TESTS: 1 passed, 0 failed”, exited 7, and tools/featuretest.sh reported success. My suggestion was to require both the passing summary and a zero exit status from each child, with that fixture as a regression test. Would that fit the exit conventions of all supported runners, or is there a better way to detect a failure after the summary?
- Codex-review (2026-11-22): Question for the integrator about P28. On reading integrate.py at 579834a, resume() stages all tracked edits with git add -u before committing. How should a merge handle a production edit made while paused for an architecture update? My suggestion was to stage the expected documentation explicitly and rerun the gate if the code has changed since it passed. A paused merge in a temporary repo could establish whether the risk occurs and whether that extra check is worthwhile.
- Codex-review (2026-11-22): Question for the integrator about the existing T88 plan. Would Paint make a useful first worked example for other tool authors? My suggestion was to use its painting and hover highlighting to judge whether ToolContext gives an agent enough information to change both behaviours without tracing through Main. That experience could inform the remaining migrations if it proves useful.
- H063 (2026-11-22): log.py add can't add a Tunables row (no kind for it), so OUTSIDE_SAVE_WAIT's and WATCH_S's rows were added to the Tunables table by hand.
- H063 (2026-11-22): Session.sync() rebuilds from the op list when an undo goes past FreeCAD's 20 steps, and that rebuild loses a FreeCAD change below the undo floor (it starts from an empty document); it should start from the file the floor came from. Before T64 this was already true after opening an externally edited file.
- H063 (2026-11-22): after a crash during an outside-save wait, "Keep Shop Sketch's" on the new worker saves FreeCAD's file plus the window's actions on top (the new worker loaded FreeCAD's file); the aside copy is still made.
