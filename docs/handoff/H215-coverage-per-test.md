### H215 — Line coverage per test file for worker/ and tools/, added to the inventory (T172 step 2)

Author: Claude (integrator, integrator-opus) | Date: 2026-11-28 | Status: queued (after H214) | For: either | Item: T172

References: H214 (the inventory this adds to); William, 2026-11-28 (dense tests, quoted in H214); T172, T171, T152.

Today: once H214 merges, `tools/test_inventory.py` runs every feature test and writes `tests/test_inventory.json`.
Nothing says which code each test runs. FreeCAD's Python (3.11.14 in freecadcmd) has no `coverage` module
(`freecadcmd -c "import coverage"` fails); plain `python3` (for tools/ tests) may or may not, so don't depend on it.

Touches: tools/test_inventory.py (new in H214; `--coverage`), tools/line_trace.py (new), tools/test_test_inventory.py (new in H214),
tests/test_inventory.json (new in H214), tests/test_coverage.json (new, generated). The integrator updates the tools README at merge.

Request:
1. Write `tools/line_trace.py`: run a test file under a line tracer (`sys.settrace`, which 3.11 has; keep it to files
   under worker/ and tools/ of this repo, so FreeCAD's own code isn't traced) and write the set of `file:line` pairs it
   ran, plus which `def`s (`file:function`) those lines sit in, to a JSON file. It has to wrap both runners: under
   freecadcmd it is the script freecadcmd runs and it runs the test file with `runpy`; check that the test still prints
   its summary line and gets the same counts it does untraced.
2. `tools/test_inventory.py --coverage` runs every worker and tools test file through it (viewport files: no tracer
   exists for GDScript; leave them out and say so in the report) and writes `tests/test_coverage.json`: per test file,
   the functions it runs and its line count. Keep the lines themselves out of the committed file (they change with every
   edit); keep them in scratch/ for H216.
3. Report: per worker module, the share of its lines that some test runs; the functions no test runs (an op handler
   in that list is a red flag); and, for each test file, the lines only it runs (unique coverage). A file with none is
   a candidate probe, not a cut (William, 2026-11-28: no cuts until he agrees).
4. Say how much slower a traced run is; if over ~5×, trace only `def`-entry events (`call`) for the function list and
   say what the line numbers then lose.

Checks:
- `tools/test_test_inventory.py`: a tiny traced script gives the expected lines and functions; a traced test keeps its
  summary line and counts; FreeCAD's own files aren't in the output.
- Run it for real, commit tests/test_coverage.json, paste the report into your response.
- `tools/TEST_BEFORE_MERGING.sh` passes.
