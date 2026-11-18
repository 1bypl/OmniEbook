"""Ebook/document reader with the animated page-flip widget and typography tools."""

from __future__ import annotations

import threading
import time
from pathlib import Path

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk  # noqa: E402

from ...config import Settings
from ...constants import user_cache_dir, user_imports_dir
from ...i18n import tr
from ...readers import paginate, read_document, read_epub_images
from ..widgets.page_flip import PageFlip

READER_PALETTES = {
    "sepia": ("#f4ecd8", "#5b4636"),
    "light": ("#ffffff", "#202124"),
    "dark": ("#1b1b1b", "#e8e8e8"),
    "green": ("#e8f2e4", "#2c3e2e"),
}


class ReaderView(Gtk.Box):
    def __init__(self, window, **kwargs) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4, **kwargs)
        self.window = window
        self.settings = Settings()
        self.book = None
        self._load_generation = 0
        self._restoring_page = False
        self._toc_entries: list[str] = []

        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        toolbar.set_margin_top(6)
        toolbar.set_margin_start(12)
        toolbar.set_margin_end(12)
        back = Gtk.Button()
        back_content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        back_icon = Gtk.Image.new_from_icon_name("go-previous-symbolic")
        back_icon.set_pixel_size(18)
        back_content.append(back_icon)
        back_content.append(Gtk.Label(label=tr("back")))
        back.set_child(back_content)
        back.set_tooltip_text(tr("back"))
        back.connect("clicked", lambda *_: self.window.go_back())
        toolbar.append(back)
        self.title_label = Gtk.Label(label="")
        self.title_label.add_css_class("heading")
        self.title_label.set_hexpand(True)
        self.title_label.set_xalign(0)
        toolbar.append(self.title_label)
        self.contents_button = Gtk.MenuButton(
            label="Spis treści", tooltip_text="Nawiguj po rozdziałach",
        )
        self.contents_popover = Gtk.Popover()
        self.contents_list = Gtk.ListBox()
        self.contents_list.set_selection_mode(Gtk.SelectionMode.NONE)
        contents_scroll = Gtk.ScrolledWindow()
        contents_scroll.set_min_content_width(260)
        contents_scroll.set_min_content_height(180)
        contents_scroll.set_max_content_height(420)
        contents_scroll.set_child(self.contents_list)
        self.contents_popover.set_child(contents_scroll)
        self.contents_button.set_popover(self.contents_popover)
        self.contents_button.set_sensitive(False)
        toolbar.append(self.contents_button)
        zoom_out = Gtk.Button(label="🔍−")
        zoom_out.set_tooltip_text(tr("zoom_out"))
        zoom_out.connect("clicked", lambda *_: self._zoom(-2))
        zoom_in = Gtk.Button(label="🔍+")
        zoom_in.set_tooltip_text(tr("zoom_in"))
        zoom_in.connect("clicked", lambda *_: self._zoom(2))
        toolbar.append(zoom_out)
        toolbar.append(zoom_in)
        bookmark = Gtk.Button(label="🔖")
        bookmark.set_tooltip_text(tr("bookmarks"))
        bookmark.connect("clicked", self._save_position)
        toolbar.append(bookmark)
        self.favorite_btn = Gtk.Button(label="☆")
        self.favorite_btn.set_tooltip_text(tr("add_favorite"))
        self.favorite_btn.connect("clicked", self._toggle_favorite)
        toolbar.append(self.favorite_btn)
        fullscreen = Gtk.Button(label="⛶")
        fullscreen.set_tooltip_text(tr("fullscreen"))
        fullscreen.connect("clicked", lambda *_: self.window.fullscreen())
        toolbar.append(fullscreen)
        self.append(toolbar)

        self.status = Gtk.Label(label="")
        self.status.add_css_class("dim-label")
        self.status.set_xalign(0)
        self.append(self.status)

        self.flip = PageFlip()
        frame = Gtk.Frame()
        frame.set_margin_start(24)
        frame.set_margin_end(24)
        frame.set_child(self.flip)
        viewport = Gtk.ScrolledWindow()
        viewport.set_vexpand(True)
        viewport.set_hexpand(True)
        viewport.set_child(frame)
        self.append(viewport)

        nav = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        nav.set_margin_start(24)
        nav.set_margin_end(24)
        nav.set_margin_bottom(10)
        first_btn = Gtk.Button(label="⏮")
        first_btn.set_tooltip_text("Pierwsza strona (Home)")
        first_btn.connect("clicked", lambda *_: self.flip.set_page(0, animate=True))
        prev_btn = Gtk.Button(label="‹")
        prev_btn.set_tooltip_text("Poprzednia strona (← / Page Up)")
        prev_btn.connect("clicked", lambda *_: self.flip.prev())
        next_btn = Gtk.Button(label="›")
        next_btn.set_tooltip_text("Następna strona (→ / Page Down)")
        next_btn.connect("clicked", lambda *_: self.flip.next())
        last_btn = Gtk.Button(label="⏭")
        last_btn.set_tooltip_text("Ostatnia strona (End)")
        last_btn.connect(
            "clicked",
            lambda *_: self.flip.set_page(self.flip.page_count() - 1, animate=True),
        )
        images_btn = Gtk.Button(label="🖼 Obrazy")
        images_btn.set_tooltip_text("Przejdź do pierwszej strony z obrazkiem")
        images_btn.connect("clicked", self._jump_to_image)
        self.slider = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 1, 1)
        self.slider.set_hexpand(True)
        self.slider.connect("value-changed", self._on_slider)
        self.page_label = Gtk.Label(label="")
        nav.append(first_btn)
        nav.append(prev_btn)
        nav.append(next_btn)
        nav.append(last_btn)
        nav.append(images_btn)
        nav.append(self.slider)
        nav.append(self.page_label)
        self.append(nav)

        self.flip.connect("page-changed", lambda *_: self._update_page_label())
        key_controller = Gtk.EventControllerKey()
        key_controller.connect("key-pressed", self._on_key_pressed)
        self.flip.add_controller(key_controller)
        self._apply_typography()

    # --------------------------------------------------------------- loading
    @staticmethod
    def _diag(line: str) -> None:
        try:
            log = user_cache_dir() / "reader.log"
            log.parent.mkdir(parents=True, exist_ok=True)
            with log.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")
        except Exception:  # noqa: BLE001
            pass

    def _update_favorite_button(self) -> None:
        favorite = bool(self.book and self.book.favorite)
        self.favorite_btn.set_label("⭐" if favorite else "☆")
        self.favorite_btn.set_tooltip_text(
            tr("remove_favorite") if favorite else tr("add_favorite"))

    def _toggle_favorite(self, *_args) -> None:
        """Dodaj/ usuń bieżącą książkę z ulubionych bez opuszczania czytnika."""
        if not self.book:
            return
        favorite = not self.book.favorite
        self.book.favorite = favorite
        self.window.library.db.set_favorite(self.book.id, favorite)
        # Książka z wyszukiwania może jeszcze nie być w bazie - zapisujemy ją.
        self.window.library.add_result(self.book)
        self._update_favorite_button()
        self.window.refresh_badges()
        self.window.toast(
            tr("add_favorite") if favorite else tr("remove_favorite"))

    def load(self, book) -> None:
        self._load_generation += 1
        generation = self._load_generation
        self.book = book
        self._update_favorite_button()
        self._last_text = ""
        self._last_image_pages = []
        self._toc_entries = []
        self.flip.set_pages([""])
        self.status.set_label("Otwieranie dokumentu…")
        self.title_label.set_label(book.title)
        self.title_label.set_tooltip_text(book.author_string)

        def status(message: str) -> None:
            def update() -> bool:
                if generation == self._load_generation:
                    self.status.set_label(message)
                return False
            GLib.idle_add(update)

        def extract(path: Path) -> tuple[str, list[str]]:
            # Old downloads may have no extension (arXiv) - sniff the format
            # and work on a copy with the proper suffix.
            if path.suffix.lower() not in (
                ".epub", ".pdf", ".txt", ".md", ".html", ".htm", ".fb2",
                ".docx", ".odt", ".rtf", ".djvu", ".cbz", ".cbr",
                ".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tif",
                ".tiff",
            ):
                try:
                    import shutil
                    from ...core.formats import detect_format, sniff_mime
                    fmt = detect_format(path.name, sniff=True, mime=sniff_mime(path))
                    if fmt and fmt != "unknown":
                        renamed = path.with_name(f"{path.name}.{fmt}")
                        if not renamed.exists():
                            shutil.copy2(path, renamed)
                        path = renamed
                except Exception:  # noqa: BLE001
                    pass
            content = ""
            toc_entries: list[str] = []
            if path.suffix.lower() == ".pdf":
                # Interleave each page's text with its own images, so a photo
                # appears directly below the description it belongs to.
                try:
                    from ...readers import read_pdf_interleaved
                    content, _meta = read_pdf_interleaved(path)
                    self._diag(
                        f"  PDF: {_meta.get('pages', 0)} stron, "
                        f"{content.count('@img:')} obrazów wplecionych"
                    )
                except Exception as exc:  # noqa: BLE001
                    self._diag(f"  błąd PDF interleaved: {exc}")
            if not content:
                content, metadata = read_document(path)
                toc_entries = metadata.get("toc", [])
            if not content:
                try:
                    from ...libreoffice import DocumentConverter
                    converter = DocumentConverter()
                    content = converter.to_text(path, language=book.language)
                    if converter.last_ocr_warning:
                        status(converter.last_ocr_warning)
                except Exception:  # noqa: BLE001
                    pass
            if not content and path.suffix.lower() == ".pdf":
                status("Ten PDF to prawdopodobnie skan bez warstwy tekstu "
                       "(wymaga OCR). Możesz pobrać plik ⬇️ i otworzyć go "
                       "w zewnętrznym czytniku z OCR.")
            return content, toc_entries

        def worker() -> None:
            text = ""
            toc_entries: list[str] = []
            self._diag(
                f"--- {book.title[:60]} | format={book.file_format} | "
                f"źródło={book.source} | url={book.download_url[:80]}"
            )
            path_str = book.local_path
            if path_str and Path(path_str).exists():
                status("Otwieranie dokumentu…")
                text, toc_entries = extract(Path(path_str))
            if not text and book.download_url:
                status("⬇️ Pobieranie książki do podglądu…")
                try:
                    from ...core.downloader import (
                        DownloadManager, resolve_download, _safe_filename,
                    )
                    url, filename, reason = resolve_download(book)
                    if not url:
                        raise RuntimeError(reason or "brak adresu pliku")
                    cache_name = _safe_filename(
                        filename or f"{book.id}.{book.file_format or 'epub'}")
                    cached = user_imports_dir() / cache_name
                    if cached.exists() and cached.stat().st_size > 0:
                        # Drugie otwarcie tej samej pozycji nie wymaga sieci.
                        status("Otwieranie pobranego wcześniej pliku…")
                        self._diag(f"  użyto pliku z cache: {cached.name}")
                        text, toc_entries = extract(cached)
                        book.local_path = str(cached)
                        self.window.library.set_local_path(
                            book.id, str(cached), cached.stat().st_size)
                    else:
                        dm = DownloadManager()
                        task = dm.enqueue(
                            url,
                            filename=filename or f"{book.id}.{book.file_format or 'epub'}",
                            book_id=book.id,
                            destination_dir=user_imports_dir(),
                        )
                        for attempt in range(500):  # up to 50 s
                            if task.state in ("done", "error", "cancelled"):
                                break
                            if attempt % 30 == 0:
                                status(f"Pobieranie… {attempt // 10} s")
                            time.sleep(0.1)
                        if not task.path or not task.path.exists():
                            raise RuntimeError(task.error or "pobieranie nie udało się")
                        status("Otwieranie dokumentu…")
                        self._diag(
                            f"  pobrano: {task.path.name} ({task.path.stat().st_size} B)")
                        book.local_path = str(task.path)
                        self.window.library.add_result(book)
                        self.window.library.set_local_path(
                            book.id, str(task.path), task.path.stat().st_size)
                        text, toc_entries = extract(task.path)
                except Exception as exc:  # noqa: BLE001
                    status(f"Nie udało się otworzyć: {exc}")
            self._diag(f"  wyciągnięto znaków: {len(text)}")
            self._diag(f"  znaczników @img: {text.count('@img:')}")
            if not text:
                header = f"{book.title}\n{book.author_string}\n\n"
                detail = book.description or (
                    f"Źródło: {book.source_url or book.download_url}\n\n"
                    "Nie udało się automatycznie odczytać tekstu z tego pliku. "
                    "Użyj przycisku ⬇️, aby pobrać dokument i otworzyć go "
                    "w czytniku LibreOffice."
                )
                text = header + detail
                status("Nie udało się wyciągnąć tekstu — pokazuję informacje o książce.")
            else:
                status("")
            if generation != self._load_generation:
                return
            image_pages: list[str] = []
            if book.file_format == "epub":
                # Use the FINAL path - it may have been downloaded above.
                final_path = book.local_path
                if final_path and Path(final_path).exists():
                    image_pages = read_epub_images(Path(final_path))
            elif book.file_format in ("cbz", "cbr"):
                image_pages = [
                    line.strip() for line in text.splitlines()
                    if line.strip().startswith("@img:")
                ]
            if generation != self._load_generation:
                return
            # Remember for zoom: rebuilding pages must preserve image markers.
            self._last_image_pages = image_pages
            self._last_text = text
            GLib.idle_add(
                self._finish_load, text, image_pages, generation, toc_entries,
            )

        threading.Thread(target=worker, daemon=True).start()

    def _finish_load(
        self, text: str, image_pages: list[str] | None = None,
        generation: int | None = None, toc_entries: list[str] | None = None,
    ) -> bool:
        if generation is not None and generation != self._load_generation:
            return False
        text_pages = [
            p.text for p in paginate(text, chars_per_page=self._chars_per_page())
        ]
        # read_epub() already embeds @img: markers for inline illustrations;
        # only add the separate scanned-page list when the text has none.
        is_comic = bool(self.book and self.book.file_format in ("cbz", "cbr"))
        if image_pages and "@img:" in text and not is_comic:
            image_pages = []
        self._last_image_pages = image_pages
        if image_pages:
            if is_comic:
                page_texts = image_pages
                self.status.set_label("Komiks — każda strona wyświetlana osobno.")
            else:
                # Scanned EPUBs: real page images first. Add OCR text only for
                # pages that actually carry prose (skip "Page N" stubs).
                import re
                prose = [p for p in text_pages if len(p) > 250 and not re.match(
                    r"^\s*Page\s+\d+", p)]
                page_texts = image_pages + prose
                self.status.set_label(
                    "Tryb skanu — obrazy stron oraz tekst rozpoznany z pozostałych."
                )
        else:
            page_texts = text_pages
        self._toc_entries = toc_entries or []
        self._populate_contents(self._toc_entries, page_texts)
        saved = self.window.library.db.load_progress(self.book.id) if self.book else 0.0
        self._restoring_page = True
        self.flip.set_pages(page_texts)
        self.slider.set_range(0, max(0, len(page_texts) - 1))
        if saved and page_texts:
            self.flip.set_page(int(saved * (len(page_texts) - 1)))
        self._restoring_page = False
        self._update_page_label()
        return False

    def _populate_contents(self, entries: list[str], pages: list[str]) -> None:
        self.contents_list.remove_all()
        links: list[tuple[str, int]] = []
        search_pages = pages[1:] if len(pages) > 1 else pages
        offset = len(pages) - len(search_pages)
        for entry in entries:
            needle = " ".join(entry.split()).casefold()
            if not needle:
                continue
            for index, page in enumerate(search_pages, start=offset):
                normalized = " ".join(page.split()).casefold()
                if needle in normalized:
                    links.append((entry, index))
                    break
        for title, page in links:
            row = Gtk.ListBoxRow()
            button = Gtk.Button(label=title)
            button.set_halign(Gtk.Align.FILL)
            button.connect("clicked", self._go_to_contents_page, page)
            row.set_child(button)
            self.contents_list.append(row)
        self.contents_button.set_sensitive(bool(links))

    def _go_to_contents_page(self, _button, page: int) -> None:
        self.flip.set_page(page, animate=True)
        self.contents_popover.popdown()

    # ------------------------------------------------------------ typography
    def _apply_typography(self) -> None:
        family = self.settings.get("font_family", "Sans")
        size = int(self.settings.get("font_size", 18))
        line_spacing = float(self.settings.get("line_spacing", 1.4))
        margin = int(self.settings.get("margin", 40))
        theme = self.settings.get("reader_theme", "sepia")
        bg, fg = READER_PALETTES.get(theme, READER_PALETTES["sepia"])
        self.flip.set_typography(family, size, line_spacing, margin)
        self.flip.set_theme(bg, fg)

    def _chars_per_page(self) -> int:
        size = max(8, int(self.settings.get("font_size", 18)))
        spacing = max(1.0, float(self.settings.get("line_spacing", 1.4)))
        margin = max(20, int(self.settings.get("margin", 40)))
        density = (40 / margin) * (1.4 / spacing)
        return max(300, int(size * 100 * density))

    def _zoom(self, delta: int) -> None:
        size = max(8, min(48, int(self.settings.get("font_size", 18)) + delta))
        self.settings.set("font_size", size)
        self._apply_typography()
        self._finish_load_from_existing()

    def _finish_load_from_existing(self) -> None:
        if not self.flip.pages:
            return
        progress = (
            self.flip.current / (self.flip.page_count() - 1)
            if self.flip.page_count() > 1 else 0.0
        )
        # Rebuild from the last raw text/images - never re-paginate "@img:"
        # markers, which would turn image pages into literal text.
        text = getattr(self, "_last_text", "") or "\n\n".join(
            p for p in self.flip.pages if not p.startswith("@img:")
        )
        images = getattr(self, "_last_image_pages", []) or []
        pages = paginate(text, chars_per_page=self._chars_per_page())
        text_pages = [p.text for p in pages]
        if images and "@img:" not in text:
            import re
            text_pages = [p for p in text_pages if len(p) > 250 and not re.match(
                r"^\s*Page\s+\d+", p)]
        page_texts = images + text_pages
        self._populate_contents(self._toc_entries, page_texts)
        self._restoring_page = True
        self.flip.set_pages(page_texts)
        self.slider.set_range(0, max(0, self.flip.page_count() - 1))
        if len(page_texts) > 1:
            self.flip.set_page(round(progress * (len(page_texts) - 1)))
        self._restoring_page = False
        self._update_page_label()

    # -------------------------------------------------------------- navigation
    def _jump_to_image(self, *_args) -> None:
        for index, page in enumerate(self.flip.pages):
            if "@img:" in page:
                self.flip.set_page(index)
                self.status.set_label(
                    f"Obrazek {sum(1 for p in self.flip.pages[:index + 1] if '@img:' in p)}"
                    f" z {sum(1 for p in self.flip.pages if '@img:' in p)}")
                return
        self.status.set_label("Ta książka nie ma osadzonych obrazków.")

    def _on_slider(self, slider) -> None:
        value = int(slider.get_value())
        if value != self.flip.current:
            self.flip.set_page(value, animate=True)

    def _update_page_label(self, *_args) -> None:
        self.page_label.set_label(
            f"{tr('page')} {self.flip.current + 1} {tr('of')} {self.flip.page_count()}"
        )
        self.slider.set_value(self.flip.current)
        if not self._restoring_page and self.book and self.flip.page_count() > 1:
            self.window.library.db.save_progress(
                self.book.id,
                self.flip.current / (self.flip.page_count() - 1),
            )

    def _on_key_pressed(self, _controller, keyval, _keycode, _state) -> bool:
        from gi.repository import Gdk
        if keyval in (Gdk.KEY_Page_Down, Gdk.KEY_Right, Gdk.KEY_space):
            self.flip.next()
            return True
        if keyval in (Gdk.KEY_Page_Up, Gdk.KEY_Left, Gdk.KEY_BackSpace):
            self.flip.prev()
            return True
        if keyval == Gdk.KEY_Home:
            self.flip.set_page(0, animate=True)
            return True
        if keyval == Gdk.KEY_End:
            self.flip.set_page(self.flip.page_count() - 1, animate=True)
            return True
        return False

    def _save_position(self, *_args) -> None:
        if self.book and self.flip.page_count() > 1:
            position = self.flip.current / (self.flip.page_count() - 1)
            self.window.library.db.save_progress(self.book.id, position)
            self.window.toast(tr("bookmarks"))
