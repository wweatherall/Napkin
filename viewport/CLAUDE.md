# viewport/: the Godot side

Godot 4.6, Compatibility renderer (on a Mac it draws through Metal; Forward+ hatches edges on thin faces, Q5).
Everything you see and touch: tools, instant drafts, the confirmation wave, typed values, panels. FreeCAD is the
evaluator; this side predicts. The top-level CLAUDE.md has the overview; ARCHITECTURE.md the module map and
protocol (update it in the same commit when you change either). Tools have their own guide in `tools/CLAUDE.md`.

## Files
- `main.gd` (~2,300 lines; its split is T39 / T41): setup and UI, worker link and lifecycle, `sync`, drafts, waves,
  remembered states, selection and context, typed input (`apply_vcb`), input dispatch, model switching.
- `inference.gd`: the one snapping engine (pick; endpoint > midpoint > on edge; axis inference). Every tool uses it.
- `tools/`: one object per tool (see its guide). `property_panel.gd`: the Properties panel (T46, I36).
- `units.gd`: lengths. `evaluate_length` / `evaluate_pair` give FreeCAD's answer for a typed length at once (a
  port of `worker/length_input.py`; what it declines goes to FreeCAD); `format_length` for showing lengths.
- `worker_client.gd`: TCP framing, reconnect. `tests.gd`: every scripted suite (added only in test mode).
- Shaders: `confirm_wave*.gdshader` (the wave), `overlay.gdshader` (highlights on faces), `line.gdshader` /
  `line.gdshaderinc` (lines), `wood.gdshader` (painted boards).

## How it works
- Every action is drawn at once as a draft (the tool builds the op, appends it to `ops`, draws, starts the wave,
  calls `sync()`); FreeCAD catches up and the real mesh replaces the draft (W01–W09). Never block input on FreeCAD.
- Confirmed boards: the worker writes `bodies.json` plus `meshes/<board>-<key>.bin` (triangles, normals, FreeCAD's
  exact edges and corners, as PackedVector3Array bytes); `_apply_confirmed` builds only files it hasn't seen
  (A29). The last 40 confirmed states are remembered (`_remember_state`), so undo shows at once (A28).
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
- Hide (T28, I37): H hides the selection (else the board under the cursor), Shift+H unhides all; Edit > Unhide
  selected / last; View > Hidden geometry ghosts hidden boards (pickable, to unhide one). The hidden set comes
  from `ops` (`hidden_boards()`, applied in `_apply_context`), so hide and its undo show at once; `is_hidden`
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
- The quick test is `tests.gd` `_run_quick_test` (`--quicktest`, run by `tools/quicktest.sh`): every feature once,
  each step checking its own answer. Each section is a `_q_<name>()`; `QUICK_LANES` deals them into the three windows
  the script runs side by side (`--quick-lane=N`, T49; keep the lanes about equal in time). A new feature: a step in a
  section, or a new section listed in a lane and in the `match` in `_run_quick_test`. Its sections share one model (`_fresh` clears
  the window and syncs the section's ops; `own_file` for model switching); in quick mode drags take 2 frames, waves
  get 2 frames' pad and frames skip the physics tick (T48: 26 → 14 s). It prints where its time goes (`QUICK timing`).
  `--fast` gives any suite that pace but keeps the physics tick (picking a draft drawn a moment ago needs one: the
  face test's draw-on-a-draft step misses without it). Not for recordings (P03).
- Recorded suites (`--facetest --movetest --mirrortest --infertest --holetest --zfighttest`) are compared with
  `tests/reference/` by the full test; targeted: `--undotest --snaptest --recttest --shelltest --jointest
  --rejecttest`. Visual only: `--linetest`, `--zfighttest`; timing `--perftest`; `--heavytest --model=<file>`.
- `test_units.gd` (`Godot --headless --path viewport --script res://test_units.gd`, 114): the parser, and the local
  evaluator against FreeCAD's answers in `tests/length_cases.json`.
- Tests use a private worker on a port it picks itself and reports in a file (T47); `--port=N` uses an outside
  one; `--shared-port=N` tries sharing next to a running app.
- Suites drive the UI with a simulated cursor; in test mode mouse events that aren't at it are ignored (the real
  pointer over a test window used to scramble runs). Run suites on their own port (not 7878: the app's worker may
  hold it), one at a time per worker (the full test's four lanes each have their own), and don't name a results folder after a viewport copy. Test runs at
  the same time each own their worker ports (T47).
