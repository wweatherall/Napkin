# Work board

William says "check the board": this file tells each agent what to do next. The integrator (a Claude session in
/Users/Will/Sites/fretchup, P16) keeps it; nobody else edits it. Jobs run through the queue (P24, `tools/job.py`):
the table below is built from docs/handoff/ and the queue's live state; the integrator keeps the Order line.

Order: H069, H072, H052

## If you're not the integrator

1. `python3 tools/job.py take --as claude` (or `--as codex`), run anywhere in the repository: it gives you the
   first Ready job for you whose files don't overlap a job in progress, makes its worktree (`../fretchup-<id>`)
   and branch from main, and prints the job's handoff. A returned job comes first and continues its branch, with
   the integrator's notes. Nothing Ready for you? Run `python3 tools/job.py take --wait` in the background;
   it takes the next job when one is Ready, or stops after 20 min (then tell William).
2. Read "Notes" below for anything addressed to you, then do the job in its worktree.
3. Hung tests are yours (P40): run tests and other long commands through
   `python3 tools/job.py run -- <command>`, in the background (run_in_background). It always ends: past 10 minutes
   it stops the command and every process it started, prints HUNG and exits 124, so you're woken and fix it
   yourself (look at the log, fix, run again). `python3 tools/job.py check` lists your worktree's processes any
   time; `done` refuses while one looks hung. No timer: commits, test runs and `job.py` commands push the job's
   30-minute deadline back (the dead man's switch); only a worker that has gone quiet reaches the integrator.
4. Waiting on William? `python3 tools/job.py wait "<the question>"`, and ask him in chat: the switch pauses until
   your next beat.
5. When it's done (tests pass, the goal is met): append your response to the handoff (branch, commit, tests,
   anything open; your result goes there, not the Work list, P17), end it with a line `Result: <commit>; <tests>; <what changed>` (integrate.py copies it into the Work list),
   set its Status to answered, commit, then
   `python3 tools/job.py done`. It refuses until the response, the Status and a quick-test pass on your latest
   commit are there (it runs the quick test if that commit has none; `python3 tools/job.py test` runs and
   records it any time). It tells the integrator; tell William "ready for review: <ID>", then
   stop: one job a session (P37), then William starts a fresh one. Don't take the integrator lock.

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
| H069 | either | **Ready** | Three timing-sensitive tests that fail under load | [H069](docs/handoff/H069-flaky-timing-tests.md) |  |
| H072 | either | **Ready** | T88 step 3: Circle moves to ToolContext | [H072](docs/handoff/H072-t88-circle-to-toolcontext.md) |  |
| H052 | either | Queued | T66: lengths shown in the model's units | [H052](docs/handoff/H052-t66-units.md) | T88's tool moves |

<!-- end of job table -->

Done since the board started: H033 (T74 + T77), H034 (T76), H035 (T44), T56 (startup report), H036 (T75), H037 (T54), H038 (T78), H039 (T80), H040 (T33), H043 (T85), H044 (T58), H042 (T70), H041 (T81, Circle), H045 (T86), H047 (T88 spec), H048 (T79), H051 (T88 step 0), H049 (T90), H056 (T94), H058 (T96), H054 (T92), H055 (T93), H053 (T91).

## Notes

- T88: steps 1-2 (Paint H065, Select H071) merged; step 3 (Circle) is H072; step 4 (Rectangle) after it (they share tool_context.gd).
- Codex: take jobs with `python3 tools/job.py take --as codex` (P24).
- Claude: take jobs with `python3 tools/job.py take --as claude` (P24, P27).
