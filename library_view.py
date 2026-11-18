"""Local library view with import, custom URL import and duplicate cleanup."""

from __future__ import annotations

import hashlib

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Adw, Gtk  # noqa: E402

from ...core.formats import detect_format
from ...core.models import Book, MediaType, SearchQuery
from ...i18n import tr
from .base_view import BookGridView


class LibraryView(BookGridView):
    def __init__(self, window, **kwargs) -> None:
        super().__init__(window, tr("my_library"), bulk_delete=True, **kwargs)
        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        import_file = Gtk.Button(label=tr("import"))
        import_file.connect("clicked", lambda *_: self.window.choose_file(import_file=True))
        import_dir = Gtk.Button(label=tr("import_folder"))
        import_dir.connect("clicked", lambda *_: self.window.choose_file(import_file=False))
        add_url = Gtk.Button(label="➕ Dodaj z linku")
        add_url.connect("clicked", self._add_from_url)
        clean = Gtk.Button(label=tr("remove_duplicates"))
        clean.connect("clicked", self._clean_duplicates)
        for btn in (import_file, import_dir, add_url, clean):
            toolbar.append(btn)
        self.insert_child_after(toolbar, self.get_first_child())
        self.refresh()

    def refresh(self) -> None:
        result = self.window.library.db.search(SearchQuery(page_size=10000))
        self.set_books(result.items)

    def _clean_duplicates(self, *_args) -> None:
        removed = self.window.library.remove_duplicates()
        self.window.toast(f"{tr('remove_duplicates')}: {removed}")
        self.refresh()
        self.window.refresh_badges()

    # ------------------------------------------------------------- custom URL
    def _add_from_url(self, *_args) -> None:
        dialog = Adw.Dialog(title="Dodaj zasób z linku")
        dialog.set_content_width(480)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_margin_top(20)
        box.set_margin_bottom(20)
        box.set_margin_start(20)
        box.set_margin_end(20)

        url_entry = Gtk.Entry()
        url_entry.set_placeholder_text("https://… (link do książki, PDF, audiobooka)")
        title_entry = Gtk.Entry()
        title_entry.set_placeholder_text("Tytuł (opcjonalnie)")
        author_entry = Gtk.Entry()
        author_entry.set_placeholder_text("Autor (opcjonalnie)")
        type_combo = Gtk.DropDown.new_from_strings(["Ebook", "Dokument", "Audiobook"])
        type_combo.set_selected(0)

        group = Adw.PreferencesGroup()
        for title, widget in (
            ("Adres URL", url_entry), ("Tytuł", title_entry),
            ("Autor", author_entry), ("Typ", type_combo),
        ):
            row = Adw.ActionRow(title=title)
            row.add_suffix(widget)
            widget.set_hexpand(True)
            group.add(row)
        box.append(group)

        note = Gtk.Label(label="Możesz dodać własne, płatne lub własne źródła — link zostanie zapisany w Twojej bibliotece.")
        note.set_wrap(True)
        note.add_css_class("dim-label")
        box.append(note)

        add_btn = Gtk.Button(label="Dodaj do biblioteki")
        add_btn.add_css_class("suggested-action")
        add_btn.connect("clicked", self._save_url, dialog, url_entry,
                        title_entry, author_entry, type_combo)
        box.append(add_btn)
        dialog.set_child(box)
        dialog.present(self.window)

    def _save_url(self, _button, dialog, url_entry, title_entry,
                  author_entry, type_combo) -> None:
        url = url_entry.get_text().strip()
        if not url:
            self.window.toast("Wpisz adres URL")
            return
        title = title_entry.get_text().strip() or url.rsplit("/", 1)[-1]
        authors = [a.strip() for a in author_entry.get_text().split(",") if a.strip()]
        media_type = (
            MediaType.AUDIOBOOK if type_combo.get_selected() == 2
            else MediaType.DOCUMENT if type_combo.get_selected() == 1
            else MediaType.EBOOK
        )
        filename = url.split("?", 1)[0].rsplit("/", 1)[-1]
        book = Book(
            id="url-" + hashlib.sha1(url.encode()).hexdigest()[:16],
            title=title,
            authors=authors,
            source="custom",
            source_url=url,
            download_url=url,
            media_type=media_type,
            file_format=detect_format(filename),
            categories=["własne"],
            tags=["własne", "link"],
            license="Własny zasób użytkownika",
        )
        self.window.library.add_result(book)
        self.window.toast(tr("library_added_url", title=title[:40]))
        dialog.close()
        self.refresh()
        self.window.refresh_badges()
