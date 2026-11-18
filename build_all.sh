#!/bin/sh
# Zbuduj pakiety instalacyjne dla Debian, Ubuntu i Fedora jednym poleceniem.
# Użycie: ./packaging/build_all.sh
set -e

ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"

echo "==> Debian i Ubuntu (.deb)"
sh packaging/build_deb.sh

echo "==> Fedora (.rpm)"
sh packaging/build_rpm.sh

echo "==> Gotowe pliki:"
find dist/debian dist/ubuntu dist/fedora -maxdepth 1 -type f \
    \( -name '*.deb' -o -name '*.rpm' \) -print | sort
