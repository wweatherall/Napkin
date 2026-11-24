# viewport/: the Godot side

Godot 4.6, Compatibility renderer (on a Mac it draws through Metal; Forward+ hatches edges on thin faces, Q5).
Everything you see and touch: tools, instant drafts, the confirmation wave, typed values, panels. FreeCAD is the
evaluator; this side predicts. The top-level CLAUDE.md has the overview; ARCHITECTURE.md the module map and
protocol (update it in the same commit when you change either). Tools have their own guide in `tools/CLAUDE.md`.

## Files
- `main.gd` (~1,400 lines; split in T39 / T41 / T75 / T113): setup, materials (`_lines` still forwards to the presenter for callers that want a node),
  worker process and lifecycle, rejection bookkeeping, input dispatch (camera input to `camera_rig.gd`, menus in `menus.gd`, the interface built by `ui.gd`), model switching.
- `keys.gd` (T75): the keyboard, `m.keys`: shortcuts, tool keys (`m.tool_keys`, from each tool's `TOOL`), Esc, Enter, Delete / Backspace (I48), typed
  characters, Tab / ⌥ for Push/Pull. main's `_input` / `_unhandled_input` stay the entry points (tests call
  `m._unhandled_input`) and hand it key presses.
- `camera_rig.gd` (T113): the camera, `m.camera_rig`: orbit, pan, zoom (mouse and trackpad) and the live trackpad and
  wheel tunables. main dispatches camera input to it and owns the scene Camera3D (`m.cam`); tests set a view through
  `m.camera_rig` (`target`, `yaw`, `pitch`, `dist`, then `update_camera()`).
- `measure_box.gd` (T75): the measurements box, `m.measure`: typed text (`vcb`), `typing`, the box itself, typed
  values (`apply`) and `length` requests FreeCAD works out. main forwards the old names (`m.vcb`, `m.apply_vcb()`,
  `m._update_vcb()`, ...).
- `document.gd` (T39, A31): the document controller, `m.doc`. Owns the op list, ID reservations and `next_id` (the only ID allocator, T67), `seq` / `in_flight` /
  `dirty`, which reply counts, confirmed ids, undo floor, redo stack, open / reset, save revisions; reports by
  signals and knows nothing of meshes. main.gd forwards those names (`m.ops`, `m.seq`, ...) to it. Undo, redo and
  removal go through it (`op_removed` tells main to take away what an op drew).
- `selection.gd` (T41, A33b): selection and context, `m.sel`. Owns `selection`, `context`, each board's assembly /
  row / family / array / mirror plane, the hidden/deleted sets, `show_hidden`, `hover_body`; deletion (T34, I46); the queries (`unit_of`,
  `in_context`, `is_hidden`, ...) and the actions that add hide / assembly / unlink ops. Draws nothing: main.gd
  and the presenter draw on its signals. main forwards its properties (`m.selection`, `m.context`, ...); its methods are
  called as `m.sel.*` (H114).
- `presenter.gd` (T41, A33b): geometry on screen, `m.pres`. Owns `body_tris` / `body_verts` / `body_edges` /
  `body_cuts`, drafts and rects, confirmed board nodes, remembered states, waves (`step_waves` each frame) and the
  selection / context highlights. Also owns a unit's joined triangles (`m.pres.unit_tris`), Select's drag box (T88 step 2), the mesh / line / collision /
  marker helpers (`tri_mesh`, `line_mesh` (a mesh for a node already in the scene: previews, outlines, guides), `lines` (a new node), `add_collision`, `show_marker`), Push/Pull's face highlight, Move's guides (`draw_guides` / `clear_guides`) and
  `mirror_preview` (T88 step 6), and `present_draft` (a committed draft and its wave, Push/Pull's and Move's);
  `draft_tests` (was `push_tests`) is the test recorder of new boards' draft bounds and the rejection filter. main forwards the old
  names (`m.body_tris`, `m.drafts`, `m._begin_wave`, ...). main routes the document's signals to it.
- `inference.gd`: the one snapping engine (pick; endpoint > midpoint > on edge; axis inference). Every tool uses it.
- `tools/`: one object per tool (see its guide); `tool_registry.gd` finds them (each declares a `TOOL`), and the
  toolbar, Tools menu and tool keys come from that. `property_panel.gd`: the Properties panel (T46, I36).
- `appearance.gd` (T88 step 1, T113): wood: the library, each board's material, the wood shader material presenter.gd
  asks for (`wood_material`), the current Paint wood, and the Paint and T (grain) commands. Made with the document
  and a texture-path callable, not Main.
