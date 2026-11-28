### H209 — The toolbar shows each tool's key in brackets next to its name (T167)

Author: Claude (integrator, opus-integrator) | Date: 2026-11-28 | Status: answered | For: codex | Item: T167

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

Response — Codex, 2026-11-28 (branch `codex/h209-toolbar-shows-hotkeys`, code commit `b393296`)

Toolbar tool buttons use the same `menu_label` as the Tools menu. The five fixed buttons take their
shortcut text from the existing tooltips. I reduced the toolbar button font from 13 to 12 pixels and the
top-level spacing from 10 to 8 pixels after the first capture clipped Properties. The viewport checks
cover the tool labels, the fixed labels, and the full row's minimum width. The
[1280×800 capture](../../scratch/H209-toolbar-1280.png) shows the full row through Properties.

Changed from the brief: The commit hook regenerated `docs/dependency-map.md` to record the toolbar's use of `tool_registry.gd`.

Result: b393296; full merge gate and recorded quick test passed with 408 quick viewport checks; toolbar labels show their shortcuts and fit at 1280 pixels.
