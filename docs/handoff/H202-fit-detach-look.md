### H202 — Design: how a fit that lost its face looks (a chain crumbling, or another gentle metaphor), a proposal with drafts for William

Author: Claude (integrator, opus-integrator) | Date: 2026-11-27 | Status: answered | For: codex

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

Response — Codex, 2026-11-28 · `codex/h202-fit-detach-look` · `7b029c4`

[The proposal](../proposals/fit-detach-look.md) and [the Godot comparison](../../viewport/demos/fit_detach_demo.tscn)
show falling links and slack thread beside an intact paused fit. Each effect takes 1.08 s, or 1.32 s including
replay lead-in. Both fitted boards stay at 600 mm and the detached end keeps a charcoal mark. I recommend
falling links because the intact and opened shapes read more distinctly side by side.

The docs-scope merge gate passed for the proposal. The recorded quick run on the complete commit passed
405 viewport checks and all feature tests. The stand-alone scene opened headlessly in Godot 4.6.1. I checked
both variants' held length, settled mark, paused connector and mid-effect replay, and inspected 1280 × 800
Compatibility renders. The proposal estimates draw calls and outlines the production frame-time check.

Follow-up: After William replays both, ask which look best shows that the board kept its length and the fit let go.

Result: 7b029c4; docs-scope merge gate, recorded quick test, headless scene and both rendered drafts passed; proposed two standalone fit detachment effects and recommended falling links
