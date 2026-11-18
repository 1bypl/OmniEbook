"""Audiobook player powered by GStreamer (playbin).

Supports every audio format GStreamer can decode: MP3, M4A/M4B, AAC, FLAC,
Ogg, Opus, WAV, WMA, AIFF and more. Falls back gracefully when GStreamer is
not installed.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

import gi
gi.require_version("Gtk", "4.0")
try:
    gi.require_version("Gst", "1.0")
    from gi.repository import Gst
    HAVE_GST = True
except (ValueError, ImportError):  # pragma: no cover - depends on system
    Gst = None
    HAVE_GST = False
from gi.repository import GLib, Gtk  # noqa: E402

from ...constants import user_imports_dir
from ...core.formats import human_duration
from ...i18n import tr


def _icon_content(icon_name: str, label: str = "") -> Gtk.Widget:
    icon = Gtk.Image.new_from_icon_name(icon_name)
    icon.set_pixel_size(20)
    if label:
        content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        content.append(icon)
        content.append(Gtk.Label(label=label))
        return content
    return icon


def _icon_button(icon_name: str, tooltip: str, label: str = "") -> Gtk.Button:
    button = Gtk.Button()
    button.set_child(_icon_content(icon_name, label))
    button.set_tooltip_text(tooltip)
    return button


class AudiobookPlayer(Gtk.Box):
    def __init__(self, window, **kwargs) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=10, **kwargs)
        self.window = window
        self.book = None
        self._seeking = False
        self._load_generation = 0
        self.set_margin_top(18)
        self.set_margin_start(24)
        self.set_margin_end(24)
        self.set_margin_bottom(18)

        back = _icon_button("go-previous-symbolic", tr("back"), tr("back"))
        back.set_halign(Gtk.Align.START)
        back.connect("clicked", lambda *_: self.stop_and_go_back())
        self.append(back)

        self.title = Gtk.Label(label="")
        self.title.add_css_class("title-2")
        self.append(self.title)
        self.status = Gtk.Label(label="")
        self.status.add_css_class("dim-label")
        self.status.set_wrap(True)
        self.append(self.status)

        if not HAVE_GST:
            warn = Gtk.Label(label="GStreamer nie jest zainstalowany - odtwarzanie audio niedostępne.")
            warn.add_css_class("dim-label")
            self.append(warn)
            self.player = None
        else:
            Gst.init(None)
            self.player = Gst.ElementFactory.make("playbin", "omniebook-player")
            if self.player is not None:
                self.player.set_property("volume", 0.8)
                self.bus = self.player.get_bus()
                self.bus.add_signal_watch()
                self.bus.connect("message", self._on_bus_message)
                self._timeout = GLib.timeout_add(500, self._update_position)
            else:
                warn = Gtk.Label(label="Nie można utworzyć odtwarzacza GStreamer (playbin).")
                warn.add_css_class("dim-label")
                self.append(warn)

        controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        controls.set_halign(Gtk.Align.CENTER)
        self.play_btn = _icon_button(
            "media-playback-start-symbolic", tr("listen"), tr("listen"),
        )
        self.play_btn.connect("clicked", self._toggle_play)
        rewind_btn = _icon_button(
            "media-seek-backward-symbolic", tr("rewind_15"), "15 s",
        )
        rewind_btn.connect("clicked", lambda *_: self._seek_by(-15))
        forward_btn = _icon_button(
            "media-seek-forward-symbolic", tr("forward_15"), "15 s",
        )
        forward_btn.connect("clicked", lambda *_: self._seek_by(15))
        self.stop_btn = _icon_button(
            "media-playback-stop-symbolic", tr("stop"), tr("stop"),
        )
        self.stop_btn.connect("clicked", self._stop)
        self.download_btn = _icon_button(
            "folder-download-symbolic", tr("download"), tr("download"),
        )
        self.download_btn.connect("clicked", lambda *_: self.book and self.window.download_book(self.book))
        self.favorite_btn = Gtk.Button(label="☆")
        self.favorite_btn.set_tooltip_text(tr("add_favorite"))
        self.favorite_btn.connect("clicked", self._toggle_favorite)
        controls.append(self.play_btn)
        controls.append(rewind_btn)
        controls.append(forward_btn)
        controls.append(self.stop_btn)
        controls.append(self.download_btn)
        controls.append(self.favorite_btn)
        self.append(controls)

        self.slider = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        self.slider.set_hexpand(True)
        self.slider.connect("value-changed", self._on_seek)
        self.append(self.slider)

        self.time_label = Gtk.Label(label="0:00 / 0:00")
        self.append(self.time_label)

        speed_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        speed_box.set_halign(Gtk.Align.CENTER)
        speed_box.append(Gtk.Label(label="Prędkość:"))
        self.speed = Gtk.DropDown.new_from_strings(["0.75×", "1×", "1.25×", "1.5×", "2×"])
        self.speed.set_selected(1)
        self.speed.connect("notify::selected", self._on_speed)
        speed_box.append(self.speed)
        self.append(speed_box)

        volume_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        volume_box.set_halign(Gtk.Align.CENTER)
        volume_box.append(Gtk.Image.new_from_icon_name("audio-volume-high-symbolic"))
        self.volume = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        self.volume.set_value(80)
        self.volume.set_size_request(160, -1)
        self.volume.set_tooltip_text(tr("volume"))
        self.volume.connect("value-changed", self._on_volume)
        volume_box.append(self.volume)
        self.append(volume_box)

    def _update_favorite_button(self) -> None:
        favorite = bool(self.book and self.book.favorite)
        self.favorite_btn.set_label("⭐" if favorite else "☆")
        self.favorite_btn.set_tooltip_text(
            tr("remove_favorite") if favorite else tr("add_favorite"))

    def _toggle_favorite(self, *_args) -> None:
        """Dodaj/ usuń audiobook z ulubionych bez opuszczania odtwarzacza."""
        if not self.book:
            return
        favorite = not self.book.favorite
        self.book.favorite = favorite
        self.window.library.db.set_favorite(self.book.id, favorite)
        self.window.library.add_result(self.book)
        self._update_favorite_button()
        self.window.refresh_badges()
        self.window.toast(
            tr("add_favorite") if favorite else tr("remove_favorite"))

    # --------------------------------------------------------------- playback
    def load(self, book) -> None:
        self._load_generation += 1
        generation = self._load_generation
        self.book = book
        self._update_favorite_button()
        self.title.set_label(f"{book.title} — {book.author_string}")
        self._reset()  # nowa książka zawsze zaczyna się od początku
        self.slider.set_value(0)
        self.time_label.set_label("0:00 / 0:00")
        self.status.set_label("")
        if self.player is None:
            return
        if book.local_path and Path(book.local_path).exists():
            self._set_uri(book.local_path)
            return
        if not book.download_url:
            self.status.set_label("Brak pliku audio do odtworzenia.")
            return

        self._stream_url = ""
        self._fallback_used = False
        self.status.set_label("Łączenie ze źródłem audio…")
        self.window.library.add_result(book)

        def resolve():
            try:
                from ...core.downloader import resolve_download
                url, filename, reason = resolve_download(book)
                if not url:
                    GLib.idle_add(self._download_failed, reason, generation)
                else:
                    GLib.idle_add(self._start_stream, url, filename, generation)
            except Exception as exc:  # noqa: BLE001
                GLib.idle_add(self._download_failed, str(exc), generation)

        threading.Thread(target=resolve, daemon=True).start()

    def _start_stream(self, url: str, filename: str, generation: int) -> bool:
        if generation != self._load_generation or self.window.stack.get_visible_child() is not self:
            return False
        if not url:
            self.status.set_label("Brak adresu pliku audio.")
            return False
        self._stream_url = url
        self._stream_filename = filename
        self.status.set_label("Ładowanie strumienia audio…")
        self._set_uri(url)
        if self.player is not None:
            result = self.player.set_state(Gst.State.PLAYING)
            if result == Gst.StateChangeReturn.FAILURE:
                self._fallback_used = True
                self._download_and_play()
            else:
                self.status.set_label("Odtwarzanie…")
                self._set_play_button(playing=True)
        return False

    def _download_and_play(self) -> None:
        """Fallback for sources that GStreamer cannot stream directly."""
        generation = self._load_generation
        book = self.book
        url = getattr(self, "_stream_url", "")
        filename = getattr(self, "_stream_filename", "")
        if book is None:
            return
        self.status.set_label("Pobieranie audiobooka…")

        def worker():
            try:
                from ...core.downloader import DownloadManager
                if not url:
                    raise RuntimeError("brak adresu")
                dm = DownloadManager()
                task = dm.enqueue(
                    url, filename=filename or f"{book.id}.mp3",
                    book_id=book.id, destination_dir=user_imports_dir(),
                )
                for _ in range(600):
                    if task.state in ("done", "error", "cancelled"):
                        break
                    time.sleep(0.1)
                if not task.path or not task.path.exists():
                    raise RuntimeError(task.error or "pobieranie nie udało się")
                if generation != self._load_generation:
                    return
                path = str(task.path)
                book.local_path = path
                self.window.library.set_local_path(
                    book.id, path, task.path.stat().st_size)
                GLib.idle_add(self._download_done, path, generation)
            except Exception as exc:  # noqa: BLE001
                GLib.idle_add(self._download_failed, str(exc), generation)

        threading.Thread(target=worker, daemon=True).start()

    def _download_done(self, path: str, generation: int) -> bool:
        if generation != self._load_generation:
            return False
        self._set_uri(path)
        # Do not start audio if the user already left the player view while
        # the file was downloading.
        if self.window.stack.get_visible_child() is not self:
            self.status.set_label("Gotowe — naciśnij Odtwarzaj przy ponownym wejściu.")
            return False
        self.status.set_label("Odtwarzanie…")
        if self.player is not None:
            result = self.player.set_state(Gst.State.PLAYING)
            if result == Gst.StateChangeReturn.FAILURE:
                self.status.set_label("Nie udało się uruchomić odtwarzania audio.")
            else:
                self._set_play_button(playing=True)
        return False

    def _download_failed(self, message: str, generation: int) -> bool:
        if generation != self._load_generation:
            return False
        self.status.set_label(f"Nie udało się pobrać: {message}")
        return False

    def _set_uri(self, path: str) -> None:
        if self.player is None:
            return
        text = str(path)
        if text.startswith(("http://", "https://")):
            self.player.set_property("uri", text)
        else:
            self.player.set_property("uri", Path(path).resolve().as_uri())

    def _toggle_play(self, *_args) -> None:
        if self.player is None:
            return
        state = self.player.get_state(Gst.CLOCK_TIME_NONE)[1]
        if state == Gst.State.PLAYING:
            self.player.set_state(Gst.State.PAUSED)
            self._set_play_button(playing=False)
        else:
            self.player.set_state(Gst.State.PLAYING)
            self._set_play_button(playing=True)

    def _set_play_button(self, playing: bool) -> None:
        icon_name = (
            "media-playback-pause-symbolic" if playing
            else "media-playback-start-symbolic"
        )
        label = tr("pause") if playing else tr("listen")
        self.play_btn.set_child(_icon_content(icon_name, label))
        self.play_btn.set_tooltip_text(label)

    def _stop(self, *_args) -> None:
        """Przycisk Stop: wstrzymaj odtwarzanie, ale ZACHOWAJ pozycję.

        Użycie Gst.State.NULL zwalnia potok i cofa odtwarzanie do 0 sekundy.
        PAUSED zatrzymuje dźwięk w miejscu, więc kolejne kliknięcie
        „Odtwarzaj" wznawia ścieżkę od miejsca zatrzymania.
        """
        if self.player is not None:
            self.player.set_state(Gst.State.PAUSED)
        self._set_play_button(playing=False)

    def _reset(self) -> None:
        """Pełne wyzerowanie odtwarzacza (nowa książka, wyjście, błąd, koniec)."""
        if self.player is not None:
            self.player.set_state(Gst.State.NULL)
        self._set_play_button(playing=False)

    def stop_playback(self) -> None:
        """Called when leaving the player view - no audio in the background."""
        self._load_generation += 1
        self._reset()  # wychodząc z widoku nie zachowujemy pozycji
        self.status.set_label("")

    def stop_and_go_back(self) -> None:
        self.window.go_back()

    def _on_seek(self, slider) -> None:
        if self.player is None:
            return
        ok, duration = self.player.query_duration(Gst.Format.TIME)
        if not ok or duration <= 0 or self._seeking:
            return
        target = int((slider.get_value() / 100) * duration)
        event = Gst.Event.new_seek(
            1.0, Gst.Format.TIME,
            Gst.SeekFlags.FLUSH | Gst.SeekFlags.KEY_UNIT,
            Gst.SeekType.SET, target, Gst.SeekType.NONE, 0,
        )
        self.player.send_event(event)

    def _seek_by(self, seconds: int) -> None:
        if self.player is None:
            return
        ok, position = self.player.query_position(Gst.Format.TIME)
        if not ok:
            return
        ok, duration = self.player.query_duration(Gst.Format.TIME)
        if not ok or duration <= 0:
            return
        target = max(0, min(duration, position + seconds * Gst.SECOND))
        rate = [0.75, 1.0, 1.25, 1.5, 2.0][self.speed.get_selected()]
        event = Gst.Event.new_seek(
            rate, Gst.Format.TIME,
            Gst.SeekFlags.FLUSH | Gst.SeekFlags.KEY_UNIT,
            Gst.SeekType.SET, target, Gst.SeekType.NONE, 0,
        )
        self.player.send_event(event)

    def _on_speed(self, dropdown, _param) -> None:
        if self.player is None:
            return
        rates = [0.75, 1.0, 1.25, 1.5, 2.0]
        rate = rates[dropdown.get_selected()]
        ok, position = self.player.query_position(Gst.Format.TIME)
        position = position if ok else 0
        event = Gst.Event.new_seek(
            rate, Gst.Format.TIME,
            Gst.SeekFlags.FLUSH | Gst.SeekFlags.ACCUMULATE,
            Gst.SeekType.SET, position, Gst.SeekType.NONE, 0,
        )
        self.player.send_event(event)

    def _on_volume(self, slider) -> None:
        if self.player is not None:
            self.player.set_property("volume", slider.get_value() / 100.0)

    def _on_bus_message(self, _bus, message) -> None:
        if message.type == Gst.MessageType.EOS:
            self._reset()
        elif message.type == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            if getattr(self, "_stream_url", "") and not getattr(self, "_fallback_used", False):
                # Streaming failed - try downloading the file locally instead.
                self._fallback_used = True
                self._download_and_play()
                return
            self.window.toast(f"{tr('error')}: {err.message}")
            self._reset()

    def _update_position(self) -> bool:
        self._seeking = True
        if self.player is not None:
            ok, duration = self.player.query_duration(Gst.Format.TIME)
            ok2, position = self.player.query_position(Gst.Format.TIME)
            if ok and duration > 0:
                self.slider.set_range(0, 100)
                self.slider.set_value((position / duration) * 100)
                self.time_label.set_label(
                    f"{human_duration(position // Gst.SECOND)} / "
                    f"{human_duration(duration // Gst.SECOND)}"
                )
        self._seeking = False
        return True
