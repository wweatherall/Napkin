### H082 — For the next integrator session: where things stand

Author: Claude (integrator, fretchup-73) | Date: 2026-11-22 | Status: open | For: the integrator

References: docs/integrator.md, BOARD.md, tools/startup.py.

Touches: nothing (a note). Archive it once read: `python3 tools/handoff.py archive H0NN`.

Taking over: `python3 tools/integrator.py take fretchup-73` (a /clear keeps the name; another name needs
`--william`), then `python3 tools/startup.py`, then re-arm the watch (docs/integrator.md).

Merged this session (2026-11-22, evening; main pushed, gate passing): H072 (Circle) and H075 (Rectangle), T88
steps 3-4; H073 (number_ids numbers only real placeholders; integrate.py settles BOARD.md by section); H076
(tests refuse to run in the main checkout for a session holding a job); H077 (integrate.py's main() in named
steps; the gate runs BEFORE the map pause); H078 (worker steps all in BOARD.md, in plain words; CLAUDE.md and
AGENTS.md shorter). Small fixes: job.py take makes scratch/; test_job's hung-command check no longer sees another
worktree's run; five tool tests now exit 1 on a failed check.

Ready, all for Codex (William is spending Codex tokens; don't start Claude workers unless he asks): H079 (T88 step
5, Push/Pull: the biggest move; William may want an ultra review before merge, ask him), H080 (T105, done reuses
a quick pass across handoff-only commits), H081 (T106, test progress lines and scratch/ output). Their files
don't overlap. Then H052 (T66 units) after T88's tool moves, and T88 step 6 (Move) needs a job after H079.

Waiting on William: T107 (a per-job briefing at take: his call later). Earlier, still open: the whole-code
`/code-review ultra` findings (see H074 in the archive for how to handle them) and the proposal of a light
/code-review on every merge (process changes were frozen; he has since allowed tooling changes from worker
feedback).

Machine: it ran out of memory once this session (load 200+, swap full) with many sessions open; an orphaned
freecadcmd from a removed worktree was killed. If tests time out oddly, check `uptime` and swap first.
