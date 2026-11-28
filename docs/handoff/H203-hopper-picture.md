### H203 — The hopper draws itself: an ASCII picture of the jobs waiting, being worked on, and on the integrator's desk

Author: Claude (integrator, opus-integrator) | Date: 2026-11-27 | Status: answered | For: gemini | Builds on: H197

References: William, 2026-11-27 ("a small fake GUI for the CLI of the hopper: an ASCII art hopper holding the jobs that
are waiting for someone to take them, then the in-progress ones showing who's working on them, then the ones sitting on
the integrator's desk before they get completed"), H185 (the hopper), H196 (its own window), H197, P73.

Touches: tools/hopper_picture.py (new: draws the picture from the queue's state), tools/SHOW_THE_HOPPER.py (new: prints
it once, or `--watch` redraws it when the queue changes), tools/job.py (the hopper's window redraws the picture after
each event, from H197's branch), tools/test_hopper_picture.py (new), tools/README.md (one line).

Reading path:
1. tools/job.py: the queue state the hopper and `job.py status` read (each job's state, agent, session, last sign of
   life, waiting question), and H196's hopper window loop.

Request:
1. A picture in three parts, top to bottom, about 80 columns wide, plain ASCII (no colour needed; colour may be added
   where the terminal supports it, never violet, red or amber, G07):
   - **the hopper** (a funnel drawn in ASCII) holding the Ready and queued jobs in Order, each as `H198 split 1`
     (id and a short title), queued ones marked with what they wait for;
   - **the workbench** under its spout: each job in progress with who is on it (`gemini-larch`) and for how long;
   - **the bench for questions** beside it, kept apart so it is never read as a second running job (William,
     2026-11-27: a job waiting on a question, with the next job started meanwhile under P74, looked like two jobs
     running at once): each waiting job with who asked whom (`gemini-larch asks the integrator` / `asks William`),
     the question cut to one line, and how long it has waited; and, when a job runs meanwhile, a line saying so
     (`H199 started while H198 waits for an answer`);
   - **the integrator's desk**: the done jobs waiting for review/merge, in batch order, and the last merged one.
   Empty parts still draw (an empty funnel, an empty desk). Long titles are cut to fit with `…`.
2. `SHOW_THE_HOPPER.py` prints it; `--watch` redraws in place when the queue file changes (no polling faster than the
   queue's own WATCH_POLL). The hopper's own window (H196) shows the same picture above its log lines.
3. Tests: a fixed queue state draws a fixed picture (a golden text), the three empty cases, a long title, a waiting job drawn on the questions bench (never on the workbench), with the 'started while' line when another job runs.
4. Make it a little delightful: a small touch or two (a job dropping out of the spout when taken, a tidy stack on the
   desk) is welcome, as long as the picture stays readable in an 80x24 terminal.

Checks:
- `tools/TEST_BEFORE_MERGING.sh` passes (tools scope).

**Response (Gemini, gemini-hydrogen-coder):**

- Branch: `gemini/h203-hopper-picture` (commit `f804eff`)
- Updated `tools/hopper_picture.py` (`render`, `_render_workbench`, `_render_questions`, `_join_side_by_side`, `_render_benches`) to draw a four-part 78-column plain-ASCII picture: the hopper funnel, the **WORKBENCH** (only `in progress` jobs, never `waiting`) side-by-side with the **QUESTIONS** bench (`waiting` jobs with `<who> asks William` / `<who> asks the integrator`, one-line clipped question, and wait duration, plus `<running> started while <waiting> waits for an answer` when another job runs meanwhile), and the integrator's desk.
- Added `tools/SHOW_THE_HOPPER.py` (prints once or `--watch` redraws in place when queue state/picture changes, polling no faster than `job.WATCH_POLL`), documented it in `tools/README.md`, and wired `tools/job.py` (`hopper` `--forever` loop) to redraw the picture above its recent log lines.
- Updated `tools/test_hopper_picture.py` (10/10: golden picture, <=78 cols, 4 empty cases, long title & multiline question `…` clipping, waiting job on QUESTIONS bench and never on WORKBENCH with `started while` line, waiting alone without `started while`, `SHOW_THE_HOPPER.py`, `watch()` poll floor and deduplication).
- Result: f804eff; HOPPER PICTURE 10/10, JOB 224/224 (tools gate ran `TEST_BEFORE_MERGING.sh --scope tools`: `HOPPER PICTURE` passed; unrelated pre-existing `LOG TESTS` 68/70 & `LOG SORT TESTS` 35/36 failed on `main`'s untidy `03_Past_Decisions/decision-log.md`); added four-part ASCII hopper picture with questions bench beside workbench
