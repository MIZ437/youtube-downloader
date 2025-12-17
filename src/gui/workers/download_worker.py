"""
ダウンロード用ワーカースレッド
"""

from PyQt6.QtCore import QThread, pyqtSignal

from src.downloader import YouTubeDownloader


class DownloadWorker(QThread):
    """ダウンロード用ワーカースレッド"""
    progress = pyqtSignal(dict)
    item_progress = pyqtSignal(int, int, str)
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, downloader: YouTubeDownloader, urls: list, options: dict):
        super().__init__()
        self.downloader = downloader
        self.urls = urls
        self.options = options

    def run(self):
        try:
            self.downloader.set_progress_callback(lambda d: self.progress.emit(d))

            results = self.downloader.download_batch(
                self.urls,
                format_option=self.options.get('format', 'best'),
                audio_only=self.options.get('audio_only', False),
                subtitle=self.options.get('subtitle', False),
                item_callback=lambda i, t, u: self.item_progress.emit(i, t, u)
            )
            self.finished.emit(results)
        except Exception as e:
            self.error.emit(str(e))
