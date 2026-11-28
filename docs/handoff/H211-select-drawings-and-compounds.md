### H211 — Double-click enters William's copies; drawings (2D shapes) can be selected; a compound's properties show (T167)

Author: Claude (integrator, opus-integrator) | Date: 2026-11-28 | Status: open | For: codex | Item: T167

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
