"""Portable core tests; these do not require GTK or Linux-specific services."""

from pathlib import Path
import os
import sqlite3
import subprocess
import tempfile
import unittest
import zipfile

from omniebook.core.database import Database, SCHEMA
from omniebook.core.formats import is_supported
from omniebook.core.library import Library
from omniebook.core.models import Book, SearchQuery
from omniebook.constants import (
    default_download_dir, user_cache_dir, user_config_dir, user_data_dir,
)
from omniebook.process import run_hidden
from omniebook.readers import (
    decode_text, paginate, read_comic, read_document, read_epub, read_epub_images,
)
from omniebook.sources.custom import CustomSourceProvider, WOLNELEKTURY_SOURCE


class LibraryImportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.database = Database(self.root / "library.db")
        self.library = Library(self.database)

    def tearDown(self) -> None:
        self.database._connect().close()
        self.temp_dir.cleanup()

    def test_import_file_rejects_unsupported_types(self) -> None:
        supported = self.root / "Book.TXT"
        supported.write_text("Book text", encoding="utf-8")
        unsupported = self.root / "notes.csv"
        unsupported.write_text("a,b", encoding="utf-8")
        sniffed = self.root / "download-without-extension"
        sniffed.write_bytes(b"%PDF-1.7\n")

        self.assertEqual(self.library.import_file(supported).title, "Book")
        self.assertIsNone(self.library.import_file(unsupported))
        self.assertEqual(self.library.import_file(sniffed).file_format, "pdf")
        image = self.root / "cover.webp"
        image.write_bytes(b"image data")
        imported_image = self.library.import_file(image)
        self.assertIsNotNone(imported_image)
        self.assertEqual(imported_image.file_format, "webp")
        self.assertEqual(self.database.count(), 3)

    def test_folder_import_skips_unsupported_files_and_keeps_nested_books(self) -> None:
        nested = self.root / "nested"
        nested.mkdir()
        (self.root / "Book.epub").write_bytes(b"not parsed during import")
        (nested / "Notes.csv").write_text("a,b", encoding="utf-8")
        (nested / "Story.txt").write_text("Text", encoding="utf-8")

        imported = self.library.import_folder(self.root)

        self.assertEqual({book.title for book in imported}, {"Book", "Story"})
        self.assertTrue(all(book.is_new for book in imported))
        self.assertEqual(self.database.count(), 2)

    def test_deleting_collection_keeps_books_and_removes_membership(self) -> None:
        path = self.root / "Book.txt"
        path.write_text("Book text", encoding="utf-8")
        book = self.library.import_file(path)
        assert book is not None
        self.database.create_collection("shelf-1", "Test shelf")
        self.database.add_to_collection("shelf-1", book.id)

        self.database.delete_collection("shelf-1")

        self.assertEqual(self.database.list_collections(), [])
        self.assertEqual(self.database.books_in_collection("shelf-1"), [])
        self.assertIsNotNone(self.database.get(book.id))

    def test_delete_many_removes_selected_books_and_their_collection_links(self) -> None:
        books = []
        for name in ("First.txt", "Second.txt", "Third.txt"):
            path = self.root / name
            path.write_text(name, encoding="utf-8")
            imported = self.library.import_file(path)
            assert imported is not None
            books.append(imported)

        self.database.create_collection("shelf-1", "Test shelf")
        for book in books:
            self.database.add_to_collection("shelf-1", book.id)
        self.database.save_progress(books[0].id, 0.5)

        removed = self.library.delete_many([books[0].id, books[1].id, books[0].id])

        self.assertEqual(removed, 2)
        self.assertEqual(self.database.count(), 1)
        self.assertEqual(
            [b.id for b in self.database.books_in_collection("shelf-1")],
            [books[2].id],
        )
        progress_rows = self.database._connect().execute(
            "SELECT COUNT(*) FROM reading_progress"
        ).fetchone()[0]
        self.assertEqual(progress_rows, 0)
        self.assertIsNotNone(self.database.get(books[2].id))

    def test_delete_many_with_empty_selection_does_nothing(self) -> None:
        self.assertEqual(self.library.delete_many([]), 0)
        self.assertEqual(self.database.count(), 0)

    def test_imports_are_marked_new_and_stay_sorted_after_dismissal(self) -> None:
        first_path = self.root / "First.txt"
        second_path = self.root / "Second.txt"
        first_path.write_text("First", encoding="utf-8")
        second_path.write_text("Second", encoding="utf-8")

        first = self.library.import_file(first_path)
        second = self.library.import_file(second_path)
        first.date_added = "2025-01-01T00:00:00"
        second.date_added = "2025-01-02T00:00:00"
        self.database.upsert(first)
        self.database.upsert(second)
        results = self.database.search(SearchQuery(page_size=10)).items

        self.assertTrue(first.is_new)
        self.assertTrue(second.is_new)
        self.assertEqual([book.id for book in results[:2]], [second.id, first.id])

        second_date = second.date_added
        self.database.mark_seen(second.id)
        refreshed = self.database.search(SearchQuery(page_size=10)).items

        self.assertFalse(self.database.get(second.id).is_new)
        self.assertEqual(self.database.get(second.id).date_added, second_date)
        self.assertEqual([book.id for book in refreshed[:2]], [second.id, first.id])

    def test_collection_addition_marks_new_and_sorts_by_membership_time(self) -> None:
        first_path = self.root / "Zebra.txt"
        second_path = self.root / "Aardvark.txt"
        first_path.write_text("First", encoding="utf-8")
        second_path.write_text("Second", encoding="utf-8")
        first = self.library.import_file(first_path)
        second = self.library.import_file(second_path)
        assert first is not None and second is not None
        self.database.mark_seen(first.id)
        self.database.create_collection("shelf-1", "Test shelf")
        self.database.add_to_collection("shelf-1", second.id)
        self.database.add_to_collection("shelf-1", first.id)
        with self.database.transaction() as connection:
            connection.execute(
                "UPDATE collection_items SET added_at='2025-01-02T00:00:00' "
                "WHERE collection_id='shelf-1' AND book_id=?",
                (first.id,),
            )
            connection.execute(
                "UPDATE collection_items SET added_at='2025-01-01T00:00:00' "
                "WHERE collection_id='shelf-1' AND book_id=?",
                (second.id,),
            )

        books = self.database.books_in_collection("shelf-1")

        self.assertEqual([book.id for book in books], [first.id, second.id])
        self.assertTrue(self.database.get(first.id).is_new)

    def test_existing_database_is_migrated_for_new_item_state(self) -> None:
        path = self.root / "legacy.db"
        legacy_schema = SCHEMA.replace(
            "    is_new          INTEGER NOT NULL DEFAULT 0,\n", ""
        ).replace(
            "    added_at      TEXT NOT NULL DEFAULT '',\n", ""
        )
        connection = sqlite3.connect(path)
        try:
            connection.executescript(legacy_schema)
            connection.execute(
                "INSERT INTO books (id, title) VALUES ('legacy', 'Legacy book')"
            )
            connection.execute(
                "INSERT INTO collections (id, name) VALUES ('shelf', 'Shelf')"
            )
            connection.execute(
                "INSERT INTO collection_items (collection_id, book_id) "
                "VALUES ('shelf', 'legacy')"
            )
            connection.commit()
        finally:
            connection.close()

        migrated = Database(path)

        try:
            self.assertFalse(migrated.get("legacy").is_new)
            self.assertIn(
                "added_at",
                {row["name"] for row in migrated._connect().execute(
                    "PRAGMA table_info(collection_items)"
                )},
            )
        finally:
            migrated._connect().close()

    def test_new_search_result_is_marked_new(self) -> None:
        book = Book(id="remote-book", title="Remote book", source="custom")

        self.library.add_result(book)

        self.assertTrue(self.database.get(book.id).is_new)


