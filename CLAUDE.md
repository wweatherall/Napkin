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
  `tools/rect_tool.gd`, `push_tool.gd`, `move_tool.gd` (base `tools/tool.gd`: each owns its state and gets
  mouse_moved / click / key / typed); `tests.gd` the scripted suites (added only in test mode).
  Tools and tests `preload("res://main.gd")` for typing; main.gd `load()`s them at runtime (no preload cycle,
  and no `class_name`: Godot run from the command line doesn't register new global class names).
  It starts, watches and restarts its own worker (A27); `--port=N` uses an outside one instead (tests).
  It remembers the last 40 confirmed states, so undo shows at once while FreeCAD catches up (A28).
  Lines (edges, grid, axes) are anti-aliased strips from `line.gdshader` / `line.gdshaderinc`, made by `_lines()` (W12).
  Every action is drawn at once as a draft, then FreeCAD catches up and the real mesh replaces it (A01 idea, W01–W09).
- `worker/replay.py`, which runs inside FreeCAD's command-line program (`freecadcmd`): a long-running
  worker on 127.0.0.1:7878 (newline JSON). It keeps a live FreeCAD document.
- The .FCStd file is the model (A21). Each action becomes native features in one undo transaction (A22, A23):
  board = App::Part with Part::Plane → Part::Extrusion, then booleans, and a `Tip` link.
  Back-to-back cuts share one Part::Cut whose tool is a Part::Compound of cutters (`SSRole` = `cutters`);
  back-to-back merges share one Part::MultiFuse (`SSRole` = `merge-run`) (A22b, Q20). Find a hole by its
  cutter's `SSOp` (`cutter_of`, `tools_of`), not by its boolean. Older files keep one boolean per op; both work.
  components = App::Link; mirrors = Part::Mirroring; copied holes = Draft OrthoArray of the cutter.
  A component instance is mirrored through a Part::Compound wrapper (`SSRole` = `mirror-input`, A26):
  released FreeCAD 1.1 mirrors an App::Link without its placement. Walk mirrors with `mirror_source()`, not `.Source`.
  All Shop Sketch state lives on those objects (`BodyId`, `SSRole`, `RectId`, `SSMaterial`, `SSOp`).
- `sync(ops)`: keep the common prefix, take back the rest with FreeCAD undo, apply new ops (A23).
  Autosave is atomic, after 0.25 s idle. The journal `<model>.shopsketch.json` sits beside the file (A24).
  Opening a file adopts its journal. An outside edit sets an undo floor; merging is stage 2 (A25, Q19).
- Units: model space is Z-up millimetres; Godot is Y-up metres (`m2g` / `g2m`).
  Faces are referenced by geometry `{body, normal, point}`, never by face numbers (A03).

## Run (macOS)
- `./Start Shop Sketch.command` opens `models/model.FCStd`; the app starts its worker. Worker log: `worker.log`.
- FreeCAD's command-line program: `/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd`
- Godot: `/Applications/Godot.app/Contents/MacOS/Godot`

## Tests (run after every change)
Worker tests:
- `freecadcmd worker/test_native.py`: 50 checks (native tree, undo walks, reopen, outside edits, mirrors of moved instances, rejections, runs, undo past 20)
- `freecadcmd worker/test_arrays.py`: 10 checks (hole arrays and moves)

Viewport suites: `Godot --path viewport -- --<suite> --out=<dir>/out --shots=<dir>/shots --port=7878`, with the worker running.
- Suites: `--facetest` `--movetest` `--mirrortest` `--infertest` `--holetest` `--zfighttest`.
- Each writes `<tag>_bodies.json` checkpoints. Compare them with a known-good run: volumes and world boxes must match.
- Other test modes (print their results; look at the shots): `--linetest` (line visibility), `--undotest` (needs a worker
  on --port), `--snaptest` (Rectangle and Push/Pull snapping, needs a worker on --port),
  `--gesturetest` and `--lifecycletest` (no --port: the app starts its own worker), `--heavytest --model=<file>`. Recordings use `--true-latency` (P03), with Godot's `--write-movie`.
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
- Viewport suites drive the UI frame by frame: run them one at a time with no other Godot window open
  (a window that takes focus loses their input), and don't name a results folder after a viewport copy.
  `--holetest` and `--zfighttest` are flaky even then: a typed push sometimes lands after the next
  rectangle. Compare against a run that has all its ops.
