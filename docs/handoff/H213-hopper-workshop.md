### H213 — The hopper workshop: William's animated, width-aware hopper picture (made with ChatGPT) brought into Napkin

Author: Claude (integrator, integrator-teak) | Date: 2026-11-28 | Status: open | For: either | Item: T170

References: William, 2026-11-28: "I worked on this with chat gpt can you add getting this all integrated into our
setup to your jobs?"; the prototype in `docs/proposals/hopper-workshop/` (README.md first, then `hopper_workshop.py`,
`test_hopper_workshop.py`, `integration.patch`, `preview-78.txt`, `preview-120.txt`); H203 (the current
`tools/hopper_picture.py` and `tools/SHOW_THE_HOPPER.py`); the keep-awake change on main (`job.py` `KeepAwake`,
`hopper_has_work`, William, 2026-11-28); C07 (no token cost: it's a terminal picture), C06.

Today: the `--forever` hopper (`tools/job.py` `hopper`) redraws `hopper_picture.render_root` in its Terminal window
when the picture changes, with the last six log lines under it; `SHOW_THE_HOPPER.py [--watch]` draws the same picture.
The prototype adds an animated workshop (a sprite per agent: Claude a sunburst, Gemini twin diamonds, Codex a knot),
side-by-side panels at 100+ columns, compact symbols when the window is small, and keeps the old picture for
redirected output and `--plain`. Its patch was made against excerpts reconstructed from GitHub, not a live checkout,
and main has moved since (the keep-awake lines sit in the same loop), so expect to apply it by hand.

Touches: tools/hopper_workshop.py (new), tools/test_hopper_workshop.py (new), tools/SHOW_THE_HOPPER.py,
tools/job.py (`hopper`: the drawing part of its loop only), tools/README.md (the SHOW_THE_HOPPER and RUN_THE_HOPPER
lines), docs/integrator.md (one line, if the hopper's window changes how it reads).

Request:
1. Bring `hopper_workshop.py` into tools/ and wire it in as the patch intends: the `--forever` hopper draws the
   workshop in a Terminal (a tty, TERM not dumb), anything else keeps the old picture; `SHOW_THE_HOPPER.py` draws the
   workshop, `--plain` the old one. Keep H203's renderer and its golden tests unchanged.
2. Keep everything the loop does today, in the same order, in the workshop path too: the stop-file check each poll
   (STOP_THE_HOPPER must still stop it within one poll), `hopper_step`, `KeepAwake.follow`, the log lines (now passed to
   the workshop), and the poll interval. Whatever waits between polls must go through the `sleep` the function was
   given, so the existing hopper tests (which pass a `sleep` that raises) still drive it.
3. Make `test_hopper_workshop.py` one of ours: the feature tests find `tools/test_*.py` and need the summary line
   `HOPPER WORKSHOP TESTS: N passed, M failed` (see any tools test); convert from unittest or wrap it, and run it with
   `tools/RUN_ONE_TEST.sh`.
4. Check the agent names it draws against the ones the queue records (`claude`, `codex`, `gemini`) and that an unknown
   agent gets a plain sprite rather than an error.
5. Look at it: run `python3 tools/SHOW_THE_HOPPER.py` in a Terminal at about 78 and 120 columns against the live queue
   (read-only) and paste both into scratch/; say in the response how it looks and anything you'd change, as a question
   for William if it's a matter of taste.

What can fail (P42):
- The workshop raises on an odd queue (a job with no agent, a returned job, a stacked `base:` job): the hopper must keep
  dispatching. Check: render the prototype's edge states plus those three; and in `hopper`, a drawing error falls back to
  the old picture for that poll with one log line, never stopping the loop.
- Output that isn't a terminal gets escape codes. Check: `SHOW_THE_HOPPER.py | cat` prints the plain picture.

Checks:
- `tools/test_hopper_workshop.py` (summary line), `tools/test_hopper_picture.py` and `tools/test_job.py` pass.
- `tools/TEST_BEFORE_MERGING.sh` passes.
