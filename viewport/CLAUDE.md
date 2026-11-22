# viewport/: the Godot side

Godot 4.6, Compatibility renderer (on a Mac it draws through Metal; Forward+ hatches edges on thin faces, Q5).
Everything you see and touch: tools, instant drafts, the confirmation wave, typed values, panels. FreeCAD is the
evaluator; this side predicts. The top-level CLAUDE.md has the overview; ARCHITECTURE.md the module map and
protocol (update it in the same commit when you change either). Tools have their own guide in `tools/CLAUDE.md`.

## Files
- `main.gd` (~2,000 lines; split in T39 / T41): setup and UI, materials and mesh helpers (`_tri_mesh`, `_lines`),
  worker process and lifecycle, rejection bookkeeping, typed input (`apply_vcb`), input dispatch, model switching.
- `document.gd` (T39, A31): the document controller, `m.doc`. Owns the op list, counters, `seq` / `in_flight` /
  `dirty`, which reply counts, confirmed ids, undo floor, redo stack, open / reset, save revisions; reports by
  signals and knows nothing of meshes. main.gd forwards those names (`m.ops`, `m.seq`, ...) to it. Undo, redo and
  removal go through it (`op_removed` tells main to take away what an op drew).
- `selection.gd` (T41, A33b): selection and context, `m.sel`. Owns `selection`, `context`, each board's assembly /
  row / family / array / mirror plane, the hidden/deleted sets, `show_hidden`, `hover_body`; deletion (T34, I43); the queries (`unit_of`,
  `in_context`, `is_hidden`, ...) and the actions that add hide / assembly / unlink ops. Draws nothing: main.gd
  and the presenter draw on its signals; main forwards the old names.
- `presenter.gd` (T41, A33b): geometry on screen, `m.pres`. Owns `body_tris` / `body_verts` / `body_edges` /
  `body_cuts`, drafts and rects, confirmed board nodes, remembered states, waves (`step_waves` each frame) and the
  selection / context highlights. Draws with main's helpers through `m` (like the tools); main forwards the old
  names (`m.body_tris`, `m.drafts`, `m._begin_wave`, ...). main routes the document's signals to it.
- `inference.gd`: the one snapping engine (pick; endpoint > midpoint > on edge; axis inference). Every tool uses it.
- `tools/`: one object per tool (see its guide). `property_panel.gd`: the Properties panel (T46, I36).
- `units.gd`: lengths. `evaluate_length` / `evaluate_pair` give FreeCAD's answer for a typed length at once (a
  port of `worker/length_input.py`; what it declines goes to FreeCAD); `format_length` for showing lengths.
- `worker_client.gd`: TCP framing, reconnect. `tests.gd`: small test-mode dispatcher; `tests/harness.gd`: shared input, timing and assertions;
  `tests/suites/`: one script per UI suite; `tests/quick/`: one script per quick section (T51).
- Shaders: `confirm_wave*.gdshader` (the wave), `overlay.gdshader` (highlights on faces), `line.gdshader` /
  `line.gdshaderinc` (lines), `wood.gdshader` (painted boards).

## How it works
- Every action is drawn at once as a draft (the tool builds the op, appends it to `ops`, draws, starts the wave,
  calls `sync()`); FreeCAD catches up and the real mesh replaces the draft (W01–W09). Never block input on FreeCAD.
- Confirmed boards: the worker writes `bodies.json` plus `meshes/<board>-<key>.bin` (triangles, normals, FreeCAD's
  exact edges and corners, as PackedVector3Array bytes); `presenter.gd` `apply_confirmed` builds only files it
  hasn't seen (A29). The last 40 confirmed states are remembered (`_remember_state`), so undo shows at once (A28).
- Redo (T31, ⇧⌘Z): `undo()` puts the action on `redo_stack` with the ops key it left; `redo()` puts it back only
  while `ops` still has that key, so any new action, amend or rejection ends redo (linear until U01). Esc cancels
  the tool's gesture (`in_gesture()`) first, then the selection, then the assembly you're in.
- Worker (W13): a window uses the worker on port 7878 if `hello` reports the same hash (`_worker_identity()`: every
  worker .py except tests), else starts one there (a different version gets a private worker on a free port). Each
  window has its own FreeCAD document; a model is open in one window at a time (`already_open`, the owner gets
  `focus`; a window launched on a taken model closes itself). Closing a window sends `bye`. If the worker dies,
  whichever window notices restarts it. File > New Window (⌘⇧N). Files beside the viewport: `_beside_project()`.
- Typed values: `apply_vcb` keeps Move's count syntax (`3x`, `/3`) for the tool; a length is worked out by
  `units.gd` at once and handed to the tool in mm; only what it declines waits for a `length` reply.
- Context: from outside, a board stands for its assembly or array row (`unit_of`); double-click with Select enters
  one (`enter_context_of`, the rest greyed and unpickable), Esc leaves. Inside an entered array a moved copy leaves
  the row (op `"detach": true`, I32); a board pushed out inside an assembly joins it (op `"assembly"`). Inside a
  mirror group the plane shows and moving the copy moves the original reflected.
