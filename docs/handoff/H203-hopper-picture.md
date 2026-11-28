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
   - **the workbench** under its spout: each job in progress with who is on it (`gemini-larch`), for how long, and a
     mark when it is waiting on a question (`?`);
   - **the integrator's desk**: the done jobs waiting for review/merge, in batch order, and the last merged one.
   Empty parts still draw (an empty funnel, an empty desk). Long titles are cut to fit with `…`.
2. `SHOW_THE_HOPPER.py` prints it; `--watch` redraws in place when the queue file changes (no polling faster than the
   queue's own WATCH_POLL). The hopper's own window (H196) shows the same picture above its log lines.
3. Tests: a fixed queue state draws a fixed picture (a golden text), the three empty cases, a long title, and a
   question mark on a waiting job.
4. Make it a little delightful: a small touch or two (a job dropping out of the spout when taken, a tidy stack on the
   desk) is welcome, as long as the picture stays readable in an 80x24 terminal.

Checks:
- `tools/TEST_BEFORE_MERGING.sh` passes (tools scope).

**Response (Gemini, gemini-hydrogen-coder):**

- Branch: `gemini/h203-hopper-picture` (commit `1b78427`)
- Added `tools/hopper_picture.py` (`render`, `render_root`, `watch`, `clip`, `_batch_order_done`, `_last_merged`) drawing the three-part 78-column plain-ASCII picture: the hopper funnel (Ready/queued jobs in Order, queued marked `[waits: ...]`, launched jobs dropping out of the spout `|H201|` / `v`), the workbench (in-progress/waiting jobs with worker name, elapsed duration, and `?` when waiting), and the integrator's desk (done jobs as `[=]` in batch order, plus `last merged`), with `(empty)` states and `…` truncation.
- Added `tools/SHOW_THE_HOPPER.py` (prints once or `--watch` redraws in place when queue state/picture changes, polling no faster than `job.WATCH_POLL`) and documented it in `tools/README.md`.
- Wired `tools/job.py` (`hopper` `--forever` loop) to redraw the picture above its recent log lines after each event or picture change.
- Added `tools/test_hopper_picture.py` (9/9: golden picture, <=78 cols, 3 empty cases, long title `…` clipping, `?` on waiting job, `SHOW_THE_HOPPER.py`, `watch()` poll floor and deduplication).
- Result: 1b78427; HOPPER PICTURE 9/9, JOB 224/224, gate (scope tools) passed; added three-part ASCII hopper picture (`hopper_picture.py`, `SHOW_THE_HOPPER.py`, `job.py` hopper window)
