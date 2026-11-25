### H137 — T123: Move array live preview before click and amend after click

Author: Gemini (integrator, gemini-cedar-1124-0100) | Date: 2026-11-24 | Status: answered | For: either

References: T123, I66, I14, I25, G03, G06, G13.

Touches: viewport/tools/move_tool.gd, viewport/tests/quick/move.gd. Not viewport/measure_box.gd (line 233 already routes `^(?:[0-9]+x|[x*][0-9]+|/[0-9]+)$` directly to `move.typed(txt)` without length evaluation; ask with `job.py wait --scope` if a change there is needed).

Why: I66 (William, 2026-11-24) specifies that typing an array multiplier (`x8`, `8x`, `*8`) or divisor (`/8`) *during* a Move previews the array live before clicking (and commits all copies on click or typed distance), while post-click typing before any other action continues to amend the count or spacing/span.

Today (checked 2026-11-24):
- `viewport/tools/move_tool.gd`:
  - `state` already initializes `"count": 1, "divide": false` (~279), and `_preview_move()` (~378–389) already iterates `_move_offsets(state["vec"], state["count"], state["divide"], copy)`!
  - `typed(txt)` (~83–105): when `state.get("active", false)` is true and not mirroring, it only handles `tl.is_valid_float()` and commits `commit_move(state["vec"].normalized() * absf(float(tl)))` — ignoring `xN`/`Nx`/`*N`/`/N` completely and never passing `state["count"]` or `state["divide"]`!
  - `_finish()` (~287–295) calls `commit_move(state["vec"])`, dropping `state["count"]` and `state["divide"]` (defaulting to `1, false`).
  - `_amend_last_move(txt)` (~497–525) parses `/N`, `Nx`, `xN`, `*N`, and float distances after commit.
- `viewport/measure_box.gd` (`apply`, ~230–235): already recognizes `^(?:[0-9]+x|[x*][0-9]+|/[0-9]+)$` when `tool == "move"` and calls `active.typed(txt)` directly.

Request:
1. Extract a tiny shared helper in `viewport/tools/move_tool.gd`, e.g. `_parse_array(txt: String) -> Dictionary`, returning `{"ok": true, "count": maxi(1, n), "divide": bool}` for `Nx`, `xN`, `*N`, and `/N` (or `{"ok": false}` otherwise), used by both active `typed()` and `_amend_last_move()` so the syntax never drifts.
2. In `typed(txt)` while `state.get("active", false)` (and not `mirror`):
   - If `_parse_array(txt)` succeeds:
     - Enable `copy = true` (if not already on, so typing `x8` mid-move immediately enters copy-array preview without forcing the user to tap Option first — the point of previewing before clicking).
     - Set `state["count"] = parsed.count` and `state["divide"] = parsed.divide`.
     - Call `_preview_move()` and `ctx.ui.refresh_tip(ctx.pick.cursor())`, and **return without committing**, so the user sees all N copies live as they move the cursor (and can type a different count like `x4` or `/5`, click to place, or type a distance to commit!).
   - If `tl.is_valid_float()` and `state["vec"].length() >= GEOMETRY_TOLERANCE_MM`:
     - Commit with `commit_move(state["vec"].normalized() * absf(float(tl)), state.get("count", 1), state.get("divide", false))`.
3. In `_finish()`:
   - Pass `state.get("count", 1)` and `state.get("divide", false)` to `commit_move(state["vec"], state.get("count", 1), state.get("divide", false))`.
4. Update `tip()` (~129–131) and `vcb_label()` (~108–109) during an active array preview so the user sees the active count (e.g. `Copy ×8` or `Divide /8` in the tooltip/label when `copy` and `state.get("count", 1) > 1`).
5. Keep post-click `_amend_last_move()` working identically for both distance and count/divide changes (including amending an array that was already previewed and committed with `x8` -> e.g. changing it to `x5`, `/4`, or a new spacing before any other action).
6. Verify hole arrays (`state.get("cut")`) and assembly arrays work through the same pre-click preview + commit path (since both `commit_move` and `_commit_cut_move` already accept `count` and `divide`).

Cases that must still work:
- Plain move, Option-copy single copy, post-click `5x` / `x5` / `*5` / `/5` and post-click distance amend, mirror move (`Shift`), hole-array move/copy, assembly-row move/copy, and all existing checks in `viewport/tests/quick/move.gd`.

Checks (new, named) in `viewport/tests/quick/move.gd`:
1. Start a Move on a board, drag along an axis, type `x4` + Enter **before clicking**: stays active (`in_gesture() == true`), enables copy mode, preview geometry contains 4 shifted copies (at `1×..4×` vector), and clicking commits all 4 copies in one op.
2. Start a Move+Copy, type `/3` + Enter before clicking, then type `300` + Enter: commits 3 evenly distributed copies spanning 300 mm (at 100, 200, 300 mm).
3. After clicking to commit a pre-previewed `x4` array, type `x2` + Enter before any other action: amends the committed array down to 2 copies cleanly.
4. After clicking to commit a pre-previewed `x3` array, type `250` + Enter: amends spacing to 250 mm while keeping all 3 copies.

Reading path: `viewport/tools/move_tool.gd` (`typed`, `vcb_label`, `tip`, `_finish`, `_move_offsets`, `_preview_move`, `commit_move`, `_amend_last_move`) → `viewport/measure_box.gd` (`apply`, lines 224–240) → `viewport/tests/quick/move.gd`.

Run `tools/quicktest.sh` while building, then `python3 tools/job.py test`. End your response with `Follow-up:` lines for leftovers and a `Result:` line.

**Response (Gemini, 2026-11-24):**
Branch: `gemini/h137-t123-move-array-live-preview`, commit: `9bea6be`.

- Extracted `_parse_array(txt: String) -> Dictionary` in `viewport/tools/move_tool.gd` and shared it between active `typed(txt)` and `_amend_last_move(txt)`.
- In active `typed(txt)` (when not mirroring): array multipliers/divisors (`Nx`, `xN`, `*N`, `/N`) enable `copy = true`, update `state["count"]` and `state["divide"]`, refresh the live preview (`_preview_move()`) and tip (`ctx.ui.refresh_tip(ctx.pick.cursor())`), and return without committing. Typed distances and `_finish()` now pass `state.get("count", 1)` and `state.get("divide", false)` to `commit_move(...)`.
- Updated `vcb_label()` and `tip()` to display `Copy ×N` or `Divide /N` during an active array preview (`copy` and `state.get("count", 1) > 1`).
- Added the 4 requested named checks to `viewport/tests/quick/move.gd` (pre-click `x4` live preview + click commit, post-click `x2` amend, pre-click `/3` + `300` commit, and pre-click `x3` + click + post-click `250` spacing amend).
- Verified `python3 tools/job.py test` on `9bea6be`: all 355 viewport quick checks and all feature test suites passed.
- IDs added: none. Open questions: none.

Follow-up: none.
Result: 9bea6be; quicktest passed (355 viewport quick, all feature suites); Move array live preview before click and amend after click
