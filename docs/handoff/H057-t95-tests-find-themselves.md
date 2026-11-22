### H057 — T95: the feature tests find the test files themselves

Author: Claude (integrator, fretchup-73) | Date: 2026-11-22 | Status: queued (after H049) | For: either

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
