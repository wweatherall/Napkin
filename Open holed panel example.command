#!/bin/bash
# Opens a copy of the 32-hole panel from the breathing video (pushing its top face takes FreeCAD a while).
cd "$(dirname "$0")"
mkdir -p models/example
cp -f examples/holed_panel.FCStd models/example/holed_panel.FCStd
cp -f examples/holed_panel.shopsketch.json models/example/holed_panel.shopsketch.json
exec "./Start Shop Sketch.command" "$PWD/models/example/holed_panel.FCStd"
