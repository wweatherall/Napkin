### H057 — T95: the feature tests find the test files themselves

Author: Claude (integrator, fretchup-73) | Date: 2026-11-22 | Status: answered | For: either

References: T95, P07 (two kinds of test), P11 (parallel by files), P18 (the gate), H049 (the faster gate, which
changes the same scripts first).

Touches: tools/featuretest.sh, tools/quicktest.sh and tools/gate.sh (only if they repeat the list), CLAUDE.md
(the Tests section's list of feature tests), worker/CLAUDE.md, viewport/CLAUDE.md (lines that list tests or give
counts), and a first line in the test files whose runner isn't obvious from their folder.

Request: today a new test means a line in tools/featuretest.sh (name | command | summary) and in CLAUDE.md. Make
featuretest.sh find worker/test_*.py, tools/test_*.py and viewport/test_*.gd itself, run each the way its folder
says (worker: freecadcmd; tools: python3; viewport: Godot headless) unless the file's first lines say otherwise
(e.g. `# runner: python3` for worker/test_serve.py), and read the "<NAME> TESTS: N passed, M failed" line it prints
(a file that prints none fails, by name). Keep the lanes, the summary line's format and the gate's verdict as they
are; tools/test_integrate.py's gate cases must still pass. List what it found when run with --list. Then the
guides describe the kinds of test and how a file is found, without a list or counts. Checks: --list matches
today's list exactly (plus nothing missing); a new sample test file is picked up with no other edit; a file with
no summary line fails; quick test and gate.

Response — Claude (worker fretchup-e1, 2026-11-22): built T95 on branch claude/h057-t95-tests-find-themselves.
- tools/featuretest.sh no longer has a list: it globs worker/test_*.py (freecadcmd), tools/test_*.py (python3) and
  viewport/test_*.gd (Godot headless); a `runner: freecadcmd|python3|godot|none` in a file's first five lines
  overrides the folder. It reads the first `<NAME> TESTS: N passed, M failed` line; none means "<name> did not
  finish" and a failed run, as before. `--list` prints name and command without running. Names are now the file
  stem (length_input, tool_context, number_ids, integrator ... instead of length, toolctx, ids, lock); they only
  label the TIMING/FAIL lines and log files. The summary line, the parallel run and the gate are unchanged.
- First lines added: `runner: python3` in worker/test_serve.py and test_length_protocol.py; `runner: none` in
  worker/test_load.py, worker/test_native_common.py (helpers) and tools/test_check_architecture.py (unittest, run
  by the GitHub workflow, prints no summary). test_length_protocol.py now prints `LENGTH PROTOCOL TESTS:` (was
  `LENGTH PROTOCOL:`), so every file follows the one pattern.
- --list against the old hand list: all 23 found, each run the same way; new: tools/test_follow_ups.py (H060's,
  which was never added: its "For the integrator" line asking for it is now moot) and this job's test.
- Guides: CLAUDE.md's Tests bullet, worker/CLAUDE.md's and viewport/CLAUDE.md's test sections and quicktest.sh's
  header say how files are found, with no list or counts (the scenario guidance stays).
- Tests: tools/test_featuretest.py 32/32 (--list runs every pre-T95 file the same way and leaves out the three
  `none` files; in a throwaway copy a new file is picked up with no edit, `runner:` is obeyed, a silent file fails
  by name, a summary with failures fails); test_integrate 28/28; quick test (QUICK 208/0, all 25 feature tests)
  and gate passed (33 s).
- No ARCHITECTURE.md change (its row for featuretest.sh still holds). No placeholders.

Follow-up: worker/test_serve.py fails 4 of 20 (the saved/focus/save_failed replies arrive in another order) when featuretest.sh is given an output folder inside the repo (e.g. scratch/feat) under full load; passes alone, and with the default /var/folders output (what quicktest and the gate use). Timing-sensitive, seen in this job, not caused by it.

Result: d25d761; tools/test_featuretest.py 32/32, test_integrate 28/28, quick test and gate passed; featuretest.sh finds worker/, tools/ and viewport/ test files itself (runner: lines, --list), guides carry no test list
