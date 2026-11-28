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
FC_VER=""
if mkdir -p scratch && FC_PROBE=$(mktemp -d "$PWD/scratch/freecad-version.XXXXXX"); then
  FC_VER=$("$FC" -u "$FC_PROBE/user.cfg" -s "$FC_PROBE/system.cfg" --version 2>/dev/null | awk '$1 == "FreeCAD" {print $2; exit}')
  rm -rf "$FC_PROBE"
fi
GD_VER=$("$GD" --version 2>/dev/null | tail -1)
echo "FreeCAD: $FC_VER   ($FC)"
echo "Godot:   $GD_VER"
