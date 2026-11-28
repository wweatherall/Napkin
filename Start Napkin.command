#!/bin/bash
# Opens Napkin. It starts its own FreeCAD worker (and starts it again if it stops); log: worker.log.
# The model is models/model.FCStd: open it in FreeCAD any time (Napkin autosaves it).
source "$(dirname "$0")/common.sh"
case "$GD_VER" in
  4.6*|4.7*|4.8*|4.9*|5.*) ;;
  *) echo; echo "Napkin needs Godot 4.6 or newer (you have '$GD_VER')."
     echo "Get it from https://godotengine.org/download/macos/ and replace /Applications/Godot.app."
     read -p "Press Return to close"; exit 1 ;;
esac
MODEL="$PWD/models/model.FCStd"
[ "$1" != "" ] && MODEL="$1"          # or drag a .FCStd onto the Terminal command line
echo "Opening $MODEL"
DRAW=""
command -v python3 >/dev/null && DRAW="--drawing=$PWD/worker/drawing.py"
"$GD" --path viewport -- --model="$MODEL" --out="$PWD/models/out" $DRAW \
  --freecad="$FC" --worker="$PWD/worker/replay.py" --worker-log="$PWD/worker.log"
echo "Napkin closed; its worker saved and stopped."
