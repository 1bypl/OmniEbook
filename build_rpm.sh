#!/bin/sh
# Build a Fedora 40+ .rpm package for OmniEbook.
# Usage: ./packaging/build_rpm.sh
set -e

ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"

VERSION="1.3.0"
NAME="omniebook"
TARBALL="${NAME}-${VERSION}.tar.gz"

# Jeśli system nie ma rpmbuild, używamy wbudowanego budowniczego w Pythonie.
if ! command -v rpmbuild >/dev/null 2>&1; then
    echo "==> rpmbuild nie jest dostępny - używam wbudowanego budowniczego Python."
    exec python3 "$ROOT/packaging/build_rpm_py.py"
fi

RPMROOT="${HOME}/rpmbuild"
mkdir -p "$RPMROOT"/{BUILD,BUILDROOT,RPMS,SOURCES,SPECS,SRPMS}

echo "==> Tworzenie archiwum źródeł..."
# %autosetup -n omniebook-1.3.0 requires that exact top-level directory.
STAGE=$(mktemp -d)
SRCDIR="$STAGE/${NAME}-${VERSION}"
mkdir -p "$SRCDIR/packaging"
cp -a omniebook data bin meson.build pyproject.toml README.md LICENSE "$SRCDIR/"
cp -a packaging/debian "$SRCDIR/packaging/"
find "$SRCDIR" -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true

rm -f "$TARBALL"
tar -C "$STAGE" -czf "$TARBALL" "${NAME}-${VERSION}"
rm -rf "$STAGE"

cp "$TARBALL" "$RPMROOT/SOURCES/"
cp packaging/fedora/omniebook.spec "$RPMROOT/SPECS/"

echo "==> Budowa pakietu RPM..."
rpmbuild -ba "$RPMROOT/SPECS/omniebook.spec"

echo "==> Gotowe. Pakiety:"
find "$RPMROOT/RPMS" -name "${NAME}-*.rpm" -print

RPMFILE=$(find "$RPMROOT/RPMS" -name "${NAME}-*.noarch.rpm" | sort | head -n1)
if [ -n "$RPMFILE" ]; then
    cp "$RPMFILE" "$ROOT/"
    echo "==> Skopiowano do: $ROOT/$(basename "$RPMFILE")"
    echo "==> Instalacja: sudo dnf install ./$(basename "$RPMFILE")"
fi
rm -f "$TARBALL"
