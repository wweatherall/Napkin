### H190 — What each step cost: a member's Log shown with the quota used between its lines

Author: Claude (integrator, opus-integrator) | Date: 2026-11-27 | Status: answered | For: gemini

References: William, 2026-11-27 ("automate the usage tracker to be smart about what's going on: include usage
alongside integrator logs so we can see the difference that section made"), H162 (the two-repo pattern: a Napkin
branch and a comitatus branch), P69 (organization tools live in comitatus/09_Tools), T117/T126 (passive job usage),
the integrator's hand count for session e3611376 (its Log, 2026-11-27 19:17), P73.

Touches: tools/startup.py (the integrator brief's "Log (... last 10 lines)" block only), tools/test_startup.py.

Also in the comitatus repo (not in Touches: the check reads Napkin paths): 09_Tools/MEASURE_TOKEN_USE.py (a `log`
subcommand), 09_Tools/SHOW_WHAT_EACH_STEP_COST.py (new), 09_Tools/test_measure_token_use.py, 09_Tools/README.md
(one line).

Reading path:
1. comitatus/04_Personal_Space/<member>/Log.md: one line per step, `YYYY-MM-DD HH:MM <what>` (local time), written by
   WRITE_IN_YOUR_LOG.py and by job.py / integrate.py (merged, answered, returned).
2. comitatus/09_Tools/MEASURE_TOKEN_USE.py: how it reads claude-usage/history.jsonl and agy-usage-monitor/
   history.jsonl and works out a quota change between two times for `report` (window resets included). Reuse that
   code: don't write a second reading of the histories.
3. Napkin's .git/shopsketch-jobs.json: each job's `taken` and `done` times and agent (which workers ran when).
4. tools/startup.py: where the integrator brief prints the Log's last 10 lines.

Today (checked 2026-11-27): the quota monitors record every few seconds, and every Log line has a time, but nothing
joins them: to see what a session cost, the integrator added up the history by hand (Claude 5h about 18% across two
windows for session e3611376), and MEASURE_TOKEN_USE.py has no view of a stretch of work, only of jobs and of a
start-up turn.

Request:
1. **`MEASURE_TOKEN_USE.py log <member> [--last N] [--since YYYY-MM-DD]`** (and `SHOW_WHAT_EACH_STEP_COST.py
   <member> ...`, a one-line wrapper, named for what it does): prints each Log line with the quota used in the
   stretch **before** it (from the previous line's time to its own: a line says what was just done, so the cost
   leading up to it is its cost): Claude 5h and 7d, Gemini 5h and weekly, in percentage points.
   - A window reset inside a stretch: count what was used on both sides of it, never the jump back up.
   - A stretch where a monitor recorded nothing: `no data` for that provider, not 0.
   - The workers that were running in the stretch (jobs whose taken–done overlaps it, from shopsketch-jobs.json):
     `workers: H183 (gemini)`, so a Gemini figure there reads as the workers' cost and a Claude figure with no Claude
     worker as the member's own. Fail-open when the jobs file isn't there.
   - A last line: totals for the lines shown.
2. **The integrator brief** (startup.py `--role integrator`): its last-10 Log lines show the Claude 5h figure for each
   (`... merged H184  [claude 5h -1.2]`), calling `log` fail-open like job.py calls the tool today (no tool, no
   histories, an error: the lines print as now).
3. Tests (09_Tools/test_measure_token_use.py): synthetic Log and histories with a reset inside a stretch, a gap with no
   data, and a job overlapping a stretch; tools/test_startup.py: the brief with and without the tool's figures.
4. Two branches, as H162: the Napkin side in your job worktree; the comitatus side in a worktree you make,
   `git -C /Users/Will/Sites/comitatus worktree add /Users/Will/Sites/comitatus/08_Code_Bases/.worktrees/comitatus/h190
   -b gemini/h190-log-with-usage`. Don't commit in comitatus's main checkout. Name both branches and commits in your
   response; the integrator merges the comitatus one first.

Not in this job: changing how Log lines are written, storing quota in the Log itself (the histories already hold it),
the job tables (`report`, `bench`), or the Journal.

What can fail:
- A brief that breaks when the histories are missing or the tool errors: the startup brief is every session's first
  step. Check: test_startup.py runs the brief with the tool absent and with it raising.
- Local time vs. the histories' epoch milliseconds: Log lines are local; convert with the machine's zone, as
  MEASURE_TOKEN_USE.py already does for jobs. Check: a test line at a known time lands in the right stretch.

Checks:
- `tools/TEST_BEFORE_MERGING.sh` passes; `python3 ../../09_Tools/test_measure_token_use.py` passes.
- `python3 ../../09_Tools/SHOW_WHAT_EACH_STEP_COST.py opus-integrator --since 2026-11-27` shows today's merges with
  figures, and the 17:58 reset of the Claude 5h window is counted, not shown as a gain.

Response — Gemini:

- Added `MEASURE_TOKEN_USE.py log <member> [--last N] [--since YYYY-MM-DD] [--space-dir DIR] [--json]` (reusing
  `load_quota_history` and `compute_quota_deltas`) and the one-line wrapper `09_Tools/SHOW_WHAT_EACH_STEP_COST.py`, plus
  a one-line entry in `09_Tools/README.md`.
- Each Log line reports Claude 5h/7d and Gemini 5h/weekly burn in percentage points over the stretch from the previous
  Log line's local timestamp to its own (reset-aware, `no data` when a monitor recorded nothing in the stretch, `0.0%`
  without double-counting when consecutive lines share the same minute), overlapping workers from `shopsketch-jobs.json`
  (fail-open when absent), and a `Total` line at the end.
- Updated `tools/startup.py` (`--role integrator`) to annotate its last-10 Log lines with `  [claude 5h -X.X]` via
  `fetch_log_claude_5h` + `annotate_integrator_log_lines` (fail-open when the tool is absent, errors, or histories are
  missing).
- Added unit tests in `09_Tools/test_measure_token_use.py` (`TestMemberLog`: reset inside a stretch, gap with `no data`,
  overlapping worker, missing jobs file, `--last`/`--since`/`--json`, local time, and `SHOW_WHAT_EACH_STEP_COST.py`)
  and `tools/test_startup.py` (Log-only annotation, absent tool, failing tool, working tool).
- Branches (merge comitatus first):
  - comitatus: `gemini/h190-log-with-usage` (`80ce492`)
  - Napkin: `gemini/h190-log-with-usage`

Result: `python3 ../../09_Tools/test_measure_token_use.py` passed (`USAGE TESTS: 20 passed, 0 failed`),
`tools/test_startup.py` passed (`STARTUP TESTS: 78 passed, 0 failed`), `tools/TEST_BEFORE_MERGING.sh` passed
(`GATE PASS (scope tools): tools quick test passes; 34 s total`), and `SHOW_WHAT_EACH_STEP_COST.py opus-integrator --since 2026-11-27`
counted the 17:58 Claude 5h reset (`18:21 merged H185` -> `claude: 5h -5.0%  7d -1.0%`) rather than showing a gain.
