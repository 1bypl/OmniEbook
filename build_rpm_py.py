#!/usr/bin/env python3
"""Build a Fedora noarch .rpm using only the Python standard library.

Fallback for build environments without ``rpmbuild``. An RPM file consists
of a 96-byte lead, a signature header, the main header and a compressed cpio
payload. This module writes exactly that structure (RPM v4, gzip payload).

Usage:  python3 packaging/build_rpm_py.py [--dist-tag fc45]
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import os
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NAME = "omniebook"
VERSION = "1.3.0"
RELEASE = "1"
SUMMARY = "Find, read and organise free ebooks, documents and audiobooks"
LICENSE = "GPL-3.0-or-later"
URL = "https://github.com/1bypl"
BUILDHOST = "localhost"
STAMP = int(os.environ.get("SOURCE_DATE_EPOCH", "1794960000"))

DESCRIPTION = """OmniEbook is a lightweight GTK4/libadwaita application for discovering
completely free ebooks, scientific documents and audiobooks. It searches
trusted open collections (Project Gutenberg, Open Library, Internet Archive,
arXiv, DOAJ, LibriVox) and the user's local library. It features a reader with
an animated page-turn effect, an audiobook player, favourites, collections,
seven interface languages and switchable skins. Document conversion uses the
LibreOffice engine through UNO.

Author: 1bypl - https://github.com/1bypl"""

POSTIN = """if [ -x /usr/bin/gtk4-update-icon-cache ]; then
    /usr/bin/gtk4-update-icon-cache -q -f -t /usr/share/icons/hicolor || :
elif [ -x /usr/bin/gtk-update-icon-cache ]; then
    /usr/bin/gtk-update-icon-cache -q -f -t /usr/share/icons/hicolor || :
fi
if [ -x /usr/bin/update-desktop-database ]; then
    /usr/bin/update-desktop-database -q /usr/share/applications || :
fi
"""

# Typy pól w nagłówku RPM (zgodne z rpmtag.h).
INT16, INT32, STRING, BIN, STRING_ARRAY, I18NSTRING = 3, 4, 6, 7, 8, 9

# Numery znaczników zaczerpnięte z oficjalnego pakietu OmniEbook 1.0.0,
# żeby metadane (m.in. zależności) pozostały identyczne jak w specyfikacji.
REQ_NAMES = [
    "/bin/sh", "/usr/bin/sh", "gstreamer1", "gstreamer1-libav",
    "gstreamer1-plugins-base", "gstreamer1-plugins-good", "gtk4",
    "hicolor-icon-theme", "libadwaita", "libreoffice-core",
    "libreoffice-pyuno", "poppler-utils", "python3", "python3-gobject",
    "rpmlib(CompressedFileNames)", "rpmlib(FileDigests)",
    "rpmlib(PayloadFilesHavePrefix)",
]
REQ_VERSIONS = [
    "", "", "", "", "", "", "", "", "", "", "", "", "3.9", "",
    "3.0.4-1", "4.6.0-1", "4.0-1",
]
REQ_FLAGS = [1280, 16384] + [0] * 10 + [12, 0, 16777226, 16777226, 16777226]
RECOMMEND_NAMES = ["gstreamer1-plugins-bad", "python3-pymupdf"]


