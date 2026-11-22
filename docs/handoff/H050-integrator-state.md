### H050 — For the next integrator session: where things stand

Author: Claude (integrator, fretchup-73) | Date: 2026-11-22 | Status: open | For: the integrator

References: P16, P17-P21, BOARD.md, tools/startup.py, tools/integrate.py, tools/integrator.py, tools/gate.sh.

Touches: nothing (a note). Archive it once read: `python3 tools/handoff.py archive H0NN`.

Taking over: William must have told you, in your session, that you're the integrator. Then
`python3 tools/integrator.py take <your session name>`: refused while fretchup-73 holds it; if William says so, add
`--william`. A plain /clear of fretchup-73 keeps the name, so `take fretchup-73` works. Then `python3 tools/startup.py`.

In flight (2026-11-22 ~11:00; main pushed, gate passing): H048 (T79) merged. William answered everything that was
waiting: I56 (T38 key: Option), I57 + I59 (T66 units; job H052, queued after the tool moves), I58 (Line: L, chain
plus drag), and approved the T88 spec with Line starting after step 0. Ready: H051 (T88 step 0, Claude; add its
test_tool_context line to tools/featuretest.sh at merge), H049 (Codex). Next to write once H051 lands: H046 Ready
(Codex) and T88 steps 1-4 one job each (Claude), not overlapping H046's Touches; steps 5-6 after Line.

How merges go: review the diff against its handoff and Touches; `python3 tools/integrate.py <branch> --as <name>
--status T<n>=Done --push` (add `--impact "<reason>"` if the architecture hook asks). It settles handoff/log
conflicts, stops on any other conflict, renumbers placeholders and the protocol version, flags files outside the
Touches list, runs the gate. Then update BOARD.md (startup.py must show no OVERLAP) and push.

Waiting on William: `python3 tools/startup.py` lists it, from main (T93); it isn't kept here.

Check-ins: William asked for one every ~45 min (a one-shot CronCreate that schedules the next). They live only in
the session that made them: after a clear, check CronList and schedule one if he still wants them.


Housekeeping done 2026-11-22: old worktrees and /private/tmp scratch removed; job scratch now goes in scratch/ inside
the worktree (P25), so merges clean it up.