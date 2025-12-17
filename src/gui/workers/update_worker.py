"""
yt-dlp更新用ワーカースレッド
"""

import sys
import subprocess

from PyQt6.QtCore import QThread, pyqtSignal


class UpdateYtDlpWorker(QThread):
    """yt-dlp更新用ワーカースレッド"""
    progress = pyqtSignal(str)
    finished = pyqtSignal(bool, str)  # success, message

    def run(self):
        try:
            self.progress.emit("yt-dlpを更新中...")

            # pipでyt-dlpを更新
            result = subprocess.run(
                [sys.executable, '-m', 'pip', 'install', '--upgrade', 'yt-dlp'],
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )

            if result.returncode == 0:
                # バージョン確認
                import yt_dlp
                # モジュールをリロード
                import importlib
                importlib.reload(yt_dlp)
                version = yt_dlp.version.__version__
                self.finished.emit(True, f"yt-dlpを更新しました (v{version})")
            else:
                self.finished.emit(False, f"更新に失敗しました:\n{result.stderr}")
        except Exception as e:
            self.finished.emit(False, f"更新エラー: {str(e)}")
