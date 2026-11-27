# Habits

Habits are scripts that run by themselves (from `.githooks/`) or always hold at the start of every session.
Each script is a thin wrapper around the library code in `tools/`.

- `REMEMBER_WHO_YOU_ARE.py` — print the session start-up brief (`tools/startup.py`).
- `WHEN_THE_LOG_IS_COMMITTED_TIDY_IT.py` — sort and tidy `03_Past_Decisions/` when committed (`tools/sort_decision_log.py`).
- `WHEN_WATCHED_CODE_IS_COMMITTED_CHECK_THE_MAP.py` — check `Architecture-Impact:` trailers on commits (`tools/check_architecture.py`).
- `WHEN_MAIN_CHANGES_FILL_THE_TO_DOS.py` — sync `comitatus/06_To-dos/` from `main` (`tools/org_todos.py`).