class ReaderUtilityTests(unittest.TestCase):
    def test_decode_text_handles_cyrillic_legacy_encodings_and_html_charset(self) -> None:
        self.assertEqual(decode_text("Привет".encode("cp1251")), "Привет")
        html = b'<meta charset=windows-1251><p>\xcf\xf0\xe8\xe2\xe5\xf2</p>'
        self.assertIn("Привет", decode_text(html))

    def test_decode_text_handles_dos_polish_code_page(self) -> None:
        polish = "Zażółć gęślą jaźń Pchnąć w tę łódź jeża"
        self.assertEqual(decode_text(polish.encode("cp852")), polish)
        document = (
            b'<?xml version="1.0" encoding="ibm852"?>'
            + f"<p>{polish}</p>".encode("cp852")
        )
        self.assertEqual(decode_text(document), document.decode("cp852"))

    def test_decode_text_prefers_valid_utf8_and_detects_utf16_bom(self) -> None:
        polish = "Zażółć gęślą jaźń — Pchnąć w tę łódź jeża."
        self.assertEqual(decode_text(polish.encode("utf-8")), polish)
        self.assertEqual(decode_text(polish.encode("utf-16")), polish)
        self.assertEqual(decode_text(polish.encode("cp1250")), polish)

    def test_image_suffix_is_detected_from_content_not_extension(self) -> None:
        from omniebook.readers import _image_suffix

        png = b"\x89PNG\r\n\x1a\n" + b"data" * 8
        jpeg = b"\xff\xd8\xff\xe0" + b"data" * 8
        self.assertEqual(_image_suffix(png, ".jpg"), ".png")
        self.assertEqual(_image_suffix(jpeg, ".png"), ".jpg")
        self.assertEqual(_image_suffix(b"not an image", ".xyz"), ".png")

    def test_decode_text_finds_encoding_declaration_later_in_head(self) -> None:
        expected = "Zażółć gęślą jaźń"
        prefix = b"<html><head>" + b" " * 600 + \
            b'<meta charset="windows-1250"></head><body>'
        document = prefix + expected.encode("cp1250") + b"</body></html>"

        self.assertIn(expected, decode_text(document))

    def test_read_plain_uses_correct_utf8_decoding(self) -> None:
        expected = "Zażółć gęślą jaźń — tekst z polskimi znakami."
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "polski.txt"
            path.write_bytes(expected.encode("utf-8"))

            text, _metadata = read_document(path)

        self.assertEqual(text, expected)

    def test_cbz_pages_are_extracted_in_natural_page_order(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "comic.cbz"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("pages/page10.png", b"page 10")
                archive.writestr("pages/page2.jpg", b"page 2")
                archive.writestr("pages/page1.jpg", b"page 1")

            from unittest.mock import patch
            with patch(
                "omniebook.constants.user_cache_dir",
                return_value=Path(temp_dir) / "cache",
            ):
                text, metadata = read_comic(path)
                page_data = [
                    Path(line[5:]).read_bytes()
                    for line in text.splitlines()
                    if line.startswith("@img:")
                ]

        self.assertEqual(page_data, [b"page 1", b"page 2", b"page 10"])
        self.assertEqual(metadata["pages"], 3)

    def test_pagination_keeps_inline_images_with_surrounding_text(self) -> None:
        pages = paginate(
            "First paragraph.\n@img:C:\\cover.png\nLast paragraph.",
            chars_per_page=900,
        )

        self.assertEqual(len(pages), 1)
        self.assertLess(
            pages[0].text.index("First paragraph."),
            pages[0].text.index("@img:"),
        )
        self.assertLess(
            pages[0].text.index("@img:"),
            pages[0].text.index("Last paragraph."),
        )

    def test_epub_table_of_contents_is_available_for_reader_navigation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "book.epub"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr(
                    "META-INF/container.xml",
                    '<container><rootfiles><rootfile full-path="OPS/book.opf"/>'
                    '</rootfiles></container>',
                )
                archive.writestr(
                    "OPS/book.opf",
                    '<package><manifest><item id="chapter" href="chapter.xhtml"/>'
                    '</manifest><spine><itemref idref="chapter"/></spine></package>',
                )
                archive.writestr(
                    "OPS/chapter.xhtml",
                    "<html><body><h1>Chapter One</h1><p>Story body.</p></body></html>",
                )
                archive.writestr(
                    "OPS/toc.ncx",
                    "<ncx><navMap><navPoint><navLabel><text>Chapter One</text>"
                    "</navLabel></navPoint></navMap></ncx>",
                )

            text, metadata = read_epub(path)

        self.assertIn("Chapter One", text)
        self.assertEqual(metadata["toc"], ["Chapter One"])

    def test_epub_inline_illustration_stays_between_its_paragraphs(self) -> None:
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "illustrated.epub"
            expected_image = b"expected atlas image"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr(
                    "META-INF/container.xml",
                    '<container><rootfiles><rootfile full-path="OPS/content/book.opf"/>'
                    '</rootfiles></container>',
                )
                archive.writestr(
                    "OPS/content/book.opf",
                    '<package><manifest><item id="chapter" href="text/chapter.xhtml"/>'
                    '</manifest><spine><itemref idref="chapter"/></spine></package>',
                )
                archive.writestr(
                    "OPS/content/text/chapter.xhtml",
                    "<html><body><p>Before illustration.</p>"
                    '<img src="../images/illustration.png"/>'
                    "<p>After illustration.</p></body></html>",
                )
                archive.writestr(
                    "OPS/content/images/illustration.png", expected_image,
                )
                archive.writestr(
                    "OPS/images/illustration.png", b"wrong relative image",
                )

            with patch(
                "omniebook.constants.user_cache_dir",
                return_value=Path(temp_dir),
            ):
                text, _metadata = read_epub(path)
                scanned_images = read_epub_images(path)
                image_marker = next(
                    line for line in text.splitlines()
                    if line.startswith("@img:")
                )
                inline_image_data = Path(image_marker[5:]).read_bytes()
                scanned_image_data = [
                    Path(image[5:]).read_bytes() for image in scanned_images
                ]

            pages = paginate(text, chars_per_page=900)

        self.assertEqual(len(pages), 1)
        page = pages[0].text
        self.assertLess(page.index("Before illustration."), page.index("@img:"))
        self.assertLess(page.index("@img:"), page.index("After illustration."))
        self.assertEqual(len(scanned_images), 1)
        self.assertEqual(inline_image_data, expected_image)
        self.assertEqual(scanned_image_data, [expected_image])

    def test_epub_image_spine_items_are_images_not_decoded_as_text(self) -> None:
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "magazine.epub"
            image_data = [
                b"\x89PNG\r\n\x1a\n\x00\xff\xfe",
                b"\xff\xd8\xff\x00\x80",
            ]
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr(
                    "META-INF/container.xml",
                    '<container><rootfiles><rootfile full-path="OPS/book.opf"/>'
                    '</rootfiles></container>',
                )
                archive.writestr(
                    "OPS/book.opf",
                    '<package><manifest>'
                    '<item id="one" href="images/page1.png" media-type="image/png"/>'
                    '<item id="two" href="images/page2.jpg" media-type="image/jpeg"/>'
                    '</manifest><spine><itemref idref="one"/>'
                    '<itemref idref="two"/></spine></package>',
                )
                archive.writestr("OPS/images/page1.png", image_data[0])
                archive.writestr("OPS/images/page2.jpg", image_data[1])

            with patch(
                "omniebook.constants.user_cache_dir",
                return_value=Path(temp_dir) / "cache",
            ):
                text, _metadata = read_epub(path)
                pages = paginate(text)
                extracted = [
                    Path(page.text[5:]).read_bytes()
                    for page in pages
                    if page.text.startswith("@img:")
                ]

        self.assertEqual(len(pages), 2)
        self.assertEqual(extracted, image_data)

    def test_epub_spine_cover_image_stays_between_chapters(self) -> None:
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "magazine.epub"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr(
                    "META-INF/container.xml",
                    '<container><rootfiles><rootfile full-path="OPS/book.opf"/>'
                    '</rootfiles></container>',
                )
                archive.writestr(
                    "OPS/book.opf",
                    '<package><manifest>'
                    '<item id="before" href="text/before.xhtml" '
                    'media-type="application/xhtml+xml"/>'
                    '<item id="cover" href="images/cover.jpg" '
                    'media-type="image/jpeg"/>'
                    '<item id="after" href="text/after.xhtml" '
                    'media-type="application/xhtml+xml"/>'
                    '</manifest><spine><itemref idref="before"/>'
                    '<itemref idref="cover"/><itemref idref="after"/>'
                    '</spine></package>',
                )
                archive.writestr(
                    "OPS/text/before.xhtml",
                    "<html><body><p>Before cover.</p></body></html>",
                )
                archive.writestr("OPS/images/cover.jpg", b"\xff\xd8\xffcover")
                archive.writestr(
                    "OPS/text/after.xhtml",
                    "<html><body><p>After cover.</p></body></html>",
                )

            with patch(
                "omniebook.constants.user_cache_dir",
                return_value=Path(temp_dir) / "cache",
            ):
                text, _metadata = read_epub(path)

        self.assertLess(text.index("Before cover."), text.index("@img:"))
        self.assertLess(text.index("@img:"), text.index("After cover."))
        self.assertNotIn("ÿ", text)

    def test_unknown_audio_mime_is_not_treated_as_importable(self) -> None:
        self.assertTrue(is_supported("track.mp3"))
        self.assertFalse(is_supported("track.unknown", "audio/x-unknown"))

    def test_common_comic_image_formats_are_supported(self) -> None:
        for extension in ("jpg", "jpeg", "png", "gif", "webp", "bmp", "tif", "tiff"):
            with self.subTest(extension=extension):
                self.assertTrue(is_supported(f"page.{extension}"))
        self.assertTrue(is_supported("comic.cbz"))


class CustomSourceTests(unittest.TestCase):
    def test_static_rss_feed_filters_entries_by_search_text(self) -> None:
        from unittest.mock import patch

        provider = CustomSourceProvider({
            "id": "custom-static-rss",
            "name": "Aktualności",
            "kind": "feed",
            "search_url": "https://news.example/feed.xml",
        })

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                return (
                    b"<rss><channel>"
                    b"<item><title>Atlas ryb</title><link>/fish</link></item>"
                    b"<item><title>Atlas grzybow</title><link>/mushrooms</link></item>"
                    b"</channel></rss>"
                )

            def geturl(self):
                return "https://news.example/feed.xml"

        with patch(
            "omniebook.sources.custom.urllib.request.urlopen",
            return_value=FakeResponse(),
        ):
            result = provider.search(SearchQuery(text="ryb"))

        self.assertEqual([book.title for book in result.items], ["Atlas ryb"])

    def test_rss_feed_maps_book_link_cover_and_audio_enclosure(self) -> None:
        provider = CustomSourceProvider({
            "id": "custom-rss",
            "name": "Katalog RSS",
            "kind": "feed",
            "search_url": "https://catalog.example/feed.xml?q={query}",
        })
        feed = (
            '<rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/">'
            "<channel><item><guid>book:atlas</guid>"
            "<title>Atlas ryb</title><link>/books/atlas</link>"
            "<author>Jan Autor</author><pubDate>Tue, 03 Jan 2023 10:00:00 GMT</pubDate>"
            "<description>&lt;p&gt;Ilustrowany atlas&lt;/p&gt;</description>"
            '<media:thumbnail url="/covers/atlas.jpg"/>'
            '<enclosure url="/audio/atlas.mp3" type="audio/mpeg"/>'
            "<category>przyroda</category></item></channel></rss>"
        )

        books = provider._parse_feed(feed, "https://catalog.example/feed.xml")

        self.assertEqual(len(books), 1)
        book = books[0]
        self.assertEqual(book.title, "Atlas ryb")
        self.assertEqual(book.authors, ["Jan Autor"])
        self.assertEqual(book.source_url, "https://catalog.example/books/atlas")
        self.assertEqual(book.cover_url, "https://catalog.example/covers/atlas.jpg")
        self.assertEqual(book.download_url, "https://catalog.example/audio/atlas.mp3")
        self.assertEqual(book.media_type.value, "audiobook")
        self.assertEqual(book.year, 2023)
        self.assertEqual(book.description, "Ilustrowany atlas")

    def test_wolnelektury_source_parses_its_result_cards(self) -> None:
        provider = CustomSourceProvider(WOLNELEKTURY_SOURCE)
        markup = (
            '<article class="l-books__item book-container-activator">'
            '<figure><a href="/katalog/lektura/czapla-ryby/">'
            '<img src="/media/book/cover.jpg"></a></figure>'
            '<h3><a href="/katalog/autor/ignacy-krasicki/">Ignacy Krasicki</a></h3>'
            '<h2><a href="/katalog/lektura/czapla-ryby/">Czapla, ryby i rak</a></h2>'
            '<span class="other-info s">Bajka Oświecenie</span></article>'
        )

        books = provider._parse_html(markup, "https://wolnelektury.pl/szukaj/")

        self.assertEqual(len(books), 1)
        book = books[0]
        self.assertEqual(book.title, "Czapla, ryby i rak")
        self.assertEqual(book.authors, ["Ignacy Krasicki"])
        self.assertEqual(
            book.source_url,
            "https://wolnelektury.pl/katalog/lektura/czapla-ryby/",
        )
        self.assertEqual(
            book.cover_url, "https://wolnelektury.pl/media/book/cover.jpg"
        )

    def test_search_url_template_encodes_query_and_parses_feed(self) -> None:
        from unittest.mock import patch
        from urllib.parse import parse_qs, urlparse

        provider = CustomSourceProvider({
            "id": "custom-query",
            "name": "Katalog",
            "kind": "opds",
            "search_url": "https://catalog.example/search?q={query}",
        })

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                return (
                    b'<feed xmlns="http://www.w3.org/2005/Atom"><entry>'
                    b"<id>fish</id><title>Ryby</title></entry></feed>"
                )

            def geturl(self):
                return "https://catalog.example/search"

        query = SearchQuery(text="ryby & grzyby")
        with patch(
            "omniebook.sources.custom.urllib.request.urlopen",
            return_value=FakeResponse(),
        ) as open_url:
            result = provider.search(query)

        request = open_url.call_args.args[0]
        self.assertEqual(
            parse_qs(urlparse(request.full_url).query)["q"],
            ["ryby & grzyby"],
        )
        self.assertEqual([book.title for book in result.items], ["Ryby"])

    def test_html_source_extracts_relative_book_metadata_and_audio_link(self) -> None:
        provider = CustomSourceProvider({
            "id": "custom-test",
            "name": "Katalog testowy",
            "kind": "html",
            "results_selector": "article.book",
            "title_selector": "h2 a",
            "link_selector": "h2 a",
            "cover_selector": "img.cover",
            "description_selector": ".description",
            "author_selector": ".author",
            "download_selector": "a.file",
        })
        markup = (
            '<article class="book"><h2><a href="/books/fish">Atlas ryb</a></h2>'
            '<img class="cover" src="/covers/fish.jpg">'
            '<p class="author">Jan Autor</p><p class="description">Opis atlasu</p>'
            '<a class="file" type="audio/mpeg" href="/audio/atlas.mp3">Audio</a>'
            "</article>"
        )

        books = provider._parse_html(markup, "https://catalog.example/search")

        self.assertEqual(len(books), 1)
        book = books[0]
        self.assertEqual(book.title, "Atlas ryb")
        self.assertEqual(book.authors, ["Jan Autor"])
        self.assertEqual(book.source_url, "https://catalog.example/books/fish")
        self.assertEqual(book.cover_url, "https://catalog.example/covers/fish.jpg")
        self.assertEqual(book.download_url, "https://catalog.example/audio/atlas.mp3")
        self.assertEqual(book.file_format, "mp3")
        self.assertEqual(book.media_type.value, "audiobook")

    def test_opds_source_reads_alternate_cover_and_acquisition_links(self) -> None:
        provider = CustomSourceProvider({
            "id": "custom-opds",
            "name": "Katalog OPDS",
            "kind": "opds",
            "search_url": "https://catalog.example/search?q={query}",
        })
        feed = (
            '<feed xmlns="http://www.w3.org/2005/Atom"><entry>'
            "<id>book:atlas</id><title>Atlas grzybów</title>"
            "<author><name>Anna Autorka</name></author>"
            "<summary>Ilustrowany przewodnik</summary>"
            "<published>2024-01-01</published>"
            '<link rel="alternate" type="text/html" href="/books/atlas"/>'
            '<link rel="http://opds-spec.org/image/thumbnail" '
            'type="image/jpeg" href="/covers/atlas.jpg"/>'
            '<link rel="http://opds-spec.org/acquisition/open-access" '
            'type="application/epub+zip" href="/files/atlas.epub"/>'
            "</entry></feed>"
        )

        books = provider._parse_opds(feed, "https://catalog.example/opds")

        self.assertEqual(len(books), 1)
        book = books[0]
        self.assertEqual(book.title, "Atlas grzybów")
        self.assertEqual(book.authors, ["Anna Autorka"])
        self.assertEqual(book.source_url, "https://catalog.example/books/atlas")
        self.assertEqual(book.cover_url, "https://catalog.example/covers/atlas.jpg")
        self.assertEqual(book.download_url, "https://catalog.example/files/atlas.epub")
        self.assertEqual(book.file_format, "epub")
        self.assertEqual(book.year, 2024)


@unittest.skipUnless(os.name == "nt", "Windows path behavior")
class WindowsPathTests(unittest.TestCase):
    def test_user_paths_use_roaming_and_local_appdata(self) -> None:
        from unittest.mock import patch

        with patch.dict(os.environ, {
            "APPDATA": r"C:\Users\reader\AppData\Roaming",
            "LOCALAPPDATA": r"C:\Users\reader\AppData\Local",
            "XDG_CONFIG_HOME": r"C:\xdg-config",
            "XDG_DATA_HOME": r"C:\xdg-data",
            "XDG_CACHE_HOME": r"C:\xdg-cache",
        }):
            self.assertEqual(
                user_config_dir(), Path(r"C:\Users\reader\AppData\Roaming\OmniEbook"),
            )
            self.assertEqual(
                user_data_dir(), Path(r"C:\Users\reader\AppData\Local\OmniEbook"),
            )
            self.assertEqual(
                user_cache_dir(),
                Path(r"C:\Users\reader\AppData\Local\OmniEbook\Cache"),
            )
            self.assertEqual(default_download_dir(), Path.home() / "Downloads")


@unittest.skipUnless(os.name == "nt", "Windows subprocess behavior")
class WindowsProcessTests(unittest.TestCase):
    def test_run_hidden_sets_no_console_creation_flags(self) -> None:
        from unittest.mock import patch

        with patch("omniebook.process.subprocess.run") as run:
            run_hidden(["optional-tool"], capture_output=True)

        options = run.call_args.kwargs
        self.assertTrue(options["creationflags"] & subprocess.CREATE_NO_WINDOW)
        self.assertTrue(
            options["startupinfo"].dwFlags & subprocess.STARTF_USESHOWWINDOW
        )


if __name__ == "__main__":
    unittest.main()
