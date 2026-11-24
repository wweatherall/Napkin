### H136 — T122: Rectangle after-the-fact typed dimensions

Author: Gemini (integrator, gemini-cedar-1124-0100) | Date: 2026-11-24 | Status: open | For: either

References: T122, I65, I02, I14, G03, G06.

Touches: viewport/tools/rect_tool.gd, viewport/tests/quick/rect.gd. Not viewport/keys.gd or viewport/measure_box.gd (both already route typed pairs to `rect.typed()` whenever `busy()` is true; ask with `job.py wait --scope` if a change there is needed).

Why: I65 (William, 2026-11-24) specifies that typing `width, height` + Enter right after placing a rectangle — before clicking again, switching tools, undoing, or taking any other action — alters that rectangle's dimensions, matching Move's after-the-fact typing (I14) and SketchUp (G03).

Today (checked 2026-11-24):
- `viewport/tools/rect_tool.gd`:
  - `busy()` (~20) returns `state.get("active", false)` and inherits `in_gesture() -> busy()` from `tool.gd`.
  - `typed(txt)` (~54–61) returns early unless `state.get("active", false)` is true.
  - `commit_rect(du, dv)` (~107–122) allocates `rid := ctx.document.next_id("r")`, appends the `rect` op, calls `ctx.view.register_profile(op)`, clears `state = {}`, clears preview, and syncs. Nothing remembers the just-created rectangle.
- `viewport/tools/move_tool.gd` (~12, 27–32, 83–86, 497–525) shows the exact established pattern for post-commit typing: `last_oid`, `busy()` returning `state.get("active", false) or last_oid != ""`, `in_gesture()` returning `state.get("active", false)` (so Esc still clears selection/context rather than thinking a gesture is active), and `_amend_last_move(txt)` calling `ctx.document.remove(last_oid)` then re-committing with `reuse_oid`.
- `viewport/tools/tool.gd` `accepts(ch)` (~70) accepts digits/operators when `typed_text() == ""`, and letters/units once typing has started — so pressing `P`, `M`, `L`, `Space`, etc. when `last_oid != ""` and the box is empty still switches tools normally instead of entering text.

Request:
1. Track the just-created rectangle in `viewport/tools/rect_tool.gd` (e.g. `last_oid := ""` plus a small `last_meta := {}` holding `origin`, `n`, `x`, `y`, `on`, `su`, `sv`, `du`, `dv`):
   - `busy()` returns `state.get("active", false) or last_oid != ""` so digits typed right after creation enter the measurements box.
   - `in_gesture()` returns `state.get("active", false)` so Esc behaves per I38 when idle after a rectangle.
   - `reset()` clears `state`, `press_reset()`, and `last_oid = ""` / `last_meta = {}` (so switching tools or pressing Esc ends amending).
   - Starting a new rectangle in `click()` clears `last_oid = ""` / `last_meta = {}` before setting the new `state`.
   - When `commit_rect(du, dv, reuse_oid := "")` commits:
     - Reuses `reuse_oid` when non-empty (preserving the rectangle's ID across amendments, per U02 / `worker/session.py` `creations()`), else allocates `ctx.document.next_id("r")`.
     - Records `last_oid = rid` and `last_meta` (`origin`, `n`, `x`, `y`, `on`, `su`, `sv`, `du`, `dv`).
   - In `typed(txt)`:
     - When `state.get("active", false)` is true: keep current behaviour (parse `w, h`, preserve drag signs `su`/`sv`, commit).
     - When not active and `last_oid != ""`: verify the rectangle is still the **last** op in the document (e.g. check `ctx.document.op(last_oid)` exists and no other op was added or consumed it — if another action happened or the op was undone/removed, clear `last_oid` and return without touching anything, so "before any other action" is strictly enforced). Parse `w, h` (rejecting non-positive or malformed pairs cleanly), call `ctx.document.remove(last_oid)` and re-commit with `w * su, h * sv` and `reuse_oid = last_oid`, keeping `last_oid` set so the user can even retype dimensions a second time before doing anything else!
   - `vcb_value()`: when not active and `last_oid != ""`, show the last rectangle's formatted dimensions (`"%s, %s"`) if its op is still present (matching SketchUp feedback that the rectangle is still amendable; clear if gone).
2. Rules (with purpose, P44):
   - Always check that `last_oid` is still the document's latest op before amending, so undo or a keyboard action (Delete, Hide, etc.) never silently mutates an older op.
   - Preserve `origin`, `plane`, and quadrant signs (`su`, `sv`) from the original drag so amending resizes in the same direction the user drew.

Cases that must still work:
- Active-drag typing (`w, h` + Enter before the second click), press-and-drag rectangles (I43), click-click rectangles, ground and on-face rectangles, immediate tool switch (`P`, `M`, `Space`) after placing a rectangle without eating the key, and `Undo` after amending (reverts cleanly in one step).

Checks (new, named) in `viewport/tests/quick/rect.gd`:
1. Place a rectangle by click-click, then type `200, 120` + Enter with no active drag: the single `rect` op keeps its ID/origin/plane/quadrant and updates to `200 × 120` in both the viewport profile draft and FreeCAD.
2. Retype `80, 90` + Enter a second time before any other action: updates again cleanly.
3. Place a rectangle, press `P` (Push/Pull): switches tools (not eaten by measurements box); returning to Rectangle does not amend the old rectangle.
4. Place a rectangle, undo it, then type `100, 100` + Enter: does nothing (does not resurrect or alter an earlier op).

Reading path: `viewport/tools/rect_tool.gd` → `viewport/tools/move_tool.gd` (`last_oid`, `busy`, `in_gesture`, `_amend_last_move`) → `viewport/keys.gd` (lines 26–52) → `viewport/measure_box.gd` (`apply`, lines 224–258) → `viewport/tests/quick/rect.gd`.

Run `tools/quicktest.sh` while building, then `python3 tools/job.py test`. End your response with `Follow-up:` lines for leftovers and a `Result:` line.
