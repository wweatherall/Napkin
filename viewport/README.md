# Shop Sketch viewport (Godot 4.6), v0.1

Tool-first, no modes. Everything you do is recorded as an op (`oplog/0.1`); the FreeCAD worker
replays the log and the viewport swaps amber **draft** geometry for the confirmed mesh.

## Run it on your machine
1. Install Godot 4.6 and FreeCAD 1.1 (or newer).
2. Open this folder in Godot and press Play, or from a terminal:
   `godot --path . -- --drawing=$(realpath ../worker/drawing.py)`
   Shop Sketch starts its own FreeCAD worker on a free port (and again if it stops). It looks for
   freecadcmd in /Applications/FreeCAD.app; override with `--freecad=/path/to/freecadcmd`,
   `--worker=/path/to/replay.py`, `--worker-log=/path/worker.log` (default `user://worker.log`).
   `--port=N` uses a worker you started yourself instead (`SERVE_PORT=N freecadcmd ../worker/replay.py`); tests do this.
   For PDFs from the Drawing button, run `pip install cairosvg`; without it you get the SVG plus the TechDraw page in model.FCStd.

Your op log autosaves to Godot's `user://ops.json` (reopened on next launch); outputs go to `user://out/`.
Override with `-- --oplog=/path/ops.json --out=/path/outdir`.

## Controls
| | |
|---|---|
| R | Rectangle: click a face or the ground, click again or type `width,height` Enter |
| P | Push/Pull: click a rectangle or face, move, click or type a distance Enter (minus = cut) |
| M | Move: grab a point on a board, move, click or type a distance. Drag roughly along an axis and it sticks (dotted line); snaps to endpoints, midpoints, edges and other boards' faces; free moves slide at the grab height. Tap an arrow to cycle: lock to that axis → lock to the plane perpendicular to it → free. Tap Ctrl (Option on Mac) to toggle copy, tap Shift to toggle mirror (the board flips across the plane halfway to the cursor; typed number = grabbed face to plane). Option+Shift = linked mirrored copy. After a copy type `5x` / `*5` for an array or `/5` to spread copies; a plain number right after a move changes its distance |
| Ctrl+Z | undo last op (shown at once; FreeCAD catches up) |
| D | drawing + cut list (PDF) |
| G / B | grid snap 10 mm / "new board" when pushing a rectangle drawn on a face |
| Esc | cancel current tool action |
| middle or right drag | orbit; with Shift, pan; wheel zooms toward the cursor |
| trackpad | two fingers orbit; Shift + two fingers pan; pinch zooms toward the cursor |

Snapping: corners within 14 px (green dot), otherwise the 10 mm grid. Typed values follow the direction
you're dragging, as in SketchUp.

## The operation wave
When you finish a push/pull, a colour wave starts at once from where your cursor ended. It runs to about 80%
and breathes there until FreeCAD answers (usually well before then):
- accepted: it completes into the real material. New boards start amber; edits only get a soft pigment ripple.
- rejected: a red wave travels back toward the cursor. A new board fades away, an edit gets a red ring,
  the op is removed from the log, and the reason stays in the status bar.
Settings worth adjusting are at the top of `confirm_wave.gdshader`: `softness`, `pigment_strength`, `cell_size`, and the colours.
`HOLD` and `REJECT_DUR` are in `main.gd`. Cut previews are violet so red stays reserved for rejections.

## Rules worth knowing
- A rectangle on the ground becomes a new board. A rectangle on a face becomes a new board when
  "new board" is on; otherwise it merges into that board. A negative push always cuts the board under it.
- Pushing an existing face always edits that board.
- You can keep working on draft boards before FreeCAD confirms them.

## Not yet
Components and materials UI, inference beyond corners and grid (midpoints, on-edge,
parallel), selection, and a Metal renderer. The project uses the Compatibility renderer so it runs
anywhere. On a Mac, switch to Forward+ in Project Settings to get Metal.
