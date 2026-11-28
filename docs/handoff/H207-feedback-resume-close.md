### H207 — Workers give feedback at every submit and resubmit; resume commands are recorded; windows close after the merge

Author: Claude (integrator, opus-integrator) | Date: 2026-11-27 | Status: answered | For: gemini

References: William, 2026-11-27 ("after the jobs pass, the hopper could ask the coder windows for feedback, which I've
been doing by hand, then close the window after they give it; and record the restart key the Gemini coders give, so
if you need to relaunch one with context to fix its work you can do so easily"), the two Gemini feedback answers he
pasted the same evening (what a good answer looks like), H185/H196 (the hopper), T134 (launch.py), H195/H206
(finding an agent's session from its rollouts and transcripts), P73.

Touches: tools/job.py (`done`: the feedback and the resume command; the hopper: closing a merged job's window, and
resuming a returned job's session), tools/launch.py (each agent's resume command; recording the window and process it
opened; closing them), tools/startup.py (the integrator brief shows feedback not yet read), docs/worker-feedback.md
(new), tools/test_job.py, tools/test_launch.py, tools/test_startup.py, tools/README.md (if a script is added).

Reading path:
1. tools/launch.py `agent_command` and `open_terminal`: how a window is opened (AppleScript `do script`, which returns
   the tab and window it made) and what is known about the session then (its name; Claude's `--remote-control` name).
2. tools/job.py `done`, `return_job`, and the hopper's launch step: where a job is submitted, put back, and relaunched.
3. How each agent resumes a session: Claude `claude --resume <session id>`, Gemini `agy --conversation <id>`, Codex
   `codex resume <id>`; and how 09_Tools/MEASURE_TOKEN_USE.py (comitatus repo) matches a job's worktree to its Claude
   transcript, Gemini (agy) brain transcript, and Codex rollout to find that id.

Request:
1. **Feedback at every submit** (William, 2026-11-27: ask when they submit, and again if they have to resubmit).
   `SUBMIT_JOB.py` refuses until the worker answers the two questions William asked by hand, "How was working on
   this job in our code base?" and "Any improvements you can think of?" (`SUBMIT_JOB.py --feedback "<answer 1>"
   --improvements "<answer 2>"`). On a resubmit after a return, the first question becomes "How was the review
   round: were the return notes clear, and what would have avoided the return?". Each answer goes to
   docs/worker-feedback.md as one dated entry (job, agent, session, first submit or resubmit, both answers),
   committed with the job. Asking in the session at submit needs no window typed into, and the conversation's cache
   is still warm.
2. **Resume command.** At submit, record the session's resume command in the job's state (for example
   `agy --conversation 1f3e...` run from the job's worktree), found from the agent's own transcript or rollout as
   H195/H206 do; `job.py status` shows it, and the integrator brief lists it for jobs on the desk.
3. **Resume on return.** When the integrator returns a job and its resume command is known, the hopper relaunches by
   resuming that session in a new window with the return notes as the first message, instead of a fresh worker; with
   no resume command it launches fresh as today.
4. **Close after merge.** launch.py records the window and the agent's process it opened. After a job merges, the
   hopper ends that agent's process and closes its window; a job returned or still
   on the desk keeps its window open until its merge. A window William opened by hand (not recorded) is never touched.
5. The integrator brief shows feedback entries not yet read, and the integrator marks them read
   (`docs/worker-feedback.md` keeps them all).
6. Tests for each: a submit without feedback is refused; a resubmit asks the review-round question; the entry is written; the resume command is recorded and
   used on return; a merged job's recorded window is closed and an unrecorded one isn't (with launch's AppleScript
   faked).

What can fail:
- Closing the wrong window, or one with unsaved work (G09). Check: only a recorded window id is closed, only after
  its job merged, and only once its process has ended.
- A resume that loads another session's conversation. Check: the recorded id is the one whose transcript matches the
  job's worktree; a test with two sessions in the same hour picks the right one.

Checks:
- `tools/TEST_BEFORE_MERGING.sh` passes (tools scope).

Response — Gemini (worker, gemini-teak-1127-231349), 2026-11-27:
- Branch: `gemini/h207-feedback-resume-close` (code commit `792fc7f`).
- Implemented:
  - `tools/job.py`: `done()` now requires `--feedback` and `--improvements` (asking the first-submit questions or the resubmit review-round question when `returned` is set), appends a dated entry to `docs/worker-feedback.md` and commits it, and records `resume_cmd` via `find_resume_command()` (matching worktree in AGY brain transcripts, Claude `sessions.jsonl`, or Codex `rollout-*.jsonl`, ignoring integrator transcripts). `job.py status` shows `resume_cmd`. Added `feedback-read` subcommand to mark entries read in queue state while keeping all entries in `docs/worker-feedback.md`. `hopper_step` resumes returned jobs with `resume_cmd` via `launch.launch_resume` and closes recorded windows via `_close_merged_windows` only after `state == "merged"` and all recorded/tty agent processes have exited.
  - `tools/launch.py`: added `resume_prompt`, `resume_command`, `open_terminal_window` (recording Terminal window `id`, `tty`, and `pid`), `tty_pids`, `close_terminal`, `launch_agent`, and `launch_resume`.
  - `tools/startup.py`: `collect_live_jobs` and `integrator_next_actions` include `resume_cmd` for jobs on the desk; `unread_worker_feedback` shows unread `main:docs/worker-feedback.md` entries in the integrator brief; `role_brief("worker")` notes `--feedback` and `--improvements`.
  - `docs/worker-feedback.md`: created feedback log.
  - Tests: `tools/test_job.py` (241/241), `tools/test_launch.py` (28/28), `tools/test_startup.py` (83/83).
- Result: 792fc7f; JOB 241/241, LAUNCH 28/28, STARTUP 83/83; feedback at submit/resubmit, resume_cmd matching & resume on return, close window after merge, unread feedback in integrator brief.
