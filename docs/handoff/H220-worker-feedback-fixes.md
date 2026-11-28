### H220 — Small tools fixes from worker feedback and the integrator's follow-ups

Author: Claude (integrator, integrator-opus) | Date: 2026-11-28 | Status: open | For: either

References: William, 2026-11-28: "yes, the small fixes as a job"; docs/worker-feedback.md (H207: `handoff.py` with no
command); docs/follow-ups.md (integrator, 2026-11-27: `startup.waiting_handoffs` false positives; `number_ids` renaming
placeholders inside test fixtures, which broke 3 tests at P75). Already fixed and not part of this job: GET_A_JOB copying
a stacked job's brief (H211), the gate's pass counting for SUBMIT_JOB, RECORD_A_DECISION passing tunable arguments, the
hopper picture test's fixed queue.

Today:
- `tools/startup.py` `waiting_handoffs` lists an open or queued handoff as waiting on William whenever its text matches
  `ASK` (`\bask William\b`) with no "William's answer" after it. A brief that only says to ask him later (H193's "what
  to ask William", H194's "stop and ask William") lands in "Waiting on William" and in `comitatus/06_To-dos/
  waiting_on_William/` before anything was asked.
- `tools/number_ids.py` `SKIP` holds `tools/test_number_ids.py` and `tools/test_log_archive.py`, but
  `tools/test_integrate.py` (7 placeholders) and `tools/test_log.py` (1) also use placeholders such as `P-new-1` as
  fixture text: the first real P-new-1 ruling after them (P75) renamed those too and broke 3 tests until restored.
- `python3 tools/handoff.py` with no command prints its whole usage text (about 20 lines).

Touches: tools/startup.py (`waiting_handoffs` and its caller only), tools/test_startup.py, tools/number_ids.py (`SKIP`),
tools/test_number_ids.py, tools/handoff.py (its no-command case only), tools/test_handoff.py. The integrator clears the
two follow-up lines at merge.

Request:
1. `waiting_handoffs`: a handoff waits on William only when a question to him is actually pending, so the list and the
   to-dos mean "William has something to answer now": its job is `waiting` in the queue on a non-scope question
   (`job.py wait "<q>"`), or its entry has a response asking him something (a `Response` section with an "Ask William"
   or "Question for William" line) with no "William's answer" after it. A brief's own text asking him later no longer
   counts. Keep the other sources of "Waiting on William" (Work list "your call" items, Tentative principles, board
   notes) as they are.
2. `number_ids.py`: skip every `tools/test_*.py` (they are fixtures, not records), so a merge never renames their
   placeholder text; keep the explicit SKIP entries' comment true.
3. `handoff.py` with no command: print the open jobs read-only (what `list` would write, without writing) and one line
   naming the commands (`list`, `tidy`, `split`, `check`, `overlaps`, `archive`; `--help` for the full text).

Checks:
- `tools/test_startup.py`: a brief saying "stop and ask William" with no question pending isn't waiting; a job waiting on
  a William question is; a response asking William with no answer is; one with "William's answer" after it isn't.
- `tools/test_number_ids.py`: a placeholder inside a `tools/test_*.py` file is left alone when a row defines it.
- `tools/test_handoff.py`: no command prints the open list and the one-line hint, and writes nothing.
- `tools/TEST_BEFORE_MERGING.sh` passes.
