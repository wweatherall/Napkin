### H154 — Tools and habits take the organization's names: FOR_<doing>.py and WHEN_<this>_<DO_THAT>.py

Author: Claude (integrator, napkin-77) | Date: 2026-11-26 | Status: draft (names being settled with William; not a job yet) | For: either

Item: T149

References: T149 (this item), comitatus's proposal (docs/proposals/organization-2026-11-25.md, "Habits" and
"Tools"), P60 (the folders come later: this job renames in place), T134, T143 (usage.py may move out later).

Touches: tools/, .githooks/, CLAUDE.md, AGENTS.md, GEMINI.md, BOARD.md, ARCHITECTURE.md, README.txt, docs/integrator.md, docs/agent-handoff.md, docs/protocol.md, docs/specs/, viewport/CLAUDE.md, viewport/tools/CLAUDE.md, worker/CLAUDE.md, 03_Past_Decisions/decision-log.md, Check FreeCAD speed.command.

Reading path:
1. The proposal's two sections: a habit is a script "in the form IF ___ HAPPENS DO ___.py or WHEN ___ HAPPENS DO
   ___.py. They do what the name says"; a tool is "named FOR_<noun form of the verb, and the object>.py".
2. `.githooks/pre-commit` and `.githooks/commit-msg`: what runs by itself today (the habits).
3. `git grep -n "tools/"`: every place a name is written (about 1,300 in 138 files; most are in the history files,
   which keep the old names, see below).

Today (checked 2026-11-26 on main bfb9650; recheck after H153, which changes some of these files): tools have plain
lower-case names (`job.py`, `quicktest.sh`); `SORT_PRINCIPLES.py` is the first in the new style.

Request: rename with `git mv` (history follows the files) and rewrite every reference with one script you write and
keep, `tools/FOR_RENAMING_TOOLS.py` (a table old -> new, applied to tracked text files), so the change is one
mechanical pass and can be run again on a branch made before it. The names (keep them exactly; a name that turns out
wrong in use is a later change, not this job's):

| Now | New | Kind |
|---|---|---|
| job.py | FOR_RUNNING_THE_JOB_QUEUE.py | tool | GET_A_JOB
| integrate.py | FOR_MERGING_A_JOB.py | tool | MERGE_JOB
| integrator.py | FOR_HOLDING_THE_INTEGRATOR_LOCK.py | tool | HOLD_THE_INTEGRATOR_LOCK
| startup.py | WHEN_YOU_START_UP_REMEMBER_WHO_YOU_ARE.py | habit (the proposal's own example) | REMEMEMBER_WHO_YOU_ARE
| launch.py | FOR_LAUNCHING_A_WORKER.py | tool | LAUNCH_A_WORKER
| log.py | FOR_RECORDING_DECISIONS.py | tool | RECORD_A_DECISION
| handoff.py | FOR_KEEPING_THE_HANDOFF.py | tool | not sure, let's talk
| number_ids.py | FOR_NUMBERING_NEW_IDS.py | tool | NUMBER_A_NEW_ID
| personal_space.py | FOR_KEEPING_A_LOG_AND_JOURNAL.py | tool | how does this tool work? it seems overloaded
| SORT_PRINCIPLES.py | FOR_SORTING_PRINCIPLES.py | tool | SORT_PRINCIPLES
| usage.py | FOR_MEASURING_TOKEN_USE.py | tool | MEASURE_TOKEN_USE
| compare_suites.py | FOR_COMPARING_TEST_SUITES.py | tool | COMPARE_TEST_SUITES
| cut_chain_check.py | FOR_TIMING_CUT_CHAINS.py | tool | not sure what this tool does
| length_cases.py | FOR_CHECKING_LENGTH_CASES.py | tool | not sure what this tool does
| atomize_log.py | FOR_ATOMIZING_THE_LOG.py | tool | ATOMIZE_YOUR_LOG
| quicktest.sh | FOR_QUICK_TESTING.sh | tool | TEST_YOUR_CODE_FAST
| fulltest.sh | FOR_FULL_TESTING.sh | tool | TEST_YOUR_CODE_THOROUGHLY
| featuretest.sh | FOR_FEATURE_TESTING.sh | tool | not sure what this tool does
| gate.sh | FOR_GATING_A_MERGE.sh | tool | not sure what this tool does
| parsecheck.sh | FOR_PARSE_CHECKING.sh | tool | not sure what this tool does
| start_worker.sh | FOR_STARTING_A_FREECAD_WORKER.sh | tool | START_A_WORKER
| build_app.sh | FOR_BUILDING_THE_APP.sh | tool (watched code: see below) | BUILD_THE_APP
| sort_decision_log.py | WHEN_THE_LOG_IS_COMMITTED_TIDY_IT.py | habit (the hook runs it) |good
| check_architecture.py | WHEN_WATCHED_CODE_IS_COMMITTED_CHECK_THE_MAP.py | habit (the hooks run it) | good
| org_todos.py | WHEN_MAIN_CHANGES_FILL_THE_TO_DOS.py | habit (the hook runs it) | good

Rules that go with it:
1. **Tests keep their names** (`tools/test_job.py` etc.): they are found by `test_*`, and that convention is the test
   runner's, not a tool's. Rename their imports (`import job` -> `import FOR_RUNNING_THE_JOB_QUEUE as job`, so the
   test bodies stay as they are).
2. **Modules that import each other** do the same (`import FOR_RUNNING_THE_JOB_QUEUE as job`), so code reads as before.
3. **The git hooks keep git's names** (`.githooks/pre-commit`, `commit-msg`); their bodies call the habit scripts.
   Split `pre-commit`'s blocks only if that's needed to keep it working; a later job can make each block its own habit.
4. **History keeps the old names**: don't rewrite `03_Past_Decisions/decision-archive.md`, `03_Past_Decisions/rulings/`
   (each ruling's text is what was decided), `docs/handoff-archive.md`, `docs/proposals/`, `docs/handoff/` entries
   other than ones still open, or `tests/reference/`. The live decision-log's Work list and Tunables `Where` cells are
   rewritten (they are where things are now).
5. **The app bundle**: `tools/FOR_BUILDING_THE_APP.sh` is watched code (`check_architecture.py`'s `watched` list
   names it): update the list, and the commit says `Architecture-Impact: in the handoff - <this ID>` with an
   `Architecture:` line.
6. **Nothing else changes**: no behaviour, output or option of any tool. A tool's output that names itself (a usage
   line, "run tools/job.py ...") says its new name.
7. `tools/FOR_RENAMING_TOOLS.py --check` exits 1 if any tracked file outside the history list still names an old
   tool path (`tools/job.py`, `tools/quicktest.sh` ...): the feature tests run it, so an old name can't come back.

What can fail:
- A reference missed: `--check` finds it (item 7), and the gate runs every tool through its tests.
- An import cycle or a name clash from `as` imports: the feature tests and quick test catch it.
- Agents' habits: Claude, Codex and Gemini type `tools/job.py` from memory. Say in your response which guides you
  changed; the integrator updates Claude's memory files outside the repo.
- A branch made before the rename (none should be open: this job runs alone): `FOR_RENAMING_TOOLS.py` run on it
  rewrites its references.

Checks:
- tools/test_renaming_tools.py (new): "every old name in the table maps to a file that exists under its new name";
  "--check fails on a file that names tools/job.py and passes on main after the rename"; "history files are left
  as they are".
- `tools/FOR_FEATURE_TESTING.sh --list` finds the same tests as before (same count; quote both counts).
- The gate (`tools/FOR_GATING_A_MERGE.sh`) passes.
