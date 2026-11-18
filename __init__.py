"""Application views/pages."""

from .home import HomeView
from .results import ResultsView
from .favorites import FavoritesView
from .library_view import LibraryView
from .collections_view import CollectionsView
from .downloads_view import DownloadsView
from .reader import ReaderView
from .audiobook_player import AudiobookPlayer
from .settings_view import SettingsView
from .about import AboutDialog

__all__ = [
    "HomeView", "ResultsView", "FavoritesView", "LibraryView",
    "CollectionsView", "DownloadsView", "ReaderView", "AudiobookPlayer",
    "SettingsView", "AboutDialog",
]
