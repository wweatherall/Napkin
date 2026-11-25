### H141 — T127: Enter and edit components, and Component Properties window (prioritizing critical dimensions and linked measurements)

Author: Gemini (integrator, gemini-cedar-1124-2201) | Date: 2026-11-24 | Status: open | For: either

References: T127, T61, I69, Q35, I28, I36, I40, I57, G04, `viewport/property_panel.gd`, `Gpts properties panel idea; good but needs refinement.png`.

Touches: viewport/selection.gd, viewport/presenter.gd (`apply_context`), viewport/property_panel.gd, viewport/main.gd (`_request_properties`, `_on_properties`, `_edit_property`, `_apply_context`), worker/object_properties.py, viewport/test_selection.gd, viewport/tests/quick/properties.gd, worker/test_properties.py.

Reading path:
1. `viewport/selection.gd` (`set_boards`, `unit_of`, `in_context`, `enter_context_of`, `leave_context`, `siblings_of`) — current assembly and row context model.
2. `viewport/presenter.gd` (`apply_context`, lines 873–898, and `show_siblings`) — how context ghosts non-member boards and how linked siblings are tinted.
3. `worker/object_properties.py` (`inspect`, `describe`, `apply`) and `worker/plane_fit.py` (`snapshot`) — what `inspect_properties` returns today.
4. `viewport/property_panel.gd` (`_ready`, `display`, `_build_summary`, `_show_feature`) and `viewport/main.gd` (`_request_properties`, `_on_properties`, `_edit_property`) — current Properties panel UI and unit formatting in `main.gd`.

Today (verified 2026-11-24 on `main`, post-H126):
- `viewport/selection.gd` supports `context` values `""`, `"assembly:<id>"`, and `"row:<original>"`. Double-clicking a linked board (`body_family[bid] != ""`) that isn't in an assembly or row does nothing (`enter_context_of` returns early). Inside an assembly, double-clicking a linked board also does nothing (`if context.begins_with("assembly:"): return`).
- `viewport/presenter.gd` `apply_context()` ghosts every board with `not sel.in_context(bid)` using `mat_ghost` and disables its collision/edges.
- `worker/object_properties.py` `inspect(model, body)` returns `{body, boards, objects, references}`. When `plane_fit.snapshot(obj)` is `None` (cut boards, non-rectangular boards), `boards` has no entry for `body`, so `viewport/property_panel.gd` hides `summary` completely (`summary.visible = not board.is_empty()`).
- `viewport/property_panel.gd` hardcodes `"%s mm" % board.sizes[i]` instead of using the model's display units (I57), and displays raw native FreeCAD properties expanded by default.

Request:
1. **Enter and isolate linked components on double-click (I69)**:
   - In `viewport/selection.gd`, add component context `component:<bid>` (entering a linked board where `body_family.get(bid, "") != ""`).
   - `enter_context_of(bid)`:
     - When `context == ""`: preserve existing assembly-row / assembly / row entry first; if none of those apply and `body_family.get(bid, "") != ""`, enter `"component:" + bid`.
     - When `context.begins_with("assembly:")`: if `body_family.get(bid, "") != ""`, enter `"component:" + bid` and remember the parent assembly context so `leave_context()` (Esc) steps back to `"assembly:<aid>"` (and a second Esc returns to `""`).
   - `in_context(bid)`: when `context.begins_with("component:")`, return `true` for the entered board (`bid == context.substr(10)`). Add a helper `is_context_sibling(bid) -> bool` returning `true` when in component context and `bid` is in `siblings_of(entered_bid)` (not the entered board itself).
   - Keep `context` valid across `set_boards()` (if the entered board disappears, fall back to its parent context or `""`).
   - In `viewport/presenter.gd` (`apply_context()`): when in component context, the entered board is active/pickable (`inside == true`), its linked siblings (`sel.is_context_sibling(bid)`) remain visible and tinted with the sibling highlight material (not greyed out with `mat_ghost`, so you see edits propagate to every instance, while staying unpickable like outside boards), and all other boards are greyed out (`mat_ghost`) and unpickable.
