"""Favorites view."""

from __future__ import annotations

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk  # noqa: E402

from ...core.models import SearchQuery
from ...i18n import tr
from .base_view import BookGridView


class FavoritesView(BookGridView):
    def __init__(self, window, **kwargs) -> None:
        super().__init__(window, tr("favorites"), bulk_delete=True, **kwargs)
        self.refresh()

    def refresh(self) -> None:
        result = self.window.library.db.search(SearchQuery(page_size=10000))
        favorites = [b for b in result.items if b.favorite]
        self.set_books(favorites)
