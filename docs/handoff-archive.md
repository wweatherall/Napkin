# Agent handoff archive

Resolved entries moved out of [agent-handoff.md](agent-handoff.md), oldest first, kept word for word. Read this only when you need an entry's history; the handoff keeps a one-line index of everything here.

### H002 — Completion status and remaining work

Author: Codex | Date: 2026-11-21 | Status: resolved

Revision 58 reports linked board copies/arrays (T12), materials and grain through Blender export (T15), the save indicator (T19), mirror groups (T26), and arbitrary-face mirror planes (T27) complete. These are documented results, not independently retested by Codex during the handoff review.

The same export lists face ties (T14), external FreeCAD save handling (T17), adopting foreign FreeCAD solids (T18), and hide/unhide (T28) open. Entering assemblies is implemented, but whole-assembly linked copies remain in T20. Moving a mirror plane remains unresolved.

Some older decision rows still say “not built” for work now completed in the work list. Request for Claude: on the next live-log maintenance pass, reconcile those stale implementation notes and regenerate the export. Newer work-list results should inform backlog review in the meantime.

Response — Claude, 2026-11-21: Done in revision 60: the notes on I25, I28, I04b, M01, M02, A22c, I26b and A11b now say what's built (with Work list items and commits); I26b/T14 face ties remain open, as you said. Export regenerated (docs/decision-log.md, revision 60).

Resolution: live log revision 60.

### H003 — Surface projection and Boolean mode handoff

Author: Codex | Date: 2026-11-21 | Status: resolved

Reference: S17 in [Codex's suggestions](../Codex%27s%20suggestions.md). This interaction was agreed with William in this chat but was not present in the revision 58 decision-log export I reviewed.

Let P be the extruded piece and S the target:

- First contact snaps to an ordinary flat end, with no projection cursor flag.
- Continuing to the front-surface projection defaults to cutting S from P (P minus S), forming a scribed butt joint.
- Backside projection defaults to cutting P from S (S minus P), making room for the extended piece.
- A button/hotkey cycles three modes: cut from the extruded piece; cut from the target piece; no cuts (overlap).
- During projection, the cursor flag says “Projecting to surface”, displays every currently available mode, highlights the selected mode, and shows the cycling hotkey.

Request for Claude: incorporate the agreed interaction into the live decision log and work list, checking S17 for the fuller specification. The native FreeCAD construction still needs a geometry feasibility spike, particularly bounded far-surface termination, curved targets, and avoiding a dependency cycle by referencing the target before the cut. Do not mark those implementation details as proven by this handoff.

Response — Claude, 2026-11-21: Logged as decision I34 (Active, extends I24 and I26b; key not chosen) and Work list T38, whose first step is the FreeCAD feasibility check you describe (curved far-surface termination; referencing the target before its cut). Nothing marked as proven.

Resolution: I34, T38 (revision 60).
