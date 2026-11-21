#!/bin/bash
# Builds "dist/Shop Sketch.app" for this Mac: the viewport packed into Resources, run by a copy of the Godot
# program (no export templates needed), plus the FreeCAD worker scripts. Ad-hoc signed: for this machine.
# Needs /Applications/Godot.app (4.6+) to build, and FreeCAD in /Applications to run.
set -euo pipefail
cd "$(dirname "$0")/.."
GD=/Applications/Godot.app/Contents/MacOS/Godot
APP="dist/Shop Sketch.app"
C="$APP/Contents"
rm -rf "$APP"
mkdir -p "$C/MacOS" "$C/Resources/worker"

echo "Packing the viewport..."
"$GD" --headless --path viewport --export-pack "macOS" "$PWD/$C/Resources/Shop Sketch.pck" > dist/pack.log 2>&1 \
  || { tail -20 dist/pack.log; exit 1; }
cp "$GD" "$C/MacOS/Shop Sketch"              # Godot runs "<its name>.pck" from Resources
cp worker/replay.py worker/drawing.py worker/materials.py "$C/Resources/worker/"
mkdir -p "$C/Resources/materials" && cp -R materials/textures "$C/Resources/materials/"     # wood (T15)

echo "Icon..."
ICON_TMP=$(mktemp -d)
qlmanage -t -s 1024 -o "$ICON_TMP" tools/icon.svg > /dev/null 2>&1
mkdir -p "$ICON_TMP/ShopSketch.iconset"
for s in 16 32 128 256 512; do
  sips -z $s $s "$ICON_TMP/icon.svg.png" --out "$ICON_TMP/ShopSketch.iconset/icon_${s}x${s}.png" > /dev/null
  sips -z $((s * 2)) $((s * 2)) "$ICON_TMP/icon.svg.png" --out "$ICON_TMP/ShopSketch.iconset/icon_${s}x${s}@2x.png" > /dev/null
done
iconutil -c icns "$ICON_TMP/ShopSketch.iconset" -o "$C/Resources/ShopSketch.icns"
rm -rf "$ICON_TMP"

VERSION=$(git describe --always --dirty 2>/dev/null || echo dev)
cat > "$C/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>Shop Sketch</string>
  <key>CFBundleDisplayName</key><string>Shop Sketch</string>
  <key>CFBundleExecutable</key><string>Shop Sketch</string>
  <key>CFBundleIdentifier</key><string>local.shopsketch</string>
  <key>CFBundleIconFile</key><string>ShopSketch</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>0.2</string>
  <key>CFBundleVersion</key><string>$VERSION</string>
  <key>LSMinimumSystemVersion</key><string>12.0</string>
  <key>NSHighResolutionCapable</key><true/>
  <key>LSApplicationCategoryType</key><string>public.app-category.graphics-design</string>
</dict>
</plist>
PLIST

codesign --force --deep -s - "$APP" > /dev/null 2>&1
echo "Built $APP ($(du -sh "$APP" | cut -f1)). Open it, or drag it to /Applications."
