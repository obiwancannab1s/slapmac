#!/bin/bash
# Convert project-root slapapp.png into an .icns for the app bundle Resources
set -e
ROOT_DIR="$(cd "$(dirname "$0")/../../.." && pwd)"
SRC="$ROOT_DIR/slapapp.png"
DEST_DIR="$(cd "$(dirname "$0")" && pwd)"

if [ ! -f "$SRC" ]; then
  echo "Error: slapapp.png not found in project root ($SRC)"
  exit 2
fi

TMPDIR=$(mktemp -d)
ICONSET="$TMPDIR/SlapMac.iconset"
mkdir -p "$ICONSET"

sips -z 16 16     "$SRC" --out "$ICONSET/icon_16x16.png"
sips -z 32 32     "$SRC" --out "$ICONSET/icon_16x16@2x.png"
sips -z 32 32     "$SRC" --out "$ICONSET/icon_32x32.png"
sips -z 64 64     "$SRC" --out "$ICONSET/icon_32x32@2x.png"
sips -z 128 128   "$SRC" --out "$ICONSET/icon_128x128.png"
sips -z 256 256   "$SRC" --out "$ICONSET/icon_128x128@2x.png"
sips -z 256 256   "$SRC" --out "$ICONSET/icon_256x256.png"
sips -z 512 512   "$SRC" --out "$ICONSET/icon_256x256@2x.png"
sips -z 512 512   "$SRC" --out "$ICONSET/icon_512x512.png"
sips -z 1024 1024 "$SRC" --out "$ICONSET/icon_512x512@2x.png"

iconutil -c icns "$ICONSET" -o "$DEST_DIR/slapapp.icns"
rm -rf "$TMPDIR"

echo "Created $DEST_DIR/slapapp.icns"
exit 0
