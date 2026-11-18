"""Home view: search entry, thematic categories and library statistics."""

from __future__ import annotations

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk  # noqa: E402

from ...constants import CATEGORIES
from ...i18n import tr
from ..icon_utils import find_app_icon
from ..widgets.category_card import CategoryCard


class HomeView(Gtk.Box):
    def __init__(self, window, **kwargs) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=18, **kwargs)
        self.window = window
        self.set_margin_top(24)
        self.set_margin_bottom(24)
        self.set_margin_start(24)
        self.set_margin_end(24)

        brand = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
        brand.set_halign(Gtk.Align.START)
        brand.add_css_class("card")
        brand.set_margin_top(8)
        brand.set_margin_bottom(8)
        brand.set_margin_start(12)
        brand.set_margin_end(12)
        icon_path = find_app_icon()
        if icon_path:
            logo = Gtk.Image.new_from_file(icon_path)
            logo.set_pixel_size(54)
            brand.append(logo)
        brand_text = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=2
        )
        brand_text.set_valign(Gtk.Align.CENTER)
        title = Gtk.Label(label=tr("app_name"))
        title.add_css_class("title-1")
        title.set_xalign(0)
        brand_text.append(title)
        subtitle = Gtk.Label(label=tr("free_content"))
        subtitle.add_css_class("dim-label")
        subtitle.set_xalign(0)
        brand_text.append(subtitle)
        brand.append(brand_text)
        self.append(brand)

        # Search entry lives in the header bar, but we mirror a prominent one here
        self.search = Gtk.SearchEntry()
        self.search.set_placeholder_text(tr("search_placeholder"))
        self.search.connect("activate", self._on_search)
        self.append(self.search)

        stats_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.stats_labels: dict[str, Gtk.Label] = {}
        for key, emoji in (("total_books", "📖"),
                           ("favorites_count", "⭐"),
                           ("audiobooks_count", "🎧")):
            card = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            card.add_css_class("card")
            card.set_margin_top(6)
            card.set_margin_bottom(6)
            card.set_margin_start(12)
            card.set_margin_end(12)
            icon = Gtk.Label(label=emoji)
            icon.add_css_class("stat-emoji")
            card.append(icon)
            lbl = Gtk.Label(label=f"{tr(key)}: 0")
            self.stats_labels[key] = lbl
            card.append(lbl)
            stats_box.append(card)
        self.append(stats_box)

        cat_title = Gtk.Label(label=tr("categories"))
        cat_title.add_css_class("title-3")
        cat_title.set_xalign(0)
        self.append(cat_title)

        self.flow = Gtk.FlowBox()
        self.flow.set_column_spacing(12)
        self.flow.set_row_spacing(12)
        self.flow.set_homogeneous(True)
        self.flow.set_selection_mode(Gtk.SelectionMode.NONE)
        self.flow.set_max_children_per_line(5)
        self.refresh_categories()
        scroll = Gtk.ScrolledWindow()
        scroll.set_child(self.flow)
        scroll.set_vexpand(True)
        self.append(scroll)
        self.refresh_stats()

    def _on_search(self, entry) -> None:
        text = entry.get_text().strip()
        if text:
            self.window.perform_search(text)

    def _on_category(self, card, key: str) -> None:
        self.window.perform_search("", category=key)

    def refresh_categories(self) -> None:
        self.flow.remove_all()
        for index, (key, (_icon, _keywords)) in enumerate(CATEGORIES.items()):
            if key == "all":
                continue
            card = CategoryCard(key, index=index)
            card.connect("category-selected", self._on_category)
            self.flow.append(card)

    def refresh_stats(self) -> None:
        stats = self.window.library.stats()
        self.stats_labels["total_books"].set_label(f"{tr('total_books')}: {stats['total']}")
        self.stats_labels["favorites_count"].set_label(f"{tr('favorites_count')}: {stats['favorites']}")
        self.stats_labels["audiobooks_count"].set_label(f"{tr('audiobooks_count')}: {stats['audiobooks']}")
