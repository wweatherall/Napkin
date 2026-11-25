### H147 — T131: Quiet-by-default tool tests (failures + summary; -v/--verbose for PASS lines)

Author: Gemini (integrator, gemini-cedar-1124-2201) | Date: 2026-11-24 | Status: answered | For: either

References: T131.

Touches: tools/test_bookkeeping.py, tools/test_featuretest.py, tools/test_follow_ups.py, tools/test_handoff.py, tools/test_integrate.py, tools/test_integrator.py, tools/test_job.py, tools/test_log_archive.py, tools/test_log.py, tools/test_number_ids.py, tools/test_sort_decision_log.py, tools/test_start_worker.py, tools/test_startup.py.

Reading path:
1. `tools/test_job.py` (lines 1–35) and `tools/test_integrate.py` (lines 1–30) — typical `check(name, ok, detail="")` helper printing `PASS ` on every check.
2. `tools/featuretest.py` (read-only) — verify how `featuretest.py` invokes `tools/test_*.py` and checks their exit codes / summaries.

Today (verified 2026-11-24 on `main`):
- All 13 `tools/test_*.py` scripts print a `PASS <name>` line for every single passing assertion (`test_job.py` + `test_integrate.py` alone print ~275 lines / ~20 KB of stdout), flooding agent context windows when run directly.
- Each script also prints a final summary line (e.g. `JOB TESTS: 192 passed, 0 failed`) and exits `0` on pass, `1` on failure.

Request:
- Across all 13 `tools/test_*.py` files listed in `Touches`:
  - By default (no `-v` / `--verbose` flag), suppress `PASS ...` lines and print ONLY `FAIL ...` lines (with detail) plus the final summary line (`<SUITE> TESTS: N passed, M failed`).
  - When `-v` or `--verbose` is passed on the command line (e.g. `python3 tools/test_job.py -v`), print every `PASS ...` line just like before, so debugging individual checks stays easy.
  - Keep exit codes, summary lines, and every single test assertion unchanged.
  - Do not break any test that inspects a subprocess's stdout (if any test itself runs another `test_*.py` and asserts on `PASS`, pass `-v` there or keep that assertion green).

Checks:
- Run each of the 13 `tools/test_*.py` scripts both without flags (verify 0 `PASS ` lines, summary line printed, exit 0) and with `-v` (verify `PASS ` lines printed, exit 0).
- Run `python3 tools/job.py test` to confirm `tools/featuretest.py` and the full quick test pass cleanly.

#### Response (Gemini, 2026-11-24)

Branch: `gemini/h147-quiet-tool-tests` | Commit: `ffc7a0b`

- Updated all 13 `tools/test_*.py` scripts listed in `Touches` so `check(...)` suppresses `PASS ` lines by default and prints only `FAIL ` lines plus the final `<SUITE> TESTS: N passed, M failed` summary line.
- Added `VERBOSE = "-v" in sys.argv[1:] or "--verbose" in sys.argv[1:]` in each script so passing `-v` or `--verbose` prints every `PASS ` line as before.
- Verified:
  - Ran all 13 `tools/test_*.py` scripts without flags (0 `PASS ` lines, summary line printed, exit 0) and with `-v` (`PASS ` lines printed, summary line printed, exit 0).
  - Ran `python3 tools/job.py test` on `ffc7a0b`: parse passed (8 s), feature tests passed (118 s), viewport tests passed (85 s; QUICK 359 passed, 0 failed).
- IDs added: none.
- Open questions: none.

Result: ffc7a0b; all 13 tools/test_*.py quiet/verbose + quicktest passed; quiet-by-default tool tests with -v/--verbose for PASS lines
