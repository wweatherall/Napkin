### H202 — Design: how a fit that lost its face looks (a chain crumbling, or another gentle metaphor), a proposal with drafts for William

Author: Claude (integrator, opus-integrator) | Date: 2026-11-27 | Status: open | For: codex

References: I77 (William, 2026-11-27: "Reference unavailable is a bit harsh, it still has the length it got"; give it a
metaphor, "like a chain crumbling to the ground"), G07 (violet cuts, red rejects, amber is new: none of them here),
G01 (feel first), H201 (the fit's `detached` state in bodies.json), docs/proposals/T159-push-pull.md (a proposal's shape).

Touches: docs/proposals/fit-detach-look.md (new), viewport/demos/fit_detach_demo.tscn (new) and viewport/demos/fit_detach_demo.gd (new: a scene William can open in Godot to watch each option; nothing in the app loads it).

Request:
1. Two or three looks for the moment a fit detaches and for a detached fit afterwards (for example: a short chain
   between the boards whose links fall and fade; a thread that goes slack; a small broken-link badge on the end face),
   each drawn in the demo scene with the app's own board and line styles, under 1.5 s, using no violet, red or amber.
2. For each: what the user sees at the moment and afterwards, how it says the board kept its length, how it reads
   with a paused fit (I76) beside a detached one, and what it costs to build (files, frame time).
3. A recommendation and what to ask William. No change to the app.

Checks:
- `tools/TEST_BEFORE_MERGING.sh` passes (docs scope); the demo scene opens headless without errors.
