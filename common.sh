# shared by the .command launchers: find FreeCAD's command-line program and Godot
cd "$(dirname "$0")"
FC=""
for c in /Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd \
         /Applications/FreeCAD.app/Contents/Resources/bin/FreeCADCmd \
         /Applications/FreeCAD.app/Contents/MacOS/freecadcmd \
         /Applications/FreeCAD.app/Contents/MacOS/FreeCADCmd; do
  [ -x "$c" ] && FC="$c" && break
done
GD=/Applications/Godot.app/Contents/MacOS/Godot
if [ -z "$FC" ]; then echo "Couldn't find FreeCAD's command-line program inside /Applications/FreeCAD.app"; read -p "Press Return to close"; exit 1; fi
if [ ! -x "$GD" ]; then echo "Couldn't find /Applications/Godot.app"; read -p "Press Return to close"; exit 1; fi
FC_VER=$("$FC" -c "import FreeCAD; print('FCVER', '.'.join(FreeCAD.Version()[:3]))" 2>/dev/null | grep '^FCVER' | cut -d' ' -f2)
GD_VER=$("$GD" --version 2>/dev/null | tail -1)
echo "FreeCAD: $FC_VER   ($FC)"
echo "Godot:   $GD_VER"
