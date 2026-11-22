### H058 — T96: the job queue (take, done, the dead man's switch)

Author: Claude (integrator, fretchup-73) | Date: 2026-11-22 | Status: answered | For: Claude

References: P24 (the design, William's: read `### P24` in docs/decision-log.md first), P14 (the board), P16, P19
(tools/integrator.py: its lock lives in git's common folder; the queue's state goes beside it), P20
(tools/integrate.py), P11 (overlap by files: tools/handoff.py touches / overlaps_in), T96.

Touches: tools/job.py (new), tools/test_job.py (new; give its feature-test line in your response, H057 owns that
script), tools/integrate.py (after a merge: delete the branch and its worktree, mark the job merged), BOARD.md
(its job table becomes generated; its worker and integrator steps), docs/agent-handoff.md (its rules section),
AGENTS.md (the worker steps). Not CLAUDE.md (H057) or tools/startup.py (H055): give the lines they need in your
response and the integrator adds them at merge.

Request: build P24.
- `job.py take [--as claude|codex]`: the first Ready job for that agent, in the board's order, whose Touches don't
  overlap a job in progress (handoff.overlaps_in); makes the worktree (../fretchup-<id>) and branch
  (<agent>/<id>-<slug>) from main; records it in progress (who, when, branch, worktree); prints the handoff.
  Refuses if that agent's session already holds a job. A returned job resumes its branch.
- `job.py beat`: pushes the deadline back. Also counted as beats: a commit on the job's branch, a quick-test run in
  its worktree (read their times; don't edit quicktest.sh), and every job.py command.
- `job.py check`: what the worker runs at each 15-30 minute check-in: lists processes started from its worktree
  (Godot, freecadcmd, the test scripts) with their age, flags any that look hung (older than a limit you set as a
  tunable), and beats. Say in the instructions how a Claude worker sets its timer (CronCreate or ScheduleWakeup) and
  that a Codex worker without one still has the switch.
- `job.py wait "<question>"`: waiting on William; pauses the switch until the next beat.
- `job.py done`: refuses unless the handoff has its response and Status answered, and the quick test passed on the
  latest commit; marks done and tells the integrator.
- `job.py status` and `job.py board`: the queue as text; `board` rewrites BOARD.md's job table from the handoffs
  (Ready / queued from their Status, in an order list the integrator keeps at the top of the board) plus the live
  state. The commit hook rebuilds it like the handoff list.
- `job.py watch`: for the integrator; prints one line per event (done, stale: deadline passed, returned, queue empty
  for Claude or Codex) and keeps running, so the integrator can run it under its watcher. `job.py return <id>
  "<notes>"` puts a reviewed job back.
State: a JSON file in git's common folder next to the integrator lock, written atomically; never committed.
Deadline: 30 minutes (a tunable). Checks: take (order, overlap refused, one job per session, returned resumes),
beats from commits and test runs, the deadline and wait, done's refusals, watch's events, board generation, and
integrate.py's cleanup, all in temporary repos. Quick test, then the gate.

Response — Claude (worker, branch `claude/h058-job-queue`), 2026-11-22: built P24.
- `tools/job.py`: take / beat / check / test / wait / done / status / board / watch / return, as the request lists.
  State: `shopsketch-jobs.json` beside the integrator lock (git's common folder), written atomically under a file
  lock, never committed. Take reads the jobs and the Order line from main (what the integrator committed), skips
  jobs claimed by a hand-made branch (the old rule), passes over overlaps (handoff.touches / _covers) against
  every job in progress, waiting, done or returned, and gives a returned job first (re-making its worktree if
  it's gone). Session: `--session`, else `CLAUDE_CODE_SESSION_ID`, else `CODEX_SESSION_ID` / `CODEX_THREAD_ID`,
  else the agent's name (then it's one job per agent).
- Beats: any job.py command run in the worktree, the branch's last commit time, a recorded test run, and a
  process running in the worktree that isn't older than HUNG_AFTER (lsof's cwd, or the worktree in its command
  line). quicktest.sh isn't touched, so a quick test run by hand counts only while it runs; `done` needs a pass
  recorded for the latest commit, so it runs `tools/quicktest.sh` itself when there is none (`job.py test` runs
  and records it any time).
- Watch: one line per new event (done, stale, waiting, returned, queue empty for Claude / Codex); `--once` for one
  look. I added "waiting" to the request's list: the integrator hears a worker is waiting on William.
- integrate.py: after the commit, `job.merged`: the job marked merged, its worktree removed (`git worktree remove`;
  a dirty one is left and said), its branch deleted (`-d`). The board's table is rebuilt in the merge commit; a
  conflict in BOARD.md keeps main's and rebuilds the table. Its "left for you" no longer names BOARD.md.
- BOARD.md: an Order line at the top (the integrator keeps it), the table between markers, rebuilt by
  `job.py board` and by the pre-commit hook on main only (so worker branches never carry a rebuilt table). New
  worker and integrator steps (the timer: CronCreate every 20 minutes, CronDelete after done; a Codex worker
  without one still has the switch). The hand-kept "next" row moved to Notes as "Later (no handoff yet)".
  docs/agent-handoff.md: one rule on entries as jobs. AGENTS.md: the worker steps.
- Tunables (decision log): DEADLINE 1800 s, HUNG_AFTER 600 s, WATCH_POLL 20 s (tools/job.py, P24).
- Tests: `tools/test_job.py`, JOB TESTS 52 passed, 0 failed (~3.5 s): take (order, overlap passed over, one job per
  session, queued not taken, branch claims, returned resumes with notes), beats from commands, commits, test
  runs and processes, the deadline and wait (a commit after a wait resumes), check's hung flag, done's four
  refusals and a stale pass, watch's five events, board generation, and integrate.py's cleanup end to end, all in
  temporary repos. INTEGRATE TESTS 28/28, LOCK TESTS 9/9. Quick test: QUICK 208 passed, features all pass.

For the integrator at merge:
- tools/featuretest.sh (H057's): `"job|python3 tools/test_job.py|JOB TESTS"` (or nothing, if H057's discovery finds
  `tools/test_*.py` itself).
- CLAUDE.md, "Working with Codex": `Jobs run through the queue (P24): a worker runs python3 tools/job.py take, works
  in the worktree it gets, and finishes with python3 tools/job.py done; the integrator runs python3 tools/job.py
  watch under its watcher and reviews each done job.` and in the integrator line: integrate.py now also removes the
  job's worktree and branch.
- tools/startup.py (H055's): print `python3 tools/job.py status` (the live queue: in progress, waiting, done, next
  for each agent) beside or instead of "Ready on the board (main:BOARD.md)", which only changes at a commit.
- This merge itself: main's integrate.py is the old one, so a BOARD.md conflict stops it; take the branch's
  BOARD.md (it carries the new steps) with main's Order and Notes, then `python3 tools/job.py board`. After the
  merge, run `python3 tools/job.py board` once on main. H058 itself was claimed by hand (its branch), not through
  the queue: the board shows it "Claimed" until it's merged.
- ARCHITECTURE.md: not changed (it doesn't map the process tools; tools/job.py has no app module, protocol or file
  format). If you'd like a row beside tools/integrate.py, say so.
