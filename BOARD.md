# Work board

William says "check the board": this file tells each agent what to do next. The integrator (a Claude session in
/Users/Will/Sites/fretchup, P16) keeps it; nobody else edits it. Jobs run through the queue (P24, `tools/job.py`):
the table below is built from docs/handoff/ and the queue's live state; the integrator keeps the Order line.

Order: H046, H062, H064, H063, H059, H052

## If you're not the integrator

1. `python3 tools/job.py take --as claude` (or `--as codex`), run anywhere in the repository: it gives you the
   first Ready job for you whose files don't overlap a job in progress, makes its worktree (`../fretchup-<id>`)
   and branch from main, and prints the job's handoff. A returned job comes first and continues its branch, with
   the integrator's notes. Nothing Ready for you? Run `python3 tools/job.py take --wait` in the background;
   it takes the next job when one is Ready, or stops after 20 min (then tell William).
2. Read "Notes" below for anything addressed to you, then do the job in its worktree.
3. The dead man's switch: anything you do through the job pushes its deadline back (30 minutes): a commit, a
   quick test run from the worktree, any `job.py` command. Check in every 15-30 minutes with
   `python3 tools/job.py check`: it lists the processes you started from the worktree (Godot, freecadcmd, the
   test scripts) with their age, flags any that look hung (kill what's stuck), and beats.
   A Claude worker sets a timer for it right after taking the job: CronCreate, recurring every 20 minutes, with the
   prompt "check-in for <id>: run python3 tools/job.py check in <worktree>, deal with anything hung, then go on";
   CronDelete it after done. A Codex worker without a timer still has the switch: its commits and test runs beat,
   and if it goes quiet the integrator is told.
4. Waiting on William? `python3 tools/job.py wait "<the question>"`, and ask him in chat: the switch pauses until
   your next beat.
5. When it's done (tests pass, the goal is met): append your response to the handoff (branch, commit, tests,
   anything open; your result goes there, not the Work list, P17), end it with a line `Result: <commit>; <tests>; <what changed>` (integrate.py copies it into the Work list),
   set its Status to answered, commit, then
   `python3 tools/job.py done`. It refuses until the response, the Status and a quick-test pass on your latest
   commit are there (it runs the quick test if that commit has none; `python3 tools/job.py test` runs and
   records it any time). It tells the integrator; tell William "ready for review: <ID>", then
   `take --wait` for the next (at most 3 a session, P27). Don't take the integrator lock.

## If you're the integrator

You're the integrator only if William said so in this session (P16) and you hold the lock: `python3
tools/integrator.py take <your session name>` (refused if another holds it: ask William; after a context clear
he says so and you run it with `--william`, P19). Run `python3 tools/job.py watch` under your watcher (Monitor):
one line per event: a job done, a job stale (its deadline passed: check its branch and worktree), a worker
waiting on William, a job returned, the queue empty for Claude or Codex (check in with William). Review every
done job; merge what's good with `python3 tools/integrate.py <branch> --as <name> --push` (a job with Architecture:
lines stops with the merge staged: write the map, then `integrate.py --continue --as <name> --push`, P28) (P20; it also removes
the job's worktree and branch and marks it merged); put one that fails review or the gate back with
`python3 tools/job.py return <id> "<notes>"`. integrate.py commits each response's Result line
to its Work list row (T91) and, with --push, stops before pushing for you to look (`--yes` goes on); a
response without one is yours to record. It also copies Follow-up lines into docs/follow-ups.md and prints
For the integrator lines under "for you now:" (P26); clear a follow-up in the commit that does it. Then write the next jobs (a handoff entry
with Status open is Ready; "queued (after H0NN)" waits), and keep the Order line. `python3 tools/job.py status`
shows the queue; `python3 tools/job.py board` rebuilds the table (the commit hook does it on main).

## Jobs

<!-- job table: built by tools/job.py board from docs/handoff/ and the queue; don't edit by hand -->

| Job | For | Status | Item | Handoff | Waits for |
|---|---|---|---|---|---|
| H063 | Claude | In progress (claude since 13:08) | T64: watch the model file and reload FreeCAD's saves, with a wave | [H063](docs/handoff/H063-t64-reload-freecad-saves.md) |  |
| H059 | Codex | Queued | T67: IDs that never collide across kept history branches | [H059](docs/handoff/H059-t67-branch-safe-ids.md) | H046 |
| H052 | either | Queued | T66: lengths shown in the model's units | [H052](docs/handoff/H052-t66-units.md) | T88's tool moves |

<!-- end of job table -->

Done since the board started: H033 (T74 + T77), H034 (T76), H035 (T44), T56 (startup report), H036 (T75), H037 (T54), H038 (T78), H039 (T80), H040 (T33), H043 (T85), H044 (T58), H042 (T70), H041 (T81, Circle), H045 (T86), H047 (T88 spec), H048 (T79), H051 (T88 step 0), H049 (T90), H056 (T94), H058 (T96), H054 (T92), H055 (T93), H053 (T91).

## Notes

- Later (no handoff yet): T88 steps 1-4, Paint, Select, Circle, Rectangle move to ToolContext (Claude; one job each, on files H046 doesn't touch), after H054 and H055 (William's priority: the integrator's tools first).
- Codex: after H046 (Lines), H059 (T67, branch-safe IDs: William's choice, 2026-11-22);  Take jobs with `python3 tools/job.py take --as codex` (P24).
- Claude: H062 (T40, save generations, A32) in progress; H064 (T100, the map is the integrator's, P28: William's call, 2026-11-22) Ready beside it; H063 (T64, A36) after H062. Take jobs with `python3 tools/job.py take --as claude` (P24, P27).
