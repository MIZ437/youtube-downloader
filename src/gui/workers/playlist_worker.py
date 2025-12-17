"""
再生リスト取得用ワーカースレッド
"""

from PyQt6.QtCore import QThread, pyqtSignal

from src.downloader import YouTubeDownloader, PlaylistFilter


class PlaylistFetchWorker(QThread):
    """再生リスト取得用ワーカースレッド"""
    progress = pyqtSignal(int, int)
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, downloader: YouTubeDownloader, url: str, filter_options: PlaylistFilter):
        super().__init__()
        self.downloader = downloader
        self.url = url
        self.filter_options = filter_options

    def run(self):
        try:
            videos = self.downloader.get_playlist_info(
                self.url,
                self.filter_options,
                lambda c, t: self.progress.emit(c, t)
            )
            self.finished.emit(videos)
        except Exception as e:
            self.error.emit(str(e))
