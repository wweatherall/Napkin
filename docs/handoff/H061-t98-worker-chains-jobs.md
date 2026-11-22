### H061 — T98: a worker session chains up to 3 jobs

Author: Claude (integrator, fretchup-73) | Date: 2026-11-22 | Status: open | For: Claude

References: P27 (William's call, 2026-11-22), P24 (the queue), T96 (tools/job.py), tunables DEADLINE / WATCH_POLL.

Touches: tools/job.py, tools/test_job.py, AGENTS.md (the worker steps), CLAUDE.md (the "Jobs run through the queue
(P24)" bullet), docs/decision-log.md (P27's "Where in the code" and two Tunables rows, with `log.py add`). Not
BOARD.md (the integrator's): give its lines in your response.

Request: build P27.
1. Count: job.py records, per session (take's session: CLAUDE_CODE_SESSION_ID / CODEX_* as default_session() reads
   it, or `--session <name>`), how many jobs that session has taken. A take that would be its 4th (MAX_JOBS = 3, a
   tunable) refuses: "this session has done 3 jobs: tell William it's ready for a /clear". Check, and say in your
   response, whether a /clear gives a Claude session a new CLAUDE_CODE_SESSION_ID; if it doesn't, find what does
   reset the count (and say so) rather than guessing.
2. Wait: `job.py take --wait` (WORKER_WAIT = 20 min, a tunable): when nothing is Ready for the agent, it polls every
   WATCH_POLL and exits as soon as it has taken a job (printing what `take` prints), or at WORKER_WAIT with
   "nothing came in 20 min: stopping" and a non-zero exit. While waiting it holds no job, so it doesn't beat or go
   stale; the integrator's watcher should not report it as a job. Meant to be run in the background
   (`run_in_background`), so the session is woken when it exits.
3. done's closing message says what to do next: run `job.py take --wait` in the background, unless the session is at
   its 3rd job, then "tell William you're ready for a /clear".
4. AGENTS.md and CLAUDE.md: the loop in one or two lines (take, work, done, take --wait; at most 3; stop and tell
   William after the 3rd or a wait that times out).
Checks (tools/test_job.py): the count per session and the refused 4th; a different session isn't refused; --wait
takes a job that turns Ready while it waits; --wait times out (with a short test value); done's message at jobs 1
and 3. Quick test, then the gate. End your response with a Result line; leftovers as Follow-up lines, BOARD.md
lines as For the integrator lines.
