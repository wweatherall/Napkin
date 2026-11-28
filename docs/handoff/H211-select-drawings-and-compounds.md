### H211 — Double-click enters William's copies; drawings (2D shapes) can be selected; a compound's properties show (T167)

Author: Claude (integrator, opus-integrator) | Date: 2026-11-28 | Status: answered | For: codex | Item: T167

References: T167 (William, 2026-11-28: "can't select drawings"; "properties should show up for compound objects"),
I69 (double-click enters a linked component), I32/I46 (entered contexts), G03 (SketchUp: a loose face or edge is
selectable with one click), G13; `viewport/selection.gd`, `viewport/select_tool`
(`viewport/tools/select_tool.gd`), `viewport/property_panel.gd`, `worker/object_properties.py`.

Today: what "drawings" and "compound objects" mean in William's model isn't certain, and finding out is step 1.
Most likely: "drawings" are rectangles, circles, polygons, arcs and lines drawn but not pushed into boards (profiles),
which the select tool's pick may skip because it picks bodies; "compound objects" are assemblies, arrays or linked
components (selection.gd's contexts), for which the property panel may show nothing when one is selected whole.
William's model: `models/model.FCStd` (open a copy in scratch/, never the original).

Touches: viewport/tools/select_tool.gd, viewport/selection.gd, viewport/selection_view.gd, viewport/property_panel.gd,
worker/object_properties.py, worker/serve.py and viewport/main.gd only if the properties reply needs a new field
(then PROTOCOL_VERSION, docs/protocol.md, tests/op_contracts.json; say so in the response), viewport and worker tests.

Request:
0. First and most important (William, 2026-11-28: "whenever I made multiple copies of a single shape, did it not make
   a component of them? Because I couldn't double click into it"). In his model (`models/model.FCStd`; the app's
   last bodies.json is `~/Library/Application Support/Godot/app_userdata/Napkin/out/model-0f8e6337/bodies.json`)
   b16 and five copies share `component: b16_665c...`, `family: Board`, `row: b16_665c...` (the copies also
   `array: Array`). So they are a linked component, and `selection.gd` `enter_context_of` should enter `row:b16...`
   (or the component, I69). Reproduce the double-click in the app on that model (a copy in scratch/), find why it
   doesn't enter (does the double-click reach `enter_context_of`? does entering a row show anything William can
   see? should a row of linked copies enter as the component, per I69?), and make double-click on any one of them
   enter and isolate them as I69 says. Say what was wrong in the response. If the fix needs a choice (row vs
   component), choose I69's behaviour and list the question for William.
1. In a copy of William's model, list what in it can't be selected with a click (by FreeCAD object type and Napkin
   kind) and what shows no properties when selected. Put the list in the response.
2. A click on a drawn shape that isn't a board selects it (highlighted in the selection's style, G07: no violet, red
   or amber), Delete removes it (undoable), and Move moves it, as with a board. A drag-box select includes them.
3. Selecting an assembly, array or linked component whole shows its properties: its name, kind ("Assembly of 4",
   "Array of 6", "Linked component (3 instances)", the wording `object_properties.py` already uses) and its overall
   size; fields that belong to one member stay hidden until you enter it (I69).
4. Anything here that's a behaviour choice beyond these (e.g. what a drawn line's properties are): pick the simplest,
   list it as a question for William in the response, and don't block on it.

