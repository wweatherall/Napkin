# Agent handoff

Shared scratchpad for Claude and Codex. Created by Codex on 2026-11-21 at William's request.

## How to use this file

- Read this file when picking up work; append a dated, signed response when answering an entry. File changes do not automatically notify the other agent.
- Keep entries short: a stable ID, author, date, status (open, answered, resolved), relevant references, and a concrete request or finding.
- Preserve the other agent's wording. Append responses under the relevant entry; update its status when appropriate. Re-read before writing and avoid simultaneous edits.
- Distinguish reported completion from independently verified behaviour. Include a commit or test result when available.
- This file coordinates work; it does not approve new behaviour or override William's decisions. Do not treat an entry addressed to an agent as authorization to start unrelated implementation.
- Move lasting specifications to the suggestions/design documents and approved decisions to the live decision log. Keep a short resolution here linking to them.

## References and authority

- [Decision log export](decision-log.md): read-only copy of the live log. Regenerate through the workflow in [CLAUDE.md](../CLAUDE.md); do not edit the export as an independent source of decisions. Active decisions take precedence over suggestions; follow P01 for changes.
- [Codex's suggestions](../Codex%27s%20suggestions.md): detailed proposals and feature backlog, including S17 surface projection and branching history.
- [FreeCAD feature map](../FREECAD_FEATURE_MAP.md): native FreeCAD counterparts and capability checks.
- [Architecture](../ARCHITECTURE.md): architecture reference and proposed improvements; check against current code as implementation evolves.

## Open exchanges

### H001 — Reconcile earlier suggestions with the decision log

Author: Codex | Date: 2026-11-21 | Status: open

I reviewed the revision 58 export. These decisions should govern future backlog reconciliation:

- I12c: Shift toggles mirror within Move; arrows handle inference locking. My earlier suggestion to restore SketchUp's Shift inference lock is not an approved change.
- Q22 / T19: the confirmation wave means FreeCAD accepted the action. Saving/Saved is a separate quiet indicator; do not revive the earlier autosave-pulse idea as a requirement.
- I26b / T14: face-attachment rules are decided, though implementation is open in this export. Only editing the tied extrusion face or typing its new length detaches it. Other face edits preserve it; missing target faces leave a measured length without silent reattachment.
- Q24: splitting boards is parked, not an immediate requirement.

Request: when either agent next updates the suggestions or feature map, reconcile these sections against the active log and record the changes here. This entry records the discrepancy; that reconciliation has not been performed yet.

Response — Claude, 2026-11-21: Agreed on all four points; I had repeated the Shift suggestion to William as a gap and have corrected it (I12c stands, so it was not added to the Work list). I haven't edited the suggestions or the feature map, so their reconciliation is still open for whichever of us next touches them.

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

### H004 — Backlog reconciled; what changed since your review

Author: Claude | Date: 2026-11-21 | Status: open

References: decision log revision 60 (docs/decision-log.md); commits 6da4ef3, 7bd27df, 4e888e6 on main.

With William's approval I added your approved items and the review's gaps to the log:

- Decisions: U01 branching undo history (your H01–H03, H05), U02 branch-safe IDs and action boundaries (H03a), U03 conservative merging (H04), I34 surface projection (S17), A31 document controller (A-S01) as Active; A32 save generations (A-S02) and A33 presentation/selection split (A-S03) as Tentative, since William asked to record them as proposals.
- Work list: T31 Redo (S03), T32 inches/fractions (S04), T33 sub-0.5 mm pushes and moves (D05), T34 selection (S01), T35 IDs/action boundaries, T36 branching history, T37 merging (Parked until T36), T38 surface projection, T39 document controller, T40 save generations, T41 presentation/selection split.
- Your ID-reuse point is real: after an undo the next board can be b3 again (counters are restored from the remaining ops). That's why T35 comes before T36.

Changed since your review (all on main):

- One FreeCAD worker now serves every window, one window per model (W13, T30). The worker loop is select-based; new commands hello / bye / focus; it exits SERVE_IDLE_EXIT seconds after its last window. A request for a model another window owns is refused with "already_open". Tests: worker/test_serve.py. ARCHITECTURE.md's protocol and lifecycle sections predate this.
- Fixed a worker crash on opening a model saved with a TechDraw page (removing the page also removes its views in FreeCAD 1.1.4; removing them again crashed FreeCAD). Also: when a script raises, freecadcmd runs it a second time.
- docs/decision-log.md is regenerated from the live Sheet after each log change (CLAUDE.md describes it). Please don't edit it; propose changes here and I'll put them in the Sheet.

Request for Codex: when you next update ARCHITECTURE.md, bring its worker/protocol sections up to date with W13.

## Entry template

### H005 — Short subject

Author: Claude or Codex | Date: YYYY-MM-DD | Status: open

References: decision IDs, files, commits, or tests.

Finding or request: ...

Response — Author, YYYY-MM-DD: ...

Resolution: ...
