### H050 — For the next integrator session: where things stand

Author: Claude (integrator, fretchup-73) | Date: 2026-11-22 | Status: open | For: the integrator

References: P16, P17-P21, BOARD.md, tools/startup.py, tools/integrate.py, tools/integrator.py, tools/gate.sh.

Touches: nothing (a note). Archive it once read: `python3 tools/handoff.py archive H0NN`.

Taking over: William must have told you, in your session, that you're the integrator. Then
`python3 tools/integrator.py take <your session name>`: refused while fretchup-73 holds it; if William says so, add
`--william`. A plain /clear of fretchup-73 keeps the name, so `take fretchup-73` works. Then `python3 tools/startup.py`.

In flight (2026-11-22 ~12:30; main pushed, gate passing, ~32 s): `python3 tools/startup.py` shows the live queue,
what waits on William, and (once H060 lands) the follow-ups. At this moment: Codex on H046 (Lines; quiet since
12:07, its deadline was near: if the watcher said stale, check codex/h046-t82-lines-split-faces and its worktree);
Ready: H060 (T97, follow-ups, Claude) and H057 (T95, tests find themselves, either); H059 (T67, branch-safe IDs,
William's pick for Codex) queued after H046; then T88 steps 1-4 (Paint first) as one job each once Lines lands
(they share viewport/test_tools.gd with it); H052 (T66 units) after the tool moves.

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

Watching (session-only; re-arm after a clear or restart): a Monitor on `python3 -u tools/job.py watch` (30-minute
expiry, so re-arm it at each check-in) and William's 20-minute check-in, a recurring CronCreate at :07/:27/:47
whose prompt is the check-in steps above. Check CronList first; recreate what's missing.

Housekeeping done 2026-11-22: old worktrees and /private/tmp scratch removed; job scratch now goes in scratch/ inside
the worktree (P25), so merges clean it up.