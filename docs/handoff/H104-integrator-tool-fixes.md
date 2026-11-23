### H104 — Integrator tools: `job.py reassign`, a quieter watch, a short result at merge

Author: Claude (integrator, fretchup-74) | Date: 2026-11-22 | Status: open | For: gemini

References: the integrator's feedback to William, 2026-11-22 (his OK to write it up): handing H083 from Codex to
Gemini took four hand edits of the queue's state file; the watch woke the integrator for empty queues that were
planned; integrate.py printed whole Work list rows. P24 (the queue), P37 (MAX_JOBS), P39 (the watch), T91 (results).

Touches: tools/job.py, tools/test_job.py, tools/integrate.py, tools/test_integrate.py, docs/integrator.md (one
line each where it describes return, the watch and results). Not BOARD.md, not the viewport or worker.

Today (checked 2026-11-22):
- `job.py return <id> "<notes>"` (`return_job`) sets the job's state to returned, `session` to None, and keeps
  its `agent`: `takeable` gives a returned job only to a worker of that agent. A job's `worktree` is the path
  recorded at `take`. Each session's jobs are listed in the state's `sessions` (`jobs_taken`, MAX_JOBS = 1): a
  session that took a job and lost it still counts it.
- `watch` (`events`, ~line 740) adds a `("empty", agent)` event for every agent `takeable` finds nothing for,
  whether or not any worker of that agent is looking. `take --wait` polls every WATCH_POLL until a job is taken
  or WORKER_WAIT passes; nothing in the state records that a worker is waiting.
- integrate.py `draft_results` ends by printing `git show --word-diff=plain HEAD` of the result commit: the whole
  Work list row (T88's row is a paragraph of history) to show one appended Result.

Request:
1. `python3 tools/job.py reassign <id> --to claude|codex|gemini ["<notes>"]`, the integrator's (refuse when run
   in a job worktree, as `return` does if it does; say so if not). For a job in state returned, in progress or
   waiting (refuse done or merged, or a job not in the queue): sets `agent` to the new one, state returned,
   `session` None, notes (default `reassigned from <old> by the integrator`); takes the job off the old
   session's list in `sessions` (the session didn't finish it, so it doesn't count toward MAX_JOBS); and if the
   recorded worktree isn't under `<checkout>-jobs/`, moves it there (`git worktree move` to `worktree_for(root,
   id)`, making the folder) and records the new path. Uncommitted work in the worktree is left as it is (the move
   keeps it): print `<id>: <n> files not committed in <path>` when there are any, so the integrator decides.
   The branch is kept (the new worker resumes it). Records an event `reassigned`; the watch reports it like
   `returned`. Prints `<id> reassigned to <agent>: the next <agent> worker resumes <branch> in <path>`.
2. The watch says a queue is empty only when it matters: `take --wait` records the waiting worker in the state
   (`waiting_workers`: `{session: {agent, since}}`, removed when it takes a job or stops); the `empty` event
   for an agent is reported only when at least one of its workers is waiting. Its text: `queue empty for
   <Agent>: a worker is waiting with nothing Ready (check in with William)`. A worker killed mid-wait mustn't
   leave the flag forever: an entry older than WORKER_WAIT + WATCH_POLL is ignored and dropped.
3. integrate.py's result step prints, instead of the word diff, one line per item: `<T id> (<H id>): Result
   (<commit>, merged <merge>): <the Result text, cut to 160 characters with … if longer>`, then the commit's
   oneline. The commit itself is unchanged.

What can fail:
- reassign of a job whose worker is still running (in progress, recent beat): allowed, but print `<id>: its
  worker beat <n> min ago; tell that worker to stop` so the integrator does. Check it.
- The worktree move fails (the path is in use, the target exists): nothing in the state changes, and the error
  is printed. Check (a target that already exists).
- A `sessions` list without the job (the session was never counted, CODEX fallback names): no error. Check.
- Two watchers or two `take --wait` at once: the state file is changed only under `locked` (as today). Check
  that `waiting_workers` is written under the lock.
- A worker waiting, then taking a job: its entry goes, and no `empty` event fires for that agent. Check.

Checks: each case above, plus: reassign of a returned job to another agent, then `take --as <new>` resumes its
branch in the moved worktree; reassign refuses a done job; the empty event appears with a waiting worker and
not without; the stale entry is dropped; the result step's line for a long Result is cut with … (in
test_integrate.py's style, with a throwaway repo).

Reading path: job.py `return_job` → `takeable` → `_take` (the `prev` branch for a returned job) → `jobs_taken`
/ `counted` → `take` with `--wait` (the poll loop) → `events` / `watch` → integrate.py `record_result` /
`draft_results`. Who owns what: job.py owns the queue state; integrate.py only reads it and records results.

Run `python3 tools/test_job.py` and `python3 tools/test_integrate.py` while building, then `python3 tools/job.py
test`. End your response with a Result line; leftovers as Follow-up lines; anything for the merge as For the
integrator lines.
