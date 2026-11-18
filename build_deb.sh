#!/bin/sh
# Build a Debian/Ubuntu .deb package for OmniEbook.
# Usage: ./packaging/build_deb.sh
set -e

ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"

VERSION="1.3.0"
REVISION="1"
PKG="omniebook_${VERSION}-${REVISION}_all"
OUTPUT="$ROOT/${PKG}.deb"

# Jeśli system nie ma dpkg-deb, używamy wbudowanego budowniczego w Pythonie.
if ! command -v dpkg-deb >/dev/null 2>&1; then
    echo "==> dpkg-deb nie jest dostępny - używam wbudowanego budowniczego Python."
    exec python3 "$ROOT/packaging/build_deb_py.py"
fi

# Clean Python bytecode caches created during development
find omniebook -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true

TMP=$(mktemp -d)
STAGE="$TMP/$PKG"
mkdir -p "$STAGE/DEBIAN"

if command -v meson >/dev/null 2>&1 && command -v ninja >/dev/null 2>&1; then
    echo "==> Building with meson..."
    rm -rf build-deb
    meson setup build-deb --prefix=/usr
    DESTDIR="$STAGE" meson install -C build-deb
else
    echo "==> meson not found - installing files manually..."
    mkdir -p "$STAGE/usr/bin" \
             "$STAGE/usr/lib/omniebook" \
             "$STAGE/usr/share/applications" \
             "$STAGE/usr/share/metainfo" \
             "$STAGE/usr/share/icons/hicolor/scalable/apps" \
             "$STAGE/usr/share/doc/omniebook"
    install -m 755 bin/omniebook "$STAGE/usr/bin/omniebook"
    cp -a omniebook/. "$STAGE/usr/lib/omniebook/"
    install -m 644 data/*.desktop "$STAGE/usr/share/applications/"
    install -m 644 data/*.appdata.xml "$STAGE/usr/share/metainfo/"
    install -m 644 data/icons/hicolor/scalable/apps/*.svg \
        "$STAGE/usr/share/icons/hicolor/scalable/apps/"
    install -m 644 LICENSE README.md "$STAGE/usr/share/doc/omniebook/"
fi

# Debian control metadata
cp packaging/debian/control "$STAGE/DEBIAN/control"
for file in postinst prerm; do
    if [ -f "packaging/debian/$file" ]; then
        cp "packaging/debian/$file" "$STAGE/DEBIAN/$file"
        chmod 755 "$STAGE/DEBIAN/$file"
    fi
done
if [ -f packaging/debian/copyright ]; then
    mkdir -p "$STAGE/usr/share/doc/omniebook"
    cp packaging/debian/copyright "$STAGE/usr/share/doc/omniebook/copyright"
fi

echo "==> Packing $OUTPUT"
dpkg-deb --build --root-owner-group "$STAGE" "$OUTPUT"
rm -rf "$TMP"

echo "==> Gotowe: $OUTPUT"
echo "==> Instalacja: sudo apt install ./$PKG.deb"
