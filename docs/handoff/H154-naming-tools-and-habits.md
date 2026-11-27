### H154 — One named script per action: tools named for what you do (GET_A_JOB), habits in 02_Habits

Author: Claude (integrator, napkin-77) | Date: 2026-11-26 | Status: open | For: either

Item: T149

References: T149 (this item), comitatus's proposal (docs/proposals/organization-2026-11-25.md, "Habits" and
"Tools"), P60 (the folders come later: this job renames in place), T134, T143 (usage.py may move out later).

Touches: tools/, .githooks/, CLAUDE.md, AGENTS.md, GEMINI.md, BOARD.md, ARCHITECTURE.md, README.txt, docs/integrator.md, docs/agent-handoff.md, docs/protocol.md, docs/specs/, viewport/CLAUDE.md, viewport/tools/CLAUDE.md, worker/CLAUDE.md, 03_Past_Decisions/work/, Check FreeCAD speed.command.

New folder: 02_Habits/ (not in Touches: the check needs paths that exist).

Reading path:
1. This brief's Request. William settled the names with the integrator on 2026-11-26 (below): they replace the
   proposal's FOR_<doing> form. In his words: "when you want to do a thing, you look for the thing with the name on
   it that does the thing you want and you fire that." 
2. `.githooks/pre-commit` and `.githooks/commit-msg`: what runs by itself today (the habits).
3. `git grep -n "tools/"`: every place a name is written (about 1,300 in 138 files; most are in the history files,
   which keep the old names, see below).

Today (checked 2026-11-26 on main bfb9650; recheck after H153, which changes some of these files): tools have plain
lower-case names (`job.py`, `quicktest.sh`); `SORT_PRINCIPLES.py` (now in comitatus/09_Tools, not this repo) was the first in the new style.

Request: give every action a person or worker fires its own script, named as a command for that action, and put
the habits (what runs by itself, or always holds) in a new top-level folder `02_Habits/`. **The code stays where it
is**: `tools/job.py`, `tools/log.py` and the rest keep their names and are the library; each new script is a few
lines that call one command of it (for `job.py take`: `sys.exit(job.main(["take", *sys.argv[1:]]))`, run from any
directory). Tests, imports between modules and the hooks keep using the library names, so nothing breaks. What
changes is what people and agents are told to type: guides, the start-up brief (`startup.py`'s checklists), tool
usage lines and messages that say "run tools/job.py take ..." now name the new script.

Tools (in `tools/`, `.py` for Python, `.sh` for shell; keep the names exactly):

| Library command now | New script |
|---|---|
| job.py take | GET_A_JOB.py |
| job.py done | SUBMIT_JOB.py |
| job.py answer | ANSWER_A_WORKERS_QUESTION.py |
| job.py return | RETURN_JOB.py |
| job.py status | CHECK_THE_JOB_BOARD.py |
| job.py watch --next | WAIT_FOR_THE_NEXT_JOB.py |
| job.py board | REBUILD_THE_JOB_BOARD.py |
| integrate.py | MERGE_JOB.py |
| integrator.py take | HOLD_THE_INTEGRATOR_LOCK.py |
| launch.py | LAUNCH_A_WORKER.py |
| log.py add | RECORD_A_DECISION.py |
| log.py pick | PICK_UP_A_TO_DO.py |
| log.py note | ADD_A_NOTE_TO_A_DECISION.py |
| number_ids.py | NUMBER_A_NEW_ID.py |
| personal_space.py log / integrator.py note | WRITE_IN_YOUR_LOG.py |
| personal_space.py journal | WRITE_IN_YOUR_JOURNAL.py |
| handoff.py archive | ARCHIVE_A_FINISHED_JOB.py |
| handoff.py overlaps | CHECK_JOBS_DONT_OVERLAP.py |
| usage.py | MEASURE_TOKEN_USE.py (all its subcommands, passed through) |
| compare_suites.py | COMPARE_TEST_SUITES.py |
| length_cases.py | CHECK_TYPED_LENGTHS_AGAINST_FREECAD.py (run with freecadcmd, as now) |
| quicktest.sh | TEST_YOUR_CODE_FAST.sh |
| fulltest.sh | TEST_YOUR_CODE_THOROUGHLY.sh |
| featuretest.sh | TEST_WITHOUT_THE_APP.sh |
| gate.sh | TEST_BEFORE_MERGING.sh |
| parsecheck.sh | CHECK_THE_SCRIPTS_PARSE.sh |
| start_worker.sh | START_A_WORKER.sh |
| build_app.sh | BUILD_THE_APP.sh |

Commands not in the table (job.py beat/check/guard-checkout/run/test/wait/reassign, log.py set/show, handoff.py
list/split/check, integrator.py status) are run by other tools and hooks: they get no script.

Habits (in `02_Habits/`, same few-line form):

| Library now | New script |
|---|---|
| startup.py | REMEMBER_WHO_YOU_ARE.py (William: an always-on command; no "WHEN_" in front) |
| sort_decision_log.py | WHEN_THE_LOG_IS_COMMITTED_TIDY_IT.py |
| check_architecture.py | WHEN_WATCHED_CODE_IS_COMMITTED_CHECK_THE_MAP.py |
| org_todos.py | WHEN_MAIN_CHANGES_FILL_THE_TO_DOS.py |

`02_Habits/README.md` says in a few lines what a habit is and lists them; `tools/README.md` (new) lists the tool
scripts, one line each, what you fire it for. The hooks call the habit scripts.

Rules that go with it:
1. **Each new script is only a call**: no logic of its own, so the library's tests cover it. Write one check that
   runs every new script with `--help` (or its library's equivalent harmless call) from a different directory and
   sees it reach the library.
2. **Names are exact.** A name that turns out wrong in use is a later change, not this job's.
3. **History keeps the old names**: don't rewrite `03_Past_Decisions/decision-archive.md`, `03_Past_Decisions/rulings/`,
   `docs/handoff-archive.md`, `docs/proposals/`, closed `docs/handoff/` entries, or `tests/reference/`. Live guides
   (CLAUDE.md, AGENTS.md, GEMINI.md, docs/integrator.md, docs/agent-handoff.md, the part CLAUDE.md files, README.txt,
   `Check FreeCAD speed.command`) and the live Work list are rewritten to the new names.
4. **The app bundle**: `build_app.sh` is watched code (check_architecture.py's `watched` list). If the change to it or
   to the list needs it, the commit says `Architecture-Impact: in the handoff - <this ID>` with an `Architecture:` line.
5. **Nothing else changes**: no behaviour, output (other than names in instructions) or option of any tool.
6. `tools/test_named_scripts.py` (new) also checks that no live guide tells you to type an old command
   (`tools/job.py take`, `tools/quicktest.sh` ...) where a new script exists. The feature tests pick it up.

What can fail:
- A guide still saying the old command: item 6 finds it.
- A script that only works from the repo root: item 1 runs them from elsewhere.
- Agents' habits: Claude, Codex and Gemini type `tools/job.py` from memory. The old commands keep working, so nothing
  breaks; say in your response which guides you changed; the integrator updates Claude's memory files.

Checks:
- tools/test_named_scripts.py (new): every script in both tables exists and reaches its library command; no live guide
  names an old command; history files untouched.
- `tools/featuretest.sh --list` finds the same tests as before plus the new one (quote both counts).
- The gate (`tools/gate.sh`) passes.
