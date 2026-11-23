### H119 — T114: a worker's question is answered through the queue (scope to the integrator, behaviour to William)

Author: Claude (integrator, fretchup-73) | Date: 2026-11-23 | Status: answered | For: either

References: T114, P24 (the queue), P45 (Touches), P01 (behaviour is William's), P39 (no timed check-ins).

Touches: tools/job.py (`wait`, a new `answer`, the watch's waiting event and `status` lines, the command line and
the usage text at the top), tools/test_job.py, AGENTS.md and GEMINI.md (the worker steps on asking). Not
BOARD.md or docs/integrator.md (the integrator's: write what they should say as "For the integrator:" lines).

Why: on 2026-11-23 H096 stopped at 08:48 with `job.py wait`, asking to touch two functions outside its Touches.
That is the integrator's call (no other job held them), and the integrator answered at once, but the only way to
deliver it was typing into the worker's own window, and William was at work. The job and the two waiting on it
sat for hours. The purpose: a question reaches whoever can answer it, and the answer reaches the worker, with
nobody at the worker's keyboard.

Today (checked 2026-11-23): `wait(cwd, question)` (job.py ~546) sets the job's state to "waiting" with the
question, records a "waiting" event, prints "waiting on William ... Ask him in chat", and returns at once; the
worker then waits in its chat. `watch` reports it as `waiting: H0NN asks William: <question>` (~847). The next
beat puts the job back in progress (~310). `take_wait` (~433) is the model for a blocking wait: it polls every
WATCH_POLL and gives up after WORKER_WAIT, and workers run it in the background so they wake when it exits.

Request:
1. `job.py wait [--scope] "<question>"`: `--scope` marks a question about files or functions outside Touches
   (for the integrator); without it, a question for William (behaviour, wording he sees, what is saved). It
   records the question and its kind as today, then blocks, polling every WATCH_POLL, until an answer is
   recorded for the job; it prints `answer from <who>: <text>` and exits 0. After WORKER_WAIT with no answer it
   prints `no answer yet: run job.py wait again to keep waiting` and exits 1, the job still waiting. Workers run
   it in the background, as `take --wait`.
2. `job.py answer H0NN "<text>" [--from integrator|william]` (default integrator): records the answer on a job in
   state waiting and puts it back in progress (a beat); refused, saying why, for a job that isn't waiting.
   William's answers reach a worker through the integrator (he tells it, it runs answer --from william), or he
   runs it himself.
3. `watch` and `status` say who is asked: `waiting: H0NN asks the integrator (scope): <q>` /
   `waiting: H0NN asks William: <q>`; the integrator's watch wakes on both, as today.
4. AGENTS.md and GEMINI.md (keep them in step): the worker's asking step says to use `--scope` for a file or
   function outside Touches, plain `wait` for William, both in the background, and to quote the answer in the
   response. Give the matching BOARD.md step 5 and docs/integrator.md (the queue watch) text as "For the
   integrator:" lines.

What can fail (each gets a named check in tools/test_job.py, with a fake clock and sleep as take_wait's tests):
- The answer arrives while the worker's wait is polling: it prints it and exits 0 within one poll.
- The answer arrives before the worker starts waiting again (its first wait timed out): the next `wait` prints
  the stored answer at once, without re-asking.
- The worker's session ends while waiting, and the job is returned or reassigned: the answer stays on the job
  and `take` prints it with the handoff for the session that resumes it.
- `answer` for a job not waiting, or an unknown id: refused with the reason; nothing changes.
- Two answers before the worker reads them: both are printed, in order.
- While waiting, the dead man's switch stays paused (as today), and the job's files stay held.
- Concurrent `answer` and the waiting poll: both go through the state lock (`locked`), so no answer is lost.

Reading path: `wait` → `with_job` → the beat that ends a wait (~310) → `take_wait` (the polling model) → `watch`'s
event lines (~816-850) → `take`'s print of the handoff (for a resumed job).

Run `python3 tools/test_job.py` while building, then `python3 tools/job.py test`. End your response with a
Result line; leftovers as Follow-up lines; anything for the merge as For the integrator lines.

#### Response — Codex, 2026-11-23

Branch `codex/h119-worker-answers`, implementation `5b6bb12`. All quick-test feature suites and 303
viewport checks passed on that commit, including 157 queue checks and 61 decision-log checks. Named
checks cover routing, timeout and retry, return and reassignment, refusal, ordered follow-ups, file
holds and lock contention.

Decision P-new-1 records William's “Yes. That is perfect” after confirming the worker sees answers in the
order the queue records them. If both are unread at the next poll, the worker receives both together.
No open questions.

Changed from the brief: The first answer resumes the worker's deadline. Further answers are accepted while the job still holds an unread answer, as William approved.
Changed from the brief: Updated the placeholder output assertion in tools/test_log.py under P46. The fixture now starts from the copied log's next process ID, so the required decision row can coexist with the assertion.
Changed from the brief: Extended the tools/job.py edits to the take output and waiting refresh so a resumed worker receives pending answers and the background wait process itself cannot end the wait.

For the integrator: BOARD.md step 5 can say “For work outside Touches, run `python3 tools/job.py wait --scope "<question>"` to ask the integrator. For behaviour, wording or what is saved, ask William in chat and run `python3 tools/job.py wait "<question>"`. Run either in the background. On timeout, run the same command again. Quote the answer in your response.”
For the integrator: In docs/integrator.md describe both queue-watch notifications. For a scope question, reply with `python3 tools/job.py answer H0NN "<text>"`. For a behaviour question, relay William's answer with `python3 tools/job.py answer H0NN "<text>" --from william`. William can also run the latter command directly. Unread follow-ups are delivered in recorded order.
For the integrator: H096 was still waiting in the old format at verification. After H119 merges, its worker can merge main and run `job.py wait --scope` with the original question so it is routed as scope and can receive the queue answer.
Result: 5b6bb12; job.py test passed with 303 viewport, 157 queue and 61 log checks and all feature suites passing; workers receive integrator and William answers through the queue in recorded order.
