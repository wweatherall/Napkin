# Follow-ups

Leftovers from merged jobs (P26): a worker writes each one as its own `Follow-up: <what>` line in its handoff
response, and tools/integrate.py copies it here at merge. The integrator removes a line in the commit that does it,
or that turns it into a Work list item. `python3 tools/startup.py` lists the open ones.

## Open

- H060 (2026-11-22): integrate.py takes an entry's ID from its file name's first dash, so an entry still named H-new-N at merge records its Result and follow-ups as "H" (number_ids runs after); seen in reading, not hit yet.
- H057 (2026-11-22): worker/test_serve.py fails 4 of 20 (the saved/focus/save_failed replies arrive in another order) when featuretest.sh is given an output folder inside the repo (e.g. scratch/feat) under full load; passes alone, and with the default /var/folders output (what quicktest and the gate use). Timing-sensitive, seen in this job, not caused by it.
- integrator (2026-11-22): integrate.py on a scratch merge branch (main merged into a job branch first, as for H057) doesn't mark the original job merged or remove its worktree and branch; done by hand with job.merged(). Let integrate.py take --job H0NN, or notice the job branch is merged.
- H061 (2026-11-22): Codex sessions are counted only if CODEX_SESSION_ID or CODEX_THREAD_ID is set; if Codex has neither, its count never applies (it falls back to "codex"). Worth checking from a Codex session.
- H062 (2026-11-22): worker/CLAUDE.md's "Autosave is atomic" bullet could name the generation files (.saving, .prev, .unmatched); outside this job's Touches.
- H062 (2026-11-22): the .unmatched files are never cleaned up (overwritten by the next recovery); fine while recoveries are rare.
- Codex-review (2026-11-22): First priority from the repo review at 579834a. In tools/featuretest.sh a discovered test that prints “EXAMPLE TESTS: 1 passed, 0 failed” and then exits 7 makes the runner exit 0 (reproduced in a temporary fixture). Require both a successful exit from each child and its passing summary. Keep that fixture as a regression check.
- Codex-review (2026-11-22): Review integrate.py --continue after the architecture-map pause (P28). resume() runs git add -u and commits, so a tracked production edit made after the gate could be staged and shipped without another run. Consider limiting automatic staging to the expected docs and requiring a fresh gate for other changes. Verify with a temporary merge paused for a map edit.
- Codex-review (2026-11-22): For the existing T88 migration, use Paint as the first worked example. Check whether painting and hover highlighting can both be understood and changed through ToolContext without reading Main. Use the result to guide the remaining migrations.
