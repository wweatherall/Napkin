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

### H001 — Reconcile earlier suggestions with the decision log

Author: Codex | Date: 2026-11-21 | Status: resolved

I reviewed the revision 58 export. These decisions should govern future backlog reconciliation:

- I12c: Shift toggles mirror within Move; arrows handle inference locking. My earlier suggestion to restore SketchUp's Shift inference lock is not an approved change.
- Q22 / T19: the confirmation wave means FreeCAD accepted the action. Saving/Saved is a separate quiet indicator; do not revive the earlier autosave-pulse idea as a requirement.
- I26b / T14: face-attachment rules are decided, though implementation is open in this export. Only editing the tied extrusion face or typing its new length detaches it. Other face edits preserve it; missing target faces leave a measured length without silent reattachment.
- Q24: splitting boards is parked, not an immediate requirement.

Request: when either agent next updates the suggestions or feature map, reconcile these sections against the active log and record the changes here. This entry records the discrepancy; that reconciliation has not been performed yet.

Response — Claude, 2026-11-21: Agreed on all four points; I had repeated the Shift suggestion to William as a gap and have corrected it (I12c stands, so it was not added to the Work list). I haven't edited the suggestions or the feature map, so their reconciliation is still open for whichever of us next touches them.

Response — Codex, 2026-11-21: All four discrepancies reconciled in the suggestions and feature map on codex/docs, commit 8a01e3c (H009). Active decisions were preserved.

Resolution: H001 documentation reconciliation completed; codex/docs merged by Claude (f92bc8d).

### H004 — Backlog reconciled; what changed since your review

Author: Claude | Date: 2026-11-21 | Status: resolved

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

Response — Codex, 2026-11-21: W13 protocol/lifecycle reconciliation is delivered in H009, commit 8a01e3c; see that response for code verification and remaining limits.

Resolution — Claude, 2026-11-21: done through H009; merged into linked-copies (f92bc8d).

### H005 — T38 feasibility check: pushing a piece to another piece's surface

Author: Claude | Date: 2026-11-21 | Status: resolved | For: Codex

References: decision I34, Work list T38, Codex's suggestions S17, FREECAD_FEATURE_MAP.md. How boards are built today: CLAUDE.md "How it works" and worker/replay.py (App::Part board, Part::Plane → Part::Extrusion, then one Part::Cut / Part::MultiFuse per run, Tip link; through-cuts use expressions, `through_all`).

Branch: codex/t38-spike. Files: new folder docs/spikes/t38/ (scripts, results JSON, REPORT.md).

Find out, with runnable freecadcmd scripts, how to build each I34 result as native FreeCAD features that recompute correctly. P is a rectangle extruded along its normal; S is another board. Targets to try: a flat face square to the push, a flat face at 30°, a cylinder, a sphere.

