"""Downloads view showing active and completed downloads."""

from __future__ import annotations

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk  # noqa: E402

from ...core.downloader import DownloadState
from ...core.formats import human_size
from ...i18n import tr


class DownloadsView(Gtk.Box):
    def __init__(self, window, **kwargs) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8, **kwargs)
        self.window = window
        self.set_margin_top(12)
        self.set_margin_start(12)
        self.set_margin_end(12)
        self.set_margin_bottom(12)
        title = Gtk.Label(label=tr("downloads"))
        title.add_css_class("title-2")
        title.set_xalign(0)
        self.append(title)
        self.list_box = Gtk.ListBox()
        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_child(self.list_box)
        self.append(scroll)
        self.refresh()

    def refresh(self) -> None:
        self.list_box.remove_all()
        for task in self.window.download_manager.tasks:
            row = Gtk.ListBoxRow()
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            box.set_margin_top(6)
            box.set_margin_bottom(6)
            name = task.filename or task.url.rsplit("/", 1)[-1]
            label = Gtk.Label(label=name, xalign=0)
            status = {
                DownloadState.QUEUED: tr("loading"),
                DownloadState.DOWNLOADING: tr("download"),
                DownloadState.DONE: tr("downloaded"),
                DownloadState.ERROR: tr("error"),
                DownloadState.CANCELLED: tr("cancel"),
            }.get(task.state, "")
            detail = Gtk.Label(label=f"{status} · {human_size(task.downloaded)} / {human_size(task.total)}",
                               xalign=0)
            detail.add_css_class("dim-label")
            bar = Gtk.ProgressBar()
            fraction = task.downloaded / task.total if task.total else (1 if task.state == DownloadState.DONE else 0)
            bar.set_fraction(fraction)
            box.append(label)
            box.append(detail)
            box.append(bar)
            row.set_child(box)
            self.list_box.append(row)
