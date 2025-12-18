"""
文字起こし用ワーカースレッド
"""

import logging
from typing import Union, List

from PyQt6.QtCore import QThread, pyqtSignal

from src.transcriber import Transcriber, TranscriptResult

logger = logging.getLogger(__name__)


class TranscribeWorker(QThread):
    """文字起こし用ワーカースレッド（複数ファイル対応）"""
    progress = pyqtSignal(dict)
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, transcriber: Transcriber, url_or_path: Union[str, List[str]], options: dict):
        super().__init__()
        self.transcriber = transcriber
        self.url_or_path = url_or_path
        self.options = options

    def run(self):
        try:
            self.transcriber.set_progress_callback(lambda d: self.progress.emit(d))

            # カスタム辞書を取得
            custom_vocabulary = self.options.get('custom_vocabulary', '')

            # 複数ファイル/URL対応
            items = self.url_or_path if isinstance(self.url_or_path, list) else [self.url_or_path]
            results = []

            for i, item in enumerate(items):
                self.progress.emit({
                    'status': 'processing',
                    'message': f'処理中... ({i+1}/{len(items)})',
                    'percent': (i / len(items)) * 100
                })

                if self.options.get('is_file', False):
                    result = self.transcriber.transcribe_audio(
                        item,
                        language=self.options.get('language', 'ja'),
                        model_name=self.options.get('model', 'base'),
                        custom_vocabulary=custom_vocabulary
                    )
                else:
                    result = self.transcriber.transcribe_youtube(
                        item,
                        language=self.options.get('language', 'ja'),
                        model_name=self.options.get('model', 'base'),
                        prefer_youtube_subtitles=self.options.get('prefer_youtube', True)
                    )
                results.append(result)

            # 単一ファイルの場合はそのまま返す、複数の場合は最初の結果を返す
            # TODO: 将来的には複数結果を統合するUIが必要
            if len(results) == 1:
                self.finished.emit(results[0])
            else:
                # 複数結果を結合（将来的には改善が必要）
                combined = self._combine_results(results)
                self.finished.emit(combined)

        except Exception as e:
            logger.error(f"Transcription error: {e}")
            self.error.emit(str(e))
        finally:
            # メモリリーク対策: コールバックをクリア
            self.transcriber.set_progress_callback(None)

    def _combine_results(self, results: List[TranscriptResult]) -> TranscriptResult:
        """複数の結果を結合"""
        if not results:
            raise ValueError("No results to combine")

        combined_segments = []
        for result in results:
            combined_segments.extend(result.segments)

        return TranscriptResult(
            video_title=f"{results[0].video_title} 他{len(results)-1}件" if len(results) > 1 else results[0].video_title,
            video_id=results[0].video_id,
            language=results[0].language,
            segments=combined_segments,
            source=results[0].source
        )