# ------------------------------------------------------------------ nagłówki
def pack_header(entries: list[tuple[int, int, object]],
                region_tag: int | None = None) -> bytes:
    """Zbuduj strukturę Header: indeks + zbiór danych z odpowiednim wyrównaniem.

    ``region_tag`` to obowiązkowy wpis „region": 62 w nagłówku sygnatury
    i 63 w nagłówku głównym. Bez niego rpm czyta metadane, ale odmawia
    instalacji pakietu („package format not supported").
    """
    entries = sorted(entries, key=lambda e: e[0])
    store = bytearray()
    index: list[list[int]] = []
    region_position: int | None = None
    for tag, typ, value in entries:
        size = {INT16: 2, INT32: 4}[typ] if typ in (INT16, INT32) else 1
        while len(store) % size:
            store.append(0)
        offset = len(store)
        if tag == region_tag:
            count = 16
        elif typ in (INT16, INT32):
            fmt = ">H" if typ == INT16 else ">I"
            values = value if isinstance(value, (list, tuple)) else [value]
            for item in values:
                store += struct.pack(fmt, int(item))
            count = len(values)
        elif typ in (STRING, I18NSTRING):
            store += str(value).encode("utf-8") + b"\0"
            count = 1
        elif typ == STRING_ARRAY:
            for item in value:
                store += str(item).encode("utf-8") + b"\0"
            count = len(value)
        elif typ == BIN:
            store += value
            count = len(value)
        else:
            raise ValueError(f"Nieobsługiwany typ RPM: {typ}")
        index.append([tag, typ, offset, count])
        if tag == region_tag:
            region_position = len(index) - 1

    if region_tag is not None:
        if region_position is None:
            raise ValueError(f"Brak znacznika regionu {region_tag}")
        # Wpis w indeksie wskazuje na koniec zbioru danych, gdzie ląduje
        # 16-bajtowy marker powtarzający ten sam wpis z ujemnym offsetem.
        index[region_position][2] = len(store)
        # Ujemny offset zapisujemy jako liczbę bez znaku (np. -112 → 0xffffff90).
        negative_offset = (-(len(entries) * 16)) & 0xFFFFFFFF
        store += struct.pack(">IIII", region_tag, 7, negative_offset, 16)

    return (b"\x8e\xad\xe8\x01" + b"\0" * 4 +
            struct.pack(">II", len(entries), len(store)) +
            b"".join(struct.pack(">IIII", *entry) for entry in index) +
            bytes(store))


# --------------------------------------------------------------------- cpio
def pack_cpio(files: list[tuple[str, bytes, int, int]]) -> bytes:
    """Nowoczesny format cpio 'newc', z wyrównaniem do 4 bajtów."""
    out = bytearray()
    for inode, (path, data, mode, mtime) in enumerate(files, start=1):
        name = ("./" + path).encode("utf-8")
        fields = [inode, mode, 0, 0, 1, mtime, len(data), 0, 0, 0, 0,
                  len(name) + 1, 0]
        out += b"070701" + b"".join(f"{f:08X}".encode() for f in fields)
        out += name + b"\0"
        out += b"\0" * ((-len(out)) % 4)
        out += data
        out += b"\0" * ((-len(out)) % 4)
    name = b"TRAILER!!!"
    fields = [len(files) + 1, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, len(name) + 1, 0]
    out += b"070701" + b"".join(f"{f:08X}".encode() for f in fields)
    out += name + b"\0"
    out += b"\0" * ((-len(out)) % 4)
    out += b"\0" * ((-len(out)) % 512)
    return bytes(out)


# --------------------------------------------------------------------- pliki
def collect_files() -> list[tuple[str, bytes, int, int]]:
    """Zwraca (ścieżka, treść, tryb, czas modyfikacji) dla wszystkich plików."""
    result: list[tuple[str, bytes, int, int]] = []

    def add_file(dest: str, source: Path, mode: int = 0o644) -> None:
        result.append((dest, source.read_bytes(), mode | 0o100000, STAMP))

    def add_dir(dest: str) -> None:
        result.append((dest.rstrip("/"), b"", 0o040755, STAMP))

    add_file("usr/bin/omniebook", ROOT / "bin/omniebook", 0o755)
    package = ROOT / "omniebook"
    dirs: set[str] = {"usr/lib/omniebook"}
    for path in sorted(package.rglob("*")):
        rel = path.relative_to(package).as_posix()
        if "__pycache__" in rel or path.suffix == ".pyc":
            continue
        dest = "usr/lib/omniebook/" + rel
        parent = Path(dest).parent.as_posix()
        if parent != ".":
            dirs.add(parent)
        if path.is_dir():
            dirs.add(dest)
        elif path.is_file():
            add_file(dest, path)
    for directory in sorted(dirs):
        add_dir(directory)

    # Uwaga: NIE deklarujemy tu katalogów systemowych (/usr/bin, /usr/lib,
    # /usr/share, ...). Należą one do pakietu 'filesystem' - rpm zgłosiłby
    # konflikt plików i odmówił instalacji. Dodajemy tylko katalogi
    # należące wyłącznie do OmniEbook; pozostałe powstaną automatycznie.
    for dest in ("usr/share/doc/omniebook", "usr/share/licenses/omniebook"):
        add_dir(dest)

    add_file("usr/share/applications/io.github.onebypl.OmniEbook.desktop",
             ROOT / "data/io.github.onebypl.OmniEbook.desktop")
    add_file("usr/share/metainfo/io.github.onebypl.OmniEbook.appdata.xml",
             ROOT / "data/io.github.onebypl.OmniEbook.appdata.xml")
    add_file("usr/share/icons/hicolor/scalable/apps/io.github.onebypl.OmniEbook.svg",
             ROOT / "data/icons/hicolor/scalable/apps/io.github.onebypl.OmniEbook.svg")
    add_file("usr/share/doc/omniebook/README.md", ROOT / "README.md")
    add_file("usr/share/doc/omniebook/LICENSE", ROOT / "LICENSE")
    add_file("usr/share/licenses/omniebook/LICENSE", ROOT / "LICENSE")
    return result


