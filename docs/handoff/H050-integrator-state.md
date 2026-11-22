### H050 — For the next integrator session: where things stand

Author: Claude (integrator, fretchup-73) | Date: 2026-11-22 | Status: open | For: the integrator

References: P16, P17-P21, BOARD.md, tools/startup.py, tools/integrate.py, tools/integrator.py, tools/gate.sh.

Touches: nothing (a note). Archive it once read: `python3 tools/handoff.py archive H0NN`.

Taking over: William must have told you, in your session, that you're the integrator. Then
`python3 tools/integrator.py take <your session name>`: refused while fretchup-73 holds it; if William says so, add
`--william`. A plain /clear of fretchup-73 keeps the name, so `take fretchup-73` works. Then `python3 tools/startup.py`.

In flight (2026-11-22 ~16:25; main pushed, gate passing, ~42 s): `python3 tools/startup.py` and
`python3 tools/job.py status` show the live queue. Ready: H059 (T67, branch-safe IDs, Codex). Queued behind it:
H065 (T88 step 1, Paint to ToolContext, either; both edit tool_context.gd), H066 (T101, A37 recovery: the newest
file wins, either; shares worker/session.py), then H052 (T66 units, after the tool moves). After H065: T88 steps
2-4 (Select, Circle, Rectangle), one job each. Parked: T65 (waits for the branch view, T71). fretchup-e1 has done
its 3 jobs (P27): it needs a /clear before taking more.

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

Watching (session-only; re-arm after a clear or restart): `python3 -u tools/job.py watch --next` with Bash
run_in_background. It wakes you once, on the first new queue event (done, stale, waiting, returned, queue empty);
deal with it, then start it again. No timed check-ins and no Monitor: William removed the 20-minute check-in on
2026-11-22 (each wake re-reads the whole context and used up his usage), and a Monitor expires every 30 min.

Housekeeping done 2026-11-22: old worktrees and /private/tmp scratch removed; job scratch now goes in scratch/ inside
the worktree (P25), so merges clean it up.