Checks:
- Named checks: double-click on a member of a linked row of copies enters it (a fixture like William's: one board, 5x copies); click-select a profile; box-select includes it; Delete then Undo brings it back; an assembly, an array
  and a linked component each show their summary properties when selected whole.
- `tools/TEST_BEFORE_MERGING.sh` passes.


Response — Codex, 2026-11-28:

Architecture: `viewport/selection.gd` owns the entered context and resolves a current selection to one piece or one compound for inspection.
Architecture: `viewport/inference.gd` owns viewport picking for drawable profiles and projected loose edges. `viewport/profiles.gd` owns the visible projection of drawing Move and Delete ops, including undo, redo, and reopen.
Architecture: `worker/model.py` resolves drawing op IDs to editable native features and clears unused derived outlines when their source geometry changes. The existing `move` and `delete` ops accept drawing op IDs for native transactions.
Architecture: `worker/object_properties.py` owns the drawing and compound summaries. `inspect_properties` now accepts optional compound membership and drawing IDs. Both sides speak protocol 25.

Branch `codex/h211-select-drawings-and-compounds`, code commit `b3a468f`.

I reproduced step 0 in the app with a scratch copy of William's `models/model.FCStd`. Double-clicking b18 reached Select and entered `row:b16…`. All six copies stayed editable in place, so there was little visual change. The new entry goes into the clicked instance, keeps its five siblings tinted and greys the separate board. Esc leaves the component. I used I69 for linked board rows and kept row entry for rows of assemblies.

Before the change the eight loose rectangles (Napkin `rect`, FreeCAD `Part::Plane`, Rect005–Rect012) and two arcs (Napkin `arc`, FreeCAD `Sketcher::SketchObject`, Arc and Arc001) could not be selected. The six `App::Link` instances under the `App::Placement` array selected together but produced the one-piece Properties prompt. The polygon sketch and cutter compound in the file are native dependencies of the existing solids and cuts. The same file now allows click selection of all ten loose drawings. The whole array displays “Board 16” and “Array of 6”, with X/Y/Z extents of about 1256.74 × 10456.74 × 1029 mm. The saved original and the scratch copy had identical hashes after verification.

Named Godot and FreeCAD checks cover original plus five linked copies, assembly/array/component properties, click selection of rectangles, circles, polygons, lines and arcs, enclosing and crossing boxes, native Move and Delete, and Undo. Moving a line that breaks a closed outline clears the obsolete derived face and Undo restores it.

Choices for William to review: Drawing properties currently show a name, kind and read-only overall size. Move translates a drawing as a separate feature and clears its attachment if it was drawn on a board face. Edges of a closed line loop are selectable individually. Would you prefer native drawing edits in Properties, retention of face attachment during an in-plane move, or a way to select the whole filled loop? For linked rows I chose I69's entered-instance behavior. If you also want direct entry to a row for editing several copies together, that is a separate choice.

Scope answer from the integrator: “Yes: extend those entry points (move_tool.gd, tool_context.gd, profiles.gd, inference.gd, worker/move.py, deletion.py, model.py) and update the folder guides if ownership changes; reusing the move/delete ops is right. Conditions: (1) do step 0 first (double-click into William's linked copies): it blocks him most; (2) keep the ops' field shape where you can; if a field or accepted id kind changes, bump PROTOCOL_VERSION and update docs/protocol.md, tests/op_contracts.json and worker/scenario/99_op_registry.py; (3) an Architecture: line for each changed ownership; (4) H210 (queued) also touches move_tool.gd: keep your change there to the id check. If profile Move/Delete grows past ~300 lines, submit steps 0, select and 3, with a Follow-up: line for the rest.”

Changed from the brief: The additional worker and viewport entry points and folder guides were approved above. Move needed drawing IDs and geometry at pickup, with outlines during the gesture and drawing IDs excluded from the solid draft mesh at commit. The changes are scoped to pickup, previews and commit filtering.
Changed from the brief: Compound inspection needed an optional request field for the selected members. It reuses the existing summary reply and protocol 25 applies on both sides.
Changed from the brief: The pre-commit hook regenerated `ARCHITECTURE.md` from the touched module's entry points.

The merge gate passed with 425 viewport checks, the full feature suite, the recorded viewport suites and the field audit. The preceding gate run's quick leg hit the hopper display test's live queue race. Its full suite passed and the gate was rerun without code changes.

Result: b3a468f; merge gate passed, 425 quick viewport checks and full suites; linked copies enter individually, drawings select and edit, and compounds show summary properties.
