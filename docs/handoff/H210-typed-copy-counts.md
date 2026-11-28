### H210 — Typed copy counts: 5x, x5, *5 (and 5*) all work after a move or copy (T167)

Author: Claude (integrator, opus-integrator) | Date: 2026-11-28 | Status: answered | For: codex | Item: T167

References: T167 (William, 2026-11-28: "having trouble with the times feature, maybe we should make x5 as well as 5x,
*5 too work if there aren't side effects"), G06 (typed values understood however you write them), G03 (SketchUp:
type 5x or *5 after a copy-move for an array, /5 to divide), `viewport/tools/move_tool.gd` `_parse_array`, `accepts`,
`typed`, `_amend_last_move`; `viewport/measure_box.gd` `apply`; `viewport/tools/tool.gd` `accepts`.

Today: `_parse_array` already reads "5x", "x5", "*5" and "/5". So William's trouble is upstream of it, and finding
where is the job. Candidates seen reading the code (check each, don't assume): `tool.gd` `accepts` lets letters in
only once something is typed, and `move_tool.gd` adds "x" as a first key; "*5" or "5*" may be read as arithmetic by
the measure box before `_parse_array` sees it; X may be bound as a key (`viewport/keys.gd`) that wins before the
tool; amending after a move (`_amend_last_move`) may take a different path from typing during one; Push/Pull's
copies (Option-push, if it takes counts) may not parse counts at all.

Touches: viewport/tools/move_tool.gd, viewport/measure_box.gd (count text only), viewport/tools/tool.gd (`accepts`
only), viewport/tools/push_tool.gd (only if Option-push copies take counts and don't parse them; ask before changing it),
a viewport test (`viewport/test_tools.gd` or the move tool's test), a quick-test step.

Request:
1. Reproduce William's trouble: in the app, copy-move a board (Option while moving), then type each of "5x", "x5",
   "*5", "5*", "/5" + Enter, both right after the move and during it. Write down which ones fail and why
   (the exact function where the text goes wrong) in the response.
2. Make all five work in both places: "5x", "x5", "*5", "5*" give 5 copies; "/5" divides. Keep plain lengths and
   arithmetic working ("50*2" is still 100 mm while dragging a distance: a count only when the text is a bare whole
   number with one x or * and nothing else). That rule is what "no side effects" means: no length that worked
   before reads differently.
3. If anything here would change what a typed value means elsewhere (another tool's arithmetic), stop and ask the
   integrator before changing it.

Checks:
- A named check per form ("5x", "x5", "*5", "5*", "/5") after a move and during one, and one that "50*2" while
  dragging is still a 100 mm distance.
- `tools/TEST_BEFORE_MERGING.sh` passes.

Response — Codex, 2026-11-28 (`codex/h210-typed-copy-counts`, code commit `ecec8bb`).

Reproduced in the app with an Option-copy of a board and viewport keyboard events, including Shift+8 for the asterisk.

| Form | During the copy-move before the fix | Right after the copy-move before the fix |
|---|---|---|
| `5x` | Previewed and committed five copies at the dragged spacing | Amended to five copies at that spacing |
| `x5` | Previewed and committed five copies at the dragged spacing | Amended to five copies at that spacing |
| `*5` | Shift switched to Mirror, Return ignored the count, and clicking committed a mirror | Amended to five copies, with Mirror left on |
| `5*` | Return sent a length request and the click committed one copy | Return sent a length request and the original single copy stayed |
| `/5` | Previewed and committed five copies across the dragged distance | Amended to five copies across that distance |

`Move.key()` toggled Mirror as soon as Shift went down. `Move.typed()` then took its mirror branch
during the gesture, while the post-click path went straight to `_amend_last_move()`. `MeasureBox.apply()`
omitted trailing `*` from its count matcher and sent `5*` to the length evaluator before Move could see it.
`Move.accepts()` already accepts leading `x`, the base `Tool.accepts()` already accepts `*` and `/`,
and the input dispatch gives a busy Move the character before tool shortcuts. Push/Pull uses Option
to cycle the fit end condition (I41) and has no copy-count path.

Move now supplies the same whole-number count parser to Measurements, its live preview, and its amendment
path. The quick test names each form in both paths and checks the positions FreeCAD confirmed. It also
checks that `50*2` moves the board 100 mm without a worker length request. The existing mirror suites
still pass with a standalone Shift tap. No new decision IDs or open questions.

Changed from the brief: `viewport/keys.gd` forwards Move's Shift events and intervening key presses through its existing early input path so Move can distinguish a standalone tap on release from Shift+8.

Result: ecec8bb; merge gate and recorded `job.py test` passed with 416 quick viewport checks, full suites and field audit passed at the gate; all five count forms work during and immediately after an Option-copy, and length arithmetic still works.
