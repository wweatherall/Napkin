### H205 — Fewer stops for workers: branch log checks ignore newer comitatus rulings, the gate's pass counts for SUBMIT_JOB, the Result line is checked first

Author: Claude (integrator, opus-integrator) | Date: 2026-11-27 | Status: queued (after H199) | For: gemini

References: William, 2026-11-27 (make the log-check fix a job; Gemini's feedback after H186), docs/follow-ups.md (the
integrator's 2026-11-27 line on branch log checks reading live comitatus rulings), H080 (SUBMIT_JOB reuses a clean pass
after handoff-only commits), T91 (the Result line), P73.

Touches: tools/sort_decision_log.py (the index checks for comitatus rulings), tools/test_sort_decision_log.py,
tools/gate.sh (record its quick-test pass), tools/job.py (`done`: the Result note before the tests; reading the pass
the gate recorded), tools/test_job.py, docs/follow-ups.md (clear the branch log-check line).

Reading path:
1. tools/sort_decision_log.py around `ruling file exists without an index line`: comitatus/03_Past_Decisions/rulings/
   is one live folder shared by every checkout and worktree, but each branch has its own index in
   03_Past_Decisions/decision-log.md.
2. tools/job.py `quick_pass_covers` and `done` (the `no quick-test pass recorded` and `has no line "Result:` lines),
   and `test`, which records `j["test"] = {commit, clean, ok, at}`.
3. tools/gate.sh: `run_stage "gate: quick test" ... tools/quicktest.sh`.

Today (checked 2026-11-27): H196, H198 and H203 each stopped with a question because a Process ruling was added or
reworded in comitatus after their branch started, so their branch's index line was missing or out of date; main was
fine each time. A worker that runs `tools/TEST_BEFORE_MERGING.sh` and then commits only its handoff still has
SUBMIT_JOB run the quick test again (about a minute), because only `job.py test` records a pass. SUBMIT_JOB says the
Result line is missing only after that test.

Request:
1. Branch log checks: in a job worktree (not the main checkout), a problem that concerns only a comitatus ruling (an
   index line missing, out of date, or without a file) whose index line this branch didn't change since its merge
   base with main is printed as a note (`note: P75 is newer in comitatus than this branch's index; merging main
   brings it`) and doesn't fail the check or the tidy. On main it fails as today. Tests for both, and for a branch
   that did change such a line (still fails).
2. The gate's quick test records its pass the way `job.py test` does (same commit, clean and ok fields), when it
   runs in a job's worktree, so a handoff-only commit after a passing gate reuses it (H080's rules unchanged). Only
   a quick test of the same scope `job.py test` runs counts: a gate that ran a narrower scope (`scope tools`, `docs`,
   app tests skipped) records nothing, so SUBMIT_JOB never skips app tests on the strength of a tools-only run.
3. `done` checks for the Result line before any test runs and says so first (same wording as today).
4. Clear the follow-ups line this job takes on.

Not in this job: what counts as a handoff-only commit (H080), the Result line's format.

Checks:
- `tools/TEST_BEFORE_MERGING.sh` passes (tools scope); a run of the gate followed by a handoff-only commit and
  SUBMIT_JOB reuses the gate's pass (a test in tools/test_job.py).