def build(dist_tag: str) -> Path:
    files = collect_files()
    missing = [str(p) for p in (
        ROOT / "bin/omniebook", ROOT / "README.md", ROOT / "LICENSE",
    ) if not p.exists()]
    if missing:
        raise SystemExit("Brakujące pliki źródłowe: " + ", ".join(missing))

    release = f"{RELEASE}.{dist_tag}" if dist_tag else RELEASE
    full_version = f"{VERSION}-{release}"

    cpio_raw = pack_cpio(files)
    payload = gzip.compress(cpio_raw, compresslevel=9, mtime=0)

    directories: list[str] = []
    dir_indexes: list[int] = []
    basenames: list[str] = []
    for path, _data, _mode, _mtime in files:
        parent = str(Path(path).parent)
        dirname = "/" if parent in (".", "") else "/" + parent + "/"
        if dirname not in directories:
            directories.append(dirname)
        dir_indexes.append(directories.index(dirname))
        basenames.append(Path(path).name)
        # Katalogi w cpio mają nazwę bez końcowego '/', ale RPM oczekuje
        # basename z '/' - dodajemy go dla wpisów typu DIRECTORY.
        if basenames[-1] == ".":
            basenames[-1] = ""

    sizes = [len(data) for _p, data, _m, _t in files]
    modes = [mode & 0xFFFF for _p, _d, mode, _t in files]
    mtimes = [mtime for _p, _d, _m, mtime in files]
    digests = [hashlib.sha256(data).hexdigest() if mode & 0o100000 else ""
               for _p, data, mode, _t in files]
    links = [""] * len(files)
    flags = [0] * len(files)
    owners = ["root"] * len(files)
    groups = ["root"] * len(files)
    verify = [0xFFFFFFFF] * len(files)
    devices = [1] * len(files)
    inodes = list(range(1, len(files) + 1))
    langs = [""] * len(files)

    provides = [
        "application()",
        "application(io.github.onebypl.OmniEbook.desktop)",
        "metainfo()",
        "metainfo(io.github.onebypl.OmniEbook.appdata.xml)",
        NAME,
    ]
    provide_flags = [32768, 32768, 32768, 32768, 8]
    provide_versions = ["", "", "", "", full_version]

    header_entries: list[tuple[int, int, object]] = [
        (63, BIN, None),  # obowiązkowy region nagłówka głównego
        (100, STRING_ARRAY, ["C"]),
        (1000, STRING, NAME),
        (1001, STRING, VERSION),
        (1002, STRING, release),
        (1004, I18NSTRING, SUMMARY),
        (1005, I18NSTRING, DESCRIPTION),
        (1006, INT32, STAMP),
        (1007, STRING, BUILDHOST),
        (1009, INT32, sum(sizes)),
        (1014, STRING, LICENSE),
        (1016, I18NSTRING, "Unspecified"),
        (1020, STRING, URL),
        (1021, STRING, "linux"),
        (1022, STRING, "noarch"),
        (1024, STRING, POSTIN),
        (1028, INT32, sizes),
        (1030, INT16, modes),
        (1033, INT16, [0] * len(files)),
        (1034, INT32, mtimes),
        (1035, STRING_ARRAY, digests),
        (1036, STRING_ARRAY, links),
        (1037, INT32, flags),
        (1039, STRING_ARRAY, owners),
        (1040, STRING_ARRAY, groups),
        (1044, STRING, f"{NAME}-{full_version}.src.rpm"),
        (1045, INT32, verify),
        (1047, STRING_ARRAY, provides),
        (1048, INT32, REQ_FLAGS),
        (1049, STRING_ARRAY, REQ_NAMES),
        (1050, STRING_ARRAY, REQ_VERSIONS),
        (1064, STRING, "6.1.0"),
        (1094, STRING, f"{BUILDHOST} {STAMP}"),
        (1095, INT32, devices),
        (1096, INT32, inodes),
        (1097, STRING_ARRAY, langs),
        (1112, INT32, provide_flags),
        (1113, STRING_ARRAY, provide_versions),
        (1116, INT32, dir_indexes),
        (1117, STRING_ARRAY, basenames),
        (1118, STRING_ARRAY, directories),
        (1124, STRING, "cpio"),
        (1125, STRING, "gzip"),
        (1126, STRING, "9"),
        (1132, STRING, "noarch-redhat-linux-gnu"),
        # Nowoczesne wersje rpm (Fedora 34+) wymagają informacji o algorytmie
        # skrótów plików oraz podsumowania samego payloadu. Bez tych tagów
        # dnf/Discover odrzuca pakiet jako uszkodzony.
        (5011, INT32, 8),  # 8 = SHA256
        (5092, STRING_ARRAY, [hashlib.sha256(payload).hexdigest()]),
        (5093, INT32, 8),  # algorytm skrótu payloadu: SHA256
        (5097, STRING_ARRAY, [hashlib.sha256(cpio_raw).hexdigest()]),
        (5046, STRING_ARRAY, RECOMMEND_NAMES),
        (5047, STRING_ARRAY, ["", ""]),
        (5048, INT32, [0, 0]),
        (5062, STRING, "utf-8"),
    ]
    main_header = pack_header(header_entries, region_tag=63)

    signature_entries: list[tuple[int, int, object]] = [
        (62, BIN, None),  # obowiązkowy region nagłówka sygnatury
        (269, STRING, hashlib.sha1(main_header).hexdigest()),
        (273, STRING, hashlib.sha256(main_header).hexdigest()),
        (1000, INT32, len(main_header) + len(payload)),
        (1004, BIN, hashlib.md5(main_header + payload).digest()),
        (1007, INT32, len(cpio_raw)),
    ]
    signature_header = pack_header(signature_entries, region_tag=62)
    signature_header += b"\0" * ((-len(signature_header)) % 8)

    lead = bytearray(96)
    lead[0:4] = b"\xed\xab\xee\xdb"
    lead[4] = 3       # major
    lead[5] = 0       # minor
    struct.pack_into(">H", lead, 6, 0)   # type: binary
    struct.pack_into(">H", lead, 8, 1)   # archnum
    label = f"{NAME}-{full_version}".encode("ascii")
    lead[10:10 + len(label)] = label
    struct.pack_into(">H", lead, 76, 1)  # osnum: linux
    struct.pack_into(">H", lead, 78, 5)  # signature type: header-style

    rpm = bytes(lead) + signature_header + main_header + payload

    out_dir = ROOT / "dist" / "fedora"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{NAME}-{full_version}.noarch.rpm"
    out.write_bytes(rpm)
    print(f"==> Gotowe: {out}")
    print(f"==> Instalacja: sudo dnf install ./{out.name}")
    return out


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Budowa pakietu RPM dla Fedora")
    parser.add_argument("--dist-tag", default="fc45",
                        help="znacznik dystrybucji w nazwie pliku (domyślnie fc45)")
    args = parser.parse_args()
    build(args.dist_tag)
