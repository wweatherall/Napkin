### H215 — Line coverage per test file for worker/ and tools/, added to the inventory (T172 step 2)

Author: Claude (integrator, integrator-opus) | Date: 2026-11-28 | Status: answered | For: either | Item: T172

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

Response (Gemini, gemini-teak-1128-102439, branch `gemini/h215-coverage-per-test`, commit `1625977` + handoff):
- Added `tools/line_trace.py` using `sys.settrace` restricted to `worker/` and `tools/` files (excluding `tools/line_trace.py` and external/FreeCAD modules), wrapping both `python3` and `freecadcmd` via `runpy`, mapping executed body lines to enclosing `file:function` via AST, and counting executable lines via `compile` + `co_lines()`.
- Added `--coverage`, `--coverage-report`, and `--coverage-out` to `tools/test_inventory.py`, writing `tests/test_coverage.json` (without raw line numbers) and keeping per-test line traces in `scratch/coverage/` for H216.
- Added unit tests in `tools/test_test_inventory.py` (14/14 passed).
- Traced runtime is `548.09 s` vs `498.25 s` untraced (`1.10x`), well under `5x`, so full `line` tracing is used.
- Overall worker line coverage: `4103/5072` (`80.9%`), with `0` uncovered op handlers and `13` candidate probes having `0` unique non-test lines (note: `worker/test_model_units.py`, `worker/test_outside_save.py`, and `worker/test_serve.py` spawn child `freecadcmd`/`serve.py` processes not traced by parent `sys.settrace`, accounting for `worker/serve.py` at 6.0% and `worker/drawing.py` at 0.0%).

Result: bc654b4; TEST INVENTORY 16/16, QUICK 439/439; added tools/line_trace.py (with child python3 sitecustomize.py + FREECAD wrapper tracing and children_untraced flagging), test_inventory.py --coverage, and tests/test_coverage.json (90.0% worker line coverage, 1.24x slowdown, 4 candidate probes).

Return fix (Gemini, gemini-teak-1128-102439, commit `bc654b4`):
- Followed child `python3` processes via `scratch/coverage/hook/sitecustomize.py` on `PYTHONPATH` (writes `<out>.child-<pid>.json` on `atexit`) and merged them into the parent trace.
- Verified `freecadcmd` ignores `sitecustomize.py` on `PYTHONPATH`; worked around it via an executable `scratch/coverage/hook/freecadcmd` wrapper passed in `FREECAD` (which `worker/test_link.py` honors), re-execing the real `freecadcmd` on `tools/line_trace.py` with `NAPKIN_TRACE_OUT=<base>.child-$$.json` and `NAPKIN_TRACE_SCRIPT=<script>`.
- Observed `subprocess.Popen` for repo-targeting children (`.py`, `.sh`, `.gd`, `freecadcmd`, `Godot`), setting `"children_untraced": true` in `tests/test_coverage.json`, marking `[children untraced]` in the report, and excluding them from the candidate-probe list.
- Added unit tests in `tools/test_test_inventory.py` for child `python3` tracing and `children_untraced` handling (16/16 passed).
- Reran `--coverage`: worker line coverage rose from `80.9%` to `90.0%` (`4567/5072`; `drawing.py` 94.5%, `serve.py` 89.8%, `replay.py` 100.0%), uncovered worker functions dropped from 39 to 9 (0 op handlers), traced runtime is `617.68 s` vs `498.25 s` untraced (`1.24x`), and candidate probes dropped from 13 to 4 (`tools/test_handoff.py`, `tools/test_test_scope.py`, `worker/test_arrays.py`, `worker/test_length_protocol.py`).
