"""
タブモジュール
各タブのウィジェットを提供
"""

from src.gui.tabs.download_tab import DownloadTab
from src.gui.tabs.playlist_tab import PlaylistTab
from src.gui.tabs.spaces_tab import SpacesTab
from src.gui.tabs.transcribe_tab import TranscribeTab

__all__ = [
    'DownloadTab',
    'PlaylistTab',
    'SpacesTab',
    'TranscribeTab',
]
