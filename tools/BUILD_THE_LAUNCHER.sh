#!/bin/bash
# Makes Napkin.app in the code base's folder: click it (or keep it in the Dock) and it builds Shop Sketch from this
# checkout if main has moved since the last build (tools/build_app.sh), then opens dist/Shop Sketch.app.
# Run it once; run it again only if the folder moves. Napkin.app is local to this Mac (it holds this folder's path).
set -euo pipefail
cd "$(dirname "$0")/.."
REPO="$PWD"
L="Napkin.app/Contents"
rm -rf Napkin.app
mkdir -p "$L/MacOS" "$L/Resources"

cat > "$L/MacOS/Napkin" <<SCRIPT
#!/bin/bash
# Napkin: build the latest Shop Sketch if this checkout has moved since the last build, then open it.
cd "$REPO" || exit 1
APP="dist/Shop Sketch.app"
if pgrep -f "\$APP/Contents/MacOS" > /dev/null; then open "\$APP"; exit 0; fi   # already open: bring it forward
WANT=\$(git describe --always --dirty 2>/dev/null || echo dev)
HAVE=\$(/usr/libexec/PlistBuddy -c "Print :CFBundleVersion" "\$APP/Contents/Info.plist" 2>/dev/null || echo none)
if [ "\$WANT" != "\$HAVE" ]; then
  mkdir -p dist
  osascript -e 'display notification "Building the latest Shop Sketch…" with title "Napkin"'
  if ! tools/build_app.sh > dist/launcher-build.log 2>&1; then
    osascript -e 'display alert "Napkin couldn'"'"'t build Shop Sketch" message "The build log is dist/launcher-build.log in the Napkin folder."'
    exit 1
  fi
fi
open "\$APP"
SCRIPT
chmod +x "$L/MacOS/Napkin"

ICON_TMP=$(mktemp -d)
qlmanage -t -s 1024 -o "$ICON_TMP" tools/icon.svg > /dev/null 2>&1
mkdir -p "$ICON_TMP/Napkin.iconset"
for s in 16 32 128 256 512; do
  sips -z $s $s "$ICON_TMP/icon.svg.png" --out "$ICON_TMP/Napkin.iconset/icon_${s}x${s}.png" > /dev/null
  sips -z $((s * 2)) $((s * 2)) "$ICON_TMP/icon.svg.png" --out "$ICON_TMP/Napkin.iconset/icon_${s}x${s}@2x.png" > /dev/null
done
iconutil -c icns "$ICON_TMP/Napkin.iconset" -o "$L/Resources/Napkin.icns"
rm -rf "$ICON_TMP"

cat > "$L/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>Napkin</string>
  <key>CFBundleDisplayName</key><string>Napkin</string>
  <key>CFBundleExecutable</key><string>Napkin</string>
  <key>CFBundleIdentifier</key><string>local.shopsketch.napkin-launcher</string>
  <key>CFBundleIconFile</key><string>Napkin</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>LSMinimumSystemVersion</key><string>12.0</string>
  <key>LSUIElement</key><true/>
</dict>
</plist>
PLIST
codesign --force -s - Napkin.app > /dev/null 2>&1
echo "Made Napkin.app in $REPO: click it to build (when needed) and open Shop Sketch; drag it to the Dock to keep it there."
