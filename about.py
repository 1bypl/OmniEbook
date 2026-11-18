"""About window - with our own owl logo instead of a missing-icon placeholder."""

from __future__ import annotations

from pathlib import Path

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk  # noqa: E402

from ... import APP_VERSION, AUTHOR, AUTHOR_URL, LICENSE
from ...i18n import tr

ICON_FILE = "io.github.onebypl.OmniEbook.svg"


def _logo_path() -> str:
    candidates = [
        Path(__file__).resolve().parents[3] / "data" / "icons" / "hicolor" /
        "scalable" / "apps" / ICON_FILE,
        Path("/usr/share/icons/hicolor/scalable/apps") / ICON_FILE,
        Path("/usr/local/share/icons/hicolor/scalable/apps") / ICON_FILE,
    ]
    for path in candidates:
        if path.exists():
            return str(path)
    return ""


def AboutDialog(parent) -> Adw.Window:
    win = Adw.Window(title=tr("about"), transient_for=parent, modal=True)
    win.set_default_size(460, 540)

    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
    box.set_margin_top(24)
    box.set_margin_bottom(24)
    box.set_margin_start(28)
    box.set_margin_end(28)
    box.set_halign(Gtk.Align.CENTER)

    logo_path = _logo_path()
    if logo_path:
        logo = Gtk.Image.new_from_file(logo_path)
        logo.set_pixel_size(112)
        box.append(logo)

    title = Gtk.Label(label="OmniEbook")
    title.add_css_class("title-1")
    box.append(title)

    subtitle = Gtk.Label(label=tr("version").format(version=APP_VERSION))
    subtitle.add_css_class("dim-label")
    box.append(subtitle)

    author = Gtk.Label(label=tr("author").format(author=AUTHOR))
    author.set_wrap(True)
    box.append(author)

    license_label = Gtk.Label(label=tr("license").format(license=LICENSE))
    license_label.set_wrap(True)
    box.append(license_label)

    desc = Gtk.Label(label=tr("about_text"))
    desc.set_wrap(True)
    desc.set_justify(Gtk.Justification.CENTER)
    desc.set_margin_top(12)
    box.append(desc)

    link = Gtk.LinkButton(label="github.com/1bypl", uri=AUTHOR_URL)
    link.set_margin_top(12)
    box.append(link)

    close_btn = Gtk.Button(label=tr("close"))
    close_btn.add_css_class("pill")
    close_btn.set_margin_top(20)
    close_btn.set_halign(Gtk.Align.CENTER)
    close_btn.connect("clicked", lambda *_: win.destroy())
    box.append(close_btn)

    scroll = Gtk.ScrolledWindow()
    scroll.set_child(box)
    scroll.set_vexpand(True)
    win.set_content(scroll)
    win.present()
    return win