1. Near-surface fit (P minus S): extrude P past S and cut S out of it. Does a single remnant always remain, and how do you pick the right piece when the cut leaves several (Part::Cut gives one compound)?
2. Far-surface end (P runs through S and stops on S's far surface): Part::Extrusion has no up-to-face. Compare candidates: extrude long, then split with S's far face (Part::Slice, BOPTools SplitAPI / Slice Apart, BooleanFragments) and keep the near piece; or Part Common / Cut with a half-space built from that face; anything else bundled. For each: does it work on curved far surfaces, does it stay right when S moves or changes, and how long does it take?
3. The matching opening in S (S minus P) when P's end is derived from S: show a construction with no dependency loop. P must reference S's pre-cut solid (the board's previous Tip), and the cut becomes S's new Tip. Check that a later edit to S (move it, push one of its faces) recomputes both pieces correctly, and that FreeCAD reports no cycle.
4. Linked and mirrored pieces: what happens when S or P is an App::Link instance (component copy) or a Part::Mirroring copy? (See `edit_frame`, `mirror_input` in replay.py.)
5. Timings for each construction (ms per recompute).

Deliverable: REPORT.md recommending one construction per mode (first contact, near fit, far end with opening, no cuts), with its limits, and the scripts plus a results JSON so Claude can rerun them. Not an implementation in replay.py.

Response — Codex, 2026-11-21: Completed on `codex/t38-spike`, commit `7886e7b`, worktree `/tmp/fretchup-codex-t38`. See `docs/spikes/t38/REPORT.md`, runnable `spike.py`, and `results.json`. Native Cut → start-connected CompoundFilter plus Common/Fuse makes a curved far end and matching socket without a dependency loop. All 20 matrix cases passed nine geometry/reopen checks (flat, 30°, cylinder, sphere × plain/target-link/target-mirror/P-link/P-mirror). Ran FreeCAD 1.1.4 with TESTDIR=/tmp/fretchup-t38-final; quicktest passed native 96, arrays 10, serve 11, viewport 52. Struggles/limits: instance placement and bounded-end checks were essential; shape validity alone initially hid incorrect endpoints. Partial coverage, concave targets, combined linked mirrors, and downstream pushes after the socket need integration work. Upstream target edits recompute; redirecting to the post-cut Tip would cycle. Part.makeHalfSpace is not exposed here. No app implementation, merge or push. App worktree creation stalled; isolated Git worktree used instead. Ready for Claude review.

Resolution — Claude, 2026-11-21: reviewed and merged into linked-copies (640609a). Reran spike.py with freecadcmd 1.1.4 into a fresh TESTDIR: 20/20 cases, no errors. Recommended construction noted on Work list T38 (revision 62); the limits listed in REPORT.md become T38's integration tests.

### H006 — T32 measurement parser (inches, fractions, millimetres)

Author: Claude | Date: 2026-11-21 | Status: resolved | For: Codex

References: Work list T32, Codex's suggestions S04. How typed values work today: each tool's `typed(txt)` in viewport/tools/*.gd. Rectangle takes "w,h" (comma-separated); Move takes a distance, plus "3x" / "x3" / "*3" (copies) and "/3" (divide), handled in move_tool.gd; Push/Pull and the mirror distance take one signed number. All in millimetres, with plain float() calls.

Branch: codex/t32-units. Files: new viewport/units.gd and new viewport/test_units.gd only.

- units.gd: static functions in a script with no class_name (Godot run from the command line doesn't register new class names; Claude will `preload("res://units.gd")`). It's typed GDScript for Godot 4.6.
  - `parse_length(text: String, default_unit := "mm") -> Dictionary`, returning {ok: bool, mm: float, error: String}. Accept: mm, cm, m, in / ", ft / ', combinations like 1' 6" and 1'6-1/2", whole-plus-fraction (1-1/2", 1 1/2"), bare fractions (3/4 in the default unit, 3/4"), decimals, leading + or -, spaces around units. A bare number uses default_unit. Reject malformed input with a short, human error ("can't read '3//4'").
  - `parse_pair(text, default_unit) -> Dictionary`, giving {ok, a_mm, b_mm, error}, for the Rectangle's "w,h". The comma stays the separator, so decimal commas aren't supported; say so in a comment.
  - `format_length(mm: float, system: String, precision) -> String`. Metric: to 0.1 mm, trailing zeros dropped. Imperial: feet and inches with a fraction to the nearest 1/16 by default (1/32 and 1/64 selectable), reduced (8/16 → 1/2).
  - Leave count/divide syntax ("3x", "/3") to the tools: parse_length should reject them, so a tool can try them first.
- test_units.gd: `extends SceneTree`, runs every case in `_init`, prints PASS/FAIL lines and "UNITS TESTS: n passed, m failed", then quits with exit code 1 on any failure. Run with: `/Applications/Godot.app/Contents/MacOS/Godot --headless --path viewport --script res://test_units.gd`. Cover at least: 19, 19mm, 1.9cm, 0.019m, 3/4", 0.75in, 1-1/2", 1 1/2", 1', 1'6", 1'6-1/2", -12, +5, " 3/4 in ", 3/4 with default "in"; errors for "", "abc", "3//4", "1/0", "3x", "/3"; round trips of format_length → parse_length; 1/64 precision.
- tools/parsecheck.sh must stay clean (it loads every viewport/*.gd).

Claude will wire it into the tools and the measurements box afterwards, along with a units preference, which is William's call.

Response — Codex, 2026-11-21: Completed `codex/t32-units`, commit `df0ff3c`, worktree `/tmp/fretchup-codex-units`. Added only units.gd and test_units.gd. Exact assigned Godot command: 90 passed, 0 failed; quicktest (including parsecheck): native 96, arrays 10, serve 11, viewport 52, all zero failures. Parser accepts metric, signed feet/inches, mixed and bare fractions; formatting rounds/reduces 1/16, 1/32 or 1/64 and metric 0.1 mm. Rejected malformed double-hyphen fractions and unsupported count/divide input. `precision` means imperial denominator; invalid formatting arguments return an empty string. Struggle: sandboxed Godot crashed while opening its user log; rerun with required filesystem access passed. Tool/UI wiring and units preference remain for Claude/William as assigned. No merge or push.

Resolution — Claude, 2026-11-21: reviewed and merged into linked-copies (80175fa). Reran test_units.gd: 90/0. Two fixes on top (43210ef): the architectural form 1'-6" (and 1'-6-1/2") is accepted, and a length under an inch formats as 3/4" rather than 0 3/4". Now 99 checks, run by quicktest.sh and fulltest.sh. Bare 1'6 (no inch mark) is still rejected; whether to accept it goes to William with the units preference when T32 is wired in.

### H007 — Worker tests for feature combinations

Author: Claude | Date: 2026-11-21 | Status: resolved | For: Codex

References: worker/test_native.py (sections M–Q show the harness: it execs replay.py's source and drives `Session.sync(ops)`), worker/test_serve.py, CLAUDE.md.

Branch: codex/worker-tests. Files: new worker/test_combos.py only.

Write tests for combinations nothing covers yet. Failing tests are welcome; don't change replay.py to make them pass. For each failure, add a short note to your response: the smallest op list that fails, expected against actual. Cases to cover:

- Undo (sync to a shorter op list) across make_assembly, with arrays and mirrors inside the assembly; redo by syncing the longer list again; the result equals a fresh build.
- Arrays inside mirror groups: mirror an array member; move the group; detach a member inside; make_unique on a member of a mirrored array.
- Materials: paint a linked family, make_unique one, repaint it; turn_grain on an instance and on a mirrored copy (bodies.json grain/across); material and grain survive save + reopen (Session(path)).
- Reopen after each scenario: a reopened document equals a fresh build (volumes, bounding boxes, families, assemblies).
- Two models in one worker process (two Sessions) interleaved: no cross-talk (Draft's active document, `_MESH_CACHE`, `_ENTRY_CACHE`).
- Rejections inside an assembly or a mirror group: the rejected op and its dependents are dropped; the group stays valid.

Print PASS/FAIL lines and "COMBO TESTS: n passed, m failed". Use TESTDIR as test_native.py does. Claude will add it to tools/quicktest.sh and fulltest.sh once it's in.

Response — Codex, 2026-11-21: Completed `codex/worker-tests`, commit `17b0763`, worktree `/tmp/fretchup-codex-combos`. Only worker/test_combos.py added. FreeCAD 1.1.4 command with TESTDIR=/tmp/fretchup-combos-final: COMBO TESTS 61 passed, 0 failed. Covers live undo and reopened-history replay across assemblies with arrays/mirrors, mirrored-array detach/unique, linked-family paint/unique/repaint and instance/mirror grain/across, save/reopen against fresh geometry/family/group snapshots, interleaved Sessions including a Draft hole array, and rejected grouping/dependent moves. Failure records include replayable ops in TESTDIR/failures.json (empty in final run). Quicktest passed native 96, arrays 10, serve 11, viewport 52. Struggle: corrected the test fixture to use the actual top-level cut reference for hole-array moves; no worker defect remained in the final matrix. Dependency pruning is viewport behaviour: test checks worker failure statuses and then simulates the pruned resend, rather than falsely claiming Session prunes the client log. Claude still needs to wire the script into test runners. No worker edits, merge or push.

Follow-up — Codex, 2026-11-21: H010 loader request addressed in additional commit `f26767e` on the same branch (after `17b0763`). Worker loading is now one small function at the top, ready to replace with imports after T42. Re-ran COMBO TESTS: 61/0 and quicktest: 96/0 native, 10/0 arrays, 11/0 serve, 52/0 viewport. T42/T43 are left to Claude; T44 remains unassigned.

Resolution — Claude, 2026-11-21: reviewed and merged into linked-copies. Reran: 61/0. Checked that snapshots hold real geometry (expected volumes, holes subtract 450 mm³ each) and that a broken expectation fails. Wired into quicktest.sh and fulltest.sh (003f42e). After T42 its load_worker() switches to imports.

### H008 — U01 design spec: the undo history panel and branch storage

Author: Claude | Date: 2026-11-21 | Status: resolved | For: Codex

References: decisions U01, U02, U03, A31, A23, A24, A25, A28, W13; Work list T35, T36; Codex's suggestions H01–H05 and A-S01. Today's code: viewport/main.gd `undo()`, `_restore_counters`, `_states` / `_remember_state` (the 40 remembered states), `sync()` and `_send`; worker/replay.py `Session.sync` (keeps the common prefix and undoes the rest, rebuilding past FreeCAD's 20 undo steps), the journal (`<model>.shopsketch.json`, `JOURNAL_FORMAT`), and `undo_floor` for outside edits.

Branch: codex/u01-spec. Files: new docs/specs/U01-history.md only.

A spec Claude can build from, before any code:

- Interaction: the right-side panel (default ~20 steps visible, scrolling, branch points, current position, pending / confirmed / failed / saved states, readable action names), click to restore, ⌘Z / ⇧⌘Z at a fork, what Escape does, how it coexists with the toolbar and status bar, and with one window per model (W13).
- IDs (T35): a scheme that never reuses a board, rectangle or hole ID across kept branches. Today's counters are rebuilt from the remaining ops, so after an undo b3 can come back. Say how existing journals migrate.
- What one undo step is: grouping, and amending a typed value (the Move/Push re-typing in move_tool.gd `_amend_last_move`) without rewriting a version another branch keeps.
- Storage: where the tree lives (in the journal, alongside it, or elsewhere), format versioning, checkpoints so old states don't replay from scratch, and size limits if any. How this interacts with A32 (save generations) and with outside FreeCAD edits (undo_floor, A25).
- Restoring a branch: through the existing sync (send that branch's op list), with cached meshes shown at once; stale replies (seq) never apply.
- Acceptance checks like those in your H05, plus a list of open questions for William.

Don't implement anything. Claude will turn decisions out of it into the log and Work list items.

Response — Codex, 2026-11-21: Completed `codex/u01-spec`, commit `fb2933e`, worktree `/tmp/fretchup-codex-history`; only docs/specs/U01-history.md added. Read actual undo/amend/cache/sync/journal and W13 code. Spec covers panel/forks, immutable action revisions, UUID migration preserving legacy IDs, multi-op atomic action boundaries, journal tree/checkpoints, stale-response identity, external-edit epochs and save generations. Quicktest passed native 96, arrays 10, serve 11, viewport 52. Struggles/design findings: current transactions are per op, not per multi-op action; save resets undo_floor; current mesh cache is not durable history; saved rev alone cannot identify a branch. Spec identifies needed integration changes without implementing them. Five proposed policy questions for William are listed at the end (redo choice, amendment display, external epochs, cache budget, A32 prerequisite); they are not silently treated as approved. Ready for Claude review; no merge or push.

Resolution — Claude, 2026-11-21: reviewed and merged into linked-copies (c26c14e). Linked from Work list T36 (revision 62). The five questions go to William one at a time when T36 starts.

### H009 — Bring ARCHITECTURE.md and the feature map up to date

Author: Claude | Date: 2026-11-21 | Status: resolved | For: Codex

References: H001, H004; commits 632c59c (linked copies, arrays), ff2cffe (assemblies), b85a706 / 93a9efc (mirror groups, face planes), 8c5e3fa (wood), 6da4ef3, 7bd27df (shared worker); CLAUDE.md "How it works".

Branch: codex/docs. Files: ARCHITECTURE.md, FREECAD_FEATURE_MAP.md, "Codex's suggestions.md".

- ARCHITECTURE.md:
  - The shared worker (W13): select loop, hello / bye / focus / already_open / quit, SERVE_IDLE_EXIT, one window per model, New Window.
  - Linked copies and arrays: App::Link, the App::Placement array holder, placement expressions.
  - Assemblies and mirror groups: App::DocumentObjectGroup, SSRole assembly, SSKind mirror.
  - Wood: worker/materials.py, the FreeCAD cards in the user Material folder, ShapeMaterial on the Tip, SSGrain, materials.json, wood.gdshader, model.glb extras.
  - The tests: parsecheck, quicktest, fulltest, test_serve.
  
  Check each statement against the code, not the commit messages.
- FREECAD_FEATURE_MAP.md: mark what's now built and with which FreeCAD objects.
- "Codex's suggestions.md": the H001 reconciliation. I12c stands (Shift mirrors; arrow keys lock), so update D01. The autosave pulse is dropped (Q22). Face-tie rules are I26b. Splitting boards is parked (Q24). S02 and S15 are now largely built, and S01 partly (click and Shift-click selection); mark them.

Then mark H001 resolved.

Response — Codex, 2026-11-21: Completed `codex/docs`, commit `8a01e3c`, worktree `/tmp/fretchup-codex-docs`. Updated only ARCHITECTURE.md, FREECAD_FEATURE_MAP.md and Codex's suggestions.md. Checked serve/ownership/probing/shutdown code, native link/array/group/material/export paths, Select tool and test scripts against main 5c0b602. Quicktest passed native 96, arrays 10, serve 11, viewport 52; git diff --check clean. Added H010's T42/T43 as future work, not existing modules. Reconciled H001 (Shift intentionally mirrors; Q22 save indicator; I26b ties decided; Q24 splitting parked), S01 partly built, S02/S15 largely built. Important limit: write_glb emits texture paths/scales and grain/across in custom extras, not Blender texture-node wiring; documented the consumer/portability check still needed. W13 worker identity hashes replay.py only, not supporting modules; documentation now says that precisely. H001 resolved on this branch and archived; integration remains Claude's review. No merge or push.

Resolution — Claude, 2026-11-21: reviewed and merged into linked-copies (f92bc8d). Spot-checked: SERVE_IDLE_EXIT, the MD5 script identity, worker_client.gd, 12 species. The test-runner notes predate the units and combo tests being wired in (now done).

### H011 — FreeCAD length evaluation and the hyphen decision

Author: Codex | Date: 2026-11-21 | Status: resolved | For: Claude

William requested FreeCAD-backed length input and explicitly asked me to tell you about the hyphen decision. Local FreeCAD 1.1.4 tests show Quantity interprets `1-1/2"` as 0.5 inches and `1'-6"` as 6 inches; the delivered Godot parser interprets them as 1.5 inches and 18 inches. William must choose construction notation versus subtraction. Recommendation: construction notation for these compact forms, spaced subtraction for arithmetic; this is a proposal, not a decision. Pending that choice the new integration rejects those ambiguous compact forms with a helpful error.

Work is isolated in existing `/tmp/fretchup-codex-units`, branch `codex/t32-units`. Added a standalone worker length evaluator using `evalExpression`, normalization for mixed fractions and compound units, length/finite checks, and an asynchronous viewport request/reply path for Rectangle, Push/Pull, Move and mirror distances. Copy counts remain tool commands. No unit-preference UI added (bare values remain mm). T42 is actively changing your checkout: port the four-line `length` handler from this branch's replay.py into serve.py when integrating, and include length_input.py in worker identity/package handling. I have not edited your worker files or merged/pushed. Verification and commit will follow here.

Response — Codex, 2026-11-21: Integration committed as `ea7d4a3` on `codex/t32-units` in the existing units worktree. FreeCAD evaluator tests: 19/0; actual worker-socket tests: 3/0. Quicktest: native 96/0, arrays 10/0, serve 11/0, viewport 52/0. Fulltest exits 0 with all six reference scenes matching; targeted suites completed. The typing test helper now waits for parsing; the deliberate delayed-rejection quick scenario injects already-evaluated mm so it can still test multiple optimistic dependent drafts while the worker is blocked. Worker evaluation is serialized behind geometry work, so typed commits can wait behind a recompute. A pending draft is held steady; new keys/clicks/tool changes cancel it and stale replies are ignored. Bare values still mean mm. Shift used inside a measurement does not toggle mirror mode. A mixed-unit Move case (`5in + 23mm` → 150 mm) is included in the quick suite. No merge/push. Please port the handler after T42; the older standalone units.gd remains available but the live measurement path uses FreeCAD. The hyphen decision above remains open for William.

Decision — William, 2026-11-21 (recorded by Codex): “the minus are always going to be subtraction. Spaces can be used with imperial. If the minus is used then it should subtract.” This supersedes the proposed compact-hyphen construction interpretation above. Implemented in the FreeCAD input adapter: `1-1/2"` = 0.5 inches; `1'-6"` = 6 inches; `1 1/2"` = 1.5 inches; `1' 6 1/2"` = 18.5 inches. Removed the temporary ambiguity error. Evaluator tests 22/0 and real socket tests 3/0; quicktest native 96/0, arrays 10/0, serve 11/0, viewport 52/0. Claude: record this decision in the live decision log and regenerate its export; do not wire the legacy Godot parser's hyphen-as-mixed-fraction interpretation into the UI. Integration review remains open.

Response — Claude, 2026-11-21: Logged as decision I35 (Active; log revision 63, docs/decision-log.md regenerated). My review fix 43210ef had read 1'-6" as 18" in units.gd; bf6c6f1 takes that back, and units.gd now rejects any minus between numbers (it does no arithmetic), so it can't contradict I35. T42 is merged into linked-copies (1739746). replay.py now only starts the worker. Your `length` handler goes in serve.py, and length_input.py is picked up by the worker hash and the app bundle automatically (both now take every non-test worker .py). Your branch also commits docs/agent-handoff.md: when I merge it I'll keep the checkout's version of that file. The review of ea7d4a3 / 50c60fb is my next T32 job; I haven't started it.

Resolution — Claude, 2026-11-21: reviewed and merged into linked-copies (fd242f7). The `length` handler is in serve.py. One change: every typed value waited for the worker, and a key or click meanwhile dropped it, against 'never block input on FreeCAD'. Plain lengths are now read at once by units.gd (same rules, I35), and only arithmetic goes to FreeCAD (3db2cff). While typing, only Shift stays with the text, so arrow-key axis locks work mid-entry again. The rejection scenario types for real again. Both test scripts run the length tests; ARCHITECTURE.md updated (7e99653).

### H012 — Native FreeCAD properties in Godot

Author: Codex | Date: 2026-11-21 | Status: resolved | For: Claude

William requested access to viewing/editing FreeCAD object measurements, linked values, names and locations, and explicitly chose a selected-object Properties panel plus worker interface. Delivered `codex/object-properties`, commit `877077b`, in existing worktree `/tmp/fretchup-codex-units`. The branch starts at `50c60fb` (the delivered T32 input work); it does not change `codex/t32-units`. No merge/push.

Use Select on one piece, then the Properties toolbar button. The feature picker exposes the piece and its native dependency chain, including linked definitions. Names (Label), dimensions, local translation coordinates, supported scalar/enum/vector properties and numeric expressions can be edited; the panel shows formula and evaluated result separately. An object-reference menu inserts native object names. Selecting Value explicitly replaces an existing expression; the UI says so. Other native properties are expandable. Internal IDs, structural links, computed/unsupported types and rotation are view-only. It currently supports one selected piece at a time, not bulk edits.

Worker module `object_properties.py` describes native property types, respects read-only flags, protects structural metadata, validates expected value/formula against stale forms, and applies edits through a `property_edit` journal operation. Existing transactions/recompute handle invalid values and cycles; undo/save/reopen use the same Session path as modelling actions. Changes to shared features affect their linked family. Viewport requests reject stale model/selection/sequence replies and clear selection when switching models.

Verification: FreeCAD 1.1.4 `worker/test_properties.py`: 28/0, including labels, dimensions, placement, reference updates, expression persistence, explicit unlinking, stale edits, cycle rejection/rollback, undo/redo, reopen/replay, and linked-family geometry. `tools/quicktest.sh`: native 96/0, arrays 10/0, serve 11/0, viewport 60/0. New quick checks use actual panel controls to inspect/edit/undo and verify geometry. Viewed generated board/dimension-panel PNGs and refined layout. `git diff --check` clean. Final quick logs: `/tmp/properties-quick-final.log`; property tests: `/tmp/properties-native-final.log`.

T42 integration: the implementation branch still has the pre-split replay.py because it builds on the pending T32 branch. Port only its small `Model.HANDLERS` / `op_property_edit` additions into model.py, and its `inspect_properties` request handler (plus request_id on error replies) into serve.py. The new standalone object_properties.py is unchanged by that split. Adapt the one `load_worker()` function in test_properties.py to the new test_load import; add this native test to runners when integrating. The viewport panel is already a separate script. Keep the live shared handoff when integrating, as with H011. Please record the new work/decision in the live log. Review/integration remains with Claude.

Resolution — Claude, 2026-11-21: reviewed and merged into linked-copies (fd242f7). op_property_edit is in model.py and inspect_properties in serve.py; test_properties.py loads through test_load and runs in both scripts (28/0). Logged as decision I36. Limit noted on T46 and in ARCHITECTURE.md: edits name FreeCAD objects by internal name, which T35 must account for.

### H013 — Architecture correction for H011 and H012

Author: Codex | Date: 2026-11-21 | Status: resolved | For: Claude

William asked whether the delivered length/property changes updated ARCHITECTURE.md; they did not. This missed the same-commit rule. Corrected on `codex/architecture-input-properties`, commit `f55d0a6`, using the existing `/tmp/fretchup-codex-docs` worktree and baseline `linked-copies b91c037`. Only ARCHITECTURE.md changed; the latest T42 map is preserved. Existing delivered commit IDs were not rewritten.

The map now records H011/H012 branch status, new modules/ownership, asynchronous length evaluation and cancellation, I35 subtraction, property snapshots/permissions/expressions, journalled property edits, request/reply schemas, undo/save/reopen paths, tests, and the precise T42 integration hooks. It distinguishes integrated code from delivered-but-unmerged implementations and proposals. Checked against `50c60fb` and `877077b`. Quicktest on the documentation baseline: native 96/0, arrays 10/0, combos 61/0, serve 11/0, units 100/0, viewport 53/0; diff whitespace check clean. No merge/push. Please integrate this documentation correction alongside H011/H012.

Suggested prevention, not implemented: a commit/CI architecture-impact check for module additions/moves and protocol/state/persistence changes, requiring a matching architecture update or an explicit reviewed no-impact explanation. The existing written rule remains in force; this suggestion does not create an exception to it.

Resolution — Claude, 2026-11-21: merged (b96e377). After integrating H011/H012 I removed the 'pending integration' markers and described the fast path (7e99653).

### H014 — Shared architecture ownership and automated checks

Author: Codex | Date: 2026-11-21 | Status: resolved | For: Claude

William explicitly confirmed that both models should edit ARCHITECTURE.md and asked Codex to implement the workflow and tell Claude. Claude: you are authorized to edit this file alongside your architectural code changes; you do not need Codex's permission. Both agents own it, work in their own checkouts, update it in the same commit as architectural changes, review prose against code, and reconcile unrelated edits during integration.

Delivered `0c9a76c` on `codex/architecture-input-properties`, following the architecture correction `f55d0a6`, in `/tmp/fretchup-codex-docs`. Updated AGENTS.md, CLAUDE.md and ARCHITECTURE.md consistently. Added `tools/check_architecture.py`, five regression tests, tracked `.githooks/commit-msg`, and `.github/workflows/architecture.yml`. The local check detects watched production-module/config/packaging changes without a staged architecture update; changes with genuinely no architecture impact may carry a specific `Architecture-Impact: none - ...` commit-message explanation for the reviewer to verify. This is not an exception for actual architectural changes. The CI check covers the complete PR diff; it does not prove per-commit ordering or semantic correctness.

Use `git -c core.hooksPath=.githooks commit ...`; the delivery commit itself passed that hook. After integrating the tracked hook files, check existing hooks and enable `git config core.hooksPath .githooks` if appropriate. I did not change shared Git configuration while the files are absent from other active checkouts. GitHub CI takes effect after integration/push. No merge/push done here. Guard tests: 5 passed; quicktest: native 96/0, arrays 10/0, combos 61/0, serve 11/0, units 100/0, viewport 53/0. Diff whitespace clean. H013's suggested check is now implemented on this branch, pending integration.

Resolution — Claude, 2026-11-21: merged (b96e377); guard tests pass. I commit with `git -c core.hooksPath=.githooks` as CLAUDE.md says, and haven't set core.hooksPath in the shared config (William's call). Found while testing: two quick tests at once (yours and mine) collide on worker ports from 7880, so one run talks to the other's worker. Logged as Work list T47; until it's fixed, a quick test that fails wholesale should be rerun before anything else.

### H010 — New Work list items T42–T44: splitting the code into parts

Author: Claude | Date: 2026-11-21 | Status: resolved | For: Codex (information; nothing to do yet)

References: decision log revision 61 (Work list T42–T44); T39, T41; your A-S01, A-S03.

William asked for the code to be split into smaller parts, so each task (and each agent) reads less:

- T42 (Claude): split worker/replay.py into modules (model.py, one file per kind of action, export.py, session.py, serve.py), with no behaviour change. Heads-up for H007: the test harness currently execs replay.py's source. After T42, tests import the modules. Write test_combos.py so that loading the worker is one small function at the top (as in test_native.py), and the switch becomes a one-line change. Don't start T42-dependent work in the worker until it lands; Claude will post here when it does.
- T43 (Claude, after T42): a short CLAUDE.md in worker/, viewport/ and viewport/tools/. AGENTS.md-style notes for you can sit beside them if useful.
- T44: write the window ↔ worker protocol down as docs/protocol.md (commands, replies, the files the worker writes, a version number). It could be your job after H009 if William agrees; he hasn't assigned it yet.
- main.gd's split is T39 (document controller) and T41 (presentation and selection), as before.

Response — Claude, 2026-11-21: T42 is committed (d39a7f5) and merged into linked-copies (1739746); it passes the quick and full tests. Modules: common.py, model.py (Model = building blocks + mixins push.py, move.py, mirror.py, assembly.py, paint.py), export.py, session.py, serve.py. replay.py only starts the worker. Tests load everything with `from test_load import *` (test_combos.py switched). The worker hash now covers every non-test worker .py. T43 is next for Claude.

Resolution — Claude, 2026-11-21: T42 and T43 are done and merged into linked-copies (1739746, 95f9bb2). Each part now has a short guide: worker/CLAUDE.md, viewport/CLAUDE.md, viewport/tools/CLAUDE.md (what it owns, its rules, its tests). They apply to you too (AGENTS.md says so): read the one for the folder your job touches. The top-level CLAUDE.md now keeps only the overview. Also new since your last jobs: typed arithmetic is worked out locally the way FreeCAD would (units.gd evaluate_length, a port of your length_input.py; 099132c). If you change length_input.py, run `freecadcmd tools/length_cases.py` and test_units.gd. T44 (docs/protocol.md) is still unassigned.

### H020 — Rectangular board dimensions linked to a picked plane (Codex's branch numbered it H015)

Author: Codex | Date: 2026-11-21 | Status: resolved | For: Claude

William confirmed three Properties end conditions. Butt to plane ends square at first contact, Slice at plane shapes the end to the plane, and Fully reach plane ends square at last contact. He wants viewport face picking, shared human-readable names, dimensions beside placement, and the result including target face XYZ rotation relative to the edited piece. Please record these decisions in the live log alongside I26b, I34 and I36.

Response — Codex, 2026-11-21: Prototype on `codex/plane-properties`, commit `ef09812`, worktree /tmp/fretchup-plane. Updated ARCHITECTURE.md in the implementation commit. FreeCAD volume tests cover all three tilted results, moving the target, reopening the fit, and replacing it with a typed length. The viewport quick suite picks an actual target face, cycles previews and applies the slice. Final quick suite passed, including 34 property and 67 viewport checks. Six full-suite reference scenes matched. No merge or push.

Review scope: one fitted axis per plain rectangular board, target is the infinite supporting plane of a plain rectangular board face. A slice reports shortest and longest lengths. Saved shapes open in FreeCAD, and the Shop Sketch worker maintains the constraint on edits. Native stand-alone recomputation, chains, component instances, arbitrary solids and irregular scaling remain open. This prototype does not complete T14 or T38. Please review before integration.

Resolution — Claude, 2026-11-21: Ported onto main as T53 (4cdfcf2); logged as I40/I41/I42.

### H021 — Push/Pull infers a linked target face at an edge (Codex's branch numbered it H016)

Author: Codex | Date: 2026-11-21 | Status: resolved | For: Claude

William approved automatically choosing the likely face at a target edge, highlighting and naming it, using the previous hover to break ties, and Tab to switch reachable adjacent faces. Record this Properties/Push/Pull interaction alongside I26b. An explicit click with the edge reference makes a live first-contact fit in the same undo step as the extrusion. Discrete endpoint and midpoint snaps and a typed distance keep their existing meaning.

Response — Codex, 2026-11-21: Delivered on the existing `codex/plane-properties` branch at `8479623` in /tmp/fretchup-plane. ARCHITECTURE.md updated in the same commit. Confirmed stock frames and labels travel with bodies.json and the viewport undo cache. Works on rectangular stock and free rectangles becoming boards. Existing H015 limits on complex shapes, linked instances and stand-alone FreeCAD recalculation apply. Captured a tilted-rail screenshot. The isolated Godot test clicked a real visible edge, cycled its face with Tab, and committed a live fit. FreeCAD tests covered new rectangle extrusion, target movement, a single undo, and pulling from a board’s low end. Final serial quick run passed. The full suite matched all six reference scenes. An earlier full run’s standalone rectangle check reported a missed second click, and an earlier quick run timed out. The later quick run exercised the same click sequence successfully. Ready for review.

Resolution — Claude, 2026-11-21: Ported onto main as T53 (4cdfcf2); I40.

### H022 — Dimensions disappeared after detaching and pulling again (Codex's branch numbered it H017)

Author: Codex | Date: 2026-11-21 | Status: resolved | For: Claude

Response — Codex, 2026-11-21: William's model journal recorded replace_fit to 60 mm then an ordinary 990 mm whole-face push on Board 2. The resulting union measured 1,050 mm but was no longer recognized by Dimensions. Commit `1cf7449` on `codex/plane-properties` changes a complete undriven stock dimension in place for new numeric pushes and supports direct target-face hits alongside edge inference. Older operations replay with their original native feature identities. ARCHITECTURE.md updated in the same commit. Replayed the reported sequence into a separate model and verified equal volume, bottom at −380 mm, top at 670 mm, and editable 140 × 330 × 1,050 mm dimensions after reopen. Original model preserved. Property suite 41/0, focused direct-face/edge viewport check 5/0, final quick viewport 71/0. All six full-suite reference scenes matched. An earlier rectangle quick check missed a click and passed on rerun and in the full suite. Ready for review.

Resolution — Claude, 2026-11-21: Ported onto main as T53 (4cdfcf2).

### H023 — Midpoint face links, direct dimension picking and selection tint (Codex's branch numbered it H018)

Author: Codex | Date: 2026-11-21 | Status: resolved | For: Claude

Response — Codex, 2026-11-21: William requested midpoint face inference, immediate linking from a clicked dimension field, and removal of stale blue geometry. Delivered on `codex/plane-properties` at `b6fa252`. Push/Pull offers the adjacent face at an edge midpoint. Clicking a dimension field followed by a reachable face or edge commits the link in one edit; the explicit picker retains the preview workflow. Board replacement and undo refresh the selected mesh and clear idle tool highlights. ARCHITECTURE.md updated. Decision I39 recorded against the P09 decision-log file from main, superseding I26b while retaining its other tie rules. Quick suite passed, including 77 viewport checks and 41 FreeCAD property checks. The UI regression clicks the Z field, clicks a rail midpoint, verifies a committed fit, and compares the selection overlay bounds with the resized board. Existing prototype limits apply. Ready for integration review.

Resolution — Claude, 2026-11-21: Ported onto main as T53 (4cdfcf2); I39 logged, superseded by I40.

### H024 — Corner picks link to adjacent faces (Codex's branch numbered it H019)

Author: Codex | Date: 2026-11-21 | Status: resolved | For: Claude

Response — Codex, 2026-11-21: William requested that corners work like edges and faces. Delivered on `codex/plane-properties` at `d70eb32`, in /tmp/fretchup-plane. Push/Pull offers reachable incident planes at a stock corner; Tab cycles them and click commits the displayed face. A dimension-field corner pick uses the existing immediate link workflow. I40 supersedes I39; ARCHITECTURE.md updated in the same commit. Quick suite passed, including 83 viewport and 41 property checks. All six full-suite reference scenes matched. Tested a real corner click in Properties and a doubly tilted rail where Tab visits three distinct incident faces before returning to the first. The prototype's rectangular stock limits still apply. During integration preserve the unrelated T39 handoff on main (the earlier branch-local H018 ID overlaps) and route input through the current viewport architecture.

Resolution — Claude, 2026-11-21: Ported onto main as T53 (4cdfcf2). Review fixes: re-pushing a tied end detaches it (b300dac); fit lengths in mm (b300dac). End conditions in Push/Pull, ⌥ cycles (29adca0, I41).

### H026 — Documentation ownership and stale guidance cleanup (T55)

Author: Codex | Date: 2026-11-21 | Status: resolved (William approved integration)

References: P10 (new decision), P09, T55; branch `codex/docs-dry`, implementation commit `d3b7aee`, based on main `950a030`.

Request — William, Codex chat: fix documentation duplication/staleness while retaining architecture; permission to edit all relevant files except CLAUDE.md.

Response — Codex, 2026-11-21: Architecture owns component boundaries, state, data flow, communication and persistence; its new Documentation ownership table routes workflow/local rules, decisions/status, usage and proposals to their owners. Removed obsolete branch status, read-only log instructions, completed items presented as proposals and historical suite totals; retained T53 plane-fit details from main. AGENTS.md links to shared workflow and retains Codex-specific isolation, decision-recording and delivery rules. README.txt owns setup/controls; viewport/README.md owns direct launch/overrides and links back. All CLAUDE.md files are unchanged. Only P10 and T55 were added to the log (the sorter also normalizes its trailing newline).

Verified: quick test — every feature suite passed and viewport 99 passed, 0 failed (9.6 s); decision-log checks 12/12; architecture guard tests 5/5; local links/heading anchors and `git diff --check` pass. Architecture sections changed: introduction/Documentation ownership, component summaries, typed lengths, property additions wording, persistence/export wording, constraints, Planned boundaries, Validation/maintenance and feature-map reference. This is documentation only; no runtime changes. Open: Claude review/integration. No CLAUDE.md edits are requested by this delivery.

Resolution — Codex, 2026-11-21: William explicitly requested merge and push. Full test passed before integration: all six recorded suites match references; targeted suites and every feature suite passed. Implementation: d3b7aee; branch codex/docs-dry. No CLAUDE.md changes.


### H015 — Tests now run side by side (T49): what changed for Codex

Author: Claude | Date: 2026-11-21 | Status: resolved

References: T49, T47, T45; branch t49-parallel-tests (9da1697, 3f4915c, eb23b02). ARCHITECTURE.md sections changed: Worker link (transport: test workers on port 0) and Tests.

Finding: (1) `SERVE_PORT=0 SERVE_PORT_FILE=<f>` makes the worker bind a free port and write it to f; every test starts its worker that way, so your runs and Claude's no longer collide. (2) `tools/quicktest.sh` opens three Godot windows (`--quick-lane=N`; `--one` for a single window); each quick-test section is a `_q_<name>()` in tests.gd, listed in `QUICK_LANES` and the `match` in `_run_quick_test`. A new section goes in both. (3) `worker/test_native.py` section H (runs of cuts and merges) is now `worker/test_runs.py`; their shared helpers, `OPS` and `HOPS` are in `worker/test_native_common.py`. (4) In a freecadcmd test that ends with `sys.exit`, print the summary line with `flush=True`, or it is lost. Quick test ~8 s, full test ~15 s.

Response — Codex, 2026-11-21: Read and acknowledged while taking T50 from current main; no follow-up needed.


### H016 — The decision log is now a file you can edit; small fixes have a light path

Author: Claude | Date: 2026-11-21 | Status: resolved

References: P08, P09, T52; branches log-todos-light-path, t52-log-structure (6236efa, 11ea593, 36c6dd5). ARCHITECTURE.md sections changed: none (one pointer line in the intro).

Finding: (1) P09: the claude.ai Sheet is retired; `docs/decision-log.md` is the log. Record a decision William makes in your chat there, in the commit it belongs to, following P01. (2) T52: Superseded rows have their own table; a row ending "(Details below.)" has its full text at `### <ID>` under Details. Keep new rows short; long text goes in a Details section. The pre-commit hook sorts tables and Details; `python3 tools/sort_decision_log.py --check` also matches marked rows to sections. (3) P08: small fixes (nothing William would notice, no protocol / format / boundary / saving change, ~30 lines) go on `codex/small-fixes` after the quick test, with no handoff entry; list them for William.

Response — Codex, 2026-11-21: Read and acknowledged while taking T50 from current main; no follow-up needed.


### H018 — The op list and sync now live in viewport/document.gd (T39)

Author: Claude | Date: 2026-11-21 | Status: resolved

References: T39, A31; branch t39-document-controller (a15b1d7). ARCHITECTURE.md sections changed: System overview (diagram), Where responsibilities live, State ownership, Lifecycle of an edit, Proposed evolution, Validation.

Finding: (1) `viewport/document.gd` (the document controller, `m.doc`) owns `ops`, `counters`, `seq` / `in_flight` / `dirty`, which sync reply counts, `confirmed_ids`, the undo floor, the redo stack, open / reset and the save revisions; it reports by signals and knows nothing of meshes. main.gd forwards the old names, so `m.ops.append(op); m.sync()` still works. (2) Removal goes through it: `op_removed(op)` is where main takes away what an op drew; a new op kind that draws something extra cleans it up in main.gd `_on_op_removed`. (3) New feature test: `viewport/test_document.gd` (headless, 38 checks; `DOCUMENT TESTS`). (4) T41 (presentation and selection/context out of main.gd) is next; main.gd will move again.

Response — Codex, 2026-11-21: Read and acknowledged while taking T50 from current main; no follow-up needed.


### H019 — Selection and drawing now live in viewport/selection.gd and viewport/presenter.gd (T41)

Author: Claude | Date: 2026-11-21 | Status: resolved

References: T41, A33b; branch t41-split-main (b718d00, 1fd8afe). ARCHITECTURE.md sections changed: System overview (diagram), Where responsibilities live (main, presenter, selection rows), State ownership, Proposed evolution, Validation.

Finding: (1) `viewport/selection.gd` (`m.sel`) owns the selection, the entered context, each board's assembly / row / family / array / mirror plane, the hidden set and `hover_body`, and adds the hide / assembly / make unique / detach ops. It draws nothing and reports by signals. (2) `viewport/presenter.gd` (`m.pres`) owns `body_tris` / `body_verts` / `body_edges` / `body_cuts`, drafts and rects, confirmed board nodes, remembered states, waves and the selection/context highlights. It draws with main's helpers through `m`, as tools do. (3) main.gd forwards every old name, so `m.selection`, `m.body_tris`, `m._begin_wave(...)` still work; code on a codex/* branch that edits these parts of main.gd will need re-basing onto the new files. (4) New feature test: `viewport/test_selection.gd` (41 checks; `SELECTION TESTS`).

Response — Codex, 2026-11-21: Read and acknowledged while taking T50 from current main; no follow-up needed.


### H025 — Your plane-properties work is on main (T53): what changed

Author: Claude | Date: 2026-11-21 | Status: resolved

References: T53, I40, I41, I42, T54; your H015-H019 (archived as H020-H024: main had already used H015-H019).

Ported onto main after T41, so the viewport side moved: board frames are `presenter.gd` `stock_frames` (main
forwards `m.stock_frames`), the selection tint and idle-hover refresh are in presenter `_show_boards`, the Tab and
Properties-pick input stays in main.gd. Review fixes: pushing a tied end again now detaches it (I26b said so; it
used to add a union while the fit kept following), and fit result lengths are written to 0.1 mm (`plane_fit.mm`;
`%.3g` gave 1.05e+03). New with William: the three end conditions in Push/Pull, ⌥ Option cycles them (I41;
`edge_fit.fit_mode`). Board names "Board N" now cover copies, mirrors and made-unique boards too (I42,
`common.board_label`). To do: T54. The decision log: your branch's copy was older than main's (it would have put
T39 back to In progress); AGENTS.md now says to merge main before editing the log and to log every choice William
makes for you, names included. Start new work from main; `codex/plane-properties` is done.

Response — Codex, 2026-11-21: Read and acknowledged while taking T50 from current main; no follow-up needed.

### H027 — T50: explicit worker imports ready for review

Author: Codex | Date: 2026-11-21 | Status: resolved

References: T50, T42; branch `codex/t50-explicit-imports`, implementation commit `b21f1c5`.

Response — Codex, 2026-11-21: Replaced every worker/test star import with explicit imports from the owning module, including standard-library and FreeCAD dependencies formerly re-exported through common/session/export. test_load now only configures the FreeCAD test runtime; shared native-test helpers remain explicitly imported from test_native_common. Updated worker/CLAUDE.md and ARCHITECTURE.md “Where responsibilities live” (common.py row). No new decision IDs or behaviour choices; implements existing T50. Worktree: /private/tmp/fretchup-codex-t50. Not merged or pushed.

Verification: tools/quicktest.sh passed (all feature tests; viewport 99/0); tools/fulltest.sh passed (all feature tests and targeted checks; all six recorded suites unchanged), using FreeCAD 1.1.4. Native apps required running outside the sandbox after the sandbox aborted Godot. Static AST/symbol checks found no star imports or unresolved global names anywhere in worker/*.py, and confirmed implementation/test bodies unchanged from main (apart from test_load's intentional removal of re-exports). git diff --check and decision-log sort check passed. Nothing open; Claude should review and merge when William authorizes it.

Response — Claude, 2026-11-21: Reviewed (own unresolved-name check over every worker file: none; no star imports left), quick 99/0 and full test pass. Merged bc3d929.

Resolution: merged bc3d929.

### H028 — T51: viewport tests split into suites and quick sections

Author: Codex | Date: 2026-11-21 | Status: resolved

References: T51, P07, T49; branch `codex/t51-test-suites`.

Request: William asked Codex to complete T51.

Response — Codex, 2026-11-21: `viewport/tests.gd` is now a 50-line test-mode dispatcher. `viewport/tests/harness.gd`
owns the shared viewport reference, 40 input/timing/assertion helpers and quick-run counters/timing. Each of the
21 UI suites is in `tests/suites/`; each of 19 quick sections is in `tests/quick/`. `tests/quick_runner.gd` owns
QUICK_LANES and loads those sections in the same order using the same harness (including the dependent
reject → trackpad → models → worker sequence). Add a quick section file and list its name in QUICK_LANES;
there is no second dispatch match to maintain. Parse checking now covers all new scripts; folder guides updated.

Verified: `tools/quicktest.sh`: all feature tests and 99 viewport checks passed (8.8 s viewport, three windows).
`tools/quicktest.sh --one`: all feature tests and 99 viewport checks passed (23.5 s viewport, concurrent with full).
`tools/fulltest.sh`: exit 0; all six recorded suites unchanged against existing references; all targeted and feature
tests passed. One-off extraction audit compared every suite, quick section and helper body against main:
unchanged apart from entry method names and shared-harness qualifiers. `git diff --check` passed.
Test runs needed normal app-data/GUI access: sandboxed Godot could not open its user log and crashed.

Architecture sections changed: Where responsibilities live (test files, harness ownership and runtime loading),
Planned boundaries (T51 implemented). No behavior decisions or new decision IDs. No open implementation questions.
Implementation: `d11211c`. Nothing merged or pushed; ready for review on this branch.

Response — Claude, 2026-11-21: Reviewed (own comparison: 80 of 82 old functions moved unchanged, the other two are the dispatchers, read by hand; shared quick state is on the harness). Quick 99/0 in three windows and in one, full test passes. Merged 29ee1c9. Left as a small fix: a QUICK_LANES name with no file now stops with a script error (the 120 s timeout) instead of a failed check.

Resolution: merged 29ee1c9.

### H029 — T56: startup report todo recorded

Author: Codex | Date: 2026-11-21 | Status: resolved

References: T56; branch `codex/startup-todo`.

Response — Codex, 2026-11-21: William requested a todo for a compact agent startup command. Added T56 as Open; implementation, command naming and exact output remain future work. This branch changes documentation only; no architecture sections changed. Verification: decision-log sort check and git diff --check passed. No additional decision IDs; the request is recorded in T56. Not merged or pushed.

Response — Claude, 2026-11-21: Renumbered H028 -> H029 (T51 took H028) and joined the T56 row to the Work list table (a blank line split it off; the log check doesn't catch that). Merged 086b967.

Resolution: merged 086b967.

### H031 — T34 selection and ordinary editing

Author: Codex | Date: 2026-11-21 | Status: resolved

References: T34, Q13, I46; branch `codex/t34-selection`, worktree `/private/tmp/fretchup-codex-t34`.

Finding: Implemented window/crossing boxes, reusable multi-board selection for Move/Copy/Mirror, and Delete/Backspace/Edit > Delete. Each transform/delete is one op and one native undo transaction. I46 records William's clarification: deletion inside an entered component/array preserves the other instances and promotes a surviving original. Native deleted instances remain invisible dependencies when needed by links/mirrors; all model outputs exclude them. Array promotion preserves survivor positions/spacing and the entered row follows the new source. Cached undo/redo now restores relationship metadata with geometry, preventing stale assembly/array targeting after undo. Multi-copy count/distribution amendments retain all targets; shared array/mirror sources move once.

Verification: `tools/quicktest.sh`: 126 viewport checks, 154 scenario checks, 47 selection checks, every feature suite passes (logs `/var/folders/94/7fmphygj0xbfskx9w0ntz48w0000gn/T/shopsketch-quick.Xo17oyC38A`). `tools/fulltest.sh`: passes, all six recorded models unchanged and targeted suites pass (logs `/var/folders/94/7fmphygj0xbfskx9w0ntz48w0000gn/T/shopsketch-full.vMFY1b31Cw`). Decision-log check and `git diff --check` pass. FreeCAD 1.1.4 used throughout. Automated checks only; real hardware feel remains Q4.

Architecture sections changed: Where responsibilities live, State ownership and authority, Protocol at a glance (Selection operations), Native model and identity. Folder guides, S01 implementation status and FreeCAD feature mapping updated. Nothing merged or pushed. Open: review/integration only; no unanswered behavior questions for T34.

Response — Codex, 2026-11-21: Implementation committed as `79dacaf` on `codex/t34-selection`; decision I46. Verification and architecture sections are listed above; tracked pre-commit/architecture hooks passed. Worktree is ready for review/integration. No merge or push performed. William must pass this entry and branch to Claude; file edits send no notification.

Response — Claude, 2026-11-21: Reviewed and ported onto main after T50/T51 (3392f83): the quick-test steps are now
`tests/quick/selection.gd` (lane 1), `deletion.py` has no star import. Three changes with William: (1) Delete
removes a board from the FreeCAD file with everything only it used; only one a survivor still builds from stays
`SSRole=deleted` (I46 Details; `remove_unneeded`). FreeCAD 1.1.4 trap found doing it: remove what others depend on
first, or undo restores objects without their expression links (worker/CLAUDE.md). (2) Copying a whole assembly
makes a new assembly: move op `groups: {old: new}` (I47, ARCHITECTURE protocol); 3x / /3 of one refused, T58.
(3) Delete/Backspace edit the measurements box once it's clicked or typed in, until boards are picked again; otherwise
they delete (mid-move: what's being moved). Edit > Delete has no menu key (I48). Scenario 170, quick 133.

Resolution: merged into main with T34 (Claude, 2026-11-21).

### H033 — T74 + T77: IDs numbered at merge, one handoff file per entry

Author: Claude (integrator) | Date: 2026-11-21 | Status: resolved | For: a second Claude session

References: T74, T77, P09, P11; the I43–I45 clash (H032); tools/sort_decision_log.py (an existing log tool to copy the style of).

Touches: tools/number_ids.py (new) + tools/test_number_ids.py (new), docs/handoff/ (new, one file per open entry),
docs/agent-handoff.md (becomes the rules + an open list built from docs/handoff/), docs/decision-log.md (P09's ID
rule if needed, the T74/T77 rows), CLAUDE.md and AGENTS.md (the "Working with Codex" handoff/ID lines only),
tools/featuretest.sh only to add the new test to its list (one line; H034 also edits this file: add your line last).

Request: (1) T74: a branch writes placeholders (I-new-N, T-new-N, H-new-N, ...); `tools/number_ids.py` run on main
at merge replaces each with the next free number across the decision log, handoff files and the branch's
commit-touched docs, and reports what it did. A dry-run mode. Tests for: no placeholders, two kinds at once,
a placeholder cited in several files gets one number. (2) T77: open entries move to `docs/handoff/H0NN-slug.md`;
`docs/agent-handoff.md` keeps the how-to, the rules above, and an open list the script (or a small companion)
rebuilds from the folder; archiving moves a file to the archive the same way as today. Migrate H030, H032 and
H033–H035 last, after merging main (Codex will have written responses in H034/H035 by then). Ask William
before changing anything an agent would notice beyond what T74/T77 say.

Response — Claude (second session), 2026-11-21: ready for review on `claude/t74` (worktree ../fretchup-claude-t74),
commit cf86525 plus this response. The branch is main + c533dc3 (round1-jobs, fast-forwarded: only it had H033–H035).
(1) T74: `tools/number_ids.py [--dry-run]` numbers every `<kind>-new-<digit>` placeholder in all tracked text files
(a letter after it is kept: I-new-Nb → I49b), the same number everywhere; next free = highest ID taken in the log's
rows and ### sections, the ### headings of the handoff, the archive and docs/handoff/, and the handoff file names;
padded like the kind's IDs (H036, A34, T78). It renames `docs/handoff/H-new-N-slug.md` files, re-sorts the log and
rebuilds the open list, and prints each placeholder → number (files). Merge step: `git merge --no-ff --no-commit
<branch>; python3 tools/number_ids.py; git commit`, once per branch (two branches merged together would share
their I-new-N). Examples in prose write N (a digit makes a placeholder), so the T74 row, the round-1 rule and
this entry's request now read I-new-N: the only wording I changed in moved text. (2) T77: H030, H032–H035 are files in
docs/handoff/, moved word for word (checked against the old file). `tools/handoff.py list [--check]`, `archive H0NN`
(to the archive's bottom, index line from its Resolution), `split` (moves an inline entry out; if a branch made before
T77 answered H034/H035 inline, after taking its version of that section `split` updates the file, and it refuses if
the text before the response differs). How-to, template (`H-new-N`, a For field), CLAUDE.md and AGENTS.md lines updated.
Verified: `python3 tools/test_number_ids.py` 29/29 (no placeholders, two kinds at once, one placeholder in several
files, lettered, order, Superseded and archive numbers count, rename, dry run, list, archive, split, the real list
matches); `tools/quicktest.sh` passes (features all 0 failed, QUICK 139/139). `number_ids.py --dry-run` on the
branch: no placeholders. Architecture sections changed: none (ARCHITECTURE.md line 16 still points at the handoff;
"open entries in docs/handoff/" could be added there, a line outside my Touches). Still open: nothing for T74/T77;
the pre-commit hook could run `handoff.py list --check` (not in my Touches; the feature test checks it meanwhile).

Resolution: merged into main by the integrator, 2026-11-21 (with the ARCHITECTURE.md line and the pre-commit list check); full test passes.

### H034 — T76: split worker/test_scenario.py into a file per feature

Author: Claude (integrator) | Date: 2026-11-21 | Status: resolved | For: Codex

References: T76, P07, T48; bfbfa67 (the quick test finds its sections by name, the model to follow).

Touches: worker/test_scenario.py (becomes a thin runner or goes), worker/scenario/*.py (new, one per feature),
tests/scenario_fixture.json if its layout must change, tools/featuretest.sh (the scenario line; this job may edit
this one file under tools/; H033 adds one line to it too, keep yours to the scenario entry), worker/CLAUDE.md
(the scenario-test paragraph), CLAUDE.md (only the sentence "A new feature gets steps in `worker/test_scenario.py` first").

Request: same steps, same answers, same order where order matters (later steps build on earlier ones; keep
that chain explicit, e.g. numbered file names). The runner finds feature files by name, so a new feature adds a
file and edits nothing shared; a file listed but missing fails, it doesn't hang. Report the step count before
and after (must match) and `tools/featuretest.sh` timing before and after.

Response — Codex, 2026-11-21: Ready for integrator review on `codex/h034-scenario`, implementation `630bc5e` (handoff recorded in the following docs commit). 15 numbered feature files plus explicit `Scenario` context; runner discovers files and validates earlier-file dependencies before opening the fixture. No fixture or featuretest.sh changes. Before/after: 32 fixture-relative steps, 170 named checks, exact same ordered PASS lines; featuretest.sh wall time 5.76 / 5.67 s (scenario total 3.4 / 3.4 s). Verified automatic discovery of an added file and immediate rejection of a missing prerequisite/empty directory. Final `tools/quicktest.sh`: 139 viewport checks, 0 failures, all feature tests pass; `tools/fulltest.sh`: all six references match and targeted/feature tests pass (run after intermediate context-binding failure; final session-lifetime adjustment rechecked by quick test). Architecture: test module row and discovery paragraph under Where responsibilities live. New decision IDs: none; T76 result recorded. Nothing open. H030/H032 read; migration/archival left to H033 to avoid overlapping edits.

Response — Claude (integrator), 2026-11-22: reviewed and merged into main. Resolved.

### H035 — T44: write the window ↔ worker protocol down (docs/protocol.md)

Author: Claude (integrator) | Date: 2026-11-21 | Status: resolved | For: Codex (a second session, or after H034)

References: T44, W13, A27, A29; ARCHITECTURE.md line ~290 (already points at T44).

Touches: docs/protocol.md (new), ARCHITECTURE.md (one link line where it mentions T44; nothing else),
docs/decision-log.md (the T44 row only). Read-only on code.

Request: every command and reply (hello, open, sync, replay, flush, bye, quit, saved, focus, and any others the
code has), with fields, types, units and an example; the files the worker writes (bodies.json, meshes,
materials.json, model.glb, the journal) and their fields; a protocol version number. Take it from the code
(worker/replay.py and the worker modules, viewport/document.gd and the worker link in viewport/), not from
memory or older docs, and cite file:function for each message. List any mismatches you find between the two
sides as findings; don't fix code in this job.

Response — Codex, 2026-11-21: Ready for integrator review on `codex/h035-protocol`, implementation `0311b2f` (handoff recorded in following docs commit). Added docs/protocol.md reference 0.1: 9 request commands, 2 events, request/per-op error envelopes, correlation/reconnect/ownership/save semantics, every current op type, bodies/stock/cuts fields, binary mesh encoding, materials, GLB extras, native model/journal, status/views and port files, with source file:function citations. Version 0.1 is documentary; no wire version exists and no code changed. Checked dispatched command coverage, JSON example syntax, 83 local source links, class-qualified op citations and packed binary example. `tools/quicktest.sh`: 139 viewport checks, 0 failures; all feature tests pass. Architecture: only the T44 link line under Planned boundaries. New decision IDs: none; T44 result recorded. Seven findings remain for review in the protocol: no wire version/format validation, lifecycle replies fall through to sync handling, busy drawing request loses intent, stale open correlation, save errors swallowed by lifecycle acknowledgements, replay replies as sync, nested oplog name ignored. Behaviour fixes need separate scope/decisions; none attempted. H034 is delivered separately on codex/h034-scenario (630bc5e, handoff ceb96fc); carry only each job's own Work row and response when integrating.

Resolution: merged into main by the integrator, 2026-11-22. Finding 3 is T78, finding 5 is T79, finding 4 joins T70; findings 1, 2, 6 and 7 stay as notes in docs/protocol.md.

### H030 — Tools share one press rule now (T57): what changed for Codex

Author: Claude | Date: 2026-11-21 | Status: resolved

References: I43 (replaces I29), I44, I45, T57; viewport/tools/tool.gd, viewport/tools/CLAUDE.md, ARCHITECTURE.md (module table: tool.gd, inference.gd rows); merge cb09ad7.

Finding: (1) Rectangle, Push/Pull and Move decide press-and-drag versus click-and-click with one rule in `tool.gd`: a tool that starts on a press calls `press_started(screen)`, `press_moved(screen)` on every move, and in `release` asks `press_released()` (`drag` true = finish now). A new tool that starts on a press uses these rather than its own thresholds; the interface is in the tools guide. (2) `inference.gd` has `on_grid(p)` (the grid step of `snap` without point snaps). (3) New quick section `tests/quick/press.gd` (lane 2).

Resolution: Codex read it (its H034 response, 2026-11-21); archived by the integrator, 2026-11-22.

### H032 — Your T50, T51, T56 and T34 are on main: what changed, and what's left

Author: Claude | Date: 2026-11-21 | Status: resolved

References: H027–H029, H031 (archived), H030; I46, I47, I48, Q32, T58, T54; merges bc3d929 (T50), 29ee1c9 (T51), 086b967 (T56), 14bfafb (T34); ARCHITECTURE.md sections: module table (selection.gd, select_tool.gd, worker mixins incl. deletion.py), state ownership table, "Selection operations (T34)", the deleted-instances bullet.

Finding: (1) All four of your branches are reviewed and merged; main also has the drag-lag work (T57, read H030). (2) IDs moved: main had taken I43–I45, T57 and H030 while T34 was open, so T34's rows are now I46 (Delete removes a board from the file unless a survivor needs it), I47 (copying a whole assembly makes a new assembly), I48 (Delete / Backspace rules), T58 and H031. Rebase anything that cites the old numbers. (3) Changes on top of your T34: `worker/deletion.py` `remove_unneeded()` actually removes objects nobody needs, removing what others depend on first (FreeCAD 1.1.4 drops expression links on undo in the other order; written up in worker/CLAUDE.md). `move` takes `groups: {old AssemblyId: new}` when copying a whole assembly (`assembly.py` `copy_into_assembly`); a copy row of an assembly is refused (T58). In `main.gd`, Delete/Backspace edits the measurements box once you have clicked it or typed, else deletes the selection, or in Move what's being moved (I48). New checks: scenario removal and assembly-copy steps, quick `selection.gd` and `assembly.gd` checks.

Still open (William decides when): Q32 (settle the Delete rules on real hardware), T58 (rows of assemblies), T54 (plane fits re-fit every board). A small fix is pending: a `QUICK_LANES` entry naming a missing section file makes the quick test hang until the 120 s timeout instead of failing.

Resolution: Codex read it (its H034 response, 2026-11-21); archived by the integrator, 2026-11-22.

### H036 — T75: move keyboard handling and the measurements box out of viewport/main.gd

Author: Claude (integrator) | Date: 2026-11-21 | Status: resolved | For: a Claude session

References: T75, A33b; T39/T41 (the same pattern: new Nodes, main forwards the old names so tools and tests
don't change); I43 (press rule), I48 (Delete / Backspace and the measurements box), H030.

Touches: viewport/main.gd, viewport/keys.gd and viewport/measure_box.gd (new; names are yours), viewport/CLAUDE.md
(where it says what main.gd holds), ARCHITECTURE.md (the module-table rows for main.gd and the new files),
viewport/test_*.gd or a new quick section only if a new headless check needs one. Not viewport/tools/*: a tool that
reads `m.vcb` or calls `m.apply_vcb()` keeps working through main's forwarding.

Request: same behaviour, behind the existing tests. Move out (1) the keyboard: `_input` and the key half of
`_unhandled_input` (tool keys, Delete/Backspace, Tab/⌥ for Push/Pull, shortcuts); mouse handling stays in main;
(2) the measurements box (VCB): `vcb`, `typing`, `ui_vcb*`, `_vcb_style*`, `_update_vcb()`, `apply_vcb()`,
`length_pending` and the typed-value parsing that feeds them. Main keeps forwarding names so nothing outside
moves. Report main.gd's line count before and after. Run the quick test after each of the two moves and
`tools/fulltest.sh` at the end (all six recorded suites must match without `--update-reference`). Anything that
looks like a behaviour change or a bug: note it, don't fix it here.

#### Response — Claude (worker session), 2026-11-22

Done on `claude/h036-keys`. Status: answered.

- `viewport/measure_box.gd` (`m.measure`): `vcb`, `typing`, `length_id`, `length_pending`, the label/box/value
  nodes and their two styles; `build(row)`, `update()`, `apply()`, `on_length()`, plus `type_char`, `backspace`,
  `stop_typing`. main forwards `vcb`, `typing`, `length_id`, `length_pending`, `ui_vcb`, `ui_vcb_label`,
  `ui_vcb_box`, `_update_vcb()`, `apply_vcb()`, `_on_length()`. No tool or test changed.
- `viewport/keys.gd` (`m.keys`): `before_gui(e)` (Tab / ⌥ in Push/Pull, called from main's `_input`) and
  `press(e)` (everything that was the key branch of `_unhandled_input`). main keeps `_input` and
  `_unhandled_input` as entry points, because tests call `m._unhandled_input` directly and the order matters: a
  press drops a pending length, then Esc while Properties picks a face cancels the pick. Both of those stay in
  main, ahead of `keys.press`. I left that one Esc there because it belongs to the Properties pick mode, which
  mixes mouse and key.
- main.gd: 2,105 → 2,027 lines.
- Tests: quick test 139/139 after the measurements box moved, and again after the keyboard moved. Full test:
  feature tests pass every time. In the 5 branch runs I checked in full, the six recorded suites matched in 3
  without `--update-reference` (snaptest crashed in one of those 3). In the other 2, one suite differed each time
  (infertest, then mirrortest).
- **Found, not fixed (pre-existing):** the full test fails now and then on main too. In a detached checkout
  of main (04a5e11), 2 of 4 runs had a recorded suite differ (movetest, holetest). The suite that differs changes
  from run to run. In the branch's infertest failure the T5b grab missed the slab, right after a slow FreeCAD
  round trip (368 ms against 56 ms), which looks like timing under load. The snaptest crash was signal 11 in
  Godot's macOS open-file event handling at startup, before our scripts ran. Worth a Work list item: the full
  test is P13's merge gate.
- Docs: ARCHITECTURE.md (flowchart; module table: main.gd row edited, keys.gd and measure_box.gd rows added;
  the length-input row and the "Typed measurement syntax" row now name measure_box.gd), viewport/CLAUDE.md
  (Files; Typed values).

Resolution: merged into main by the integrator, 2026-11-22. The flaky full test it found is T80.

### H037 — T54: plane fits re-fit only the boards whose source or target changed

Author: Claude (integrator) | Date: 2026-11-22 | Status: resolved | For: Codex

References: T54, T53, I40, I26b; worker/model.py `Model.apply` (the loop over every `SSFitResult` object after
each op), worker/plane_fit.py `update()`.

Touches: worker/model.py (`apply` only), worker/plane_fit.py, worker/scenario/97_plane_fit_refit.py (T76:
a numbered file, no shared list), worker/test_properties.py only if an existing fit check must change,
ARCHITECTURE.md (one line, if the fit/recompute description there changes).

Request: today every op re-fits every fitted board, recomputes once per fit and reports each as changed. Re-fit
only fits whose source board or target board the op changed (or that a re-fit in this same op changed: a fit
whose target is itself a fitted board; keep the result the same as today's for that case), recompute once, and
report only those boards. Same geometry and fit text as today in every case; the viewport doesn't read
`changed` yet, so nothing William sees should differ. Checks: an op on an unrelated board re-fits nothing; moving
the target re-fits its fit; a fit on a fitted target follows; undo/reopen equal a fresh build. Report the time of
an unrelated op on a model with ~10 fits, before and after.


Response — Codex, 2026-11-22:

- Ready for review on `codex/h037-plane-refits`, implementation commit `10c89fd`; worktree
  `/private/tmp/fretchup-h037`. Main merged/confirmed up to date before the final records. No merge to main or push.
- `Model.apply` captures transient fit inputs before the handler and compares after native recompute. Only
  affected fits update; dependents propagate even when listed before their target, with one additional recompute
  for the whole fit batch. No state persists across undo/rebuild/reopen. Native expressions and target labels are
  included; detached fits are skipped. Changed lists no longer append untouched fits or duplicate fitted owners.
- Existing fitted-target behavior is preserved: fitting a target makes its dependent references unavailable,
  retains their last geometry, and writes the same result text. The scenario verifies this against a fresh build.
- Verification: `tools/quicktest.sh` passed on the final code: 199 scenario checks, 139 viewport checks, all other
  feature suites and parse checks passed. Standalone `TESTDIR=/private/tmp/h037-after freecadcmd
  worker/test_scenario.py` also passed (199 checks). Checks include unrelated/source/target moves, expression-driven
  targets, label changes, deleted targets, undo/reopen/fresh geometry and exact fit text, and recompute counts
  (unrelated move: one native recompute; ten affected fits: native plus one fit-batch recompute).
- Timing: standalone scenario, same unrelated move with ten fits, median of 15 sync samples excluding undo:
  before `4.150 ms`, after `2.279 ms` (~45% faster). Baseline used main's implementation before editing it.
  FreeCAD/Godot tests required running outside the sandbox because sandboxed Qt reported missing NEON support.
- Architecture changed: Lifecycle of an edit → Native property inspection and editing, plane-fit paragraph.
  No decision placeholders or new behavior choices. No test references changed.
- Scope note: native property handlers still conservatively return all boards in their own `changed` result
  (`worker/object_properties.py`, outside this job); the fit scheduler does not use that result, so it still skips
  unrelated refits. There is no requested behavior question left open.

Resolution: merged into main by the integrator, 2026-11-22.

### H038 — T78: a drawing request made while a sync is in flight is lost

Author: Claude (integrator) | Date: 2026-11-22 | Status: resolved | For: Codex

References: T78; docs/protocol.md finding 3; viewport/document.gd `request_drawing`, `_send`, `on_sync_reply`.

Touches: viewport/document.gd, viewport/test_document.gd (headless, in the feature tests), docs/protocol.md
(finding 3: mark it fixed). Not viewport/main.gd (H036 is moving code out of it).

Request: when `request_drawing()` arrives during a sync, remember it, and send `drawing: true` with the
follow-up sync. Add document-test checks for: the request while idle (as today), the request during a sync
(the follow-up carries drawing), and a request that is answered once (the flag clears after it's sent).


Response — Codex, 2026-11-22:

- Ready for review: `codex/h038-drawing-request`, implementation commit `5ce74b2`.
  Worktree: `/private/tmp/fretchup-h038`; main confirmed up to date before writing these final records.
- `request_drawing` now retains pending intent during an in-flight sync. `_send` consumes it into the existing
  `drawing` field, alongside the latest ops. Later syncs send false unless another drawing was requested.
  `reset` clears queued intent so it cannot leak into the next model. Protocol finding 3 is marked fixed.
- Reproduced first: new headless regression failed on main's implementation at the busy follow-up drawing check
  (42 passed, 1 failed). After the fix, the document test passes all 43 checks: idle request, busy/coalesced
  requests with edits, clearing after send, settling without an extra sync, and model switching.
- Verification: `Godot --headless --path viewport --script res://test_document.gd` 43/43;
  `tools/fulltest.sh` passed, all six recorded suites match references and all feature tests pass;
  final `tools/quicktest.sh` passed, 139/139 viewport checks plus all feature suites.
- Test reliability note for the integrator/H039: the first quick run passed all feature tests but failed
  `[worker] a new worker took over and confirmed the next board` (138 passed, 1 failed). Full test then passed,
  and the unchanged quick retry passed. No test-reliability files or references were changed.
  Logs: `/private/tmp/h038-document-before.log`, `/private/tmp/h038-document-after.log`,
  `/private/tmp/h038-quick.log`, `/private/tmp/h038-full.log`, `/private/tmp/h038-quick-retry.log`.
- Architecture sections changed: none. Commit rationale: existing document-controller intent tracking and
  existing wire field; no module boundary, state ownership, file format or persistence change.
  Decision placeholders: none. No behavior questions remain open. Nothing merged into main or pushed.

Resolution: merged into main by the integrator, 2026-11-22.

### H039 — T80: make the full test reliable (suites that sometimes differ, a startup crash)

Author: Claude (integrator) | Date: 2026-11-22 | Status: resolved | For: Claude

References: T80, P07, P13 (the full test is the merge gate), T45 (an earlier timing race fixed the same way:
watch for the state, don't assume how fast it comes); the H036 worker's notes in docs/handoff-archive.md (### H036).

Touches: viewport/tests/suites/*.gd, viewport/tests/harness.gd, tools/fulltest.sh, tools/compare_suites.py,
tests/reference/ only if a recording itself is wrong (say why). Not viewport/tools/* (H040 owns them) and not
viewport/main.gd unless a test hook there is the cause (say so first).

Request: on main, `tools/fulltest.sh` fails now and then: one recorded suite differs, a different one each run
(movetest, holetest, infertest, mirrortest seen), and once Godot crashed at startup (signal 11 in macOS
file-open handling, before our scripts ran). Reproduce first: run it 10 times and count, and note the load (other
agents run tests at the same time). Find each cause; make the suites wait on state (a confirmed mesh, a reply)
rather than on time; retry a run that crashes before any script starts, and say so in the output. Done when 10
runs in a row pass, also with a quick test running beside them. Report the before/after counts.

#### Response — Claude (worker session), 2026-11-22

Done on `claude/h039-flaky-full-test`. Status: answered.

- **Before (main 0166d74, no change):** 10 of 10 full tests passed with the load average at 19–113 (other agents
  testing too), then 10 of 10 more with quick tests looping beside them (load 94–122). So 20/20: the recorded-suite
  differences H036 saw (on 04a5e11 and its branch) don't reproduce on today's main. I found nothing in the suites to
  make wait on state; I didn't change a suite or a reference.
- **The startup crash:** `tools/fulltest.sh` now runs a suite once more when Godot dies by a signal before any of
  our scripts print (no SHOT/TEST/SHOPSKETCH/QUICK/SCRIPT ERROR line, no GDScript backtrace), and prints
  "<suite>: Godot crashed at startup (exit N) before our scripts ran; ran it again (log: ...godot-crash.log)".
  One retry only. A crash after our scripts started, a timeout (124) or a kill (143) still fails. Checked with a
  stand-in Godot that segfaults on its first start: holetest was retried, said so, and the run passed.
- **After:** quick test 139/139; full test passes.
- **Found, not fixed (quick test, pre-existing):** 1 of 11 quick tests run beside the full tests failed
  `[worker] a new worker took over and confirmed the next board` (shown ["b1","b3"], no b9). The new worker's log
  has `sync seq=57 ... nothing` and no seq=58, and `_wait_confirm` returned with nothing in flight. My guess is
  that a reply from before the restart (or the re-sent request) cleared `in_flight` in `document.gd`
  (`on_sync_reply` clears it for any seq), which is T70's ground. I didn't touch it: H038 owns document.gd.
  Logs: shopsketch-quick.7bvkF18Yev (vp3.log, vp3/worker.log).
- Architecture: none (a test script only).

Resolution: merged into main by the integrator, 2026-11-22. The quick-test flake it found (a worker restart, a reply clearing in_flight) joins T70 (H042).

### H040 — T33: small distances: typed values of any size get through

Author: Claude (integrator) | Date: 2026-11-22 | Status: resolved | For: Codex

References: T33 (your D05), I35 (typed lengths); viewport/tools/move_tool.gd (`vec.length() < 0.5` at ~422, and
~102), rect_tool.gd (~49, ~101), push_tool.gd; the worker's push/move handlers if they refuse tiny values too.

Touches: viewport/tools/move_tool.gd, rect_tool.gd, push_tool.gd, tool.gd (shared distance constants), viewport/tools/CLAUDE.md (if the tool interface
says anything about it), a new quick section viewport/tests/quick/small.gd (found by name), a new
worker/scenario/98_small_distances.py, worker/push.py and worker/move.py only if the worker refuses them, the T33
row. Not viewport/tests/suites/* or harness.gd (H039 owns them), not viewport/main.gd.

Request: today pushes and moves under 0.5 mm are dropped. Keep that for drags (a drag that small is an accident),
but a typed value of any size (0.2 mm, 1/64") goes through, as does a snap to a point that close. Keep three
things separate in the code, each named: the accidental-drag threshold, FreeCAD's geometry tolerance, and display
rounding. If the drag threshold should become a Tunable, or anything else needs William, ask in chat first.
Checks: a typed 0.2 mm push and move land in FreeCAD at 0.2 mm; a 0.3 mm drag is still ignored; undo is one step.


Response — Codex, 2026-11-22:

- Implementation delivered for review on `codex/h040-small-distances`, commit `40533fc`, worktree
  `/private/tmp/fretchup-h040`. Main confirmed up to date before these records. **The whole quick-test gate
  remains open** due to baseline failures below; do not read this as an all-tests-green delivery.
- Pointer completion applies the existing 0.5 mm accidental-drag filter; typed values and geometry snaps reach
  the commit methods using the existing 0.001 mm worker/model tolerance. Tiny nonzero preview vectors can supply
  the direction of a typed move. Move amendments, rectangle sizes and push distances retain fractional values
  instead of being quantized to 0.001 mm. Display text remains whole millimetres, as before. Integer-plane snap
  noise is cleaned separately, preserving the existing exact back-face snap and fractional input precision.
- Scope addition announced before editing: `viewport/tools/tool.gd` holds shared, separately named
  `ACCIDENTAL_DRAG_MM`, `GEOMETRY_TOLERANCE_MM`, `DISTANCE_DISPLAY_FORMAT` and `DIMENSIONS_DISPLAY_FORMAT`.
  No Tunable added. Worker handlers needed no change: scenarios pass 0.2 mm, 1/64 inch and 0.0012 mm operations.
- Verification: new `worker/scenario/98_small_distances.py` contributes 28 checks (227 scenario checks total),
  including exact small moves/push strips, narrow stock and undo back to the fixture. New quick section
  `small.gd` passes all 14 checks: typed 0.2 mm push/move, one-step undo, fractional push and move amendment,
  typed small preview direction, intentional small point snaps, rejecting unsnapped 0.3 mm completions, and
  small rectangle dimensions. It uses real UI input for typed values; exact final pointer/snap states are
  injected for threshold checks so those assertions do not depend on camera pixels or snap radii.
- `tools/fulltest.sh` PASSED: all six recorded suites unchanged, targeted suites and every feature suite passed.
  No references changed. Logs: `/private/tmp/h040-full1.log`.
- Whole quick-suite results: corrected three-window run 151 passed / 2 failed (hide, worker restart);
  `tools/quicktest.sh --one` 150 passed / 3 failed (hide, undo's redo check, worker restart). All feature suites
  passed in both. First iteration also caught/fixed back-face float noise and the new test's missing axis lock.
  Logs: `/private/tmp/h040-quick1.log`, `/private/tmp/h040-quick2.log`, `/private/tmp/h040-quick-one.log`.
- Independently reproduced on clean main `5578552` in a detached temporary worktree: `tools/quicktest.sh`
  138 passed / 1 failed at `[hide] View > Hidden geometry shows it ghosted` (null material override), with every
  feature suite passing. Log: `/private/tmp/h040-baseline-quick.log`. The worker restart failure is already
  assigned to H042; the hide failure and single-window redo check still need integrator triage. H040 does not
  change hide, undo, controller, main or harness code. These failures are retained, not suppressed or retried away.
- Architecture sections changed: none; existing tool/op interfaces, ownership and persistence are unchanged.
  The tool guide documents the separate numeric policies. Decision placeholders: none; no William behavior
  questions remain. Open: whole quick-test gate and integrator review. Nothing merged into main or pushed.

Resolution: merged into main by the integrator, 2026-11-22. Quick test with H040: only the hide check fails, which fails on main back to 8ff1f91 too (now T85); the worker-restart check is H042. Full test passes.

### H043 — T85: the quick test's hide check fails on main

Author: Claude (integrator) | Date: 2026-11-22 | Status: resolved | For: Claude

References: T85, P07; viewport/tests/quick/hide.gd (the check at "View > Hidden geometry shows it ghosted"),
viewport/selection.gd `toggle_hidden_geometry`, viewport/presenter.gd (where `mat_hidden_ghost` is applied).

Touches: viewport/tests/quick/hide.gd, viewport/tests/quick/selection_row.gd (if its occasional failures share the
cause), viewport/tests/harness.gd. Read-only on selection.gd, presenter.gd and main.gd: H041 (the Circle tool) is
changing presenter.gd and main.gd. If the cause is in app code rather than the test, stop and report it in the
handoff before changing anything.

Request: `[hide] View > Hidden geometry shows it ghosted` fails on every quick test since at least 2026-11-22 01:00,
on main back to 8ff1f91, though workers saw it pass the evening before. b1's material_override is null, so the H
press before it didn't hide b1 (the click on b1 then H, in hide.gd). Find out why: the test's timing, the click
missing b1, or something in the environment (it passed before on the same code). Also seen once: four
`[selection_row]` checks failing together. Done when 5 quick tests in a row pass with no hide failure. Report what
the cause was.

**Response — Claude, 2026-11-22.** Branch `claude/h043-hide-check`. Cause: the test, not the app. `main.gd`'s
`_menu` drops a repeat of the same command within 150 ms (so a menu item and its key don't both fire). hide.gd
presses H, then (wave, drag, Cmd+Z, wave, click) H again; instrumented, the gap at the click was 190–270 ms, and on
a fast run the second H fell inside 150 ms and was thrown away: b1 selected, never hidden, material_override null.
Passing runs were the slower ones (16–21 s), which is why it looked environmental. The `[selection_row]` cluster
fits the same cause (Backspace → `_menu("delete")` right after the previous lap's Backspace); not reproduced in
these runs. Fix (test only): `harness._menu_settle()` waits until no command fired in the last 160 ms; every
`_key*` helper calls it, and hide.gd's direct `m._menu(...)` calls go through `harness._menu(tag)`. No app code
changed. Verified: `tools/quicktest.sh` 6 runs in a row, no hide failure (5 × 153/153; the 6th 152/153, see below).
Architecture sections changed: none.
Still open: (1) `[worker] a new worker took over and confirmed the next board` fails intermittently, on main
before this change too (shown ids `["b1","b3"]`, no b9); outside this job's files (worker.gd). (2) Capturing a
quick test's output with `$(...)` sometimes never returns, as if a process from the run outlives it holding stdout
(perhaps the worker the `[worker]` lap restarts); a plain run redirected to a file takes 17 s. Both worth a Work
list item. (3) linked.gd calls `m._menu("detach")` directly; harmless now, but could use `harness._menu`.

Resolution: merged into main by the integrator, 2026-11-22.

### H044 — T58: copy an assembly into a row (3x, /3)

Author: Claude (integrator) | Date: 2026-11-22 | Status: resolved | For: Codex

References: T58, I47 (copying a whole assembly makes a new assembly; a row of them is refused today), I32 (a row
works like a component you enter), T12 / A22c (rows of boards, linked copies), I48; viewport/tools/move_tool.gd
(`_whole_assemblies`, the count amendment), worker/move.py (`groups`), worker/assembly.py (`copy_into_assembly`).

Touches: viewport/tools/move_tool.gd, viewport/selection.gd (what a row member stands for), worker/move.py,
worker/assembly.py, worker/scenario/70_assembly.py (replace the old refusal check), a new worker/scenario/NN_assembly_rows.py, a new viewport/tests/quick/assembly_row.gd (or steps
in quick/assembly.gd), the T58 row. Not viewport/presenter.gd, main.gd, keys.gd, push_tool.gd, worker/push.py,
worker/model.py, docs/protocol.md or ARCHITECTURE.md: H041 (the Circle tool) is changing them. If you need one
of them, say so in chat first; for docs/protocol.md and ARCHITECTURE.md, put the text you'd add in your response
and the integrator adds it at merge.

Additional Touches — Codex, 2026-11-22: viewport/CLAUDE.md (remove the old row-refusal description);
ARCHITECTURE.md, Selection operations and Native model and identity only,
to satisfy AGENTS.md's same-commit architecture rule; announced in chat, separate from H041's module table rows.

Request: `3x` or `/3` after copying a whole assembly makes a row of assemblies: each copy a new assembly (I47),
the row spaced like a row of boards, its spacing editable later the same way. From outside, a click picks the
whole row; inside the row, an assembly stands as one member (entering it again enters that assembly). Undo is one
step. Anything this doesn't settle (what moving one assembly out of the row does, whether the copies are linked
like a row of boards): ask William in chat, one question at a time, with a recommendation, and log the answer.
Checks: scenario steps for 3x and /3 of a two-board assembly, an edit of the spacing, undo, reopen equal a fresh
build; a quick section that does it with the real Move tool.

Response — Codex, 2026-11-22 (claimed; behaviour clarification pending):

- Claimed `codex/h044-assembly-rows` from main `4aec99f` in `/private/tmp/fretchup-h044`.
  H041 is already claimed; H044's implementation files do not overlap H041 or H043.
- Added `worker/scenario/70_assembly.py` to Touches above: it asserts that assembly rows are refused.
  The existing `viewport/tests/quick/assembly.gd` has the matching refusal check and is already in scope.
- Asked William whether the row's copies stay linked in shape (recommendation: yes, as existing board rows
  and single assembly copies). Awaiting his answer before implementing dependent behaviour.
- Still to settle, one question at a time: moving a copied assembly inside the entered row (recommendation:
  detach that whole assembly's position from the row, retaining shape links, following I32).
- No application code changed; Status remains open. Protocol/architecture wording will be supplied here
  for the integrator as the assignment requests.
- Baseline `tools/quicktest.sh`: runtime aborts in Godot/FreeCAD, three viewport windows and twelve feature
  checks did not finish; terminated the stalled serve test. Log-sort/ID/startup tests passed (12/29/25).
  Logs: `/var/folders/94/7fmphygj0xbfskx9w0ntz48w0000gn/T/shopsketch-quick.mlFeHj9mXg`.

Response — Codex, 2026-11-22 (implementation complete):

- Branch: `codex/h044-assembly-rows`; implementation commit `15f81d4`. Based on current main `b426d7f`.
- William confirmed linked shapes (I52, which supersedes I47's temporary refusal) and moving a copied
  assembly inside its row detaches all its positions while keeping shape links (I53). No questions remain.
- `3x` / `/3` amend the original copy op; each offset gets its own assembly. Source-major board IDs and old
  single-copy journals remain readable. Array holders keep their board origins and share Count/Step/Span
  through the first holder. Editing that master Step (fixed) or Span (distributed) changes the whole row.
- Existing board `assembly`/`row` metadata resolves row → assembly → board context; Esc returns to the row.
  Moving outside moves every board once; inside a row, moving a copied assembly detaches all its members.
  Shape edits still propagate, including after detachment. One undo removes the row. Mirrored assembly
  members retain native mirror chains of hidden linked sources, with array expressions on source placements
  and mirror planes; detaching clears both. Added native checks for reflected geometry, shared shape edits,
  spacing, whole-row movement, detachment, fresh builds and reopen, plus atomic invalid-ID rejection.
- Verification: `tools/quicktest.sh` passed: 165 viewport checks, all feature tests (259 scenario checks).
  Logs: `/var/folders/94/7fmphygj0xbfskx9w0ntz48w0000gn/T/shopsketch-quick.AVMXaGcRdT`.
  `tools/fulltest.sh` passed: all six recorded suites unchanged, targeted suites and all feature tests pass.
  Logs: `/var/folders/94/7fmphygj0xbfskx9w0ntz48w0000gn/T/shopsketch-full.RViv4aHKnq`.
  The initial UI failure was only an overly strict new assertion: exported boxes round /3's 66.666… to 66.67;
  fixed its tolerance to the export precision. The earlier runtime aborts were confined to sandboxed runs;
  the completed verification ran with approved host execution.
- Architecture: updated Selection operations and Native model and identity in the same code commit, as
  AGENTS.md and the commit hook require. Announced the ARCHITECTURE.md overlap in chat before editing;
  H041 owns module table rows, which are untouched. Also corrected viewport/CLAUDE.md's old refusal description (announced first; no other job lists it).
  No other job's application files were touched.
- Integrator: update `docs/protocol.md`'s move schema to `groups?: {old AssemblyId: new AssemblyId | new AssemblyId[]}`.
  A string represents one copy; an array contains exactly `count` distinct destination IDs, one per offset.
  Replace "assembly rows are currently refused" with "whole-assembly copies support fixed and distributed
  rows; each offset gets its own assembly; board IDs remain source-major". Bump the reference revision
  alongside H041's pending protocol changes. This document remains untouched here as assigned.
- Placeholders: I52, I53. No merge to main or push performed.

Resolution: merged into main by the integrator, 2026-11-22.

### H042 — T70: a late worker reply can't replace a newer state

Author: Claude (integrator) | Date: 2026-11-22 | Status: resolved | For: Claude

References: T70, U02 (its last clause), W13; docs/protocol.md findings 2 and 4 (lifecycle replies reach sync
logic; an open reply has no seq); viewport/document.gd `send_open`, `on_opened`, `on_sync_reply`;
viewport/main.gd `_on_worker`, `_on_open`; worker/serve.py `handle`.

Touches: viewport/document.gd, viewport/main.gd (`_on_worker` and `_on_open` only), worker/serve.py (`handle`:
echo seq on open and lifecycle replies), viewport/test_document.gd, a new worker/scenario or a check in
worker/test_serve.py, docs/protocol.md (findings 2 and 4: mark fixed; the reply fields), ARCHITECTURE.md if the
protocol section names reply fields. Not viewport/tools/* (H040), not viewport/tests/suites/* or harness.gd (H039).

Request: every worker reply the window acts on can be matched to the request it answers, and one that answers
an older request is ignored. (1) `open` echoes the request's seq and model; the window drops an open reply for a
model it has since left, or older than its latest open. (2) `_on_worker` routes flush / hello / bye / quit replies
by cmd, so they never reach `on_sync_reply`. (3) Sync already does this by seq: check it holds when a reply
arrives after a model switch. This is a protocol change: bump the reference version in docs/protocol.md. (4) Also seen by H039 (1 in 11 quick tests under load): `[worker] a new worker took over and confirmed the next
board` failed: after a worker restart a reply from before it (or the re-sent request) cleared `in_flight`
(`on_sync_reply` clears it for any seq), so the next sync was never sent. Make `in_flight` follow the seq. Checks:
a stale open after a quick A → B switch is ignored (headless document test), a flush reply doesn't touch sync
state, the serve test sees seq echoed.

**Response — Claude (worker), 2026-11-22.** Done on `claude/h042-late-replies`.
- (1) `send_open` advances `seq` and records it as `open_seq`. The worker echoes `seq` (and the absolute model)
  on open success, `already_open` and errors. `document.gd:is_current_open` drops a reply that isn't for the
  latest open or names another model. `main.gd:_on_open` checks it first, so a late refusal can't send the
  window back either.
- (2) `_on_worker` sends only `sync`/`replay` replies to `on_sync_reply`. Other replies are dropped (an error is
  shown in the status line). hello/flush/bye/quit now echo `seq` too.
- (3) and (4) `in_flight_seq`: `on_sync_reply` ignores any reply that isn't for the request in flight, so an
  answer from before a reconnect (or a lifecycle reply) can't clear `in_flight` and strand the next sync. With
  that, a reply after a model switch is matched by seq as before.
- Two existing document checks used replies the worker never sends (an error with no seq, and an answer for a
  seq that wasn't in flight); I corrected them to real ones.
- Tests: document test 53/53 (8 new: stale open after A → B, stale refusal, wrong model, re-open, lifecycle
  reply leaves sync state alone, reply from before a reconnect, resend then latest). Serve test 15/15 (5 new
  seq-echo checks). Quick test: 152 passed, 1 failed (T85's hide check, failing on main already). Full test
  passes.
- Docs: protocol reference 0.2 (findings 2 and 4 fixed, reply fields). ARCHITECTURE.md: "Lifecycle of an edit"
  step 8 and the paragraph after it, and the commands table (open's fields, seq echo).

Status: answered

Resolution: merged into main by the integrator, 2026-11-22.

### H041 — T81: the Circle tool

Author: Claude (integrator) | Date: 2026-11-22 | Status: resolved | For: either

References: T81, I49, I50 (key C) (Codex S08), A03 (faces by geometry), A22b (hole runs), I04b (new board vs cut),
viewport/tools/CLAUDE.md (the tool interface), rect_tool.gd (the model to follow), FREECAD_FEATURE_MAP.md (S08 row).

Touches: viewport/tools/circle_tool.gd (new), viewport/tools/push_tool.gd and worker/push.py (pushing a circle's
face), worker/circle.py (new, a CircleActions class: found by itself, no model.py edit), viewport/presenter.gd (the circle's
draft), (no main.gd or keys.gd edit: circle_tool.gd declares its TOOL constant, viewport/tools/CLAUDE.md "Adding a tool"),
viewport/test_tools.gd and viewport/tests/quick/registry.gd (add Circle to the pinned tool list), worker/scenario/99_op_registry.py (the new op type), viewport/tools/CLAUDE.md,
viewport/tests/quick/circle.gd and worker/scenario/NN_circle.py (new), docs/protocol.md (the new op),
ARCHITECTURE.md (module table rows).

Touches clarification — Codex, 2026-11-22: also viewport/measure_box.gd (route typed circle radii through
the length evaluator), viewport/inference.gd (iterate the actual loose-profile perimeter instead of four corners); main.gd includes the small redo, menu selection and sibling-highlight tool lists.
Circle profiles reuse the existing r counter / rect target key, so document.gd needs no change. H042 is queued
behind H041; H043 and H044 do not own these files.

Rework Touches — Codex, 2026-11-22: the assigned registry/test/documentation files above, plus
worker/serve.py and viewport/main.gd for the paired protocol-version bump; main.gd retains the existing
Circle profile undo/redo support and generic profile tooltip, with no tool-registration edits. Also retain
viewport/inference.gd (profile perimeter snapping) and viewport/measure_box.gd (Circle radius length parsing)
from the original implementation. The comparison
of Circle predictions with FreeCAD goes in the already assigned viewport/tests/quick/circle.gd (P21).
Working on codex/h041-registry in /private/tmp/fretchup-h041-registry; original Circle branch preserved.

Request: centre click, then radius by drag or typed value (any length syntax the measurements box takes), on the
ground or on a face, snapping like Rectangle. In FreeCAD an exact circle (sketch or Part circle), never a polygon;
the viewport draws facets. Push/Pull turns it into a round board (on the ground, or with New board on) or a round
hole / boss on a face, with the same new-board and cut rules as a rectangle. The key is C (I50, William's call); ask William
before building about anything in the gesture that rect_tool.gd doesn't settle. Checks: scenario
steps for circle → push into a dowel, a round hole through a board, undo/reopen equal a fresh build; a quick
section that draws one with the real tool.


Response — Codex, 2026-11-22:

- Ready for review on `codex/h041-circle-tool`, implementation commit `5d8e3be`; based on main through
  `b426d7f`. No merge into main or push. No placeholder IDs or new William decisions.
- Built Circle (C, toolbar and Tools menu), centre then radius by click-click or press-drag-release, typed
  lengths through the shared evaluator (fractional inches included), ground/face snapping, immediate faceted
  draft, Escape, undo/redo and loose-profile restoration. The presenter and snapping iterate a profile's actual
  perimeter. Circle and rectangle profiles share `r` IDs, `RectId` and `target.rect`; document.gd is unchanged.
- Native profiles are exact, fully constrained `Sketcher::SketchObject` circles with an editable radius;
  Push/Pull reuses/clones native sketches in world or board-definition coordinates. Ground pushes make round
  boards; face pushes cut or join, with through-cut expressions and B for separate boards, like Rectangle.
- Verification: `tools/quicktest.sh` passed: **169 viewport checks, 0 failed**, all feature tests passed
  (including **272 scenario checks**, 0 failed). Logs:
  `/var/folders/94/7fmphygj0xbfskx9w0ntz48w0000gn/T/shopsketch-quick.lXZbaUltLN`.
  `tools/fulltest.sh` passed (exit 0): all six suites match, targeted UI and feature tests pass. Logs:
  `/var/folders/94/7fmphygj0xbfskx9w0ntz48w0000gn/T/shopsketch-full.2u5RQvlFaQ`.
  The full run preceded the final two extra scenario cases and UI volume-tolerance correction (bodies.json
  rounds volumes to 0.1 mm³); the final quick run covers those. Earlier quick runs also reproduced the known
  H042 worker-restart and H043 hide failures; both passed in the final run.
- Tests cover exact cylinder/bore/boss volumes, native circular edges and sketch constraints, vertical mirrored
  stock, translated linked stock, an arbitrary plane, reusing a consumed profile, invalid radii, undo, fresh-build
  and reopen parity. UI checks use the real tools, including fractional-inch and sub-mm radii, centre picking,
  undo/redo, round holes/bosses and separate boards. Visually inspected `circle_dowel.png` and
  `circle_hole_boss_board.png` in the quick run's `vp3/shots/`: toolbar fits; round solids and through-hole show.
- Architecture sections changed: **Where responsibilities live** and **Native model and identity**.
  `docs/protocol.md` is now reference **0.2**, adding the `circle` op and defining `target.rect` as a rectangle or
  circle profile ID; H042 should bump from this version. The tool guide includes Circle and its limits.
- Nothing in the H041 request remains open. Existing rectangular-stock plane-fit end conditions remain
  rectangle-only; circles keep point/back-face depth inference. Round-hole Move/array UI remains outside this
  job (exported cut handles are still rectangular). The integrator can update I49/I50's implementation-status
  cells when merging; only T81's result row was edited here.

Response — Claude (integrator), 2026-11-22: reviewed; held for the tool registry (A34), now on main. Please
merge main into `codex/h041-circle-tool`, then: drop your edits to viewport/main.gd (tool list, toolbar) and
viewport/keys.gd (the C key) and put a `TOOL` constant in circle_tool.gd instead (id "circle", label "Circle",
tip "Circle (C)", key KEY_C, order between Rectangle and Push/Pull; viewport/tools/CLAUDE.md "Adding a tool");
move your worker op into a `CircleActions` class in worker/circle.py and drop the HANDLERS / Model-bases edits in
worker/model.py; add Circle to the pinned lists in viewport/test_tools.gd, viewport/tests/quick/registry.gd and
worker/scenario/99_op_registry.py; bump nothing in the protocol version unless a message changed (a new op type
inside sync is a payload change: bump PROTOCOL_VERSION to 2 on both sides, A35). Run `tools/gate.sh`, then
answer again. Don't edit the Work list (P17).

Response — Codex, 2026-11-22 (A34/A35/P18/P21 rework):

- Ready on `codex/h041-registry` in `/private/tmp/fretchup-h041-registry`; original
  `codex/h041-circle-tool` preserved. Merged main through `f4f752c` and resolved the registry conflicts.
  Rework implementation commit `59b9d4e`. No main merge, push or integrator lock taken.
- Circle declares `TOOL` (id circle, label Circle, tip Circle (C), KEY_C, order 35 between Rectangle and
  Push/Pull, show_links true). Toolbar, Tools menu, shortcut and linked tint come from the registry.
  `viewport/keys.gd` and `worker/model.py` are identical to main: no explicit Circle registration remains.
  `CircleActions` is automatically discovered in worker/circle.py. Pinned viewport and worker registry
  tests include Circle. main.gd retains only the protocol bump and the existing generic-profile tooltip
  and Circle profile redo handling; inference/measure-box support is retained as described in Touches.
- Paired wire `PROTOCOL_VERSION` values are 2 because Circle adds a sync payload type (A35).
  Protocol reference 0.3 preserves H042's reply matching and documents Circle and the new wire version.
- P21: added five comparisons using the actual presenter prediction and FreeCAD's exported cylinder volume
  and bounds: ground, vertical, tilted, reversed normal/sub-mm radius, translated/large radius. Radius
  checks allow exported-volume precision; bounds allow the 64-facet sagitta and floating-point precision.
- `tools/gate.sh`: GATE PASS; quick 200 passed, 0 failed; zero known failures used. Full test passes,
  all six recorded suites unchanged; all feature suites pass (308 scenario checks, tool registry 10,
  serve 16, document 53). Logs:
  `/var/folders/94/7fmphygj0xbfskx9w0ntz48w0000gn/T/shopsketch-gate.e7ffwD`.
- Architecture sections: Where responsibilities live; Native model and identity. Registration follows A34;
  exact sketches, previews and profile identity retain the original implementation described above.
- No new behavior decisions or placeholder IDs. Work list left as main (P17); integrator records the result.
  No implementation questions remain; the original limits on rectangular-stock plane fits and round-hole
  Move/array UI still apply.
- `tools/build_app.sh` passed; the packaged app discovers all six tools, including Circle
  (`dist/tools-check.log`: TOOL TESTS 10 passed, 0 failed). Its bundled worker includes CircleActions
  and protocol version 2. Build stayed in this isolated worktree's dist/ directory.
- Refreshed main again through `30a21da` after verification: only the new H045 board/Work-list/handoff
  coordination entries changed. Preserved them; regenerated the open list with H041 answered and H045 open.

Resolution: merged into main by the integrator, 2026-11-22.

### H045 — T86: a process outlives the quick test

Author: Claude (integrator) | Date: 2026-11-22 | Status: resolved | For: Claude

References: T86, P07, P18 (the gate captures the quick test's output); found by the H043 worker
(docs/handoff-archive.md, ### H043, "Still open" 2 and 3); T47 (test workers on their own ports), T80.

Touches: tools/quicktest.sh, viewport/tests/quick_runner.gd, viewport/tests/quick/worker.gd,
viewport/tests/quick/linked.gd, viewport/tests/harness.gd. Read-only on viewport/main.gd (the worker process code):
if the cause is there, say so in chat before changing it.

Request: capturing the quick test's output (`out=$(tools/quicktest.sh)`) sometimes never returns, as if a process
from the run outlives it and keeps stdout open; the likely one is the worker the `[worker]` section restarts. Find
what's left running after a quick test (`pgrep -fl freecadcmd` before and after), make every test worker stop when
its window does, and make quicktest.sh wait for or stop what it started. Also: linked.gd calls `m._menu("detach")`
directly; use `harness._menu` (it waits out the menu's 150 ms repeat filter, T85). Done when 10 captured runs in a
row return, no freecadcmd from a test run is left afterwards, and `tools/gate.sh` passes.

**Response — Claude, 2026-11-22.** Branch `claude/h045-leftover-process`, commit 2f7c9ac. Cause: not a test worker.
`pgrep -fl freecadcmd` before and after a quick test: none left. What outlived the run was the watchdog's
`sleep 120` (tools/quicktest.sh): line 29 killed the watchdog subshell, but its `sleep` child lived on with the
script's stdout, so anything capturing the output waited out the 120 s (~128 s a run). Fix: the watchdog runs its
sleep in the background, kills it on TERM, and its output goes to /dev/null (it writes to stopped.log anyway); the
120 s stop still works. No change to main.gd, worker.gd or quick_runner.gd was needed. linked.gd's
`m._menu("detach")` now goes through `harness._menu`.
Verified: 10 captured runs in a row (`out=$(tools/quicktest.sh)`) all returned, 17–38 s, 174/174 each; 3 more with
each leftover's cwd checked: nothing left. During runs 4–8 a `sleep 120` and a `freecadcmd worker/test_scenario.py`
from another checkout appeared (most likely Codex's H041 worktree, whose quicktest.sh lacks this fix); they cleared
on their own. `tools/gate.sh`: GATE PASS in 37 s. Architecture sections changed: none.
Still open: the intermittent `[worker] a new worker took over` failure (H043's note 1) didn't appear in these 13
runs; no fix attempted.

Resolution: merged into main by the integrator, 2026-11-22.

### H047 — T88 stage 1: the tools' interface to Main (inventory and proposal)

Author: Claude (integrator) | Date: 2026-11-22 | Status: resolved | For: Codex

References: T88, A33b, A34 (the tool registry), P10 (documentation owners); viewport/tools/*.gd, viewport/main.gd,
viewport/document.gd, selection.gd, presenter.gd, inference.gd, measure_box.gd, keys.gd; viewport/tools/CLAUDE.md
(the tool interface as written today). William's call, 2026-11-22: this goes before the Line tool (H046 waits for it).

Touches: docs/specs/T88-tool-interface.md (new). Read-only on all code. Delivery metadata: this entry
and the generated H047 status in docs/agent-handoff.md. No overlap with H045 or H048 implementation files.

Request: tools reach into Main for shared state (move_tool.gd uses `m.` ~130 times, push_tool.gd ~61); main.gd is
~2,060 lines and every feature touches it. Write the spec for a small, named interface tools use instead:
1. Inventory: for each tool, every `m.` name it reads, writes or calls, grouped by what it's for (picking and
   snapping, drafts and previews, the op list and counters, selection and context, the measurements box, materials,
   messages), and which module really owns it today (main.gd itself, or forwarded from doc / sel / pres / measure).
2. Proposal: the interface: what a tool may read, what it may call, and what goes through which owner, so a tool
   needs nothing else from Main. Name each member, say who implements it, and mark what tools write today that
   they shouldn't (state they should ask an owner to change). Say how the tests keep working (they call m.* too).
3. A migration plan: an order to move the tools (smallest first: paint, select, circle, rect, push, move), each a
   separate step behind the gate, with what each step removes from main.gd, and where the Line tool (H046) slots in.
4. Open questions for William, if any (behaviour shouldn't change; ask only where the code forces a choice).
Keep it to what a reviewer can check against the code: cite file:function for each group.


Response — Codex, 2026-11-22:

- Ready for review on `codex/h047-tool-interface`, spec commit `cde86a3`; worktree
  `/private/tmp/fretchup-h047`. Refreshed from main at `116a336` before delivery.
- Added [T88 interface proposal](../specs/T88-tool-interface.md): every `m.*` member in all six
  tools and their base, access kinds, current owners and function citations; direct inference calls and
  static Main dependencies; named context capabilities, owner-controlled writes, test compatibility,
  separate gated migrations (Paint → Select → Circle → Rectangle → Push/Pull → Move), and Line placement.
- Verified the inventory's members against source for all seven files, and checked explicit file:function
  citations. `git diff --check` passes. `tools/quicktest.sh`: 200 viewport checks passed, 0 failed,
  all feature suites passed. `tools/fulltest.sh`: exit 0; all six recorded suites unchanged, targeted
  checks and all feature suites passed. No references updated. The first sandboxed quick run aborted
  Godot/FreeCAD before tests could complete; rerunning outside the sandbox produced the passing results.
  Logs: `/private/tmp/h047-quick-unrestricted.log`, `/private/tmp/h047-full.log`.
- Architecture sections changed: none; this is a proposed design, with no implementation/boundary change.
  The existing architecture map was read and left describing current code. No production files changed.
- Decision IDs/placeholders: none added; existing T88/A33b/A34 govern. No new William choices.
- Open: integrator review of the proposed interface and follow-on implementation jobs. H046 stays queued
  until the six tool migrations and their gates finish; its key/gesture questions remain for William.
  This completes H047's spec-only assignment, not T88 implementation. Nothing merged or pushed.

Resolution: merged into main by the integrator, 2026-11-22.

### H048 — T79: a failed save is forgotten

Author: Claude (integrator) | Date: 2026-11-22 | Status: resolved | For: Claude

References: T79, A21 (the .FCStd is the model), A24 (the journal), A35 (protocol version), Q22/T19 (the save
indicator), T45; docs/protocol.md finding 5; worker/serve.py `save_pending`, `handle` (flush / bye / quit);
viewport/document.gd `on_saved`; viewport/main.gd the save indicator (~line 460) and `_shutdown_worker`.

Touches: worker/serve.py, worker/session.py (only if the save itself must report more), worker/test_serve.py,
viewport/document.gd, viewport/test_document.gd, viewport/main.gd (the save indicator and `_shutdown_worker` only),
a new viewport/tests/quick/save_failure.gd, docs/protocol.md, ARCHITECTURE.md (the saving / recovery section).
Not viewport/tools/* (H047 is reading them for the T88 spec), not tools/quicktest.sh, quick_runner.gd, harness.gd,
quick/worker.gd (H045). If H045's worker-cleanup work needs `_shutdown_worker` too, the two of you say so in chat
before either edits it.

Request: today `save_pending` logs a save failure, drops the pending save, and flush / bye / quit still answer ok;
the window shows "Saved" only when a `saved` event comes, but nothing tells it a save failed, and closing waits a
bounded time instead of for the saved revision. Make a failed save stay pending (retried on the next sync or
flush), send the window a `save_failed` event (model, rev, error), and make flush / bye / quit answer with what
was saved (and not ok when the latest revision couldn't be). The window shows the failure and, on closing, waits
for the latest revision to be saved, or says it couldn't be. Bump the protocol version (A35) and document the
event. Ask William before building, one question at a time with a recommendation, and log each answer: what the
indicator says on a failure (recommend "Couldn't save: <reason>", in the save indicator's place, staying until a
save lands) and what closing does when the save keeps failing (recommend: a dialog with Retry / Close without
saving / Cancel). Checks: a scenario or serve test that makes a save fail (a read-only folder) and sees the event,
the retry and the not-ok flush; a document test for the window's side; a quick section for the indicator.

Response — Claude (worker session), 2026-11-22: done on `claude/h048-failed-save`, commit 2a624aa.
- William's answers, logged: I54 (the indicator says "Couldn't save: <reason>" in Saved's place, red, until a
  save lands) and I55 (closing waits for the latest revision; if it can't be saved: Retry / Close without saving /
  Cancel). New tunable CLOSE_WAIT_S = 10 s (no answer from FreeCAD in that long asks too).
- Worker: a failed save stays pending; the timer skips it, the next sync / flush / bye / quit retries it; each failure
  sends the owner `save_failed {model, rev, error}`; flush / bye / quit carry `saved` / `failed` lists, ok only when
  nothing failed (quit still stops: the window asked first). `flush` takes an optional `model`. `Session.save` rolls
  the revision back on failure (the retry saves the same rev) and raises "the folder <name> is read-only" instead of
  FreeCAD's "Failed to open file". Protocol version 2 → 3 (both sides).
- Window: `document.gd` gains `save_error`, `on_save_failed`, `unsaved`, `begin_close` / `cancel_close` /
  `on_flush_reply` and signals `close_ready` / `close_blocked`; `main.gd` turns off auto-accept quit and handles
  `NOTIFICATION_WM_CLOSE_REQUEST` (`_request_close`, `_ask_close` with the native alert, `_close_choice`,
  `_close_now`); `_shutdown_worker` runs once. `_shutdown_worker` itself is otherwise unchanged (H045: no clash).
- Verified: `python3 worker/test_serve.py` 20/20 (7 new); `test_document.gd` 65/65 (15 new); `tools/quicktest.sh`
  208 passed, 0 failed (new section `save_failure`, joined lane 2); `tools/fulltest.sh` exit 0.
- Architecture sections changed: "Protocol at a glance" (flush, bye, save_failed rows) and "Files, persistence and
  recovery" (failed saves; closing). docs/protocol.md: lifecycle, events, version, finding 5 marked fixed.
- Outside the Touches list: docs/decision-log.md (I54, I55, the tunable) and one line of worker/CLAUDE.md
  (the serve test's count and what it covers).
- Not tested by hand: the native close dialog itself (test mode records the question instead of showing it). Worth
  a look by William: put a model in a read-only folder, draw, close the window.

Resolution: merged into main by the integrator, 2026-11-22.

### H051 — T88 step 0: the tools' interface, foundation

Author: Claude (integrator, fretchup-73) | Date: 2026-11-22 | Status: resolved | For: Claude

References: T88, docs/specs/T88-tool-interface.md (the spec, Codex, H047; William approved it 2026-11-22), A33b,
A34 (a new tool is one file; no hard-coded tool lists in Main), viewport/tools/CLAUDE.md (the tool interface).

Touches: viewport/tool_context.gd (new), viewport/tool_geometry.gd (new), viewport/tools/tool.gd (setup only),
viewport/main.gd (wiring and the static wrappers that forward to tool_geometry.gd), viewport/inference.gd (explicit
inputs), viewport/presenter.gd (the rendering constants only), viewport/tool_registry.gd and its test, a new
headless viewport/test_tool_context.gd (don't add it to the feature-test script: H049 owns it; give the
line in your response and the integrator adds it at merge), ARCHITECTURE.md (the viewport modules
section), viewport/tools/CLAUDE.md. Not any tool other than tool.gd's setup: each tool moves in its own later job.
Not the test scripts in tools/ (H049, Codex).

Request: build the spec's step 0 ("Tests and incremental delivery", row 0; "Proposed surface"; "Static geometry"):
ToolContext with its capability adapters (pick, model, selection, document, view, ui, paint), each holding its owner
privately and returning snapshots; the pure static functions moved to tool_geometry.gd with Main keeping wrappers;
explicit inference inputs; a context-only setup path beside the legacy setup(Main), with the temporary marker the
registry test checks (no list of migrated tool IDs in Main). No tool moves to it yet, and nothing you'd see changes.
Checks: test_tool_context.gd covers the public member allowlist against the spec's surface, snapshot isolation, ID
sequences, append without early sync, remove signalling; the registry test instantiates tools with a context;
the exported pack still finds every tool; quick test, then the gate. Recorded references stay as they are.
Where the spec leaves a choice open, take the narrower interface and say so in your response. Later stages, for
the integrator: 1 Paint, 2 Select, 3 Circle, 4 Rectangle (beside H046 Line, on files it doesn't touch), then 5
Push/Pull and 6 Move after Line lands, 7 cleanup.

#### Response — Claude (worker), 2026-11-22: done, commit f25f58b on `claude/h051-t88-foundation`

Built step 0. No tool moved and nothing on screen changes. Gate PASS (quick test 208/208, full test passes, 0
known failures); `tools/build_app.sh` pack check: TOOL TESTS 12/12 inside the built app. References unchanged.

- `viewport/tool_context.gd`: ToolContext with `pick`, `model`, `selection`, `document`, `view`, `ui`, `paint`, each
  an inner adapter holding its owner in `_` fields and answering with copies (deep copies for dictionaries). Main
  builds it once (`_make_tool_context`) from the owners and a few narrowly bound Callables for bodies still in Main
  (`_tri_mesh`, `_lines`, `_show_marker`, `_draw_guides`, `_update_tip`, `_cursor_pos`, `paint`, the reject note,
  `new_board`, the paint name). `_make_tools` now runs after `_make_world`, so the camera and overlays exist.
- `viewport/tool_geometry.gd`: the spec's static functions under their new names; Main keeps one-line wrappers.
  `arr3` keeps its 0.001 rounding.
- `inference.gd`: no Main. Its inputs are `cam`, `world`, `pres`, `sel` and `grid_enabled` (a Callable), wired in
  `_make_tools`. It owns `GRID` / `SNAP_PX` (Main aliases them) and has the new `ray` / `project`.
- `presenter.gd`: `DEFAULT_BASE`, `SNAP_COLORS`, `AXIS_COLORS` (Main aliases them). Nothing else changed there.
- `tools/tool.gd`: `setup_context(ctx)` for every tool. `uses_main()` is the temporary marker (true by default):
  Main calls the legacy `setup(self)` only for a tool that says true, so Main has no list of migrated tool IDs.
  `accepts` reads `ctx.ui.typed_text()` (same value as `m.vcb`). Without that, a context-only tool would crash on
  its first typed character. It is the one change in tool.gd beyond setup.

Where the spec left a choice, I took the narrower interface:
- `selection.set(ids)` is `set_ids(ids)`: GDScript can't override `Object.set`.
- `view.present_draft` and `view.mirror_preview` are not there yet. They are composite and have no consumer before
  Push/Pull (step 5) and Move (step 6), so they arrive with those steps. The allowlist test lists them as deferred.
  The Push/Pull test rejection filter also waits for step 5.
- `pick.snap` / `pick.on_grid` duplicate the dictionary passed in and return the answer. Inference mutates its
  argument; through the context a tool must use the return value.
- `document.next_id` with a prefix the document doesn't count returns "" and pushes an error.
  There is no new registry.
- `model.unit_triangles` is implemented on the presenter's cache in the adapter; Main's `unit_tris` stays.

Checks: new `viewport/test_tool_context.gd`, 68 passing. It covers each capability's public members against the
allowlist, no public variables, no raw names; snapshot isolation (triangles, profile, stock frame, body ids,
selection ids, unit, members, op, append copies); id sequences, including after `restore_counters`; append doesn't
sync; remove with and without resync (signals, sync); ray/project against the camera's own answers on a tilted
camera, including the round trip and behind-camera points; view/ui/paint with bound stand-ins; Main's wrappers
against Geo; and a source check that the context, geometry and inference code never reference main.gd.
`test_tools.gd` (12) makes every tool with a context and pins `STILL_ON_MAIN` (all six).

For the integrator:
- Add to the feature-test script (H049 owns it): run
  `"$GD" --headless --path viewport --script res://test_tool_context.gd`; summary line `TOOL CONTEXT TESTS: N passed, M failed`.
  One expected `ERROR:` line is printed (the unknown-prefix check announces it).
- Architecture: the "Where responsibilities live" rows for main.gd (entry point), presenter.gd, tools/tool.gd and
  inference.gd; new rows for tool_context.gd and tool_geometry.gd; the paragraph under the table; the
  build_app.sh row. Decision log: only the Tunables rows for GRID and SNAP_PX (they now live in inference.gd).
- Outside the Touches list: `docs/decision-log.md` (those two Tunables locations only) and this handoff file. Not
  touched though stale: `viewport/CLAUDE.md`'s Files list doesn't name tool_context.gd / tool_geometry.gd, and its
  test_tools line still says five tools. Worth a line when step 1 lands.
- Step 1 (Paint) can now set `uses_main()` false and use `ctx.pick.hit`, `ctx.model.unit_triangles`,
  `ctx.selection.unit_of`, `ctx.view.preview(..., "hover")` and `ctx.paint`; the appearance.gd move is that step's.

Resolution: merged into main by the integrator, 2026-11-22.

### H049 — T90: a faster gate

Author: Claude (integrator) | Date: 2026-11-22 | Status: resolved | For: Codex

References: T90, P18 (the gate), T49 (lanes side by side), T47 (own ports), T80 and T85 (timing flakes found
under load), H045 (the leftover test process, which changes quicktest.sh first).

Touches: tools/gate.sh, tools/quicktest.sh, tools/fulltest.sh, tools/featuretest.sh, tools/test_integrate.py (the
gate's checks), ARCHITECTURE.md (validation orchestration), and this handoff entry.
Not the suites or quick sections themselves unless a timing fix needs one (say so first).

Request: the gate runs the quick test, then the full test: ~3-4 minutes, and merges wait on it. Measure where the
time goes (each lane, each suite, the feature tests, which run twice: once in each). Try: the two side by side;
running the feature tests once and sharing the result; dropping what the full test repeats from the quick test.
Keep the verdict as strict as it is (tools/test_integrate.py's gate cases must still pass). Report the times and
how many of 10 runs passed before and after, with the machine otherwise idle and with other agents' tests running.


Response — Codex, 2026-11-22:

- Branch: `codex/h049-faster-gate`; implementation: `b9f0af5`; current-main merge: `4c68334` (main through `a89c54b`). No merge to main or push.
- The gate remains quick then full (P18). Only a successful quick run with its feature/UI summary permits `--gate-ui-only`: full reuses parsing and feature checks, keeping every recorded comparison and targeted UI suite. Any quick failure retains independent full parsing/features. Standalone full remains complete. Timing lines expose parse, lanes, suites, individual features and total gate time.
- No suite or quick section was dropped: overlapping functionality does not make their assertions equivalent. Regression checks cover reuse, fallback, known/unlisted UI failures, feature failure/missing completion, missing summary, script errors, unexplained quick exits and full failures.
- Decisions/placeholders: none; P18 preserved. Architecture changed: **Validation and maintenance** only. The incoming foundation's viewport map and new `toolctx` feature-test entry are preserved.

Measurements: wall-clock seconds, same production source held fixed for the comparison (`ec3380b` baseline; `b9f0af5` patch, whose intervening main updates were documentation only). Shell timings have one-second resolution; quick-lane figures measure checks, excluding startup. Loaded means a separate baseline quick runner repeats continuously throughout each gate. Background tests also passed (23 baseline runs; 20 candidate runs).

| Gate | Passed | Mean | Median | Range |
|---|---:|---:|---:|---:|
| Before, idle | 10/10 | 38.78 | 38.84 | 38.31–39.59 |
| After, idle | 10/10 | 34.56 | 33.52 | 32.60–44.49 |
| Before, loaded | 10/10 | 81.77 | 71.25 | 70.39–115.83 |
| After, loaded | 10/10 | 62.68 | 59.41 | 57.39–94.73 |

Mean gain: 10.9% idle, 23.3% loaded. All outliers retained except a specifically observed H056 gate overlap: idle sample 8 is excluded; the driver was stopped, and its unrecorded next sample is excluded too. The idle set is candidate samples 1–7 plus three clean replacement samples, whose monitor waits for foreign test runners and rejects overlap. Replacement source is an independent frozen Git snapshot, preventing live main/board changes from affecting smoke tests. Initial snapshot-without-Git setup failures are excluded from the baseline; every measured baseline has passing smoke checks.

Parallel experiment: one pass each, 37.34 s idle and 57.72 s loaded, with unchanged full checks. It slowed individual quick lanes and parsing (loaded parsing 16 s each; feature scenario 41 s each), gave no idle advantage over reuse, and has no ten-run stability evidence. Kept P18's sequential order. H045 already removed the old watchdog delay: today's measured baseline is ~39 s idle, not the job's earlier 3–4 minutes.

<details>
<summary>Idle timing means by lane, suite and feature (seconds)</summary>

| Part | Before | After |
|---|---:|---:|
| Parsing (quick / full) | 3.7 / 4.0 | 4.0 / reused |
| Quick lane checks (1 / 2 / 3) | 7.5 / 9.8 / 11.3 | 8.0 / 10.3 / 11.8 |
| Full lanes (1 / 2 / 3 / 4) | 14.4 / 16.0 / 15.9 / 16.6 | 12.7 / 14.5 / 14.6 / 14.9 |
| undotest | 8.4 | 7.6 |
| snaptest | 2.7 | 2.6 |
| recttest | 2.3 | 2.1 |
| facetest | 6.8 | 6.2 |
| movetest | 5.1 | 5.1 |
| shelltest | 3.0 | 2.8 |
| mirrortest | 6.5 | 6.0 |
| infertest | 5.5 | 5.3 |
| jointest | 3.0 | 3.0 |
| holetest | 5.6 | 4.9 |
| zfighttest | 6.0 | 5.8 |
| rejecttest | 4.0 | 3.8 |

Features run side by side; these durations must not be added. Before is **quick / full**; after runs them once in quick (full reuses the result). The longest feature scenario fell from two runs of 13.7 / 17.1 s to one of 15.2 s; under load it was 28.7 / 34.5 s before and 28.1 s once after.

| Feature | Before quick / full | After once |
|---|---:|---:|
| native | 11.2 / 14.5 | 12.5 |
| runs | 11.4 / 14.8 | 12.6 |
| arrays | 4.0 / 4.7 | 4.0 |
| combos | 6.7 / 8.0 | 7.7 |
| properties | 2.5 / 2.8 | 2.5 |
| scenario | 13.7 / 17.1 | 15.2 |
| length | 5.7 / 6.4 | 6.3 |
| lengthproto | 1.6 / 1.1 | 1.7 |
| serve | 6.6 / 6.7 | 7.0 |
| units | 2.5 / 3.1 | 2.5 |
| document | 1.4 / 1.0 | 1.4 |
| selection | 1.4 / 1.0 | 1.3 |
| tools | 2.2 / 2.9 | 2.5 |
| logsort | 0.3 / 0.0 | 0.0 |
| ids | 0.6 / 0.2 | 0.2 |
| startup | 1.0 / 0.8 | 1.1 |
| lock | 0.2 / 0.0 | 0.1 |
| integrate | 3.5 / 3.7 | 5.9 |

</details>

Raw logs and full idle/loaded breakdown: `/private/tmp/h049-results/` (`summary.txt`, `baseline-valid`, `candidate`, `candidate-replacement`, `parallel`). Reproduction driver/analyzer: `/private/tmp/h049-benchmark.py`, `/private/tmp/h049-idle.py`, `/private/tmp/h049-summarize.py`. The final source also includes newer main (tool-context foundation), so the controlled benchmark is the optimization comparison, not a claim that newer features have zero cost.

Verification: 40/40 comparison gates pass; `python3 tools/test_integrate.py`: **28 passed, 0 failed**; shell syntax and `git diff --check` pass. Final `tools/fulltest.sh` after merging main completed with all six recorded comparisons identical, all targeted/feature checks passing (including 68 tool-context checks), no script errors and no lane failure files (`/private/tmp/h049-results/final-standalone-full.log`). Final `tools/gate.sh` exits 0: **GATE PASS**, QUICK **208 passed, 0 failed**, full passes, **0 known failures**, **33 s total** (`/private/tmp/h049-results/final-gate.log`). Both tracked architecture checks passed.

Open: none. Status answered; ready for the integrator's review. No Work list edits or new placeholder IDs.

Resolution: merged into main by the integrator, 2026-11-22.

### H056 — T94: reshape the decision log (live file + archive, subjects, principles)

Author: Claude (integrator, fretchup-73) | Date: 2026-11-22 | Status: resolved | For: Claude

References: P23 (the shape, William's call 2026-11-22), P09, P01 (never delete; superseded rows are kept), T74
(placeholders and numbering), P20 (integrate.py), P17, tools/sort_decision_log.py, tools/number_ids.py,
tools/startup.py (report_ids), tools/integrate.py (settling log conflicts, --status).

Touches: docs/decision-log.md, docs/decision-archive.md (new), tools/sort_decision_log.py and
tools/test_sort_decision_log.py, tools/number_ids.py and tools/test_number_ids.py, tools/startup.py and
tools/test_startup.py, tools/integrate.py, a new tools/test_log_archive.py for integrate.py's new steps (not
the existing integrate tests or the feature-test script, H049 owns them; give the feature-test line in your
response), .githooks/pre-commit, CLAUDE.md, AGENTS.md and docs/agent-handoff.md (only lines that say how to search the log;
the folder guides don't mention it).

Request: build P23.
1. Archive: move to docs/decision-archive.md the Superseded decisions, the Decided questions, the Done Work list
   items (and Split ones whose parts are all done), and every Details section that belongs only to moved rows.
   Rows move whole and unchanged. Measure the live file before and after.
2. Subjects: replace the Area column with one subject per decision from a fixed list, given in the log's header
   (start from: Principles, Architecture, Files/saving/undo, Drawing tools, Push/Pull, Move/copies/arrays, Snapping,
   Measurements, View and look, Feedback wave, Materials, Output, Process; merge or split where the rows say so).
   Group the Decisions table under one ### heading per subject, sorted by ID inside each. An index at the top of
   the file: subject, one line of what it covers, its IDs (generated by sort_decision_log.py, so it can't drift).
3. Principles: a Principles section before the decisions, ~8-12, each one statement plus the IDs it explains.
   Draft them from the rows (the integrator's draft: feel first / never wait on FreeCAD; the .FCStd is the model;
   SketchUp's ways unless there's a reason; relationships stay live; one key per idea; typed values follow the
   direction; one meaning per colour; refer to geometry, not FreeCAD's numbers; every prediction tested against
   FreeCAD). Give them a one-letter kind not already used (e.g. G01) so the ID tools handle them; status
   Tentative until William approves each. Each decision gets its principle(s) in a column. Fold nothing.
4. Tools across both files: `grep "^| I34 "` keeps working on either file; number_ids.py takes the next free
   number across both; startup.py's ID report finds rows in either and says which; sort_decision_log.py --check
   covers both (each row in one file only, details beside their row, the index in step); integrate.py --status
   T<n>=Done moves the item to the archive, and its log settling places a branch's new rows (written in the old
   layout, e.g. H051 and H049 in flight) under the right subject heading, asking when the subject isn't clear.
5. The instruction files' lines on searching the log name both files.
Also (2026-11-22, William agreed): the subject is what a decision is about; its letter is just part of its name.
P covers process and product, W13 is architecture, I24 is architecture: file each by subject, keep every ID, and
say so in the log's header. Don't renumber.
Checks: sort/number/startup tests for both files; a sample branch in the old layout settles into the new one; a
round trip (every ID before = every ID after, each in exactly one file, rows byte-identical apart from the
subject/principle columns). Quick test, then the gate. William reviews the principles list at merge.

Response (Claude, worker on claude/h056-log-reshape, 2026-11-22): built P23. Gate: PASS (quick 208/208, full test
passes, 0 known failures).
1. Archive: docs/decision-archive.md holds the 28 Superseded decisions, 25 Decided questions, 59 Done Work list
   items and the 14 Details sections that belong only to them; no Split item qualified (T14, T17, T35, T36 all
   have open parts). Rows moved whole. Live file: 566 lines / 145 KB before, 543 lines / 95 KB after (-35%;
   the line count barely drops because of the 13 subject headings and the index); archive 163 lines / 58 KB.
   Round trip, checked by the one-off migration: all 274 IDs before are in exactly one file after, the 120 live
   decisions differ only in the Principles cell (was Area), all 34 Details sections identical, each in one file.
2. Subjects (13): Product, Architecture, Files/saving/undo, Drawing tools, Push/Pull, Move/copies/arrays,
   Snapping, Measurements, View and look, Feedback, Materials, Output, Process. Changes from your starting list:
   "Principles" became "Product" (P04, P05, I01: it would have clashed with the Principles section), and the
   wave subject is "Feedback" (it also holds what colours mean: I06, I07). The index's Decisions column is
   generated by sort_decision_log.py, and the subject groups follow the index's order.
3. Principles: 12, written as G01..G12 (T74: the merge numbers them G01..G12, in order), all
   Tentative, each with a generated Explains column. Yours plus three drawn from the rows: never lose work
   (A24, A25, A32, I54, I55, U01-U03), a rejected action says why and leaves nothing (I06, I08, A23, W06),
   work splits by files with one integrator (A31, A33b, A34, the P rows on coordination). "Every prediction
   tested" is part of a wider "nothing rests on memory" (P01, P07, P09, P21, P23). M04, W11 and W12 name no
   principle ("—": none fits; the check accepts — but not an empty cell). William reviews the list at merge.
4. Tools: sort_decision_log.py tidies both files (moves Superseded/Decided/Done rows and their Details to the
   archive, a moved decision's cell keeps "<subject>; <principles>"; sorts; rebuilds the generated columns) and
   --check covers both (ID in both files, Details beside their row, index vs headings, unknown principles,
   statuses per table). A live file with no archive beside it is only sorted, as before. number_ids.py counts
   both files and tidies after numbering; startup.py's ID report finds rows in either file and marks archived
   ones "[in the archive]". integrate.py: --status T<n>=Done moves the item to the archive and says so; when a
   branch changed the log, its rows are settled onto main's two files before merging, and a branch written in
   the old layout always is: a changed row keeps main's subject and principles, a new decision goes under the
   subject its Area names (Architecture, Process, Wave->Feedback, Saving/Undo->Files ...), and an
   "Interaction" row stops integrate.py before it merges anything, asking for --subject <ID>=<subject>. Tunables
   rows are carried by name. Placeholder rows (I-new-N) now count as rows: the old carry_rows skipped them.
   Replayed on the 33 last real merges that touched the log: all settle onto the new files; H044's two
   "Interaction" rows ask, as intended. .githooks/pre-commit tidies both files and then runs --check.
5. CLAUDE.md (two lines), AGENTS.md (step 3) and docs/agent-handoff.md (the log link) name both files.
Tests: tools/test_log_archive.py (new, 37 checks: tidy, generated columns, checks, numbering and startup across
both files, an old-layout branch settling, --status moving an item). Add it to tools/featuretest.sh (H049 owns
it): `  "logarchive|python3 tools/test_log_archive.py|LOG ARCHIVE TESTS"`. Also added: test_sort_decision_log.py
(18), test_number_ids.py (37), test_startup.py (29); test_integrate.py unchanged (14 pass).
Not done / for the integrator: ARCHITECTURE.md line 15 still names only decision-log.md (not in my Touches);
T94's Work list row is yours (P17). A row set back from Done to something else stays in the archive and --check
reports it (no "unarchive" step).

Resolution: merged into main by the integrator, 2026-11-22.

### H058 — T96: the job queue (take, done, the dead man's switch)

Author: Claude (integrator, fretchup-73) | Date: 2026-11-22 | Status: resolved | For: Claude

References: P24 (the design, William's: read `### P24` in docs/decision-log.md first), P14 (the board), P16, P19
(tools/integrator.py: its lock lives in git's common folder; the queue's state goes beside it), P20
(tools/integrate.py), P11 (overlap by files: tools/handoff.py touches / overlaps_in), T96.

Touches: tools/job.py (new), tools/test_job.py (new; give its feature-test line in your response, H057 owns that
script), tools/integrate.py (after a merge: delete the branch and its worktree, mark the job merged), BOARD.md
(its job table becomes generated; its worker and integrator steps), docs/agent-handoff.md (its rules section),
AGENTS.md (the worker steps). Not CLAUDE.md (H057) or tools/startup.py (H055): give the lines they need in your
response and the integrator adds them at merge.

Request: build P24.
- `job.py take [--as claude|codex]`: the first Ready job for that agent, in the board's order, whose Touches don't
  overlap a job in progress (handoff.overlaps_in); makes the worktree (../fretchup-<id>) and branch
  (<agent>/<id>-<slug>) from main; records it in progress (who, when, branch, worktree); prints the handoff.
  Refuses if that agent's session already holds a job. A returned job resumes its branch.
- `job.py beat`: pushes the deadline back. Also counted as beats: a commit on the job's branch, a quick-test run in
  its worktree (read their times; don't edit quicktest.sh), and every job.py command.
- `job.py check`: what the worker runs at each 15-30 minute check-in: lists processes started from its worktree
  (Godot, freecadcmd, the test scripts) with their age, flags any that look hung (older than a limit you set as a
  tunable), and beats. Say in the instructions how a Claude worker sets its timer (CronCreate or ScheduleWakeup) and
  that a Codex worker without one still has the switch.
- `job.py wait "<question>"`: waiting on William; pauses the switch until the next beat.
- `job.py done`: refuses unless the handoff has its response and Status answered, and the quick test passed on the
  latest commit; marks done and tells the integrator.
- `job.py status` and `job.py board`: the queue as text; `board` rewrites BOARD.md's job table from the handoffs
  (Ready / queued from their Status, in an order list the integrator keeps at the top of the board) plus the live
  state. The commit hook rebuilds it like the handoff list.
- `job.py watch`: for the integrator; prints one line per event (done, stale: deadline passed, returned, queue empty
  for Claude or Codex) and keeps running, so the integrator can run it under its watcher. `job.py return <id>
  "<notes>"` puts a reviewed job back.
State: a JSON file in git's common folder next to the integrator lock, written atomically; never committed.
Deadline: 30 minutes (a tunable). Checks: take (order, overlap refused, one job per session, returned resumes),
beats from commits and test runs, the deadline and wait, done's refusals, watch's events, board generation, and
integrate.py's cleanup, all in temporary repos. Quick test, then the gate.

Response — Claude (worker, branch `claude/h058-job-queue`), 2026-11-22: built P24.
- `tools/job.py`: take / beat / check / test / wait / done / status / board / watch / return, as the request lists.
  State: `shopsketch-jobs.json` beside the integrator lock (git's common folder), written atomically under a file
  lock, never committed. Take reads the jobs and the Order line from main (what the integrator committed), skips
  jobs claimed by a hand-made branch (the old rule), passes over overlaps (handoff.touches / _covers) against
  every job in progress, waiting, done or returned, and gives a returned job first (re-making its worktree if
  it's gone). Session: `--session`, else `CLAUDE_CODE_SESSION_ID`, else `CODEX_SESSION_ID` / `CODEX_THREAD_ID`,
  else the agent's name (then it's one job per agent).
- Beats: any job.py command run in the worktree, the branch's last commit time, a recorded test run, and a
  process running in the worktree that isn't older than HUNG_AFTER (lsof's cwd, or the worktree in its command
  line). quicktest.sh isn't touched, so a quick test run by hand counts only while it runs; `done` needs a pass
  recorded for the latest commit, so it runs `tools/quicktest.sh` itself when there is none (`job.py test` runs
  and records it any time).
- Watch: one line per new event (done, stale, waiting, returned, queue empty for Claude / Codex); `--once` for one
  look. I added "waiting" to the request's list: the integrator hears a worker is waiting on William.
- integrate.py: after the commit, `job.merged`: the job marked merged, its worktree removed (`git worktree remove`;
  a dirty one is left and said), its branch deleted (`-d`). The board's table is rebuilt in the merge commit; a
  conflict in BOARD.md keeps main's and rebuilds the table. Its "left for you" no longer names BOARD.md.
- BOARD.md: an Order line at the top (the integrator keeps it), the table between markers, rebuilt by
  `job.py board` and by the pre-commit hook on main only (so worker branches never carry a rebuilt table). New
  worker and integrator steps (the timer: CronCreate every 20 minutes, CronDelete after done; a Codex worker
  without one still has the switch). The hand-kept "next" row moved to Notes as "Later (no handoff yet)".
  docs/agent-handoff.md: one rule on entries as jobs. AGENTS.md: the worker steps.
- Tunables (decision log): DEADLINE 1800 s, HUNG_AFTER 600 s, WATCH_POLL 20 s (tools/job.py, P24).
- Tests: `tools/test_job.py`, JOB TESTS 52 passed, 0 failed (~3.5 s): take (order, overlap passed over, one job per
  session, queued not taken, branch claims, returned resumes with notes), beats from commands, commits, test
  runs and processes, the deadline and wait (a commit after a wait resumes), check's hung flag, done's four
  refusals and a stale pass, watch's five events, board generation, and integrate.py's cleanup end to end, all in
  temporary repos. INTEGRATE TESTS 28/28, LOCK TESTS 9/9. Quick test: QUICK 208 passed, features all pass.

For the integrator at merge:
- tools/featuretest.sh (H057's): `"job|python3 tools/test_job.py|JOB TESTS"` (or nothing, if H057's discovery finds
  `tools/test_*.py` itself).
- CLAUDE.md, "Working with Codex": `Jobs run through the queue (P24): a worker runs python3 tools/job.py take, works
  in the worktree it gets, and finishes with python3 tools/job.py done; the integrator runs python3 tools/job.py
  watch under its watcher and reviews each done job.` and in the integrator line: integrate.py now also removes the
  job's worktree and branch.
- tools/startup.py (H055's): print `python3 tools/job.py status` (the live queue: in progress, waiting, done, next
  for each agent) beside or instead of "Ready on the board (main:BOARD.md)", which only changes at a commit.
- This merge itself: main's integrate.py is the old one, so a BOARD.md conflict stops it; take the branch's
  BOARD.md (it carries the new steps) with main's Order and Notes, then `python3 tools/job.py board`. After the
  merge, run `python3 tools/job.py board` once on main. H058 itself was claimed by hand (its branch), not through
  the queue: the board shows it "Claimed" until it's merged.
- ARCHITECTURE.md: not changed (it doesn't map the process tools; tools/job.py has no app module, protocol or file
  format). If you'd like a row beside tools/integrate.py, say so.

Resolution: merged into main by the integrator, 2026-11-22.

### H054 — T92: tools/log.py add, for decision log rows

Author: Claude (integrator, fretchup-73) | Date: 2026-11-22 | Status: resolved | For: Claude

References: T92, P09 (the log's format, in its header), P01, T74 (placeholders on a branch, numbers on main),
tools/sort_decision_log.py (its parsing), tools/number_ids.py.

Touches: tools/log.py (new), a new tools/test_log.py (don't add it to the feature-test script: H049 owns it; give
the line in your response), docs/decision-log.md (its header: one line on the command). Not the instruction files: H053 has them; give the
line for them in your response and the integrator adds it.

Request: `python3 tools/log.py add <I|A|P|M|Q|T|...> "<decision or item>" [--rel "Refines I35"] [--area X] [--where
"..."] [--why "..."] [--status Active]` adds a row to the right table: the next free number when run on main (by the
integrator), else the kind's next placeholder (I-new-N, T74); dated today; sorted by sort_decision_log.py. Also `log.py
note T66 "<text>"` appends to a Work list row's last column. Print the row it wrote. The log is now two files (P23, merged 6c1f65d): a decision goes under its subject's ###
group (--subject, required for decisions) with a Principles cell (--principles G01,G04, or —); use
sort_decision_log.py's functions (insert_row, sort_text) rather than new parsing; numbering counts both files. Also `log.py show <subject|ID>` (William, 2026-11-22), so an agent reads only what it needs: a subject name prints
the log's top (header, Subjects, Principles) only with --top, otherwise just that subject's ### group; an ID prints
its row from whichever file holds it, plus its `### <ID>` details if it has them, plus the principles it names;
`log.py show --top` prints the file down to `## Decisions`. Give the instruction lines for CLAUDE.md and AGENTS.md
("read the top, then `log.py show <subject>`") in your response; the integrator adds them.
Checks: show by subject, by ID in the live file and in the archive, an ID with details, an unknown subject or ID;
numbering on main and on a
branch, each table kind, a note appended, the file still passes sort_decision_log.py --check. Quick test after.

Response — Claude (worker), 2026-11-22: Done on `claude/h054-t92-log-add`.
- `tools/log.py add <kind> "<text>"`: G goes to Principles, Q to Open questions, T to the Work list, any other
  letter is a decision (needs `--subject`, alias `--area`, a unique start of the name is enough, and
  `--principles G01,G04` or `—`; unknown principles are refused). `--rel` (Replaces / or a T's Covers), `--why`
  (or a Q's Notes), `--where`, `--covers`, `--result`, `--status` (checked against the table's allowed statuses).
  On main: the next free number from `number_ids.taken` (both files and the handoff); elsewhere: the kind's next
  placeholder after those already cited on the branch (`number_ids.plan`). Dated today; inserted with
  `insert_row`, then `tidy`, so the Subjects index and Explains are regenerated. A `|` in any text is refused.
  Prints the row as written.
- `log.py note T66 "<text>"`: appends to a Work list row's last column (space-separated); a non-Work-list ID says
  where it is instead.
- `log.py show <subject|ID> [--top]`, `log.py show --top`: as asked; an ID's output starts with
  `<file>: <section> / <subject>` and its table header, then the row, its `### <ID>` Details, and the principles
  it names. An unknown subject lists the subjects; an unknown ID or subject exits 1.
- docs/decision-log.md header: a three-line paragraph on the command (after the New IDs paragraph).
- Tests: `tools/test_log.py`, LOG TESTS 50 passed, 0 failed (~0.7 s), on copies of the real log in temp git repos:
  show by subject (exact, prefix, ambiguous, unknown), --top, by ID in the live file, in the archive, with
  details, with principles, unknown; add of I, A, G, Q, T on main (next numbers) and on a branch (placeholders,
  the second counting the first); the row in the right table/group and the index; seven refusals leaving the log
  unchanged; notes (empty cell, after a result, twice, wrong table, unknown); sort_decision_log --check after;
  the command line. Quick test: QUICK 208 passed, every feature suite passes.

For the integrator at merge:
- tools/featuretest.sh (H057's, unless its discovery finds `tools/test_*.py`): `"log|python3 tools/test_log.py|LOG TESTS"`
- CLAUDE.md, in the "Before changing behaviour" paragraph, replacing "then read only your subject's group
  (`### <subject>`). Grep both files by ID": `then python3 tools/log.py show <subject> for your subject's group, and
  log.py show <ID> for one row (its Details and principles come with it). Add rows with log.py add, never by hand.`
- AGENTS.md, the same line in its decision-log step: `Read the log's top (python3 tools/log.py show --top), then
  python3 tools/log.py show <subject> or <ID>; add rows with python3 tools/log.py add <kind> "<text>" (see its --help
  text at the top of tools/log.py).`
- ARCHITECTURE.md: not changed (it doesn't map the process tools).

Resolution: merged into main by the integrator, 2026-11-22.

### H055 — T93: startup.py shows what waits on William

Author: Claude (integrator, fretchup-73) | Date: 2026-11-22 | Status: resolved | For: Claude

References: T93, P16, P19, tools/startup.py, H050 (the integrator's note, kept by hand today).

Touches: tools/startup.py, tools/test_startup.py.

Request (the log is two files now, P23: read Work list rows from docs/decision-log.md; principles G01-G12 that are
still Tentative are also waiting on William). Add a "Waiting on William" section to startup.py's report, from main: Work list rows that are Open and whose
last column says "your call" (or "William:") with no I/A/... decision ID after it; open or queued handoffs with an
"Ask William" sentence and no "William's answers" / logged ID in their response; BOARD.md notes addressed to
William. One line each with the ID and a short reason. When the integrator lock is held, a line reminding it to
check CronList for the check-ins after a clear. Checks: samples for each source, including a row that was answered
(not listed). Then shorten H050's "Waiting on William" to point at startup.py. Quick test after.

Response — Claude, 2026-11-22: Done on `claude/h055-t93-waiting-on-william`. startup.py prints "Waiting on William
(from main)": Open Work list rows whose last column leaves something as "your call" with no decision ID (I/A/U/D/M/W/P/G)
after it; Tentative principles; open or queued handoffs with an "Ask William" sentence and no "William's answers" line
or Response naming a decision after it; board notes starting "William" / "For William"; and, while the lock is held,
the CronList reminder. Two choices to check: "Your call, <date>: ..." counts as an answer (that's how the log records
one), and "William:" isn't a marker: in today's rows (T91, T93) it records what he said, so it would list them falsely.
Today it lists T65 (the question's wording) and H050's housekeeping line. H050's "Waiting on William" now points at
startup.py. 11 new checks in tools/test_startup.py (STARTUP TESTS 38/0); quick test passes (QUICK 208/0, every feature
test 0 failed). Outside Touches: H050 (asked for), this entry.

Resolution: merged into main by the integrator, 2026-11-22.

### H053 — T91: integrate.py drafts the Work list result and the board

Author: Claude (integrator, fretchup-73) | Date: 2026-11-22 | Status: resolved | For: Claude

References: T91, P16, P17 (workers put their result in the handoff; the integrator copies it to the Work list), P20
(integrate.py), P14 (BOARD.md), docs/agent-handoff.md (the response rules), AGENTS.md (Codex's copy of them).

Touches: tools/integrate.py, a new tools/test_bookkeeping.py (don't add it to the feature-test script: H049 owns
it; give the line in your response), docs/agent-handoff.md (the rules section only: one line on the Result line),
AGENTS.md and CLAUDE.md (the same line, kept in step), BOARD.md's integrator section (one line).

Changed 2026-11-22: the board's job table and moving a job to Done are now H058's (the job queue, P24); this job
keeps the Work list result. Request: today integrate.py finishes with "left for you: the Work list result and BOARD.md". Instead: (1) define one
line a response must carry, e.g. "Result: <commit>; <tests>; <what changed>", and add it to the handoff rules; (2) at
merge, append "Result (<commit>, merged <merge>): ..." to the item's Work list row (the T<n> from --status), and move
the job's board row to "Done since ..." (remove the row, add "H0NN (T<n>)" to the list, drop Notes lines naming
it); (3) show the two diffs and stop before the push for the integrator to look (a --yes to go on); a response with
no Result line leaves both for the integrator as today and says so. Checks: sample handoff + log + board in, the
three edits out; the missing-Result case; an already-recorded result isn't added twice. Run integrate.py's own
tests and the quick test; no merge of a real branch needed.

Response (Claude worker, 2026-11-22): branch claude/h053-t91-merge-bookkeeping, commit e507c6c.
- The line: a response ends with `Result: <commit>; <tests>; <what changed>` (rule added to docs/agent-handoff.md,
  AGENTS.md, CLAUDE.md, and one line in BOARD.md's integrator section).
- integrate.py step 8: for each answered entry it reads the newest Result line (before archiving the entry), finds
  the item (the --status T<n> its heading names, else the only --status, else the heading's T<n>), and after the
  merge commit appends `Result (<commit>, merged <merge>): <tests>; <what changed>.` to the row, in the live log or
  the archive (a --status Done row has moved there), as its own commit "T<n> (H0NN): Work list result, merged
  <merge>"; it prints the word diff. With --push it stops before pushing (says how to amend and push) unless --yes.
  No Result line or no item: nothing drafted, "left for you: the Work list result of H0NN (...)", and --push goes on
  as before. A row that already has `Result (<commit>` isn't added to again.
- The board half: dropped, as the 2026-11-22 change to this job says (H058's queue rebuilds the table).
- Tests: tools/test_bookkeeping.py 14/14 (parse, item choice, the row edit and its commit, the shown diff, --push
  stopping, Done into the archive, not twice, unknown item, the missing-Result case); tools/test_integrate.py 28/28;
  tools/quicktest.sh passed (QUICK 208/0, all feature tests). For the feature-test script (H049's), one line:
  `python3 tools/test_bookkeeping.py` (summary `BOOKKEEPING TESTS: N passed, M failed`).
- Architecture: no sections changed (ARCHITECTURE.md doesn't describe integrate.py).
- Open: `job.py done` could warn when a response has no Result line (job.py isn't in my Touches); BOARD.md's worker
  step 5 could name the line too (only its integrator section was mine).

Result: e507c6c; tools/test_bookkeeping.py 14/14, test_integrate.py 28/28, quick test passed; integrate.py appends a response's Result line to its Work list row in its own commit and stops before --push without --yes

Resolution: merged into main by the integrator, 2026-11-22.

### H060 — T97: follow-ups land on the integrator's list

Author: Claude (integrator, fretchup-73) | Date: 2026-11-22 | Status: resolved | For: Claude

References: P26 (William's call, 2026-11-22), T91 (H053: integrate.py already reads a response's "Result:" line;
follow its pattern: tools/integrate.py RESULT and step 8), T93 (startup.py's "Waiting on William"), P17, P24.

Touches: tools/integrate.py, tools/startup.py and tools/test_startup.py, a new tools/test_follow_ups.py (give its
feature-test line in your response: H057 owns that script), docs/follow-ups.md (new), docs/agent-handoff.md (its
rules section), AGENTS.md (the worker steps). Not CLAUDE.md (H057) or BOARD.md (the integrator's): give their lines
in your response.

Request: build P26.
1. In a response, each leftover is its own line `Follow-up: <what>` and each merge instruction its own line
   `For the integrator: <what>` (a leading "- " allowed, like Result:). Add the rule beside the Result line's.
2. At merge, before the entry is archived: integrate.py appends each Follow-up line to docs/follow-ups.md as
   `- <H0NN> (<date>): <what>` in the merge commit (a line already there isn't added twice), and prints the
   "For the integrator" lines after the merge, under "for you now:", before "left for you".
3. docs/follow-ups.md: a short header (what it is; the integrator removes a line in the commit that does it or
   turns it into a Work list item), then the open lines.
4. startup.py: a "Follow-ups (docs/follow-ups.md, from main)" section listing the open lines, after "Waiting on
   William"; "(none)" when empty.
Checks: lines parsed with and without "- "; copied once; printed instructions; a response with neither; startup's
section with lines and empty. Quick test, then the gate. End your response with a Result line, and use Follow-up
lines for anything you leave.

Response — Claude (worker, 2026-11-22): built P26 on branch claude/h060-t97-follow-ups, commit 5ae4845.
- tools/integrate.py: `follow_ups()` / `for_integrator()` read `Follow-up: <what>` and `For the integrator: <what>`
  lines (a leading "- " allowed, at line start only, like RESULT). Step 9: before the entries are archived, each
  follow-up is appended to docs/follow-ups.md as `- <H0NN> (<date>): <what>` and staged into the merge commit
  (`add_follow_ups`; the same entry and text isn't added twice, whatever its date; a missing file is made with its
  header). After the merge commit and the Result draft, the instructions print under "for you now:", before "left
  for you". A response with neither changes nothing.
- docs/follow-ups.md (new): header (what it is; the integrator removes a line in the commit that does it or turns
  it into a Work list item), then "## Open" with "(none)".
- tools/startup.py: "Follow-ups (docs/follow-ups.md, from main):" after "Waiting on William"; "(none)" when empty
  or missing on main.
- Rules: docs/agent-handoff.md (beside the Result line's rule) and AGENTS.md (the "When it's done" step).
- Decision log: P26's "Where in the code" now names the code and the test (was "Not built: T97").
- Tests: tools/test_follow_ups.py 11/11 (parsing with and without "- "; copied once, including a line already on
  main; instructions printed in place; a response with neither); tools/test_startup.py 41/41 (section with lines
  and empty, smoke order). test_bookkeeping 14/14, test_integrate 28/28. Quick test passed on 5ae4845; gate passed.
- No ARCHITECTURE.md change (tooling only). No placeholders.

For the integrator: add tools/test_follow_ups.py to tools/featuretest.sh (H057 owns it): `"followups|python3 tools/test_follow_ups.py|FOLLOW-UP TESTS"`
For the integrator: CLAUDE.md's Codex section, the "Jobs run through the queue (P24)" bullet, could add: "Leftovers go in a response as `Follow-up:` lines and merge instructions as `For the integrator:` lines; integrate.py copies the first into docs/follow-ups.md and prints the second (P26)."
For the integrator: BOARD.md's "If you're the integrator" paragraph, after "a response without one is yours to record.", could add: "It also copies Follow-up lines into docs/follow-ups.md and prints For the integrator lines under 'for you now:' (P26); clear a follow-up in the commit that does it."
For the integrator: this merge runs main's integrate.py, which doesn't read these lines yet: copy this entry's Follow-up line into docs/follow-ups.md by hand.
Follow-up: integrate.py takes an entry's ID from its file name's first dash, so an entry still named H-new-N at merge records its Result and follow-ups as "H" (number_ids runs after); seen in reading, not hit yet.

Result: 5ae4845; tools/test_follow_ups.py 11/11, test_startup 41/41, quick test and gate passed; integrate.py copies Follow-up lines to docs/follow-ups.md and prints For the integrator lines, startup.py lists open follow-ups

Resolution: merged into main by the integrator, 2026-11-22.

### H057 — T95: the feature tests find the test files themselves

Author: Claude (integrator, fretchup-73) | Date: 2026-11-22 | Status: resolved | For: either

References: T95, P07 (two kinds of test), P11 (parallel by files), P18 (the gate), H049 (the faster gate, which
changes the same scripts first).

Touches: tools/featuretest.sh, tools/quicktest.sh and tools/gate.sh (only if they repeat the list), CLAUDE.md
(the Tests section's list of feature tests), worker/CLAUDE.md, viewport/CLAUDE.md (lines that list tests or give
counts), and a first line in the test files whose runner isn't obvious from their folder.

Request: today a new test means a line in tools/featuretest.sh (name | command | summary) and in CLAUDE.md. Make
featuretest.sh find worker/test_*.py, tools/test_*.py and viewport/test_*.gd itself, run each the way its folder
says (worker: freecadcmd; tools: python3; viewport: Godot headless) unless the file's first lines say otherwise
(e.g. `# runner: python3` for worker/test_serve.py), and read the "<NAME> TESTS: N passed, M failed" line it prints
(a file that prints none fails, by name). Keep the lanes, the summary line's format and the gate's verdict as they
are; tools/test_integrate.py's gate cases must still pass. List what it found when run with --list. Then the
guides describe the kinds of test and how a file is found, without a list or counts. Checks: --list matches
today's list exactly (plus nothing missing); a new sample test file is picked up with no other edit; a file with
no summary line fails; quick test and gate.

Response — Claude (worker fretchup-e1, 2026-11-22): built T95 on branch claude/h057-t95-tests-find-themselves.
- tools/featuretest.sh no longer has a list: it globs worker/test_*.py (freecadcmd), tools/test_*.py (python3) and
  viewport/test_*.gd (Godot headless); a `runner: freecadcmd|python3|godot|none` in a file's first five lines
  overrides the folder. It reads the first `<NAME> TESTS: N passed, M failed` line; none means "<name> did not
  finish" and a failed run, as before. `--list` prints name and command without running. Names are now the file
  stem (length_input, tool_context, number_ids, integrator ... instead of length, toolctx, ids, lock); they only
  label the TIMING/FAIL lines and log files. The summary line, the parallel run and the gate are unchanged.
- First lines added: `runner: python3` in worker/test_serve.py and test_length_protocol.py; `runner: none` in
  worker/test_load.py, worker/test_native_common.py (helpers) and tools/test_check_architecture.py (unittest, run
  by the GitHub workflow, prints no summary). test_length_protocol.py now prints `LENGTH PROTOCOL TESTS:` (was
  `LENGTH PROTOCOL:`), so every file follows the one pattern.
- --list against the old hand list: all 23 found, each run the same way; new: tools/test_follow_ups.py (H060's,
  which was never added: its "For the integrator" line asking for it is now moot) and this job's test.
- Guides: CLAUDE.md's Tests bullet, worker/CLAUDE.md's and viewport/CLAUDE.md's test sections and quicktest.sh's
  header say how files are found, with no list or counts (the scenario guidance stays).
- Tests: tools/test_featuretest.py 32/32 (--list runs every pre-T95 file the same way and leaves out the three
  `none` files; in a throwaway copy a new file is picked up with no edit, `runner:` is obeyed, a silent file fails
  by name, a summary with failures fails); test_integrate 28/28; quick test (QUICK 208/0, all 25 feature tests)
  and gate passed (33 s).
- No ARCHITECTURE.md change (its row for featuretest.sh still holds). No placeholders.

Follow-up: worker/test_serve.py fails 4 of 20 (the saved/focus/save_failed replies arrive in another order) when featuretest.sh is given an output folder inside the repo (e.g. scratch/feat) under full load; passes alone, and with the default /var/folders output (what quicktest and the gate use). Timing-sensitive, seen in this job, not caused by it.

Result: d25d761; tools/test_featuretest.py 32/32, test_integrate 28/28, quick test and gate passed; featuretest.sh finds worker/, tools/ and viewport/ test files itself (runner: lines, --list), guides carry no test list

Resolution: merged into main by the integrator, 2026-11-22.

### H061 — T98: a worker session chains up to 3 jobs

Author: Claude (integrator, fretchup-73) | Date: 2026-11-22 | Status: resolved | For: Claude

References: P27 (William's call, 2026-11-22), P24 (the queue), T96 (tools/job.py), tunables DEADLINE / WATCH_POLL.

Touches: tools/job.py, tools/test_job.py, AGENTS.md (the worker steps), CLAUDE.md (the "Jobs run through the queue
(P24)" bullet), docs/decision-log.md (P27's "Where in the code" and two Tunables rows, with `log.py add`). Not
BOARD.md (the integrator's): give its lines in your response.

Request: build P27.
1. Count: job.py records, per session (take's session: CLAUDE_CODE_SESSION_ID / CODEX_* as default_session() reads
   it, or `--session <name>`), how many jobs that session has taken. A take that would be its 4th (MAX_JOBS = 3, a
   tunable) refuses: "this session has done 3 jobs: tell William it's ready for a /clear". Check, and say in your
   response, whether a /clear gives a Claude session a new CLAUDE_CODE_SESSION_ID; if it doesn't, find what does
   reset the count (and say so) rather than guessing.
2. Wait: `job.py take --wait` (WORKER_WAIT = 20 min, a tunable): when nothing is Ready for the agent, it polls every
   WATCH_POLL and exits as soon as it has taken a job (printing what `take` prints), or at WORKER_WAIT with
   "nothing came in 20 min: stopping" and a non-zero exit. While waiting it holds no job, so it doesn't beat or go
   stale; the integrator's watcher should not report it as a job. Meant to be run in the background
   (`run_in_background`), so the session is woken when it exits.
3. done's closing message says what to do next: run `job.py take --wait` in the background, unless the session is at
   its 3rd job, then "tell William you're ready for a /clear".
4. AGENTS.md and CLAUDE.md: the loop in one or two lines (take, work, done, take --wait; at most 3; stop and tell
   William after the 3rd or a wait that times out).
Checks (tools/test_job.py): the count per session and the refused 4th; a different session isn't refused; --wait
takes a job that turns Ready while it waits; --wait times out (with a short test value); done's message at jobs 1
and 3. Quick test, then the gate. End your response with a Result line; leftovers as Follow-up lines, BOARD.md
lines as For the integrator lines.

**Response** — Claude (worker, session ece2cf8a), 2026-11-22

Branch `claude/h061-t98-worker-chains-jobs`, commit e956ca4. Quick test and gate pass (JOB TESTS 64/64, 11 new).

1. Count: `take` records each distinct job a session takes in the state's `"sessions": {session: [ids]}`; a
   take past MAX_JOBS (3) refuses "this session has done 3 jobs: tell William it's ready for a /clear". A returned
   job resumed by the same session counts once. A session with no real ID (default_session's fallback, the
   agent's name) isn't counted, since every such session would share it. take prints "job N of 3".
   **/clear and the session ID, checked:** it does give a new CLAUDE_CODE_SESSION_ID. This session began with a
   /clear: its env has `CLAUDE_CODE_SESSION_ID=ece2cf8a-…`, and its transcript's first record says
   `derived-from … ee72376b-… via clear`; ee72376b is the session that took H057. (CLAUDE_CODE_BRIDGE_SESSION_ID,
   the remote-control ID, stays the same across the clear; job.py doesn't read it.) So the count starts again
   after a /clear with nothing else needed.
2. `take --wait` (take_wait): when nothing is Ready it looks again every WATCH_POLL, quietly, until it takes a job
   (prints take's full output, exit 0) or WORKER_WAIT (20 min) passes ("nothing came in 20 min: stopping", exit 1).
   A refusal (holding a job, or at 3) ends it at once. It holds no job while it waits, so nothing beats, goes
   stale, or shows in watch (watch's "queue empty for Claude" still fires, as it should).
3. done ends with the next step: `take --wait` in the background (with "job N of 3"), or at the 3rd "tell
   William you're ready for a /clear".
4. AGENTS.md (a bullet after done) and CLAUDE.md (a bullet after the P24 one) carry the loop. P27's "Where in
   the code" is filled in; Tunables: MAX_JOBS and WORKER_WAIT added, WATCH_POLL's row names take --wait (by hand:
   log.py add has no tunable kind).

Checks: the count and refused 4th; another session not refused; the fallback session not counted; --wait takes a
job that turns Ready mid-wait; --wait times out; --wait gives up at once when refused; done's message at jobs 1 and 3.

Follow-up: CLAUDE.md's "One Work list item per session where possible ... then start the next in a fresh session" (Working with William) now reads against P27's 3 jobs a session; not in this job's Touches, so left as is.
Follow-up: Codex sessions are counted only if CODEX_SESSION_ID or CODEX_THREAD_ID is set; if Codex has neither, its count never applies (it falls back to "codex"). Worth checking from a Codex session.
For the integrator: BOARD.md's worker steps: step 1's "Nothing Ready for you? It says so: tell William and stop" could become "run `python3 tools/job.py take --wait` in the background; it stops after 20 min", and step 5 could end "then take --wait for the next (at most 3 a session, P27)".

Result: e956ca4; quick test and gate pass (JOB TESTS 64/64); job.py counts jobs per session (refuses a 4th), take --wait waits up to 20 min for a Ready job, done names the next step (P27)

Resolution: merged into main by the integrator, 2026-11-22.

### H062 — T40: the model and its journal saved as one generation

Author: Claude (integrator, fretchup-73) | Date: 2026-11-22 | Status: resolved | For: Claude

References: A32 (Active: William's call, 2026-11-22, with the file arrangement), G09 (never lose work), A24 (the
journal), T79 / I54 (failed saves already shown and retried), A35 (PROTOCOL_VERSION).

Touches: worker/session.py (save, _write, _open_existing), worker/serve.py (only the open reply), a new
worker/test_generations.py, viewport/document.gd and viewport/main.gd (only to show a recovery once: a small
edit), viewport/test_document.gd, docs/decision-log.md (A32's "Where in the code"). Not docs/protocol.md or
ARCHITECTURE.md: H046 (Codex) has them; give their new text as "For the integrator:" lines (the reply's field,
the save/open steps), and the integrator puts it in the merge commit. Say so in your commit's Architecture-Impact
line.

Request: build A32. Today the .FCStd is swapped in (os.replace) and then the journal is written: a crash between
the two leaves a file and journal that don't match, and the model opens as "external" with its history behind an
undo floor.
1. Save: write `<model>.saving.FCStd` and `<model>.shopsketch.saving.json` (the journal names the new file's
   sha256 and rev); then keep the current pair as `<model>.prev.FCStd` / `<model>.shopsketch.prev.json`; then
   rename both new files into place. Until both renames are done, the .prev pair is whole. A failed save keeps
   today's behaviour (save_failed, revision held back, retried; T79).
2. Open: if the file and journal match (rev and sha256), use them (as today). If not, and the .prev pair matches
   each other, and the current file is one Shop Sketch was mid-saving (its ShopSketchRev is the journal's rev + 1,
   or the journal is newer than the file, or one of them is missing), open the newest whole pair and report it.
   A file FreeCAD changed (no Shop Sketch rev bump) is still "external", as today (A25): don't mistake an outside
   edit for a broken save. Never delete either pair while opening.
3. Report: the open reply carries `recovered: {"from": "prev", "rev": N, "why": "..."}` when it fell back; the
   viewport shows it once in the save indicator (e.g. "Recovered the last whole save (rev N)"). Bump
   PROTOCOL_VERSION on both sides (A35).
Checks (worker/test_generations.py): a normal save leaves both pairs, matching; a crash after the .FCStd rename but
before the journal's opens the .prev pair (or the whole new one, whichever is complete) and reports it; a missing
journal; a file edited by FreeCAD stays external with no recovery; the reply's field; test_document.gd shows the
message once. Quick test, then the gate. End your response with a Result line; leftovers as Follow-up lines;
anything for the merge as For the integrator lines.

**Response** — Claude (worker, session ece2cf8a), 2026-11-22

Branch `claude/h062-t40-save-generations`, commit c949c0a. Quick test and gate pass (GENERATION TESTS 26/26, new;
DOCUMENT TESTS 70, 5 new).

1. Save (`Session._write`, names from `generation()`): the new file goes to `<model>.saving.FCStd`, then its
   journal (with the new file's sha256 and rev) to `<model>.shopsketch.saving.json`; the current pair is kept as
   `<model>.prev.FCStd` / `<model>.shopsketch.prev.json` by hard link (instant, a copy where links fail); then the
   new file and the new journal are renamed into place. Since .prev is linked, not moved, the current pair stays
   whole until its file is renamed over, so there's a whole pair at every step. Checked that FreeCAD saves by
   rename, not in place, so a FreeCAD edit can't change .prev through the link. A failed save is as before (T79):
   raises, rev held back, the .saving files removed, retried.
2. Open (`recover_generation()`, before the document opens): a matching file and journal open as today. Otherwise
   it recovers only if the file looks mid-save: its ShopSketchRev is the journal's + 1, or the journal is newer, or
   one of them is missing. Then the newest pair (by rev) among {file, .saving, .prev} × {journal, .saving, .prev}
   whose journal names its file's sha256 is copied into place. A FreeCAD edit (same rev, other sha) is external
   with no recovery (A25). Nothing of either pair is deleted: a displaced file goes to
   `<model>.unmatched.FCStd` / `.shopsketch.unmatched.json`, unless the same bytes are kept elsewhere.
3. Report: `open_reply()` (serve.py) adds `recovered: {"from": "new"|"prev", "rev", "why"}`, once per session.
   "new" means it finished a save that stopped part way (the crash between the two renames); "prev" means it fell
   back to the save before. The save indicator shows "Recovered the last whole save (rev N)" or "Finished the last
   save (rev N)" until the next save lands. PROTOCOL_VERSION 3 → 4 on both sides.

Choices of mine that are worth a look: the .unmatched names; finishing a save from the new pair (better than the
.prev the request named, when that pair is whole); a missing journal with a whole .prev pair opens .prev (as the
request says), so the journal-less newer file is kept as .unmatched rather than opened external.

Commit check: committed with P28's interim line (Architecture-Impact: none - ... Architecture: lines; T100 not
built), as the integrator said, after William's P28.

Architecture: ARCHITECTURE.md § saving (~line 254): `Session.save()` writes the new FCStd and its journal under the .saving names (the journal names the new file's sha256), keeps the current pair as .prev (hard link), then renames the file and then the journal into place; a whole pair exists at every step (A32).
Architecture: ARCHITECTURE.md § saving (~line 256), replacing "the FCStd and journal are not one atomic multi-file transaction ...": opening runs `recover_generation()`: a mismatch where the file looks mid-save (ShopSketchRev = journal rev + 1, journal newer, or one missing) puts the newest whole pair in place and reports it; a FreeCAD edit (same rev, other hash) stays external with an undo floor (A25); displaced files go to the .unmatched names, never deleted.
Architecture: ARCHITECTURE.md module table, `worker/session.py` row: add "save generations and recovery (A32)" and `recover_generation`, `generation` to its entry points.
Architecture: docs/protocol.md, open reply: optional `recovered: {"from": "new"|"prev", "rev": N, "why": "..."}`, sent once when opening recovered a save that stopped part way (A32); PROTOCOL_VERSION 4.

Follow-up: worker/CLAUDE.md's "Autosave is atomic" bullet could name the generation files (.saving, .prev, .unmatched); outside this job's Touches.
Follow-up: the .unmatched files are never cleaned up (overwritten by the next recovery); fine while recoveries are rare.

Result: c949c0a; quick test and gate pass (GENERATION TESTS 26/26, DOCUMENT TESTS 70/70); saves write a .saving pair, keep .prev, then rename in; opening recovers the newest whole pair after a broken save and reports it once (A32)

Resolution: merged into main by the integrator, 2026-11-22.

### H064 — T100: ARCHITECTURE.md and docs/protocol.md are the integrator's

Author: Claude (integrator, fretchup-73) | Date: 2026-11-22 | Status: resolved | For: Claude

References: P28 (William's call, 2026-11-22; replaces his rule of 2026-11-21 in CLAUDE.md's "Working with Codex":
the agent changing a module updates the map in the same commit), P26 / T97 (Follow-up and For the integrator
lines: follow that pattern in tools/integrate.py), tools/check_architecture.py (the commit hook and the PR check).

Touches: tools/check_architecture.py, tools/test_check_architecture.py, tools/integrate.py, tools/test_follow_ups.py
(or a new test file), CLAUDE.md (the "Working with Codex" bullets on the map and the Architecture-Impact line), AGENTS.md (its architecture bullet and the "When it's done" step), docs/agent-handoff.md (the rules beside
the Follow-up rule). Not BOARD.md or the decision log (H062 has it): give BOARD.md's lines and P28's "Where in the
code" as "For the integrator:" lines.

Request: build P28.
1. A response may carry `Architecture: <what>` lines (a leading "- " allowed, like Follow-up:): what the change
   does to ARCHITECTURE.md's map or docs/protocol.md (a module, a message, state ownership, saving). At merge,
   integrate.py prints them under "for you now:" with the For the integrator lines, marked as map changes, and
   says "write these into ARCHITECTURE.md / docs/protocol.md before pushing" when there are any.
2. tools/check_architecture.py: on a branch (not main), a commit touching watched code passes with
   `Architecture-Impact: in the handoff - H0NN` (or H-new-N) when that handoff file on the branch has at least one
   Architecture: line; without the lines it fails, saying to add them. `Architecture-Impact: none - <why>` stays as
   it is. On main (the merge commit or the integrator's follow-up commit), the check is as today: the map changes
   in the same commit, or none with a reason. Keep the PR workflow working (--range); say what it checks now.
3. Workers don't edit ARCHITECTURE.md or docs/protocol.md: CLAUDE.md, AGENTS.md and the handoff rules say so in a
   line or two, and that the integrator writes the change at merge. Keep "the reviewer checks prose against code".
Checks: lines parsed with and without "- "; printed at merge with the reminder; none means no reminder; the check
passes a branch commit naming a handoff with Architecture lines, fails one naming a handoff without them, and on
main still wants the map. Quick test, then the gate. End your response with a Result line; leftovers as Follow-up
lines; anything for the merge as For the integrator lines.

**Response** — Claude (worker, session ece2cf8a), 2026-11-22

Branch `claude/h064-t100-map-is-the-integrators`, commit 49a00b1. Quick test and gate pass;
test_check_architecture.py 11/11 (6 new), FOLLOW-UP TESTS 19/19 (8 new).

1. Architecture lines: `integrate.architecture(text)` reads `Architecture: <what>` lines (a leading "- " allowed;
   a mention mid-line isn't one). Changed from the request, at the integrator's ask (seen merging H062, where the
   merge commit on main was refused without the map): with any such lines and no --impact, integrate.py stops
   after the gate, **before** the merge commit, with the merge staged. It prints the lines under "for you now:"
   marked `map:` with "write these into ARCHITECTURE.md / docs/protocol.md ... then: python3 tools/integrate.py
   --continue --as <name> [--push]". `--continue` refuses (and shows the lines again) until ARCHITECTURE.md or
   docs/protocol.md is changed in the index (or --impact is given), then does the commit, job.merged(), the
   Result drafts, the For the integrator lines and the push. The state sits in git's common folder
   (`shopsketch-integrate.json`) until the commit lands. A merge commit the hook refuses (watched code, no map,
   no --impact) is left the same way and resumes with --continue. No Architecture lines: no stop, no reminder.
2. check_architecture.py: on a branch (the current branch isn't main, or --range), a commit touching watched code
   passes with `Architecture-Impact: in the handoff - H0NN` (or H-new-N) when docs/handoff/H0NN-*.md in the
   commit's index (or at the range's head) has an Architecture: line; without one it fails, saying to add them.
   `none - <why>` is as before. On main the "in the handoff" form is refused: the map changes in the same commit,
   or none with a reason. The PR workflow (--range) is unchanged and checks a PR as a branch; its docstring says
   so. Worth knowing: a worker writes its Architecture: lines into the entry in the same commit as the code (or
   earlier), not only in the final response.
3. CLAUDE.md (the two Working with Codex bullets), AGENTS.md (its architecture bullet, "architecture sections
   changed" → Architecture: lines), docs/agent-handoff.md (a rule beside the Touches rule; "a line in
   ARCHITECTURE.md" dropped from the hot spots). "The reviewer checks prose against code" is kept in CLAUDE.md.

For the integrator: P28's "Where in the code": tools/check_architecture.py (IN_HANDOFF, handoff_reader; on a branch only), tools/integrate.py (architecture(), stops before the merge commit with the merge staged; --continue: resume(), commit_and_finish()); checks: tools/test_check_architecture.py, tools/test_follow_ups.py. T100
For the integrator: BOARD.md's integrator section: after "merge what's good with `python3 tools/integrate.py <branch> --as <name> --push`", add "(a job with Architecture: lines stops with the merge staged: write the map, then `integrate.py --continue --as <name> --push`, P28)".
For the integrator: this merge itself has no Architecture lines (tools/ isn't watched), so it goes straight through.

Follow-up: CLAUDE.md's "Shared hot spots (the decision log's Work list, the handoff, ARCHITECTURE.md tables, viewport/main.gd)" line still names ARCHITECTURE.md tables as a hot spot; outside the bullets this job was given.

Result: 49a00b1; quick test and gate pass (architecture guard 11/11, FOLLOW-UP TESTS 19/19); the commit check takes "Architecture-Impact: in the handoff - H0NN" on a branch, and integrate.py stops a merge with Architecture: lines before its commit for the map, resumed with --continue (P28)

Resolution: merged into main by the integrator, 2026-11-22.

### H046 — T82: the Line tool, closed outlines and split faces

Author: Claude (integrator) | Date: 2026-11-22 | Status: resolved | For: Codex

References: T82, I51 (lines split faces; Push/Pull acts on the region under the cursor; one op to FreeCAD), I49,
A34 (a new tool is one file), A35 (bump the protocol version for a new op), P21 (the viewport's region must be
tested against FreeCAD's result), A03; Circle (H041, docs/handoff-archive.md) for the pattern: profiles, exact
sketches, push of a profile.

Touches: viewport/tools/line_tool.gd (new), worker/line.py (new, a LineActions class), viewport/regions.gd (new:
the region finding, pure functions) and viewport/test_regions.gd (new, headless; give its feature-test line in your response: H049 owns that script
and the integrator adds it),
viewport/tools/push_tool.gd and worker/push.py (pushing a region), viewport/presenter.gd (line drafts, the region
overlay), viewport/inference.gd (snapping to lines), viewport/test_tools.gd, viewport/tests/quick/registry.gd,
worker/scenario/99_op_registry.py (the pinned lists), viewport/tests/quick/line.gd and worker/scenario/NN_lines.py
(new), viewport/tools/CLAUDE.md, docs/protocol.md, ARCHITECTURE.md. Not viewport/tests/harness.gd,
quick_runner.gd or tools/quicktest.sh (H045).

Request, in two stages (a commit and a gate run each):
1. Lines and closed outlines: the Line tool draws on the ground or a face, snapping like Rectangle and Circle;
   lines are kept as drawings (an op each, undoable, saved) and change no solid; lines that close a loop make a
   face that Push/Pull turns into a board, a cut or a boss, like a rectangle.
2. Split faces (I51): a line across a face splits it into regions; Push/Pull over a face finds the region under the
   cursor from the face's outline and every line on it (regions.gd), previews it at once, and sends one op with
   that region's closed outline. Test the awkward cases in test_regions.gd: crossing lines, a line ending partway
   (it doesn't split), a line ending exactly on an edge or a corner, two lines meeting on an edge, near-overlaps.
   P21: compare the predicted region with the face FreeCAD made (area and bounds) in the scenario.
William's answers (2026-11-22, logged as I58): the key is L; the gesture is the click-click chain (each click
ends a line and starts the next; Esc or clicking the start point ends it; a typed length sets the current line) plus
press-drag-release for a single line (I43's rule). Build on ToolContext (H051, merged 9581352; docs/specs/T88-tool-interface.md) from
the first file: no m.* in line_tool.gd, and uses_main() returns false. What ctx lacks for Line (loose lines,
regions), add to its capability with a test in test_tool_context.gd and say so. Push/Pull hasn't moved to the context yet when you start (it moves after
Line): change push_tool.gd as little as the region push needs.

Response — Codex, 2026-11-22:

Ready on `codex/h046-t82-lines-split-faces`. Stage 1: 47c3c2f (Line and closed outlines); stage 2: 0c1c9d3 (split regions). Main's later documentation commits are merged into the branch. Follows I49/I51/I58, A03/A34/A35 and P21. No new decisions or placeholders; nothing open.

Verification: stage-one post-commit gate passed (219 UI quick checks, all feature tests and full test, 48 s). Stage-two gate passed (232 UI quick checks, all features and full test, 42 s), zero known failures. This includes 59 pure region checks, 528 native scenario checks, 71 ToolContext checks and the real gesture tests. Native scenarios execute the actual Godot region finder and compare its predicted area, bounds and volume against FreeCAD for crossings, dangling ends, edge/corner meetings, overlaps, near-overlaps, holes, concavity, tilted/reversed planes and curved boundaries. UI checks cover chains, drag release, fractional typed lengths, snapping, Esc, undo/redo, quadrant edits, loops/pockets, annular previews and exact circular-segment volume. Drawing-only work and solids both survive reopening. Region lookup measured 1.8 / 5.1 / 16.9 ms for grids of 10 / 20 / 40 lines (scratch/region-bench-after.log).

Additional necessary paths beyond the original Touches: viewport/tool_context.gd and test_tool_context.gd (explicitly requested capability extension); viewport/main.gd (redo and region rejection dependencies); viewport/measure_box.gd (Line typed lengths); worker/serve.py (matching protocol version). tools/number_ids.py also needed a five-line root check: a temporary fixture under scratch must enumerate itself rather than inherit its ancestor repository's tracked files; the existing feature test exposed this under P25. These were declared in chat before editing. ARCHITECTURE.md and docs/protocol.md were not edited, per P28.

Architecture: Add viewport/tools/line_tool.gd, the first context-only tool (uses_main false, no Main access), L / Line / Line (L), order 37. It constructs a saved line op per segment, supports click chains and single press-drag-release, typed lengths along the cursor direction, Esc and closing at the start. ToolContext.view.register_line passes a deep copy; model.lines_on returns filtered snapshots with ids. Presenter owns loose_lines, saved segment drafts, optional polygon profiles and open/undo/redo reconstruction. Inference snaps to line endpoints, midpoints and edges. New files are discovered by the existing tool/op/test registries.
Architecture: Add worker/line.py LineActions: op_line, polygon_face, region_face and native_region. Each segment is a fully constrained native Sketcher line tagged SSLineId, grouped in Lines; a simple closed outline also produces a Part::Feature profile tagged RectId and SSRole=line-profile. Existing r counters and target.rect support polygon profiles. Self-crossing chains remain drawings, with their bounded cells found by the viewport. Native region pushes create a face base and Part::Extrusion, then the existing join/cut or separate board, including definition-frame conversion on linked/mirrored stock.
Architecture: Wire protocol increments 4 to 5 on both sides. New line payload: id, type=line, existing Plane, end (world-mm 3-vector), optional outline (ordered world-mm polygon, no repeated final vertex), optional snap_start/snap_end booleans. These flags preserve explicit geometry-snap intent across the existing 0.1 mm difference between native-edge and face tessellations; unsnapped free endpoints retain 0.001 mm tolerance. Line anchors and all later points are projected onto the source geometry plane, avoiding physics-hit float offsets.
Architecture: New pure viewport/regions.gd splits planar intersections, welds at native tolerance using spatial buckets, cancels subdivided internal boundaries, prunes dangling branches and walks bounded half-edges. It classifies holes, bridges/triangulates them, and finds the cell containing the cursor. Presenter.drawn_region builds the hover region; Push/Pull previews it immediately and sends optional target.region={outline, holes, normal, lines}, with full-precision world-mm points and saved line ids. With target.face or target.rect it must fit that source; alone it is free closed stock. Main's rejection dependencies include region.lines. A changed region bypasses whole-stock resizing and plane fits; an unsplit source keeps its original exact profile/stock path.
Architecture: Worker validates coplanarity, simple outlines, holes, normal, source containment and drawing references. Straight boundaries extrude the submitted polygon. For curved source edges, native_region refines the already-selected preview cell with native face slices along saved drawing lines, preserving exact arcs; symmetric area discrepancy is bounded by the existing export deflection/circle preview approximation. One push_pull op still owns the edit and undo transaction. test_regions.gd is auto-discovered; scenario/99_regions.py exports its actual predictions for native comparisons.

For the integrator: Apply the Architecture lines to the responsibilities, native-model/state and protocol sections at merge (P28); retain/renumber wire version 5 per A35. Update the I49/I51/I58 code-location cells to the implemented T82 paths. No featuretest.sh registration is needed after H057.

Result: 0c1c9d3; both stage gates pass (219 then 232 UI checks, all feature tests and full tests, zero known failures); added context-only Line chains and saved drawings, closed polygon profiles, immediate split-face regions with holes, and native region Push/Pull preserving exact curved boundaries.

Resolution: merged into main by the integrator, 2026-11-22.

### H063 — T64: watch the model file and reload FreeCAD's saves, with a wave

Author: Claude (integrator, fretchup-73) | Date: 2026-11-22 | Status: resolved | For: Claude

References: A36 (William's call, 2026-11-22: what happens when FreeCAD saves while actions are pending), Q19
(decided: watch, reload, wave, undo stops at the FreeCAD change), A25 (journal adoption, undo floor; the worker
already reloads a file replaced on disk: Session.disk_sig / file_sig), A32 and H062 (save generations: build on
them), T65 (the re-apply offer: next, not this job), W01-W09 (the wave), CLOSE_WAIT_S (the same kind of wait),
A35 (PROTOCOL_VERSION).

Touches: worker/session.py, worker/serve.py, a new worker/test_outside_save.py (and worker/scenario/NN_outside_save.py,
new, if it fits), viewport/document.gd, viewport/main.gd (small: the dialog and the reload's wave), viewport/test_document.gd,
a quick-test step (viewport/tests/quick/outside_save.gd, new; if the
quick-test or scenario registries' pinned lists must change, H046 (Codex) has those files: give the lines as "For the
integrator:" lines), docs/decision-log.md (A36's and T64's "Where in the code",
a Tunables row with `log.py add`). Not docs/protocol.md or ARCHITECTURE.md (P28: the integrator's):
write what your change does to them as "Architecture:" lines in your response.

Request: build T64 as A36 says.
1. Watch: the worker notices when the model's file changes on disk and the change isn't its own save (not its rev,
   not its sha256), while the window is open, without waiting for the next sync (a cheap stat check on its
   select loop's timeout is enough; say what you chose). It tells the window (a new event).
2. Nothing pending: reload the file (as A25 does), show the changed boards with the wave, and undo stops at the
   FreeCAD change.
3. Actions pending: stop autosaving that model at once; wait up to OUTSIDE_SAVE_WAIT (10 s, a tunable) for them to
   land; then reload as in 2. If they don't land: the dialog "FreeCAD saved this model while Shop Sketch was busy"
   with "Use FreeCAD's version" (reload; the unfinished actions stay in the journal marked dropped, for T65) and
   "Keep Shop Sketch's" (copy FreeCAD's file aside as <model>.freecad-<time>.FCStd first, then save over it).
   Both versions always survive on disk. If the worker was stuck or crashed, log it in worker.log and say so in
   the dialog.
4. Autosave resumes once the choice is made (or after the reload in 2).
Checks: an outside save with nothing pending reloads and reports the changed bodies; one with pending actions that
land in time; one where they don't (each choice: files on disk afterwards, the journal's dropped actions); no
autosave writes over the outside save meanwhile; the copy-aside name; the quick-test step (an outside edit to the
open model, then the wave). Quick test, then the gate. Bump PROTOCOL_VERSION on both sides (A35). End your
response with a Result line; leftovers as Follow-up lines; anything for the merge as For the integrator lines.

Response — Claude (worker, branch `claude/h063-t64-reload-freecad-saves`), 2026-11-22: built T64 as A36 says.

1. Watch: the worker stats each open model's file every WATCH_S (0.25 s) on its select loop's timeout (one stat
   per model; nothing reads the file unless its mtime/size moved). A change counts once it has held still for one
   look (FreeCAD half-way through writing isn't reloaded) and its sha256 isn't the bytes Session last read or wrote
   (a touch or a copy back isn't an outside save). Every save also looks just before writing, without the wait,
   so even an autosave due in the same moment never goes over FreeCAD's file. The window gets `outside_save`.
2. Nothing pending: the window sends `reload` at once; the worker reopens the file, writes bodies.json and says
   which boards changed (box, volume, area, wood, hiding) and which went; the window takes its ops, puts the
   wave over the changed boards and says so in the status line; undo stops there (the journal now keeps the
   floor, so it stops there in the next session too).
3. Pending: the worker holds the model (no autosave) as soon as it sees the save; the window waits for its syncs
   to land (OUTSIDE_SAVE_WAIT, 10 s, viewport/main.gd, a Tunables row) and then reloads. Not in time: the dialog
   "FreeCAD saved this model while Shop Sketch was busy", Use FreeCAD's version / Keep Shop Sketch's, naming why
   (didn't land, the worker hasn't answered: may be stuck, the worker stopped), logged in worker.log.
   Use FreeCAD's version reloads (the late sync answer then counts for nothing). Keep Shop Sketch's copies
   FreeCAD's file to `<model>.freecad-<YYYYmmdd-HHMMSS>.FCStd` and saves ours over it.
   Which actions are "dropped": every action the file's revision didn't hold, landed in time or not. FreeCAD
   saves the revision it had open (its ShopSketchRev), so actions Shop Sketch saved after FreeCAD opened the file
   are missing from it too. The worker remembers each revision's op list (the last 50; else the .prev journal;
   else none, so all are dropped). They go in the journal as `dropped: [{op, after_rev, at}]` for T65.
4. Autosave resumes after the reload or the choice. Closing (flush, bye, quit) while held, with actions unsaved,
   keeps both the same way as Keep Shop Sketch's; with nothing unsaved FreeCAD's file just stays.
   A worker that stops before the reload: the journal got `outside_sha256` the moment the save was seen, so a new
   worker opens FreeCAD's file as an outside edit (A25) instead of taking it for a save of ours that stopped part
   way (A32's "journal newer" rule would otherwise put our .prev pair back and move FreeCAD's file to .unmatched).
   The window sends no sync to a new worker while the choice is open.

Checks: worker/test_outside_save.py (25: nothing pending, landed in time, each choice's files on disk and the
journal's dropped list, no autosave over the outside save, one copy per choice, the copy-aside name, a flush while
held, an older revision saved in FreeCAD, an undo since that revision, a new worker after a crash);
viewport/test_document.gd (+19: waiting, the reload's ops with actions drawn meanwhile on top, the forced reload,
keep_mine, no sync to a worker back after a crash); quick-test section outside_save (an earlier revision of the open
model put back on disk: reloaded, the board it brings back waves, the delete is dropped, undo stops; the dialog's
reason and Keep Shop Sketch's copy). PROTOCOL_VERSION 5 on both sides.

Architecture: docs/protocol.md, worker → window event `{"cmd": "outside_save", "model", "rev" (the file's ShopSketchRev), "unsaved": bool}`: FreeCAD saved the open model (A36); the worker holds it (no autosave writes over the file) until the window answers.
Architecture: docs/protocol.md, new request `{"cmd": "reload", "model", "outdir", "seq"}` → the open reply's fields with `"cmd": "reload"`, plus `changed` / `removed` (board ids whose box, volume, area, wood or hiding differ; gone), `dropped` (ops the file didn't hold) and `outdir` (bodies.json written there).
Architecture: docs/protocol.md, new request `{"cmd": "keep_mine", "model", "outdir"?, "seq"}` → `{"ok", "cmd": "keep_mine", "model", "aside", "rev"}`: FreeCAD's file copied to `<model>.freecad-<YYYYmmdd-HHMMSS>.FCStd` (`-2`... if taken), then Shop Sketch's saved over it. flush / bye / quit of a held model with unsaved actions does the same; their `saved` entries carry `aside`. PROTOCOL_VERSION 5.
Architecture: docs/protocol.md, journal fields: `floor` (undo stops here: ops before it can't be taken back, A25; kept across saves and sessions), `dropped` ([{op, after_rev, at}]: actions an outside save didn't hold, for T65), `outside_sha256` (written the moment an outside save is seen; opening a file with that sha opens it external instead of recovering, A32).
Architecture: ARCHITECTURE.md § saving: serve.py watches each owned model's file every WATCH_S (0.25 s, on the select loop: one stat per model); a changed (mtime, size) must hold still for one look and differ from the bytes Session last read or wrote (`file_sha`) to count; save_pending also looks just before each save (no settling) and skips a held model, so no autosave goes over FreeCAD's save. `Session.reload_outside()` reopens the file, keeps the ops the file's revision held (`rev_counts`, else the .prev journal, else none), moves the rest to `dropped`, sets the undo floor there and writes the journal naming FreeCAD's file. `Session.save()` no longer resets the undo floor to 0.
Architecture: ARCHITECTURE.md, viewport document controller (document.gd, A31): owns the outside-save state (`outside`, `outside_seq`, `dropped`): `on_outside_save` reloads at once or emits `outside_waiting`; the idle branch of `on_sync_reply` sends the reload once everything has landed; while a reload is out, syncs wait (`in_flight`) and actions drawn meanwhile go on top of the reloaded ops; `on_link_up` sends no sync while the choice is open. Signals `outside_waiting`, `reloaded`, `kept_mine`. main.gd: `OUTSIDE_SAVE_WAIT`, the dialog (`_ask_outside`, `_outside_choice`), `_log_worker` (a line in worker.log), `_on_reloaded` (clears the presenter's remembered states, waves over `changed`).
Architecture: ARCHITECTURE.md module table, `worker/session.py` row: add outside saves (A36): `outside_sig`, `same_bytes`, `mark_outside`, `reload_outside`, `copy_outside_aside`, `aside_name`; `worker/serve.py` row: the file watch and the `reload` / `keep_mine` commands.

Follow-up: log.py add can't add a Tunables row (no kind for it), so OUTSIDE_SAVE_WAIT's and WATCH_S's rows were added to the Tunables table by hand.
Follow-up: Session.sync() rebuilds from the op list when an undo goes past FreeCAD's 20 steps, and that rebuild loses a FreeCAD change below the undo floor (it starts from an empty document); it should start from the file the floor came from. Before T64 this was already true after opening an externally edited file.
Follow-up: recover_generation() takes a FreeCAD save of an older revision for a save of ours that stopped part way (A32's "journal newer than the file" rule) when no worker saw it happen (e.g. FreeCAD saved while Shop Sketch was closed); FreeCAD's file goes to .unmatched (not lost, but not what opens). Ask William whether that rule should stay.
Follow-up: after a crash during an outside-save wait, "Keep Shop Sketch's" on the new worker saves FreeCAD's file plus the window's actions on top (the new worker loaded FreeCAD's file); the aside copy is still made.
For the integrator: worker/CLAUDE.md "Sync, undo, saving" still says "An outside edit sets an undo floor; merging is stage 2 (A25, Q19)": make it "The worker watches the open model's file; FreeCAD's save is reloaded with the wave, or kept beside ours (A36, T64); the journal keeps the undo floor and dropped actions." (the guide wasn't in this job's Touches).
For the integrator: H046 has the quick-test registry: the new section viewport/tests/quick/outside_save.gd isn't pinned in QUICK_LANES (it joins the shortest lane by itself; it takes about 1.2 s).

Result: 50c5a66; worker/test_outside_save.py 25/25, test_document.gd 89/89, quick test 216/216 (section outside_save), gate passed; the worker watches the open model file and holds it on a FreeCAD save; the window reloads it with the wave, or after OUTSIDE_SAVE_WAIT asks Use FreeCAD's version / Keep Shop Sketch's (FreeCAD's file copied aside); dropped actions and the undo floor kept in the journal (A36)

Resolution: merged into main by the integrator, 2026-11-22.
