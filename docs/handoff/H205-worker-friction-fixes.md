### H205 — Fewer stops for workers: branch log checks ignore newer comitatus rulings, the gate's pass counts for SUBMIT_JOB, the Result line is checked first, one test file runs on its own

Author: Claude (integrator, opus-integrator) | Date: 2026-11-27 | Status: answered | For: gemini

References: William, 2026-11-27 (make the log-check fix a job; Gemini's feedback after H186), docs/follow-ups.md (the
integrator's 2026-11-27 line on branch log checks reading live comitatus rulings), H080 (SUBMIT_JOB reuses a clean pass
after handoff-only commits), T91 (the Result line), P73.

Touches: tools/sort_decision_log.py (the index checks for comitatus rulings), tools/test_sort_decision_log.py,
tools/gate.sh (record its quick-test pass), tools/job.py (`done`: the Result note before the tests; reading the pass
the gate recorded), tools/test_job.py, tools/RUN_ONE_TEST.sh (new), tools/featuretest.sh (only if the runner is shared),
tools/test_featuretest.py, tools/README.md (one line), docs/follow-ups.md (clear the branch log-check line).

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
4. `tools/RUN_ONE_TEST.sh <test file>` runs one test file the way featuretest.sh runs it (freecadcmd for worker tests
   that need FreeCAD, Godot headless for viewport ones, python3 otherwise), found the same way common.sh finds them,
   and prints its summary line (a Gemini worker on H198, 2026-11-27: `freecadcmd` isn't on PATH, so checking a
   one-line fix took the whole two-minute gate). `--list` in featuretest.sh shows how each file is run.
5. Clear the follow-ups line this job takes on.

Not in this job: what counts as a handoff-only commit (H080), the Result line's format.

Checks:
- `tools/TEST_BEFORE_MERGING.sh` passes (tools scope); a run of the gate followed by a handoff-only commit and
  SUBMIT_JOB reuses the gate's pass (a test in tools/test_job.py).

Response:
- Branch: `gemini/h205-worker-friction-fixes`, code commit `6959eb9`.
- Branch log checks (`tools/sort_decision_log.py`, `tools/test_sort_decision_log.py`): in a linked job worktree, `_branch_comitatus_skips` checks comitatus rulings whose index lines (`decision-log.md` / `decision-archive.md`) were not changed on this branch since `git merge-base HEAD main`. Unchanged comitatus mismatches (missing, out of date, or in index without a file) are preserved by `tidy`/`generate_indexes`, skipped by `layout_problems`, and emitted as `note: <ID> is newer in comitatus than this branch's index; merging main brings it`; on `main` or when the branch edited the index line, they still fail. Added 5 tests in `tools/test_sort_decision_log.py` (`41 passed, 0 failed`).
- Gate quick-test pass reuse (`tools/gate.sh`, `tools/job.py`, `tools/test_job.py`): added `record_test` / `job.py record-test` called by `tools/gate.sh` only when `QRC=0` and `TEST_SCOPE != "tools"`, recording `{commit, clean, ok, at}` for the worktree's job so a handoff-only commit after a passing full gate reuses it; `scope tools` records nothing.
- `done` Result check (`tools/job.py`, `tools/test_job.py`): moved the `Result:` line check before `quick_pass_covers` / `test(cwd, k, out)` so missing-`Result:` notes print before any test runs. Added 4 tests in `tools/test_job.py` (`226 passed, 0 failed`).
- Single-test runner (`tools/RUN_ONE_TEST.sh`, `tools/featuretest.sh`, `tools/test_featuretest.py`, `tools/README.md`): extracted `test_runner_for` in `tools/featuretest.sh` and added `tools/RUN_ONE_TEST.sh <test file>` to run one test with the same runner resolution and print its summary line. Added 4 tests in `tools/test_featuretest.py` (`49 passed, 0 failed`); verified `tools/RUN_ONE_TEST.sh tools/test_sort_decision_log.py` (`LOG SORT TESTS: 41 passed, 0 failed`).
- Cleared the `sort_decision_log.py --check` follow-up line from `docs/follow-ups.md`.
- Tests on `6959eb9`: `tools/TEST_BEFORE_MERGING.sh` passed (`GATE PASS: full test passes; QUICK 405 passed, 0 failed in 34.9 s ; 0 known failure(s); 96 s total`).
- Result: 6959eb9; GATE PASS (405/405 quick, full pass, LOG SORT 41/41, JOB 226/226, FEATURETEST 49/49); branch log checks ignore unchanged comitatus rulings, gate records full quick-test pass, done checks Result first, added RUN_ONE_TEST.sh, cleared follow-up.