2. **Enriched summary payload in `worker/object_properties.py`**:
   - In `inspect(model, body)`, keep `body`, `boards`, `objects`, `references` intact (so existing callers/tests don't break) and add a `"summary"` dict that is ALWAYS populated for the selected piece (whether plain rectangular stock, a cut/non-rectangular board, a linked component, or a part in an assembly):
     - `label`: readable piece name (`root.Label`).
     - `context`: human-readable subtitle, e.g. `"Part within <AssemblyLabel>"` when in an assembly, `"Linked component (<N> instances)"` when in a family of `N >= 2` instances, or both joined with `" · "` when in both; `"Board"` otherwise.
     - `parametric`: `bool` — `True` if the piece has a plane fit (`boards.get(body, {}).get("fitted", False)`) or any `ExpressionEngine` entry on its `related(model, body)` objects.
     - `dimensions`: list of critical dimension dicts (up to 3 axes: `{"axis": i, "label": "Length"|"Width"|"Thickness"|..., "value_mm": float, "editable": bool, "linked": bool, "target_label": str, "target_face": str, "offset_mm": float}`). For rectangular stock (`boards.get(body)` present), populate from `boards[body]` (matching its `sizes`, `linked_axis`, and plane-fit target/face/offset when fitted); for cut or non-rectangular boards where `boards.get(body)` is absent, populate read-only bounding-box extents from `root.Shape.BoundBox` (`XLength`, `YLength`, `ZLength`) so the top section is never blank.
3. **Upgraded Component Properties window in `viewport/property_panel.gd` and `viewport/main.gd` (I69)**:
   - Wire a `format_length: Callable` on `property_panel` from `viewport/main.gd` (using the model's I57 unit formatter, e.g. `measure.format_length` / `units`, with a `"%.2f mm"` fallback when unset so standalone tests work).
   - **Header**: show readable piece name (`summary.label`), context subtitle (`summary.context`), and a visible `"Parametric"` badge when `summary.parametric` is true.
   - **Top section (always visible)**: clean key-value rows prioritizing critical dimensions and linked measurements formatted in the model's display units (I57):
     - For rectangular stock: keep the editable dimension inputs (formatted in display units), Placement inputs, `"Pick face…"`, fit mode picker, and `"Apply fit"` workflow working cleanly; for a linked axis, show the linked indicator (`🔗 <Target> · <Face>` plus offset if non-zero) and `"Current evaluated length"` in display units.
     - For cut / non-rectangular boards (where `boards.get(body)` is empty): show the read-only critical dimensions from `summary.dimensions` in display units instead of hiding `summary`.
   - **Native FreeCAD properties collapsed by default**: wrap `object_picker`, `help`, `reference_picker`, and `fields` in a collapsible section toggled by a button (`"Native FreeCAD properties"`), collapsed by default so critical dimensions and linked measurements dominate the window, while keeping every native property, expression editor, and reference picker accessible when expanded.

Checks:
- `viewport/test_selection.gd`: test double-clicking (`enter_context_of`) a standalone linked board enters `component:<bid>`, `in_context` is true for the entered board, `is_context_sibling` is true for its siblings and false for unrelated boards, `leave_context` returns to `""`; test entering a linked board from inside an assembly returns to `assembly:<aid>` on first `leave_context` and `""` on second.
- `worker/test_properties.py`: test `inspect()` always returns `summary` with `label`, `context` (plain board, assembly member, linked component instance count), `parametric` flag, and `dimensions` for both rectangular stock (including fitted/linked target info) and a cut/non-rectangular board.
- `viewport/tests/quick/properties.gd`: keep existing plane-fit and property-edit checks passing (expand the native toggle where a test clicks native fields, and accept formatted display units), plus verify the new header/subtitle/Parametric badge, display-unit formatting, cut-board summary visibility, and entering a linked component keeps siblings visible/tinted while greying out unrelated boards.
- Keep `Q35` (extruding off a drawing on a board's face) untouched — it is a separate future decision.

Architecture: `viewport/selection.gd` adds `"component:<bid>"` context (with `_context_parent` for assembly-nested components) and `is_context_sibling(bid)` so `viewport/presenter.gd` `apply_context()` keeps linked siblings visible and tinted with `mat_sibling` while unpickable.
Architecture: `worker/object_properties.py` `inspect()` adds an always-populated `summary` dict (`label`, `context`, `parametric`, `dimensions`) alongside `body`, `boards`, `objects`, `references`.
Architecture: `viewport/property_panel.gd` adds `format_length: Callable` (wired from `measure.format_length` in `viewport/main.gd`), a piece header with `Parametric` badge, read-only `BoundBox` dimensions when `boards[body]` is absent, and a collapsed-by-default `"Native FreeCAD properties"` toggle.
