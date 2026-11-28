### H197 — When all work is paused, the hopper brings in the integrator: wakes it, or starts a new one

Author: Claude (integrator, opus-integrator) | Date: 2026-11-27 | Status: open | For: gemini | Builds on: H196

References: P74 (William, 2026-11-27: the hopper brings in the integrator only when all work is paused; questions
don't hold the queue; a hopper-started integrator has his standing permission), H196 (the hopper in its own window,
`WAIT_FOR_THE_HOPPER.py`), H185, P13 (one integrator), T134 (launch.py), P73.

Touches: tools/job.py (the hopper's wake conditions and Pace's question rule, from H196's branch), tools/launch.py
(an integrator launch), tools/integrator.py (`take`: a `--hopper` flag), tools/startup.py (the integrator brief's
"Next actions" when started by the hopper), tools/test_job.py, tools/test_launch.py, tools/test_integrator.py,
tools/test_startup.py, docs/integrator.md (the hopper paragraph).

Reading path:
1. H196's `hopper_step` / `--forever` / `hopper-wait` and the wake conditions it factored out.
2. tools/job.py `takeable`: under `one at a time`, a job waiting on the integrator holds the pace (H185); P74 ends that.
3. tools/integrator.py `take` (the lock, `--william`), and tools/startup.py's `--role integrator` brief.
4. tools/launch.py: how a worker window gets its brief as its first prompt.

Today (checked 2026-11-27, with H196 merged): the hopper wakes the integrator on the first question, and a question
for the integrator pauses the whole queue; with no integrator session running, nothing reads the wake.

Request:
1. **Questions don't hold the queue** (P74): under `one at a time`, only a job `in progress` holds the pace; a waiting
   worker idles and the hopper launches the next takeable job.
2. **One wake: all work paused**: nothing `in progress`, no launch pending, and nothing takeable, with at least one
   job submitted or waiting on a question. This replaces the separate wakes for batch ready and questions (stale jobs
   and launch failures still wake at once). The wake's line lists what is waiting: `paused: review H191, H192;
   questions: H193 (integrator) ...; H194 (William) ...`.
3. **Wake or start**: on that wake, if an integrator's `WAIT_FOR_THE_HOPPER.py` is running (H196's pid file, or one of
   its own), it exits with the line; if none is running, the `--forever` hopper launches an integrator:
   `launch.py integrator` opens a Terminal window running Claude (`--model opus`, the same `--add-dir` and
   `--remote-control` as a Claude worker, William's own permission settings, no bypass flag) with the integrator brief
   and this first message: `You are the integrator: you have William's standing permission (P74), started by the
   hopper. Take the lock with python3 tools/HOLD_THE_INTEGRATOR_LOCK.py <session> --hopper, then: <the wake line>.
   Answer the questions, review and merge what's submitted, then run python3 tools/WAIT_FOR_THE_HOPPER.py in the
   background.` It launches at most one integrator per pause (a record in the job state, cleared when the work moves
   on), so a slow start doesn't open a second.
4. **The lock**: `take <session> --hopper` takes it when the hopper started this session (the launch record names the
   session), and records `by hopper (P74)` instead of William's word; refused otherwise.
5. docs/integrator.md: P74 in the hopper paragraph: leave the integrator running or close it; either way the hopper
   brings one back when the work pauses.

Not in this job: answering questions automatically, merging without an integrator, Codex or Gemini as integrator, or
the worker launch commands.

What can fail:
- Two integrators: one running (its wait alive) and one the hopper starts. The hopper starts one only when no wait is
  running, and once per pause. Check: tests with a wait running (no launch) and with none (one launch, not two).
- A worker answered while the integrator is still reviewing: the queue moves on (that job is `in progress` again) and
  the next pause brings the integrator back; nothing is lost.
- A hopper-started integrator stalled on a permission prompt overnight: it waits for William, like any session;
  the pause stays recorded, so no second one is launched.

Checks:
- `tools/TEST_BEFORE_MERGING.sh` passes; JOB, LAUNCH, LOCK and STARTUP tests include the cases above.
- `python3 tools/LAUNCH_A_WORKER.py integrator --dry-run` prints the Terminal command and the first message.
