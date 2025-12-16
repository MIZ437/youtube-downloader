"""
セットアップダイアログ
FFmpegのダウンロードと初期設定を行う
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QProgressBar, QPushButton,
    QMessageBox, QHBoxLayout
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

from src.setup_ffmpeg import is_ffmpeg_installed, setup_ffmpeg, setup_ffmpeg_path


class FFmpegSetupWorker(QThread):
    """FFmpegセットアップ用ワーカー"""
    progress = pyqtSignal(int, int)  # downloaded, total
    status = pyqtSignal(str)
    finished = pyqtSignal(bool)

    def run(self):
        try:
            self.status.emit("FFmpegをダウンロード中...")
            result = setup_ffmpeg(
                download_callback=lambda d, t: self.progress.emit(d, t),
                extract_callback=lambda msg: self.status.emit(msg)
            )
            self.finished.emit(result)
        except Exception as e:
            self.status.emit(f"エラー: {str(e)}")
            self.finished.emit(False)


class SetupDialog(QDialog):
    """初回セットアップダイアログ"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("初回セットアップ")
        self.setFixedSize(450, 200)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        self.worker = None
        self.setup_success = False
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # 説明
        info_label = QLabel(
            "YouTube Downloaderを使用するにはFFmpegが必要です。\n"
            "自動的にダウンロードしてセットアップします。"
        )
        info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(info_label)

        # ステータス
        self.status_label = QLabel("準備完了")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)

        # プログレスバー
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        # ボタン
        button_layout = QHBoxLayout()

        self.setup_btn = QPushButton("セットアップ開始")
        self.setup_btn.setMinimumHeight(35)
        self.setup_btn.clicked.connect(self.start_setup)
        button_layout.addWidget(self.setup_btn)

        self.skip_btn = QPushButton("スキップ")
        self.skip_btn.setMinimumHeight(35)
        self.skip_btn.clicked.connect(self.skip_setup)
        button_layout.addWidget(self.skip_btn)

        layout.addLayout(button_layout)

    def start_setup(self):
        """セットアップ開始"""
        self.setup_btn.setEnabled(False)
        self.skip_btn.setEnabled(False)
        self.progress_bar.setValue(0)

        self.worker = FFmpegSetupWorker()
        self.worker.progress.connect(self.on_progress)
        self.worker.status.connect(self.on_status)
        self.worker.finished.connect(self.on_finished)
        self.worker.start()

    def on_progress(self, downloaded, total):
        """進捗更新"""
        if total > 0:
            percent = int(downloaded / total * 100)
            self.progress_bar.setValue(percent)
            mb_downloaded = downloaded / 1024 / 1024
            mb_total = total / 1024 / 1024
            self.status_label.setText(f"ダウンロード中... {mb_downloaded:.1f}MB / {mb_total:.1f}MB")

    def on_status(self, status):
        """ステータス更新"""
        self.status_label.setText(status)

    def on_finished(self, success):
        """完了処理"""
        self.setup_success = success
        if success:
            self.progress_bar.setValue(100)
            self.status_label.setText("セットアップ完了!")
            QMessageBox.information(self, "完了", "FFmpegのセットアップが完了しました。")
            self.accept()
        else:
            self.setup_btn.setEnabled(True)
            self.skip_btn.setEnabled(True)
            QMessageBox.warning(
                self, "エラー",
                "FFmpegのセットアップに失敗しました。\n"
                "インターネット接続を確認してください。\n\n"
                "手動でFFmpegをインストールすることもできます。"
            )

    def skip_setup(self):
        """スキップ"""
        reply = QMessageBox.question(
            self, "確認",
            "FFmpegがないと動画のダウンロードに失敗する場合があります。\n"
            "本当にスキップしますか?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.reject()


def check_and_setup_ffmpeg(parent=None) -> bool:
    """FFmpegをチェックし、必要ならセットアップダイアログを表示"""
    if is_ffmpeg_installed():
        setup_ffmpeg_path()
        return True

    dialog = SetupDialog(parent)
    result = dialog.exec()

    return dialog.setup_success or result == QDialog.DialogCode.Accepted
