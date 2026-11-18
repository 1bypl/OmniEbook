#!/usr/bin/env python3
"""Build a Debian/Ubuntu .deb package using only the Python standard library.

Used as a fallback when ``dpkg-deb`` is not installed (for example in a
minimal build container). The result is a normal, installable .deb file:
an ``ar`` archive with ``debian-binary``, ``control.tar.gz`` and
``data.tar.gz`` members.

Usage:  python3 packaging/build_deb_py.py
"""

from __future__ import annotations

import hashlib
import io
import os
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VERSION = "1.3.0"
REVISION = "1"
PACKAGE = f"omniebook_{VERSION}-{REVISION}_all"
ARCHIVE_NAME = f"{PACKAGE}.deb"
STAMP = int(os.environ.get("SOURCE_DATE_EPOCH", "1794960000"))  # 2026-11-18


def _collect_files() -> list[tuple[str, Path | bytes, int]]:
    """Zwraca listę (ścieżka w pakiecie, źródło, tryb)."""
    files: list[tuple[str, Path | bytes, int]] = []

    def add(dest: str, source: Path | bytes, mode: int = 0o644) -> None:
        files.append((dest, source, mode))

    add("usr/bin/omniebook", ROOT / "bin/omniebook", 0o755)

    package = ROOT / "omniebook"
    add("usr/lib/omniebook", package, 0o755)
    for path in sorted(package.rglob("*")):
        rel = path.relative_to(package).as_posix()
        if "__pycache__" in rel or path.suffix == ".pyc":
            continue
        dest = "usr/lib/omniebook/" + rel
        if path.is_dir():
            add(dest, path, 0o755)
        elif path.is_file():
            add(dest, path, 0o644)

    add("usr/share/applications/io.github.onebypl.OmniEbook.desktop",
        ROOT / "data/io.github.onebypl.OmniEbook.desktop")
    add("usr/share/metainfo/io.github.onebypl.OmniEbook.appdata.xml",
        ROOT / "data/io.github.onebypl.OmniEbook.appdata.xml")
    add("usr/share/icons/hicolor/scalable/apps/io.github.onebypl.OmniEbook.svg",
        ROOT / "data/icons/hicolor/scalable/apps/io.github.onebypl.OmniEbook.svg")
    add("usr/share/doc/omniebook/README.md", ROOT / "README.md")
    add("usr/share/doc/omniebook/LICENSE", ROOT / "LICENSE")
    add("usr/share/doc/omniebook/copyright", ROOT / "packaging/debian/copyright")
    add("usr/share/licenses/omniebook/LICENSE", ROOT / "LICENSE")
    return files


def _tar_info(name: str, mode: int, size: int, is_dir: bool = False) -> tarfile.TarInfo:
    info = tarfile.TarInfo(name)
    info.mode = mode
    info.uid = 0
    info.gid = 0
    info.uname = "root"
    info.gname = "root"
    info.mtime = STAMP
    info.type = tarfile.DIRTYPE if is_dir else tarfile.REGTYPE
    info.size = 0 if is_dir else size
    return info


def _make_data_tar(files) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz", compresslevel=9,
                      format=tarfile.GNU_FORMAT) as tar:
        seen: set[str] = set()
        for dest, source, mode in files:
            parts = dest.split("/")
            for i in range(1, len(parts)):
                directory = "/".join(parts[:i]) + "/"
                if directory not in seen:
                    seen.add(directory)
                    tar.addfile(_tar_info("./" + directory, 0o755, 0, True))
            if isinstance(source, Path) and source.is_dir():
                name = dest.strip("/") + "/"
                if name not in seen:
                    seen.add(name)
                    tar.addfile(_tar_info("./" + name, 0o755, 0, True))
                continue
            if isinstance(source, Path):
                data = source.read_bytes()
            else:
                data = source
            tar.addfile(_tar_info("./" + dest, mode, len(data)), io.BytesIO(data))
    return buf.getvalue()


def _make_control_tar(files) -> bytes:
    control = (ROOT / "packaging/debian/control").read_bytes()
    entries: list[tuple[str, bytes, int]] = [
        ("./control", control, 0o644),
    ]
    for name in ("postinst", "prerm"):
        script = ROOT / "packaging/debian" / name
        if script.exists():
            entries.append((f"./{name}", script.read_bytes(), 0o755))

    sums = []
    for dest, source, _mode in files:
        if isinstance(source, Path):
            if source.is_dir():
                continue
            data = source.read_bytes()
        else:
            data = source
        sums.append(f"{hashlib.md5(data).hexdigest()}  {dest}\n")
    entries.append(("./md5sums", "".join(sums).encode(), 0o644))

    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz", compresslevel=9,
                      format=tarfile.GNU_FORMAT) as tar:
        for name, data, mode in entries:
            tar.addfile(_tar_info(name, mode, len(data)), io.BytesIO(data))
    return buf.getvalue()


def _ar_member(name: str, data: bytes) -> bytes:
    header = (
        f"{name:<16}{0:<12}{0:<6}{0:<6}{0o644:<8o}{len(data):<10}`\n"
    ).encode("ascii")
    if len(header) != 60:
        raise RuntimeError("Niepoprawny nagłówek ar")
    padding = b"\n" if len(data) % 2 else b""
    return header + data + padding


def build() -> Path:
    files = _collect_files()
    missing = [str(s) for _d, s, _m in files
               if isinstance(s, Path) and not s.exists()]
    if missing:
        raise SystemExit("Brakujące pliki źródłowe: " + ", ".join(missing))

    deb = bytearray(b"!<arch>\n")
    deb += _ar_member("debian-binary/", b"2.0\n")
    deb += _ar_member("control.tar.gz/", _make_control_tar(files))
    deb += _ar_member("data.tar.gz/", _make_data_tar(files))

    outputs = []
    for distro in ("debian", "ubuntu"):
        out_dir = ROOT / "dist" / distro
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / ARCHIVE_NAME
        out.write_bytes(deb)
        outputs.append(out)
        print(f"==> Gotowe: {out}")
    print(f"==> Instalacja: sudo apt install ./{ARCHIVE_NAME}")
    return outputs[0]


if __name__ == "__main__":
    build()
