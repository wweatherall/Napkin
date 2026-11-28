### H196 — The hopper runs in its own Terminal window; the integrator waits for it separately (and Order is kept across agents)

Author: Claude (integrator, opus-integrator) | Date: 2026-11-27 | Status: answered | For: gemini

References: William, 2026-11-27 ("launch the hopper in a new terminal window so it can run independently of you"),
H185 (the hopper), T134 (launch.py opens Terminal windows), P39 (no timed check-ins), the follow-up of 2026-11-27
(the hopper launched H192 before H195: Order not kept across agents), P73.

Touches: tools/job.py (`hopper_step`, `hopper`, and the `hopper` / new `hopper-wait` commands in `main`),
tools/RUN_THE_HOPPER.py, tools/WAIT_FOR_THE_HOPPER.py (new), tools/launch.py (a function that opens a Terminal window
for a command), tools/test_job.py, tools/test_launch.py, tools/README.md, docs/integrator.md (the hopper paragraph).

Reading path:
1. tools/job.py `hopper_step` and `hopper` (~1355-1460): each poll launches the next worker or returns `exit` (batch
   ready, a question, stale, launch timeout or failure), and `hopper` stops on `exit`, which is what wakes the
   integrator's background Bash.
2. The `for j in candidates` loop in `hopper_step`: it calls `takeable(<entry's agent>)`, which returns that agent's
   next Ready job, not the entry, so a finished Gemini entry first in Order launched H192 ahead of H195 (Codex).
3. tools/launch.py `main` and `applescript`: how a worker's Terminal window is opened.

Today (checked 2026-11-27): the hopper runs as the integrator's background Bash, so it ends when the integrator's
session is cleared, and launching stops until a new integrator starts it again. It also does two jobs at once:
launching, and waking the integrator by exiting.

Request:
1. **The launcher keeps running**: `RUN_THE_HOPPER.py --window` opens a Terminal window (via launch.py's new function,
   outside the sandbox) running `RUN_THE_HOPPER.py --forever`, and prints that it did. `--forever` launches as today but
   never exits on a wake condition: it prints each one (`20:14 batch ready to merge: H191, H195 ...`) and carries on
   (a question waits for its answer; batch ready waits for new Ready jobs). Plain `RUN_THE_HOPPER.py` keeps today's
   behaviour. Only one `--forever` hopper at a time: a second one started while one runs says so and exits (a pid file
   in .git/, cleared when the window's process ends or found dead).
2. **The integrator's wake**: `WAIT_FOR_THE_HOPPER.py` (`job.py hopper-wait`), run in the integrator's background,
   launches nothing and exits on the first new wake condition the hopper would have exited on (the same conditions,
   from the same code: factor them out of `hopper_step` so the two can't drift), printing it. Like
   `WAIT_FOR_THE_NEXT_JOB.py`, it ignores conditions already true when it starts, except batch ready, which it reports
   at once (a cleared integrator must learn that the batch is waiting).
3. **Order across agents**: `hopper_step` launches the first entry in Order that is takeable **as itself**
   (`picked["id"] == j["id"]`), or a returned job (takeable already puts those first). Test: Order [done Gemini job,
   Ready Codex job, Ready Gemini job] launches the Codex one.
4. docs/integrator.md's hopper paragraph: start the hopper once with `RUN_THE_HOPPER.py --window`; after each start-up
   or clear, run `WAIT_FOR_THE_HOPPER.py` in the background; no need to restart the hopper after a clear.

Not in this job: what counts as a wake condition, batch merging, Pace, or the worker launch commands.

What can fail:
- Two hoppers launching for one job (the window's and an old background one): the pid file refuses a second
  `--forever`, and the existing `launched` record still stops a double launch. Check: a test starting a second one.
- The integrator never woken: the wait reuses the hopper's own conditions. Check: a test where the hopper side sees
  batch ready and the wait exits with the same line.

Checks:
- `tools/TEST_BEFORE_MERGING.sh` passes; JOB and LAUNCH tests include the cases above.
- `python3 tools/RUN_THE_HOPPER.py --window --dry-run` prints the Terminal command without opening it.

Response: Added `open_terminal` in `tools/launch.py` and wired `RUN_THE_HOPPER.py --window` / `--forever` (with a `.git/shopsketch-hopper.pid` single-instance lock cleared on exit or dead pid), factored `hopper_wake_conditions` and `_next_hopper_candidate` out of `hopper_step` in `tools/job.py` so `WAIT_FOR_THE_HOPPER.py` (`job.py hopper-wait`) shares the exact wake conditions while ignoring already-active non-batch conditions, fixed `hopper_step` to preserve Order across agents unless a returned job takes priority, updated `docs/integrator.md` and `tools/README.md`, and added tests in `tools/test_job.py` (220/220) and `tools/test_launch.py` (17/17). Merged `main` after asking via `job.py wait --scope` about `P74` in `decision-log.md`; integrator answered: "Main is fine: 1385804 (P74 and H197) added the index line; your branch starts at 36d009a, just before it, so it sees the ruling file without the line. Merge main into your branch (git merge main), rerun the gate and carry on; no need to wait. Note H197 is queued after you and builds on your work." `tools/TEST_BEFORE_MERGING.sh` passed (`GATE PASS (scope tools): tools quick test passes; 34 s total`).

Result: `RUN_THE_HOPPER.py --window` / `--forever`, `WAIT_FOR_THE_HOPPER.py`, and cross-agent hopper Order implemented and passing gate (H196).
