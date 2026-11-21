Shop Sketch - Mac

1. Double-click "Start Shop Sketch.command".
   First time only: macOS may refuse to open it because it was downloaded.
   Right-click it > Open > Open (or run:  xattr -dr com.apple.quarantine <this folder>).
2. The Shop Sketch window opens; it runs FreeCAD in the background (and restarts it if it stops).
   Your model is models/model.FCStd. It autosaves; open it in FreeCAD whenever you like
   (close Shop Sketch first: watching the file for FreeCAD's changes is stage 2).
3. Keys: R rectangle, P push/pull, M move (Option = copy, Shift = mirror), arrows lock axes,
   type a number + Return, Cmd+Z (or Ctrl+Z) undo, D drawing.
   Orbit: middle/right drag, or two fingers on a trackpad. Pan: Shift+drag (Shift+two fingers).
   Zoom: wheel, or pinch.
   Holes: M on a hole's wall grabs the hole. Option = copy; type a spacing, then 8x (or /8) for a row.

Also here:
- "Open holed panel example.command": the 32-hole panel from the breathing video.
- "Check FreeCAD speed.command": times 24 chained cuts in your FreeCAD (open question Q18).

Needs: FreeCAD 1.0 or newer and Godot 4.6 or newer, both in /Applications.
