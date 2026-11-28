### H209 — The toolbar shows each tool's key in brackets next to its name (T167)

Author: Claude (integrator, opus-integrator) | Date: 2026-11-28 | Status: open | For: codex | Item: T167

References: T167 (William, 2026-11-28: "hotkeys in brackets next to names"), G05 (one key per idea), G03 (Mac app
feel), `viewport/tool_registry.gd` `menu_label` (the Tools menu already shows "Rectangle (R)").

Today: `viewport/ui.gd` (line ~131) builds the toolbar from `m.tool_list` with `t["label"]` only; the key is in the
tooltip. The fixed buttons after it (Undo, Redo, Drawing, Grid snap, New board) also show names only.

Touches: viewport/ui.gd (the toolbar row only), viewport/tool_registry.gd (`menu_label`, if you share it), and
the viewport test that already covers `menu_label` (find it with grep; a new test file is fine).

Request:
1. Toolbar tool buttons read like the Tools menu: `tool_registry.gd`'s `menu_label` ("Select (Space)", "Rectangle (R)").
   Use the same function, so the toolbar, the menu and the key can't disagree (one spot per idea, C06).
2. The fixed buttons get their keys too: "Undo (⌘Z)", "Redo (⇧⌘Z)", "Drawing (D)", "Grid snap (G)", "New board (B)",
   taken from where those keys are bound (`viewport/keys.gd`) if you can do it without a new module; otherwise
   from the tooltip strings already in ui.gd.
3. The toolbar must still fit a 1280-pixel-wide window without clipping (William uses a laptop): if it doesn't,
   shrink the separation or font a little, and say so in the response with a screenshot in scratch/.

Checks:
- A named viewport check that every toolbar tool button's text equals `menu_label` of its tool.
- `tools/TEST_BEFORE_MERGING.sh` passes. A screenshot at 1280 wide in the response.
