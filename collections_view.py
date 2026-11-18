"""Collections (user-created thematic shelves) view."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk  # noqa: E402

from ...i18n import tr
from .base_view import BookGridView


class CollectionsView(Gtk.Box):
    def __init__(self, window, **kwargs) -> None:
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=12, **kwargs)
        self.window = window
        self.set_margin_top(12)
        self.set_margin_start(12)
        self.set_margin_end(12)
        self.set_margin_bottom(12)

        sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        sidebar.set_size_request(275, -1)
        sidebar.set_vexpand(True)
        new_btn = Gtk.Button(label=tr("new_collection"))
        new_btn.connect("clicked", self._new_collection)
        sidebar.append(new_btn)
        folder_btn = Gtk.Button(label="📁 Kolekcja z folderu")
        folder_btn.set_tooltip_text("Importuje cały folder (ebooki i audio) jako nową kolekcję")
        folder_btn.connect("clicked", self._collection_from_folder)
        sidebar.append(folder_btn)
        self.delete_selected_button = Gtk.Button(label="Usuń wybrany zbiór")
        self.delete_selected_button.set_sensitive(False)
        self.delete_selected_button.connect(
            "clicked", self._confirm_delete_selected_collection
        )
        sidebar.append(self.delete_selected_button)
        list_title = Gtk.Label(label="Moje zbiory")
        list_title.set_xalign(0)
        list_title.add_css_class("heading")
        sidebar.append(list_title)
        self.list_box = Gtk.ListBox()
        self.list_box.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.list_box.connect("row-selected", self._on_select)
        self.list_box.connect(
            "row-selected", self._on_collection_selection_changed
        )
        scroll = Gtk.ScrolledWindow()
        scroll.set_child(self.list_box)
        scroll.set_vexpand(True)
        sidebar.append(scroll)
        self.append(sidebar)

        self.collection_title = Gtk.Label(label="")
        self.collection_title.add_css_class("title-2")
        self.collection_title.set_xalign(0)
        # Zbiory używają tego samego widoku siatki co biblioteka - włączamy
        # zaznaczanie i masowe usuwanie (domyślnie wyłączone).
        self.content = BookGridView(window, "", bulk_delete=True)
        self.content.set_hexpand(True)
        self.content.set_vexpand(True)
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        content_box.append(self.collection_title)
        content_box.append(self.content)
        self.append(content_box)
        self.refresh()

    def refresh(self, selected_id: str | None = None) -> None:
        current = self.list_box.get_selected_row()
        selected_id = selected_id or (
            current.collection_id if current is not None else None
        )
        self.list_box.remove_all()
        rows = []
        for collection in self.window.library.db.list_collections():
            row = Gtk.ListBoxRow()
            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            box.append(Gtk.Label(label=collection["name"], xalign=0, hexpand=True))
            count_label = Gtk.Label(label=str(collection["item_count"]))
            count_label.add_css_class("dim-label")
            box.append(count_label)
            row.set_child(box)
            row.collection_id = collection["id"]
            row.collection_name = collection["name"]
            self.list_box.append(row)
            rows.append(row)
        target = next((row for row in rows if row.collection_id == selected_id), None)
        if target is None:
            target = self.list_box.get_row_at_index(0)
        if target:
            self.list_box.select_row(target)
        else:
            self.collection_title.set_label("")
            self.content.set_books([])

    def _on_select(self, listbox, row) -> None:
        if row is None:
            self.collection_title.set_label("")
            self.content.set_books([])
            return
        self.collection_title.set_label(row.collection_name)
        books = self.window.library.db.books_in_collection(row.collection_id)
        self.content.set_books(books)

    def _on_collection_selection_changed(self, listbox, row) -> None:
        self.delete_selected_button.set_sensitive(row is not None)

    def _collection_from_folder(self, *_args) -> None:
        dialog = Gtk.FileDialog(title="Wybierz folder z książkami")
        dialog.select_folder(self.window, None, self._folder_chosen)

    def _folder_chosen(self, dialog, result) -> None:
        try:
            folder = dialog.select_folder_finish(result)
        except Exception:  # noqa: BLE001
            return
        if not folder:
            return
        path = folder.get_path()
        if not path:
            return
        name = Path(path).name
        books = self.window.library.import_folder(path, recursive=True)
        if not books:
            self.window.toast(tr("import_folder_empty", path=path))
            return
        cid = str(uuid4())
        self.window.library.db.create_collection(cid, name, f"Zaimportowano z: {path}")
        for book in books:
            self.window.library.db.add_to_collection(cid, book.id)
        self.window.toast(tr(
            "collection_added_folder",
            count=len(books),
            name=name,
            path=path,
        ))
        self.window.refresh_badges()
        self.refresh(selected_id=cid)

    def _new_collection(self, *_args) -> None:
        dialog = Gtk.Dialog(title=tr("new_collection"), transient_for=self.window, modal=True)
        dialog.add_button(tr("cancel"), Gtk.ResponseType.CANCEL)
        dialog.add_button(tr("save"), Gtk.ResponseType.OK)
        area = dialog.get_content_area()
        entry = Gtk.Entry()
        entry.set_placeholder_text(tr("collection_name"))
        area.append(entry)
        dialog.connect("response", self._save_collection, entry)
        dialog.present()

    def _save_collection(self, dialog, response, entry) -> None:
        if response == Gtk.ResponseType.OK and entry.get_text().strip():
            cid = str(uuid4())
            self.window.library.db.create_collection(cid, entry.get_text().strip())
            self.window.toast(tr("ok"))
            self.refresh(selected_id=cid)
        dialog.destroy()

    def _confirm_delete_selected_collection(self, button) -> None:
        selected = self.list_box.get_selected_row()
        if selected is None:
            return
        dialog = Gtk.Dialog(
            title="Usuń zbiór",
            transient_for=self.window,
            modal=True,
        )
        dialog.add_button(tr("cancel"), Gtk.ResponseType.CANCEL)
        dialog.add_button("Usuń zbiór", Gtk.ResponseType.ACCEPT)
        message = Gtk.Label(
            label=(
                f"Czy usunąć zbiór „{selected.collection_name}”?\n"
                "Książki i pliki pozostaną w bibliotece."
            )
        )
        message.set_wrap(True)
        message.set_margin_top(12)
        message.set_margin_bottom(12)
        message.set_margin_start(18)
        message.set_margin_end(18)
        dialog.get_content_area().append(message)
        dialog.connect(
            "response",
            self._delete_collection_response,
            selected.collection_id,
        )
        dialog.present()

    def _delete_collection_response(
        self, dialog, response, collection_id: str
    ) -> None:
        if response == Gtk.ResponseType.ACCEPT:
            self.window.library.db.delete_collection(collection_id)
            self.window.toast("Usunięto zbiór; książki pozostały w bibliotece")
            self.refresh()
        dialog.destroy()
