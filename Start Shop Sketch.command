#!/bin/bash
# Starts the FreeCAD worker in the background, then the Shop Sketch window.
# The model is models/model.FCStd: open it in FreeCAD any time (Shop Sketch autosaves it).
source "$(dirname "$0")/common.sh"
case "$GD_VER" in
  4.6*|4.7*|4.8*|4.9*|5.*) ;;
  *) echo; echo "Shop Sketch needs Godot 4.6 or newer (you have '$GD_VER')."
     echo "Get it from https://godotengine.org/download/macos/ and replace /Applications/Godot.app."
     read -p "Press Return to close"; exit 1 ;;
esac
PORT=7878
MODEL="$PWD/models/model.FCStd"
[ "$1" != "" ] && MODEL="$1"          # or drag a .FCStd onto the Terminal command line
if lsof -iTCP:$PORT -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Something is already listening on port $PORT (an old worker?). Stopping it."
  kill $(lsof -tiTCP:$PORT -sTCP:LISTEN) 2>/dev/null; sleep 1
fi
echo "Starting FreeCAD worker (log: worker.log)..."
SERVE_PORT=$PORT "$FC" worker/replay.py > worker.log 2>&1 &
WORKER=$!
trap 'kill $WORKER 2>/dev/null' EXIT
for i in $(seq 1 60); do
  grep -q "WORKER listening" worker.log 2>/dev/null && break
  if ! kill -0 $WORKER 2>/dev/null; then echo "The FreeCAD worker stopped:"; tail -20 worker.log; read -p "Press Return to close"; exit 1; fi
  sleep 0.5
done
echo "Worker ready. Opening $MODEL"
DRAW=""
command -v python3 >/dev/null && DRAW="--drawing=$PWD/worker/drawing.py"
"$GD" --path viewport -- --model="$MODEL" --port=$PORT --out="$PWD/models/out" $DRAW
echo "Shop Sketch closed; the worker saves and stops."
sleep 1
