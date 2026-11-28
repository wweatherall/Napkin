### H185 — The hopper: queued jobs run one at a time, each worker starting the next, and the integrator merges the batch once

Author: Claude (integrator, opus-integrator) | Date: 2026-11-27 | Status: open | For: gemini

References: William, 2026-11-27 ("stop hammering the computer all at once, at least while we're not in a rush: put
3 jobs in the hopper, go to sleep, they wake up the coder one at a time, and once they're all submitted you merge all
three at once; you'd still get woken up for questions"), P24 (the job queue), P37 (one job per session), P39 (no
timed check-ins), P45 (overlap by named functions), H146 (queued jobs unblock by themselves), T134 (launch.py), the
follow-up of 2026-11-27 (the gate timed out at load average 348 while three workers ran their gates at once).

Touches: tools/job.py (`takeable`, `take`, `conditions`, `watch`, and a reader for the board's `Pace:` line),
tools/integrate.py (a batch entry point; the one-branch path unchanged), tools/RUN_THE_HOPPER.py (new),
tools/MERGE_THE_BATCH.py (new), tools/test_job.py, tools/test_integrate.py, tools/README.md (two lines),
docs/integrator.md (the queue watch and review sections: a short "The hopper" paragraph), and whatever test pins the
named-scripts list (NAMED SCRIPTS TESTS) if it needs the two new names.

Reading path:
1. tools/job.py `takeable` (~line 347): how a Ready job is passed over when its Touches overlap a job in an ACTIVE
   state (`in progress`, `waiting`, `done`, `returned`: a submitted job holds its files until merged).
2. tools/job.py `take` (~526): the new worktree is always cut from `main` (~567).
3. tools/job.py `conditions` and `watch` (~1117-1165): the events that wake the integrator, and `--next`
   (`until_new`) waking once and exiting.
4. tools/launch.py's docstring and `main`: how a worker window is opened for an agent (`launch.py <agent>`).
5. tools/integrate.py's main flow: merge, bookkeeping, the gate, the P31/P44 pauses, `--continue`, `--push`.

Today (checked 2026-11-27): every Ready job that doesn't overlap another can be taken at once, and the integrator
launches one window per Ready job, so three workers can run three gates together (load average 348 on 2026-11-27;
the quick test, normally 25 s, timed out). A job that overlaps a submitted one waits until that one is merged, so
the integrator is woken, merges, launches the next worker, and sleeps again: once per job.

Request:
1. **Pace.** BOARD.md gets a `Pace:` line under `Order:`, kept by the integrator: `Pace: one at a time` or
   `Pace: all at once` (no line = all at once, today's behaviour, so nothing changes until the integrator writes it).
   Under `one at a time`, `GET_A_JOB.py` hands out no job while another job (any agent) is `in progress` or waiting
   on the integrator: that is what keeps one worker's tests on the machine at a time. A job waiting on **William**
   does not hold the pace (it may wait all night); the hopper goes on with the next job that doesn't overlap it.
2. **Stacking.** Under `one at a time`, a Ready job whose Touches overlap only jobs that are `done` (submitted, not
   yet merged) is no longer held back: its worktree is cut from the newest such job's branch instead of `main`, and
   the job's state records `base: <that branch>`. So job 2 sees job 1's changes and the two merge without conflicts.
   It still waits behind a job that is `in progress`, `waiting` or `returned`.
3. **RUN_THE_HOPPER.py** (the integrator runs it in the background, outside the sandbox, instead of
   `WAIT_FOR_THE_NEXT_JOB.py`): if nothing is in progress and a job is Ready, it launches that job's worker
   (`launch.py <the job's For agent>`; `either` means gemini) and keeps watching. Each time a job is submitted it
   launches the next. It launches at most one window per job, and not again while a launched worker hasn't taken
   its job yet (record `launched: <time>` for the job; if no take within 10 minutes, that's an event). It prints one
   line per launch and exits, waking the integrator, only when: every job of the batch is submitted (nothing Ready
   or in progress, at least one `done`), a worker asks a question (integrator or William), a job goes stale, a
   launch fails or a take doesn't follow one. Run again after answering, it carries on where it was (idempotent: it
   never launches a second worker for a job that has one).
4. **MERGE_THE_BATCH.py** `[--push] [--yes]`: merges every `done` job in stacking order (a job before the ones built
   on it; then BOARD.md's Order), doing each one's bookkeeping as `MERGE_JOB.py` does, but shows all the review
   pauses (P31 structure, P44 "changed from the brief", `Architecture-Impact`) together first and takes one
   `--continue`. It runs the gate **once**, after the last merge, and pushes once. If the gate fails, main goes back
   to where it was before the batch (nothing pushed) and it prints which jobs to merge one by one with `MERGE_JOB.py`.
   A job built on a branch that isn't in the batch (its base was returned) is left out, with a line saying why.
5. Returning a job that others are stacked on: `RETURN_JOB.py` prints which jobs were built on it (their `base`), so
   the integrator can return them too or leave them for a later batch.

Not in this job: changing what overlaps (the Touches rules), the launch commands themselves, MAX_JOBS, or the
one-branch `MERGE_JOB.py` path (it must work exactly as today).

What can fail:
- Two windows launched for one job (the hopper run twice, or re-run before the worker took it): the `launched`
  record and "has a worker already" check prevent it. Check: a test that runs the hopper step twice with no take
  between and sees one launch.
- A stacked job merged before its base: the batch orders by `base`. Check: a test with job 2 based on job 1 listed
  first in Order still merges job 1 first.
- A gate failure leaving main half-merged: main is reset to the pre-batch commit and nothing is pushed. Check: a test
  with a failing gate stub.
- `Pace:` missing or misspelt silently changing behaviour: no line, or an unknown value, means all at once, and an
  unknown value prints a warning in `CHECK_THE_JOB_BOARD.py`.

Checks:
- `tools/TEST_BEFORE_MERGING.sh` passes (full scope); quick 401/401; JOB and INTEGRATE tests include the cases above.
- `python3 tools/RUN_THE_HOPPER.py --dry-run` prints what it would launch, and `python3 tools/MERGE_THE_BATCH.py
  --dry-run` the order it would merge in, without launching or merging.
