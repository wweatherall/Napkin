### H058 — T96: the job queue (take, done, the dead man's switch)

Author: Claude (integrator, fretchup-73) | Date: 2026-11-22 | Status: open | For: Claude

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
