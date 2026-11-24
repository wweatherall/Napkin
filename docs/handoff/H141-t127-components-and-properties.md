### H141 — T127: Enter and edit components, and Component Properties window (prioritizing critical dimensions and linked measurements)

Author: Gemini (integrator, gemini-cedar-1124-0100) | Date: 2026-11-24 | Status: queued (after H126) | For: either

References: T127, T61, T62, I69, Q35, I28, I36, I40, I57, G04, `viewport/property_panel.gd` (Codex's H012/T53 window), `Gpts properties panel idea; good but needs refinement.png`.

Touches: viewport/selection.gd, viewport/property_panel.gd, viewport/main.gd (`_request_properties`, `_edit_property`, `_apply_context`), worker/object_properties.py, viewport/test_selection.gd, viewport/tests/quick/properties.gd, worker/test_properties.py.

Why: I69 (William, 2026-11-24) approves entering and isolating linked components on double-click (just like assemblies: greys out the rest of the model, keeps siblings tinted so you see what changes, Esc leaves) and upgrading Codex's Properties window (`viewport/property_panel.gd`) to match the clean hierarchy in `Gpts properties panel idea; good but needs refinement.png`:
- Header: readable piece name (e.g. `Apron · Front`), subtitle showing context (`Part within Table Assembly` / `Linked component (N instances)`), and a `Parametric` badge when driven by fits/expressions.
- Top section (always visible for components, assemblies, and cut boards — not hidden when `stock_frame` is absent): clean key-value rows prioritizing critical dimensions (Thickness, Height, Length) and linked measurements (`🔗 Target · Face` with clearance/offset if any and `Current evaluated length`), all formatted in the model's display units (I57) instead of hardcoded `mm`.
- Raw FreeCAD native properties / Placement / ExpressionEngine remain accessible collapsed below.

Note for the integrator: queued after H126 (T61: face ties on linked copies). Once H126 merges, recheck `viewport/property_panel.gd`, `viewport/selection.gd`, and `worker/object_properties.py` against `main` and expand `Today`, `Request`, `Checks`, and `Reading path` before marking `open`. (Extruding off a drawing on a board's face becoming two parts within a component is tracked separately as Q35 to discuss with William first.)
