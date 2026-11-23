### H089 — For the next integrator session: where things stand

Author: Claude (integrator, fretchup-73) | Date: 2026-11-22 | Status: open | For: the integrator

References: docs/integrator.md, BOARD.md, tools/startup.py, GEMINI.md.

Touches: nothing (a note). Archive it once read: `python3 tools/handoff.py archive H0NN`.

Taking over: `python3 tools/integrator.py take fretchup-73` (a /clear keeps the name; another name needs
`--william`), then `python3 tools/startup.py`, then re-arm the watch (docs/integrator.md). A watch from before the
clear may still be running; a second one is harmless.

Done this session (2026-11-22, night; main pushed): merged H080 (T105) and H081 (T106, map line written); small
fixes merged: the queue takes Gemini (`--as gemini`, `gemini/` branches, GEMINI.md = AGENTS.md plus its
differences), 99_regions.py's absolute output path, test_length_protocol.py under TESTDIR. William's calls logged:
I60 (Arc tool: A, 2-Point and Centre, A again switches; arcs don't chain), I61 (an arc on a corner is tangent),
T108 (FreeCAD fillet, after edge selection), T109 (loops of lines and arcs make a face), A38 (the floor copy
beside the model).

The queue:
- H083 (T88 step 6, Codex) is stale since 20:13: Codex ran out of tokens with uncommitted work in
  ../fretchup-h083. William's answer to its question (line.gd yes, test_log.py no, drop its A-new-1 row) was
  given to it. Leave it for Codex to resume; don't return it (the work isn't committed).
- Queued behind H083: H052 (T66 units), then H085 (Arc tool), then H086 (tangent corners).
- For Gemini (Gemini 4 Neon; William has it for a while): H087 (A38, worker/session.py) and H088 (integrate.py /
  job.py relay test progress live). Ready, no overlaps. Review them like Codex's branches.

The ultra review: the diff limit is 8,000 lines / 500 files. A local branch `ultra-base` at 2483a3b (H064's merge,
13:09) gives 7,761 lines to main; William runs `/ultrareview ultra-base` himself from the main checkout. When the
findings arrive, turn them into jobs and clear the ultra-review follow-up in docs/follow-ups.md. Still waiting on
William from earlier: a light /code-review on every merge.
