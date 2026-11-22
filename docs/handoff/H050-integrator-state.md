### H050 — For the next integrator session: where things stand

Author: Claude (integrator, fretchup-73) | Date: 2026-11-22 | Status: open | For: the integrator

References: P16, P17-P21, BOARD.md, tools/startup.py, tools/integrate.py, tools/integrator.py, tools/gate.sh.

Touches: nothing (a note). Archive it once read: `python3 tools/handoff.py archive H0NN`.

Taking over: William must have told you, in your session, that you're the integrator. Then
`python3 tools/integrator.py take <your session name>`: refused while fretchup-73 holds it; if William says so, add
`--william`. A plain /clear of fretchup-73 keeps the name, so `take fretchup-73` works. Then `python3 tools/startup.py`.

In flight (2026-11-22 ~10:20; main 70538ec, pushed, gate passing with no known failures):
- H045 (T86, leftover test process): claude/h045-leftover-process. Then H049 (T90, faster gate) can be made Ready:
  it waits only for H045's quicktest.sh changes.
- H048 (T79, failed saves): claude/h048-failed-save. Bumps the protocol version; integrate.py renumbers if needed.
- H047 (T88 stage 1, the tools' interface spec): codex/h047-tool-interface. When it's answered, merge the spec, then
  ask William to review it before any tool moves (his call, option A). T88's later stages and H046 (Lines) follow;
  write each stage as its own job, smallest tool first, as the spec orders them.
- claude/h043-hide-check has one extra commit (a263559) proposing a Work list item that duplicates T86 (H045).
  Don't merge it; tell the H043 session or delete the branch once William agrees.

How merges go: review the diff against its handoff and Touches; `python3 tools/integrate.py <branch> --as <name>
--status T<n>=Done --push` (add `--impact "<reason>"` if the architecture hook asks). It settles handoff/log
conflicts, stops on any other conflict, renumbers placeholders and the protocol version, flags files outside the
Touches list, runs the gate. Then update BOARD.md (startup.py must show no OVERLAP) and push.

Waiting on William: T66 (the units preference), T38 (the cycling key for push-to-surface), H048's two questions
(the failure message, what closing does), H046's two (the Line key, the gesture), and his review of the T88 spec.

Check-ins: William asked for one every ~45 min (a one-shot CronCreate that schedules the next). They live only in
the session that made them: after a clear, check CronList and schedule one if he still wants them.

Housekeeping, ask William first: ~25 old worktrees in /private/tmp, ~/.codex/worktrees and ../fretchup-* are on
merged branches (startup.py hides them); `git worktree list` shows them.
