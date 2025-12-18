"""
文字起こし用ワーカースレッド
"""

from PyQt6.QtCore import QThread, pyqtSignal

from src.transcriber import Transcriber


class TranscribeWorker(QThread):
    """文字起こし用ワーカースレッド"""
    progress = pyqtSignal(dict)
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, transcriber: Transcriber, url_or_path: str, options: dict):
        super().__init__()
        self.transcriber = transcriber
        self.url_or_path = url_or_path
        self.options = options

    def run(self):
        try:
            self.transcriber.set_progress_callback(lambda d: self.progress.emit(d))

            # カスタム辞書を取得
            custom_vocabulary = self.options.get('custom_vocabulary', '')

            if self.options.get('is_file', False):
                result = self.transcriber.transcribe_audio(
                    self.url_or_path,
                    language=self.options.get('language', 'ja'),
                    model_name=self.options.get('model', 'base'),
                    custom_vocabulary=custom_vocabulary
                )
            else:
                result = self.transcriber.transcribe_youtube(
                    self.url_or_path,
                    language=self.options.get('language', 'ja'),
                    model_name=self.options.get('model', 'base'),
                    prefer_youtube_subtitles=self.options.get('prefer_youtube', True)
                )
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))
