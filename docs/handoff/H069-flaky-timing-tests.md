### H069 — Three timing-sensitive tests that fail under load

Author: Claude (integrator, fretchup-73) | Date: 2026-11-22 | Status: answered | For: either

References: P18 (the gate), H057's and the integrator's follow-ups in docs/follow-ups.md, A36 (outside saves), W13.
William chose this job, 2026-11-22 (review: re-running the gate on a flake must not become a habit).

Touches: worker/test_serve.py, worker/test_outside_save.py, tools/test_startup.py, docs/follow-ups.md (remove the lines this clears: H057's, the integrator's outside-save one, H066's and H071's).
Not worker/serve.py or worker/session.py unless the cause is a real bug there: then stop and say so in your response
first (that would be a behaviour fix, its own job).

Request: make all three deterministic without weakening what they check. (1) test_serve.py fails 4 of 20 (saved / focus /
save_failed replies in another order) when featuretest.sh writes inside the repo under full load. (2)
test_outside_save.py "an outside save with actions unsaved says so" once got `unsaved: False` in the gate's quick
test. (3) tools/test_startup.py timed out (its 10-second subprocess limit, line 131, running startup.py T1) in
H066's quick test and the integrator's after H065: seen twice on 2026-11-22. Find whether each waits on time instead of on the event it means (a sleep, a fixed timeout, a reply order it
assumes) and wait on the event. Checks: each test passes 20 runs in a row under load (all feature tests side by side:
`tools/featuretest.sh`, run through `python3 tools/job.py run -- ...`, P40); say how you loaded it. Quick test.


Response — Codex, 2026-11-22:

Branch: `codex/h069-flaky-timing-tests`. Implementation: `c048f60`. Merged main into the branch before delivery (already up to date).

The protocol test windows now retrieve already-buffered events, match asynchronous events to the model being checked, normalize TESTDIR to an absolute path, and enforce receive deadlines with the monotonic clock. A socket-pair regression queues saved events for two models and focus before a sync reply, then retrieves them in a different order. This also caught a stale saved event from two.FCStd being mistaken for three.FCStd's initial save.

The unsaved outside-save case prepares FreeCAD's edited file separately, acknowledges SIGSTOP with waitpid, queues the sync and publishes the edited file, then resumes the worker. Its first watch settles the changed file; the queued sync lands before the next watch reports it. The existing unsaved, no-overwrite, reload and dropped-actions assertions remain, with a new successful-sync check. Other outside-save cases still edit the watched model directly. No production worker changes.

Startup's three smoke subprocesses now wait for completion rather than impose a 10-second speed limit; P40's job.py run still bounds the enclosing run and stops its process group if hung. The final quick test's startup test took 12 seconds and passed all 41 checks.

Verification:
- 20 consecutive complete `tools/featuretest.sh` runs, each through `python3 tools/job.py run -- tools/featuretest.sh <absolute worktree>/scratch/h069-loaded-NN`. Every run starts all feature tests side by side; serve 22/22, outside-save 26/26 and startup 41/41 passed every time, as did all other feature tests. Logs and the runner are in this worktree's scratch/.
- `python3 tools/job.py run -- env TESTDIR=scratch/h069-relative-serve python3 worker/test_serve.py`: 22/22 under the full-suite load, covering the original relative-path serve case.
- `python3 tools/job.py run -- tools/quicktest.sh`: all feature tests and 240/240 viewport checks passed. `python3 tools/job.py run -- tools/fulltest.sh`: all feature, recorded comparison and targeted checks passed. The queue verifies the final delivery commit separately.
- `git diff --check` and tracked architecture commit hook passed. Removed the four cleared H057 / outside-save / H066 / H071 follow-ups.

Decision IDs / placeholder IDs: none; no new behavior choices.

Architecture: none — test harness synchronization only; no module boundary, protocol, file format, state ownership or production saving changes.

Follow-up: With a relative whole-suite output path (`scratch/h069-load-01`), worker/scenario/99_regions.py timed out after 30 seconds invoking Godot with `--regions-output=scratch/h069-load-01/scenario/region-predictions.json`. This is outside H069's files; the subsequent 20 complete runs with absolute paths inside the same worktree all passed. Evidence: scratch/h069-load-01/scenario.log.

For the integrator: review H069 on codex/h069-flaky-timing-tests; no architecture-map or folder-guide updates needed.

Result: c048f60; 20 complete loaded feature runs, quick test 240/240 and full test passed; protocol events and the unsaved outside-save fixture are synchronized, startup smoke checks wait for completion.
