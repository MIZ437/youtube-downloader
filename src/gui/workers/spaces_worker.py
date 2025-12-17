"""
Xスペースダウンロード用ワーカースレッド
"""

import os
import sys
import logging
from typing import Optional

from PyQt6.QtCore import QThread, pyqtSignal

from src.gui.utils import BYTES_PER_SECOND, DOWNLOAD_TIMEOUT_SECONDS, format_duration

logger = logging.getLogger(__name__)


class SpacesDownloadWorker(QThread):
    """Xスペースダウンロード用ワーカースレッド（複数URL対応）"""
    progress = pyqtSignal(dict)
    item_progress = pyqtSignal(int, int, str)  # current_index, total, url
    finished = pyqtSignal(list)  # 結果リスト
    error = pyqtSignal(str)

    def __init__(self, urls: list, output_dir: str, options: dict):
        super().__init__()
        self.urls = urls  # URLリスト
        self.output_dir = output_dir
        self.options = options
        self._cancel_flag = False
        self._subprocess_pid: Optional[int] = None  # 子プロセスのPID
        self._download_start_time = None
        self._duration = 0  # 再生時間（秒）
        self._ydl = None  # yt-dlpインスタンス
        self._current_index = 0
        self._total_urls = len(urls)

    def cancel(self):
        """キャンセルフラグを設定"""
        logger.info("Download cancellation requested")
        self._cancel_flag = True

    def force_stop(self):
        """強制停止（自プロセスのみ終了）"""
        logger.info("Force stop requested")
        self._cancel_flag = True

        # 特定の子プロセスのみ終了（全FFmpegを殺さない）
        if self._subprocess_pid:
            try:
                import subprocess
                if sys.platform == 'win32':
                    # 特定のPIDのプロセスツリーを終了
                    subprocess.run(
                        ['taskkill', '/F', '/T', '/PID', str(self._subprocess_pid)],
                        capture_output=True,
                        creationflags=subprocess.CREATE_NO_WINDOW
                    )
                    logger.info(f"Terminated subprocess PID: {self._subprocess_pid}")
            except Exception as e:
                logger.warning(f"Failed to terminate subprocess: {e}")

    def _track_subprocess(self):
        """子プロセスのPIDを追跡"""
        try:
            import psutil
            current_process = psutil.Process()
            children = current_process.children(recursive=True)
            for child in children:
                if 'ffmpeg' in child.name().lower():
                    self._subprocess_pid = child.pid
                    logger.debug(f"Tracking FFmpeg subprocess PID: {self._subprocess_pid}")
                    break
        except ImportError:
            # psutilがない場合はスキップ
            pass
        except Exception as e:
            logger.debug(f"Could not track subprocess: {e}")

    def run(self):
        import yt_dlp

        logger.info(f"Starting download for {self._total_urls} URLs")

        results = []  # ダウンロード結果リスト

        def progress_hook(d):
            if self._cancel_flag:
                raise Exception("ダウンロードがキャンセルされました")

            # 子プロセス追跡（ダウンロード中に定期的に確認）
            self._track_subprocess()

            status = d.get('status', '')
            info = {'status': status}

            if status == 'downloading':
                downloaded = d.get('downloaded_bytes', 0)
                total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                speed = d.get('speed', 0)
                eta = d.get('eta', 0)

                # ETAが不明な場合、再生時間とビットレートから推定
                if (not eta or eta <= 0) and self._duration > 0 and speed and speed > 0:
                    estimated_total = self._duration * BYTES_PER_SECOND
                    remaining_bytes = max(0, estimated_total - downloaded)
                    eta = int(remaining_bytes / speed) if speed > 0 else 0

                # 進捗率も再計算
                percent = 0
                if total > 0:
                    percent = (downloaded / total * 100)
                elif self._duration > 0:
                    estimated_total = self._duration * BYTES_PER_SECOND
                    percent = min(99, (downloaded / estimated_total * 100))

                info.update({
                    'downloaded': downloaded,
                    'total': total,
                    'speed': speed,
                    'eta': eta,
                    'percent': percent,
                    'duration': self._duration
                })
            elif status == 'finished':
                info['message'] = '音声変換中...'

            self.progress.emit(info)

        try:
            if not os.path.exists(self.output_dir):
                os.makedirs(self.output_dir)

            # FFmpegパス設定
            from src.downloader import get_ffmpeg_path
            ffmpeg_path = get_ffmpeg_path()

            # 各URLを順番に処理
            for idx, url in enumerate(self.urls):
                if self._cancel_flag:
                    break

                self._current_index = idx + 1
                self.item_progress.emit(self._current_index, self._total_urls, url)

                logger.info(f"Processing URL {self._current_index}/{self._total_urls}: {url}")

                try:
                    # ステップ1: 情報取得（ダウンロードなし）
                    self.progress.emit({
                        'status': 'extracting',
                        'message': f'[{self._current_index}/{self._total_urls}] スペース情報を取得中...'
                    })

                    extract_opts = {
                        'quiet': True,
                        'no_warnings': True,
                    }
                    if ffmpeg_path:
                        extract_opts['ffmpeg_location'] = ffmpeg_path

                    with yt_dlp.YoutubeDL(extract_opts) as ydl:
                        info = ydl.extract_info(url, download=False)

                    if not info:
                        results.append(f"ERROR: {url} - 情報を取得できませんでした")
                        continue

                    # タイトルと再生時間を取得
                    title = info.get('title', 'Unknown')

                    # 再生時間を複数のフィールドから取得を試みる
                    duration = info.get('duration', 0)
                    if not duration:
                        formats = info.get('formats', [])
                        for fmt in formats:
                            if fmt.get('duration'):
                                duration = fmt.get('duration')
                                break
                    if not duration:
                        req_formats = info.get('requested_formats', [])
                        for fmt in req_formats:
                            if fmt.get('duration'):
                                duration = fmt.get('duration')
                                break
                    if not duration:
                        fragments = info.get('fragments', [])
                        if fragments:
                            duration = sum(f.get('duration', 0) for f in fragments if f.get('duration'))

                    self._duration = duration

                    duration_str = format_duration(duration) if duration else ""
                    estimated_size_mb = (duration * BYTES_PER_SECOND) / (1024 * 1024) if duration else 0

                    if not estimated_size_mb:
                        filesize = info.get('filesize') or info.get('filesize_approx', 0)
                        if filesize:
                            estimated_size_mb = filesize / (1024 * 1024)

                    self.progress.emit({
                        'status': 'info_ready',
                        'message': f'[{self._current_index}/{self._total_urls}] 取得完了: {title}' + (f' ({duration_str})' if duration_str else ''),
                        'title': title,
                        'duration': duration,
                        'estimated_size_mb': estimated_size_mb,
                        'duration_unknown': not bool(duration)
                    })

                    # ステップ2: ダウンロード開始
                    self.progress.emit({
                        'status': 'starting',
                        'message': f'[{self._current_index}/{self._total_urls}] ダウンロード開始...'
                    })
                    logger.info(f"Starting download phase for: {title}")

                    ydl_opts = {
                        'outtmpl': os.path.join(self.output_dir, '%(title)s.%(ext)s'),
                        'progress_hooks': [progress_hook],
                        'quiet': True,
                        'no_warnings': True,
                        'socket_timeout': DOWNLOAD_TIMEOUT_SECONDS,
                        'retries': 3,
                    }

                    if ffmpeg_path:
                        ydl_opts['ffmpeg_location'] = ffmpeg_path

                    # 音声フォーマット設定
                    audio_format = self.options.get('audio_format', 'mp3')
                    if audio_format != 'original':
                        ydl_opts['postprocessors'] = [{
                            'key': 'FFmpegExtractAudio',
                            'preferredcodec': audio_format,
                            'preferredquality': '320',
                        }]

                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        ydl.download([url])

                        # ファイル名を生成
                        filename = ydl.prepare_filename(info)
                        if audio_format != 'original':
                            base = os.path.splitext(filename)[0]
                            filename = f"{base}.{audio_format}"

                        logger.info(f"Download completed: {filename}")
                        results.append(filename)

                except yt_dlp.utils.DownloadError as e:
                    error_msg = str(e)
                    logger.error(f"Download error for {url}: {error_msg}")
                    if "Unsupported URL" in error_msg:
                        results.append(f"ERROR: {url} - このURLはサポートされていません")
                    elif "Private" in error_msg or "protected" in error_msg.lower():
                        results.append(f"ERROR: {url} - このスペースは非公開です")
                    elif "not available" in error_msg.lower():
                        results.append(f"ERROR: {url} - このスペースは利用できません")
                    else:
                        results.append(f"ERROR: {url} - {error_msg}")
                except Exception as e:
                    logger.error(f"Unexpected error for {url}: {e}")
                    results.append(f"ERROR: {url} - {str(e)}")

            # 全件処理完了
            self.finished.emit(results)

        except Exception as e:
            logger.error(f"Critical error: {e}")
            self.error.emit(str(e))
        finally:
            # リソースクリーンアップ
            self._subprocess_pid = None
