"""Shared base for views that display a grid of local books."""

from __future__ import annotations

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk  # noqa: E402

from ...i18n import tr
from ..widgets.book_tile import BookTile


def confirm_bulk_delete(window, count: int, on_accept) -> None:
    """Wspólne okno potwierdzenia masowego usuwania dla różnych widoków."""
    if not count:
        return
    dialog = Gtk.Dialog(
        title=tr("delete_selected_title"),
        transient_for=window,
        modal=True,
    )
    dialog.add_button(tr("cancel"), Gtk.ResponseType.CANCEL)
    confirm = dialog.add_button(
        tr("delete_selected_confirm", count=count), Gtk.ResponseType.ACCEPT)
    confirm.add_css_class("destructive-action")
    message = Gtk.Label(label=tr("delete_selected_message", count=count))
    message.set_wrap(True)
    message.set_margin_top(12)
    message.set_margin_bottom(12)
    message.set_margin_start(18)
    message.set_margin_end(18)
    dialog.get_content_area().append(message)

    def on_response(dlg, response) -> None:
        if response == Gtk.ResponseType.ACCEPT:
            on_accept()
        dlg.destroy()

    dialog.connect("response", on_response)
    dialog.present()


class BookGridView(Gtk.Box):
    """Scrollable grid of :class:`BookTile` with common callbacks.

    When ``bulk_delete=True`` the view also offers a selection bar: the user
    ticks several tiles and removes all of them with a single confirmation.
    """

    def __init__(self, window, title: str = "", bulk_delete: bool = False,
                 **kwargs) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8, **kwargs)
        self.window = window
        self.bulk_delete = bulk_delete
        self.selected_ids: set[str] = set()
        self._books: list = []
        self.set_margin_top(12)
        self.set_margin_start(12)
        self.set_margin_end(12)
        self.set_margin_bottom(12)
        if title:
            lbl = Gtk.Label(label=title)
            lbl.add_css_class("title-2")
            lbl.set_xalign(0)
            self.append(lbl)
        if bulk_delete:
            self._build_selection_bar()
        self.flow = Gtk.FlowBox()
        self.flow.set_column_spacing(12)
        self.flow.set_row_spacing(12)
        self.flow.set_homogeneous(True)
        self.flow.set_selection_mode(Gtk.SelectionMode.NONE)
        self.scrolled = Gtk.ScrolledWindow()
        self.scrolled.set_vexpand(True)
        self.scrolled.set_child(self.flow)
        self.append(self.scrolled)
        self.empty = Gtk.Label(label=tr("no_results"))
        self.empty.add_css_class("dim-label")
        self.empty.set_visible(False)
        self.append(self.empty)

    # ------------------------------------------------------- selection toolbar
    def _build_selection_bar(self) -> None:
        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

        self.select_mode_btn = Gtk.ToggleButton(label=tr("select_items"))
        self.select_mode_btn.set_tooltip_text(tr("select_items_tooltip"))
        self.select_mode_btn.connect("toggled", self._on_selection_mode)

        self.select_all_btn = Gtk.Button(label=tr("select_all"))
        self.select_all_btn.set_sensitive(False)
        self.select_all_btn.connect("clicked", self._on_select_all)

        self.delete_selected_btn = Gtk.Button(
            label=tr("delete_selected_count", count=0))
        self.delete_selected_btn.add_css_class("destructive-action")
        self.delete_selected_btn.set_sensitive(False)
        self.delete_selected_btn.set_tooltip_text(tr("delete_selected_tooltip"))
        self.delete_selected_btn.connect("clicked", self._on_delete_selected)

        bar.append(self.select_mode_btn)
        bar.append(self.select_all_btn)
        bar.append(self.delete_selected_btn)
        self.append(bar)

    def _update_selection_ui(self) -> None:
        if not self.bulk_delete:
            return
        count = len(self.selected_ids)
        self.delete_selected_btn.set_label(
            tr("delete_selected_count", count=count))
        self.delete_selected_btn.set_sensitive(count > 0)
        all_selected = bool(self._books) and count == len(self._books)
        self.select_all_btn.set_label(
            tr("deselect_all") if all_selected else tr("select_all"))
        self.select_all_btn.set_sensitive(bool(self._books))

    def _on_selection_mode(self, button) -> None:
        """Włączenie trybu pokazuje checkboxy, wyłączenie czyści zaznaczenie."""
        active = button.get_active()
        self.selected_ids.clear()
        for tile in self.flow.get_children():
            tile.set_selection_mode(active)
        self._update_selection_ui()

    def _on_select_all(self, *_args) -> None:
        select = len(self.selected_ids) != len(self._books)
        self.selected_ids = (
            {book.id for book in self._books} if select else set()
        )
        for tile in self.flow.get_children():
            tile.set_selected(select)
        self._update_selection_ui()

    def _on_selection_toggled(self, tile, book, selected: bool) -> None:
        if selected:
            self.selected_ids.add(book.id)
        else:
            self.selected_ids.discard(book.id)
        self._update_selection_ui()

    def _on_delete_selected(self, *_args) -> None:
        count = len(self.selected_ids)
        if not count:
            return
        dialog = Gtk.Dialog(
            title=tr("delete_selected_title"),
            transient_for=self.window,
            modal=True,
        )
        dialog.add_button(tr("cancel"), Gtk.ResponseType.CANCEL)
        confirm = dialog.add_button(
            tr("delete_selected_confirm", count=count), Gtk.ResponseType.ACCEPT)
        confirm.add_css_class("destructive-action")
        message = Gtk.Label(label=tr("delete_selected_message", count=count))
        message.set_wrap(True)
        message.set_margin_top(12)
        message.set_margin_bottom(12)
        message.set_margin_start(18)
        message.set_margin_end(18)
        dialog.get_content_area().append(message)
        dialog.connect("response", self._delete_selected_response)
        dialog.present()

    def _delete_selected_response(self, dialog, response) -> None:
        if response == Gtk.ResponseType.ACCEPT:
            ids = list(self.selected_ids)
            removed = self.window.library.delete_many(ids)
            self.window.toast(tr("deleted_count", count=removed))
            self.window.refresh_badges()
            if self.bulk_delete:
                self.select_mode_btn.set_active(False)
            self.selected_ids.clear()
            self.refresh()
        dialog.destroy()

    # ------------------------------------------------------------------ books
    def set_books(self, books: list) -> None:
        self._books = list(books)
        self.selected_ids.clear()
        # Świeża lista = świeży tryb. Inaczej przełącznik zaznaczania mógł
        # zostać włączony z poprzedniej wizyty i blokować przyciski
        # „Czytaj"/„Słuchaj" w Ulubionych i Zbiorach.
        if self.bulk_delete and self.select_mode_btn.get_active():
            self.select_mode_btn.set_active(False)
        self.flow.remove_all()
        for book in books:
            tile = BookTile(book)
            tile.connect("open-requested", lambda t, b: self.window.open_book(b))
            tile.connect("favorite-toggled", self._on_favorite)
            tile.connect("new-item-dismissed", self._on_new_item_dismissed)
            tile.connect("download-requested", lambda t, b: self.window.download_book(b))
            tile.connect("delete-requested", self._on_delete)
            if self.bulk_delete:
                tile.connect("selection-toggled", self._on_selection_toggled)
                tile.set_selection_mode(self.select_mode_btn.get_active())
            self.flow.append(tile)
        self.empty.set_visible(not books)
        self._update_selection_ui()

    def _on_favorite(self, tile, book, favorite: bool) -> None:
        self.window.library.db.set_favorite(book.id, favorite)
        self.window.library.add_result(book)
        self.window.refresh_badges()
        if "favorites" in type(self).__name__.lower():
            self.refresh()

    def _on_new_item_dismissed(self, tile, book) -> None:
        self.window.library.db.mark_seen(book.id)

    def _on_delete(self, tile, book) -> None:
        self.window.library.delete(book.id)
        self.window.toast(tr("delete"))
        self.window.refresh_badges()
        self.refresh()

    def refresh(self) -> None:
        pass
