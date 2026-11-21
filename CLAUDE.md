# Shop Sketch

A SketchUp-feel modeller over FreeCAD for woodworking: tool-first (no workbenches), fast to draw,
while the model stays a real, editable FreeCAD file with FreeCAD's drawings. Blender is for renders only.
Owner: William (teacher; shop and construction background). He thinks in systems and likes values he can tune.

## Before changing behaviour, read the decision log
https://claude.ai/artifact/4smrjxGQm7Rt8H4jWBkpyK (tabs: Decisions, Tunables, Open questions).
Rule P01: a change that contradicts a logged decision gets a new row naming the old ID, and the old row is
marked Superseded (never deleted). Ask William before countermanding an Active decision.
If you can't reach the log, say so; don't guess at what it says.

## How it works
- `viewport/` (Godot 4.6, Compatibility renderer): tools, instant drafts, the confirmation wave (T4 layout):
  `main.gd` setup, worker link, sync, drafts, waves, remembered states, input dispatch;
  `inference.gd` the one snapping engine (pick, endpoint > midpoint > on edge, axis inference);
  `tools/select_tool.gd`, `paint_tool.gd`, `rect_tool.gd`, `push_tool.gd`, `move_tool.gd` (base `tools/tool.gd`: each owns its state and gets
  mouse_moved / click / key / typed); `tests.gd` the scripted suites (added only in test mode).
  Tools and tests `preload("res://main.gd")` for typing; main.gd `load()`s them at runtime (no preload cycle,
  and no `class_name`: Godot run from the command line doesn't register new global class names).
  It starts, watches and restarts its own worker (A27); `--port=N` uses an outside one instead (tests).
  After each action the worker writes `bodies.json` plus `meshes/<board>-<key>.bin` for boards whose shape
  changed (triangles, normals, FreeCAD's exact edges and corners, as Godot PackedVector3Array bytes); the viewport
  builds only boards whose file it hasn't seen (`_apply_confirmed`, A29). The whole-model `model.glb` is written
  at autosave, for renders.
  It remembers the last 40 confirmed states (which board file each had), so undo shows at once (A28).
  Lines (edges, grid, axes) are anti-aliased strips from `line.gdshader` / `line.gdshaderinc`, made by `_lines()` (W12).
  Every action is drawn at once as a draft, then FreeCAD catches up and the real mesh replaces it (A01 idea, W01–W09).
- `worker/replay.py`, which runs inside FreeCAD's command-line program (`freecadcmd`): a long-running
  worker on 127.0.0.1:7878 (newline JSON). It keeps a live FreeCAD document.
- The .FCStd file is the model (A21). Each action becomes native features in one undo transaction (A22, A23):
  board = App::Part with Part::Plane → Part::Extrusion, then booleans, and a `Tip` link.
  Back-to-back cuts share one Part::Cut whose tool is a Part::Compound of cutters (`SSRole` = `cutters`);
  back-to-back merges share one Part::MultiFuse (`SSRole` = `merge-run`) (A22b, Q20). Find a hole by its
  cutter's `SSOp` (`cutter_of`, `tools_of`), not by its boolean. Older files keep one boolean per op; both work.
  A cut pushed to the opposite face (op `"through": true`, cutter `SSThrough`) has expression-driven
  LengthFwd/LengthRev that follow the board's extent (`through_all`, I24): it stays through when the board changes.
  components = App::Link; mirrors = Part::Mirroring; copied holes = Draft OrthoArray of the cutter.
  Copies are linked (A22c, T12): copying a plain board first makes it a component (`as_component`), copies are
  App::Links to the shared definition. Nx and /N copies get an array holder (App::Placement, `SSRole` = `array`:
  Origin, Step, Count, Span, Distributed; /N's Step = Span / Count) and each copy's position is an expression on it
  (`array_follow`; `SSArray`, `SSArrayIndex` on the copy). Moving any member moves its row; `detach` clears the
  expressions; `make_unique` deep-copies the definition into a board of its own (it stays in its row).
  Assemblies (T20) are App::DocumentObjectGroup (`SSRole` = `assembly`, `AssemblyId`), not App::Part: a group
  doesn't move its members' frames, so mirrors and links that reach in or out keep working (an App::Part
  container breaks them: "out of the allowed scope"). Moving an assembly moves each member (and its arrays).
  In the viewport, from outside a board stands for its assembly or its array row (`unit_of`); double-click with
  Select enters one (`context`, the rest greyed and unpickable), Esc leaves. Inside an entered array a moved copy
  leaves the row (op `"detach": true`, I32); a board pushed out inside an assembly joins it (op `"assembly"`).
  A mirrored copy and its original form a mirror group (T26, A11b: an assembly with `SSKind` = `mirror`, op
  `"group"`); inside it the plane shows (`mirror_plane` in bodies.json) and moving the copy moves the original
  reflected. `move_assembly` moves each real board once and shifts each mirror's Base to keep it with the rest.
  A component instance is mirrored through a Part::Compound wrapper (`SSRole` = `mirror-input`, A26):
  released FreeCAD 1.1 mirrors an App::Link without its placement. Walk mirrors with `mirror_source()`, not `.Source`.
  All Shop Sketch state lives on those objects (`BodyId`, `SSRole`, `RectId`, `SSMaterial`, `SSOp`, `SSGrain`).
  Wood (T15, M03): `worker/materials.py` is the library (Wood Handbook numbers, ambientCG CC0 textures in
  `materials/textures`, `<key>_end.jpg` end grain). The worker installs it as FreeCAD cards in
  `~/Library/Application Support/FreeCAD/v1-1/Material/Shop Sketch/` on first use and puts the card on the board's
  current solid (`ShapeMaterial`; `set_tip` carries it to each new solid). `SSGrain` (board frame, zero = longest
  edge) and the across-the-width direction go out in bodies.json; `materials.json` is the paint list. The viewport
  draws painted boards with `wood.gdshader` (no UVs: laid out from world position along grain / across; end grain
  is mirror-repeated). Board nodes are cached by mesh + material + grain, so a repaint rebuilds the look.
  Paint tool (no key yet, Q14), Wood menu, T turns the grain of the board under the cursor.
- `sync(ops)`: keep the common prefix, take back the rest with FreeCAD undo, apply new ops (A23).
  Autosave is atomic, after 0.25 s idle. The journal `<model>.shopsketch.json` sits beside the file (A24).
  Each save adds FreeCAD's view part (`GuiDocument.xml`, `write_gui_document`): without it FreeCAD opens the model
  with everything hidden. When a save lands the worker sends `{"cmd": "saved", "rev"}`; the status bar shows it (Q22).
  Opening a file adopts its journal. An outside edit sets an undo floor; merging is stage 2 (A25, Q19).
- Units: model space is Z-up millimetres; Godot is Y-up metres (`m2g` / `g2m`).
  Faces are referenced by geometry `{body, normal, point}`, never by face numbers (A03).

## Run (macOS)
- `tools/build_app.sh` builds `dist/Shop Sketch.app` (A30): a copy of the Godot program runs
  `Resources/Shop Sketch.pck` (`--export-pack`, preset in `viewport/export_presets.cfg`; no export templates needed),
  with `Resources/worker/*.py`, an icon from `tools/icon.svg`, ad-hoc signed. Files next to the viewport are found
  with `_beside_project()` (repo when run from source, bundle Resources in the app).
- The app opens the last model (`user://settings.cfg`), else `~/Documents/Shop Sketch/Untitled.FCStd`; File > New /
  Open call `switch_model()`. Each model's outputs go in `user://out/<name>-<hash>/` (tests keep `--out` as is).
- Renderer: Compatibility (on a Mac it draws through Metal). Forward+ works (`--rendering-method forward_plus`,
  background matched) but hatches edges on thin faces; see Q5.
- `./Start Shop Sketch.command` opens `models/model.FCStd`; the app starts its worker. Worker log: `worker.log`.
- FreeCAD's command-line program: `/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd`
- Godot: `/Applications/Godot.app/Contents/MacOS/Godot`

## Tests
- After every change: `tools/quicktest.sh` (~20 s). The worker tests, plus every viewport feature once in a single
  Godot session (`--quicktest`, in `tests.gd` `_run_quick_test`), each step checking its own answer. It starts its
  own worker, so it never touches a running Shop Sketch. Add a step there for each new feature.
- When the quick test fails, or before a merge: `tools/fulltest.sh` (~2 min): the six recorded suites (`--facetest`
  `--movetest` `--mirrortest` `--infertest` `--holetest` `--zfighttest`, one session each) compared with
  `tests/reference/` by `tools/compare_suites.py`, then the targeted tests (`--undotest` `--snaptest` `--recttest`
  `--shelltest` `--jointest` `--rejecttest`), then the worker tests. After an intended change in behaviour:
  `tools/fulltest.sh --update-reference`.
- Both scripts first run `tools/parsecheck.sh` (every viewport script, ~3 s): a script that doesn't parse used to
  leave Godot sitting with no test running. The quick test's Godot run is also stopped after 120 s.
- Worker tests alone: `freecadcmd worker/test_native.py` (94 checks) and `worker/test_arrays.py` (10).
- Visual checks (screenshots, no pass/fail): `--linetest`, `--zfighttest`; timing: `--perftest`. Recordings use
  `--true-latency` (P03) with Godot's `--write-movie`; `--heavytest --model=<file>`.
- Test hooks (`delay_ms`, forced rejection, `--*test`) are for testing only (P02).

## Known problems / open work
- Q18: FreeCAD booleans slow down along a chain (24 chained cuts: 5 → 358 ms). Done: hole arrays, one boolean
  per run (A22b): hole 48 on a panel is 290 ms (was 4.3 s). In reserve (T9): answer from plain shapes first.
- The work list is the decision log's "Work list" tab (T1, T2, ...).
- Q19: stage 2, watch the file and merge FreeCAD-side changes. Q17 / stage 3: adopt solids from files Shop Sketch didn't make.
- Q4: feel test on real hardware. Earlier tuning was judged from software-rendered recordings.

## Conventions
- Keep the user-facing feel first: drafts appear instantly. Never block input on FreeCAD.
- Overlays lying on faces use `overlay.gdshader` (depth bias in the shader). Never offset node transforms:
  that broke rectangle picking. Lines get the same bias in `line.gdshaderinc`; the grid has none and draws first.
- Never draw with PRIMITIVE_LINES: 1-pixel GL lines get no anti-aliasing and vanish. Use `_lines()`.
- Godot 4.6 delivers an injected gesture (Input.parse_input_event) twice per frame; `_repeat_gesture` drops the copy.
- New FreeCAD properties go on objects when they are created. Adding properties inside an undo transaction
  isn't reliably undone.
- `freecadcmd` passes the script itself as `sys.argv[1]`. Pass paths through environment variables.
- Draft makes objects in the *active* document: call `App.setActiveDocument(self.doc.Name)` first.
- Combined merges must be Part::MultiFuse: a Part::Fuse whose tool is a compound of overlapping pieces
  counts the overlap twice. A Part::Cut with a compound tool is right even when cutters overlap.
- Viewport suites drive the UI with a simulated cursor. In test mode the viewport ignores mouse events that
  aren't at that cursor (the real pointer over a test window used to scramble runs: the old "flaky" suites).
  Run them on their own port (not 7878: the app's own worker may hold it), one suite at a time, and don't
  name a results folder after a viewport copy.
