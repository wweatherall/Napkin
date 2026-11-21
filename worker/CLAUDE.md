# worker/: the FreeCAD side

Runs inside FreeCAD's command-line program (`freecadcmd`): a long-running worker on 127.0.0.1 (newline JSON),
one thread serving every connected window with `select` (W13). It keeps a live FreeCAD document per model, turns
each action into native features, and writes what the viewport reads. The top-level CLAUDE.md has the overview;
ARCHITECTURE.md the module map and protocol (update it in the same commit when you change either).

## Modules (T42)
- `replay.py` only starts the worker (`freecadcmd` runs it by name; it names the module `replay`, not `__main__`,
  and doesn't put this folder on `sys.path`, so replay.py does). One-off: `OPLOG=ops.json OUTDIR=out`.
- `common.py`: shared basics (FreeCAD imports, `TOL`, `OpError`, `vec`/`unit`, `add_props`, `Frame`, wood cards);
  every module starts with `from common import *`.
- `model.py`: `Model` (reads the document; building blocks: boards, planes, extrusions, booleans, `Tip`; `apply`
  and `HANDLERS`). Each kind of action is a mixin in its own file: `push.py` (rect, push/pull, through-cuts),
  `move.py` (move, copies, links, arrays, detach, make unique), `mirror.py`, `assembly.py`, `paint.py` (paint,
  grain). A new op: an `op_<type>` in the right mixin (or a new mixin listed in `Model`), and its type in `HANDLERS`.
- `export.py`: bodies.json entries, per-board mesh files and their caches, model.glb, the TechDraw page.
- `session.py`: `Session`, one live document per .FCStd: `sync`, undo, rebuild, journal, saves.
- `serve.py`: the connection loop (`hello`, `open`, `sync`, `length`, `inspect_properties`, `bye`, `quit`; `saved`
  and `focus` events), ownership (one window per model), delayed saves, idle exit (`SERVE_IDLE_EXIT`).
  `SERVE_PORT=0` binds a free port and writes it to `SERVE_PORT_FILE` (T47): tests start workers this way.
- `length_input.py`: typed lengths through FreeCAD's expressions (T32, I35). `viewport/units.gd`
  `evaluate_length` ports it: after changing it, run `freecadcmd tools/length_cases.py` and the units test.
- `object_properties.py`: the Properties panel's snapshot and `property_edit` (T46, I36).
- `materials.py`: the wood library (T15, M03). `drawing.py`: shop drawings (plain python3, not the worker).
- The worker's hash (`hello`) is the MD5 of every .py here except `test_*`; main.gd `_worker_identity()` computes
  the same. A new non-test .py is in the hash and the app bundle automatically.

## How a model is built
- The .FCStd file is the model (A21). Each action becomes native features in one undo transaction (A22, A23):
  board = App::Part with Part::Plane → Part::Extrusion, then booleans, and a `Tip` link.
- Back-to-back cuts share one Part::Cut whose tool is a Part::Compound of cutters (`SSRole` = `cutters`);
  back-to-back merges share one Part::MultiFuse (`SSRole` = `merge-run`) (A22b, Q20). Find a hole by its
  cutter's `SSOp` (`cutter_of`, `tools_of`), not by its boolean. Older files keep one boolean per op; both work.
- A cut pushed to the opposite face (op `"through": true`, cutter `SSThrough`) has expression-driven
  LengthFwd/LengthRev that follow the board's extent (`through_all`, I24): it stays through when the board changes.
- components = App::Link; mirrors = Part::Mirroring; copied holes = Draft OrthoArray of the cutter.
- Copies are linked (A22c, T12): copying a plain board first makes it a component (`as_component`); copies are
  App::Links to the shared definition. Nx and /N copies get an array holder (App::Placement, `SSRole` = `array`:
  Origin, Step, Count, Span, Distributed; /N's Step = Span / Count) and each copy's position is an expression on it
  (`array_follow`; `SSArray`, `SSArrayIndex` on the copy). Moving any member moves its row; `detach` clears the
  expressions; `make_unique` deep-copies the definition into a board of its own (it stays in its row).
- Assemblies (T20) are App::DocumentObjectGroup (`SSRole` = `assembly`, `AssemblyId`), not App::Part: a group
  doesn't move its members' frames, so mirrors and links that reach in or out keep working (an App::Part
  container breaks them: "out of the allowed scope"). Moving an assembly moves each member (and its arrays).
- A mirrored copy and its original form a mirror group (T26, A11b: an assembly with `SSKind` = `mirror`, op
  `"group"`); `mirror_plane` goes out in bodies.json. `move_assembly` moves each real board once and shifts each
  mirror's Base to keep it with the rest.
- A component instance is mirrored through a Part::Compound wrapper (`SSRole` = `mirror-input`, A26): released
  FreeCAD 1.1 mirrors an App::Link without its placement. Walk mirrors with `mirror_source()`, not `.Source`.
- All Shop Sketch state lives on those objects (`BodyId`, `SSRole`, `RectId`, `SSMaterial`, `SSOp`, `SSGrain`).
- Wood: `materials.py` has Wood Handbook numbers and ambientCG CC0 textures (`materials/textures`, `<key>_end.jpg`
  end grain). The worker installs it as FreeCAD cards in
  `~/Library/Application Support/FreeCAD/v1-1/Material/Shop Sketch/` on first use and puts the card on the board's
  current solid (`ShapeMaterial`; `set_tip` carries it to each new solid). `SSGrain` (board frame, zero = longest
  edge) and the across-the-width direction go out in bodies.json; `materials.json` is the paint list.
- Faces are referenced by geometry `{body, normal, point}`, never by face numbers (A03). Model space is Z-up mm.

## Sync, undo, saving
- `sync(ops)`: keep the common prefix, take back the rest with FreeCAD undo, apply new ops (A23). FreeCAD's
  command-line program keeps only 20 undo steps; further back, Session rebuilds from the journal (T10).
- After each action: `bodies.json` plus `meshes/<board>-<key>.bin` for boards whose shape changed (A29).
- Autosave is atomic, after 0.25 s idle; model.glb at autosave. The journal `<model>.shopsketch.json` sits beside
  the file (A24). Each save adds FreeCAD's view part (`GuiDocument.xml`, `write_gui_document`): without it FreeCAD
  opens the model with everything hidden. A landed save sends `{"cmd": "saved", "rev"}` (Q22).
- Opening a file adopts its journal. An outside edit sets an undo floor; merging is stage 2 (A25, Q19).

## FreeCAD rules (learned the hard way)
- New FreeCAD properties go on objects when they are created: adding them inside an undo transaction isn't
  reliably undone.
- `freecadcmd` passes the script itself as `sys.argv[1]`: pass paths through environment variables.
- When a script raises, `freecadcmd` runs it a second time: a crashed test shows every check twice, and the second
  pass trips over the first one's files. Read the first error.
- Removing a TechDraw page also removes its views and template (1.1.4); removing an already-deleted object then
  crashes FreeCAD with a bus error (the worker just dies). Remove by name, views first, and check
  `doc.getObject(name)` before each removal (`remove_drawing_pages`).
- Draft makes objects in the *active* document: call `App.setActiveDocument(self.doc.Name)` first.
- Combined merges must be Part::MultiFuse: a Part::Fuse whose tool is a compound of overlapping pieces counts the
  overlap twice. A Part::Cut with a compound tool is right even when cutters overlap.
- FreeCAD 1.1.4 is installed; don't work around bugs that 1.1.4 no longer has.

## Tests (each runs in both test scripts)
- `freecadcmd worker/test_native.py` (96: feature tree, op-by-op = fresh, undo/amend walks, reopen, outside edits),
  `test_arrays.py` (10: hole arrays and moves), `test_combos.py` (61: features together, undo/reopen equal a fresh
  build, two models at once), `test_length_input.py` (23, incl. FreeCAD still matching tests/length_cases.json),
  `test_properties.py` (28), `test_scenario.py` (86, T48: one busy fixture model from
  `tests/scenario_fixture.json`, 17 steps each checked and undone back to the fixture, then a cumulative story that
  must equal a fresh build and a reopen; ~1 s. A new worker behaviour: add a step there first).
  Plain python3, starting freecadcmd themselves: `test_serve.py` (12: one worker, two windows; a worker on port 0),
  `test_length_protocol.py` (3). Use `TESTDIR=<dir>` for outputs.
- Tests load the modules with `from test_load import *` (after putting this folder on `sys.path`).
