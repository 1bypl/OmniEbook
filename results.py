"""Search results grid with 20 tiles per page and pagination."""

from __future__ import annotations

import threading

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk  # noqa: E402

from ...config import Settings
from ...core.models import SearchQuery
from ...i18n import tr
from ..widgets.book_tile import BookTile
from .base_view import confirm_bulk_delete


class ResultsView(Gtk.Box):
    def __init__(self, window, **kwargs) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8, **kwargs)
        self.window = window
        self.query = SearchQuery()
        self.books: list = []
        self.errors: list[str] = []
        self.selected_ids: set[str] = set()
        self.page = 1
        self.set_margin_top(12)
        self.set_margin_start(12)
        self.set_margin_end(12)
        self.set_margin_bottom(12)

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.title_label = Gtk.Label(label=tr("search_results"))
        self.title_label.add_css_class("title-2")
        self.title_label.set_xalign(0)
        self.title_label.set_hexpand(True)
        header.append(self.title_label)
        self.count_label = Gtk.Label(label="")
        self.count_label.add_css_class("dim-label")
        header.append(self.count_label)
        self.append(header)

        status_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.spinner = Gtk.Spinner()
        self.spinner.set_halign(Gtk.Align.START)
        status_box.append(self.spinner)
        self.status_label = Gtk.Label(label=tr("searching"))
        self.status_label.add_css_class("dim-label")
        self.status_label.set_xalign(0)
        status_box.append(self.status_label)
        self.append(status_box)

        self.sources_label = Gtk.Label(label="")
        self.sources_label.add_css_class("dim-label")
        self.sources_label.set_wrap(True)
        self.sources_label.set_xalign(0)
        self.append(self.sources_label)

        self._build_selection_bar()

        self.scrolled = Gtk.ScrolledWindow()
        self.scrolled.set_vexpand(True)
        self.flow = Gtk.FlowBox()
        self.flow.set_column_spacing(12)
        self.flow.set_row_spacing(12)
        self.flow.set_homogeneous(True)
        self.flow.set_selection_mode(Gtk.SelectionMode.NONE)
        self.scrolled.set_child(self.flow)
        self.append(self.scrolled)

        self.empty = Gtk.Label(label=tr("no_results"))
        self.empty.set_wrap(True)
        self.empty.add_css_class("dim-label")
        self.empty.set_visible(False)
        self.append(self.empty)

        pager = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        pager.set_halign(Gtk.Align.CENTER)
        self.prev_btn = Gtk.Button(label=tr("previous"))
        self.prev_btn.connect("clicked", lambda *_: self.change_page(-1))
        self.page_label = Gtk.Label(label="")
        self.next_btn = Gtk.Button(label=tr("next"))
        self.next_btn.connect("clicked", lambda *_: self.change_page(1))
        pager.append(self.prev_btn)
        pager.append(self.page_label)
        pager.append(self.next_btn)
        self.append(pager)

    def _build_selection_bar(self) -> None:
        """Pasek zaznaczania - wyniki można usuwać zbiorczo jak w bibliotece."""
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

        for button in (self.select_mode_btn, self.select_all_btn,
                       self.delete_selected_btn):
            bar.append(button)
        self.append(bar)

    def set_query(self, query: SearchQuery) -> None:
        self.query = query
        self.page = query.page
        overrides = Settings().get("category_overrides", {})
        category = (
            overrides.get(query.category, {}).get("label")
            if isinstance(overrides, dict) else ""
        )
        self.title_label.set_label(
            f"{tr('search_results')}: {query.text or category or tr(query.category)}"
        )
        self.start_search()

    def start_search(self) -> None:
        self._generation = getattr(self, "_generation", 0) + 1
        generation = self._generation

        def is_current() -> bool:
            return generation == self._generation

        self.spinner.start()
        self.status_label.set_visible(True)
        self.source_status: dict[str, str] = {}
        self._found = 0
        self._tiles_added = 0
        self.sources_label.set_label("")
        self.flow.remove_all()
        self.empty.set_visible(False)
        self._clear_selection()
        self.query.page = self.page
        self.query.page_size = int(Settings().get("page_size", 20))

        def on_result(result):
            def idle():
                if not is_current():
                    return False
                if result.error:
                    self.source_status[result.source] = f"✗ {result.source}"
                else:
                    self.source_status[result.source] = (
                        f"✓ {result.source}: {len(result.items)}")
                self.sources_label.set_label(
                    "   |   ".join(self.source_status.values()))
                self._found += len(result.items)
                self.count_label.set_label(
                    tr("results_count").format(count=self._found))
                self._append_books(result.items)
                return False
            GLib.idle_add(idle)

        def on_done(books, errors):
            def idle():
                if not is_current():
                    return False
                self.spinner.stop()
                self.status_label.set_visible(False)
                self.books = books
                self.errors = errors
                self._render_page()
                if errors:
                    self.window.toast("; ".join(errors[:2]))
                return False
            GLib.idle_add(idle)

        # Run the whole aggregation in a background thread so the UI stays
        # responsive while remote sources answer (up to 15 s each).
        def worker():
            self.window.search_manager.search(
                self.query, on_result=on_result, on_done=on_done)

        threading.Thread(target=worker, daemon=True).start()

    def _append_books(self, books) -> None:
        for book in books:
            try:
                tile = BookTile(book)
                tile.connect("open-requested", self._on_open)
                tile.connect("favorite-toggled", self._on_favorite)
                tile.connect("new-item-dismissed", self._on_new_item_dismissed)
                tile.connect("download-requested", self._on_download)
                tile.connect("delete-requested", self._on_delete)
                tile.connect("selection-toggled", self._on_selection_toggled)
                tile.set_selection_mode(self.select_mode_btn.get_active())
                self.flow.append(tile)
                self._tiles_added += 1
            except Exception:  # noqa: BLE001 - never let one tile kill the grid
                import traceback
                traceback.print_exc()
                self._tile_errors = getattr(self, "_tile_errors", 0) + 1

    def _render_page(self) -> None:
        self._tiles_added = 0
        self.flow.remove_all()
        self._clear_selection()
        per_page = int(Settings().get("page_size", 20))
        start = (self.page - 1) * per_page
        page_items = self.books[start:start + per_page]
        self._append_books(page_items)
        total_pages = max(1, (len(self.books) + per_page - 1) // per_page)
        self.page_label.set_label(f"{tr('page')} {self.page} {tr('of')} {total_pages}")
        self.count_label.set_label(tr("results_count").format(count=len(self.books)))
        self.empty.set_visible(not self.books)
        if not self.books and self.errors:
            detail = "\n".join(f"• {e[:120]}" for e in self.errors[:4])
            self.empty.set_label(f"{tr('no_results')}\n\n{detail}")
        else:
            self.empty.set_label(tr("no_results"))
        prev_status = self.sources_label.get_label() or ""
        self.sources_label.set_label(
            f"{prev_status}   |   kafelki: {self._tiles_added}"
        )
        self.prev_btn.set_sensitive(self.page > 1)
        self.next_btn.set_sensitive(self.page < total_pages)

    def change_page(self, delta: int) -> None:
        self.page = max(1, self.page + delta)
        self._render_page()
        self.scrolled.get_vadjustment().set_value(0)

    # ------------------------------------------------- zaznaczanie i usuwanie
    def _clear_selection(self) -> None:
        self.selected_ids.clear()
        if self.select_mode_btn.get_active():
            self.select_mode_btn.set_active(False)
        else:
            self._update_selection_ui()

    def _update_selection_ui(self) -> None:
        count = len(self.selected_ids)
        self.delete_selected_btn.set_label(
            tr("delete_selected_count", count=count))
        self.delete_selected_btn.set_sensitive(count > 0)
        all_selected = bool(self.books) and count == len(self.books)
        self.select_all_btn.set_label(
            tr("deselect_all") if all_selected else tr("select_all"))
        self.select_all_btn.set_sensitive(bool(self.books))

    def _on_selection_mode(self, button) -> None:
        active = button.get_active()
        self.selected_ids.clear()
        for tile in self.flow.get_children():
            tile.set_selection_mode(active)
        self._update_selection_ui()

    def _on_select_all(self, *_args) -> None:
        select = len(self.selected_ids) != len(self.books)
        self.selected_ids = (
            {book.id for book in self.books} if select else set()
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
        ids = list(self.selected_ids)

        def delete() -> None:
            removed = self.window.library.delete_many(ids)
            self.window.toast(tr("deleted_count", count=removed))
            self.window.refresh_badges()
            self.selected_ids.clear()
            self.select_mode_btn.set_active(False)
            self._render_page()

        confirm_bulk_delete(self.window, len(ids), delete)

    # ------------------------------------------------------------- callbacks
    def _on_open(self, tile, book) -> None:
        self.window.open_book(book)

    def _on_favorite(self, tile, book, favorite: bool) -> None:
        # BookTile already flipped book.favorite - set the explicit value,
        # never toggle again (that would undo the change).
        self.window.library.add_result(book)
        tile.update_new_status(book.is_new)
        self.window.library.db.set_favorite(book.id, favorite)
        self.window.refresh_badges()

    def _on_download(self, tile, book) -> None:
        self.window.download_book(book)
        tile.update_new_status(book.is_new)

    def _on_new_item_dismissed(self, tile, book) -> None:
        self.window.library.db.mark_seen(book.id)

    def _on_delete(self, tile, book) -> None:
        self.window.library.delete(book.id)
        # Kafelek znika natychmiast - inaczej wyglądałby tak, jakby usuwanie
        # nie zadziałało (dane już są usunięte z bazy).
        self.flow.remove(tile)
        self.books = [b for b in self.books if b.id != book.id]
        self.selected_ids.discard(book.id)
        self._update_selection_ui()
        self.count_label.set_label(
            tr("results_count").format(count=len(self.books)))
        self.empty.set_visible(not self.books)
        self.window.toast(tr("delete"))
        self.window.refresh_badges()