- Selection (T34): Select drags right for enclosed units, left for crossing units; Shift adds. Move on a selected board uses the whole selection (copy/mirror too); a copy of every board of an assembly makes a new assembly (I44, `_whole_assemblies`), 3x / /3 of one is refused (T57). Delete / Backspace (I45): once the measurements box is clicked or typed in (`typing`), they edit it, even emptied, until a click in the view or a new selection; otherwise they delete in one op, in any tool: mid-move what's being moved, else the selection (Edit > Delete has no menu key). Deleted IDs follow ops immediately, suppressing confirmed and draft collisions even with Hidden geometry on. Deleting an entered row's original promotes a survivor and keeps the entered context with it (I43). Cached undo/redo states restore relationship metadata as well as geometry.
- Hide (T28, I37): H hides the selection (else the board under the cursor), Shift+H unhides all; Edit > Unhide
  selected / last; View > Hidden geometry ghosts hidden boards (pickable, to unhide one). The hidden set comes
  from `ops` (`hidden_boards()`, applied in the presenter's `apply_context`), so hide and its undo show at once; `is_hidden`
  boards aren't picked or snapped to.
- Wood: painted boards use `wood.gdshader` (no UVs: laid out from world position along grain / across; end grain
  mirror-repeated). Board nodes are cached by mesh + material + grain, so a repaint rebuilds the look.
- Units: model space is Z-up millimetres; Godot is Y-up metres (`m2g` / `g2m`).
- Tools and tests `preload("res://main.gd")` for typing; main.gd `load()`s them at runtime (no preload cycle).
  No `class_name`: Godot run from the command line doesn't register new global class names.

## Rules
- Overlays lying on faces use `overlay.gdshader` (depth bias in the shader). Never offset node transforms: that
  broke rectangle picking. Lines get the same bias in `line.gdshaderinc`; the grid has none and draws first.
- Never draw with PRIMITIVE_LINES: 1-pixel GL lines get no anti-aliasing and vanish. Use `_lines()` (W12).
- Godot 4.6 delivers an injected gesture (Input.parse_input_event) twice per frame; `_repeat_gesture` drops the copy.
- Test hooks (`delay_ms`, forced rejection, `--*test`) are for testing only (P02).

## Tests
- The quick test is `tests/quick_runner.gd` (`--quicktest`, run by `tools/quicktest.sh`): every feature once,
  each step checking its own answer. Each section is `tests/quick/<name>.gd` with a `run()` method;
  `QUICK_LANES` in quick_runner.gd deals them into the three windows the script runs side by side
  (`--quick-lane=N`, T49; keep the lanes about equal in time). A new feature: a step in a
  section, or a new section file listed in a lane. Its sections share one model (`_fresh` clears
  the window and syncs the section's ops; `own_file` for model switching); in quick mode drags take 2 frames, waves
  get 2 frames' pad and frames skip the physics tick (T48: 26 → 14 s). It prints where its time goes (`QUICK timing`).
  `--fast` gives any suite that pace but keeps the physics tick (picking a draft drawn a moment ago needs one: the
  face test's draw-on-a-draft step misses without it). Not for recordings (P03).
- Recorded suites (`--facetest --movetest --mirrortest --infertest --holetest --zfighttest`) are compared with
  `tests/reference/` by the full test; targeted: `--undotest --snaptest --recttest --shelltest --jointest
  --rejecttest`. Visual only: `--linetest`, `--zfighttest`; timing `--perftest`; `--heavytest --model=<file>`.
- `test_document.gd` (headless, in the feature tests): the document controller with a stand-in client: rapid
  edits coalesce, stale and dirty replies are ignored, reconnect resends, a switched model ignores the old reply,
  undo floor, redo.
- `test_selection.gd` (headless, in the feature tests): selection.gd with a stand-in document: what a board stands for
  outside and inside, entering and leaving, the hidden/deleted sets following ops, hide / delete / assembly / unlink ops and context following original promotion. Quick-test `selection` covers boxes, Shift-click, multi-board move/copy/count amendments/mirror/delete, undo/redo, tool-first grabs after undo and deletion inside an entered array.
- `test_units.gd` (`Godot --headless --path viewport --script res://test_units.gd`, 114): the parser, and the local
  evaluator against FreeCAD's answers in `tests/length_cases.json`.
- Tests use a private worker on a port it picks itself and reports in a file (T47); `--port=N` uses an outside
  one; `--shared-port=N` tries sharing next to a running app.
- Suites drive the UI with a simulated cursor; in test mode mouse events that aren't at it are ignored (the real
  pointer over a test window used to scramble runs). Run suites on their own port (not 7878: the app's worker may
  hold it), one at a time per worker (the full test's four lanes each have their own), and don't name a results folder after a viewport copy. Test runs at
  the same time each own their worker ports (T47).
