### H160 — Tests run by what changed: organization-only branches skip the app's tests

Author: Claude (integrator, napkin-77) | Date: 2026-11-26 | Status: answered | For: gemini

Item: T151

References: T151 (this item), P18 (the gate), T90 (gate reuses quick checks), T95 (featuretest finds tests),
H096/H109 and H154's first gate (app-test timing flakes that failed tools-only jobs).

Touches: tools/gate.sh, tools/quicktest.sh, tools/test_scope.py (new), tools/test_test_scope.py (new),
tools/featuretest.sh (only if it needs a way to run a subset), docs/integrator.md, CLAUDE.md.

Reading path:
1. `tools/gate.sh` from `run_stage "gate: quick test"` to the end: what it runs, and how it reads `quick.log`
   (the `features:` and `| viewport: QUICK` lines) to decide GATE PASS.
2. `tools/quicktest.sh`: parse, viewport lanes and `featuretest.sh` side by side (what `job.py test` runs).
3. `tools/featuretest.sh --list`: suites are named by folder (`tools-job`, `worker-scenario`, `viewport-units` ...).
4. `tools/integrate.py` around `gate = os.path.join(root, "tools", "gate.sh")`: the gate runs in the main checkout
   with the branch's merge **staged, not committed** (HEAD is main).

Today (checked 2026-11-26 on main a7d9f1c): every gate and quick run does everything: parse, the Godot viewport
lanes, every feature suite (FreeCAD worker suites too) and the full test's viewport and compare suites (~100 s at
merge, plus the worker's own run). H154 and H158 touched only tools, guides and personal spaces, so none of the
app checks could have caught anything, and a movetest timing flake failed H154's first gate.

Request: pick the tests from the files the change touches, and run everything whenever unsure.
1. `tools/test_scope.py` prints one word, `tools` or `full`, then the files that decided it. The changed files are:
   in a job worktree, `git diff --name-only <merge-base of HEAD and main>` (committed and uncommitted, so it widens,
   never narrows); in the main checkout during a merge, `git diff --name-only HEAD` (index and working tree, which
   holds the staged merge). No base found, git failing, or no changed files at all: `full` (nothing to go on).
2. `tools` only when **every** changed file is in this list (anything else, including a new top-level folder, is
   `full`, so a kind of file nobody thought of is tested, not skipped):
   - `tools/**`, **except** the test runners and the app tools: `tools/gate.sh`, `quicktest.sh`, `fulltest.sh`,
     `featuretest.sh`, `parsecheck.sh`, `build_app.sh`, `start_worker.sh`, `compare_suites.py`, `length_cases.py`,
     `test_scope.py` itself, and their named scripts (`TEST_*.sh`, `CHECK_THE_SCRIPTS_PARSE.sh`, `BUILD_THE_APP.sh`,
     `START_A_WORKER.sh`, `COMPARE_TEST_SUITES.py`, `CHECK_TYPED_LENGTHS_AGAINST_FREECAD.py`): those change how
     app tests run, so they run the app tests;
   - `.githooks/**`, `02_Habits/**`, `01_Principles/**`, `03_Past_Decisions/**`, `docs/**`;
   - Markdown files at the top level (`BOARD.md`, `CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, `ARCHITECTURE.md`,
     `README.txt` too).
   `viewport/`, `worker/`, `tests/`, `models/`, `materials/`, `examples/`, `sim/`, `dist/`, `*.command`,
   `common.sh` and anything unlisted: `full`.
3. With `tools`: `quicktest.sh` runs the parse check (cheap, catches a broken hook-time script) and only the
   `tools-*` feature suites; no viewport lanes, no worker or viewport suites. `gate.sh` runs that quick test and
   skips the full test. Both print the scope first, e.g. `gate: scope tools (12 files; app tests skipped:
   tools/job.py ...)`, and GATE PASS / FAIL names it (`GATE PASS (scope tools): ...`), so a reader of the merge
   log can see what was and wasn't run. The gate's pass rules are unchanged otherwise: every suite that runs must
   pass; the known-failures list still only excuses viewport quick failures.
4. With `full`: exactly today's behaviour and output, apart from the scope line.
5. `--full` on `gate.sh` and `quicktest.sh` (and `GATE_FULL=1` in the environment, so `integrate.py` and
   `job.py test` pass it through without new options) forces the full run, for a change whose risk the list
   can't see.

What can fail:
- An app file classified `tools` (the worst case: an untested app change merges). Check: test_test_scope.py, one
  case per `full` entry above (a file in each folder, each runner, each named runner script, an unknown top-level
  file), each `full`.
- A tools change that breaks how tests run (a runner): the runners are `full`. Check: same cases.
- The gate during a merge reading the wrong diff (HEAD is main, the merge only staged). Check: test_test_scope.py in
  a temp repo: a staged change to `viewport/x.gd` is `full`, a staged change to `tools/job.py` only is `tools`.
- No base, or a detached HEAD, or git failing: `full`. Check: test_test_scope.py.
- gate.sh misreading a tools-scope quick log (it looks for `| viewport: QUICK`): a tools-scope pass must still be
  GATE PASS, a failing `tools-*` suite still GATE FAIL. Check: run `tools/gate.sh` on a branch changing one tools
  file (quote the output) and once with a tools suite made to fail (quote it, then undo).
- The full run changing by accident. Check: `tools/gate.sh --full` output matches today's apart from the scope line.

Checks:
- tools/test_test_scope.py (new; featuretest picks it up as `tools-test_scope`): the cases above.
- `tools/gate.sh` on this branch: it changes `gate.sh` and `quicktest.sh`, so it must say `scope full` and run
  everything (quote the scope line and GATE PASS).
- The two runs in "What can fail" quoted in the response.
- docs/integrator.md's "Review and merge" and CLAUDE.md's testing lines say in a line each what a tools-scope gate skips and
  that `--full` / `GATE_FULL=1` forces everything.

### Response
Result: added `tools/test_scope.py` (with `# runner: none`), `tools/test_test_scope.py` (54/54), `--tools-only` on `tools/featuretest.sh`, and scope-aware `--full` / `GATE_FULL=1` support in `tools/quicktest.sh` and `tools/gate.sh`; documented in `docs/integrator.md` and `CLAUDE.md`; full gate (`GATE PASS`, 399/399 quick) and `job.py test` pass on `a766530`.

- `tools/gate.sh` on this branch (`a766530`):
  - `scope full (4 file(s): tools/featuretest.sh tools/gate.sh tools/quicktest.sh tools/test_scope.py)`
  - `GATE PASS: full test passes; QUICK 399 passed, 0 failed in 31.6 s ; 0 known failure(s); 84 s total`
- `tools/gate.sh` on a scratch branch changing one tools file (`tools/usage.py`):
  - `scope tools (1 file(s); app tests skipped: tools/usage.py)`
  - `GATE PASS (scope tools): tools quick test passes; 44 s total`
- `tools/gate.sh` on a scratch branch with `tools/test_usage.py` made to fail:
  - `scope tools (2 file(s); app tests skipped: tools/test_usage.py tools/usage.py)`
  - `NEW FAILURE: feature tests:  USAGE TESTS: 0 passed, 1 failed;`
  - `GATE FAIL (scope tools): 1 new quick-test failure(s); 43 s total`
- `Changed from the brief:` `gate.sh` prints `scope tools (...)` / `scope full (...)` without the `gate: ` prefix because `tools/test_featuretest.py` checks `re.findall(r"^gate: .+$", output, re.M)` against the four `gate: quick/full test started/passed` lines; `quicktest.sh` still prints `quick: scope ...` so `run_logged` forwards it.
