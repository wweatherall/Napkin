### H214 — Test inventory: every check, its file, its suite and its time, in one generated file (T172 step 1)

Author: Claude (integrator, integrator-opus) | Date: 2026-11-28 | Status: open | For: either | Item: T172

References: William, 2026-11-28: "we need to work on our testing. It is spiraling out of control ... as dense as
possible ... a test that would fail for what would cause the failures of any 10 other tests, that is the ideal. And
then you keep those other tests around for probing"; "we need to get testing to a higher velocity so we can move
faster"; T172 (dense tests: this is its first step), T171 (mutation testing, waiting on William), T173 (reducing the
merge gate, later), T152; C05 (a Python script, not a habit), C06 (one generated file, not hand counts).

Today: nobody can say how many checks we have, which are slow, or how they overlap. `tools/featuretest.sh` finds every
`worker/test_*.py`, `tools/test_*.py` and `viewport/test_*.gd` (51 files today; `--list` shows them and how each runs)
and keeps only each file's summary line (`<NAME> TESTS: N passed, M failed`). Most files print one line per check,
`PASS <name>` or `FAIL <name>  <detail>` (worker files through a `check(n, c, d)` helper, viewport ones through
`func check(label, condition)`, the scenario through `worker/scenario/context.py` `Scenario.check`), but some don't
(`grep -L 'PASS ' worker/test_*.py tools/test_*.py viewport/test_*.gd` lists them: test_native.py, test_scenario.py's
own lines, test_load.py which is a helper, ...). The quick test (`tools/quicktest.sh`, viewport/tests/quick/*.gd, 66
files) runs viewport steps in three lanes and prints its own per-check lines and a `QUICK ... in <time>` line per lane.
`featuretest.sh` can be sourced for `test_runner_for <file>` (it returns early when sourced), which sets `TEST_NAME`,
`TEST_RUNNER` and `TEST_CMD` the way the real run does.

Touches: tools/test_inventory.py (new; its name has no test_ prefix, so the feature tests do not run it as a test),
tools/test_test_inventory.py (new), tests/test_inventory.json (new, generated). The integrator adds its line to the tools README at merge, so this job does not overlap H213 there.

Request:
1. Write `tools/test_inventory.py`: it runs every feature test file the way featuretest.sh does (source it for
   `test_runner_for` rather than copying the runner rules, so the two can't drift; same TESTDIR and FreeCAD config
   handling, so it never touches a running Napkin), times each file, and collects each check line. Run the files side
   by side as featuretest.sh does, so the inventory costs about one feature-test run, not the sum.
   `--quick` also runs the quick test once (`tools/quicktest.sh` with an out dir) and reads its lane logs for the
   viewport steps' check lines and lane times.
2. Write `tests/test_inventory.json`: one entry per file `{file, suite (worker|tools|viewport|quick), runner,
   seconds, checks: [names], parsed: true|false}`, and one per check `{name, file}`; `parsed: false` for a file whose
   summary says N checks but whose PASS/FAIL lines don't add up to N, so we know where the counts are blind. Sort it
   so a rerun on an unchanged tree changes only the seconds.
3. Print a short report: totals (files, checks, seconds per suite), the 10 slowest files, the files that aren't
   parsed, and check names that appear in more than one file (a first rough sign of overlap). `--report` prints it
   from the saved JSON without running anything.
4. Don't change any test or runner: this job only measures (William, 2026-11-28: no cuts until he agrees, T152).

What can fail:
- A test run by the inventory leaves files behind or uses a port a running Napkin owns. Check: run it while Napkin is
  open and `git status` stays clean apart from tests/test_inventory.json; the quick run uses `--out` in scratch/.
- A check name holds the detail text (`FAIL x  {...}`), so names change from run to run. Check: names are cut at the
  two-space detail separator, and two runs on the same tree give the same names.

Checks:
- `tools/test_test_inventory.py` (summary line `TEST INVENTORY TESTS: N passed, M failed`): parsing a summary plus
  PASS/FAIL lines, a file whose counts don't add up gets `parsed: false`, detail text is cut off, the sort is stable.
- Run it for real, commit tests/test_inventory.json, and paste the report into your response.
- `tools/TEST_BEFORE_MERGING.sh` passes.
