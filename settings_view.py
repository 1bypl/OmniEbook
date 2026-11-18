"""Preferences: language, skins, downloads, reading tools and search sources."""

from __future__ import annotations

import uuid
import urllib.parse

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, Gtk  # noqa: E402

from ...config import Settings
from ...constants import CATEGORIES
from ...i18n import available_languages, current_language, set_language, tr
from ...sources.custom import WOLNELEKTURY_SOURCE
from ...themes import ACCENTS, THEMES

FONTS = ["Sans", "Serif", "Monospace", "DejaVu Sans", "DejaVu Serif",
         "Liberation Serif", "Georgia", "Times New Roman"]
READER_THEMES = ["sepia", "light", "dark", "green"]


class SettingsView(Adw.PreferencesPage):
    def __init__(self, window, **kwargs) -> None:
        super().__init__(**kwargs)
        self.window = window
        self.settings = Settings()

        # ---------------------------------------------------------- appearance
        appearance = Adw.PreferencesGroup(title=tr("theme"))
        self.theme_combo = Adw.ComboRow(title=tr("theme"))
        self.theme_combo.set_model(Gtk.StringList.new(list(THEMES.values())))
        keys = list(THEMES.keys())
        self.theme_combo.set_selected(max(0, keys.index(self.settings.get("theme", "system"))))
        self.theme_combo.connect("notify::selected", self._on_theme)
        appearance.add(self.theme_combo)

        self.accent_combo = Adw.ComboRow(title="Akcent")
        self.accent_combo.set_model(Gtk.StringList.new(list(ACCENTS.keys())))
        accents = list(ACCENTS.keys())
        self.accent_combo.set_selected(max(0, accents.index(self.settings.get("accent", "blue"))))
        self.accent_combo.connect("notify::selected", self._on_accent)
        appearance.add(self.accent_combo)
        self.add(appearance)

        # ------------------------------------------------------------ language
        lang_group = Adw.PreferencesGroup(title=tr("language"))
        self.lang_combo = Adw.ComboRow(title=tr("language"))
        langs = available_languages()
        self.lang_keys = list(langs.keys())
        self.lang_combo.set_model(Gtk.StringList.new(list(langs.values())))
        self.lang_combo.set_selected(max(0, self.lang_keys.index(current_language())))
        self.lang_combo.connect("notify::selected", self._on_language)
        lang_group.add(self.lang_combo)
        self.add(lang_group)

        # ------------------------------------------------------------ downloads
        dl_group = Adw.PreferencesGroup(title=tr("download_dir"))
        row = Adw.ActionRow(title=tr("download_dir"), subtitle=self.settings.get("download_dir", ""))
        choose = Gtk.Button(label=tr("choose_folder"))
        choose.set_valign(Gtk.Align.CENTER)
        choose.connect("clicked", self._choose_folder, row)
        row.add_suffix(choose)
        dl_group.add(row)

        auto_switch = Adw.SwitchRow(
            title=tr("import"),
            subtitle="Po pobraniu dodaj plik do biblioteki",
            active=bool(self.settings.get("auto_import_downloads", True)),
        )
        auto_switch.connect("notify::active", lambda w, p: self.settings.set(
            "auto_import_downloads", w.get_active()))
        dl_group.add(auto_switch)
        self.add(dl_group)

        # ------------------------------------------------------ reading tools
        read_group = Adw.PreferencesGroup(title=tr("reading_settings"))
        font_row = Adw.ComboRow(title=tr("font"))
        font_row.set_model(Gtk.StringList.new(FONTS))
        current_font = self.settings.get("font_family", "Sans")
        font_row.set_selected(max(0, FONTS.index(current_font) if current_font in FONTS else 0))
        font_row.connect("notify::selected", lambda w, p: self.settings.set(
            "font_family", FONTS[w.get_selected()]))
        read_group.add(font_row)

        size_row = Adw.SpinRow(
            title=tr("font_size"),
            adjustment=Gtk.Adjustment(
                lower=8, upper=48, step_increment=1, page_increment=2,
                value=float(self.settings.get("font_size", 18)),
            ),
            digits=0,
        )
        size_row.connect("notify::value", lambda w, p: self.settings.set(
            "font_size", int(w.get_value())))
        read_group.add(size_row)

        spacing_row = Adw.SpinRow(
            title=tr("line_spacing"),
            adjustment=Gtk.Adjustment(
                lower=1.0, upper=2.5, step_increment=0.1, page_increment=0.2,
                value=float(self.settings.get("line_spacing", 1.4)),
            ),
            digits=1,
        )
        spacing_row.connect("notify::value", lambda w, p: self.settings.set(
            "line_spacing", round(w.get_value(), 2)))
        read_group.add(spacing_row)

        margin_row = Adw.SpinRow(
            title=tr("margin"),
            adjustment=Gtk.Adjustment(
                lower=0, upper=120, step_increment=4, page_increment=8,
                value=float(self.settings.get("margin", 40)),
            ),
            digits=0,
        )
        margin_row.connect("notify::value", lambda w, p: self.settings.set(
            "margin", int(w.get_value())))
        read_group.add(margin_row)

        flip_switch = Adw.SwitchRow(
            title=tr("page_flip"), active=bool(self.settings.get("page_flip_effect", True)))
        flip_switch.connect("notify::active", lambda w, p: self.settings.set(
            "page_flip_effect", w.get_active()))
        read_group.add(flip_switch)

        reader_theme_row = Adw.ComboRow(title=tr("theme"), model=Gtk.StringList.new(READER_THEMES))
        reader_theme_row.set_selected(max(0, READER_THEMES.index(
            self.settings.get("reader_theme", "sepia"))))
        reader_theme_row.connect("notify::selected", lambda w, p: self.settings.set(
            "reader_theme", READER_THEMES[w.get_selected()]))
        read_group.add(reader_theme_row)

        self.add(read_group)

        # ----------------------------------------------------------- categories
        categories_group = Adw.PreferencesGroup(title="Kategorie i kafelki")
        self.category_keys = [
            key for key in CATEGORIES if key != "all"
        ]
        category_overrides = self.settings.get("category_overrides", {})
        self.category_combo = Adw.ComboRow(title="Kategoria")
        self.category_combo.set_model(Gtk.StringList.new([
            (
                category_overrides.get(key, {}).get("label")
                or tr(key)
            ) if isinstance(category_overrides, dict) else tr(key)
            for key in self.category_keys
        ]))
        self.category_combo.connect(
            "notify::selected", self._on_category_selected
        )
        categories_group.add(self.category_combo)

        self.category_name = Adw.EntryRow(title="Własna nazwa")
        categories_group.add(self.category_name)

        self.category_icon_row = Adw.ActionRow(title="Ikona kafelka")
        choose_icon = Gtk.Button(label="Wybierz obraz…")
        choose_icon.set_valign(Gtk.Align.CENTER)
        choose_icon.connect("clicked", self._choose_category_icon)
        self.category_icon_row.add_suffix(choose_icon)
        clear_icon = Gtk.Button(label="Domyślna")
        clear_icon.set_valign(Gtk.Align.CENTER)
        clear_icon.connect("clicked", self._clear_category_icon)
        self.category_icon_row.add_suffix(clear_icon)
        categories_group.add(self.category_icon_row)
        self.category_icon_path = ""

        save_category = Gtk.Button(label="Zapisz kategorię")
        save_category.connect("clicked", self._save_category)
        save_row = Adw.ActionRow(title="Zapisz zmiany")
        save_row.add_suffix(save_category)
        categories_group.add(save_row)
        self.add(categories_group)
        self._on_category_selected(self.category_combo, None)

        # ----------------------------------------------------------- sources
        sources_group = Adw.PreferencesGroup(title=tr("sources"))
        source_names = {
            "gutenberg": "Project Gutenberg", "openlibrary": "Open Library",
            "internet_archive": "Internet Archive", "arxiv": "arXiv",
            "doaj": "DOAJ", "librivox": "LibriVox", "local": tr("my_library"),
        }
        enabled = dict(self.settings.get("enable_sources", {}))
        for key, name in source_names.items():
            switch = Adw.SwitchRow(title=name, active=bool(enabled.get(key, True)))
            switch.connect("notify::active", self._on_source, key)
            sources_group.add(switch)
        self.custom_sources_group = Adw.PreferencesGroup(
            title="Własne źródła OPDS/Atom i HTML"
        )
        self.custom_sources_group.add(self._sources_help_row())
        self.add(sources_group)
        self.add(self.custom_sources_group)
        self._custom_source_widgets = []
        self._refresh_custom_source_rows()

    @staticmethod
    def _sources_help_row() -> Adw.ExpanderRow:
        """Instrukcja wpisywania adresów - chroni wyszukiwanie globalne przed błędami."""
        expander = Adw.ExpanderRow(
            title="Instrukcja: jak wpisać adres źródła",
            subtitle="Otwórz przed dodaniem linku",
        )
        tips = [
            ("Co wkleić",
             "Adres wyszukiwarki, NIE odnośnik do jednej książki. "
             "Musi zaczynać się od https:// (lub http://), bez spacji i cudzysłowów."),
            ("OPDS i HTML",
             "W adresie umieść znacznik {query}, np. "
             "https://katalog.example/szukaj?q={query}. Program sam wstawia wpisane słowo."),
            ("RSS i Atom",
             "Wklej bezpośredni adres pliku .xml lub .rss — bez {query}. "
             "Program przefiltruje pobrane wpisy lokalnie."),
            ("Strony HTML",
             "Uzupełnij selektory CSS: wyniki, tytuł i odnośnik są wymagane; "
             "okładka, opis, autor i link pobierania są opcjonalne."),
            ("Bezpieczny test",
             "Dodawaj jedno źródło naraz i wyłącz pozostałe przełącznikami. "
             "Unikaj localhost, 127.0.0.1 oraz stron wymagających logowania."),
            ("Gdy coś nie działa",
             "Jeśli wyszukiwanie zwolni lub pokaże błąd, wyłącz to źródło "
             "przełącznikiem albo usuń je przyciskiem Usuń."),
        ]
        for _title, text in tips:
            label = Gtk.Label(label=text)
            label.set_wrap(True)
            label.set_xalign(0)
            label.set_margin_top(8)
            label.set_margin_bottom(8)
            label.set_margin_start(4)
            label.set_margin_end(4)
            row = Adw.PreferencesRow()
            row.set_child(label)
            expander.add_row(row)
        return expander

    # ---------------------------------------------------------------- callbacks
    def _on_theme(self, row, _param) -> None:
        keys = list(THEMES.keys())
        theme = keys[row.get_selected()]
        self.settings.set("theme", theme)
        # Używamy jednego, współdzielonego menedżera z okna głównego.
        self.window.theme_manager.apply(theme)

    def _on_accent(self, row, _param) -> None:
        keys = list(ACCENTS.keys())
        self.settings.set("accent", keys[row.get_selected()])
        self.window.theme_manager.apply()

    def _on_language(self, row, _param) -> None:
        # set_language() notifies the window listener which rebuilds the UI.
        set_language(self.lang_keys[row.get_selected()])

    def _on_source(self, switch, _param, key: str) -> None:
        enabled = dict(self.settings.get("enable_sources", {}))
        enabled[key] = switch.get_active()
        self.settings.set("enable_sources", enabled)

    def _on_category_selected(self, row, _param) -> None:
        index = row.get_selected()
        if index >= len(self.category_keys):
            return
        key = self.category_keys[index]
        overrides = self.settings.get("category_overrides", {})
        override = overrides.get(key, {}) if isinstance(overrides, dict) else {}
        self.category_name.set_text(override.get("label", ""))
        self.category_icon_path = override.get("icon_path", "")
        self.category_icon_row.set_subtitle(
            self.category_icon_path or "Używana jest domyślna ikonka"
        )

    def _choose_category_icon(self, button) -> None:
        dialog = Gtk.FileDialog(title="Wybierz ikonę kategorii")
        dialog.open(self.window, None, self._category_icon_chosen)

    def _category_icon_chosen(self, dialog, result) -> None:
        try:
            file = dialog.open_finish(result)
        except Exception:  # noqa: BLE001 - dialog cancellation
            return
        if file and file.get_path():
            self.category_icon_path = file.get_path()
            self.category_icon_row.set_subtitle(self.category_icon_path)

    def _clear_category_icon(self, button) -> None:
        self.category_icon_path = ""
        self.category_icon_row.set_subtitle("Używana jest domyślna ikonka")

    def _save_category(self, button) -> None:
        index = self.category_combo.get_selected()
        if index >= len(self.category_keys):
            return
        key = self.category_keys[index]
        overrides = dict(self.settings.get("category_overrides", {}))
        overrides[key] = {
            "label": self.category_name.get_text().strip(),
            "icon_path": self.category_icon_path,
        }
        self.settings.set("category_overrides", overrides)
        self.window.views["home"].refresh_categories()
        self.window.toast("Zapisano ustawienia kategorii")

    def _has_wolnelektury_source(self) -> bool:
        """Sprawdza, czy źródło Wolne Lektury jest już skonfigurowane."""
        for source in self.settings.get("custom_sources", []):
            if not isinstance(source, dict):
                continue
            if source.get("id") == WOLNELEKTURY_SOURCE["id"]:
                return True
            host = urllib.parse.urlparse(
                str(source.get("search_url", ""))).hostname
            if host in ("wolnelektury.pl", "www.wolnelektury.pl"):
                return True
        return False

    def _refresh_custom_source_rows(self) -> None:
        for widget in self._custom_source_widgets:
            self.custom_sources_group.remove(widget)
        self._custom_source_widgets.clear()
        for source in self.settings.get("custom_sources", []):
            if not isinstance(source, dict):
                continue
            source_id = str(source.get("id", ""))
            if not source_id:
                continue
            kind = {
                "feed": "RSS / Atom",
                "rss": "RSS",
                "opds": "OPDS",
                "html": "HTML",
            }.get(source.get("kind"), "Źródło")
            row = Adw.ActionRow(
                title=str(source.get("name", "Własne źródło")),
                subtitle=f"{kind} · {source.get('search_url', '')}",
            )
            switch = Gtk.Switch()
            switch.set_valign(Gtk.Align.CENTER)
            enabled = self.settings.get("enable_sources", {})
            switch.set_active(bool(enabled.get(source_id, True)))
            switch.connect("notify::active", self._on_source, source_id)
            row.add_suffix(switch)
            remove = Gtk.Button(label="Usuń")
            remove.set_valign(Gtk.Align.CENTER)
            remove.connect("clicked", self._remove_custom_source, source_id)
            row.add_suffix(remove)
            self.custom_sources_group.add(row)
            self._custom_source_widgets.append(row)

        # Po usunięciu źródła nie pokazujemy już przycisku "Dodaj / napraw" -
        # użytkownik świadomie zrezygnował z Wolnych Lektur.
        if not self._has_wolnelektury_source():
            wolnelektury_button = Gtk.Button(label="Dodaj / napraw")
            wolnelektury_button.connect(
                "clicked", self._add_wolnelektury_source
            )
            wolnelektury_row = Adw.ActionRow(
                title="Wolne Lektury",
                subtitle="Gotowa konfiguracja oficjalnej wyszukiwarki",
            )
            wolnelektury_row.add_suffix(wolnelektury_button)
            self.custom_sources_group.add(wolnelektury_row)
            self._custom_source_widgets.append(wolnelektury_row)

        add_source = Gtk.Button(label="Dodaj…")
        add_source.connect("clicked", self._add_custom_source)
        add_source_row = Adw.ActionRow(title="Dodaj własne źródło")
        add_source_row.add_suffix(add_source)
        self.custom_sources_group.add(add_source_row)
        self._custom_source_widgets.append(add_source_row)

    def _add_wolnelektury_source(self, button) -> None:
        sources = list(self.settings.get("custom_sources", []))
        existing_index = next(
            (
                index for index, source in enumerate(sources)
                if isinstance(source, dict) and (
                    source.get("id") == WOLNELEKTURY_SOURCE["id"]
                    or urllib.parse.urlparse(
                        str(source.get("search_url", ""))
                    ).hostname in ("wolnelektury.pl", "www.wolnelektury.pl")
                )
            ),
            None,
        )
        source = dict(WOLNELEKTURY_SOURCE)
        if existing_index is None:
            sources.append(source)
        else:
            source["id"] = sources[existing_index]["id"]
            sources[existing_index] = source

        enabled = dict(self.settings.get("enable_sources", {}))
        enabled[source["id"]] = True
        self.settings.set("custom_sources", sources)
        self.settings.set("enable_sources", enabled)
        self.window.search_manager.reload_custom_sources()
        self._refresh_custom_source_rows()
        self.window.toast("Dodano / naprawiono źródło Wolne Lektury")

    def _add_custom_source(self, button) -> None:
        dialog = Gtk.Dialog(
            title="Dodaj własne źródło",
            transient_for=self.window,
            modal=True,
        )
        dialog.set_default_size(700, 620)
        dialog.add_button("Anuluj", Gtk.ResponseType.CANCEL)
        dialog.add_button("Dodaj", Gtk.ResponseType.ACCEPT)

        content = dialog.get_content_area()
        content.set_spacing(10)
        content.set_margin_top(12)
        content.set_margin_bottom(12)
        content.set_margin_start(12)
        content.set_margin_end(12)

        form = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_child(form)
        content.append(scroll)

        name_entry = self._form_entry(form, "Nazwa źródła")
        kind_label = Gtk.Label(label="Typ źródła")
        kind_label.set_xalign(0)
        form.append(kind_label)
        kind_row = Gtk.DropDown()
        kind_row.set_model(Gtk.StringList.new([
            "RSS / Atom", "OPDS", "HTML"
        ]))
        form.append(kind_row)
        url_entry = self._form_entry(
            form,
            "Adres źródła (dla RSS/Atom {query} jest opcjonalny)",
            "https://example.org/search?q={query}",
        )
        hint = Gtk.Label(
            label=(
                "W feedzie bez {query} program przeszuka pobrane wpisy lokalnie. "
                "Można też użyć {category}, {language} i {limit}."
            )
        )
        hint.set_wrap(True)
        hint.set_xalign(0)
        hint.add_css_class("dim-label")
        form.append(hint)

        html_fields = {
            "results_selector": ("Selektor wyników", ".book"),
            "title_selector": ("Selektor tytułu", "h2 a"),
            "link_selector": ("Selektor strony książki", "h2 a"),
            "cover_selector": ("Selektor okładki (opcjonalny)", "img.cover"),
            "description_selector": ("Selektor opisu (opcjonalny)", ".description"),
            "author_selector": ("Selektor autora (opcjonalny)", ".author"),
            "download_selector": ("Selektor pobierania (opcjonalny)", "a.download"),
        }
        entries = {
            key: self._form_entry(form, label, placeholder)
            for key, (label, placeholder) in html_fields.items()
        }
        media_label = Gtk.Label(label="Rodzaj mediów")
        media_label.set_xalign(0)
        form.append(media_label)
        media_row = Gtk.DropDown()
        media_row.set_model(Gtk.StringList.new([
            "Automatycznie", "Ebook/dokument", "Audiobook"
        ]))
        form.append(media_row)

        def update_kind_visibility(row, _param) -> None:
            is_html = row.get_selected() == 2
            for entry in entries.values():
                entry.get_parent().set_visible(is_html)
            media_label.set_visible(is_html)
            media_row.set_visible(is_html)

        kind_row.connect("notify::selected", update_kind_visibility)
        update_kind_visibility(kind_row, None)

        def response_handler(source_dialog, response) -> None:
            if response != Gtk.ResponseType.ACCEPT:
                source_dialog.destroy()
                return
            name = name_entry.get_text().strip()
            search_url = url_entry.get_text().strip().strip(" \t\n\r\"'")
            kind = {
                0: "feed",
                1: "opds",
                2: "html",
            }.get(kind_row.get_selected())
            parsed_url = urllib.parse.urlparse(search_url.replace("{query}", "q"))
            local_host = parsed_url.hostname in ("localhost", "127.0.0.1", "::1")
            if (
                not name
                or (kind != "feed" and "{query}" not in search_url)
                or parsed_url.scheme.lower() not in ("http", "https")
                or not parsed_url.netloc
                or " " in search_url
                or local_host
            ):
                self.window.toast(
                    "Podaj nazwę i prawidłowy adres HTTP(S) bez spacji. "
                    "Dla HTML oraz OPDS użyj znacznika {query}. "
                    "Nie używaj adresów localhost."
                )
                return
            if kind is None:
                self.window.toast("Wybierz prawidłowy typ źródła.")
                return
            config = {
                "id": f"custom-{uuid.uuid4().hex[:12]}",
                "name": name,
                "kind": kind,
                "search_url": search_url,
            }
            if kind == "html":
                for key, entry in entries.items():
                    config[key] = entry.get_text().strip()
                if not all(
                    config[key] for key in
                    ("results_selector", "title_selector", "link_selector")
                ):
                    self.window.toast(
                        "HTML wymaga selektorów wyników, tytułu i odnośnika."
                    )
                    return
                config["media_type"] = {
                    0: "auto", 1: "ebook", 2: "audio"
                }.get(media_row.get_selected(), "auto")

            sources = list(self.settings.get("custom_sources", []))
            sources.append(config)
            self.settings.set("custom_sources", sources)
            enabled = dict(self.settings.get("enable_sources", {}))
            enabled[config["id"]] = True
            self.settings.set("enable_sources", enabled)
            self.window.search_manager.reload_custom_sources()
            self._refresh_custom_source_rows()
            source_dialog.destroy()

        dialog.connect("response", response_handler)
        dialog.present()

    @staticmethod
    def _form_entry(form, label: str, placeholder: str = "") -> Gtk.Entry:
        row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        label_widget = Gtk.Label(label=label)
        label_widget.set_xalign(0)
        entry = Gtk.Entry(placeholder_text=placeholder)
        row.append(label_widget)
        row.append(entry)
        form.append(row)
        return entry

    def _remove_custom_source(self, button, source_id: str) -> None:
        sources = [
            source for source in self.settings.get("custom_sources", [])
            if isinstance(source, dict) and source.get("id") != source_id
        ]
        enabled = dict(self.settings.get("enable_sources", {}))
        enabled.pop(source_id, None)
        self.settings.set("custom_sources", sources)
        self.settings.set("enable_sources", enabled)
        self.window.search_manager.reload_custom_sources()
        self._refresh_custom_source_rows()

    def _choose_folder(self, button, row) -> None:
        dialog = Gtk.FileDialog(title=tr("choose_folder"))
        dialog.select_folder(self.window, None, self._folder_chosen, row)

    def _folder_chosen(self, dialog, result, row) -> None:
        try:
            folder = dialog.select_folder_finish(result)
        except Exception:  # noqa: BLE001
            return
        if folder:
            path = folder.get_path()
            if path:
                self.settings.set("download_dir", path)
                row.set_subtitle(path)
