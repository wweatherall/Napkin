# Work board

William says "check the board": this file tells each agent what to do next. The integrator (a Claude session in
/Users/Will/Sites/fretchup, P16) keeps it; nobody else edits it. Jobs run through the queue (P24, `tools/job.py`):
the table below is built from docs/handoff/ and the queue's live state; the integrator keeps the Order line.

Order: H069, H072, H073, H052

## If you're not the integrator

You're a worker: you take one job, deliver it to the integrator and stop. You don't merge into main or push.

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
   anything open, `Follow-up:` and `For the integrator:` lines; your result goes there, not the Work list, P17),
   end it with a line `Result: <commit>; <tests>; <what changed>` (integrate.py copies it into the Work list),
   set its Status to answered, commit, then
   `python3 tools/job.py done`. It refuses until the response, the Status and a quick-test pass on your latest
   commit are there (it runs the quick test if that commit has none; `python3 tools/job.py test` runs and
   records it any time). It tells the integrator; tell William "ready for review: <ID>", then
   stop: one job a session (P37: context grown over several jobs used up William's usage; `job.py` refuses a
   2nd), then William starts a fresh one (a /clear gives a new session ID). Don't take the integrator lock.

## If you're the integrator

You're the integrator only if William said so in this session (P16) and you hold the lock (P19): see
[docs/integrator.md](docs/integrator.md) for the lock, the queue watch, review, merging and writing jobs.

## Jobs

<!-- job table: built by tools/job.py board from docs/handoff/ and the queue; don't edit by hand -->

| Job | For | Status | Item | Handoff | Waits for |
|---|---|---|---|---|---|
| H073 | either | **Ready** | Two merge traps the tools cause: placeholders in prose, and BOARD.md's instructions lost | [H073](docs/handoff/H073-integrator-tool-traps.md) |  |
| H052 | either | Queued | T66: lengths shown in the model's units | [H052](docs/handoff/H052-t66-units.md) | T88's tool moves |

<!-- end of job table -->

Done since the board started: H033 (T74 + T77), H034 (T76), H035 (T44), T56 (startup report), H036 (T75), H037 (T54), H038 (T78), H039 (T80), H040 (T33), H043 (T85), H044 (T58), H042 (T70), H041 (T81, Circle), H045 (T86), H047 (T88 spec), H048 (T79), H051 (T88 step 0), H049 (T90), H056 (T94), H058 (T96), H054 (T92), H055 (T93), H053 (T91).

## Notes

- T88: steps 1-2 (Paint H065, Select H071) merged; step 3 (Circle) is H072; step 4 (Rectangle) after it (they share tool_context.gd).
