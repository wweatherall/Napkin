# Tools

Named scripts for every action a person or worker runs directly. Each script is a thin wrapper around the library modules in this folder.

- `GET_A_JOB.py` — claim the next Ready job (`job.py take`).
- `SUBMIT_JOB.py` — mark your finished job answered and ready for review (`job.py done`).
- `ANSWER_A_WORKERS_QUESTION.py` — answer a waiting worker's question (`job.py answer`).
- `RETURN_JOB.py` — return a job to the board with review notes (`job.py return`).
- `CHECK_THE_JOB_BOARD.py` — show the live job queue status (`job.py status`).
- `WAIT_FOR_THE_NEXT_JOB.py` — wait for the next worker or queue event (`job.py watch --next`).
- `RUN_THE_HOPPER.py` — run the hopper: launch one worker at a time and wake when the batch is done or needs help (`job.py hopper`).
- `REBUILD_THE_JOB_BOARD.py` — rebuild `BOARD.md`'s job table (`job.py board`).
- `MERGE_JOB.py` — review, gate, and merge a job branch into `main` (`integrate.py`).
- `MERGE_THE_BATCH.py` — merge every `done` job in stacking order with one review pause and one gate (`integrate.py --batch`).
- `HOLD_THE_INTEGRATOR_LOCK.py` — take the integrator lock (`integrator.py take`).
- `LAUNCH_A_WORKER.py` — launch a worker Terminal window with its start-up brief (`launch.py`).
- `RECORD_A_DECISION.py` — add a ruling, Work list item, question, or tunable (`log.py add`).
- `PICK_UP_A_TO_DO.py` — claim a Work list item to turn into jobs (`log.py pick`).
- `ADD_A_NOTE_TO_A_DECISION.py` — append a note to a decision or Work list item (`log.py note`).
- `NUMBER_A_NEW_ID.py` — assign real numbers to `I-new-N` / `T-new-N` / `H-new-N` placeholders (`number_ids.py`).
- `WRITE_IN_YOUR_LOG.py` — append a dated line to your `Log.md` (`personal_space.py log` / `integrator.py note`).
- `WRITE_IN_YOUR_JOURNAL.py` — append a dated line to your `Journal.md` (`personal_space.py journal`).
- `ARCHIVE_A_FINISHED_JOB.py` — archive a resolved handoff entry (`handoff.py archive`).
- `CHECK_JOBS_DONT_OVERLAP.py` — check open jobs for overlapping `Touches` (`handoff.py overlaps`).
- `dependency_map.py` — rebuild/check `docs/dependency-map.md` and find `callers` / `touches` (`python3 tools/dependency_map.py [--check | callers <f:fn> | touches <f:fn>...]`).
- `protocol_map.py` — rebuild and check the message table and references in `docs/protocol.md` (`python3 tools/protocol_map.py [--check]`).
- `../../09_Tools/MEASURE_TOKEN_USE.py` — inspect session usage and token benchmarks (moved to `comitatus/09_Tools`, P69; run `python3 ../../09_Tools/MEASURE_TOKEN_USE.py`).
- `COMPARE_TEST_SUITES.py` — compare viewport suite runs with `tests/reference/` (`compare_suites.py`).
- `CHECK_TYPED_LENGTHS_AGAINST_FREECAD.py` — regenerate `tests/length_cases.json` with `freecadcmd` (`length_cases.py`).
- `TEST_YOUR_CODE_FAST.sh` — run the quick test (`quicktest.sh`).
- `TEST_YOUR_CODE_THOROUGHLY.sh` — run the full test (`fulltest.sh`).
- `TEST_WITHOUT_THE_APP.sh` — run the headless feature tests (`featuretest.sh`).
- `TEST_BEFORE_MERGING.sh` — run the merge gate (`gate.sh`).
- `CHECK_THE_SCRIPTS_PARSE.sh` — check all viewport GDScript files parse (`parsecheck.sh`).
- `START_A_WORKER.sh` — open a Terminal window for a Claude worker (`start_worker.sh`).
- `BUILD_THE_APP.sh` — build `dist/Shop Sketch.app` (`build_app.sh`).