- `save_prompts.gd` (T113): the close and outside-save questions, `m.prompts` (a Node, main's child): their dialogs,
  state, deadlines and choices; document.gd decides when to save or reload, main connects its signals here.
- `worker_process.gd` (T113): the FreeCAD worker's process, `m.worker`: finds, probes, picks, starts, restarts, watches
  and stops the worker, and writes worker.log. main keeps `PROTOCOL_VERSION`, opening the model and reconnects
  (`_send_open`, `_on_link_up`); `worker_client.gd` owns the socket.
- `ui.gd` (T113): the interface, `m.ui`: the theme and palette (`c`, `box`), toolbar, Properties panel, status bar,
  tooltip, toggle buttons and the save indicator. Main keeps the label nodes (`ui_hint`, `ui_sync`, `ui_tip`,
  `ui_saved`); MeasureBox styles its box through `m.ui`.
- `menus.gd` (T113): the native menus, `m.menus`: builds them (the Tools menu from the registry, Units, Wood), keeps
  their check marks and shows New / Open's dialogs. Toolbar buttons, menu items and keys.gd's shortcuts all call
  `m.menus.run(tag)`; model switching and new windows stay in main.
- `preferences.gd` (I63, T111): reads, checks and watches the preferences JSON (the default units and the feel
  tunables); standalone, the caller passes the path; tests make their own file. main.gd loads and watches it outside
  test mode (H103); code reads the live tunables (`Inference.snap_px`, `Tool.drag_px`, ...), never the constants,
  which stay the built-in defaults. A test that changes them puts the defaults back (`_apply_preferences(DEFAULTS)`).
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
- Worker (W13): a window uses the worker on port 7878 if `hello` reports the same protocol version (`PROTOCOL_VERSION`,
  docs/protocol.md; `m.worker.worker_of`, worker_process.gd) and the same hash (`worker_identity()`: every worker .py except tests), else starts one there (a different version gets a private worker on a free port). Each
  window has its own FreeCAD document; a model is open in one window at a time (`already_open`, the owner gets
  `focus`; a window launched on a taken model closes itself). Closing a window sends `bye`. If the worker dies,
  whichever window notices restarts it. File > New Window (⌘⇧N). Files beside the viewport: `_beside_project()`.
- Typed values (`measure_box.gd`): `apply_vcb` keeps Move's count syntax (`3x`, `/3`) for the tool; a length is worked out by
  `units.gd` at once and handed to the tool in mm; only what it declines waits for a `length` reply.
- Context: from outside, a board stands for its assembly or array row (`unit_of`); double-click with Select enters
  one (`enter_context_of`, the rest greyed and unpickable), Esc leaves. Inside an entered array a moved copy leaves
  the row (op `"detach": true`, I32); a board pushed out inside an assembly joins it (op `"assembly"`). Inside a
  mirror group the plane shows and moving the copy moves the original reflected.
- Selection (T34): Select drags right for enclosed units, left for crossing units; Shift adds. Move on a selected board uses the whole selection (copy/mirror too); a copy of every board of an assembly makes a new assembly (`_whole_assemblies`); 3x / /3 makes a row of linked assemblies with editable spacing (T58, I52). Enter the row, then an assembly; moving a copied assembly inside the row detaches all its positions while keeping shape links (I53). Delete / Backspace (I48): once the measurements box is clicked or typed in (`typing`), they edit it, even emptied, until a click in the view or a new selection; otherwise they delete in one op, in any tool: mid-move what's being moved, else the selection (Edit > Delete has no menu key). Deleted IDs follow ops immediately, suppressing confirmed and draft collisions even with Hidden geometry on. Deleting an entered row's original promotes a survivor and keeps the entered context with it (I46). Cached undo/redo states restore relationship metadata as well as geometry.
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
- Never draw with PRIMITIVE_LINES: 1-pixel GL lines get no anti-aliasing and vanish. Use the presenter's `lines()` (`_lines()` in main, `ctx.view.preview` in a tool) (W12).
- Godot 4.6 delivers an injected gesture (Input.parse_input_event) twice per frame; `_repeat_gesture` drops the copy.
- Test hooks (`delay_ms`, forced rejection, `--*test`) are for testing only (P02).

## Tests
- The quick test is `tests/quick_runner.gd` (`--quicktest`, run by `tools/quicktest.sh`): every feature once,
  each step checking its own answer. Each section is `tests/quick/<name>.gd` with a `run()` method;
  `QUICK_LANES` in quick_runner.gd deals them into the three windows the script runs side by side
  (`--quick-lane=N`, T49; keep the lanes about equal in time). A new feature: a step in a
  section, or a new section file (it joins the shortest lane by itself; list it in a lane to pin it). Its sections share one model (`_fresh` clears
  the window and syncs the section's ops; `own_file` for model switching); in quick mode drags take 2 frames, waves
  get 2 frames' pad and frames skip the physics tick (T48: 26 → 14 s). It prints where its time goes (`QUICK timing`).
  `--fast` gives any suite that pace but keeps the physics tick (picking a draft drawn a moment ago needs one: the
  face test's draw-on-a-draft step misses without it). Not for recordings (P03).
- Recorded suites (`--facetest --movetest --mirrortest --infertest --holetest --zfighttest`) are compared with
  `tests/reference/` by the full test; targeted: `--undotest --snaptest --recttest --shelltest --jointest
  --rejecttest`. Visual only: `--linetest`, `--zfighttest`; timing `--perftest`; `--heavytest --model=<file>`.
- Headless tests: `tools/featuretest.sh` finds every `viewport/test_*.gd` and runs it with
  `Godot --headless --path viewport --script res://<file>`; each prints `<NAME> TESTS: N passed, M failed` and its
  first lines say what it covers (the document controller, selection, the tool registry, the tool interface, the
  units parser against `tests/length_cases.json`). A new file needs no other edit. `test_document.gd` provides
  `FakeClient.last_of` / `drain` and request-matched reply/event builders (`reply`, `reload_reply`,
  `keep_mine_reply`, `open_reply`, `error_reply`, `outside_save`) for P42 document-controller failure-path checks.
  `test_tools.gd` also runs inside
  the built pack (`tools/build_app.sh`); quick-test `registry` checks the real toolbar, and `selection` the
  selection behaviour in the window.
- Tests use a private worker on a port it picks itself and reports in a file (T47); `--port=N` uses an outside
  one; `--shared-port=N` tries sharing next to a running app.
- Suites drive the UI with a simulated cursor; in test mode mouse events that aren't at it are ignored (the real
  pointer over a test window used to scramble runs). Run suites on their own port (not 7878: the app's worker may
  hold it), one at a time per worker (the full test's four lanes each have their own), and don't name a results folder after a viewport copy. Test runs at
  the same time each own their worker ports (T47).
