### H217 — Mutation testing for worker/: plant small bugs one at a time and record which tests catch each (T171 step 1)

Author: Claude (integrator, integrator-opus) | Date: 2026-11-28 | Status: open | For: Codex | Item: T171

References: T171 (William, 2026-11-28: go ahead, "divide it into as many jobs as you think is necessary"); T172 and its
notes (William's tree of dense tests: ultra-dense tests at the top, each linking about 5 less dense ones, down to tests
that pinpoint the cause); H214 (`tools/test_inventory.py`, `tests/test_inventory.json`: each file's runner and seconds);
H215 (`tools/line_trace.py`, `test_inventory.py --coverage`: which lines each test runs); ChatGPT's caution, 2026-11-28:
running the same lines doesn't mean catching the same bugs, which is why this matrix matters more than coverage.

Today: `tools/test_inventory.py --coverage` traces every worker and tools test file (about 9 minutes) and writes per-test
line traces to `scratch/coverage/` (not committed; a fresh worktree has none) and per-file functions to
`tests/test_coverage.json`. `tools/featuretest.sh` can be sourced for `test_runner_for <file>` and `run_test_command`,
which set up each test's runner, TESTDIR and private FreeCAD config. Worker line coverage is 90%.

Touches: tools/mutate.py (new), tools/test_mutate.py (new), tests/kill_matrix.json (new, generated).
The integrator adds its line to the tools README at merge.

Request:
1. `tools/mutate.py --list <worker/file.py>` makes the mutants of a file with `ast`, each with a stable id
   `file:line:col:operator`: a comparison flipped (`<`↔`>=`, `<=`↔`>`, `==`↔`!=`), `+`↔`-` and `*`↔`/`, `and`↔`or`, a
   `not` dropped, a number constant n → n+1 (0 → 1), `True`↔`False`, a statement inside a function replaced by `pass`,
   and a `return x` made `return None`. Skip docstrings, logging and print lines, and `if __name__` blocks (mutants there
   are noise). Mutate worker/*.py only, never test files.
2. Run a mutant: in an isolated copy (a detached `git worktree` under `scratch/mutation/tree-<n>`, one per parallel
   lane, removed at the end; the job's own tree is never mutated), write the mutant, run every test file whose trace
   covers its line (from `scratch/coverage/`, regenerated first with `test_inventory.py --coverage` if missing or older
   than the code), each through featuretest.sh's runner with a time limit of 3× its time in `tests/test_inventory.json`,
   then restore the file. Record per test: killed (fails or prints a FAIL), survived, or timeout (counted as killed,
   kept apart). Run all covering tests, not just until the first kill: the matrix needs every test's answer. A mutant no
   test covers is recorded `no coverage` without running anything.
3. Make it resumable and bounded: results append to `scratch/mutation/results.jsonl`; a rerun skips mutant ids already
   there (unless the file changed since); `--budget-minutes N` stops cleanly; `--lanes N` (default 4) runs side by side;
   `--sample K` takes K mutants per file, spread through the file, with a fixed seed.
4. `--matrix` writes `tests/kill_matrix.json`: per mutant its id, function, operator and the tests that killed it (by
   file; the check names that failed where the output gives them); per test file its seconds. Keep it compact enough to
   commit (lists of indexes, not repeated names).
5. In this job, run `--sample 20` over all of worker/ and commit that matrix. Say in your response how long a mutant
   takes on average, the projected time for every mutant in worker/ at 4 lanes, how many mutants survived and in which
   functions, and anything that made results noisy (flaky tests, mutants that hang FreeCAD). The full run is a command
   the integrator starts overnight after the merge.

What can fail:
- A mutant leaves a FreeCAD process or a model file behind and the next run sees it. Check: every test runs with its own
  TESTDIR in its lane's tree, and after a run `git status` in that tree is clean before the next mutant.
- A killed run is reported as survived because the runner printed no summary line. Check: a test with no summary line
  counts as killed (it crashed), and a test-only check plants a mutant that makes a worker module fail to import.
- The real repo is changed. Check: a run ends with `git status` in the job's tree showing only the files it means to
  write.

Checks:
- `tools/test_mutate.py` (summary line `MUTATE TESTS: N passed, M failed`): each operator on a tiny source gives the
  expected mutant and nothing in a docstring; ids are stable across runs; resume skips finished ids; a covering-test
  lookup picks the right test files from a fake trace; a crash counts as killed.
- The sample run, `tests/kill_matrix.json` committed, the numbers in your response.
- `tools/TEST_BEFORE_MERGING.sh` passes.
