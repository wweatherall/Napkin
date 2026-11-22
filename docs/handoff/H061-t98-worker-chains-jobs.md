### H061 — T98: a worker session chains up to 3 jobs

Author: Claude (integrator, fretchup-73) | Date: 2026-11-22 | Status: answered | For: Claude

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

**Response** — Claude (worker, session ece2cf8a), 2026-11-22

Branch `claude/h061-t98-worker-chains-jobs`, commit e956ca4. Quick test and gate pass (JOB TESTS 64/64, 11 new).

1. Count: `take` records each distinct job a session takes in the state's `"sessions": {session: [ids]}`; a
   take past MAX_JOBS (3) refuses "this session has done 3 jobs: tell William it's ready for a /clear". A returned
   job resumed by the same session counts once. A session with no real ID (default_session's fallback, the
   agent's name) isn't counted, since every such session would share it. take prints "job N of 3".
   **/clear and the session ID, checked:** it does give a new CLAUDE_CODE_SESSION_ID. This session began with a
   /clear: its env has `CLAUDE_CODE_SESSION_ID=ece2cf8a-…`, and its transcript's first record says
   `derived-from … ee72376b-… via clear`; ee72376b is the session that took H057. (CLAUDE_CODE_BRIDGE_SESSION_ID,
   the remote-control ID, stays the same across the clear; job.py doesn't read it.) So the count starts again
   after a /clear with nothing else needed.
2. `take --wait` (take_wait): when nothing is Ready it looks again every WATCH_POLL, quietly, until it takes a job
   (prints take's full output, exit 0) or WORKER_WAIT (20 min) passes ("nothing came in 20 min: stopping", exit 1).
   A refusal (holding a job, or at 3) ends it at once. It holds no job while it waits, so nothing beats, goes
   stale, or shows in watch (watch's "queue empty for Claude" still fires, as it should).
3. done ends with the next step: `take --wait` in the background (with "job N of 3"), or at the 3rd "tell
   William you're ready for a /clear".
4. AGENTS.md (a bullet after done) and CLAUDE.md (a bullet after the P24 one) carry the loop. P27's "Where in
   the code" is filled in; Tunables: MAX_JOBS and WORKER_WAIT added, WATCH_POLL's row names take --wait (by hand:
   log.py add has no tunable kind).

Checks: the count and refused 4th; another session not refused; the fallback session not counted; --wait takes a
job that turns Ready mid-wait; --wait times out; --wait gives up at once when refused; done's message at jobs 1 and 3.

Follow-up: CLAUDE.md's "One Work list item per session where possible ... then start the next in a fresh session" (Working with William) now reads against P27's 3 jobs a session; not in this job's Touches, so left as is.
Follow-up: Codex sessions are counted only if CODEX_SESSION_ID or CODEX_THREAD_ID is set; if Codex has neither, its count never applies (it falls back to "codex"). Worth checking from a Codex session.
For the integrator: BOARD.md's worker steps: step 1's "Nothing Ready for you? It says so: tell William and stop" could become "run `python3 tools/job.py take --wait` in the background; it stops after 20 min", and step 5 could end "then take --wait for the next (at most 3 a session, P27)".

Result: e956ca4; quick test and gate pass (JOB TESTS 64/64); job.py counts jobs per session (refuses a 4th), take --wait waits up to 20 min for a Ready job, done names the next step (P27)
