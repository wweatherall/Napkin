### H050 — For the next integrator session: where things stand

Author: Claude (integrator, fretchup-73) | Date: 2026-11-22 | Status: open | For: the integrator

References: P16, P17-P21, BOARD.md, tools/startup.py, tools/integrate.py, tools/integrator.py, tools/gate.sh.

Touches: nothing (a note). Archive it once read: `python3 tools/handoff.py archive H0NN`.

Taking over: William must have told you, in your session, that you're the integrator. Then
`python3 tools/integrator.py take <your session name>`: refused while fretchup-73 holds it; if William says so, add
`--william`. A plain /clear of fretchup-73 keeps the name, so `take fretchup-73` works. Then `python3 tools/startup.py`.

In flight (2026-11-22 ~17:45; main pushed, gate passing, ~42 s): `python3 tools/startup.py` and
`python3 tools/job.py status` show the live queue. Merged today since 16:25: H067 (agent-role note, P29-P35
Tentative; P36: the architect plans from the map, P28 stays), P37 (one job a worker session), P38
(tools/start_worker.sh), P39 (no timed check-ins), P40 (job.py run: workers handle their own hung tests), H068
(integrate.py/log.py follow-ups), H059 (T67, branch-safe IDs, protocol 7; P41, W14). Ready: H065 (T88 step 1, Paint
to ToolContext) and H066 (T101, recovery: newest file wins), both "either", no overlap. Queued: H069 (flaky
timing tests, after H066: shares test_outside_save.py), H070 (trim CLAUDE.md and AGENTS.md, Ready). Then H052 (T66
units, after the tool moves); after H065, T88 steps 2-4 (Select, Circle, Rectangle), one job each. Parked: T65.
experiment/agent-role-system: Antigravity's prototype, kept unmerged as reference (William, 2026-11-22); its
docs/agent-workflow.md is worth reading for the role plan (H067). Next on roles: decision partner and ideator as
charter-only sessions, the architect as planner (P36); the dispatcher only after measuring.

Starting workers (P38): `tools/start_worker.sh [name]` opens Terminal with `claude --remote-control <name> "Check the
board"`; William follows it in the Claude app. Ask William before starting one (usage). One job a session (P37).

William's concerns from the 2026-11-22 review, still open: process work crowding out the product (freeze process
changes for a while; H070 trims the instructions every session reads); flaky tests (H069; don't make re-running the
gate a habit); decisions relayed by an agent ("William approved ..." in another agent's row) can't be verified:
proposed rule, not yet decided: such a row says it was relayed and William glances at it; never write an example
placeholder (P-new-1 style) in prose: number_ids.py numbers it at merge; H059's viewport test edits were skimmed,
not read line by line; Q4 feel test on real hardware.

How merges go (P28 since 2026-11-22): ARCHITECTURE.md and docs/protocol.md are the integrator's. A job with
"Architecture:" lines stops after the gate with the merge staged: check the lines against the code, write them
in, `git add` the two files, then `python3 tools/integrate.py --continue --as <name> --push --yes` (it stages only
those two files and refuses if code changed while paused). Two jobs that each bump PROTOCOL_VERSION to the same
number merge silently: bump the later one by one in the scratch merge (A35; H063 took 6 after H046's 5).
How merges go: `python3 tools/job.py status` / the watcher says what's done. Review the diff against its handoff's
Request and Touches. If the branch started from an older main and touches files main changed since, merge main
into it in a scratch worktree first (as for H056, H058) and integrate that. Then `python3 tools/integrate.py
<branch> --as <name> --status T<n>=Done --push --yes`: it settles handoff/log/board conflicts, numbers
placeholders (log.py add writes them on a branch), runs the gate, commits, copies the response's Result line into
the Work list (T91; without --yes it stops before the push so you can look), removes the job's worktree and branch
(never the standing small-fixes branches, P22), and pushes. Add what the response asks for (feature-test lines,
CLAUDE.md / AGENTS.md lines), keep BOARD.md's Order line and Notes (`python3 tools/job.py board` rebuilds the
table), and write the next jobs. Small fixes: on small-fixes, merged the same way without asking (P22).
A trap seen twice: a merge that brings in a new version of a tool integrate.py itself imports (number_ids, job)
runs the OLD one for that merge; check its effect (H056 renumbered a test file's placeholders; H058's fix still
deleted small-fixes once).

Waiting on William: `python3 tools/startup.py` lists it, from main (T93); it isn't kept here.

Watching (session-only; re-arm after a clear or restart; integrate.py's --impact takes the reason only: it adds "none - "): `python3 -u tools/job.py watch --next` with Bash
run_in_background. It wakes you once, on the first new queue event (done, stale, waiting, returned, queue empty);
deal with it, then start it again. No timed check-ins and no Monitor: William removed the 20-minute check-in on
2026-11-22 (each wake re-reads the whole context and used up his usage), and a Monitor expires every 30 min.

Housekeeping done 2026-11-22: old worktrees and /private/tmp scratch removed; job scratch now goes in scratch/ inside
the worktree (P25), so merges clean it up.