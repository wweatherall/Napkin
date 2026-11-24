### H141 — T127: Enter and edit components, and Component Properties window (prioritizing critical dimensions and linked measurements)

Author: Gemini (integrator, gemini-cedar-1124-0100) | Date: 2026-11-24 | Status: queued (after H126) | For: either

References: T127, T61, T62, I28, I36, I40, I57, G04, `viewport/property_panel.gd` (Codex's H012/T53 window).

Touches: viewport/selection.gd, viewport/property_panel.gd, viewport/main.gd (`_request_properties`, `_edit_property`, `_apply_context`), worker/object_properties.py, viewport/test_selection.gd, viewport/tests/quick/properties.gd, worker/test_properties.py.

Why: William (2026-11-24) requested a way to enter and edit components, and asked to keep and build on ChatGPT/Codex's Properties window (`viewport/property_panel.gd`) so component properties prioritize critical dimensions and linked measurements (and stay visible on components, assemblies, and cut boards instead of vanishing when `stock_frame` is absent, formatted in the model's display units instead of hardcoded `mm`).

Note for the integrator: queued after H126 (T61: face ties on linked copies) and pending William's answer on entering-component behaviour (whether double-clicking a linked component enters/isolates it like an assembly, and whether critical dimensions + linked measurements should also show for assemblies and boards with cuts). Once William answers and H126 merges, log the decision, recheck `viewport/property_panel.gd` and `viewport/selection.gd` against `main`, and expand `Today`, `Request`, `Checks`, and `Reading path` before marking `open`.
